"""
Configurações gerais do sistema de crachás.
"""
from pathlib import Path

# Diretório raiz do projeto
BASE_DIR = Path(__file__).parent.parent.resolve()

# Diretórios do sistema
DIRS = {
    "TURMAS": BASE_DIR / "TurmaCrachas",
    "MONTADOS": BASE_DIR / "crachas_montados",
    "FOTOS_ALUNOS": BASE_DIR / "fotos_alunos",
    "FOTOS_QR": BASE_DIR / "fotos_qr_104",
    "STATIC": BASE_DIR / "static",
    "LOGS": BASE_DIR / "logs",
    "DIAG_SAIDA": BASE_DIR / "_diag_saida",
    "DIAG_ANTIGOS": BASE_DIR / "_diag_saida" / "arquivos_antigos",
    "DIAG_PREVIEWS": BASE_DIR / "_diag_saida" / "previews",
    "BACKUPS": BASE_DIR / "backups",
    "DATA": BASE_DIR / "data",
    "PLANILHAS": BASE_DIR / "data" / "planilhas",
    "IMPORTACOES_PENDENTES": BASE_DIR / "data" / "pendentes",
}

# Configurações de layout do crachá (em milímetros)
LAYOUT = {
    "LARGURA": 50,       # Largura do crachá em mm (5,0 cm)
    "ALTURA": 85,        # Altura do crachá em mm (8,5 cm)
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
    "ARQUIVO": "ModeloCrachaIema.png",
    "LARGURA_PX": 591,
    "ALTURA_PX": 1004,
    # Posições em pixels (para 591x1004)
    "POS_LOGO": (40, 5, 551, 55),      # (x1, y1, x2, y2) - espaço do logo
    "POS_FOTO": (143, 155, 481, 493), # interior do quadro superior
    "POS_CURSO": (55, 546, 536, 567),
    "POS_NOME": (55, 501, 536, 544),
    "POS_QR": (143, 576, 462, 895),   # interior do quadro inferior
    "POS_TURMA": (137, 903, 469, 933), # substitui a legenda Qrcode
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
