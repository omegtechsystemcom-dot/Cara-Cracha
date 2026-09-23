import base64
import io
import re
from PIL import Image, ImageChops, ImageDraw
from cracha_extractor.config import BASE_DIR, TEMPLATE_IEMA
from cracha_extractor.models import Aluno, ConfiguracaoCracha
from cracha_extractor.montador import MontadorCracha


def test_preserva_arte_fora_dos_campos():
    original = Image.open(BASE_DIR / TEMPLATE_IEMA['ARQUIVO']).convert('RGB')
    montador = MontadorCracha(ConfiguracaoCracha(turma_nome='101', mostrar_foto=False))
    imagem = montador.montar(Aluno(
        'MARIA EDUARDA DOS SANTOS OLIVEIRA', '101', 'INFORMÁTICA', '10101'
    ))
    diferenca = ImageChops.difference(original, imagem)
    draw = ImageDraw.Draw(diferenca)
    for campo in ('POS_FOTO', 'POS_QR', 'POS_NOME', 'POS_CURSO', 'POS_TURMA'):
        x1, y1, x2, y2 = TEMPLATE_IEMA[campo]
        draw.rectangle((x1, y1, x2-1, y2-1), fill=0)
    assert diferenca.getbbox() is None
    assert imagem.size == original.size
    cores_qr = imagem.crop(TEMPLATE_IEMA['POS_QR']).getcolors(1000)
    assert {cor for _, cor in cores_qr} == {(0, 0, 0), (255, 255, 255)}


def test_html_incorpora_mesma_imagem_e_escapa_nome():
    aluno = Aluno('ANA <SILVA>', '102', 'INFORMÁTICA', '10201')
    montador = MontadorCracha(ConfiguracaoCracha(turma_nome='102', mostrar_foto=False))
    html = montador.montar_html(aluno)
    assert 'ANA &lt;SILVA&gt;' in html
    dados = re.search(r'data:image/png;base64,([^\"]+)', html).group(1)
    imagem = Image.open(io.BytesIO(base64.b64decode(dados)))
    assert ImageChops.difference(imagem, montador.montar(aluno)).getbbox() is None


def test_foto_preenche_quadro_e_opcoes_ocultam_campos(tmp_path):
    caminho = tmp_path / 'foto.png'
    Image.new('RGB', (100, 200), 'red').save(caminho)
    aluno = Aluno('TESTE', '103', 'INFORMÁTICA', '10301', foto_caminho=str(caminho))
    imagem = MontadorCracha().montar(aluno)
    assert imagem.crop(TEMPLATE_IEMA['POS_FOTO']).getcolors() == [(338*338, (255, 0, 0))]
    config = ConfiguracaoCracha(turma_nome='103', mostrar_foto=False, mostrar_qr_code=False)
    imagem = MontadorCracha(config).montar(aluno)
    for campo in ('POS_FOTO', 'POS_QR'):
        assert len(imagem.crop(TEMPLATE_IEMA[campo]).getcolors()) == 1
