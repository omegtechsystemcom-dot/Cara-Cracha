"""
Testes automatizados do sistema de crachás.
"""
import unittest
from pathlib import Path
import tempfile
import shutil
import json

# Configurar ambiente de teste
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))


class TestModels(unittest.TestCase):
    """Testes para os modelos de dados."""

    def test_aluno_criacao(self):
        from cracha_extractor.models import Aluno
        aluno = Aluno(nome="João", turma="102", curso="INFORMÁTICA")
        self.assertEqual(aluno.nome, "JOÃO")
        self.assertEqual(aluno.turma, "102")

    def test_aluno_sem_turma(self):
        from cracha_extractor.models import Aluno
        aluno = Aluno(nome="Maria", turma="", curso="")
        self.assertEqual(aluno.turma, "")

    def test_turma_adicionar_aluno(self):
        from cracha_extractor.models import Turma, Aluno
        turma = Turma(nome="102", curso="INFORMÁTICA")
        aluno = Aluno(nome="Ana", turma="102", curso="INFORMÁTICA")
        turma.adicionar_aluno(aluno)
        self.assertEqual(turma.quantidade_alunos, 1)


class TestPlanilhaReader(unittest.TestCase):
    """Testes para o leitor de planilhas."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_criar_e_ler_excel(self):
        """Testa criar um arquivo Excel e ler de volta."""
        import pandas as pd
        from cracha_extractor.planilha_reader import PlanilhaReader

        # Criar planilha de teste
        dados = {
            "Nome": ["ALUNO TESTE"],
            "Turma": ["102"],
            "Curso": ["INFORMÁTICA"],
            "Matrícula": ["2024001"],
        }
        df = pd.DataFrame(dados)
        caminho = self.temp_dir / "teste.xlsx"
        df.to_excel(caminho, index=False)

        # Ler a planilha
        reader = PlanilhaReader(caminho)
        alunos = reader.ler()
        self.assertEqual(len(alunos), 1)
        self.assertEqual(alunos[0].nome, "ALUNO TESTE")

    def test_arquivo_inexistente(self):
        from cracha_extractor.planilha_reader import PlanilhaReader
        with self.assertRaises(FileNotFoundError):
            PlanilhaReader("arquivo_inexistente.xlsx")

    def test_extensao_invalida(self):
        from cracha_extractor.planilha_reader import PlanilhaReader
        with self.assertRaises(ValueError):
            PlanilhaReader("arquivo.txt")

    def test_arquivo_inexistente_levanta_erro(self):
        from cracha_extractor.planilha_reader import PlanilhaReader
        with self.assertRaises(FileNotFoundError):
            PlanilhaReader("arquivo_inexistente.xlsx")


class TestQRGenerator(unittest.TestCase):
    """Testes para o gerador de QR Code."""

    def test_gerar_qr(self):
        from cracha_extractor.qr_generator import QRCodeGenerator
        gerador = QRCodeGenerator()
        img = gerador.gerar("Teste QR Code")
        self.assertIsNotNone(img)
        # QR Code deve ser quadrado
        self.assertEqual(img.width, img.height)

    def test_salvar_qr(self):
        from cracha_extractor.qr_generator import QRCodeGenerator
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            gerador = QRCodeGenerator()
            caminho = gerador.salvar("Dados do QR", f.name)
            self.assertTrue(Path(caminho).exists())
            self.assertGreater(Path(caminho).stat().st_size, 100)


class TestFotoHandler(unittest.TestCase):
    """Testes para o manipulador de fotos."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_criar_imagem_teste(self):
        """Cria uma imagem de teste e verifica o processamento."""
        from PIL import Image
        from cracha_extractor.foto_handler import FotoHandler

        # Criar imagem de teste
        img = Image.new("RGB", (200, 300), color="red")
        caminho = self.temp_dir / "foto_teste.jpg"
        img.save(caminho)

        # Processar
        handler = FotoHandler()
        img_carregada = handler.carregar_foto(caminho)
        self.assertIsNotNone(img_carregada)

        img_processada = handler.processar_foto(img_carregada)
        self.assertIsNotNone(img_processada)


class TestExportador(unittest.TestCase):
    """Testes para o exportador."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_exportar_png(self):
        from cracha_extractor.models import Aluno, ConfiguracaoCracha
        from cracha_extractor.montador import MontadorCracha
        from cracha_extractor.exportador import ExportadorCracha

        aluno = Aluno(nome="TESTE", turma="102", curso="INFORMÁTICA")
        config = ConfiguracaoCracha(turma_nome="102")
        montador = MontadorCracha(config)
        exportador = ExportadorCracha(montador)

        caminho = self.temp_dir / "teste.png"
        resultado = exportador.exportar_png(aluno, caminho)
        self.assertTrue(resultado.exists())
        self.assertGreater(resultado.stat().st_size, 100)

    def test_exportar_html(self):
        from cracha_extractor.models import Aluno, ConfiguracaoCracha
        from cracha_extractor.montador import MontadorCracha
        from cracha_extractor.exportador import ExportadorCracha

        aluno = Aluno(nome="TESTE", turma="102", curso="INFORMÁTICA")
        config = ConfiguracaoCracha(turma_nome="102")
        montador = MontadorCracha(config)
        exportador = ExportadorCracha(montador)

        caminho = self.temp_dir / "teste.html"
        resultado = exportador.exportar_html(aluno, caminho)
        self.assertTrue(resultado.exists())
        conteudo = resultado.read_text(encoding="utf-8")
        self.assertIn("TESTE", conteudo)
        self.assertIn("102", conteudo)


class TestUtils(unittest.TestCase):
    """Testes para utilitários."""

    def test_sanitizar_nome(self):
        from cracha_extractor.exportador import ExportadorCracha
        nome = ExportadorCracha._sanitizar_nome("Maria da Silva")
        self.assertNotIn(" ", nome)
        self.assertTrue(len(nome) > 0)

    def test_diagnosticador(self):
        from cracha_extractor.utils import Diagnosticador
        diag = Diagnosticador()
        resultado = diag.verificar_estrutura()
        self.assertIn("TURMAS", resultado)
        self.assertIn("MONTADOS", resultado)


if __name__ == "__main__":
    unittest.main(verbosity=2)
