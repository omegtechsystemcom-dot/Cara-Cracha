"""
API Flask para servir o frontend web e processar requisições.
"""
import logging
import json
import base64
import io
from pathlib import Path
from typing import Optional

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

from .config import DIRS, FORMATOS_SAIDA
from .planilha_reader import PlanilhaReader
from .montador import MontadorCracha
from .exportador import ExportadorCracha
from .models import Aluno, ConfiguracaoCracha
from .utils import Diagnosticador, criar_backup, criar_arquivo_exemplo

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)
CORS(app)

# Estado da aplicação (em memória)
app_state = {
    "alunos": [],
    "turmas": {},
    "planilha_carregada": None,
}

# Caminho padrão da planilha IEMA
PLANILHA_PADRAO = Path(r"D:\codigo-pyton\CRACHA IMPRIMIR\alunosiema.xlsx")


# ========== ROTAS DA API ==========

@app.route("/api/health")
def health():
    """Health check da API."""
    return jsonify({"status": "ok", "versao": "2.0.0"})


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

    caminho = _salvar_temporario(arquivo)
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
    selecionados = data.get("alunos", [])  # Lista de nomes, vazio = todos

    if formato not in FORMATOS_SAIDA:
        return jsonify({"erro": f"Formato inválido: {formato}"}), 400

    # Filtrar alunos se necessário
    alunos_gerar = alunos
    if selecionados:
        alunos_gerar = [a for a in alunos if a.nome in selecionados]

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


@app.route("/api/gerar/preview", methods=["POST"])
def gerar_preview():
    """Gera preview de um crachá específico e retorna como base64."""
    data = request.get_json() or {}
    nome = data.get("nome", "")

    aluno = next((a for a in app_state["alunos"] if a.nome == nome), None)
    if not aluno:
        return jsonify({"erro": "Aluno não encontrado"}), 404

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


def criar_app():
    """Configura e retorna a aplicação Flask."""
    return app


def iniciar_servidor(host="127.0.0.1", port=5000, debug=False):
    """Inicia o servidor web."""
    logger.info(f"Iniciando servidor em http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
