/**
 * CracháWeb — interface web.
 * Dados vindos da planilha são sempre inseridos com textContent para evitar
 * que nomes, turmas ou mensagens sejam interpretados como HTML.
 */
'use strict';

const STATE = {
    alunos: [],
    turmas: {},
    planilhaCarregada: false,
    importacaoPendente: null,
    alunosSelecionados: new Set(),
    alunoLocalizadoCodigo: '',
    formato: 'png',
    mostrarFoto: true,
    mostrarQR: true,
};

const API = {
    async request(url, options = {}) {
        const config = { headers: { Accept: 'application/json' }, ...options };
        if (config.body && !(config.body instanceof FormData)) {
            config.headers['Content-Type'] = 'application/json';
            config.body = JSON.stringify(config.body);
        }
        const response = await fetch(url, config);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const erro = new Error(data.erro || `HTTP ${response.status}`);
            erro.status = response.status;
            erro.data = data;
            throw erro;
        }
        return data;
    },
    get(url) { return this.request(url); },
    post(url, body = {}) { return this.request(url, { method: 'POST', body }); },
    upload(url, body) { return this.request(url, { method: 'POST', body }); },
};

const porId = id => document.getElementById(id);
const limpar = elemento => elemento.replaceChildren();
const criar = (tag, texto = '', classe = '') => {
    const elemento = document.createElement(tag);
    if (texto !== '') elemento.textContent = String(texto);
    if (classe) elemento.className = classe;
    return elemento;
};

function mostrarToast(mensagem, tipo = 'info') {
    const toast = criar('div', mensagem, `toast toast-${tipo}`);
    porId('toastContainer').appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

let focoAntesDoModal = null;
function abrirModal(titulo, conteudo) {
    focoAntesDoModal = document.activeElement;
    porId('modalTitle').textContent = titulo;
    const corpo = porId('modalBody');
    limpar(corpo);
    corpo.appendChild(conteudo instanceof Node ? conteudo : criar('p', conteudo));
    const modal = porId('modalOverlay');
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    modal.classList.add('open');
    porId('modalClose').focus();
}

function fecharModal() {
    const modal = porId('modalOverlay');
    modal.classList.remove('open');
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
    if (focoAntesDoModal?.focus) focoAntesDoModal.focus();
}

function atualizarMenuMobile(aberto) {
    porId('sidebar').classList.toggle('open', aberto);
    porId('menuToggle').setAttribute('aria-expanded', String(aberto));
    porId('menuToggle').setAttribute('aria-label', aberto ? 'Fechar menu' : 'Abrir menu');
}

function mudarAba(aba, atualizarHash = true) {
    const secao = porId(`tab-${aba}`);
    if (!secao) return;
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    secao.classList.add('active');
    document.querySelectorAll('.nav-item[data-tab]').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === aba);
    });
    const labels = {
        dashboard: 'Dashboard',
        importar: 'Importar Dados',
        alunos: 'Alunos',
        configurar: 'Configurações',
        gerar: 'Gerar Crachás',
        visualizar: 'Visualizar',
    };
    porId('pageTitle').textContent = labels[aba] || aba;
    if (atualizarHash && location.hash !== `#${aba}`) history.pushState(null, '', `#${aba}`);
    if (aba === 'dashboard') carregarDashboard();
    if (aba === 'alunos') renderizarAlunos();
    if (aba === 'gerar') carregarFiltroGeracao();
    if (aba === 'visualizar') carregarPreviewAlunos();
    atualizarMenuMobile(false);
}

function montarPreviewImportacao(data) {
    porId('previewArea').style.display = 'block';
    porId('previewStats').textContent =
        `${data.total_alunos} alunos • ${data.total_turmas} turmas${data.arquivo ? ` • ${data.arquivo}` : ''}`;
    const linhaCabecalho = porId('previewTable').querySelector('thead tr');
    const corpo = porId('previewTable').querySelector('tbody');
    limpar(linhaCabecalho);
    limpar(corpo);
    ['Nome', 'Turma', 'Curso', 'Código', 'Situação'].forEach(nome => {
        linhaCabecalho.appendChild(criar('th', nome));
    });
    (data.preview || []).forEach(aluno => {
        const linha = document.createElement('tr');
        [aluno.nome, aluno.turma, aluno.curso, aluno.codigo || aluno.matricula || '—'].forEach(valor => {
            linha.appendChild(criar('td', valor || '—'));
        });
        linha.appendChild(criar('td', `${aluno.tem_foto ? '📷' : '👤'} ${aluno.tem_qr ? '▣' : '—'}`));
        corpo.appendChild(linha);
    });
}

function aplicarAlunos(data) {
    STATE.alunos = data.alunos || data.preview || [];
    STATE.turmas = data.turmas || STATE.alunos.reduce((grupos, aluno) => {
        grupos[aluno.turma] = (grupos[aluno.turma] || 0) + 1;
        return grupos;
    }, {});
    STATE.planilhaCarregada = STATE.alunos.length > 0;
    STATE.alunosSelecionados.clear();
    porId('badge-alunos').textContent = String(STATE.alunos.length);
    porId('stat-alunos').textContent = String(STATE.alunos.length);
    porId('stat-turmas').textContent = String(Object.keys(STATE.turmas).length);
    porId('stat-planilha').textContent = STATE.planilhaCarregada ? '✅' : '—';
    preencherFiltrosTurma();
    carregarPreviewAlunos();
}

async function carregarEstadoAtivo() {
    try {
        const data = await API.get('/api/alunos');
        aplicarAlunos(data);
    } catch (erro) {
        console.error('Falha ao restaurar o estado ativo:', erro);
    }
}

async function carregarDadosIEMA() {
    try {
        mostrarToast('Carregando a planilha padrão do IEMA...', 'info');
        const data = await API.post('/api/planilha-padrao');
        const estadoCompleto = await API.get('/api/alunos');
        aplicarAlunos(estadoCompleto);
        montarPreviewImportacao(data);
        mudarAba('alunos');
        mostrarToast(`${data.total_alunos} alunos carregados.`, 'success');
    } catch (erro) {
        mostrarToast(erro.message, 'error');
    }
}

async function processarArquivo(arquivo) {
    if (!arquivo) return;
    const form = new FormData();
    form.append('arquivo', arquivo);
    try {
        mostrarToast('Lendo a planilha...', 'info');
        const data = await API.upload('/api/planilha/colunas', form);
        STATE.importacaoPendente = data.upload_id;
        montarPreviewImportacao(data);
        porId('btnConfirmarImportacao').disabled = false;
        mostrarToast(`${data.total_alunos} alunos encontrados. Confirme para ativar.`, 'success');
    } catch (erro) {
        mostrarToast(erro.message, 'error');
    }
}

async function confirmarImportacao() {
    if (!STATE.importacaoPendente) {
        mostrarToast('Selecione uma planilha antes de confirmar.', 'error');
        return;
    }
    try {
        const data = await API.post('/api/planilha/confirmar', { upload_id: STATE.importacaoPendente });
        STATE.importacaoPendente = null;
        aplicarAlunos(data);
        porId('previewArea').style.display = 'none';
        porId('fileInput').value = '';
        mudarAba('alunos');
        mostrarToast(`${data.total} alunos importados com sucesso.`, 'success');
    } catch (erro) {
        mostrarToast(erro.message, 'error');
    }
}

async function cancelarImportacao() {
    try {
        if (STATE.importacaoPendente) {
            await API.post('/api/planilha/cancelar', { upload_id: STATE.importacaoPendente });
        }
    } catch (erro) {
        mostrarToast(erro.message, 'error');
        return;
    }
    STATE.importacaoPendente = null;
    porId('previewArea').style.display = 'none';
    porId('fileInput').value = '';
    mostrarToast('Importação cancelada. A planilha ativa foi preservada.', 'info');
}

async function enviarLoteFotos(lote, substituir = false) {
    const form = new FormData();
    lote.forEach(arquivo => form.append('fotos', arquivo));
    if (substituir) form.append('substituir', 'true');
    return API.upload('/api/fotos', form);
}

async function handleFotosSelect(evento) {
    const arquivos = [...evento.target.files];
    if (!arquivos.length) return;
    const botao = porId('btnSelecionarFotos');
    const status = porId('fotosUploadStatus');
    botao.disabled = true;
    let salvas = 0;
    let erros = 0;
    try {
        for (let inicio = 0; inicio < arquivos.length; inicio += 20) {
            const lote = arquivos.slice(inicio, inicio + 20);
            status.textContent = `Enviando ${Math.min(inicio + lote.length, arquivos.length)} de ${arquivos.length}...`;
            try {
                const data = await enviarLoteFotos(lote);
                salvas += data.total_salvas || 0;
                erros += data.erros?.length || 0;
                if (data.conflitos?.length) {
                    const nomes = new Set((data.erros || [])
                        .filter(item => String(item.erro).includes('existe'))
                        .map(item => item.arquivo));
                    const conflitantes = lote.filter(arquivo => nomes.has(arquivo.name));
                    if (conflitantes.length && confirm(`${conflitantes.length} foto(s) já existem. Deseja substituí-las?`)) {
                        const substituidas = await enviarLoteFotos(conflitantes, true);
                        salvas += substituidas.total_salvas || 0;
                        erros -= conflitantes.length;
                        erros += substituidas.erros?.length || 0;
                    }
                }
            } catch (erro) {
                if (erro.status !== 409) throw erro;
                const nomes = new Set((erro.data.erros || [])
                    .filter(item => String(item.erro).includes('existe'))
                    .map(item => item.arquivo));
                const conflitantes = lote.filter(arquivo => nomes.has(arquivo.name));
                if (conflitantes.length && confirm(`${conflitantes.length} foto(s) já existem. Deseja substituí-las?`)) {
                    const data = await enviarLoteFotos(conflitantes, true);
                    salvas += data.total_salvas || 0;
                    erros += data.erros?.length || 0;
                } else {
                    erros += conflitantes.length || lote.length;
                }
            }
        }
        status.textContent = `${salvas} foto(s) importada(s)${erros ? `; ${erros} ignorada(s)` : ''}.`;
        mostrarToast(`${salvas} foto(s) prontas para uso.`, 'success');
    } catch (erro) {
        status.textContent = erro.message;
        mostrarToast(erro.message, 'error');
    } finally {
        botao.disabled = false;
        evento.target.value = '';
    }
}

function alunosVisiveis() {
    const busca = porId('searchAluno').value.trim().toLocaleLowerCase('pt-BR');
    const turma = porId('filterTurma').value;
    return STATE.alunos.filter(aluno => {
        const correspondeTurma = !turma || aluno.turma === turma;
        const texto = `${aluno.nome} ${aluno.codigo || aluno.matricula || ''}`.toLocaleLowerCase('pt-BR');
        return correspondeTurma && (!busca || texto.includes(busca));
    });
}

function renderizarAlunos() {
    const corpo = porId('alunosBody');
    limpar(corpo);
    const alunos = alunosVisiveis();
    if (!alunos.length) {
        const linha = document.createElement('tr');
        const celula = criar('td', 'Nenhum aluno encontrado.', 'estado-tabela-vazia');
        celula.colSpan = 6;
        linha.appendChild(celula);
        corpo.appendChild(linha);
    }
    alunos.forEach(aluno => {
        const codigo = String(aluno.codigo || aluno.matricula || '');
        const linha = document.createElement('tr');
        const selecao = document.createElement('input');
        selecao.type = 'checkbox';
        selecao.className = 'aluno-check';
        selecao.value = codigo;
        selecao.checked = STATE.alunosSelecionados.has(codigo);
        selecao.setAttribute('aria-label', `Selecionar ${aluno.nome}`);
        selecao.addEventListener('change', () => {
            if (selecao.checked) STATE.alunosSelecionados.add(codigo);
            else STATE.alunosSelecionados.delete(codigo);
            atualizarGerarInfo();
        });
        const celulaSelecao = document.createElement('td');
        celulaSelecao.appendChild(selecao);
        linha.appendChild(celulaSelecao);
        const nome = document.createElement('td');
        nome.appendChild(criar('strong', aluno.nome));
        linha.appendChild(nome);
        [aluno.turma, aluno.curso, codigo || '—'].forEach(valor => linha.appendChild(criar('td', valor || '—')));
        const acao = document.createElement('td');
        const botao = criar('button', '👁️', 'btn btn-outline btn-icon');
        botao.type = 'button';
        botao.setAttribute('aria-label', `Visualizar crachá de ${aluno.nome}`);
        botao.addEventListener('click', () => previewAlunoEspecifico(codigo));
        acao.appendChild(botao);
        linha.appendChild(acao);
        corpo.appendChild(linha);
    });
    porId('alunosCount').textContent = `${alunos.length} aluno(s)`;
    porId('selectAll').checked = alunos.length > 0 && alunos.every(a =>
        STATE.alunosSelecionados.has(String(a.codigo || a.matricula || '')));
    atualizarGerarInfo();
}

function selecionarTodos() {
    const marcar = porId('selectAll').checked;
    alunosVisiveis().forEach(aluno => {
        const codigo = String(aluno.codigo || aluno.matricula || '');
        if (marcar) STATE.alunosSelecionados.add(codigo);
        else STATE.alunosSelecionados.delete(codigo);
    });
    renderizarAlunos();
}

function preencherSelectTurmas(select, primeiroRotulo) {
    const atual = select.value;
    limpar(select);
    select.add(new Option(primeiroRotulo, ''));
    const turmas = [...new Set(STATE.alunos.map(a => a.turma).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b, 'pt-BR', { numeric: true }));
    turmas.forEach(turma => select.add(new Option(turma, turma)));
    select.value = turmas.includes(atual) ? atual : '';
}

function alunosDaTurmaGeracao() {
    const turma = porId('gerarTurma').value;
    const alunos = turma ? STATE.alunos.filter(a => a.turma === turma) : [...STATE.alunos];
    return alunos.sort((a, b) => String(a.nome).localeCompare(String(b.nome), 'pt-BR'));
}

function preencherSelectAlunosGeracao() {
    const select = porId('gerarAluno');
    const atual = select.value;
    const turma = porId('gerarTurma').value;
    const alunos = alunosDaTurmaGeracao();
    limpar(select);
    select.add(new Option(turma ? 'Todos os alunos da turma' : 'Todos os alunos', ''));
    alunos.forEach(aluno => {
        const codigo = String(aluno.codigo || aluno.matricula || '');
        const rotulo = turma ? aluno.nome : `${aluno.nome} - ${aluno.turma || 'Sem turma'}`;
        select.add(new Option(rotulo, codigo));
    });
    select.value = alunos.some(aluno => String(aluno.codigo || aluno.matricula || '') === atual) ? atual : '';
    select.disabled = !alunos.length;
}

function preencherFiltrosTurma() {
    preencherSelectTurmas(porId('filterTurma'), 'Todas as turmas');
    preencherSelectTurmas(porId('gerarTurma'), 'Todas as turmas');
    preencherSelectAlunosGeracao();
}

function alunosParaGerar() {
    const turma = porId('gerarTurma').value;
    const alunoSelecionado = porId('gerarAluno').value;
    let alunos = turma ? STATE.alunos.filter(a => a.turma === turma) : [...STATE.alunos];
    if (alunoSelecionado) {
        alunos = alunos.filter(a => String(a.codigo || a.matricula || '') === alunoSelecionado);
    } else if (STATE.alunosSelecionados.size) {
        alunos = alunos.filter(a => STATE.alunosSelecionados.has(String(a.codigo || a.matricula || '')));
    }
    return alunos;
}

function atualizarGerarInfo() {
    const alunos = alunosParaGerar();
    const turma = porId('gerarTurma').value;
    const totalTurma = alunosDaTurmaGeracao().length;
    const alunoSelecionado = porId('gerarAluno').value;
    porId('gerar-total').textContent = String(alunos.length);
    porId('btnGerar').textContent = alunoSelecionado ? '🚀 GERAR CRACHÁ DO ALUNO' : '🚀 GERAR CRACHÁS';
    const pdf = porId('btnPdfTurma');
    pdf.disabled = !turma || !totalTurma;
    pdf.title = pdf.disabled ? 'Selecione uma turma com alunos' : `Exportar a turma ${turma}`;
    const localizar = porId('btnLocalizarAluno');
    localizar.disabled = !alunoSelecionado;
    localizar.title = alunoSelecionado ? 'Localizar somente este aluno' : 'Selecione um aluno para localizar';
}

let requisicaoCrachasTurma = 0;
async function carregarCrachasDaTurma() {
    const turma = porId('gerarTurma').value;
    const codigoLocalizado = STATE.alunoLocalizadoCodigo;
    const alunoLocalizado = codigoLocalizado
        ? STATE.alunos.find(a => String(a.codigo || a.matricula || '') === codigoLocalizado)
        : null;
    const conteudo = porId('crachasFiltradosConteudo');
    const titulo = porId('crachasFiltradosTitulo');
    const contador = porId('crachasFiltradosTotal');
    const numero = ++requisicaoCrachasTurma;
    const botaoArquivar = porId('btnArquivarObsoletos');
    botaoArquivar.disabled = true;
    limpar(conteudo);
    contador.textContent = '';
    if (!turma && !alunoLocalizado) {
        titulo.textContent = 'Crachás gerados por turma';
        conteudo.className = 'crachas-estado-vazio';
        conteudo.textContent = 'Selecione uma turma para visualizar os crachás já gerados.';
        return;
    }
    titulo.textContent = alunoLocalizado
        ? `Cracha localizado - ${alunoLocalizado.nome}`
        : `Crachas gerados - turma ${turma}`;
    conteudo.className = 'crachas-estado-vazio';
    conteudo.textContent = 'Carregando crachás...';
    try {
        const parametros = new URLSearchParams();
        if (turma) parametros.set('turma', turma);
        if (codigoLocalizado) parametros.set('codigo', codigoLocalizado);
        const data = await API.get(`/api/crachas?${parametros.toString()}`);
        if (numero !== requisicaoCrachasTurma) return;
        const crachas = data.crachas || [];
        if (turma && !codigoLocalizado) {
            const reconciliacao = await API.get(`/api/reconciliacao?turma=${encodeURIComponent(turma)}`);
            if (numero !== requisicaoCrachasTurma) return;
            botaoArquivar.disabled = !reconciliacao.total_obsoletos;
            botaoArquivar.title = reconciliacao.total_obsoletos
                ? `Arquivar ${reconciliacao.total_obsoletos} arquivo(s) que não pertencem à turma ativa`
                : 'Nenhum arquivo obsoleto encontrado';
        } else {
            botaoArquivar.disabled = true;
            botaoArquivar.title = codigoLocalizado
                ? 'Arquivamento disponível somente na visão da turma'
                : 'Selecione uma turma com arquivos obsoletos';
        }
        contador.textContent = `${crachas.length} crachá(s)`;
        limpar(conteudo);
        if (!crachas.length) {
            conteudo.className = 'crachas-estado-vazio crachas-estado-aviso';
            conteudo.append(
                criar('strong', alunoLocalizado
                    ? `Nenhum cracha foi gerado para ${alunoLocalizado.nome}.`
                    : `Nenhum cracha foi gerado para a turma ${turma}.`),
                criar('span', 'Use Gerar Crachas para criar os arquivos.')
            );
            return;
        }
        conteudo.className = 'crachas-galeria';
        crachas.forEach(cracha => {
            const link = document.createElement('a');
            link.className = 'cracha-galeria-item';
            link.href = cracha.url;
            link.target = '_blank';
            link.rel = 'noopener';
            const visual = criar('div', '', 'cracha-galeria-preview');
            if (['png', 'jpg', 'jpeg'].includes(String(cracha.formato).toLowerCase())) {
                const imagem = document.createElement('img');
                imagem.src = `${cracha.url}?v=${Date.now()}`;
                imagem.alt = `Crachá de ${cracha.nome}`;
                imagem.loading = 'lazy';
                visual.appendChild(imagem);
            } else {
                visual.appendChild(criar('div', `📄 ${String(cracha.formato).toUpperCase()}`, 'cracha-arquivo-icone'));
            }
            link.append(visual, criar('strong', cracha.nome), criar('span',
                `${String(cracha.formato).toUpperCase()} • ${Number(cracha.tamanho_kb || 0).toFixed(1)} KB`));
            conteudo.appendChild(link);
        });
    } catch (erro) {
        if (numero !== requisicaoCrachasTurma) return;
        conteudo.className = 'crachas-estado-vazio crachas-estado-erro';
        conteudo.textContent = `Não foi possível carregar os crachás: ${erro.message}`;
    }
}

async function arquivarObsoletos() {
    const turma = porId('gerarTurma').value;
    if (!turma) return;
    if (!confirm(`Arquivar os arquivos obsoletos da turma ${turma}? Eles permanecerão no disco para recuperação.`)) return;
    try {
        const data = await API.post('/api/arquivar-obsoletos', { turma });
        mostrarToast(`${data.total} arquivo(s) movido(s) para o arquivo histórico.`, 'success');
        await carregarCrachasDaTurma();
    } catch (erro) {
        mostrarToast(erro.message, 'error');
    }
}

function carregarFiltroGeracao() {
    preencherFiltrosTurma();
    atualizarGerarInfo();
    carregarCrachasDaTurma();
}

function filtrarGeracaoPorTurma() {
    STATE.alunoLocalizadoCodigo = '';
    preencherSelectAlunosGeracao();
    atualizarGerarInfo();
    porId('resultadoGeracao').style.display = 'none';
    carregarCrachasDaTurma();
}

function filtrarGeracaoPorAluno() {
    STATE.alunoLocalizadoCodigo = '';
    atualizarGerarInfo();
    porId('resultadoGeracao').style.display = 'none';
    carregarCrachasDaTurma();
}

function localizarAlunoGeracao() {
    const codigo = porId('gerarAluno').value;
    if (!codigo) {
        mostrarToast('Selecione um aluno para localizar.', 'error');
        return;
    }
    const aluno = STATE.alunos.find(a => String(a.codigo || a.matricula || '') === codigo);
    if (!aluno) {
        mostrarToast('Aluno nao encontrado na base carregada.', 'error');
        return;
    }
    if (aluno.turma && porId('gerarTurma').value !== aluno.turma) {
        porId('gerarTurma').value = aluno.turma;
        preencherSelectAlunosGeracao();
        porId('gerarAluno').value = codigo;
    }
    STATE.alunoLocalizadoCodigo = codigo;
    atualizarGerarInfo();
    porId('resultadoGeracao').style.display = 'none';
    carregarCrachasDaTurma();
    mostrarToast(`Aluno localizado: ${aluno.nome}.`, 'success');
}

function mudarFormato(input) {
    STATE.formato = input.value;
    document.querySelectorAll('.radio-card').forEach(card => card.classList.toggle('selected', card.contains(input)));
    porId('gerar-formato').textContent = input.value.toUpperCase();
}

function atualizarOpcoesCracha() {
    STATE.mostrarFoto = porId('mostrarFoto').checked;
    STATE.mostrarQR = porId('mostrarQR').checked;
}

function montarResultadoGeracao(data) {
    const caixa = criar('div', '', 'card');
    caixa.style.borderColor = data.total_erros ? 'var(--warning)' : 'var(--success)';
    const cabecalho = criar('div', '', 'card-header');
    cabecalho.appendChild(criar('h3',
        data.total_erros ? `⚠️ ${data.total_gerados} gerados, ${data.total_erros} erro(s)`
            : `✅ ${data.total_gerados} crachá(s) gerado(s)`));
    const corpo = criar('div', '', 'card-body');
    const caminho = criar('p');
    caminho.append('Pasta: ', criar('code', data.pasta_saida));
    corpo.appendChild(caminho);
    const grade = criar('div', '', 'result-grid');
    (data.resultados || []).forEach(item => {
        const bloco = criar('div', '', 'result-item');
        bloco.append(criar('span', item.nome, 'nome'),
            criar('span', `${Number(item.tamanho_kb || 0).toFixed(1)} KB • ${String(item.formato).toUpperCase()}`, 'meta'));
        grade.appendChild(bloco);
    });
    corpo.appendChild(grade);
    if (data.erros?.length) {
        const lista = criar('ul', '', 'texto-erro');
        data.erros.forEach(item => lista.appendChild(criar('li', `${item.nome}: ${item.erro}`)));
        corpo.appendChild(lista);
    }
    caixa.append(cabecalho, corpo);
    const resultado = porId('resultadoGeracao');
    limpar(resultado);
    resultado.appendChild(caixa);
    resultado.style.display = 'block';
}

async function gerarCrachas() {
    const alunos = alunosParaGerar();
    if (!alunos.length) {
        mostrarToast('Nenhum aluno corresponde ao filtro selecionado.', 'error');
        return;
    }
    const botao = porId('btnGerar');
    const barra = porId('progressFill');
    botao.disabled = true;
    botao.textContent = 'Gerando...';
    porId('progressContainer').style.display = 'block';
    barra.classList.add('indeterminate');
    barra.style.width = '35%';
    porId('progressText').textContent = `Gerando ${alunos.length} crachá(s)...`;
    try {
        const data = await API.post('/api/gerar', {
            formato: STATE.formato,
            mostrar_foto: STATE.mostrarFoto,
            mostrar_qr: STATE.mostrarQR,
            turma: porId('gerarTurma').value,
            codigos: alunos.map(a => String(a.codigo || a.matricula || '')),
        });
        barra.classList.remove('indeterminate');
        barra.style.width = '100%';
        porId('progressText').textContent = 'Concluído.';
        montarResultadoGeracao(data);
        mostrarToast(`${data.total_gerados} crachá(s) gerado(s).`, data.total_erros ? 'warning' : 'success');
        await Promise.all([carregarDashboard(), carregarCrachasDaTurma()]);
    } catch (erro) {
        barra.classList.remove('indeterminate');
        barra.style.width = '0';
        porId('progressText').textContent = 'Falha na geração.';
        mostrarToast(erro.message, 'error');
    } finally {
        botao.disabled = false;
        atualizarGerarInfo();
    }
}

async function exportarPdfTurma() {
    const turma = porId('gerarTurma').value;
    if (!turma) {
        mostrarToast('Selecione uma turma específica para exportar.', 'error');
        return;
    }
    const botao = porId('btnPdfTurma');
    botao.disabled = true;
    botao.textContent = 'Montando PDF...';
    try {
        const data = await API.post('/api/exportar-pdf-turma', {
            turma,
            mostrar_foto: STATE.mostrarFoto,
            mostrar_qr: STATE.mostrarQR,
        });
        const link = document.createElement('a');
        link.href = data.download_url;
        link.download = data.nome_arquivo;
        document.body.appendChild(link);
        link.click();
        link.remove();
        mostrarToast(`PDF da turma ${turma} gerado com ${data.total_crachas} crachá(s).`, 'success');
    } catch (erro) {
        mostrarToast(erro.message, 'error');
    } finally {
        botao.textContent = '📄 EXPORTAR PDF DA TURMA';
        atualizarGerarInfo();
    }
}

async function baixarPngsPorTurma() {
    const turma = porId('gerarTurma').value;
    const botao = porId('btnPngsTurmas');
    botao.disabled = true;
    botao.textContent = 'Montando ZIP...';
    try {
        const data = await API.post('/api/exportar-pngs-turmas', {
            turma,
            mostrar_foto: STATE.mostrarFoto,
            mostrar_qr: STATE.mostrarQR,
        });
        const link = document.createElement('a');
        link.href = data.download_url;
        link.download = data.nome_arquivo;
        document.body.appendChild(link);
        link.click();
        link.remove();
        const alvo = turma ? `turma ${turma}` : 'todas as turmas';
        mostrarToast(`${data.total_gerados} PNG(s) preparados para ${alvo}.`, data.total_erros ? 'warning' : 'success');
        await Promise.all([carregarDashboard(), carregarCrachasDaTurma()]);
    } catch (erro) {
        mostrarToast(erro.message, 'error');
    } finally {
        botao.textContent = 'BAIXAR PNGS POR TURMA';
        botao.disabled = false;
    }
}

function carregarPreviewAlunos() {
    const select = porId('previewAluno');
    const atual = select.value;
    limpar(select);
    select.add(new Option(STATE.alunos.length ? 'Selecione um aluno' : 'Nenhum aluno carregado', ''));
    STATE.alunos.forEach(aluno => {
        const codigo = String(aluno.codigo || aluno.matricula || '');
        select.add(new Option(`${aluno.nome} — ${aluno.turma}`, codigo));
    });
    if ([...select.options].some(opcao => opcao.value === atual)) select.value = atual;
}

function previewAlunoEspecifico(codigo) {
    mudarAba('visualizar');
    porId('previewAluno').value = codigo;
    gerarPreview();
}

async function gerarPreview() {
    const codigo = porId('previewAluno').value;
    if (!codigo) return;
    try {
        const data = await API.post('/api/gerar/preview', {
            codigo,
            mostrar_foto: STATE.mostrarFoto,
            mostrar_qr: STATE.mostrarQR,
        });
        porId('previewPlaceholder').style.display = 'none';
        porId('previewCracha').style.display = 'block';
        porId('previewImagem').src = data.imagem;
        porId('previewImagem').alt = `Preview do crachá de ${data.nome}`;
    } catch (erro) {
        mostrarToast(erro.message, 'error');
    }
}

function adicionarLinhaDiagnostico(lista, rotulo, valor) {
    const item = document.createElement('li');
    item.append(criar('strong', `${rotulo}: `), document.createTextNode(String(valor)));
    lista.appendChild(item);
}

async function abrirDiagnostico() {
    try {
        const data = await API.get('/api/diagnostico');
        const painel = criar('div', '', 'diagnostico');
        const lista = document.createElement('ul');
        adicionarLinhaDiagnostico(lista, 'Alunos ativos', data.total_alunos || 0);
        adicionarLinhaDiagnostico(lista, 'Turmas', data.total_turmas || data.turmas?.length || 0);
        adicionarLinhaDiagnostico(lista, 'Crachás gerados', data.total_crachas || 0);
        adicionarLinhaDiagnostico(lista, 'Crachás ausentes', data.total_faltantes || 0);
        adicionarLinhaDiagnostico(lista, 'Arquivos obsoletos', data.total_obsoletos || 0);
        painel.appendChild(lista);
        const ausentesEncontrados = (data.reconciliacao || []).flatMap(item =>
            (item.faltantes || []).map(aluno => ({ ...aluno, turma: item.turma })));
        if (ausentesEncontrados.length) {
            painel.appendChild(criar('h4', 'Crachás ausentes'));
            const ausentes = document.createElement('ul');
            ausentesEncontrados.slice(0, 30).forEach(item =>
                ausentes.appendChild(criar('li', `${item.codigo} — ${item.nome} (${item.turma})`)));
            painel.appendChild(ausentes);
        }
        abrirModal('Diagnóstico do Sistema', painel);
    } catch (erro) {
        mostrarToast(erro.message, 'error');
    }
}

async function fazerBackup() {
    try {
        const incluirGerados = confirm('Deseja incluir também os crachás e PDFs gerados?');
        const data = await API.post('/api/backup', { incluir_gerados: incluirGerados });
        const valido = data.validacao?.valido !== false;
        mostrarToast(valido ? `Backup validado: ${data.nome || data.caminho}` : 'O backup falhou na validação.', valido ? 'success' : 'error');
    } catch (erro) {
        mostrarToast(erro.message, 'error');
    }
}

async function baixarExemplo() {
    try {
        const resposta = await fetch('/api/baixar-exemplo');
        if (!resposta.ok) throw new Error('Não foi possível baixar o modelo.');
        const blob = await resposta.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'modelo_alunos.xlsx';
        link.click();
        URL.revokeObjectURL(url);
    } catch (erro) {
        mostrarToast(erro.message, 'error');
    }
}

async function carregarDashboard() {
    try {
        const data = await API.get('/api/diagnostico');
        porId('stat-alunos').textContent = String(data.total_alunos ?? STATE.alunos.length);
        porId('stat-turmas').textContent = String(data.total_turmas ?? Object.keys(STATE.turmas).length);
        porId('stat-gerados').textContent = String(data.total_crachas || 0);
        porId('stat-planilha').textContent = data.planilha?.carregada || STATE.planilhaCarregada ? '✅' : '—';
        const container = porId('ultimos-crachas');
        limpar(container);
        const recentes = (data.crachas_montados || []).slice(-8).reverse();
        if (!recentes.length) {
            container.appendChild(criar('p', 'Nenhum crachá gerado ainda.', 'text-muted'));
            return;
        }
        const grade = criar('div', '', 'result-grid');
        recentes.forEach(cracha => {
            const item = criar('div', '', 'result-item');
            item.append(criar('span', cracha.nome, 'nome'),
                criar('span', `${cracha.turma} • ${Number(cracha.tamanho_kb || 0).toFixed(1)} KB`, 'meta'));
            grade.appendChild(item);
        });
        container.appendChild(grade);
    } catch (erro) {
        console.error('Falha ao carregar o dashboard:', erro);
    }
}

async function verificarConexao() {
    try {
        const data = await API.get('/api/health');
        porId('statusIndicator').style.background = 'var(--success)';
        porId('statusText').textContent = `v${data.versao}`;
    } catch {
        porId('statusIndicator').style.background = 'var(--error)';
        porId('statusText').textContent = 'Desconectado';
    }
}

function registrarEventos() {
    document.querySelectorAll('[data-tab], [data-go-tab]').forEach(botao => {
        botao.addEventListener('click', () => mudarAba(botao.dataset.tab || botao.dataset.goTab));
    });
    porId('menuToggle').addEventListener('click', () => atualizarMenuMobile(!porId('sidebar').classList.contains('open')));
    [porId('navCarregarIema'), porId('btnCarregarIemaDashboard')].forEach(el => el.addEventListener('click', carregarDadosIEMA));
    [porId('btnDiagnosticoNav'), porId('btnDiagnosticoDashboard')].forEach(el => el.addEventListener('click', abrirDiagnostico));
    porId('btnBackupNav').addEventListener('click', fazerBackup);
    porId('btnBaixarExemplo').addEventListener('click', baixarExemplo);
    porId('btnSelecionarPlanilha').addEventListener('click', () => porId('fileInput').click());
    porId('fileInput').addEventListener('change', evento => processarArquivo(evento.target.files[0]));
    const zona = porId('uploadZone');
    zona.addEventListener('click', evento => { if (evento.target === zona || evento.target.tagName !== 'BUTTON') porId('fileInput').click(); });
    zona.addEventListener('keydown', evento => {
        if (evento.key === 'Enter' || evento.key === ' ') { evento.preventDefault(); porId('fileInput').click(); }
    });
    ['dragenter', 'dragover'].forEach(tipo => zona.addEventListener(tipo, evento => {
        evento.preventDefault();
        zona.classList.add('drag-over');
    }));
    ['dragleave', 'drop'].forEach(tipo => zona.addEventListener(tipo, evento => {
        evento.preventDefault();
        zona.classList.remove('drag-over');
    }));
    zona.addEventListener('drop', evento => processarArquivo(evento.dataTransfer.files[0]));
    porId('btnConfirmarImportacao').addEventListener('click', confirmarImportacao);
    porId('btnCancelarImportacao').addEventListener('click', cancelarImportacao);
    porId('btnSelecionarFotos').addEventListener('click', () => porId('fotosInput').click());
    porId('fotosInput').addEventListener('change', handleFotosSelect);
    porId('searchAluno').addEventListener('input', renderizarAlunos);
    porId('filterTurma').addEventListener('change', renderizarAlunos);
    porId('selectAll').addEventListener('change', selecionarTodos);
    document.querySelectorAll('input[name="formato"]').forEach(input =>
        input.addEventListener('change', () => mudarFormato(input)));
    [porId('mostrarFoto'), porId('mostrarQR')].forEach(input =>
        input.addEventListener('change', atualizarOpcoesCracha));
    porId('gerarTurma').addEventListener('change', filtrarGeracaoPorTurma);
    porId('gerarAluno').addEventListener('change', filtrarGeracaoPorAluno);
    porId('btnLocalizarAluno').addEventListener('click', localizarAlunoGeracao);
    porId('btnGerar').addEventListener('click', gerarCrachas);
    porId('btnPdfTurma').addEventListener('click', exportarPdfTurma);
    porId('btnPngsTurmas').addEventListener('click', baixarPngsPorTurma);
    porId('btnArquivarObsoletos').addEventListener('click', arquivarObsoletos);
    porId('btnPreview').addEventListener('click', () => {
        const candidato = alunosParaGerar()[0];
        if (!candidato) return mostrarToast('Nenhum aluno disponível para visualizar.', 'error');
        previewAlunoEspecifico(String(candidato.codigo || candidato.matricula || ''));
    });
    porId('previewAluno').addEventListener('change', gerarPreview);
    porId('modalClose').addEventListener('click', fecharModal);
    porId('modalOverlay').addEventListener('click', evento => { if (evento.target === porId('modalOverlay')) fecharModal(); });
    document.addEventListener('keydown', evento => {
        if (evento.key === 'Escape' && !porId('modalOverlay').hidden) fecharModal();
        if (evento.key === 'Tab' && !porId('modalOverlay').hidden) {
            const elementos = [...porId('modalOverlay').querySelectorAll('button, a, input, select, [tabindex]:not([tabindex="-1"])')];
            if (!elementos.length) return;
            const primeiro = elementos[0];
            const ultimo = elementos[elementos.length - 1];
            if (evento.shiftKey && document.activeElement === primeiro) { evento.preventDefault(); ultimo.focus(); }
            else if (!evento.shiftKey && document.activeElement === ultimo) { evento.preventDefault(); primeiro.focus(); }
        }
    });
    window.addEventListener('hashchange', () => mudarAba(location.hash.slice(1) || 'dashboard', false));
    document.addEventListener('click', evento => {
        if (window.innerWidth <= 768 && !porId('sidebar').contains(evento.target) && !porId('menuToggle').contains(evento.target)) {
            atualizarMenuMobile(false);
        }
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    registrarEventos();
    atualizarOpcoesCracha();
    await Promise.all([verificarConexao(), carregarEstadoAtivo()]);
    mudarAba(location.hash.slice(1) || 'dashboard', false);
    setInterval(verificarConexao, 30000);
});
