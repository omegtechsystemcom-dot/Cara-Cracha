# 📁 Estrutura do Projeto - Sistema de Montagem de Crachás IEMA

```
CRACHA IMPRIMIR/
│
├── .venv/                  ← Ambiente virtual Python (dependências)
├── .vscode/                ← Configurações do VS Code
│   └── settings.json
│
├── _diag_saida/            ← Arquivos temporários e diagnósticos
│   ├── arquivos_antigos/
│   ├── previews/
│   ├── uploads/            ← Planilhas enviadas via web
│   └── modelo_alunos.xlsx  ← Planilha exemplo gerada
│
├── cracha_extractor/       ← Código fonte do sistema (pacote Python)
│   ├── __init__.py
│   ├── api.py              ← API Flask (backend web)
│   ├── config.py           ← Configurações e constantes
│   ├── exportador.py       ← Exportação PNG/JPG/PDF/HTML
│   ├── foto_handler.py     ← Processamento de fotos
│   ├── interface.py        ← Interface gráfica Tkinter (legado)
│   ├── models.py           ← Modelos de dados (Aluno, Turma)
│   ├── montador.py         ← Montagem do layout IEMA
│   ├── planilha_reader.py  ← Leitor de Excel/CSV
│   ├── qr_generator.py     ← Gerador de QR Codes
│   ├── turmas_iema.py      ← Mapeamento turma → curso IEMA
│   └── utils.py            ← Utilitários (log, backup, diagnóstico)
│
├── crachas_montados/       ← Crachás gerados (organizados por turma)
│   ├── 101/                ← 40 alunos
│   ├── 102/                ← 44 alunos
│   ├── 103/                ← 41 alunos
│   ├── 104/                ← 41 alunos
│   ├── 201/                ← 39 alunos
│   ├── 202/                ← 37 alunos
│   ├── 203/                ← 34 alunos
│   ├── 204/                ← 39 alunos
│   ├── 301/                ← 29 alunos
│   ├── 302/                ← 37 alunos
│   ├── 303/                ← 35 alunos
│   └── 304/                ← 31 alunos
│
├── logs/                   ← Logs do sistema
│   └── cracha_extractor.log
│
├── static/                 ← Frontend web
│   ├── index.html          ← Página principal
│   ├── style.css           ← Estilos CSS
│   ├── app.js              ← JavaScript (SPA)
│   ├── fundo_iema.png      ← Template de fundo IEMA
│   └── template_iema.png   ← Modelo de referência
│
├── tests/                  ← Testes automatizados
│   └── test_cracha_extractor.py  ← 14 testes
│
├── alunosiema.xlsx         ← Base de dados (440 alunos, 12 turmas)
├── cracharmodeloiema.png   ← Modelo visual de referência
├── iniciar.bat             ← Atalho para executar (duplo clique)
├── main.py                 ← Ponto de entrada do sistema
├── modelo_alunos.xlsx      ← Planilha exemplo para testes
└── requirements.txt        ← Dependências do projeto
```

---

## 🚀 Como executar

| Método | Comando |
|--------|---------|
| **Duplo clique** | Clique duas vezes em `iniciar.bat` |
| **Terminal (recomendado)** | `.venv\Scripts\python main.py` |
| **Porta personalizada** | `.venv\Scripts\python main.py --port=8080` |
| **Modo terminal (CLI)** | `.venv\Scripts\python main.py --cli --planilha alunosiema.xlsx --formato png` |
| **Modo Tkinter** | `.venv\Scripts\python main.py --gui` |
| **Diagnóstico** | `.venv\Scripts\python main.py --diagnostico` |
| **Testes** | `.venv\Scripts\python -m pytest tests/ -v` |

## 📊 Dados

- **440 alunos** em **12 turmas** (101 a 304)
- **445 crachás gerados** (~19.5 MB)
- **14 testes** automatizados
- Layout padrão **IEMA** com cores institucionais

## 🎨 Cores IEMA

| Cor | RGB | Hex |
|-----|-----|-----|
| Rosa | `(229, 67, 103)` | `#E54367` |
| Verde | `(136, 162, 1)` | `#88A201` |
| Azul | `(70, 168, 189)` | `#46A8BD` |
| Fundo | `(250, 253, 255)` | `#FAFDFF` |
