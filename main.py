#!/usr/bin/env python3
"""
Sistema de Extração e Montagem de Crachás
==========================================
Importa dados de planilhas, monta crachás com foto e QR Code,
e exporta em PDF, PNG, JPG ou HTML.

Uso:
    python main.py                  # Inicia a interface web (padrão)
    python main.py --gui            # Inicia a interface gráfica Tkinter
    python main.py --cli            # Modo terminal (linha de comando)
    python main.py --help           # Ajuda detalhada
"""
import sys
import argparse
import subprocess
import os
from pathlib import Path


def _garantir_venv():
    """
    Verifica se está rodando no .venv. Se não estiver, executa
    automaticamente com o Python do ambiente virtual e encerra.
    """
    venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        return  # Sem .venv, segue com o Python atual

    # Verifica se já estamos no .venv
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        return  # Já está no venv

    # Verifica se flask_cors está disponível
    try:
        import flask_cors  # noqa: F401
        return  # Tudo ok
    except ImportError:
        pass

    # Reexecuta com o Python do .venv usando subprocess
    print("🔄 Iniciando com o ambiente virtual (.venv)...")
    cmd = [str(venv_python), __file__] + sys.argv[1:]
    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"❌ Erro ao executar com .venv: {e}")
        print("Execute manualmente: .venv\\Scripts\\python main.py")
        sys.exit(1)
from pathlib import Path

# Garantir que o diretório raiz está no path
sys.path.insert(0, str(Path(__file__).parent.resolve()))


def main():
    # Garantir que está usando o .venv
    _garantir_venv()

    parser = argparse.ArgumentParser(
        description="Sistema de Montagem de Crachás",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python main.py                        # Iniciar interface web
  python main.py --gui                  # Iniciar interface gráfica Tkinter
  python main.py --cli --planilha dados.xlsx --formato pdf
  python main.py --diagnostico          # Verificar sistema
  python main.py --exemplo              # Criar planilha exemplo
  python main.py --web --port=8080      # Web em porta específica
        """,
    )

    parser.add_argument(
        "--cli", action="store_true",
        help="Executar em modo terminal (sem interface gráfica)",
    )
    parser.add_argument(
        "--gui", action="store_true",
        help="Executar com interface gráfica Tkinter (em vez da web)",
    )
    parser.add_argument(
        "--web", action="store_true",
        help="Forçar modo web (padrão)",
    )
    parser.add_argument(
        "--port", type=int, default=5000,
        help="Porta do servidor web (padrão: 5000)",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="Host do servidor web (padrão: 127.0.0.1)",
    )
    parser.add_argument(
        "--planilha", "-p", type=str,
        help="Caminho da planilha com dados dos alunos",
    )
    parser.add_argument(
        "--formato", "-f", type=str, choices=["png", "jpg", "pdf", "html"],
        default="png",
        help="Formato de saída dos crachás (padrão: png)",
    )
    parser.add_argument(
        "--saida", "-s", type=str,
        help="Pasta de saída para os crachás gerados",
    )
    parser.add_argument(
        "--diagnostico", action="store_true",
        help="Executar diagnóstico do sistema",
    )
    parser.add_argument(
        "--exemplo", action="store_true",
        help="Criar arquivo Excel de exemplo",
    )
    parser.add_argument(
        "--backup", action="store_true",
        help="Criar backup do sistema",
    )

    args = parser.parse_args()

    # Modo diagnóstico
    if args.diagnostico:
        from cracha_extractor.utils import Diagnosticador
        diag = Diagnosticador()
        estrutura = diag.verificar_estrutura()
        print("\n=== DIAGNÓSTICO DO SISTEMA ===\n")
        print("Estrutura de Diretórios:")
        for nome, info in estrutura.items():
            status = "✅" if info["existe"] else "❌"
            print(f"  {status} {nome}: {info['caminho']}")

        turmas = diag.listar_turmas_disponiveis()
        print(f"\nTurmas encontradas: {len(turmas)}")
        for t in turmas:
            print(f"  - {t}")

        crachas = diag.listar_crachas_montados()
        print(f"\nCrachás montados: {len(crachas)}")
        return

    # Modo backup
    if args.backup:
        from cracha_extractor.utils import criar_backup
        caminho = criar_backup()
        print(f"✅ Backup criado em: {caminho}")
        return

    # Modo exemplo
    if args.exemplo:
        from cracha_extractor.utils import criar_arquivo_exemplo
        caminho = Path("modelo_alunos.xlsx")
        criar_arquivo_exemplo(caminho)
        print(f"✅ Arquivo exemplo criado: {caminho.resolve()}")
        return

    # Modo CLI
    if args.cli:
        from cracha_extractor.planilha_reader import PlanilhaReader
        from cracha_extractor.montador import MontadorCracha
        from cracha_extractor.exportador import ExportadorCracha
        from cracha_extractor.models import ConfiguracaoCracha
        from cracha_extractor.config import DIRS

        if not args.planilha:
            print("❌ Use --planilha para especificar o arquivo de dados.")
            sys.exit(1)

        planilha = Path(args.planilha)
        if not planilha.exists():
            print(f"❌ Planilha não encontrada: {planilha}")
            sys.exit(1)

        pasta_saida = Path(args.saida) if args.saida else DIRS["MONTADOS"]

        print(f"📂 Lendo planilha: {planilha}")
        reader = PlanilhaReader(planilha)
        alunos = reader.ler()
        print(f"✅ {len(alunos)} alunos carregados")

        config = ConfiguracaoCracha(turma_nome="")
        montador = MontadorCracha(config)
        exportador = ExportadorCracha(montador)

        print(f"🚀 Gerando crachás em: {pasta_saida}")
        resultados = exportador.exportar_lote(alunos, pasta_saida, [args.formato])
        print(f"✅ {len(resultados[args.formato])} crachás gerados em {args.formato.upper()}")
        return

    # Modo GUI Tkinter (se solicitado explicitamente)
    if args.gui:
        from cracha_extractor.interface import AppCracha
        app = AppCracha()
        app.iniciar()
        return

    # Modo web (padrão)
    import webbrowser
    from cracha_extractor.api import iniciar_servidor

    url = f"http://{args.host}:{args.port}"
    print(f"""
╔══════════════════════════════════════════════╗
║     SISTEMA DE MONTAGEM DE CRACHÁS          ║
║     Interface Web                            ║
║                                              ║
║  🌐 Acesse: {url}              ║
║                                              ║
║  Pressione Ctrl+C para parar o servidor      ║
╚══════════════════════════════════════════════╝
    """)

    # Abrir navegador automaticamente
    webbrowser.open(url)

    # Iniciar servidor
    iniciar_servidor(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
