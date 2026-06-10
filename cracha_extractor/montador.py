"""
Montador de layout do crachá - Modelo IEMA.
Layout institucional com cores oficiais:
- Rosa (229,67,103), Verde (136,162,1), Azul (70,168,189)
- Faixas coloridas, foto, QR Code, nome, curso e turma
"""
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .models import Aluno, ConfiguracaoCracha
from .config import LAYOUT, STYLE, DIRS, TEMPLATE_IEMA
from .foto_handler import FotoHandler
from .qr_generator import QRCodeGenerator

logger = logging.getLogger(__name__)


class MontadorCracha:
    """
    Monta o layout do crachá no padrão IEMA.
    Utiliza template de fundo com as cores institucionais.
    """

    def __init__(self, config: Optional[ConfiguracaoCracha] = None):
        self.config = config or ConfiguracaoCracha(turma_nome="")
        self.foto_handler = FotoHandler()
        self.qr_generator = QRCodeGenerator()
        self._fontes_cache = {}

        # Dimensões fixas do template IEMA (591x1004 pixels)
        self.TEMPLATE_W = TEMPLATE_IEMA["LARGURA_PX"]
        self.TEMPLATE_H = TEMPLATE_IEMA["ALTURA_PX"]

        # Cores IEMA (RGB)
        self.COR_ROSA = (229, 67, 103)
        self.COR_VERDE = (136, 162, 1)
        self.COR_AZUL = (70, 168, 189)
        self.COR_FUNDO = (250, 253, 255)
        self.COR_BRANCO = (255, 255, 255)
        self.COR_TEXTO = (0, 0, 0)

    def _carregar_fonte(self, nome: str, tamanho: int) -> ImageFont.FreeTypeFont:
        """Carrega uma fonte com cache."""
        cache_key = f"{nome}_{tamanho}"
        if cache_key not in self._fontes_cache:
            try:
                self._fontes_cache[cache_key] = ImageFont.truetype(f"{nome}.ttf", tamanho)
            except OSError:
                try:
                    self._fontes_cache[cache_key] = ImageFont.truetype("arial.ttf", tamanho)
                except OSError:
                    self._fontes_cache[cache_key] = ImageFont.load_default()
        return self._fontes_cache[cache_key]

    def _centralizar_texto(self, draw, y: int, texto: str, fonte, cor, x1: int, x2: int):
        """Desenha texto centralizado horizontalmente entre x1 e x2."""
        bbox = draw.textbbox((0, 0), texto, font=fonte)
        largura = bbox[2] - bbox[0]
        x = x1 + (x2 - x1 - largura) // 2
        draw.text((x, y), texto, fill=cor, font=fonte)
        return x, y, largura, bbox[3] - bbox[1]

    def _criar_fundo_iema(self) -> Image.Image:
        """Cria o fundo do crachá com layout IEMA."""
        w, h = self.TEMPLATE_W, self.TEMPLATE_H
        img = Image.new("RGB", (w, h), self.COR_FUNDO)
        draw = ImageDraw.Draw(img)

        # Bordas laterais superior (0-40px) - rosa (esq) e azul (dir)
        draw.rectangle([(0, 0), (40, 40)], fill=self.COR_ROSA)
        draw.rectangle([(w - 40, 0), (w, 40)], fill=self.COR_AZUL)

        # Fundo com gradiente (40-440px)
        for y in range(40, 440):
            fator = (y - 40) / 400
            r = int(225 + (250 - 225) * (1 - fator))
            g = int(245 + (253 - 245) * (1 - fator))
            b = int(255 + (255 - 255) * (1 - fator))
            draw.line([(40, y), (w - 40, y)], fill=(r, g, b))

        # Faixa verde 1 - CURSO (440-480px)
        draw.rectangle([(0, 440), (w, 480)], fill=self.COR_VERDE)
        draw.rectangle([(0, 440), (40, 480)], fill=self.COR_ROSA)
        draw.rectangle([(w - 40, 440), (w, 480)], fill=self.COR_AZUL)

        # Área central com gradiente (480-820px)
        for y in range(480, 820):
            fator = (y - 480) / 340
            r = int(250 - (250 - 225) * fator)
            g = int(253 - (253 - 245) * fator)
            b = int(255 - (255 - 255) * fator)
            draw.line([(40, y), (w - 40, y)], fill=(r, g, b))

        # Bordas laterais área central
        draw.rectangle([(0, 480), (40, 820)], fill=self.COR_AZUL)
        draw.rectangle([(w - 40, 480), (w, 820)], fill=self.COR_ROSA)

        # Faixa verde 2 - TURMA (820-880px)
        draw.rectangle([(0, 820), (w, 880)], fill=self.COR_VERDE)
        draw.rectangle([(0, 820), (40, 880)], fill=self.COR_AZUL)
        draw.rectangle([(w - 40, 820), (w, 880)], fill=self.COR_ROSA)

        # Faixa azul (880-920px)
        draw.rectangle([(0, 880), (w, 920)], fill=self.COR_AZUL)

        # Faixa rosa - RODAPÉ (940-980px)
        draw.rectangle([(0, 940), (w, 980)], fill=self.COR_ROSA)

        # Base azul (980-1004px)
        draw.rectangle([(0, 980), (w, 1004)], fill=self.COR_AZUL)

        return img

    def montar(self, aluno: Aluno) -> Image.Image:
        """
        Monta o crachá IEMA completo para um aluno.
        Layout:
        - Topo: bordas rosa/azul com gradiente
        - Centro: FOTO do aluno
        - Faixa verde 1: CURSO
        - Centro: NOME e QR CODE
        - Faixa verde 2: TURMA
        - Faixa azul/rosa: informações IEMA
        """
        w, h = self.TEMPLATE_W, self.TEMPLATE_H

        # 1. Criar fundo IEMA
        cracha = self._criar_fundo_iema()
        draw = ImageDraw.Draw(cracha)

        # 2. FOTO do aluno (centralizada, área ~140-451 x 70-430)
        x_foto1, y_foto1, x_foto2, y_foto2 = TEMPLATE_IEMA["POS_FOTO"]
        foto_largura = x_foto2 - x_foto1
        foto_altura = y_foto2 - y_foto1

        foto = None
        if self.config.mostrar_foto:
            if aluno.foto_caminho:
                foto = self.foto_handler.carregar_foto(aluno.foto_caminho)
            else:
                foto = self.foto_handler.buscar_foto_aluno(aluno.nome)

        if foto:
            # Redimensionar foto para caber no espaço
            foto_redim = foto.resize((foto_largura, foto_altura), Image.LANCZOS)
            cracha.paste(foto_redim, (x_foto1, y_foto1))
        else:
            # Placeholder com borda
            draw.rectangle(
                [(x_foto1, y_foto1), (x_foto2, y_foto2)],
                outline="#CCCCCC",
                fill="#F0F0F0",
            )
            fonte_placeholder = self._carregar_fonte("Arial", 24)
            self._centralizar_texto(
                draw, y_foto1 + (foto_altura - 30) // 2,
                "FOTO", fonte_placeholder, "#AAAAAA",
                x_foto1, x_foto2,
            )

        # 3. CURSO na faixa verde (440-480px)
        texto_curso = aluno.curso if aluno.curso else "ENSINO MÉDIO INTEGRADO"
        fonte_curso = self._carregar_fonte("Arial", STYLE["TAMANHO_CURSO"] * 3)
        self._centralizar_texto(
            draw, 448, texto_curso, fonte_curso, self.COR_BRANCO,
            40, w - 40,
        )

        # 4. NOME do aluno (área 490-600px)
        fonte_nome = self._carregar_fonte("Arial", STYLE["TAMANHO_NOME"] * 3)
        nome = aluno.nome if len(aluno.nome) < 35 else aluno.nome[:32] + "..."
        self._centralizar_texto(
            draw, 510, nome, fonte_nome, self.COR_TEXTO,
            40, w - 40,
        )

        # 5. QR CODE (centralizado, 620-811px)
        if self.config.mostrar_qr_code:
            dados_qr = aluno.qr_code_dados or self.qr_generator.gerar_para_aluno(aluno.nome, aluno.turma)
            qr_img = self.qr_generator.gerar(dados_qr, "#46A8BD")
            qr_tamanho = 190  # pixels
            qr_img = qr_img.resize((qr_tamanho, qr_tamanho), Image.LANCZOS)
            x_qr = (w - qr_tamanho) // 2
            y_qr = 625
            cracha.paste(qr_img, (x_qr, y_qr))

        # 6. TURMA na faixa verde 2 (820-880px)
        texto_turma = f"TURMA {aluno.turma}" if aluno.turma else ""
        if texto_turma:
            fonte_turma = self._carregar_fonte("Arial", STYLE["TAMANHO_TURMA"] * 3)
            self._centralizar_texto(
                draw, 838, texto_turma, fonte_turma, self.COR_BRANCO,
                40, w - 40,
            )

        # 7. Informações na faixa azul (880-920px)
        fonte_info = self._carregar_fonte("Arial", STYLE["TAMANHO_RODAPE"] * 3)
        self._centralizar_texto(
            draw, 895,
            "INSTITUTO ESTADUAL DE EDUCAÇÃO, CIÊNCIA E TECNOLOGIA DO MARANHÃO",
            fonte_info, self.COR_BRANCO, 40, w - 40,
        )

        # 8. Rodapé na faixa rosa (940-980px)
        fonte_rodape = self._carregar_fonte("Arial", STYLE["TAMANHO_RODAPE"] * 3)
        self._centralizar_texto(
            draw, 955,
            "IEMA - ENSINO MÉDIO INTEGRADO",
            fonte_rodape, self.COR_BRANCO, 40, w - 40,
        )

        logger.info(f"Crachá IEMA montado para: {aluno.nome}")
        return cracha

    def montar_html(self, aluno: Aluno) -> str:
        """
        Gera uma representação HTML do crachá no padrão IEMA.
        Útil para visualização ou impressão via navegador.
        """
        qr_data = aluno.qr_code_dados or self.qr_generator.gerar_para_aluno(aluno.nome, aluno.turma)

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Crachá IEMA - {aluno.nome}</title>
    <style>
        @page {{
            size: 50mm 85mm;
            margin: 0;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            width: 50mm;
            height: 85mm;
            font-family: Arial, sans-serif;
            background: #FAFDFF;
            position: relative;
            overflow: hidden;
        }}
        .borda-esq {{
            position: absolute;
            left: 0;
            top: 0;
            width: 3.4mm;
            height: 3.4mm;
            background: #E54367;
        }}
        .borda-dir {{
            position: absolute;
            right: 0;
            top: 0;
            width: 3.4mm;
            height: 3.4mm;
            background: #46A8BD;
        }}
        .gradiente {{
            position: absolute;
            left: 3.4mm;
            right: 3.4mm;
            top: 3.4mm;
            height: 34mm;
            background: linear-gradient(180deg, #E1F5FF, #FAFDFF);
        }}
        .foto {{
            position: absolute;
            left: 12mm;
            top: 6mm;
            width: 26mm;
            height: 30mm;
            background: #f0f0f0;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #999;
            font-size: 8pt;
            overflow: hidden;
        }}
        .foto img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        .faixa-curso {{
            position: absolute;
            left: 0;
            top: 37.3mm;
            width: 50mm;
            height: 3.4mm;
            background: #88A201;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 6pt;
            font-weight: bold;
            letter-spacing: 0.5px;
        }}
        .faixa-curso::before {{
            content: '';
            position: absolute;
            left: 0;
            width: 3.4mm;
            height: 100%;
            background: #E54367;
        }}
        .faixa-curso::after {{
            content: '';
            position: absolute;
            right: 0;
            width: 3.4mm;
            height: 100%;
            background: #46A8BD;
        }}
        .nome {{
            position: absolute;
            left: 3.4mm;
            right: 3.4mm;
            top: 41.5mm;
            text-align: center;
            font-size: 10pt;
            font-weight: bold;
            color: #000;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .qr-code {{
            position: absolute;
            left: 50%;
            transform: translateX(-50%);
            top: 53mm;
            width: 16mm;
            height: 16mm;
        }}
        .qr-code img {{
            width: 100%;
            height: 100%;
        }}
        .faixa-turma {{
            position: absolute;
            left: 0;
            top: 69.5mm;
            width: 50mm;
            height: 5.1mm;
            background: #88A201;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 8pt;
            font-weight: bold;
        }}
        .faixa-turma::before {{
            content: '';
            position: absolute;
            left: 0;
            width: 3.4mm;
            height: 100%;
            background: #46A8BD;
        }}
        .faixa-turma::after {{
            content: '';
            position: absolute;
            right: 0;
            width: 3.4mm;
            height: 100%;
            background: #E54367;
        }}
        .faixa-azul {{
            position: absolute;
            left: 0;
            top: 74.6mm;
            width: 50mm;
            height: 3.4mm;
            background: #46A8BD;
        }}
        .info {{
            position: absolute;
            left: 3.4mm;
            right: 3.4mm;
            top: 75.8mm;
            text-align: center;
            font-size: 4.5pt;
            color: white;
            line-height: 1.2;
        }}
        .faixa-rosa {{
            position: absolute;
            left: 0;
            top: 79.7mm;
            width: 50mm;
            height: 3.4mm;
            background: #E54367;
        }}
        .rodape {{
            position: absolute;
            left: 3.4mm;
            right: 3.4mm;
            top: 81mm;
            text-align: center;
            font-size: 5pt;
            color: white;
            font-weight: bold;
        }}
        .base-azul {{
            position: absolute;
            left: 0;
            bottom: 0;
            width: 50mm;
            height: 2mm;
            background: #46A8BD;
        }}
    </style>
</head>
<body>
    <div class="borda-esq"></div>
    <div class="borda-dir"></div>

    <div class="foto">
        {f'<img src="{aluno.foto_caminho}" alt="Foto">' if aluno.foto_caminho else 'FOTO'}
    </div>

    <div class="faixa-curso">{aluno.curso or "ENSINO MÉDIO INTEGRADO"}</div>

    <div class="nome">{aluno.nome}</div>

    <div class="qr-code">
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={qr_data}" alt="QR">
    </div>

    <div class="faixa-turma">TURMA {aluno.turma}</div>

    <div class="faixa-azul"></div>
    <div class="info">INSTITUTO ESTADUAL DE EDUCAÇÃO,<br>CIÊNCIA E TECNOLOGIA DO MARANHÃO</div>

    <div class="faixa-rosa"></div>
    <div class="rodape">IEMA - ENSINO MÉDIO INTEGRADO</div>

    <div class="base-azul"></div>
</body>
</html>"""
        return html
