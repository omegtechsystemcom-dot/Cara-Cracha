"""Composição dos crachás sobre a arte original do IEMA."""
import base64
from html import escape
import io
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode
from .config import BASE_DIR, TEMPLATE_IEMA
from .models import Aluno, ConfiguracaoCracha
from .foto_handler import FotoHandler
from .qr_generator import QRCodeGenerator


class MontadorCracha:
    def __init__(self, config: Optional[ConfiguracaoCracha] = None):
        self.config = config or ConfiguracaoCracha(turma_nome="")
        self.foto_handler = FotoHandler()
        self.qr_generator = QRCodeGenerator()
        self._fontes_cache = {}
        self.TEMPLATE_W = TEMPLATE_IEMA["LARGURA_PX"]
        self.TEMPLATE_H = TEMPLATE_IEMA["ALTURA_PX"]

    def _carregar_fonte(self, nome, tamanho):
        chave = (nome, tamanho)
        if chave not in self._fontes_cache:
            for arquivo in (f"{nome}.ttf", "arial.ttf", "DejaVuSans.ttf"):
                try:
                    fonte = ImageFont.truetype(arquivo, tamanho)
                    break
                except OSError:
                    continue
            else:
                fonte = ImageFont.load_default(size=tamanho)
            self._fontes_cache[chave] = fonte
        return self._fontes_cache[chave]

    def _criar_fundo_iema(self):
        with Image.open(BASE_DIR / TEMPLATE_IEMA["ARQUIVO"]) as original:
            fundo = original.convert("RGB")
        if fundo.size != (self.TEMPLATE_W, self.TEMPLATE_H):
            raise ValueError("O modelo IEMA deve ter 591 × 1004 pixels.")
        return fundo

    def _texto_na_area(self, draw, texto, area, tamanho, cor, linhas=1):
        """Ajusta fonte e quebra de linha sem truncar o nome."""
        x1, y1, x2, y2 = area
        texto = " ".join(texto.split())
        if not texto:
            return
        for pontos in range(tamanho, 0, -1):
            fonte = self._carregar_fonte("arialbd", pontos)
            partes = [""]
            for palavra in texto.split():
                tentativa = (partes[-1] + " " + palavra).strip()
                if partes[-1] and draw.textlength(tentativa, font=fonte) > x2-x1:
                    partes.append(palavra)
                else:
                    partes[-1] = tentativa
            conteudo = "\n".join(partes)
            bbox = draw.multiline_textbbox((0, 0), conteudo, font=fonte, spacing=2)
            if len(partes) <= linhas and bbox[2]-bbox[0] <= x2-x1 and bbox[3]-bbox[1] <= y2-y1:
                break
        x = x1 + (x2-x1-(bbox[2]-bbox[0]))/2 - bbox[0]
        y = y1 + (y2-y1-(bbox[3]-bbox[1]))/2 - bbox[1]
        draw.multiline_text((x, y), conteudo, font=fonte, fill=cor, align="center", spacing=2)

    def montar(self, aluno: Aluno) -> Image.Image:
        self.foto_handler.ultima_foto_caminho = None
        cracha = self._criar_fundo_iema()
        draw = ImageDraw.Draw(cracha)
        fundo = cracha.getpixel((80, 520))
        foto_area = TEMPLATE_IEMA["POS_FOTO"]
        qr_area = TEMPLATE_IEMA["POS_QR"]
        # Substitui somente o conteúdo dos quadros e a legenda Qrcode.
        for area in (foto_area, qr_area, TEMPLATE_IEMA["POS_TURMA"]):
            x1, y1, x2, y2 = area
            draw.rectangle((x1, y1, x2-1, y2-1), fill=fundo)
        if self.config.mostrar_foto:
            foto = None
            if aluno.foto_caminho:
                foto = self.foto_handler.carregar_foto(aluno.foto_caminho)
            if foto is None:
                foto = self.foto_handler.buscar_foto_aluno(
                    aluno.nome,
                    codigo=aluno.matricula,
                    turma=aluno.turma,
                )
            if foto is not None:
                x1, y1, x2, y2 = foto_area
                foto = ImageOps.fit(ImageOps.exif_transpose(foto).convert("RGB"),
                                    (x2-x1, y2-y1), method=Image.Resampling.LANCZOS)
                cracha.paste(foto, (x1, y1))
            else:
                self._texto_na_area(draw, "FOTO", foto_area, 26, "#46A8BD")
        self._texto_na_area(draw, aluno.nome, TEMPLATE_IEMA["POS_NOME"], 26, "#202020", linhas=2)
        self._texto_na_area(draw, aluno.curso or "ENSINO MÉDIO INTEGRADO",
                            TEMPLATE_IEMA["POS_CURSO"], 20, "#28798B")
        self._texto_na_area(draw, f"TURMA {aluno.turma}" if aluno.turma else "",
                            TEMPLATE_IEMA["POS_TURMA"], 24, "#E54367")
        if self.config.mostrar_qr_code:
            dados = self.qr_generator.gerar_para_aluno(
                aluno.nome,
                aluno.turma,
                dados_extras=aluno.qr_code_dados,
                codigo=aluno.matricula,
            )
            qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, border=4, box_size=1)
            qr.add_data(dados)
            qr.make(fit=True)
            x1, y1, x2, y2 = qr_area
            modulos = len(qr.get_matrix())
            escala = min(x2-x1, y2-y1) // modulos
            if escala < 1:
                raise ValueError("Conteúdo do QR Code excede a área disponível no crachá.")
            lado = modulos * escala
            imagem_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            # Escala inteira mantém módulos nítidos e margem de quatro módulos.
            imagem_qr = imagem_qr.resize((lado, lado), Image.Resampling.NEAREST)
            draw.rectangle((x1, y1, x2-1, y2-1), fill="white")
            cracha.paste(imagem_qr, (x1+(x2-x1-lado)//2, y1+(y2-y1-lado)//2))
        return cracha

    def montar_html(self, aluno: Aluno) -> str:
        """HTML portátil idêntico à prévia, sem depender de serviços externos."""
        buffer = io.BytesIO()
        self.montar(aluno).save(buffer, format="PNG")
        imagem = base64.b64encode(buffer.getvalue()).decode("ascii")
        descricao = escape(f"Crachá IEMA - {aluno.nome} - Turma {aluno.turma}", quote=True)
        return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>{descricao}</title>
<style>
@page {{ size: 50mm 85mm; margin: 0; }}
html, body {{ margin: 0; padding: 0; width: 50mm; height: 85mm; }}
img {{ display: block; width: 50mm; height: 85mm; }}
</style></head>
<body><img src="data:image/png;base64,{imagem}" alt="{descricao}"></body>
</html>'''
