"""Persistência simples e auditável da planilha ativa do sistema local."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from .config import DIRS
from .planilha_reader import PlanilhaReader


def hash_arquivo(caminho: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def caminho_estado() -> Path:
    return DIRS["DATA"] / "estado_sistema.json"


def salvar_estado_planilha(caminho: str | Path) -> dict:
    caminho = Path(caminho).resolve()
    dados = {
        "versao": 1,
        "planilha": str(caminho),
        "sha256": hash_arquivo(caminho),
        "confirmada_em": datetime.now().isoformat(timespec="seconds"),
    }
    destino = caminho_estado()
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(destino)
    return dados


def carregar_estado_planilha() -> tuple[list, dict, dict] | None:
    estado = caminho_estado()
    if not estado.is_file():
        return None
    try:
        dados = json.loads(estado.read_text(encoding="utf-8"))
        caminho = Path(dados["planilha"])
        if not caminho.is_file() or hash_arquivo(caminho) != dados.get("sha256"):
            return None
        reader = PlanilhaReader(caminho)
        alunos = reader.ler()
        return alunos, reader.agrupar_por_turma(alunos), dados
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
