"""
Configurações gerais do sistema de crachás.
"""
import os
from pathlib import Path

# Diretório raiz do projeto
BASE_DIR = Path(__file__).parent.parent.resolve()

# Diretórios do sistema
DIRS = {
    "TURMAS": BASE_DIR / "TurmaCrachas",
    "MONTADOS": BASE_DIR / "crachas_montados",
    "FOTOS_QR": BASE_DIR / "fotos_qr_104",
    "STATIC": BASE_DIR / "static",
    "LOGS": BASE_DIR / "logs",
    "DIAG_SAIDA": BASE_DIR / "_diag_saida",
    "DIAG_ANTIGOS": BASE_DIR / "_diag_saida" / "arquivos_antigos",
    "DIAG_PREVIEWS": BASE_DIR / "_diag_saida" / "previews",
    "BACKUPS": BASE_DIR / "backups",
}

# Configurações de layout do crachá (em milímetros)
LAYOUT = {
    "LARGURA": 50,       # Largura do crachá em mm (modelo IEMA)
    "ALTURA": 85,        # Altura do crachá em mm (modelo IEMA)
    "FOTO_X": 24,        # Largura da foto em mm
    "FOTO_Y": 32,        # Altura da foto em mm
    "QR_CODE": 18,       # Tamanho do QR Code em mm
    "MARGEM": 3,         # Margem interna em mm
    "DPI": 300,          # DPI para renderização
}

# Configurações de estilo - Cores Institucionais IEMA
STYLE = {
    "FONTE_NOME": "Arial",
    "FONTE_CURSO": "Arial",
    "FONTE_TURMA": "Arial",
    "FONTE_RODAPE": "Arial",
    "TAMANHO_NOME": 16,
    "TAMANHO_CURSO": 9,
    "TAMANHO_TURMA": 11,
    "TAMANHO_RODAPE": 7,
    # Cores IEMA
    "COR_FUNDO": "#FAFDFF",
    "COR_TEXTO": "#000000",
    "COR_DESTAQUE": "#46A8BD",  # Azul IEMA
    "COR_VERDE": "#88A201",     # Verde IEMA
    "COR_ROSA": "#E54367",      # Rosa IEMA
    "COR_BRANCO": "#FFFFFF",
}

# Template de fundo do IEMA
TEMPLATE_IEMA = {
    "ARQUIVO": "static/fundo_iema.png",
    "LARGURA_PX": 591,
    "ALTURA_PX": 1004,
    # Posições em pixels (para 591x1004)
    "POS_LOGO": (40, 5, 551, 55),      # (x1, y1, x2, y2) - espaço do logo
    "POS_FOTO": (140, 70, 451, 430),   # espaço da foto (centralizado)
    "POS_CURSO": (40, 440, 551, 480),  # faixa verde - curso
    "POS_NOME": (40, 490, 551, 600),   # nome do aluno
    "POS_QR": (200, 620, 391, 811),    # QR code (centralizado)
    "POS_TURMA": (40, 820, 551, 880),  # faixa verde 2 - turma
    "POS_INFO": (40, 890, 551, 930),   # informações adicionais
    "POS_RODAPE": (40, 940, 551, 980), # faixa rosa - rodapé IEMA
}

# Formatos de saída suportados
FORMATOS_SAIDA = ["pdf", "png", "jpg", "html"]

# Extensões de planilha suportadas
EXTENSOES_PLANILHA = [".xlsx", ".xls", ".csv"]

# Configurações de log
LOG_CONFIG = {
    "NIVEL": "INFO",
    "ARQUIVO": DIRS["LOGS"] / "cracha_extractor.log",
    "FORMATO": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

# Garantir que diretórios existam
for diretorio in DIRS.values():
    diretorio.mkdir(parents=True, exist_ok=True)
