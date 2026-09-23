import io

from PIL import Image

from cracha_extractor import api, foto_handler
from cracha_extractor.foto_handler import FotoHandler
from cracha_extractor.models import Aluno
from cracha_extractor.montador import MontadorCracha
from cracha_extractor.config import TEMPLATE_IEMA


def _png_bytes(cor="red"):
    buffer = io.BytesIO()
    Image.new("RGB", (20, 30), cor).save(buffer, "PNG")
    return buffer.getvalue()


def test_busca_automatica_na_pasta_fotos_ignora_acentos(tmp_path, monkeypatch):
    monkeypatch.setitem(foto_handler.DIRS, "FOTOS_ALUNOS", tmp_path)
    (tmp_path / "João da Silva.png").write_bytes(_png_bytes())

    foto = FotoHandler().buscar_foto_aluno("JOAO DA SILVA")

    assert foto is not None
    assert foto.size == (20, 30)


def test_busca_foto_prioriza_codigo_do_aluno(tmp_path, monkeypatch):
    monkeypatch.setitem(foto_handler.DIRS, "FOTOS_ALUNOS", tmp_path)
    (tmp_path / "Maria da Silva.png").write_bytes(_png_bytes("blue"))
    (tmp_path / "2024001_maria.png").write_bytes(_png_bytes("red"))

    foto = FotoHandler().buscar_foto_aluno("MARIA DA SILVA", codigo="2024001.0")

    assert foto is not None
    assert foto.getpixel((0, 0)) == (255, 0, 0)


def test_busca_foto_em_subpasta_da_turma_com_nome_abreviado(tmp_path, monkeypatch):
    monkeypatch.setitem(foto_handler.DIRS, "FOTOS_ALUNOS", tmp_path)
    pasta_turma = tmp_path / "101"
    pasta_turma.mkdir()
    (pasta_turma / "Andressa Aguiar.jpg").write_bytes(_png_bytes("green"))

    foto = FotoHandler().buscar_foto_aluno(
        "ANDRESSA AGUIAR ARAUJO",
        codigo="2026108617111",
        turma="101",
    )

    assert foto is not None
    assert foto.getpixel((0, 0)) == (0, 128, 0)


def test_busca_nome_abreviado_com_inicial_ou_caractere_corrompido(tmp_path, monkeypatch):
    monkeypatch.setitem(foto_handler.DIRS, "FOTOS_ALUNOS", tmp_path)
    pasta_turma = tmp_path / "101"
    pasta_turma.mkdir()
    (pasta_turma / "Maria A. Vitoria.jpg").write_bytes(_png_bytes("blue"))
    (pasta_turma / "\u00c1ghata Stefanny.jpg").write_bytes(_png_bytes("red"))

    maria = FotoHandler().buscar_foto_aluno(
        "MARIA APARECIDA VITÓRIA LEITE MARTINS", turma="101"
    )
    aghata = FotoHandler().buscar_foto_aluno(
        "ÁGATHA STEFANNY VITALINO MARINHO", turma="101"
    )

    assert maria is not None and maria.getpixel((0, 0)) == (0, 0, 255)
    assert aghata is not None and aghata.getpixel((0, 0)) == (255, 0, 0)


def test_nome_abreviado_prefere_correspondencia_mais_exata(tmp_path, monkeypatch):
    monkeypatch.setitem(foto_handler.DIRS, "FOTOS_ALUNOS", tmp_path)
    pasta_turma = tmp_path / "101"
    pasta_turma.mkdir()
    (pasta_turma / "Maria A. Vitoria.jpg").write_bytes(_png_bytes("blue"))
    (pasta_turma / "Maria Victoria.jpg").write_bytes(_png_bytes("green"))

    foto = FotoHandler().buscar_foto_aluno(
        "MARIA VICTORIA VALADARES PESSOA", turma="101"
    )

    assert foto is not None
    assert foto.getpixel((0, 0)) == (0, 128, 0)


def test_busca_nao_aceita_apenas_primeiro_nome(tmp_path, monkeypatch):
    monkeypatch.setitem(foto_handler.DIRS, "FOTOS_ALUNOS", tmp_path)
    pasta_turma = tmp_path / "101"
    pasta_turma.mkdir()
    (pasta_turma / "Maria.jpg").write_bytes(_png_bytes())

    foto = FotoHandler().buscar_foto_aluno("MARIA EDUARDA LIRA", turma="101")

    assert foto is None


def test_caminho_relativo_da_planilha_parte_da_raiz(tmp_path, monkeypatch):
    monkeypatch.setattr(foto_handler, "BASE_DIR", tmp_path)
    pasta = tmp_path / "fotos_alunos"
    pasta.mkdir()
    (pasta / "aluno.png").write_bytes(_png_bytes("blue"))

    foto = FotoHandler().carregar_foto("fotos_alunos/aluno.png")

    assert foto is not None
    assert foto.getpixel((0, 0)) == (0, 0, 255)


def test_caminho_invalido_da_planilha_tenta_busca_automatica(tmp_path, monkeypatch):
    monkeypatch.setitem(foto_handler.DIRS, "FOTOS_ALUNOS", tmp_path)
    (tmp_path / "Aluno Teste.png").write_bytes(_png_bytes())
    aluno = Aluno(
        "ALUNO TESTE", "101", "INFORMÁTICA", matricula="10101",
        foto_caminho="foto_inexistente.png"
    )

    cracha = MontadorCracha().montar(aluno)

    assert cracha.crop(TEMPLATE_IEMA["POS_FOTO"]).getcolors() == [(338 * 338, (255, 0, 0))]


def test_upload_de_fotos_valida_e_salva_imagens(tmp_path, monkeypatch):
    monkeypatch.setitem(api.DIRS, "FOTOS_ALUNOS", tmp_path)
    resposta = api.app.test_client().post(
        "/api/fotos",
        data={
            "fotos": [
                (io.BytesIO(_png_bytes()), "Maria da Silva.png"),
                (io.BytesIO(b"nao e imagem"), "invalida.jpg"),
            ]
        },
        content_type="multipart/form-data",
    )

    assert resposta.status_code == 200
    dados = resposta.get_json()
    assert dados["total_salvas"] == 1
    assert len(dados["erros"]) == 1
    assert (tmp_path / "Maria_da_Silva.png").is_file()


def test_interface_exibe_importacao_multipla_de_fotos():
    html = (api.BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (api.BASE_DIR / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="fotosInput"' in html
    assert "multiple" in html
    assert "handleFotosSelect" in javascript
    assert "2024001.jpg" in html
