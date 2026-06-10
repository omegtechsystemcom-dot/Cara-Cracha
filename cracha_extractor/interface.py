"""
Interface Gráfica do Sistema de Crachás.
Construída com tkinter para facilitar o uso.
"""
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from threading import Thread
from datetime import datetime
import webbrowser

from .config import DIRS, FORMATOS_SAIDA
from .planilha_reader import PlanilhaReader
from .montador import MontadorCracha
from .exportador import ExportadorCracha
from .models import ConfiguracaoCracha
from .utils import (
    configurar_logger,
    Diagnosticador,
    criar_backup,
    criar_arquivo_exemplo,
)

logger = logging.getLogger(__name__)


class AppCracha:
    """Aplicação gráfica principal."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sistema de Montagem de Crachás")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # Configurar logger
        self.logger = configurar_logger()

        # Variáveis de estado
        self.planilha_path = tk.StringVar()
        self.pasta_saida = tk.StringVar(value=str(DIRS["MONTADOS"]))
        self.formato_saida = tk.StringVar(value="png")
        self.status_texto = tk.StringVar(value="Pronto para começar")

        # Configurações
        self.cor_destaque = tk.StringVar(value="#1a5276")
        self.mostrar_foto = tk.BooleanVar(value=True)
        self.mostrar_qr = tk.BooleanVar(value=True)

        # Dados carregados
        self.alunos = []
        self.turmas = {}

        self._construir_interface()
        self._centralizar_janela()

        logger.info("Interface gráfica iniciada")

    def _centralizar_janela(self):
        """Centraliza a janela na tela."""
        self.root.update_idletasks()
        largura = self.root.winfo_width()
        altura = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (largura // 2)
        y = (self.root.winfo_screenheight() // 2) - (altura // 2)
        self.root.geometry(f"{largura}x{altura}+{x}+{y}")

    def _construir_interface(self):
        """Constrói todos os elementos da interface."""
        # Menu
        self._criar_menu()

        # Frame principal com abas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Abas
        self._criar_aba_importar()
        self._criar_aba_configurar()
        self._criar_aba_gerar()
        self._criar_aba_log()

        # Barra de status
        self._criar_status_bar()

    def _criar_menu(self):
        """Cria a barra de menus."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Menu Arquivo
        menu_arquivo = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Arquivo", menu=menu_arquivo)
        menu_arquivo.add_command(label="Abrir Planilha...", command=self.selecionar_planilha, accelerator="Ctrl+O")
        menu_arquivo.add_command(label="Criar Arquivo Exemplo", command=self.criar_exemplo)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="Criar Backup", command=self.executar_backup)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="Sair", command=self.root.quit, accelerator="Ctrl+Q")

        # Menu Ferramentas
        menu_ferramentas = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ferramentas", menu=menu_ferramentas)
        menu_ferramentas.add_command(label="Diagnosticar Sistema", command=self.executar_diagnostico)
        menu_ferramentas.add_command(label="Abrir Pasta de Saída", command=self.abrir_pasta_saida)

        # Menu Ajuda
        menu_ajuda = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ajuda", menu=menu_ajuda)
        menu_ajuda.add_command(label="Sobre", command=self.mostrar_sobre)

        # Atalhos de teclado
        self.root.bind("<Control-o>", lambda e: self.selecionar_planilha())
        self.root.bind("<Control-q>", lambda e: self.root.quit())

    def _criar_aba_importar(self):
        """Aba de importação de dados."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📂 Importar Dados")

        # Título
        ttk.Label(frame, text="Importar Dados da Planilha",
                  font=("Arial", 14, "bold")).pack(pady=10)

        # Frame de seleção de arquivo
        frame_arquivo = ttk.LabelFrame(frame, text="Selecionar Planilha", padding=10)
        frame_arquivo.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(frame_arquivo, text="Arquivo:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame_arquivo, textvariable=self.planilha_path, width=60).grid(row=0, column=1, padx=5)
        ttk.Button(frame_arquivo, text="📁 Procurar", command=self.selecionar_planilha).grid(row=0, column=2)

        ttk.Label(frame_arquivo, text="Formatos: .xlsx, .xls, .csv",
                  font=("Arial", 9), foreground="gray").grid(row=1, column=1, sticky=tk.W)

        # Informações da planilha
        self.frame_info = ttk.LabelFrame(frame, text="Informações da Planilha", padding=10)
        self.frame_info.pack(fill=tk.X, padx=20, pady=10)

        self.label_info = ttk.Label(self.frame_info, text="Nenhuma planilha carregada.")
        self.label_info.pack()

        # Preview dos dados
        frame_preview = ttk.LabelFrame(frame, text="Preview dos Dados", padding=10)
        frame_preview.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Treeview para preview
        colunas = ("nome", "turma", "curso", "matricula")
        self.tree_preview = ttk.Treeview(frame_preview, columns=colunas, show="headings", height=8)
        self.tree_preview.heading("nome", text="Nome")
        self.tree_preview.heading("turma", text="Turma")
        self.tree_preview.heading("curso", text="Curso")
        self.tree_preview.heading("matricula", text="Matrícula")

        self.tree_preview.column("nome", width=250)
        self.tree_preview.column("turma", width=80)
        self.tree_preview.column("curso", width=200)
        self.tree_preview.column("matricula", width=100)

        scrollbar = ttk.Scrollbar(frame_preview, orient=tk.VERTICAL, command=self.tree_preview.yview)
        self.tree_preview.configure(yscrollcommand=scrollbar.set)
        self.tree_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Botões
        frame_botoes = ttk.Frame(frame)
        frame_botoes.pack(pady=10)
        ttk.Button(frame_botoes, text="🔄 Carregar Dados", command=self.carregar_dados).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes, text="📝 Criar Arquivo Exemplo", command=self.criar_exemplo).pack(side=tk.LEFT, padx=5)

    def _criar_aba_configurar(self):
        """Aba de configuração do layout."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="⚙️ Configurar")

        # Título
        ttk.Label(frame, text="Configurações do Crachá",
                  font=("Arial", 14, "bold")).pack(pady=10)

        # Frame de configurações visuais
        frame_visual = ttk.LabelFrame(frame, text="Layout Visual", padding=10)
        frame_visual.pack(fill=tk.X, padx=20, pady=10)

        # Cor de destaque
        ttk.Label(frame_visual, text="Cor de Destaque:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame_visual, textvariable=self.cor_destaque, width=15).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(frame_visual, text="🎨", command=self.escolher_cor, width=3).grid(row=0, column=2)

        # Opções
        ttk.Checkbutton(frame_visual, text="Mostrar foto do aluno",
                        variable=self.mostrar_foto).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame_visual, text="Mostrar QR Code",
                        variable=self.mostrar_qr).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)

        # Formato de saída
        frame_formato = ttk.LabelFrame(frame, text="Formato de Saída", padding=10)
        frame_formato.pack(fill=tk.X, padx=20, pady=10)

        for i, fmt in enumerate(FORMATOS_SAIDA):
            ttk.Radiobutton(
                frame_formato,
                text=fmt.upper(),
                variable=self.formato_saida,
                value=fmt,
            ).grid(row=0, column=i, padx=10)

        ttk.Label(frame_formato, text="Selecione o formato principal para exportação.",
                  font=("Arial", 9), foreground="gray").grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=5)

        # Pasta de saída
        frame_pasta = ttk.LabelFrame(frame, text="Pasta de Destino", padding=10)
        frame_pasta.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(frame_pasta, text="Salvar em:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame_pasta, textvariable=self.pasta_saida, width=60).grid(row=0, column=1, padx=5)
        ttk.Button(frame_pasta, text="📁", command=self.selecionar_pasta_saida).grid(row=0, column=2)

    def _criar_aba_gerar(self):
        """Aba de geração dos crachás."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🚀 Gerar Crachás")

        # Título
        ttk.Label(frame, text="Gerar Crachás",
                  font=("Arial", 14, "bold")).pack(pady=10)

        # Resumo
        self.frame_resumo = ttk.LabelFrame(frame, text="Resumo", padding=10)
        self.frame_resumo.pack(fill=tk.X, padx=20, pady=10)

        self.label_resumo = ttk.Label(
            self.frame_resumo,
            text="Nenhum dado carregado. Importe uma planilha primeiro.",
        )
        self.label_resumo.pack()

        # Barra de progresso
        self.progresso = ttk.Progressbar(frame, mode="determinate", length=400)
        self.progresso.pack(pady=10)

        self.label_progresso = ttk.Label(frame, text="")
        self.label_progresso.pack()

        # Botão de geração
        frame_botoes = ttk.Frame(frame)
        frame_botoes.pack(pady=20)

        self.btn_gerar = ttk.Button(
            frame_botoes,
            text="🎯 GERAR CRACHÁS",
            command=self.gerar_crachas,
            width=30,
        )
        self.btn_gerar.pack()

        ttk.Label(frame_botoes, text="Gera todos os crachás dos alunos carregados.",
                  font=("Arial", 9), foreground="gray").pack(pady=5)

    def _criar_aba_log(self):
        """Aba de log do sistema."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📋 Log")

        self.text_log = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=30)
        self.text_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Handler de log para a interface
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                msg = self.format(record)
                self.text_widget.insert(tk.END, msg + "\n")
                self.text_widget.see(tk.END)

        handler = TextHandler(self.text_log)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logging.getLogger("cracha_extractor").addHandler(handler)

    def _criar_status_bar(self):
        """Cria a barra de status inferior."""
        frame_status = ttk.Frame(self.root)
        frame_status.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Separator(frame_status, orient=tk.HORIZONTAL).pack(fill=tk.X)
        ttk.Label(frame_status, textvariable=self.status_texto,
                  relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, padx=5, pady=2)

    # ========== MÉTODOS DE AÇÃO ==========

    def selecionar_planilha(self):
        """Abre diálogo para selecionar planilha."""
        caminho = filedialog.askopenfilename(
            title="Selecionar Planilha",
            filetypes=[
                ("Planilhas", "*.xlsx *.xls *.csv"),
                ("Excel", "*.xlsx *.xls"),
                ("CSV", "*.csv"),
                ("Todos", "*.*"),
            ],
        )
        if caminho:
            self.planilha_path.set(caminho)
            self.status_texto.set(f"Planilha selecionada: {Path(caminho).name}")
            self.carregar_dados()

    def selecionar_pasta_saida(self):
        """Abre diálogo para selecionar pasta de saída."""
        caminho = filedialog.askdirectory(
            title="Selecionar Pasta de Destino",
            initialdir=self.pasta_saida.get(),
        )
        if caminho:
            self.pasta_saida.set(caminho)

    def escolher_cor(self):
        """Abre seletor de cores."""
        from tkinter import colorchooser
        cor = colorchooser.askcolor(
            title="Escolher Cor de Destaque",
            initialcolor=self.cor_destaque.get(),
        )
        if cor and cor[1]:
            self.cor_destaque.set(cor[1])

    def carregar_dados(self):
        """Carrega os dados da planilha selecionada."""
        caminho = self.planilha_path.get()
        if not caminho:
            messagebox.showwarning("Aviso", "Selecione uma planilha primeiro!")
            return

        try:
            self.status_texto.set("Carregando dados...")
            reader = PlanilhaReader(caminho)
            self.alunos = reader.ler()
            self.turmas = reader.agrupar_por_turma(self.alunos)

            # Atualizar preview
            for item in self.tree_preview.get_children():
                self.tree_preview.delete(item)

            for aluno in self.alunos[:50]:  # Mostrar até 50 no preview
                self.tree_preview.insert("", tk.END, values=(
                    aluno.nome,
                    aluno.turma,
                    aluno.curso,
                    aluno.matricula,
                ))

            # Atualizar info
            info = (
                f"✅ {len(self.alunos)} alunos carregados | "
                f"{len(self.turmas)} turmas encontradas | "
                f"Colunas: {', '.join(reader.colunas_mapeadas.keys())}"
            )
            self.label_info.config(text=info)

            # Atualizar resumo na aba de geração
            turmas_str = ", ".join([f"{t.nome} ({len(t.alunos)} alunos)" for t in self.turmas.values()])
            self.label_resumo.config(
                text=f"📊 {len(self.alunos)} alunos em {len(self.turmas)} turmas:\n{turmas_str}"
            )

            self.status_texto.set(f"✅ Dados carregados: {len(self.alunos)} alunos")
            logger.info(f"Dados carregados: {len(self.alunos)} alunos de {caminho}")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar dados:\n{str(e)}")
            self.status_texto.set("❌ Erro ao carregar dados")
            logger.error(f"Erro ao carregar dados: {e}")

    def gerar_crachas(self):
        """Gera os crachás em uma thread separada."""
        if not self.alunos:
            messagebox.showwarning("Aviso", "Nenhum dado carregado. Importe uma planilha primeiro!")
            return

        # Iniciar em thread separada para não travar a interface
        thread = Thread(target=self._gerar_crachas_thread, daemon=True)
        thread.start()

    def _gerar_crachas_thread(self):
        """Executa a geração dos crachás (executado em thread separada)."""
        try:
            self.btn_gerar.config(state=tk.DISABLED)
            self.progresso["value"] = 0
            self.progresso["maximum"] = len(self.alunos)

            # Configurar
            config = ConfiguracaoCracha(
                turma_nome="",
                cor_destaque=self.cor_destaque.get(),
                mostrar_foto=self.mostrar_foto.get(),
                mostrar_qr_code=self.mostrar_qr.get(),
            )

            montador = MontadorCracha(config)
            exportador = ExportadorCracha(montador)
            pasta_saida = Path(self.pasta_saida.get())
            formato = self.formato_saida.get()

            # Gerar um a um
            for i, aluno in enumerate(self.alunos):
                nome_base = exportador._sanitizar_nome(aluno.nome)

                if aluno.turma:
                    pasta_aluno = pasta_saida / aluno.turma
                else:
                    pasta_aluno = pasta_saida

                pasta_aluno.mkdir(parents=True, exist_ok=True)

                if formato == "png":
                    exportador.exportar_png(aluno, pasta_aluno / f"{nome_base}.png")
                elif formato == "jpg":
                    exportador.exportar_jpg(aluno, pasta_aluno / f"{nome_base}.jpg")
                elif formato == "pdf":
                    exportador.exportar_pdf(aluno, pasta_aluno / f"{nome_base}.pdf")
                elif formato == "html":
                    exportador.exportar_html(aluno, pasta_aluno / f"{nome_base}.html")

                # Atualizar progresso
                self.progresso["value"] = i + 1
                self.label_progresso.config(
                    text=f"Gerando: {aluno.nome} ({i + 1}/{len(self.alunos)})"
                )

            self.status_texto.set(f"✅ {len(self.alunos)} crachás gerados em {pasta_saida}")
            self.label_progresso.config(text="✅ Geração concluída!")

            messagebox.showinfo(
                "Concluído",
                f"{len(self.alunos)} crachás gerados com sucesso!\n"
                f"Pasta: {pasta_saida}",
            )

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gerar crachás:\n{str(e)}")
            logger.error(f"Erro ao gerar crachás: {e}")
        finally:
            self.btn_gerar.config(state=tk.NORMAL)

    def executar_backup(self):
        """Executa backup do sistema."""
        try:
            caminho = criar_backup()
            messagebox.showinfo("Backup", f"Backup criado em:\n{caminho}")
            self.status_texto.set(f"Backup criado: {caminho}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao criar backup:\n{str(e)}")

    def executar_diagnostico(self):
        """Executa diagnóstico do sistema."""
        diag = Diagnosticador()
        resultado = diag.verificar_estrutura()

        msg = "=== DIAGNÓSTICO DO SISTEMA ===\n\n"
        msg += "Estrutura de Diretórios:\n"
        for nome, info in resultado.items():
            status = "✅" if info["existe"] else "❌"
            msg += f"  {status} {nome}: {info['caminho']}\n"

        msg += f"\nTurmas encontradas: {len(diag.listar_turmas_disponiveis())}\n"
        msg += f"Crachás montados: {len(diag.listar_crachas_montados())}\n"

        messagebox.showinfo("Diagnóstico", msg)

    def abrir_pasta_saida(self):
        """Abre a pasta de saída no explorador."""
        pasta = self.pasta_saida.get()
        if Path(pasta).exists():
            webbrowser.open(pasta)
        else:
            messagebox.showwarning("Aviso", "Pasta de saída não encontrada!")

    def criar_exemplo(self):
        """Cria um arquivo Excel de exemplo."""
        caminho = filedialog.asksaveasfilename(
            title="Salvar Arquivo Exemplo",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="modelo_alunos.xlsx",
        )
        if caminho:
            try:
                criar_arquivo_exemplo(caminho)
                messagebox.showinfo(
                    "Sucesso",
                    f"Arquivo exemplo criado:\n{caminho}\n\n"
                    "Preencha com os dados dos alunos e importe no sistema.",
                )
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao criar exemplo:\n{str(e)}")

    def mostrar_sobre(self):
        """Mostra informações sobre o sistema."""
        messagebox.showinfo(
            "Sobre",
            "Sistema de Montagem de Crachás\n"
            "Versão: 1.0.0\n\n"
            "Funcionalidades:\n"
            "• Importar dados de planilhas Excel/CSV\n"
            "• Gerar QR Codes automaticamente\n"
            "• Processar fotos dos alunos\n"
            "• Exportar em PNG, JPG, PDF e HTML\n"
            "• Layout personalizável\n\n"
            "Python + PIL + Tkinter + OpenPyXL",
        )

    def iniciar(self):
        """Inicia o loop principal da interface."""
        self.root.mainloop()
