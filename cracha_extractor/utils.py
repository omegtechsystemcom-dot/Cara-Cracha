"""
Utilitários do sistema de crachás:
- Logger configurado
- Diagnóstico de arquivos
- Backup automático
- Utilitários gerais
"""
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
import shutil
import json
from typing import Optional

from .config import DIRS, LOG_CONFIG


def configurar_logger(nome: str = "cracha_extractor") -> logging.Logger:
    """Configura e retorna um logger com saída em arquivo e console."""
    logger = logging.getLogger(nome)
    logger.setLevel(LOG_CONFIG["NIVEL"])

    # Evitar duplicação de handlers
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_CONFIG["FORMATO"])

    # Handler de arquivo com rotação
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_CONFIG["ARQUIVO"],
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Handler de console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


class Diagnosticador:
    """Verifica e diagnostica arquivos e configurações do sistema."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def verificar_estrutura(self) -> dict:
        """Verifica se todos os diretórios necessários existem."""
        resultado = {}
        for nome, caminho in DIRS.items():
            existe = caminho.exists()
            resultado[nome] = {
                "caminho": str(caminho),
                "existe": existe,
                "erro": None if existe else "Diretório não encontrado",
            }
        return resultado

    def verificar_planilha(self, caminho: str | Path) -> dict:
        """Verifica se uma planilha é válida."""
        from .planilha_reader import PlanilhaReader

        caminho = Path(caminho)
        resultado = {
            "arquivo": str(caminho),
            "existe": caminho.exists(),
            "valido": False,
            "colunas": [],
            "linhas": 0,
            "erro": None,
        }

        if not caminho.exists():
            resultado["erro"] = "Arquivo não encontrado"
            return resultado

        try:
            reader = PlanilhaReader(caminho)
            colunas = reader.listar_colunas()
            alunos = reader.ler()
            resultado["colunas"] = list(colunas)
            resultado["linhas"] = len(alunos)
            resultado["valido"] = len(alunos) > 0
        except Exception as e:
            resultado["erro"] = str(e)

        return resultado

    def listar_turmas_disponiveis(self) -> list[str]:
        """Lista as turmas que já têm pastas criadas."""
        turmas = []
        pasta_turmas = DIRS["TURMAS"]
        if pasta_turmas.exists():
            turmas = [
                item.name
                for item in pasta_turmas.iterdir()
                if item.is_dir()
            ]
        return sorted(turmas)

    def listar_crachas_montados(self) -> list[dict]:
        """Lista os crachás já montados disponíveis."""
        crachas = []
        pasta_montados = DIRS["MONTADOS"]
        if pasta_montados.exists():
            for item in pasta_montados.rglob("*"):
                if item.is_file() and item.suffix.lower() in [".png", ".jpg", ".pdf", ".html"]:
                    # Extrair nome do aluno do nome do arquivo (sem extensão, substituindo _ por espaço)
                    nome_arquivo = item.stem
                    nome_aluno = nome_arquivo.replace("_", " ").strip()
                    crachas.append({
                        "caminho": str(item),
                        "nome": nome_aluno,
                        "arquivo": item.name,
                        "turma": item.parent.name,
                        "formato": item.suffix[1:].lower(),
                        "tamanho_kb": round(item.stat().st_size / 1024, 1),
                    })
        return sorted(crachas, key=lambda x: x["caminho"])


def criar_backup() -> Path:
    """Cria um backup dos arquivos de configuração e dados."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_backup = DIRS["BACKUPS"] / f"backup_{timestamp}"
    pasta_backup.mkdir(parents=True, exist_ok=True)

    # Pastas para fazer backup
    pastas_backup = [
        DIRS["TURMAS"],
        DIRS["STATIC"],
    ]

    for pasta in pastas_backup:
        if pasta.exists():
            destino = pasta_backup / pasta.name
            shutil.copytree(pasta, destino, dirs_exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.info(f"Backup criado em: {pasta_backup}")

    # Salvar metadados do backup
    metadados = {
        "data": timestamp,
        "pastas_incluidas": [str(p) for p in pastas_backup],
        "versao_sistema": "1.0.0",
    }
    (pasta_backup / "metadados_backup.json").write_text(
        json.dumps(metadados, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return pasta_backup


def criar_arquivo_exemplo(caminho: str | Path):
    """Cria um arquivo Excel de exemplo com dados fictícios."""
    import pandas as pd

    dados = {
        "Nome": [
            "MARIA DA SILVA",
            "JOÃO PEDRO SANTOS",
            "ANA BEATRIZ OLIVEIRA",
            "LUCAS GABRIEL COSTA",
            "JULIA FERNANDA LIMA",
        ],
        "Turma": ["102", "102", "102", "102", "102"],
        "Curso": [
            "INFORMÁTICA",
            "INFORMÁTICA",
            "INFORMÁTICA",
            "INFORMÁTICA",
            "INFORMÁTICA",
        ],
        "Matrícula": ["2024001", "2024002", "2024003", "2024004", "2024005"],
        "Observação": ["", "", "", "", ""],
    }

    df = pd.DataFrame(dados)
    df.to_excel(caminho, index=False, sheet_name="Alunos")
    logger = logging.getLogger(__name__)
    logger.info(f"Arquivo exemplo criado: {caminho}")
