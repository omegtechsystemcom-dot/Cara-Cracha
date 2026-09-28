"""
API Flask para servir o frontend web e processar requisições.
"""
import logging
import base64
import hashlib
import io
import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from flask import Flask, request, jsonify, send_file, send_from_directory
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

from .config import BASE_DIR, DIRS, EXTENSOES_PLANILHA, FORMATOS_SAIDA
from . import __version__
from .estado import carregar_estado_planilha, salvar_estado_planilha
from .planilha_reader import PlanilhaReader
from .montador import MontadorCracha
from .exportador import ExportadorCracha
from .models import ConfiguracaoCracha
from .qr_generator import QRCodeGenerator
from .integridade import auditar_fotos, contar_arquivos_foto
from .utils import (
    Diagnosticador,
    criar_backup,
    criar_arquivo_exemplo,
    validar_backup,
)

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
if CORS is not None:
    CORS(app, origins=["http://127.0.0.1:5000", "http://localhost:5000"])

# Estado da aplicação (em memória)
app_state = {
    "alunos": [],
    "turmas": {},
    "planilha_carregada": None,
    "planilha_confirmada_em": None,
    "importacoes_pendentes": {},
}

# Caminho padrão da planilha IEMA
PLANILHA_PADRAO = BASE_DIR / "alunosiema.xlsx"
EXTENSOES_FOTO = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}


@app.after_request
def adicionar_cabecalhos_seguranca(resposta):
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    resposta.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    return resposta


def _serializar_aluno(aluno):
    return {
        "codigo": aluno.matricula,
        "matricula": aluno.matricula,
        "nome": aluno.nome,
        "turma": aluno.turma,
        "curso": aluno.curso,
        "observacao": aluno.observacao,
    }


def _ativar_planilha(caminho: Path, alunos=None, reader=None):
    reader = reader or PlanilhaReader(caminho)
    alunos = alunos if alunos is not None else reader.ler()
    turmas = reader.agrupar_por_turma(alunos)
    estado = salvar_estado_planilha(caminho)
    app_state["alunos"] = alunos
    app_state["turmas"] = turmas
    app_state["planilha_carregada"] = str(Path(caminho).resolve())
    app_state["planilha_confirmada_em"] = estado["confirmada_em"]
    return turmas


def _restaurar_estado_inicial():
    restaurado = carregar_estado_planilha()
    if not restaurado:
        return
    alunos, turmas, estado = restaurado
    app_state["alunos"] = alunos
    app_state["turmas"] = turmas
    app_state["planilha_carregada"] = estado["planilha"]
    app_state["planilha_confirmada_em"] = estado.get("confirmada_em")


def _limpar_importacoes_pendentes():
    """Remove uploads órfãos de uma execução anterior do servidor."""
    pasta = DIRS["IMPORTACOES_PENDENTES"]
    if not pasta.is_dir():
        return
    for arquivo in pasta.iterdir():
        if arquivo.is_file():
            arquivo.unlink(missing_ok=True)


_limpar_importacoes_pendentes()
_restaurar_estado_inicial()


def _validar_codigos_qr(alunos):
    """Retorna inconsistencias que impedem QRs univocos."""
    sem_codigo = []
    por_codigo = {}
    for aluno in alunos:
        codigo = QRCodeGenerator.normalizar_codigo(aluno.matricula)
        if not codigo:
            sem_codigo.append(aluno.nome)
            continue
        por_codigo.setdefault(codigo, []).append(aluno.nome)

    duplicados = {
        codigo: nomes for codigo, nomes in por_codigo.items() if len(nomes) > 1
    }
    return sem_codigo, duplicados


def _hash_opcional(caminho) -> str | None:
    if not caminho:
        return None
    arquivo = Path(caminho)
    if not arquivo.is_file():
        return None
    digest = hashlib.sha256()
    with arquivo.open("rb") as stream:
        for bloco in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _carregar_manifesto(pasta: Path) -> dict:
    caminho = pasta / "manifesto.json"
    if caminho.is_file():
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"versao": 1, "turma": pasta.name, "crachas": []}


def _salvar_manifesto(pasta: Path, entradas: list[dict]) -> Path:
    manifesto = _carregar_manifesto(pasta)
    existentes = {
        (item.get("codigo"), item.get("formato")): item
        for item in manifesto.get("crachas", [])
    }
    for entrada in entradas:
        existentes[(entrada["codigo"], entrada["formato"])] = entrada
    manifesto.update({
        "versao": 1,
        "turma": pasta.name,
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        "crachas": sorted(
            existentes.values(), key=lambda item: (item.get("nome", ""), item.get("formato", ""))
        ),
    })
    destino = pasta / "manifesto.json"
    temporario = pasta / ".manifesto.tmp"
    temporario.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(destino)
    return destino


def _reconciliar_turma(turma: str) -> dict:
    alunos = [aluno for aluno in app_state["alunos"] if aluno.turma == turma]
    pasta = DIRS["MONTADOS"] / ExportadorCracha._sanitizar_nome(turma)
    formatos = {".png", ".jpg", ".pdf", ".html"}
    arquivos = []
    if pasta.is_dir():
        arquivos = [
            item for item in pasta.iterdir()
            if item.is_file() and item.suffix.lower() in formatos
            and not (item.suffix.lower() == ".pdf" and item.stem.startswith("Turma_"))
        ]
    esperados = {}
    stems_validos = set()
    for aluno in alunos:
        codigo = ExportadorCracha._sanitizar_nome(
            QRCodeGenerator.normalizar_codigo(aluno.matricula)
        )
        esperados[aluno.matricula] = codigo
        stems_validos.add(codigo)
    stems_atuais = {arquivo.stem for arquivo in arquivos}
    faltantes = [
        {"codigo": aluno.matricula, "nome": aluno.nome}
        for aluno in alunos
        if esperados[aluno.matricula] not in stems_atuais
    ]
    obsoletos = [
        {"arquivo": arquivo.name, "caminho": str(arquivo)}
        for arquivo in arquivos if arquivo.stem not in stems_validos
    ]
    return {
        "turma": turma,
        "total_alunos": len(alunos),
        "total_arquivos": len(arquivos),
        "faltantes": faltantes,
        "obsoletos": obsoletos,
        "total_faltantes": len(faltantes),
        "total_obsoletos": len(obsoletos),
        "valido": not faltantes and not obsoletos,
    }


# ========== ROTAS DA API ==========

@app.route("/api/health")
def health():
    """Health check da API."""
    return jsonify({"status": "ok", "versao": __version__})


@app.route("/api/fotos", methods=["POST"])
def enviar_fotos():
    """Recebe fotos e as disponibiliza para associação automática por nome."""
    arquivos = request.files.getlist("fotos")
    if not arquivos or not any(arquivo.filename for arquivo in arquivos):
        return jsonify({"erro": "Nenhuma foto enviada."}), 400

    salvas = []
    erros = []
    conflitos = []
    substituir = str(request.form.get("substituir", "false")).lower() == "true"
    pasta = DIRS["FOTOS_ALUNOS"]
    pasta.mkdir(parents=True, exist_ok=True)

    for arquivo in arquivos:
        nome = secure_filename(arquivo.filename or "")
        extensao = Path(nome).suffix.lower()
        if not nome or extensao not in EXTENSOES_FOTO:
            erros.append({"arquivo": arquivo.filename, "erro": "Formato de imagem não aceito."})
            continue

        conteudo = arquivo.read()
        try:
            Image.open(io.BytesIO(conteudo)).verify()
        except (UnidentifiedImageError, OSError):
            erros.append({"arquivo": arquivo.filename, "erro": "Arquivo de imagem inválido."})
            continue

        destino = pasta / nome
        if destino.exists() and not substituir:
            conflitos.append(nome)
            erros.append({"arquivo": arquivo.filename, "erro": "Arquivo já existe."})
            continue
        destino.write_bytes(conteudo)
        salvas.append(nome)

    if not salvas:
        status = 409 if conflitos else 400
        return jsonify({
            "erro": "Nenhuma foto foi salva.",
            "erros": erros,
            "conflitos": conflitos,
        }), status

    return jsonify({
        "total_salvas": len(salvas),
        "fotos": salvas,
        "erros": erros,
        "conflitos": conflitos,
        "pasta": str(pasta),
    })


@app.route("/api/planilha-padrao", methods=["POST"])
def carregar_planilha_padrao():
    """Carrega automaticamente a planilha padrão do IEMA."""
    caminho = PLANILHA_PADRAO
    if not caminho.exists():
        return jsonify({"erro": f"Planilha padrão não encontrada: {caminho}"}), 404

    try:
        reader = PlanilhaReader(caminho)
        colunas = reader.listar_colunas()
        alunos = reader.ler()

        # Preview (primeiros 10)
        preview = []
        for a in alunos[:10]:
            preview.append({
                "nome": a.nome,
                "turma": a.turma,
                "curso": a.curso,
                "matricula": a.matricula,
            })

        turmas = reader.agrupar_por_turma(alunos)

        _ativar_planilha(caminho, alunos=alunos, reader=reader)

        return jsonify({
            "total_alunos": len(alunos),
            "total_turmas": len(turmas),
            "colunas_detectadas": reader.colunas_mapeadas,
            "colunas_planilha": colunas,
            "turmas": {nome: len(t.alunos) for nome, t in turmas.items()},
            "preview": preview,
            "arquivo": str(caminho),
        })
    except Exception as e:
        logger.error(f"Erro ao ler planilha padrão: {e}")
        return jsonify({"erro": str(e)}), 400


@app.route("/api/diagnostico")
def diagnostico():
    """Retorna diagnóstico completo do sistema."""
    diag = Diagnosticador()
    estrutura = diag.verificar_estrutura()
    turmas = diag.listar_turmas_disponiveis()
    crachas = diag.listar_crachas_montados()
    turmas_ativas = sorted(app_state["turmas"])
    reconciliacao = [
        _reconciliar_turma(turma) for turma in turmas_ativas
    ] if app_state["alunos"] else []

    return jsonify({
        "estrutura": {k: v for k, v in estrutura.items()},
        "turmas": turmas_ativas or turmas,
        "crachas_montados": crachas,
        "total_crachas": len(crachas),
        "total_alunos": len(app_state["alunos"]),
        "total_turmas": len(turmas_ativas),
        "planilha_carregada": app_state["planilha_carregada"],
        "planilha_confirmada_em": app_state["planilha_confirmada_em"],
        "reconciliacao": reconciliacao,
        "total_faltantes": sum(len(item["faltantes"]) for item in reconciliacao),
        "total_obsoletos": sum(len(item["obsoletos"]) for item in reconciliacao),
    })


@app.route("/api/planilha/colunas", methods=["POST"])
def preview_planilha():
    """Cria uma importação pendente sem alterar a planilha ativa."""
    arquivo = request.files.get("arquivo")
    if not arquivo:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    caminho = None
    try:
        upload_id = uuid.uuid4().hex
        caminho = _salvar_temporario(arquivo, upload_id)
        reader = PlanilhaReader(caminho)
        colunas = reader.listar_colunas()
        alunos = reader.ler()

        # Preview (primeiros 10)
        preview = []
        for a in alunos[:10]:
            preview.append({
                "nome": a.nome,
                "turma": a.turma,
                "curso": a.curso,
                "matricula": a.matricula,
                "tem_foto": a.foto_caminho is not None,
                "tem_qr": a.qr_code_dados is not None,
            })

        # Turmas detectadas
        turmas = reader.agrupar_por_turma(alunos)
        turmas_info = {
            nome: len(t.alunos)
            for nome, t in turmas.items()
        }

        app_state["importacoes_pendentes"][upload_id] = {
            "caminho": caminho,
            "alunos": alunos,
            "turmas": turmas,
            "reader": reader,
        }

        return jsonify({
            "total_alunos": len(alunos),
            "total_turmas": len(turmas),
            "colunas_detectadas": reader.colunas_mapeadas,
            "colunas_planilha": colunas,
            "turmas": {nome: len(t.alunos) for nome, t in turmas.items()},
            "preview": preview,
            "upload_id": upload_id,
        })
    except Exception as e:
        if caminho:
            Path(caminho).unlink(missing_ok=True)
        logger.error(f"Erro ao ler planilha: {e}")
        return jsonify({"erro": str(e)}), 400


@app.route("/api/planilha/confirmar", methods=["POST"])
def confirmar_planilha():
    """Promove uma importação pendente para planilha ativa."""
    upload_id = str((request.get_json() or {}).get("upload_id", "")).strip()
    pendente = app_state["importacoes_pendentes"].pop(upload_id, None)
    if not pendente:
        return jsonify({"erro": "Importação pendente não encontrada ou expirada."}), 404

    sem_codigo, duplicados = _validar_codigos_qr(pendente["alunos"])
    if sem_codigo or duplicados:
        app_state["importacoes_pendentes"][upload_id] = pendente
        return jsonify({
            "erro": "A planilha possui códigos vazios ou duplicados.",
            "sem_codigo": sem_codigo,
            "codigos_duplicados": duplicados,
        }), 400

    origem = Path(pendente["caminho"])
    destino = DIRS["PLANILHAS"] / f"planilha_{upload_id}{origem.suffix.lower()}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    origem.replace(destino)
    reader = PlanilhaReader(destino)
    alunos = reader.ler()
    turmas = _ativar_planilha(destino, alunos=alunos, reader=reader)
    return jsonify({
        "sucesso": True,
        "total": len(alunos),
        "total_turmas": len(turmas),
        "alunos": [_serializar_aluno(aluno) for aluno in alunos],
        "turmas": {nome: len(turma.alunos) for nome, turma in turmas.items()},
        "arquivo": str(destino),
    })


@app.route("/api/planilha/cancelar", methods=["POST"])
def cancelar_planilha():
    """Descarta uma importação pendente sem alterar a base ativa."""
    upload_id = str((request.get_json() or {}).get("upload_id", "")).strip()
    pendente = app_state["importacoes_pendentes"].pop(upload_id, None)
    if pendente:
        Path(pendente["caminho"]).unlink(missing_ok=True)
    return jsonify({"sucesso": True, "cancelada": bool(pendente)})


@app.route("/api/alunos")
def listar_alunos():
    """Retorna lista de alunos carregados."""
    turma_filtro = request.args.get("turma", "")
    busca = request.args.get("busca", "").lower()

    alunos = app_state["alunos"]
    if turma_filtro:
        alunos = [a for a in alunos if a.turma == turma_filtro]
    if busca:
        alunos = [a for a in alunos if busca in a.nome.lower() or busca in a.matricula.lower()]

    return jsonify({
        "total": len(alunos),
        "alunos": [_serializar_aluno(aluno) for aluno in alunos],
        "planilha_carregada": app_state["planilha_carregada"],
        "confirmada_em": app_state["planilha_confirmada_em"],
    })


@app.route("/api/gerar", methods=["POST"])
def gerar_crachas():
    """Gera os crachás com as configurações fornecidas."""
    data = request.get_json() or {}
    alunos = app_state["alunos"]

    if not alunos:
        return jsonify({"erro": "Nenhum dado carregado. Importe uma planilha primeiro."}), 400

    formato = data.get("formato", "png")
    mostrar_foto = data.get("mostrar_foto", True)
    mostrar_qr = data.get("mostrar_qr", True)
    turma = str(data.get("turma", "")).strip()
    codigos_selecionados = {
        QRCodeGenerator.normalizar_codigo(codigo)
        for codigo in data.get("codigos", []) if codigo is not None
    }
    nomes_legados = set(data.get("alunos", []))

    if formato not in FORMATOS_SAIDA:
        return jsonify({"erro": f"Formato inválido: {formato}"}), 400

    # Filtrar alunos se necessário
    alunos_gerar = alunos
    if turma:
        alunos_gerar = [a for a in alunos_gerar if a.turma == turma]
    if codigos_selecionados:
        alunos_gerar = [
            aluno for aluno in alunos_gerar
            if QRCodeGenerator.normalizar_codigo(aluno.matricula) in codigos_selecionados
        ]
    elif nomes_legados:
        alunos_gerar = [aluno for aluno in alunos_gerar if aluno.nome in nomes_legados]

    if not alunos_gerar:
        return jsonify({"erro": "Nenhum aluno corresponde aos filtros selecionados."}), 400

    sem_codigo, duplicados = _validar_codigos_qr(alunos_gerar)
    if sem_codigo or duplicados:
        detalhes = []
        if sem_codigo:
            detalhes.append(
                f"{len(sem_codigo)} aluno(s) sem codigo: {', '.join(sem_codigo[:5])}"
            )
        if duplicados:
            exemplos = ", ".join(
                f"{codigo} ({'/'.join(nomes[:3])})"
                for codigo, nomes in list(duplicados.items())[:5]
            )
            detalhes.append(f"codigo(s) duplicado(s): {exemplos}")
        return jsonify({
            "erro": "Não foi possível identificar unicamente os alunos. " + "; ".join(detalhes),
            "sem_codigo": sem_codigo,
            "codigos_duplicados": duplicados,
        }), 400

    config = ConfiguracaoCracha(
        turma_nome="",
        mostrar_foto=mostrar_foto,
        mostrar_qr_code=mostrar_qr,
    )

    montador = MontadorCracha(config)
    exportador = ExportadorCracha(montador)
    pasta_saida = DIRS["MONTADOS"]

    resultados = []
    erros = []
    manifestos_por_pasta = {}

    for i, aluno in enumerate(alunos_gerar):
        try:
            codigo = QRCodeGenerator.normalizar_codigo(aluno.matricula)
            nome_base = exportador._sanitizar_nome(codigo)
            pasta_aluno = pasta_saida / (aluno.turma or "SEM_TURMA")
            pasta_aluno.mkdir(parents=True, exist_ok=True)
            caminho_final = pasta_aluno / f"{nome_base}.{formato}"
            caminho_temp = pasta_aluno / f".{nome_base}.{uuid.uuid4().hex}.tmp.{formato}"
            if formato == "png":
                exportador.exportar_png(aluno, caminho_temp)
            elif formato == "jpg":
                exportador.exportar_jpg(aluno, caminho_temp)
            elif formato == "pdf":
                exportador.exportar_pdf(aluno, caminho_temp)
            elif formato == "html":
                exportador.exportar_html(aluno, caminho_temp)
            caminho_temp.replace(caminho_final)
            caminho = caminho_final

            qr_identificador = (
                QRCodeGenerator().gerar_para_aluno(
                    aluno.nome, aluno.turma, aluno.qr_code_dados, aluno.matricula
                ) if mostrar_qr else None
            )
            foto_usada = getattr(montador.foto_handler, "ultima_foto_caminho", None)
            entrada_manifesto = {
                "codigo": codigo,
                "nome": aluno.nome,
                "turma": aluno.turma,
                "arquivo": caminho.name,
                "formato": formato,
                "sha256": _hash_opcional(caminho),
                "foto": str(foto_usada) if foto_usada else None,
                "foto_sha256": _hash_opcional(foto_usada),
                "qr": qr_identificador,
                "gerado_em": datetime.now().isoformat(timespec="seconds"),
            }
            manifestos_por_pasta.setdefault(pasta_aluno, []).append(entrada_manifesto)

            resultados.append({
                "nome": aluno.nome,
                "turma": aluno.turma,
                "codigo": aluno.matricula,
                "qr_identificador": qr_identificador,
                "arquivo": str(caminho),
                "formato": formato,
                "tamanho_kb": round(caminho.stat().st_size / 1024, 1),
            })
        except Exception as e:
            erros.append({"nome": aluno.nome, "erro": str(e)})
            logger.error(f"Erro ao gerar crachá de {aluno.nome}: {e}")

    for pasta, entradas in manifestos_por_pasta.items():
        _salvar_manifesto(pasta, entradas)

    return jsonify({
        "total_gerados": len(resultados),
        "total_erros": len(erros),
        "resultados": resultados,
        "erros": erros,
        "pasta_saida": str(pasta_saida),
        "reconciliacao": (
            _reconciliar_turma(turma) if turma else None
        ),
    })


@app.route("/api/exportar-pdf-turma", methods=["POST"])
def exportar_pdf_turma():
    """Gera uma folha A4 de impressao para a turma selecionada."""
    data = request.get_json() or {}
    turma = str(data.get("turma", "")).strip()
    if not turma:
        return jsonify({"erro": "Selecione uma turma especifica para exportar o PDF."}), 400

    alunos = [a for a in app_state["alunos"] if a.turma == turma]
    if not alunos:
        return jsonify({"erro": f"Nenhum aluno encontrado na turma {turma}."}), 404

    mostrar_qr = data.get("mostrar_qr", True)
    if mostrar_qr:
        sem_codigo, duplicados = _validar_codigos_qr(alunos)
        if sem_codigo or duplicados:
            return jsonify({
                "erro": "Corrija os codigos vazios ou duplicados antes de exportar o PDF.",
                "sem_codigo": sem_codigo,
                "codigos_duplicados": duplicados,
            }), 400

    config = ConfiguracaoCracha(
        turma_nome=turma,
        mostrar_foto=data.get("mostrar_foto", True),
        mostrar_qr_code=mostrar_qr,
    )
    exportador = ExportadorCracha(MontadorCracha(config))
    pasta_nome = exportador._sanitizar_nome(turma)
    nome_arquivo = f"Turma_{pasta_nome}_Crachas.pdf"
    caminho = DIRS["MONTADOS"] / pasta_nome / nome_arquivo

    try:
        resultado = exportador.exportar_pdf_turma(alunos, turma, caminho)
    except Exception as e:
        logger.error(f"Erro ao exportar PDF da turma {turma}: {e}")
        return jsonify({"erro": str(e)}), 500

    return jsonify({
        "turma": turma,
        "arquivo": str(resultado["caminho"]),
        "nome_arquivo": nome_arquivo,
        "download_url": (
            f"/crachas/{quote(pasta_nome, safe='')}/{quote(nome_arquivo, safe='')}"
        ),
        "total_crachas": resultado["total_crachas"],
        "total_paginas": resultado["total_paginas"],
        "tamanho_cracha_mm": "50 x 85",
        "folha": "A4 paisagem",
    })


@app.route("/api/gerar/preview", methods=["POST"])
def gerar_preview():
    """Gera preview de um crachá específico e retorna como base64."""
    data = request.get_json() or {}
    codigo = QRCodeGenerator.normalizar_codigo(data.get("codigo"))
    nome = data.get("nome", "")
    aluno = next((
        a for a in app_state["alunos"]
        if codigo and QRCodeGenerator.normalizar_codigo(a.matricula) == codigo
    ), None)
    if aluno is None and nome:
        aluno = next((a for a in app_state["alunos"] if a.nome == nome), None)
    if not aluno:
        return jsonify({"erro": "Aluno não encontrado"}), 404

    if data.get("mostrar_qr", True) and not QRCodeGenerator.normalizar_codigo(aluno.matricula):
        return jsonify({"erro": f"Aluno sem codigo oficial: {aluno.nome}"}), 400

    config = ConfiguracaoCracha(
        turma_nome=aluno.turma,
        mostrar_foto=data.get("mostrar_foto", True),
        mostrar_qr_code=data.get("mostrar_qr", True),
    )

    montador = MontadorCracha(config)
    img = montador.montar(aluno)

    # Converter para base64
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")

    return jsonify({
        "nome": aluno.nome,
        "codigo": aluno.matricula,
        "imagem": f"data:image/png;base64,{img_base64}",
    })


@app.route("/api/backup", methods=["POST"])
def criar_backup_api():
    """Cria backup do sistema."""
    try:
        incluir_gerados = bool((request.get_json(silent=True) or {}).get("incluir_gerados", False))
        caminho = criar_backup(incluir_gerados=incluir_gerados)
        validacao = validar_backup(caminho)
        return jsonify({
            "sucesso": True,
            "caminho": str(caminho),
            "arquivo": caminho.name,
            "validacao": validacao,
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/exemplo", methods=["POST"])
def criar_exemplo_api():
    """Cria arquivo Excel de exemplo."""
    caminho = DIRS["DIAG_SAIDA"] / "modelo_alunos.xlsx"
    try:
        criar_arquivo_exemplo(caminho)
        return jsonify({"sucesso": True, "caminho": str(caminho)})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/baixar-exemplo")
def baixar_exemplo():
    """Download do arquivo Excel de exemplo."""
    caminho = DIRS["DIAG_SAIDA"] / "modelo_alunos.xlsx"
    if not caminho.exists():
        criar_arquivo_exemplo(caminho)
    return send_file(caminho, as_attachment=True, download_name="modelo_alunos.xlsx")


@app.route("/api/crachas")
def listar_crachas_gerados():
    """Lista os crachás já gerados, opcionalmente filtrados por turma."""
    turma = str(request.args.get("turma", "")).strip()
    diag = Diagnosticador()
    crachas = diag.listar_crachas_montados()
    if turma:
        crachas = [cracha for cracha in crachas if cracha["turma"] == turma]

    for cracha in crachas:
        caminho_relativo = Path(cracha["caminho"]).relative_to(DIRS["MONTADOS"])
        cracha["url"] = f"/crachas/{quote(caminho_relativo.as_posix(), safe='/')}"

    return jsonify({
        "crachas": crachas,
        "turma": turma,
        "total": len(crachas),
    })


@app.route("/api/reconciliacao")
def reconciliacao():
    turma = str(request.args.get("turma", "")).strip()
    if turma:
        return jsonify(_reconciliar_turma(turma))
    return jsonify({
        "turmas": [_reconciliar_turma(nome) for nome in sorted(app_state["turmas"])]
    })


@app.route("/api/integridade/fotos")
def integridade_fotos():
    """Audita a foto efetivamente escolhida para cada aluno ativo."""
    resultado = auditar_fotos(app_state["alunos"])
    resultado["total_arquivos_foto"] = contar_arquivos_foto()
    turma = str(request.args.get("turma", "")).strip()
    if turma:
        itens = [item for item in resultado["itens"] if item["turma"] == turma]
        resultado["itens"] = itens
        resultado["total_alunos"] = len(itens)
        resultado["por_codigo"] = sum(item["metodo"] == "codigo" for item in itens)
        resultado["por_nome_legado"] = sum(
            item["metodo"] == "nome_legado" for item in itens
        )
        resultado["sem_foto"] = sum(item["metodo"] == "ausente" for item in itens)
    return jsonify(resultado)


@app.route("/api/arquivar-obsoletos", methods=["POST"])
def arquivar_obsoletos():
    turma = str((request.get_json() or {}).get("turma", "")).strip()
    if not turma:
        return jsonify({"erro": "Selecione uma turma."}), 400
    resultado = _reconciliar_turma(turma)
    if not resultado["obsoletos"]:
        return jsonify({"turma": turma, "total": 0, "arquivados": []})
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = DIRS["MONTADOS"] / "_obsoletos" / timestamp / ExportadorCracha._sanitizar_nome(turma)
    destino.mkdir(parents=True, exist_ok=True)
    arquivados = []
    raiz = DIRS["MONTADOS"].resolve()
    for item in resultado["obsoletos"]:
        origem = Path(item["caminho"]).resolve()
        if raiz not in origem.parents or origem.parent.name != ExportadorCracha._sanitizar_nome(turma):
            return jsonify({"erro": "Caminho de arquivo obsoleto inválido."}), 400
        alvo = destino / origem.name
        shutil.move(str(origem), str(alvo))
        arquivados.append(str(alvo))
    return jsonify({"turma": turma, "total": len(arquivados), "arquivados": arquivados})


@app.route("/api/backups")
def listar_backups():
    backups = sorted(DIRS["BACKUPS"].glob("backup_cracha_*.zip"), reverse=True)
    return jsonify({"backups": [
        {"arquivo": item.name, "tamanho_mb": round(item.stat().st_size / 1024 / 1024, 2)}
        for item in backups
    ]})


@app.route("/api/backup/validar", methods=["POST"])
def validar_backup_api():
    nome = secure_filename(str((request.get_json() or {}).get("arquivo", "")))
    caminho = DIRS["BACKUPS"] / nome
    try:
        return jsonify(validar_backup(caminho))
    except (OSError, ValueError, zipfile.BadZipFile) as erro:
        return jsonify({"erro": str(erro)}), 400


@app.route("/api/backup/extrair", methods=["POST"])
def extrair_backup_isolado():
    """Valida e extrai um backup em área isolada, sem alterar o sistema ativo."""
    nome = secure_filename(str((request.get_json() or {}).get("arquivo", "")))
    caminho = DIRS["BACKUPS"] / nome
    try:
        validacao = validar_backup(caminho)
        if not validacao.get("valido"):
            return jsonify({"erro": "O backup não passou na validação."}), 400
        destino = DIRS["DIAG_SAIDA"] / "restauracoes" / uuid.uuid4().hex
        destino.mkdir(parents=True, exist_ok=False)
        raiz = destino.resolve()
        with zipfile.ZipFile(caminho, "r") as arquivo_zip:
            for membro in arquivo_zip.infolist():
                alvo = (destino / membro.filename).resolve()
                if alvo != raiz and raiz not in alvo.parents:
                    raise ValueError("O backup contém um caminho inseguro.")
            arquivo_zip.extractall(destino)
        return jsonify({
            "sucesso": True,
            "pasta": str(destino),
            "validacao": validacao,
            "mensagem": "Backup extraído em área isolada; o sistema ativo não foi alterado.",
        })
    except (OSError, ValueError, zipfile.BadZipFile) as erro:
        return jsonify({"erro": str(erro)}), 400


# ========== ROTAS DO FRONTEND ==========

@app.route("/")
def index():
    """Serve o frontend."""
    return send_from_directory(str(DIRS["STATIC"]), "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve arquivos estáticos (CSS, JS, imagens)."""
    return send_from_directory(str(DIRS["STATIC"]), filename)


@app.route("/crachas/<path:filename>")
def crachas_arquivos(filename):
    """Serve arquivos de crachás gerados."""
    return send_from_directory(str(DIRS["MONTADOS"]), filename)


# ========== UTILITÁRIOS ==========

def _salvar_temporario(arquivo, upload_id: str | None = None) -> Path:
    """Salva arquivo enviado em diretorio temporario com nome seguro."""
    pasta_temp = DIRS["IMPORTACOES_PENDENTES"]
    pasta_temp.mkdir(parents=True, exist_ok=True)
    nome_seguro = secure_filename(arquivo.filename or "")
    extensao = Path(nome_seguro).suffix.lower()
    if extensao not in EXTENSOES_PLANILHA:
        raise ValueError(
            f"Extensao nao suportada: {extensao or 'sem extensao'}. "
            f"Use: {', '.join(EXTENSOES_PLANILHA)}"
        )

    identificador = upload_id or uuid.uuid4().hex
    caminho = pasta_temp / f"{Path(nome_seguro).stem}_{identificador}{extensao}"
    arquivo.save(caminho)
    return caminho


def criar_app():
    """Configura e retorna a aplicação Flask."""
    return app


def iniciar_servidor(host="127.0.0.1", port=5000, debug=False):
    """Inicia o servidor web."""
    if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("CRACHA_ALLOW_NETWORK") != "1":
        raise RuntimeError(
            "A exposição em rede exige CRACHA_ALLOW_NETWORK=1 e proteção de acesso explícita."
        )
    logger.info(f"Iniciando servidor em http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
