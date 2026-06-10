"""
Manipulador de fotos para os crachás.
Redimensiona, recorta e posiciona as fotos dos alunos.
"""
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageEnhance

from .config import LAYOUT, DIRS

logger = logging.getLogger(__name__)


class FotoHandler:
    """Processa e prepara fotos para os crachás."""

    def __init__(self):
        self.tamanho_foto_mm = (LAYOUT["FOTO_X"], LAYOUT["FOTO_Y"])
        self.tamanho_foto_px = self._mm_para_pixels(self.tamanho_foto_mm)

    def _mm_para_pixels(self, tamanho_mm: tuple) -> tuple:
        """Converte milímetros para pixels."""
        dpi = LAYOUT["DPI"]
        return (
            int(tamanho_mm[0] * dpi / 25.4),
            int(tamanho_mm[1] * dpi / 25.4),
        )

    def carregar_foto(self, caminho: str | Path) -> Optional[Image.Image]:
        """
        Carrega uma foto do disco.
        Suporta vários formatos de imagem.
        """
        try:
            caminho = Path(caminho)
            if not caminho.exists():
                logger.warning(f"Foto não encontrada: {caminho}")
                return None
            img = Image.open(caminho)
            # Converter para RGB se necessário
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            return img
        except Exception as e:
            logger.error(f"Erro ao carregar foto {caminho}: {e}")
            return None

    def processar_foto(self, imagem: Image.Image) -> Image.Image:
        """
        Redimensiona e centraliza a foto para caber no espaço do crachá.
        Mantém a proporção e preenche o espaço disponível.
        """
        largura, altura = self.tamanho_foto_px

        # Calcular proporção
        proporcao_original = imagem.width / imagem.height
        proporcao_desejada = largura / altura

        if proporcao_original > proporcao_desejada:
            # Imagem mais larga que o espaço
            nova_altura = altura
            nova_largura = int(altura * proporcao_original)
        else:
            # Imagem mais alta que o espaço
            nova_largura = largura
            nova_altura = int(largura / proporcao_original)

        # Redimensionar
        imagem_redim = imagem.resize((nova_largura, nova_altura), Image.LANCZOS)

        # Centralizar e recortar
        left = (nova_largura - largura) // 2
        top = (nova_altura - altura) // 2
        imagem_cortada = imagem_redim.crop((left, top, left + largura, top + altura))

        return imagem_cortada

    def ajustar_brilho(self, imagem: Image.Image, fator: float = 1.0) -> Image.Image:
        """Ajusta o brilho da foto."""
        enhancer = ImageEnhance.Brightness(imagem)
        return enhancer.enhance(fator)

    def ajustar_contraste(self, imagem: Image.Image, fator: float = 1.0) -> Image.Image:
        """Ajusta o contraste da foto."""
        enhancer = ImageEnhance.Contrast(imagem)
        return enhancer.enhance(fator)

    def buscar_foto_aluno(self, nome: str, pasta_fotos: Optional[Path] = None) -> Optional[Image.Image]:
        """
        Busca automaticamente a foto de um aluno por nome.
        Procura em várias pastas e formatos.
        """
        pastas_busca = [
            pasta_fotos,
            DIRS["FOTOS_QR"],
            DIRS["STATIC"],
        ]

        extensoes = [".jpg", ".jpeg", ".png", ".gif", ".bmp"]

        nome_normalizado = nome.replace(" ", "_").lower()

        for pasta in pastas_busca:
            if pasta is None or not pasta.exists():
                continue

            # Procurar por nome exato
            for ext in extensoes:
                candidatos = [
                    pasta / f"{nome_normalizado}{ext}",
                    pasta / f"{nome}{ext}",
                    pasta / f"{nome_normalizado.replace('_', '')}{ext}",
                ]
                for candidato in candidatos:
                    if candidato.exists():
                        logger.info(f"Foto encontrada: {candidato}")
                        return self.carregar_foto(candidato)

            # Procurar por nome parcial
            for arquivo in pasta.iterdir():
                if arquivo.suffix.lower() in extensoes:
                    nome_arquivo = arquivo.stem.lower()
                    # Verificar se o nome do aluno está contido no nome do arquivo
                    palavras_nome = nome_normalizado.split("_")
                    if all(palavra in nome_arquivo for palavra in palavras_nome if len(palavra) > 2):
                        logger.info(f"Foto encontrada (parcial): {arquivo}")
                        return self.carregar_foto(arquivo)

        logger.warning(f"Foto não encontrada para: {nome}")
        return None
