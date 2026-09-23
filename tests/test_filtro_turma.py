from pathlib import Path

from cracha_extractor import api
from cracha_extractor.models import Aluno


def _exportar_png_falso(self, aluno, caminho):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"png")
    return caminho


def test_api_gera_apenas_turma_filtrada(tmp_path, monkeypatch):
    monkeypatch.setitem(api.DIRS, "MONTADOS", tmp_path)
    monkeypatch.setattr(api.ExportadorCracha, "exportar_png", _exportar_png_falso)
    monkeypatch.setitem(api.app_state, "alunos", [
        Aluno("ALUNO 101", "101", "INFORMÁTICA", "10101"),
        Aluno("OUTRO 101", "101", "INFORMÁTICA", "10102"),
        Aluno("ALUNO 202", "202", "ELETROTÉCNICA", "20201"),
    ])

    resposta = api.app.test_client().post("/api/gerar", json={
        "formato": "png",
        "turma": "101",
        "mostrar_foto": False,
        "mostrar_qr": False,
    })

    assert resposta.status_code == 200
    dados = resposta.get_json()
    assert dados["total_gerados"] == 2
    assert {item["turma"] for item in dados["resultados"]} == {"101"}


def test_api_combina_turma_e_alunos_marcados(tmp_path, monkeypatch):
    monkeypatch.setitem(api.DIRS, "MONTADOS", tmp_path)
    monkeypatch.setattr(api.ExportadorCracha, "exportar_png", _exportar_png_falso)
    monkeypatch.setitem(api.app_state, "alunos", [
        Aluno("ESCOLHIDO", "101", "INFORMÁTICA", "10101"),
        Aluno("OUTRA TURMA", "202", "INFORMÁTICA", "20201"),
    ])

    cliente = api.app.test_client()
    resposta = cliente.post("/api/gerar", json={
        "formato": "png",
        "turma": "101",
        "alunos": ["ESCOLHIDO", "OUTRA TURMA"],
    })
    assert resposta.status_code == 200
    assert [item["nome"] for item in resposta.get_json()["resultados"]] == ["ESCOLHIDO"]

    sem_resultado = cliente.post("/api/gerar", json={
        "formato": "png",
        "turma": "999",
    })
    assert sem_resultado.status_code == 400
    assert "Nenhum aluno" in sem_resultado.get_json()["erro"]


def test_menu_gerar_exibe_filtro_de_turma():
    html = (api.BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (api.BASE_DIR / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="gerarTurma"' in html
    assert "filtrarGeracaoPorTurma()" in html
    assert "turma," in javascript


def test_api_bloqueia_qr_com_codigo_ausente_ou_duplicado(tmp_path, monkeypatch):
    monkeypatch.setitem(api.DIRS, "MONTADOS", tmp_path)
    monkeypatch.setitem(api.app_state, "alunos", [
        Aluno("SEM CODIGO", "101", "INFORMÁTICA", ""),
        Aluno("DUPLICADO A", "101", "INFORMÁTICA", "ABC123"),
        Aluno("DUPLICADO B", "101", "INFORMÁTICA", "abc123"),
    ])

    resposta = api.app.test_client().post("/api/gerar", json={
        "formato": "png",
        "turma": "101",
        "mostrar_qr": True,
    })

    assert resposta.status_code == 400
    dados = resposta.get_json()
    assert dados["sem_codigo"] == ["SEM CODIGO"]
    assert dados["codigos_duplicados"]["ABC123"] == ["DUPLICADO A", "DUPLICADO B"]
