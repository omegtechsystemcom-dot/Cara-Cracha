"""
API Flask para servir o frontend web e processar requisições.
"""
import logging
import base64
import io
import uuid
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
from .planilha_reader import PlanilhaReader
from .montador import MontadorCracha
from .exportador import ExportadorCracha
from .models import Aluno, ConfiguracaoCracha
from .qr_generator import QRCodeGenerator
from .utils import Diagnosticador, criar_backup, criar_arquivo_exemplo

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
}

# Caminho padrão da planilha IEMA
PLANILHA_PADRAO = BASE_DIR / "alunosiema.xlsx"
EXTENSOES_FOTO = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}


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


# ========== ROTAS DA API ==========

@app.route("/api/health")
def health():
    """Health check da API."""
    return jsonify({"status": "ok", "versao": "2.0.0"})


@app.route("/api/fotos", methods=["POST"])
def enviar_fotos():
    """Recebe fotos e as disponibiliza para associação automática por nome."""
    arquivos = request.files.getlist("fotos")
    if not arquivos or not any(arquivo.filename for arquivo in arquivos):
        return jsonify({"erro": "Nenhuma foto enviada."}), 400

    salvas = []
    erros = []
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
        destino.write_bytes(conteudo)
        salvas.append(nome)

    if not salvas:
        return jsonify({"erro": "Nenhuma foto válida foi enviada.", "erros": erros}), 400

    return jsonify({
        "total_salvas": len(salvas),
        "fotos": salvas,
        "erros": erros,
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

        # Salvar no estado
        app_state["alunos"] = alunos
        app_state["turmas"] = turmas
        app_state["planilha_carregada"] = str(caminho)

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

    return jsonify({
        "estrutura": {k: v for k, v in estrutura.items()},
        "turmas": turmas,
        "crachas_montados": crachas,
        "total_crachas": len(crachas),
    })


@app.route("/api/planilha/colunas", methods=["POST"])
def preview_planilha():
    """Lê uma planilha e retorna preview das colunas e dados."""
    arquivo = request.files.get("arquivo")
    if not arquivo:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    try:
        caminho = _salvar_temporario(arquivo)
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

        # Salvar no estado
        app_state["alunos"] = alunos
        app_state["turmas"] = turmas
        app_state["planilha_carregada"] = str(caminho)

        return jsonify({
            "total_alunos": len(alunos),
            "total_turmas": len(turmas),
            "colunas_detectadas": reader.colunas_mapeadas,
            "colunas_planilha": colunas,
            "turmas": {nome: len(t.alunos) for nome, t in turmas.items()},
            "preview": preview,
        })
    except Exception as e:
        logger.error(f"Erro ao ler planilha: {e}")
        return jsonify({"erro": str(e)}), 400


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
        "alunos": [
            {
                "nome": a.nome,
                "turma": a.turma,
                "curso": a.curso,
                "matricula": a.matricula,
                "observacao": a.observacao,
            }
            for a in alunos
        ],
    })


@app.route("/api/gerar", methods=["POST"])
def gerar_crachas():
    """Gera os crachás com as configurações fornecidas."""
    data = request.get_json() or {}
    alunos = app_state["alunos"]

    if not alunos:
        return jsonify({"erro": "Nenhum dado carregado. Importe uma planilha primeiro."}), 400

    formato = data.get("formato", "png")
    cor_destaque = data.get("cor_destaque", "#1a5276")
    mostrar_foto = data.get("mostrar_foto", True)
    mostrar_qr = data.get("mostrar_qr", True)
    turma = str(data.get("turma", "")).strip()
    selecionados = data.get("alunos", [])  # Lista de nomes, vazio = todos

    if formato not in FORMATOS_SAIDA:
        return jsonify({"erro": f"Formato inválido: {formato}"}), 400

    # Filtrar alunos se necessário
    alunos_gerar = alunos
    if turma:
        alunos_gerar = [a for a in alunos_gerar if a.turma == turma]
    if selecionados:
        alunos_gerar = [a for a in alunos_gerar if a.nome in selecionados]

    if not alunos_gerar:
        return jsonify({"erro": "Nenhum aluno corresponde aos filtros selecionados."}), 400

    if mostrar_qr:
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
                "erro": "Nao foi possivel gerar os QR Codes. " + "; ".join(detalhes),
                "sem_codigo": sem_codigo,
                "codigos_duplicados": duplicados,
            }), 400

    config = ConfiguracaoCracha(
        turma_nome="",
        cor_destaque=cor_destaque,
        mostrar_foto=mostrar_foto,
        mostrar_qr_code=mostrar_qr,
    )

    montador = MontadorCracha(config)
    exportador = ExportadorCracha(montador)
    pasta_saida = DIRS["MONTADOS"]

    resultados = []
    erros = []

    for i, aluno in enumerate(alunos_gerar):
        try:
            nome_base = exportador._sanitizar_nome(aluno.nome)
            pasta_aluno = pasta_saida / (aluno.turma or "SEM_TURMA")
            pasta_aluno.mkdir(parents=True, exist_ok=True)

            if formato == "png":
                caminho = exportador.exportar_png(aluno, pasta_aluno / f"{nome_base}.png")
            elif formato == "jpg":
                caminho = exportador.exportar_jpg(aluno, pasta_aluno / f"{nome_base}.jpg")
            elif formato == "pdf":
                caminho = exportador.exportar_pdf(aluno, pasta_aluno / f"{nome_base}.pdf")
            elif formato == "html":
                caminho = exportador.exportar_html(aluno, pasta_aluno / f"{nome_base}.html")

            resultados.append({
                "nome": aluno.nome,
                "turma": aluno.turma,
                "codigo": aluno.matricula,
                "qr_identificador": (
                    f"IEMA|V1|COD={QRCodeGenerator.normalizar_codigo(aluno.matricula)}"
                    if mostrar_qr else None
                ),
                "arquivo": str(caminho),
                "formato": formato,
                "tamanho_kb": round(caminho.stat().st_size / 1024, 1),
            })
        except Exception as e:
            erros.append({"nome": aluno.nome, "erro": str(e)})
            logger.error(f"Erro ao gerar crachá de {aluno.nome}: {e}")

    return jsonify({
        "total_gerados": len(resultados),
        "total_erros": len(erros),
        "resultados": resultados,
        "erros": erros,
        "pasta_saida": str(pasta_saida),
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
        cor_destaque=data.get("cor_destaque", "#1a5276"),
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
    nome = data.get("nome", "")

    aluno = next((a for a in app_state["alunos"] if a.nome == nome), None)
    if not aluno:
        return jsonify({"erro": "Aluno não encontrado"}), 404

    if data.get("mostrar_qr", True) and not QRCodeGenerator.normalizar_codigo(aluno.matricula):
        return jsonify({"erro": f"Aluno sem codigo oficial: {aluno.nome}"}), 400

    config = ConfiguracaoCracha(
        turma_nome=aluno.turma,
        cor_destaque=data.get("cor_destaque", "#1a5276"),
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
        "imagem": f"data:image/png;base64,{img_base64}",
    })


@app.route("/api/backup", methods=["POST"])
def criar_backup_api():
    """Cria backup do sistema."""
    try:
        caminho = criar_backup()
        return jsonify({"sucesso": True, "caminho": str(caminho)})
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
    """Lista os crachás já gerados."""
    diag = Diagnosticador()
    crachas = diag.listar_crachas_montados()
    return jsonify({"crachas": crachas})


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

def _salvar_temporario(arquivo) -> Path:
    """Salva arquivo enviado em diretório temporário."""
    pasta_temp = DIRS["DIAG_SAIDA"] / "uploads"
    pasta_temp.mkdir(parents=True, exist_ok=True)
    caminho = pasta_temp / arquivo.filename
    arquivo.save(caminho)
    return caminho


def _salvar_temporario(arquivo) -> Path:
    """Salva arquivo enviado em diretorio temporario com nome seguro."""
    pasta_temp = DIRS["DIAG_SAIDA"] / "uploads"
    pasta_temp.mkdir(parents=True, exist_ok=True)
    nome_seguro = secure_filename(arquivo.filename or "")
    extensao = Path(nome_seguro).suffix.lower()
    if extensao not in EXTENSOES_PLANILHA:
        raise ValueError(
            f"Extensao nao suportada: {extensao or 'sem extensao'}. "
            f"Use: {', '.join(EXTENSOES_PLANILHA)}"
        )

    caminho = pasta_temp / f"{Path(nome_seguro).stem}_{uuid.uuid4().hex[:8]}{extensao}"
    arquivo.save(caminho)
    return caminho


def criar_app():
    """Configura e retorna a aplicação Flask."""
    return app


def iniciar_servidor(host="127.0.0.1", port=5000, debug=False):
    """Inicia o servidor web."""
    logger.info(f"Iniciando servidor em http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
