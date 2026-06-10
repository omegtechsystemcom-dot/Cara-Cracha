"""
Modelos de dados para o sistema de crachás.
"""
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from datetime import datetime


@dataclass
class Aluno:
    """Dados de um aluno para impressão do crachá."""
    nome: str
    turma: str
    curso: str
    matricula: str = ""
    foto_caminho: Optional[str] = None
    qr_code_dados: Optional[str] = None
    observacao: Optional[str] = None
    data_nascimento: Optional[str] = None
    cpf: Optional[str] = None

    def __post_init__(self):
        self.nome = self.nome.strip().upper() if self.nome else ""
        self.turma = self.turma.strip().upper() if self.turma else ""


@dataclass
class Turma:
    """Representa uma turma com seus alunos."""
    nome: str
    curso: str
    alunos: list[Aluno] = field(default_factory=list)
    ano: int = datetime.now().year

    def adicionar_aluno(self, aluno: Aluno):
        aluno.turma = self.nome
        aluno.curso = self.curso
        self.alunos.append(aluno)

    @property
    def quantidade_alunos(self) -> int:
        return len(self.alunos)


@dataclass
class ConfiguracaoCracha:
    """Configuração de layout do crachá para uma turma."""
    turma_nome: str
    cor_fundo: str = "#FFFFFF"
    cor_destaque: str = "#1a5276"
    logo_caminho: Optional[Path] = None
    template_html: Optional[str] = None
    mostrar_foto: bool = True
    mostrar_qr_code: bool = True
    mostrar_logo: bool = True
    orientacao: str = "vertical"  # vertical ou horizontal
