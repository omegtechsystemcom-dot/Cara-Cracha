"""
Mapeamento de turmas do IEMA para cursos.
Baseado na estrutura: 1º ano = 1XX, 2º ano = 2XX, 3º ano = 3XX
"""
from dataclasses import dataclass

@dataclass
class InfoTurma:
    numero: str
    curso: str
    ano: str
    turno: str = "Integral"

# Mapeamento completo das turmas do IEMA
# O primeiro dígito indica o ano, os dois últimos o número da turma
MAPA_TURMAS_CURSOS: dict[str, InfoTurma] = {
    "101": InfoTurma("101", "ENSINO MÉDIO INTEGRADO", "1º Ano"),
    "102": InfoTurma("102", "ENSINO MÉDIO INTEGRADO", "1º Ano"),
    "103": InfoTurma("103", "ENSINO MÉDIO INTEGRADO", "1º Ano"),
    "104": InfoTurma("104", "ENSINO MÉDIO INTEGRADO", "1º Ano"),
    "201": InfoTurma("201", "ENSINO MÉDIO INTEGRADO", "2º Ano"),
    "202": InfoTurma("202", "ENSINO MÉDIO INTEGRADO", "2º Ano"),
    "203": InfoTurma("203", "ENSINO MÉDIO INTEGRADO", "2º Ano"),
    "204": InfoTurma("204", "ENSINO MÉDIO INTEGRADO", "2º Ano"),
    "301": InfoTurma("301", "ENSINO MÉDIO INTEGRADO", "3º Ano"),
    "302": InfoTurma("302", "ENSINO MÉDIO INTEGRADO", "3º Ano"),
    "303": InfoTurma("303", "ENSINO MÉDIO INTEGRADO", "3º Ano"),
    "304": InfoTurma("304", "ENSINO MÉDIO INTEGRADO", "3º Ano"),
}


def obter_curso_por_turma(turma: str) -> str:
    """Retorna o curso completo baseado no número da turma."""
    info = MAPA_TURMAS_CURSOS.get(turma)
    if info:
        return f"{info.curso} - {info.ano}"
    return "ENSINO MÉDIO INTEGRADO"


def obter_ano_por_turma(turma: str) -> str:
    """Retorna o ano baseado no número da turma."""
    info = MAPA_TURMAS_CURSOS.get(turma)
    return info.ano if info else ""


def listar_todas_turmas() -> list[str]:
    """Lista todas as turmas cadastradas."""
    return sorted(MAPA_TURMAS_CURSOS.keys())
