/**
 * Sistema de Crachás - Frontend JavaScript
 * Aplicação SPA com comunicação via API REST
 */

// ===== ESTADO GLOBAL =====
const STATE = {
    alunos: [],
    turmas: {},
    planilhaCarregada: false,
    alunosSelecionados: new Set(),
    formato: 'png',
    corDestaque: '#1a5276',
    mostrarFoto: true,
    mostrarQR: true,
};

// ===== API HELPER =====
const API = {
    async request(url, options = {}) {
        const config = {
            headers: { 'Accept': 'application/json' },
            ...options,
        };

        if (config.body && !(config.body instanceof FormData)) {
            config.headers['Content-Type'] = 'application/json';
            config.body = JSON.stringify(config.body);
        }

        const response = await fetch(url, config);
        if (!response.ok) {
            const err = await response.json().catch(() => ({ erro: 'Erro desconhecido' }));
            throw new Error(err.erro || `HTTP ${response.status}`);
        }
        return response.json();
    },

    get(url) { return this.request(url); },
    post(url, data) { return this.request(url, { method: 'POST', body: data }); },
    upload(url, formData) { return this.request(url, { method: 'POST', body: formData }); },
};

// ===== PLANILHA PADRÃO IEMA =====
async function carregarDadosIEMA() {
    try {
        mostrarToast('📂 Carregando dados do IEMA...', 'info');
        const data = await API.post('/api/planilha-padrao');

        // Salvar estado
        STATE.alunos = data.preview || [];
        STATE.turmas = data.turmas || {};
        STATE.planilhaCarregada = true;

        // Atualizar badge
        document.getElementById('badge-alunos').textContent = data.total_alunos;

        mostrarToast(`✅ ${data.total_alunos} alunos do IEMA carregados!`, 'success');

        // Ir para preview
        mudarAba('importar');

        // Mostrar preview
        const previewArea = document.getElementById('previewArea');
        previewArea.style.display = 'block';

        document.getElementById('previewStats').textContent =
            `${data.total_alunos} alunos • ${data.total_turmas} turmas • ${data.arquivo}`;

        // Renderizar tabela de preview
        const table = document.getElementById('previewTable');
        const thead = table.querySelector('thead tr');
        const tbody = table.querySelector('tbody');

        const colunas = Object.keys(data.colunas_detectadas);
        thead.innerHTML = colunas.map(c =>
            `<th>${c.charAt(0).toUpperCase() + c.slice(1)}</th>`
        ).join('');

        tbody.innerHTML = data.preview.map(a => `
            <tr>
                <td>${a.nome}</td>
                <td>${a.turma}</td>
                <td>${a.curso}</td>
                <td>${a.matricula}</td>
            </tr>
        `).join('');

        // Confirmar importação automaticamente
        await confirmarImportacao();

    } catch (err) {
        mostrarToast(`❌ ${err.message}`, 'error');
    }
}

// ===== NAVEGAÇÃO =====
function mudarAba(aba) {
    // Atualizar tabs
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.getElementById(`tab-${aba}`).classList.add('active');

    // Atualizar nav
    document.querySelectorAll('.nav-item[data-tab]').forEach(el => el.classList.remove('active'));
    const navItem = document.querySelector(`.nav-item[data-tab="${aba}"]`);
    if (navItem) navItem.classList.add('active');

    // Atualizar título
    const labels = {
        dashboard: 'Dashboard',
        importar: 'Importar Dados',
        alunos: 'Alunos',
        configurar: 'Configurações',
        gerar: 'Gerar Crachás',
        visualizar: 'Visualizar',
    };
    document.getElementById('pageTitle').textContent = labels[aba] || aba;

    // Ações específicas
    if (aba === 'dashboard') carregarDashboard();
    if (aba === 'alunos') renderizarAlunos();
    if (aba === 'visualizar') carregarPreviewAlunos();

    // Fechar sidebar mobile
    document.getElementById('sidebar').classList.remove('open');
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

// ===== TOAST =====
function mostrarToast(mensagem, tipo = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${tipo}`;
    toast.textContent = mensagem;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ===== MODAL =====
function abrirModal(titulo, conteudo) {
    document.getElementById('modalTitle').textContent = titulo;
    document.getElementById('modalBody').innerHTML = conteudo;
    document.getElementById('modalOverlay').classList.add('open');
}

function fecharModal() {
    document.getElementById('modalOverlay').classList.remove('open');
}

// ===== DASHBOARD =====
async function carregarDashboard() {
    try {
        const diag = await API.get('/api/diagnostico');

        document.getElementById('stat-alunos').textContent = STATE.alunos.length || diag.total_crachas || '0';
        document.getElementById('stat-turmas').textContent = Object.keys(STATE.turmas).length || '0';
        document.getElementById('stat-gerados').textContent = diag.total_crachas || '0';
        document.getElementById('stat-planilha').textContent = STATE.planilhaCarregada ? '✅' : '—';

        // Últimos crachás
        const container = document.getElementById('ultimos-crachas');
        if (diag.crachas_montados && diag.crachas_montados.length > 0) {
            const recentes = diag.crachas_montados.slice(-8).reverse();
            container.innerHTML = `
                <div class="result-grid">
                    ${recentes.map(c => `
                        <div class="result-item">
                            <span class="nome">${c.nome}</span>
                            <span class="meta">${c.turma} • ${(c.tamanho_kb || 0).toFixed(1)}KB</span>
                            <span class="meta">${c.formato.toUpperCase()}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            container.innerHTML = '<p class="text-muted">Nenhum crachá gerado ainda.</p>';
        }
    } catch (err) {
        console.error('Erro ao carregar dashboard:', err);
    }
}

// ===== IMPORTAR PLANILHA =====
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) processarArquivo(file);
}

function handleDrop(event) {
    event.preventDefault();
    document.getElementById('uploadZone').classList.remove('drag-over');
    const file = event.dataTransfer.files[0];
    if (file) processarArquivo(file);
}

async function processarArquivo(file) {
    if (!file) return;

    const formData = new FormData();
    formData.append('arquivo', file);

    try {
        mostrarToast('Lendo planilha...', 'info');
        const data = await API.upload('/api/planilha/colunas', formData);

        // Salvar estado
        STATE.alunos = data.preview || [];
        STATE.turmas = data.turmas || {};
        STATE.planilhaCarregada = true;

        // Atualizar badge
        document.getElementById('badge-alunos').textContent = data.total_alunos;

        // Mostrar preview
        const previewArea = document.getElementById('previewArea');
        previewArea.style.display = 'block';

        document.getElementById('previewStats').textContent =
            `${data.total_alunos} alunos • ${data.total_turmas} turmas`;

        // Renderizar tabela de preview
        const table = document.getElementById('previewTable');
        const thead = table.querySelector('thead tr');
        const tbody = table.querySelector('tbody');

        // Cabeçalho
        const colunas = Object.keys(data.colunas_detectadas);
        thead.innerHTML = colunas.map(c =>
            `<th>${c.charAt(0).toUpperCase() + c.slice(1)}</th>`
        ).join('') + '<th>Ações</th>';

        // Dados
        tbody.innerHTML = data.preview.map((a, i) => `
            <tr>
                <td>${a.nome}</td>
                <td>${a.turma}</td>
                <td>${a.curso}</td>
                <td>${a.matricula}</td>
                <td>
                    <span title="${a.tem_foto ? 'Com foto' : 'Sem foto'}">
                        ${a.tem_foto ? '📸' : '👤'}
                    </span>
                    <span title="${a.tem_qr ? 'Com QR' : 'Sem QR'}">
                        ${a.tem_qr ? '📱' : '—'}
                    </span>
                </td>
            </tr>
        `).join('');

        mostrarToast(`✅ ${data.total_alunos} alunos encontrados!`, 'success');

    } catch (err) {
        mostrarToast(`❌ ${err.message}`, 'error');
    }
}

async function confirmarImportacao() {
    try {
        // Recarregar dados completos
        const data = await API.get('/api/alunos');
        STATE.alunos = data.alunos || [];

        // Atualizar interface
        document.getElementById('badge-alunos').textContent = data.total;
        document.getElementById('stat-alunos').textContent = data.total;
        document.getElementById('stat-planilha').textContent = '✅';

        // Preencher filtro de turmas
        const select = document.getElementById('filterTurma');
        const turmas = [...new Set(STATE.alunos.map(a => a.turma).filter(Boolean))];
        select.innerHTML = '<option value="">Todas as turmas</option>' +
            turmas.map(t => `<option value="${t}">${t}</option>`).join('');

        // Carregar preview alunos
        carregarPreviewAlunos();

        mostrarToast(`✅ ${data.total} alunos importados com sucesso!`, 'success');
        mudarAba('alunos');
    } catch (err) {
        mostrarToast(`❌ ${err.message}`, 'error');
    }
}

function cancelarImportacao() {
    document.getElementById('previewArea').style.display = 'none';
    document.getElementById('fileInput').value = '';
}

// ===== ALUNOS =====
function renderizarAlunos() {
    const busca = document.getElementById('searchAluno').value.toLowerCase();
    const turmaFiltro = document.getElementById('filterTurma').value;

    let alunos = STATE.alunos;

    if (turmaFiltro) alunos = alunos.filter(a => a.turma === turmaFiltro);
    if (busca) alunos = alunos.filter(a =>
        a.nome.toLowerCase().includes(busca) ||
        (a.matricula && a.matricula.toLowerCase().includes(busca))
    );

    const tbody = document.getElementById('alunosBody');

    if (alunos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:2rem;color:var(--text-muted)">
            Nenhum aluno encontrado. Importe uma planilha primeiro.
        </td></tr>`;
        document.getElementById('alunosCount').textContent = '0 alunos';
        return;
    }

    tbody.innerHTML = alunos.map(a => `
        <tr>
            <td><input type="checkbox" class="aluno-check"
                value="${a.nome}"
                ${STATE.alunosSelecionados.has(a.nome) ? 'checked' : ''}
                onchange="toggleAluno('${a.nome}')"></td>
            <td><strong>${a.nome}</strong></td>
            <td>${a.turma}</td>
            <td>${a.curso}</td>
            <td>${a.matricula || '—'}</td>
            <td>
                <button class="btn btn-outline" style="padding:0.25rem 0.5rem;font-size:0.75rem"
                    onclick="previewAlunoEspecifico('${a.nome}')">👁️</button>
            </td>
        </tr>
    `).join('');

    document.getElementById('alunosCount').textContent = `${alunos.length} alunos`;
    atualizarGerarInfo();
}

function filtrarAlunos() {
    renderizarAlunos();
}

function toggleAluno(nome) {
    if (STATE.alunosSelecionados.has(nome)) {
        STATE.alunosSelecionados.delete(nome);
    } else {
        STATE.alunosSelecionados.add(nome);
    }
    atualizarGerarInfo();
}

function selecionarTodos() {
    const checked = document.getElementById('selectAll').checked;
    document.querySelectorAll('.aluno-check').forEach(cb => {
        cb.checked = checked;
        const nome = cb.value;
        if (checked) STATE.alunosSelecionados.add(nome);
        else STATE.alunosSelecionados.delete(nome);
    });
    atualizarGerarInfo();
}

function atualizarGerarInfo() {
    const total = STATE.alunosSelecionados.size || STATE.alunos.length;
    document.getElementById('gerar-total').textContent = total;
}

// ===== CONFIGURAÇÕES =====
function mudarFormato(input) {
    STATE.formato = input.value;
    document.querySelectorAll('.radio-card').forEach(el => el.classList.remove('selected'));
    input.closest('.radio-card').classList.add('selected');
    document.getElementById('gerar-formato').textContent = input.value.toUpperCase();
}

function atualizarCor(hex) {
    if (/^#[0-9a-fA-F]{6}$/.test(hex)) {
        STATE.corDestaque = hex;
        document.getElementById('corDestaque').value = hex;
    }
}

function atualizarPreview() {
    STATE.mostrarFoto = document.getElementById('mostrarFoto').checked;
    STATE.mostrarQR = document.getElementById('mostrarQR').checked;
}

// ===== GERAR CRACHÁS =====
async function gerarCrachas() {
    if (STATE.alunos.length === 0) {
        mostrarToast('❌ Importe uma planilha primeiro!', 'error');
        return;
    }

    const btn = document.getElementById('btnGerar');
    btn.disabled = true;
    btn.textContent = '⏳ Gerando...';

    const progressContainer = document.getElementById('progressContainer');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    progressContainer.style.display = 'block';

    try {
        // Simular progresso
        let progresso = 0;
        const interval = setInterval(() => {
            progresso = Math.min(progresso + 5, 90);
            progressFill.style.width = `${progresso}%`;
        }, 200);

        const data = await API.post('/api/gerar', {
            formato: STATE.formato,
            cor_destaque: STATE.corDestaque,
            mostrar_foto: STATE.mostrarFoto,
            mostrar_qr: STATE.mostrarQR,
            alunos: STATE.alunosSelecionados.size > 0
                ? [...STATE.alunosSelecionados]
                : [],
        });

        clearInterval(interval);
        progressFill.style.width = '100%';
        progressText.textContent = '✅ Concluído!';

        // Mostrar resultados
        const resultadoDiv = document.getElementById('resultadoGeracao');
        resultadoDiv.style.display = 'block';

        if (data.total_erros > 0) {
            resultadoDiv.innerHTML = `
                <div class="card" style="border-color: var(--warning);">
                    <div class="card-header">
                        <h3>⚠️ ${data.total_gerados} gerados, ${data.total_erros} erros</h3>
                    </div>
                    <div class="card-body">
                        <p>Pasta: <code>${data.pasta_saida}</code></p>
                        <div class="result-grid" style="margin-top: 0.75rem;">
                            ${data.resultados.map(r => `
                                <div class="result-item">
                                    <span class="nome">${r.nome}</span>
                                    <span class="meta">${(r.tamanho_kb || 0).toFixed(1)}KB • ${r.formato.toUpperCase()}</span>
                                </div>
                            `).join('')}
                        </div>
                        ${data.erros.length > 0 ? `
                            <div style="margin-top: 0.75rem; padding: 0.75rem; background: var(--error-bg); border-radius: var(--radius-sm);">
                                <strong style="color: var(--error);">Erros:</strong>
                                ${data.erros.map(e => `<p style="font-size:0.8rem;">• ${e.nome}: ${e.erro}</p>`).join('')}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        } else {
            resultadoDiv.innerHTML = `
                <div class="card" style="border-color: var(--success);">
                    <div class="card-header">
                        <h3>✅ ${data.total_gerados} crachás gerados com sucesso!</h3>
                    </div>
                    <div class="card-body">
                        <p>Pasta: <code>${data.pasta_saida}</code></p>
                        <div class="result-grid" style="margin-top: 0.75rem;">
                            ${data.resultados.map(r => `
                                <div class="result-item">
                                    <span class="nome">${r.nome}</span>
                                    <span class="meta">${(r.tamanho_kb || 0).toFixed(1)}KB • ${r.formato.toUpperCase()}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            `;
        }

        mostrarToast(`✅ ${data.total_gerados} crachás gerados!`, 'success');
        carregarDashboard();

    } catch (err) {
        progressFill.style.width = '0%';
        progressText.textContent = '❌ Erro ao gerar';
        mostrarToast(`❌ ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🚀 GERAR CRACHÁS';
    }
}

// ===== PREVIEW =====
function carregarPreviewAlunos() {
    const select = document.getElementById('previewAluno');
    const alunos = STATE.alunos;

    if (alunos.length === 0) {
        select.innerHTML = '<option value="">Nenhum aluno carregado</option>';
        return;
    }

    select.innerHTML = '<option value="">Selecione um aluno</option>' +
        alunos.map(a => `<option value="${a.nome}">${a.nome} - ${a.turma}</option>`).join('');
}

function previewAlunoEspecifico(nome) {
    const select = document.getElementById('previewAluno');
    select.value = nome;
    mudarAba('visualizar');
    gerarPreview();
}

async function gerarPreview() {
    const nome = document.getElementById('previewAluno').value;
    if (!nome) return;

    try {
        const data = await API.post('/api/gerar/preview', {
            nome,
            cor_destaque: STATE.corDestaque,
            mostrar_foto: document.getElementById('mostrarFoto').checked,
            mostrar_qr: document.getElementById('mostrarQR').checked,
        });

        document.getElementById('previewPlaceholder').style.display = 'none';
        const previewCracha = document.getElementById('previewCracha');
        previewCracha.style.display = 'block';
        document.getElementById('previewImagem').src = data.imagem;

    } catch (err) {
        mostrarToast(`❌ ${err.message}`, 'error');
    }
}

// ===== AÇÕES =====
async function abrirDiagnostico() {
    try {
        const data = await API.get('/api/diagnostico');
        let html = '<div style="font-family: monospace; font-size: 0.85rem;">';

        html += '<h4 style="margin-bottom: 0.75rem;">📁 Estrutura de Diretórios</h4>';
        for (const [nome, info] of Object.entries(data.estrutura)) {
            const status = info.existe ? '✅' : '❌';
            html += `<div>${status} <strong>${nome}</strong>: ${info.caminho}</div>`;
        }

        html += `<h4 style="margin: 1rem 0 0.5rem;">🏫 Turmas (${data.turmas.length})</h4>`;
        html += data.turmas.length > 0
            ? data.turmas.map(t => `<div>• ${t}</div>`).join('')
            : '<div class="text-muted">Nenhuma turma</div>';

        html += `<h4 style="margin: 1rem 0 0.5rem;">✅ Crachás Gerados: ${data.total_crachas}</h4>`;
        html += '</div>';

        abrirModal('🔍 Diagnóstico do Sistema', html);
    } catch (err) {
        mostrarToast(`❌ ${err.message}`, 'error');
    }
}

async function fazerBackup() {
    try {
        const data = await API.post('/api/backup');
        mostrarToast(`✅ Backup criado: ${data.caminho}`, 'success');
    } catch (err) {
        mostrarToast(`❌ ${err.message}`, 'error');
    }
}

async function baixarExemplo() {
    window.open('/api/baixar-exemplo', '_blank');
    mostrarToast('📝 Baixando arquivo modelo...', 'info');
}

// ===== HEALTH CHECK =====
async function verificarConexao() {
    try {
        const data = await API.get('/api/health');
        document.getElementById('statusIndicator').style.background = 'var(--success)';
        document.getElementById('statusText').textContent = `v${data.versao}`;
    } catch (err) {
        document.getElementById('statusIndicator').style.background = 'var(--error)';
        document.getElementById('statusText').textContent = 'Desconectado';
    }
}

// ===== INICIALIZAÇÃO =====
document.addEventListener('DOMContentLoaded', () => {
    verificarConexao();
    carregarDashboard();

    // Verificar conexão a cada 30s
    setInterval(verificarConexao, 30000);

    // Fechar sidebar ao clicar fora (mobile)
    document.addEventListener('click', (e) => {
        const sidebar = document.getElementById('sidebar');
        const toggle = document.querySelector('.menu-toggle');
        if (window.innerWidth <= 768 &&
            !sidebar.contains(e.target) &&
            !toggle.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    });
});
