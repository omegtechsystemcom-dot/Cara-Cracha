# Auditoria de prontidão para produção

Data: 23/09/2026  
Versão avaliada: 2.1.0  
Escopo: aplicação web, dados ativos, geração de crachás, fotos, QR Codes, PDF, segurança, dependências, backup, operação e implantação.

## Parecer

**O sistema não está pronto para produção em rede nem para a emissão definitiva de todos os crachás.**

Ele está **apto para uso local controlado e homologação em uma única estação**, mantendo o servidor restrito a `127.0.0.1`, por um operador autorizado e com cópia externa dos dados. A geração, o filtro por turma, os QRs e a associação das fotos existentes estão funcionando.

Os bloqueadores são:

1. 368 de 441 alunos ainda não têm foto disponível; esses crachás exibem o marcador `FOTO`.
2. Não há autenticação, autorização ou proteção adequada para exposição em rede. A variável `CRACHA_ALLOW_NETWORK=1` libera a escuta externa sem adicionar essas proteções.
3. O processo usa o servidor de desenvolvimento do Flask e estado global em memória, sem garantias para concorrência ou múltiplos processos.
4. O backup validado não contém o código Python, os scripts de inicialização nem as dependências e o sistema não possui restauração completa para o ambiente ativo.
5. A instalação não é reproduzível: `requirements.txt` usa apenas limites mínimos, sem arquivo de lock ou hashes.

## Evidências aprovadas

| Controle | Resultado |
|---|---:|
| Testes automatizados | 49/49 aprovados |
| Servidor ativo | versão 2.1.0, health `ok` |
| Base ativa | 441 alunos, 12 turmas |
| Crachás reconciliados | 441/441 |
| QR conferido contra o código oficial | 441/441 |
| Fotos disponíveis conferidas pixel a pixel | 73/73 |
| Fotos ausentes na origem | 368 |
| Associação por nome legado | 0 |
| Códigos duplicados na base ativa | 0 |
| Dependências quebradas (`pip check`) | 0 |
| Vulnerabilidades conhecidas (`pip-audit` 2.10.1) | 0 encontradas em 23/09/2026 |
| Backup operacional mais recente | válido, 81 arquivos |
| Reconciliação | 12/12 turmas válidas; 0 faltantes; 0 obsoletos ativos |

O teste de renderização foi repetido durante esta auditoria e retornou `valido: true`, sem erro em QR ou foto existente.

## Achados por prioridade

### P0 — completar as fotos antes da emissão

O sistema encontrou 74 arquivos na área de fotos, dos quais 73 estão associados por código. Há 368 alunos sem foto. A rotina se comporta corretamente e gera um marcador visual, mas o resultado não atende à finalidade de um crachá de identificação com fotografia.

**Critério de liberação:** a auditoria `/api/integridade/fotos` deve indicar 441 associações por código, zero associação legada, zero foto compartilhada indevidamente e zero foto ausente. Depois disso, todos os crachás e PDFs devem ser regenerados e revalidados.

### P0 — impedir exposição de dados e mutações sem controle de acesso

As rotas de alunos, crachás, diagnóstico, importação, geração, backup e arquivamento não exigem login ou perfil. Os crachás e nomes/códigos dos alunos podem ser obtidos diretamente. CORS restringe quais páginas conseguem ler respostas no navegador, mas não substitui autenticação e não protege todos os pedidos de alteração.

O padrão atual de `127.0.0.1` reduz o risco e deve ser mantido na homologação. Para rede ou internet, são necessários autenticação, autorização por função, sessão segura, proteção CSRF, TLS, limite de requisições e registro de auditoria. A opção `CRACHA_ALLOW_NETWORK=1` não deve ser usada antes disso.

**Critério de liberação:** usuário autenticado em todas as rotas com dados pessoais; perfil administrativo para importação, backup e arquivamento; TLS; testes de acesso negado e CSRF.

### P1 — substituir o servidor de desenvolvimento e definir concorrência

`app.run()` é adequado ao desenvolvimento local. O estado ativo e as importações pendentes ficam no dicionário global `app_state`. Em múltiplos workers, cada processo teria uma cópia diferente; em requisições simultâneas, confirmação de planilha, geração, manifesto e arquivamento podem competir pelos mesmos arquivos.

**Critério de liberação:** servidor WSGI suportado no Windows, inicialmente com um único worker; bloqueio explícito para operações mutáveis; persistência do estado fora da memória; testes de duas gerações/importações simultâneas e desligamento durante escrita.

### P1 — tornar backup e restauração completos

O backup operacional inclui planilha, modelo, fotos, dados e frontend, mas não inclui `cracha_extractor`, `requirements.txt`, `main.py` e scripts de inicialização. A função de extração só coloca os arquivos em uma área isolada; ela não executa uma restauração validada do sistema ativo. O arquivo `ponto_restauracao_antes_plano_20260923_205623.zip` é uma cópia de segurança válida para uso manual, porém não segue o manifesto aceito pelo menu.

**Critério de liberação:** documentar RPO/RTO, guardar cópia fora deste computador, incluir versão do código e lock de dependências, implementar ou documentar restauração, e realizar um ensaio em pasta/máquina limpa comprovando abertura da base, fotos, geração e PDF.

### P1 — fixar dependências e formalizar uma versão implantável

As restrições `>=` permitem instalar combinações futuras diferentes das auditadas. `pytest` está misturado às dependências de execução. A pasta `.git` local não contém um repositório válido, portanto esta cópia não oferece rastreabilidade por commit ou tag.

**Critério de liberação:** gerar lock com versões e hashes, separar dependências de produção e desenvolvimento, recriar o ambiente a partir do zero em teste, restaurar o vínculo Git e marcar uma versão imutável.

### P2 — fortalecer disponibilidade e observabilidade

- O logger rotativo existe, mas a inicialização web não chama `configurar_logger`; os eventos da API podem não ser persistidos no arquivo esperado.
- Respostas administrativas revelam caminhos absolutos do computador e algumas exceções internas são devolvidas ao cliente.
- Uploads aceitam até 100 MB por requisição e imagens são verificadas, mas não há limites próprios de dimensões/pixels, quantidade de arquivos ou taxa. Imagens muito grandes podem consumir memória e CPU.
- Não há métricas de duração, fila, espaço em disco, falhas consecutivas ou alerta de backup.
- A CSP ainda permite estilos inline e fontes externas. Isso não bloqueia a homologação local, mas deve ser endurecido numa publicação em rede.

**Critério de liberação:** log estruturado com correlação e retenção; mensagens públicas sem caminhos internos; limites por arquivo/pixels/quantidade; timeouts; monitoramento de saúde, disco e backups; CSP sem `unsafe-inline` quando viável.

## Controles que já estão adequados

- Identificador oficial único baseado no código do aluno.
- QR versionado e ligado ao código e à turma.
- Filtro por turma aplicado pela API e pela interface.
- Nomes de saída por código e manifesto com hashes.
- Importação pendente com confirmação e cancelamento.
- Escrita temporária seguida de substituição para crachás, manifesto e estado.
- Prevenção de travessia de diretório na extração do backup.
- Cabeçalhos CSP, `nosniff`, bloqueio de frame e política de referência.
- Frontend sem `innerHTML` para dados importados e sem handlers inline.
- Exposição em rede bloqueada por padrão.
- Nenhuma vulnerabilidade conhecida encontrada nas versões atualmente instaladas; esse resultado é temporal e deve integrar cada nova liberação.

## Sequência recomendada de liberação

1. Importar e auditar as 368 fotos restantes.
2. Regenerar as 441 imagens e os 12 PDFs e repetir a validação pixel a pixel.
3. Corrigir backup/restauração, dependências e rastreabilidade da versão.
4. Implantar servidor WSGI com um worker e bloqueio de operações mutáveis.
5. Se houver acesso por rede, adicionar autenticação, autorização, CSRF e TLS antes de mudar o bind.
6. Executar ensaio de restauração e teste de aceitação em uma máquina limpa.
7. Liberar a versão apenas quando todos os critérios P0 e P1 estiverem atendidos.

## Decisão de uso atual

| Cenário | Decisão |
|---|---|
| Desenvolvimento e homologação local | **Aprovado com ressalvas** |
| Operação local para completar dados e revisar crachás | **Aprovado** |
| Impressão definitiva dos 441 crachás | **Reprovado enquanto faltarem 368 fotos** |
| Uso por vários operadores na rede | **Reprovado** |
| Publicação na internet | **Reprovado** |

