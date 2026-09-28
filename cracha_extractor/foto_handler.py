"""
Manipulador de fotos para os crachás.
Redimensiona, recorta e posiciona as fotos dos alunos.
"""
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from PIL import Image, ImageEnhance

from .config import BASE_DIR, LAYOUT, DIRS

logger = logging.getLogger(__name__)


class FotoHandler:
    """Processa e prepara fotos para os crachás."""

    def __init__(self):
        self.tamanho_foto_mm = (LAYOUT["FOTO_X"], LAYOUT["FOTO_Y"])
        self.tamanho_foto_px = self._mm_para_pixels(self.tamanho_foto_mm)
        self.ultima_foto_caminho: Optional[Path] = None

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
            if not caminho.is_absolute():
                caminho = BASE_DIR / caminho
            if not caminho.exists():
                logger.warning(f"Foto não encontrada: {caminho}")
                return None
            img = Image.open(caminho)
            # Converter para RGB se necessário
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            self.ultima_foto_caminho = caminho.resolve()
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

    def buscar_foto_aluno(
        self,
        nome: str,
        pasta_fotos: Optional[Path] = None,
        codigo: Optional[str] = None,
        turma: Optional[str] = None,
    ) -> Optional[Image.Image]:
        """
        Busca automaticamente a foto de um aluno por código ou nome.
        Procura em várias pastas e formatos.
        """
        pastas_base = [
            pasta_fotos,
            DIRS["FOTOS_ALUNOS"],
            DIRS["FOTOS_QR"],
            DIRS["STATIC"],
        ]
        pastas_busca = []
        if turma:
            nome_turma = str(turma).strip()
            pastas_busca.extend(
                pasta / nome_turma for pasta in pastas_base if pasta is not None
            )
        pastas_busca.extend(pastas_base)
        # Preserva a prioridade e evita examinar a mesma pasta duas vezes.
        pastas_busca = list(dict.fromkeys(pastas_busca))

        extensoes = [".jpg", ".jpeg", ".png", ".gif", ".bmp"]

        nome_normalizado = self._normalizar_nome(nome)
        codigo_normalizado = self._normalizar_codigo(codigo)

        for pasta in pastas_busca:
            if pasta is None or not pasta.exists():
                continue

            arquivos = sorted(
                (arquivo for arquivo in pasta.iterdir() if arquivo.suffix.lower() in extensoes),
                key=lambda arquivo: arquivo.name.lower(),
            )
            if codigo_normalizado:
                for arquivo in arquivos:
                    nome_arquivo = self._normalizar_nome(arquivo.stem)
                    if (nome_arquivo == codigo_normalizado
                            or nome_arquivo.startswith(f"{codigo_normalizado}_")
                            or nome_arquivo.endswith(f"_{codigo_normalizado}")):
                        logger.info(f"Foto encontrada pelo código: {arquivo}")
                        return self.carregar_foto(arquivo)

            for arquivo in arquivos:
                nome_arquivo = self._normalizar_nome(arquivo.stem)
                if nome_arquivo in (nome_normalizado, nome_normalizado.replace("_", "")):
                    logger.info(f"Foto encontrada: {arquivo}")
                    return self.carregar_foto(arquivo)

            # As fotos fornecidas podem conter apenas parte do nome completo.
            # Ex.: "Andressa Aguiar.jpg" para "ANDRESSA AGUIAR ARAUJO".
            palavras_aluno = self._palavras_relevantes(nome_normalizado)
            correspondencias = []
            for arquivo in arquivos:
                palavras_arquivo = self._palavras_relevantes(
                    self._normalizar_nome(arquivo.stem)
                )
                pontuacao = self._pontuacao_nome_abreviado(
                    palavras_arquivo, palavras_aluno
                )
                if len(palavras_arquivo) >= 2 and pontuacao is not None:
                    correspondencias.append((pontuacao, len(palavras_arquivo), arquivo))
            if correspondencias:
                arquivo = max(correspondencias, key=lambda item: (item[0], item[1]))[2]
                logger.info(f"Foto encontrada pelo nome abreviado: {arquivo}")
                return self.carregar_foto(arquivo)

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
        self.ultima_foto_caminho = None
        return None

    @staticmethod
    def _normalizar_nome(valor: str) -> str:
        sem_acentos = unicodedata.normalize("NFKD", str(valor))
        sem_acentos = "".join(c for c in sem_acentos if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", "_", sem_acentos.lower()).strip("_")

    @classmethod
    def _normalizar_codigo(cls, valor: Optional[str]) -> str:
        if valor is None:
            return ""
        codigo = str(valor).strip()
        if re.fullmatch(r"\d+\.0", codigo):
            codigo = codigo[:-2]
        return cls._normalizar_nome(codigo)

    @staticmethod
    def _palavras_relevantes(nome_normalizado: str) -> set[str]:
        conectivos = {"da", "das", "de", "do", "dos", "e"}
        return {
            palavra for palavra in nome_normalizado.split("_")
            if len(palavra) > 1 and palavra not in conectivos
        }

    @classmethod
    def _pontuacao_nome_abreviado(
        cls,
        palavras_arquivo: set[str],
        palavras_aluno: set[str],
    ) -> Optional[int]:
        pontuacao = 0
        for palavra_foto in palavras_arquivo:
            melhor = 0
            for palavra_aluno in palavras_aluno:
                if palavra_foto == palavra_aluno:
                    melhor = max(melhor, 3)
                elif SequenceMatcher(None, palavra_foto, palavra_aluno).ratio() >= 0.80:
                    melhor = max(melhor, 2)
                elif (min(len(palavra_foto), len(palavra_aluno)) >= 4
                      and cls._distancia_edicao(palavra_foto, palavra_aluno) <= 2):
                    melhor = max(melhor, 1)
            if melhor == 0:
                return None
            pontuacao += melhor
        return pontuacao

    @staticmethod
    def _distancia_edicao(primeira: str, segunda: str) -> int:
        anterior = list(range(len(segunda) + 1))
        for indice, caractere_primeira in enumerate(primeira, start=1):
            atual = [indice]
            for outro_indice, caractere_segunda in enumerate(segunda, start=1):
                atual.append(min(
                    atual[-1] + 1,
                    anterior[outro_indice] + 1,
                    anterior[outro_indice - 1] + (caractere_primeira != caractere_segunda),
                ))
            anterior = atual
        return anterior[-1]
