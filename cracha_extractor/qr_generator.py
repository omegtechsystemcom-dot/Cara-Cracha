"""
Gerador de QR Codes para os crachás.
"""
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import qrcode
from qrcode.image.pil import PilImage
from PIL import Image

from .config import DIRS, LAYOUT

logger = logging.getLogger(__name__)


class QRCodeGenerator:
    """Gera QR Codes para os crachás."""

    def __init__(self, tamanho: int = None):
        self.tamanho = tamanho or LAYOUT["QR_CODE"]
        self.pixels = self._mm_para_pixels(self.tamanho)

    def _mm_para_pixels(self, mm: float) -> int:
        """Converte milímetros para pixels baseado no DPI configurado."""
        return int(mm * LAYOUT["DPI"] / 25.4)

    def gerar(self, dados: str, cor: str = "#1a5276") -> Image.Image:
        """
        Gera um QR Code a partir dos dados fornecidos.
        Retorna uma imagem PIL.
        """
        qr = qrcode.QRCode(
            version=None,  # Auto-detect
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Alta correção
            box_size=10,
            border=2,
        )
        qr.add_data(dados)
        qr.make(fit=True)

        # Criar imagem do QR Code
        qr_img = qr.make_image(
            image_factory=PilImage,
            fill_color=cor,
            back_color="white",
        )

        # Redimensionar para o tamanho desejado
        qr_img = qr_img.resize((self.pixels, self.pixels), Image.LANCZOS)
        return qr_img

    def salvar(self, dados: str, caminho: str | Path, cor: str = "#1a5276") -> Path:
        """Gera e salva o QR Code em um arquivo."""
        caminho = Path(caminho)
        img = self.gerar(dados, cor)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        img.save(caminho, "PNG")
        logger.info(f"QR Code salvo: {caminho}")
        return caminho

    @staticmethod
    def normalizar_codigo(codigo: object) -> str:
        """Normaliza o identificador sem alterar zeros significativos."""
        codigo_normalizado = str(codigo).strip() if codigo is not None else ""
        if codigo_normalizado.endswith(".0") and codigo_normalizado[:-2].isdigit():
            codigo_normalizado = codigo_normalizado[:-2]
        return codigo_normalizado.upper()

    def gerar_para_aluno(
        self,
        nome: str,
        turma: str,
        dados_extras: Optional[str] = None,
        codigo: object = None,
    ) -> str:
        """
        Gera os dados para o QR Code de um aluno.
        Pode conter um link, matrícula, ou informações personalizadas.
        """
        codigo_normalizado = self.normalizar_codigo(codigo)
        if not codigo_normalizado:
            raise ValueError(f"Aluno sem codigo oficial: {nome}")

        partes = [
            "IEMA",
            "V1",
            f"COD={quote(codigo_normalizado, safe='-_.')}",
            f"TURMA={quote(str(turma).strip().upper(), safe='-_.')}",
        ]
        if dados_extras and str(dados_extras).strip():
            partes.append(f"DADOS={quote(str(dados_extras).strip(), safe='-_.:/')}")
        return "|".join(partes)
