import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from cracha_extractor import api
from cracha_extractor.models import Aluno


@pytest.fixture(autouse=True)
def preservar_estado():
    anterior = {
        "alunos": api.app_state["alunos"],
        "turmas": api.app_state["turmas"],
        "planilha_carregada": api.app_state["planilha_carregada"],
        "planilha_confirmada_em": api.app_state["planilha_confirmada_em"],
        "importacoes_pendentes": api.app_state["importacoes_pendentes"],
    }
    api.app_state["importacoes_pendentes"] = {}
    yield
    api.app_state.update(anterior)


def _csv(nome="NOVO ALUNO", codigo="000123"):
    texto = f"Nome,Turma,Curso,Codigo do aluno\n{nome},101,INFORMATICA,{codigo}\n"
    return io.BytesIO(texto.encode("utf-8"))


def test_preview_e_cancelamento_nao_trocam_base_ativa(tmp_path, monkeypatch):
    monkeypatch.setitem(api.DIRS, "IMPORTACOES_PENDENTES", tmp_path / "pendentes")
    ativo = Aluno("ALUNO ATIVO", "201", "CURSO", "ATIVO-1")
    api.app_state["alunos"] = [ativo]
    api.app_state["turmas"] = {"201": object()}

    cliente = api.app.test_client()
    resposta = cliente.post(
        "/api/planilha/colunas",
        data={"arquivo": (_csv(), "nova.csv")},
        content_type="multipart/form-data",
    )
    assert resposta.status_code == 200
    upload_id = resposta.get_json()["upload_id"]
    assert api.app_state["alunos"] == [ativo]

    cancelamento = cliente.post("/api/planilha/cancelar", json={"upload_id": upload_id})
    assert cancelamento.status_code == 200
    assert cancelamento.get_json()["cancelada"] is True
    assert api.app_state["alunos"] == [ativo]


def test_upload_invalido_nao_deixa_arquivo_pendente(tmp_path, monkeypatch):
    pendentes = tmp_path / "pendentes"
    monkeypatch.setitem(api.DIRS, "IMPORTACOES_PENDENTES", pendentes)
    resposta = api.app.test_client().post(
        "/api/planilha/colunas",
        data={"arquivo": (io.BytesIO(b"coluna\nvalor\n"), "invalida.csv")},
        content_type="multipart/form-data",
    )
    assert resposta.status_code == 400
    assert not list(pendentes.glob("*"))

def test_confirmacao_ativa_planilha_com_codigo_oficial(tmp_path, monkeypatch):
    monkeypatch.setitem(api.DIRS, "IMPORTACOES_PENDENTES", tmp_path / "pendentes")
    monkeypatch.setitem(api.DIRS, "PLANILHAS", tmp_path / "planilhas")
    monkeypatch.setitem(api.DIRS, "DATA", tmp_path / "data")
    cliente = api.app.test_client()
    preview = cliente.post(
        "/api/planilha/colunas",
        data={"arquivo": (_csv(codigo="000123"), "nova.csv")},
        content_type="multipart/form-data",
    ).get_json()

    resposta = cliente.post("/api/planilha/confirmar", json={"upload_id": preview["upload_id"]})
    assert resposta.status_code == 200
    aluno = resposta.get_json()["alunos"][0]
    assert aluno["codigo"] == "000123"
    assert api.app_state["alunos"][0].matricula == "000123"


def test_geracao_usa_codigo_no_arquivo_qr_foto_e_manifesto(tmp_path, monkeypatch):
    montados = tmp_path / "montados"
    fotos = tmp_path / "fotos" / "101"
    fotos.mkdir(parents=True)
    foto = fotos / "A001.png"
    foto.write_bytes(b"foto-do-aluno")
    monkeypatch.setitem(api.DIRS, "MONTADOS", montados)
    aluno = Aluno("NOME REPETIVEL", "101", "CURSO", "A001")
    api.app_state["alunos"] = [aluno]
    api.app_state["turmas"] = {"101": object()}

    def exportar(self, aluno_recebido, caminho):
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(b"png")
        self.montador.foto_handler.ultima_foto_caminho = foto
        return caminho

    monkeypatch.setattr(api.ExportadorCracha, "exportar_png", exportar)
    resposta = api.app.test_client().post("/api/gerar", json={
        "formato": "png",
        "turma": "101",
        "codigos": ["A001"],
        "mostrar_foto": True,
        "mostrar_qr": True,
    })
    assert resposta.status_code == 200
    item = resposta.get_json()["resultados"][0]
    assert item["arquivo"].endswith("101/A001.png") or item["arquivo"].endswith("101\\A001.png")
    assert item["qr_identificador"] == "A001"

    manifesto = json.loads((montados / "101" / "manifesto.json").read_text(encoding="utf-8"))
    registro = manifesto["crachas"][0]
    assert registro["codigo"] == "A001"
    assert registro["nome"] == "NOME REPETIVEL"
    assert registro["foto_sha256"] == hashlib.sha256(foto.read_bytes()).hexdigest()
    assert registro["qr"] == item["qr_identificador"]


def test_reconciliacao_considera_apenas_saida_oficial_por_codigo(tmp_path, monkeypatch):
    monkeypatch.setitem(api.DIRS, "MONTADOS", tmp_path)
    pasta = tmp_path / "101"
    pasta.mkdir()
    (pasta / "NOME_DO_ALUNO.png").write_bytes(b"legado")
    api.app_state["alunos"] = [Aluno("NOME DO ALUNO", "101", "CURSO", "A001")]
    api.app_state["turmas"] = {"101": object()}

    dados = api.app.test_client().get("/api/reconciliacao?turma=101").get_json()
    assert dados["total_faltantes"] == 1
    assert dados["total_obsoletos"] == 1
    assert dados["valido"] is False


def test_exportar_pngs_turmas_gera_zip_com_pngs_individuais(tmp_path, monkeypatch):
    monkeypatch.setitem(api.DIRS, "MONTADOS", tmp_path / "montados")
    monkeypatch.setitem(api.DIRS, "DIAG_SAIDA", tmp_path / "diag")
    api.app_state["alunos"] = [
        Aluno("ALUNO UM", "101", "CURSO", "A001"),
        Aluno("ALUNO DOIS", "102", "CURSO", "B002"),
    ]
    api.app_state["turmas"] = {"101": object(), "102": object()}

    def exportar(self, aluno_recebido, caminho):
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(f"png-{aluno_recebido.matricula}".encode("utf-8"))
        return caminho

    monkeypatch.setattr(api.ExportadorCracha, "exportar_png", exportar)
    resposta = api.app.test_client().post("/api/exportar-pngs-turmas", json={
        "mostrar_foto": True,
        "mostrar_qr": True,
    })

    assert resposta.status_code == 200
    dados = resposta.get_json()
    assert dados["total_gerados"] == 2
    caminho_zip = Path(dados["arquivo"])
    with zipfile.ZipFile(caminho_zip) as arquivo:
        assert sorted(arquivo.namelist()) == ["101/A001.png", "102/B002.png"]
        assert arquivo.read("101/A001.png") == b"png-A001"
        assert arquivo.read("102/B002.png") == b"png-B002"


def test_csp_e_frontend_sem_handlers_inline():
    resposta = api.app.test_client().get("/")
    html = resposta.get_data(as_text=True)
    csp = resposta.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "onclick=" not in html
    assert "onchange=" not in html
    assert "oninput=" not in html
    assert "ondrop=" not in html
    javascript = (api.BASE_DIR / "static" / "app.js").read_text(encoding="utf-8")
    assert ".innerHTML" not in javascript
    assert "textContent" in javascript


def test_backup_e_extraido_em_area_isolada(tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    diagnostico = tmp_path / "diagnostico"
    backups.mkdir()
    monkeypatch.setitem(api.DIRS, "BACKUPS", backups)
    monkeypatch.setitem(api.DIRS, "DIAG_SAIDA", diagnostico)
    conteudo = b"dados"
    manifesto = {
        "versao": 1,
        "inclui_gerados": False,
        "arquivos": [{
            "caminho": "data/exemplo.txt",
            "tamanho": len(conteudo),
            "sha256": hashlib.sha256(conteudo).hexdigest(),
        }],
    }
    caminho = backups / "backup_cracha_teste.zip"
    with zipfile.ZipFile(caminho, "w") as arquivo:
        arquivo.writestr("data/exemplo.txt", conteudo)
        arquivo.writestr("MANIFESTO_BACKUP.json", json.dumps(manifesto))

    resposta = api.app.test_client().post(
        "/api/backup/extrair", json={"arquivo": caminho.name}
    )
    assert resposta.status_code == 200
    destino = Path(resposta.get_json()["pasta"])
    assert destino.is_relative_to(diagnostico)
    assert (destino / "data" / "exemplo.txt").read_bytes() == conteudo
