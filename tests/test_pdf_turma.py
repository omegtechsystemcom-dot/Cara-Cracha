from pathlib import Path

from PIL import Image

from cracha_extractor import api
from cracha_extractor.config import LAYOUT
from cracha_extractor.exportador import ExportadorCracha
from cracha_extractor.models import Aluno
from cracha_extractor.utils import Diagnosticador


class MontadorFalso:
    def __init__(self):
        self.chamadas = []

    def montar(self, aluno):
        self.chamadas.append(aluno.nome)
        intensidade = 20 + len(self.chamadas)
        mm_para_px = lambda mm: round(mm * LAYOUT["DPI"] / 25.4)
        return Image.new(
            "RGB",
            (mm_para_px(LAYOUT["LARGURA"]), mm_para_px(LAYOUT["ALTURA"])),
            (intensidade, 0, 0),
        )


def test_monta_a4_paisagem_com_dez_crachas_por_pagina_em_ordem_alfabetica():
    montador = MontadorFalso()
    exportador = ExportadorCracha(montador)
    alunos = [
        Aluno(f"ALUNO {numero:02d}", "101", "CURSO", f"COD{numero:02d}")
        for numero in range(11, 0, -1)
    ]

    folhas = exportador.montar_folhas_pdf_turma(alunos, "101")
    try:
        assert len(folhas) == 2
        assert all(folha.size == (3508, 2480) for folha in folhas)
        assert montador.chamadas == sorted(a.nome for a in alunos)

        mm_para_px = lambda mm: round(mm * LAYOUT["DPI"] / 25.4)
        cracha_w, cracha_h = mm_para_px(LAYOUT["LARGURA"]), mm_para_px(LAYOUT["ALTURA"])
        espaco = mm_para_px(3)
        margem_x = (3508 - (5 * cracha_w + 4 * espaco)) // 2
        margem_y = (2480 - (2 * cracha_h + espaco)) // 2
        assert folhas[0].getpixel((margem_x, margem_y)) == (21, 0, 0)
        assert folhas[1].getpixel((margem_x, margem_y)) == (31, 0, 0)
    finally:
        for folha in folhas:
            folha.close()


def test_exporta_pdf_a4_valido(tmp_path):
    exportador = ExportadorCracha(MontadorFalso())
    aluno = Aluno("ALUNO TESTE", "101", "CURSO", "10101")
    caminho = tmp_path / "Turma_101_Crachas.pdf"

    resultado = exportador.exportar_pdf_turma([aluno], "101", caminho)

    assert resultado["total_crachas"] == 1
    assert resultado["total_paginas"] == 1
    assert caminho.read_bytes().startswith(b"%PDF")
    assert caminho.stat().st_size > 1000


def test_api_exporta_somente_turma_escolhida_e_disponibiliza_download(tmp_path, monkeypatch):
    recebidos = {}

    def exportar_falso(self, alunos, turma, caminho, marcas_corte=True):
        recebidos["nomes"] = [aluno.nome for aluno in alunos]
        recebidos["turma"] = turma
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(b"%PDF-1.4 teste")
        return {"caminho": caminho, "total_crachas": len(alunos), "total_paginas": 1}

    monkeypatch.setitem(api.DIRS, "MONTADOS", tmp_path)
    monkeypatch.setattr(api.ExportadorCracha, "exportar_pdf_turma", exportar_falso)
    monkeypatch.setitem(api.app_state, "alunos", [
        Aluno("ZELIA", "101", "CURSO", "10102"),
        Aluno("ANA", "101", "CURSO", "10101"),
        Aluno("OUTRA TURMA", "202", "CURSO", "20201"),
    ])

    cliente = api.app.test_client()
    resposta = cliente.post("/api/exportar-pdf-turma", json={"turma": "101"})

    assert resposta.status_code == 200
    dados = resposta.get_json()
    assert dados["total_crachas"] == 2
    assert dados["total_paginas"] == 1
    assert recebidos == {"nomes": ["ZELIA", "ANA"], "turma": "101"}
    assert Path(dados["arquivo"]).exists()
    download = cliente.get(dados["download_url"])
    assert download.status_code == 200
    assert download.data.startswith(b"%PDF")


def test_api_pdf_exige_turma_especifica(monkeypatch):
    monkeypatch.setitem(api.app_state, "alunos", [
        Aluno("ALUNO", "101", "CURSO", "10101"),
    ])
    resposta = api.app.test_client().post("/api/exportar-pdf-turma", json={"turma": ""})
    assert resposta.status_code == 400
    assert "Selecione uma turma" in resposta.get_json()["erro"]


def test_menu_exibe_exportacao_pdf_por_turma():
    html = (api.BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (api.BASE_DIR / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="btnPdfTurma"' in html
    assert "porId('btnPdfTurma').addEventListener('click', exportarPdfTurma)" in javascript
    assert "onclick=" not in html
    assert "/api/exportar-pdf-turma" in javascript
    assert "PDF individual" in html


def test_pdf_coletivo_nao_entra_no_contador_de_crachas(tmp_path, monkeypatch):
    monkeypatch.setitem(api.DIRS, "MONTADOS", tmp_path)
    (tmp_path / "101").mkdir()
    (tmp_path / "101" / "ALUNO.png").write_bytes(b"png")
    (tmp_path / "101" / "Turma_101_Crachas.pdf").write_bytes(b"pdf")

    encontrados = Diagnosticador().listar_crachas_montados()

    assert [item["arquivo"] for item in encontrados] == ["ALUNO.png"]
