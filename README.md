<div align="center">
  <h1>🪪 Sistema de Montagem de Crachás IEMA</h1>
  <p><strong>Instituto Estadual de Educação, Ciência e Tecnologia do Maranhão</strong></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.13+-blue?logo=python" alt="Python">
    <img src="https://img.shields.io/badge/Flask-3.0+-green?logo=flask" alt="Flask">
    <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
    <img src="https://img.shields.io/badge/testes-14%20%F0%9F%94%80-success" alt="Testes">
  </p>
</div>

---

## 📋 Sobre

Sistema completo para **importação, montagem e exportação** de crachás institucionais do IEMA.  
Desenvolvido em Python com interface web moderna.

### ✨ Funcionalidades

- 📂 **Importar planilhas** Excel/CSV com detecção automática de colunas
- 🏫 **Carregar dados do IEMA** com 1 clique (440 alunos, 12 turmas)
- 📸 **Processar fotos** dos alunos (redimensionamento automático)
- 📱 **Gerar QR Codes** individuais para cada crachá
- 🎨 **Layout institucional** com cores oficiais IEMA (rosa, verde, azul)
- 🖼️ **Exportar** em PNG, JPG, PDF e HTML
- 🌐 **Interface web** moderna e responsiva
- 👁️ **Preview** visual do crachá antes de gerar
- 🔍 **Diagnóstico** do sistema
- 💾 **Backup** automático

---

## 🚀 Como executar

### ✅ Pré-requisitos

- Python 3.13+
- Git (para clonar)

### 📥 Instalação

```bash
# Clone o repositório
git clone https://github.com/omegtechsystemcom-dot/Cara-Cracha.git
cd Cara-Cracha

# Crie o ambiente virtual
python -m venv .venv

# Ative o ambiente
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Instale as dependências
pip install -r requirements.txt
```

### ▶️ Executar

| Método | Comando |
|--------|---------|
| 🌐 **Interface Web** (padrão) | `.venv\Scripts\python main.py` |
| 🖥️ **Duplo clique** | Clique em `iniciar.bat` |
| 🎨 **Modo Tkinter** | `.venv\Scripts\python main.py --gui` |
| 📟 **Modo terminal** | `.venv\Scripts\python main.py --cli --planilha alunosiema.xlsx --formato png` |
| 🔬 **Testes** | `.venv\Scripts\python -m pytest tests/ -v` |

Acesse: **http://127.0.0.1:5000**

---

## 📊 Dados

| Item | Quantidade |
|------|-----------|
| 👥 **Alunos** | **440** |
| 🏫 **Turmas** | **12** (101 a 304) |
| ✅ **Crachás gerados** | **445** |
| 🧪 **Testes automatizados** | **14** (100% passando) |

### Turmas

| Ano | Turmas | Alunos |
|-----|--------|--------|
| **1º Ano** | 101, 102, 103, 104 | 160 |
| **2º Ano** | 201, 202, 203, 204 | 149 |
| **3º Ano** | 301, 302, 303, 304 | 131 |

---

## 🎨 Layout IEMA

O crachá segue o **layout institucional** com as cores oficiais:

```
┌──────────────────────────────────┐
│ ██  GRADIENTE AZUL CLARO    ██  │
│          ┌──────────┐            │
│          │  FOTO DO  │            │
│          │  ALUNO    │            │
│          └──────────┘            │
│██████████ CURSO █████████████████│  ← Faixa verde
│         NOME DO ALUNO            │
│          ┌──────────┐            │
│          │ QR CODE  │            │
│          └──────────┘            │
│██████████ TURMA █████████████████│  ← Faixa verde
│████ INFORMAÇÕES IEMA ███████████│  ← Faixa azul
│██████████ IEMA █████████████████│  ← Faixa rosa
└──────────────────────────────────┘
```

### Cores institucionais

| Cor | RGB | Hex |
|-----|-----|-----|
| 🟥 Rosa | `(229, 67, 103)` | `#E54367` |
| 🟩 Verde | `(136, 162, 1)` | `#88A201` |
| 🟦 Azul | `(70, 168, 189)` | `#46A8BD` |
| ⬜ Fundo | `(250, 253, 255)` | `#FAFDFF` |

### Fotos dos alunos

Na tela **Importar Dados**, use **Importar Fotos dos Alunos** para selecionar várias imagens.
O arquivo pode ter o código/matrícula (`2024001.jpg` ou `2024001_maria_silva.jpg`) ou o
nome completo do aluno (`maria_da_silva.jpg`). O código é lido das colunas `Código do aluno`,
`Código`, `Matrícula`, `RA`, `Registro` ou `ID` da planilha.
O sistema ignora diferenças de acentos, espaços e letras maiúsculas. Também é possível
informar uma coluna `Foto` na planilha com um caminho como `fotos_alunos/maria_da_silva.jpg`.

### Identificador dos QR Codes

Cada QR Code usa obrigatoriamente o código do aluno lido da planilha. O conteúdo segue o
formato versionado `IEMA|V1|COD=2024001|TURMA=101`. Se a planilha trouxer dados adicionais
para o QR, eles são anexados ao conteúdo e não substituem o código oficial.

Antes da geração, o sistema verifica os alunos selecionados e interrompe o processo quando
encontra código vazio ou repetido. Assim, nenhum crachá com QR ambíguo é salvo.

### PDF para impressão por turma

No menu **Gerar Crachás**, selecione uma turma e use **Exportar PDF da Turma**. O sistema
organiza todos os alunos da turma em ordem alfabética, com 10 crachás de 50 x 85 mm por
folha A4 paisagem, espaçamento de 3 mm e marcas de corte. O PDF é baixado pelo navegador
e também salvo em `crachas_montados/<turma>/Turma_<turma>_Crachas.pdf`.

---

## 🏗️ Estrutura do Projeto

```
Cara-Cracha/
├── main.py                 ← Ponto de entrada
├── alunosiema.xlsx         ← Base de dados (440 alunos)
├── requirements.txt        ← Dependências
├── iniciar.bat             ← Atalho para executar
├── cracha_extractor/       ← Código fonte (pacote Python)
│   ├── api.py              ← API Flask
│   ├── config.py           ← Configurações
│   ├── montador.py         ← Layout IEMA
│   ├── planilha_reader.py  ← Leitor de planilhas
│   ├── qr_generator.py     ← QR Code
│   ├── foto_handler.py     ← Fotos
│   ├── exportador.py       ← Exportação
│   ├── models.py           ← Modelos de dados
│   ├── turmas_iema.py      ← Mapeamento IEMA
│   └── utils.py            ← Utilitários
├── static/                 ← Frontend web
│   ├── index.html          ← Página principal
│   ├── style.css           ← Estilos
│   └── app.js              ← JavaScript
└── tests/                  ← Testes
    └── test_cracha_extractor.py
```

---

## 🧪 Testes

```bash
.venv\Scripts\python -m pytest tests/ -v
```

```
collected 14 items
tests/test_cracha_extractor.py ... PASSED [100%]
✅ 14 passed in 1.31s
```

---

## 📄 Licença

Este projeto é de uso institucional do **IEMA - Instituto Estadual de Educação, Ciência e Tecnologia do Maranhão**.

---

<div align="center">
  <p>Desenvolvido com ❤️ para o IEMA</p>
  <p>
    <a href="https://github.com/omegtechsystemcom-dot/Cara-Cracha">GitHub</a>
  </p>
</div>
