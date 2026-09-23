"""
Exportadores de crachás para diversos formatos:
- PDF
- PNG/JPG (imagem)
- HTML
"""
import logging
import math
from pathlib import Path
from typing import Optional
import io
import unicodedata

from PIL import Image, ImageDraw, ImageFont

from .models import Aluno
from .montador import MontadorCracha
from .config import DIRS, LAYOUT

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

    @staticmethod
    def _chave_alfabetica(aluno: Aluno) -> str:
        texto = unicodedata.normalize("NFKD", aluno.nome.casefold())
        return "".join(c for c in texto if not unicodedata.combining(c))

    @staticmethod
    def _fonte_impressao(tamanho: int) -> ImageFont.ImageFont:
        for arquivo in ("arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(arquivo, tamanho)
            except OSError:
                continue
        return ImageFont.load_default(size=tamanho)

    @staticmethod
    def _desenhar_marcas_corte(draw: ImageDraw.ImageDraw, x: int, y: int,
                               largura: int, altura: int):
        """Desenha marcas fora da arte, sem invadir o cracha."""
        afastamento = 4
        comprimento = 12
        cor = "#555555"
        for canto_x, direcao_x in ((x, -1), (x + largura, 1)):
            for canto_y, direcao_y in ((y, -1), (y + altura, 1)):
                draw.line(
                    (canto_x + direcao_x * afastamento, canto_y,
                     canto_x + direcao_x * (afastamento + comprimento), canto_y),
                    fill=cor, width=1,
                )
                draw.line(
                    (canto_x, canto_y + direcao_y * afastamento,
                     canto_x, canto_y + direcao_y * (afastamento + comprimento)),
                    fill=cor, width=1,
                )

    def montar_folhas_pdf_turma(
        self,
        alunos: list[Aluno],
        turma: str,
        marcas_corte: bool = True,
    ) -> list[Image.Image]:
        """Monta folhas A4 paisagem com 10 crachas de 50 x 85 mm."""
        if not alunos:
            raise ValueError("A turma nao possui alunos para exportar.")

        dpi = LAYOUT["DPI"]
        mm_para_px = lambda mm: round(mm * dpi / 25.4)
        pagina_w, pagina_h = mm_para_px(297), mm_para_px(210)
        cracha_w, cracha_h = mm_para_px(50), mm_para_px(85)
        espaco = mm_para_px(3)
        colunas, linhas = 5, 2
        grade_w = colunas * cracha_w + (colunas - 1) * espaco
        grade_h = linhas * cracha_h + (linhas - 1) * espaco
        margem_x = (pagina_w - grade_w) // 2
        margem_y = (pagina_h - grade_h) // 2

        ordenados = sorted(alunos, key=self._chave_alfabetica)
        folhas = []
        total_paginas = math.ceil(len(ordenados) / (colunas * linhas))
        fonte = self._fonte_impressao(24)

        for numero_pagina in range(total_paginas):
            pagina = Image.new("RGB", (pagina_w, pagina_h), "white")
            draw = ImageDraw.Draw(pagina)
            inicio = numero_pagina * colunas * linhas
            lote = ordenados[inicio:inicio + colunas * linhas]

            for indice, aluno in enumerate(lote):
                coluna = indice % colunas
                linha = indice // colunas
                x = margem_x + coluna * (cracha_w + espaco)
                y = margem_y + linha * (cracha_h + espaco)
                cracha = self.montador.montar(aluno).convert("RGB")
                if cracha.size != (cracha_w, cracha_h):
                    cracha = cracha.resize((cracha_w, cracha_h), Image.Resampling.LANCZOS)
                pagina.paste(cracha, (x, y))
                if marcas_corte:
                    self._desenhar_marcas_corte(draw, x, y, cracha_w, cracha_h)

            rodape = f"Turma {turma} - Pagina {numero_pagina + 1}/{total_paginas}"
            caixa = draw.textbbox((0, 0), rodape, font=fonte)
            texto_x = (pagina_w - (caixa[2] - caixa[0])) // 2
            texto_y = pagina_h - max(32, margem_y // 3)
            draw.text((texto_x, texto_y), rodape, fill="#555555", font=fonte)
            folhas.append(pagina)

        return folhas

    def exportar_pdf_turma(
        self,
        alunos: list[Aluno],
        turma: str,
        caminho: str | Path,
        marcas_corte: bool = True,
    ) -> dict:
        """Salva um PDF A4 para impressao com todos os crachas da turma."""
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        folhas = self.montar_folhas_pdf_turma(alunos, turma, marcas_corte)
        temporario = caminho.with_name(f"{caminho.stem}.tmp{caminho.suffix}")
        try:
            folhas[0].save(
                temporario,
                "PDF",
                save_all=True,
                append_images=folhas[1:],
                resolution=LAYOUT["DPI"],
                quality=95,
                subsampling=0,
            )
            temporario.replace(caminho)
        finally:
            if temporario.exists():
                temporario.unlink()
            for folha in folhas:
                folha.close()

        logger.info(f"PDF da turma {turma} salvo: {caminho}")
        return {
            "caminho": caminho,
            "total_crachas": len(alunos),
            "total_paginas": len(folhas),
        }

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
