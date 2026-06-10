"""
Leitor de planilhas Excel/CSV para extrair dados dos alunos.
Suporta detecção automática de colunas e mapeamento específico
para planilhas do IEMA.
"""
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from .models import Aluno, Turma
from .config import EXTENSOES_PLANILHA
from .turmas_iema import obter_curso_por_turma

logger = logging.getLogger(__name__)


class PlanilhaReader:
    """Lê planilhas Excel/CSV e extrai dados dos alunos."""

    # Mapeamento de possíveis nomes de colunas
    MAPA_COLUNAS = {
        "nome": ["nome", "nome do aluno", "aluno", "name", "estudante", "nome completo"],
        "turma": ["turma", "classe", "sala", "turma/código", "código turma"],
        "curso": ["curso", "disciplina", "matéria", "programa", "formação"],
        "matricula": ["matrícula", "matricula", "ra", "registro", "codigo", "código aluno", "id", "código"],
        "foto": ["foto", "fotografia", "image", "imagem", "caminho foto", "arquivo foto"],
        "qr_data": ["qr", "qr code", "qrcode", "dados qr", "link", "url"],
        "observacao": ["obs", "observação", "observacao", "nota", "informação adicional", "situacao"],
        "data_nascimento": ["data_nascimento", "data de nascimento", "nascimento", "nasc", "dt_nasc"],
        "cpf": ["cpf", "documento", "doc", "rg"],
        "telefone": ["telefone", "celular", "whatsapp", "contato", "fone"],
    }

    # Colunas a serem ignoradas na detecção (evita falsos positivos)
    COLUNAS_IGNORADAS = ["data_hora_entrada", "data_hora_saida", "data_envio", "mensagem_enviada",
                         "situacao_entrada", "situacao_saida"]

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self._validar_arquivo()
        self.df: Optional[pd.DataFrame] = None
        self.colunas_mapeadas: dict = {}

    def _validar_arquivo(self):
        """Valida se o arquivo existe e tem extensão suportada."""
        if self.caminho.suffix.lower() not in EXTENSOES_PLANILHA:
            raise ValueError(
                f"Extensão não suportada: {self.caminho.suffix}. "
                f"Use: {', '.join(EXTENSOES_PLANILHA)}"
            )
        if not self.caminho.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {self.caminho}")

    def _detectar_colunas(self) -> dict:
        """
        Detecta automaticamente o mapeamento das colunas da planilha.
        Retorna um dict com as colunas padronizadas.
        """
        colunas_dict = {}
        colunas_planilha = [str(c).strip().lower() for c in self.df.columns]

        for padrao, variacoes in self.MAPA_COLUNAS.items():
            for var in variacoes:
                for idx, col in enumerate(colunas_planilha):
                    # Pular colunas explicitamente ignoradas
                    coluna_original = self.df.columns[idx]
                    if str(coluna_original).strip().lower() in self.COLUNAS_IGNORADAS:
                        continue
                    if var == col or var in col:
                        colunas_dict[padrao] = self.df.columns[idx]
                        break
                if padrao in colunas_dict:
                    break

        logger.info(f"Colunas detectadas: {colunas_dict}")
        return colunas_dict

    def ler(self) -> list[Aluno]:
        """
        Lê a planilha e retorna uma lista de objetos Aluno.
        Tenta detectar automaticamente as colunas.
        """
        logger.info(f"Lendo planilha: {self.caminho}")

        # Carregar arquivo
        if self.caminho.suffix.lower() == ".csv":
            self.df = pd.read_csv(self.caminho, encoding="utf-8-sig")
        else:
            self.df = pd.read_excel(self.caminho)

        # Detectar colunas
        self.colunas_mapeadas = self._detectar_colunas()

        if "nome" not in self.colunas_mapeadas:
            raise ValueError(
                "Não foi possível detectar a coluna 'nome' na planilha. "
                "Verifique se a planilha tem uma coluna chamada 'Nome' ou similar."
            )

        alunos = []
        tem_coluna_curso = "curso" in self.colunas_mapeadas

        for _, row in self.df.iterrows():
            try:
                turma_str = self._get_valor(row, "turma", "")

                # Se não tem coluna de curso, detectar pela turma
                curso = self._get_valor(row, "curso", "")
                if not curso and turma_str:
                    curso = obter_curso_por_turma(turma_str)

                aluno = Aluno(
                    nome=self._get_valor(row, "nome", ""),
                    turma=turma_str,
                    curso=curso,
                    matricula=self._get_valor(row, "matricula", ""),
                    foto_caminho=self._get_valor(row, "foto", None),
                    qr_code_dados=self._get_valor(row, "qr_data", None),
                    observacao=self._get_valor(row, "observacao", None),
                    data_nascimento=self._get_valor(row, "data_nascimento", None),
                    cpf=self._get_valor(row, "cpf", None),
                )
                if aluno.nome:
                    alunos.append(aluno)
            except Exception as e:
                logger.warning(f"Erro ao processar linha {row.name}: {e}")

        logger.info(f"Total de alunos lidos: {len(alunos)}")
        return alunos

    def _get_valor(self, row, chave: str, default=None):
        """Obtém o valor de uma célula da planilha."""
        if chave in self.colunas_mapeadas:
            col = self.colunas_mapeadas[chave]
            valor = row.get(col)
            if pd.isna(valor):
                return default
            if isinstance(valor, str):
                return valor.strip()
            if isinstance(valor, (int, float)):
                return str(valor)
            return valor
        return default

    def agrupar_por_turma(self, alunos: list[Aluno]) -> dict[str, Turma]:
        """Agrupa alunos por turma."""
        turmas: dict[str, Turma] = {}
        for aluno in alunos:
            nome_turma = aluno.turma or "SEM TURMA"
            if nome_turma not in turmas:
                turmas[nome_turma] = Turma(nome=nome_turma, curso=aluno.curso)
            turmas[nome_turma].adicionar_aluno(aluno)
        return turmas

    def listar_colunas(self) -> list[str]:
        """Retorna a lista de colunas encontradas na planilha."""
        if self.df is None:
            if self.caminho.suffix.lower() == ".csv":
                self.df = pd.read_csv(self.caminho, encoding="utf-8-sig", nrows=0)
            else:
                self.df = pd.read_excel(self.caminho, nrows=0)
        return list(self.df.columns)
