"""Auditoria determinística da associação entre alunos, fotos e códigos."""
from collections import defaultdict
from pathlib import Path

from .config import DIRS
from .foto_handler import FotoHandler
from .qr_generator import QRCodeGenerator


EXTENSOES_FOTO = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}


def auditar_fotos(alunos) -> dict:
    """Resolve cada foto como na geração e classifica a associação encontrada."""
    handler = FotoHandler()
    itens = []
    por_arquivo = defaultdict(list)
    for aluno in alunos:
        codigo = QRCodeGenerator.normalizar_codigo(aluno.matricula)
        imagem = handler.buscar_foto_aluno(
            aluno.nome, codigo=codigo, turma=aluno.turma
        )
        caminho = handler.ultima_foto_caminho
        if imagem is not None:
            imagem.close()
        metodo = "ausente"
        if caminho:
            stem = handler._normalizar_nome(Path(caminho).stem)
            codigo_normalizado = handler._normalizar_codigo(codigo)
            if (stem == codigo_normalizado
                    or stem.startswith(f"{codigo_normalizado}_")
                    or stem.endswith(f"_{codigo_normalizado}")):
                metodo = "codigo"
            else:
                metodo = "nome_legado"
            por_arquivo[str(Path(caminho).resolve())].append(codigo)
        itens.append({
            "codigo": codigo,
            "nome": aluno.nome,
            "turma": aluno.turma,
            "foto": str(caminho) if caminho else None,
            "metodo": metodo,
        })

    compartilhadas = {
        caminho: codigos for caminho, codigos in por_arquivo.items()
        if len(set(codigos)) > 1
    }
    return {
        "total_alunos": len(itens),
        "por_codigo": sum(item["metodo"] == "codigo" for item in itens),
        "por_nome_legado": sum(item["metodo"] == "nome_legado" for item in itens),
        "sem_foto": sum(item["metodo"] == "ausente" for item in itens),
        "fotos_compartilhadas": compartilhadas,
        "total_fotos_compartilhadas": len(compartilhadas),
        "itens": itens,
    }


def contar_arquivos_foto() -> int:
    raiz = DIRS["FOTOS_ALUNOS"]
    if not raiz.is_dir():
        return 0
    return sum(
        arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_FOTO
        for arquivo in raiz.rglob("*")
    )
