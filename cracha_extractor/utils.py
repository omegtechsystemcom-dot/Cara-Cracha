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
import json
import hashlib
import zipfile
import uuid

from .config import BASE_DIR, DIRS, LOG_CONFIG


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
        """Lista turmas encontradas nas fontes de fotos, legadas e de saída."""
        turmas = set()
        for pasta in (DIRS["TURMAS"], DIRS["FOTOS_ALUNOS"], DIRS["MONTADOS"]):
            if pasta.exists():
                turmas.update(
                    item.name for item in pasta.iterdir()
                    if item.is_dir() and not item.name.startswith("_")
                )
        return sorted(turmas)

    def listar_crachas_montados(self) -> list[dict]:
        """Lista os crachás já montados disponíveis."""
        crachas = []
        pasta_montados = DIRS["MONTADOS"]
        metadados = {}
        pastas_com_manifesto = set()
        if pasta_montados.exists():
            for manifesto in pasta_montados.glob("*/manifesto.json"):
                try:
                    dados = json.loads(manifesto.read_text(encoding="utf-8"))
                    pastas_com_manifesto.add(manifesto.parent.name)
                    for item in dados.get("crachas", []):
                        metadados[(manifesto.parent.name, item.get("arquivo"))] = item
                except (OSError, json.JSONDecodeError):
                    continue
        if pasta_montados.exists():
            for item in pasta_montados.rglob("*"):
                if "_obsoletos" in item.parts:
                    continue
                if item.is_file() and item.suffix.lower() in [".png", ".jpg", ".pdf", ".html"]:
                    if (item.suffix.lower() == ".pdf"
                            and item.stem.startswith("Turma_")
                            and item.stem.endswith("_Crachas")):
                        continue
                    # Extrair nome do aluno do nome do arquivo (sem extensão, substituindo _ por espaço)
                    if (item.parent.name in pastas_com_manifesto
                            and (item.parent.name, item.name) not in metadados):
                        continue
                    meta = metadados.get((item.parent.name, item.name), {})
                    nome_arquivo = item.stem
                    nome_aluno = meta.get("nome") or nome_arquivo.replace("_", " ").strip()
                    crachas.append({
                        "caminho": str(item),
                        "nome": nome_aluno,
                        "arquivo": item.name,
                        "turma": item.parent.name,
                        "formato": item.suffix[1:].lower(),
                        "tamanho_kb": round(item.stat().st_size / 1024, 1),
                        "codigo": meta.get("codigo", ""),
                    })
        return sorted(crachas, key=lambda x: x["caminho"])


def _hash_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def criar_backup(incluir_gerados: bool = False) -> Path:
    """Cria um ZIP atômico das fontes de verdade e, opcionalmente, das saídas."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    DIRS["BACKUPS"].mkdir(parents=True, exist_ok=True)
    destino = DIRS["BACKUPS"] / f"backup_cracha_{timestamp}.zip"
    temporario = destino.with_name(f".{destino.name}.{uuid.uuid4().hex}.tmp")
    origens = [
        BASE_DIR / "alunosiema.xlsx",
        BASE_DIR / "ModeloCrachaIema.png",
        DIRS["FOTOS_ALUNOS"],
        DIRS["DATA"],
        DIRS["STATIC"],
    ]
    if incluir_gerados:
        origens.append(DIRS["MONTADOS"])

    arquivos = []
    for origem in origens:
        if origem.is_file():
            arquivos.append(origem)
        elif origem.is_dir():
            arquivos.extend(
                item for item in origem.rglob("*")
                if item.is_file() and "__pycache__" not in item.parts
            )
    arquivos = sorted(set(arquivos), key=lambda item: str(item).lower())
    manifesto = {
        "versao": 1,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "inclui_gerados": incluir_gerados,
        "arquivos": [],
    }
    try:
        with zipfile.ZipFile(
            temporario, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True
        ) as arquivo_zip:
            for arquivo in arquivos:
                relativo = arquivo.relative_to(BASE_DIR).as_posix()
                manifesto["arquivos"].append({
                    "caminho": relativo,
                    "tamanho": arquivo.stat().st_size,
                    "sha256": _hash_arquivo(arquivo),
                })
                arquivo_zip.write(arquivo, relativo)
            arquivo_zip.writestr(
                "MANIFESTO_BACKUP.json",
                json.dumps(manifesto, indent=2, ensure_ascii=False),
            )
        temporario.replace(destino)
    finally:
        if temporario.exists():
            temporario.unlink()

    logging.getLogger(__name__).info(f"Backup criado em: {destino}")
    return destino


def validar_backup(caminho: str | Path) -> dict:
    """Valida CRC, manifesto e hashes sem alterar o projeto ativo."""
    caminho = Path(caminho)
    if not caminho.is_file() or caminho.suffix.lower() != ".zip":
        raise ValueError("Arquivo de backup não encontrado ou inválido.")
    with zipfile.ZipFile(caminho) as arquivo_zip:
        ruim = arquivo_zip.testzip()
        if ruim:
            raise ValueError(f"Arquivo corrompido no backup: {ruim}")
        try:
            manifesto = json.loads(arquivo_zip.read("MANIFESTO_BACKUP.json"))
        except (KeyError, json.JSONDecodeError) as erro:
            raise ValueError("Manifesto do backup ausente ou inválido.") from erro
        erros = []
        for item in manifesto.get("arquivos", []):
            conteudo = arquivo_zip.read(item["caminho"])
            if len(conteudo) != item["tamanho"]:
                erros.append(f"Tamanho divergente: {item['caminho']}")
            if hashlib.sha256(conteudo).hexdigest() != item["sha256"]:
                erros.append(f"Hash divergente: {item['caminho']}")
    return {
        "valido": not erros,
        "arquivo": str(caminho),
        "total_arquivos": len(manifesto.get("arquivos", [])),
        "inclui_gerados": manifesto.get("inclui_gerados", False),
        "erros": erros,
    }


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
