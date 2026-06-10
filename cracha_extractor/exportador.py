"""
Exportadores de crachás para diversos formatos:
- PDF
- PNG/JPG (imagem)
- HTML
"""
import logging
from pathlib import Path
from typing import Optional
import io

from PIL import Image

from .models import Aluno
from .montador import MontadorCracha
from .config import DIRS

logger = logging.getLogger(__name__)


class ExportadorCracha:
    """
    Exporta crachás para diferentes formatos de arquivo.
    """

    def __init__(self, montador: MontadorCracha):
        self.montador = montador

    def exportar_png(self, aluno: Aluno, caminho: str | Path) -> Path:
        """Exporta o crachá como PNG."""
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)

        cracha_img = self.montador.montar(aluno)
        cracha_img.save(caminho, "PNG")
        logger.info(f"Crachá PNG salvo: {caminho}")
        return caminho

    def exportar_jpg(self, aluno: Aluno, caminho: str | Path, qualidade: int = 95) -> Path:
        """Exporta o crachá como JPG."""
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)

        cracha_img = self.montador.montar(aluno)
        if cracha_img.mode == "RGBA":
            cracha_img = cracha_img.convert("RGB")
        cracha_img.save(caminho, "JPEG", quality=qualidade)
        logger.info(f"Crachá JPG salvo: {caminho}")
        return caminho

    def exportar_pdf(self, aluno: Aluno, caminho: str | Path) -> Path:
        """Exporta o crachá como PDF usando PIL."""
        try:
            from PIL import PdfImagePlugin  # noqa: F401
        except ImportError:
            pass

        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)

        cracha_img = self.montador.montar(aluno)
        if cracha_img.mode == "RGBA":
            cracha_img = cracha_img.convert("RGB")
        cracha_img.save(caminho, "PDF", resolution=300)
        logger.info(f"Crachá PDF salvo: {caminho}")
        return caminho

    def exportar_html(self, aluno: Aluno, caminho: str | Path) -> Path:
        """Exporta o crachá como HTML."""
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)

        html = self.montador.montar_html(aluno)
        caminho.write_text(html, encoding="utf-8")
        logger.info(f"Crachá HTML salvo: {caminho}")
        return caminho

    def exportar_todos_formatos(self, aluno: Aluno, pasta: str | Path, formatos: list[str]) -> dict[str, Path]:
        """
        Exporta o crachá em múltiplos formatos.
        Retorna um dict com {formato: caminho_do_arquivo}.
        """
        pasta = Path(pasta)
        pasta.mkdir(parents=True, exist_ok=True)

        nome_base = self._sanitizar_nome(aluno.nome)
        resultados = {}

        for fmt in formatos:
            fmt = fmt.lower()
            if fmt == "png":
                caminho = pasta / f"{nome_base}.png"
                self.exportar_png(aluno, caminho)
                resultados["png"] = caminho
            elif fmt == "jpg":
                caminho = pasta / f"{nome_base}.jpg"
                self.exportar_jpg(aluno, caminho)
                resultados["jpg"] = caminho
            elif fmt == "pdf":
                caminho = pasta / f"{nome_base}.pdf"
                self.exportar_pdf(aluno, caminho)
                resultados["pdf"] = caminho
            elif fmt == "html":
                caminho = pasta / f"{nome_base}.html"
                self.exportar_html(aluno, caminho)
                resultados["html"] = caminho

        return resultados

    def exportar_lote(
        self,
        alunos: list[Aluno],
        pasta_base: str | Path,
        formatos: list[str],
        agrupar_por_turma: bool = True,
    ) -> dict[str, list[Path]]:
        """
        Exporta crachás em lote para todos os alunos.
        Se agrupar_por_turma=True, cria subpastas por turma.
        """
        pasta_base = Path(pasta_base)
        resultados = {fmt: [] for fmt in formatos}

        for aluno in alunos:
            if agrupar_por_turma and aluno.turma:
                pasta_destino = pasta_base / aluno.turma
            else:
                pasta_destino = pasta_base

            arquivos = self.exportar_todos_formatos(aluno, pasta_destino, formatos)
            for fmt, caminho in arquivos.items():
                resultados[fmt].append(caminho)

        logger.info(f"Lote exportado: {len(alunos)} alunos em {pasta_base}")
        return resultados

    @staticmethod
    def _sanitizar_nome(nome: str) -> str:
        """Sanitiza o nome do aluno para usar como nome de arquivo."""
        nome_limpo = "".join(c for c in nome if c.isalnum() or c in " _-")
        nome_limpo = nome_limpo.strip().replace(" ", "_")
        # Limitar tamanho
        if len(nome_limpo) > 50:
            nome_limpo = nome_limpo[:50]
        return nome_limpo or "cracha"
