# Relatório de execução do plano

Data: 23/09/2026  
Versão validada: 2.1.0

## Resultado

- Base ativa: 441 alunos, 441 códigos únicos e 12 turmas.
- Saídas oficiais: 441 crachás PNG, todos nomeados pelo código do aluno.
- Reconciliação: 12 turmas válidas, sem crachá ausente e sem arquivo obsoleto na área ativa.
- Histórico: 440 crachás legados movidos para crachas_montados/_obsoletos.
- QR: 441 de 441 regiões renderizadas conferidas pixel a pixel contra o conteúdo esperado.
- Fotos disponíveis: 73 de 73 regiões renderizadas conferidas pixel a pixel.
- Fotos ausentes na origem: 368 alunos. Esses crachás exibem o marcador FOTO.
- Associação de fotos: 73 pelo código, nenhuma por nome legado e nenhum arquivo compartilhado por alunos diferentes.
- PDF da turma 101: 40 crachás em 4 páginas A4, arquivo criado e validado.
- Testes automatizados: 49 aprovados.

## Mudanças principais

- Código do aluno passou a ser a identidade oficial para seleção, nome do arquivo, QR e manifesto.
- Cada turma possui manifesto.json com código, nome, QR, foto usada e hashes SHA-256.
- Importação de planilha passou a ter estados pendente, confirmar e cancelar.
- A planilha confirmada é restaurada após reiniciar o servidor.
- Códigos são lidos como texto para preservar zeros à esquerda.
- O filtro por turma atualiza a galeria, a contagem e as ações de geração/PDF.
- A listagem usa o manifesto como fonte das saídas oficiais e não duplica arquivos legados.
- Arquivos obsoletos podem ser arquivados pela interface sem exclusão definitiva.
- Backup ZIP passou a incluir manifesto, tamanho e SHA-256 de cada arquivo.
- Backup pode ser validado e extraído em área isolada sem sobrescrever o sistema ativo.
- Conteúdo de planilha deixou de ser inserido como HTML; eventos inline foram removidos.
- Foram adicionados CSP, cabeçalhos de segurança, navegação por hash e melhorias de teclado/foco.
- A opção de cor sem efeito foi removida.
- O servidor recusa exposição fora do computador local sem habilitação explícita.

## Evidências

- Ponto de restauração anterior: backups/ponto_restauracao_antes_plano_20260923_205623.zip
- SHA-256 do ponto de restauração:
  5131778fa0f9ce1fb84a32c81148a29b7cb74d3513a9c572166127254baec089
- Backup posterior validado: backups/backup_cracha_20260923_214939.zip
- Auditoria inicial das fotos: _diag_saida/auditoria_fotos_2026-09-23.json
- Migração das fotos: _diag_saida/migracao_fotos_por_codigo_2026-09-23.json
- Auditoria posterior das fotos: _diag_saida/auditoria_fotos_pos_migracao_2026-09-23.json
- Migração das saídas: _diag_saida/relatorio_migracao_saidas_2026-09-23.json
- Validação dos pixels: _diag_saida/validacao_pixels_qr_fotos_2026-09-23.json

## Estado do servidor

O servidor foi reiniciado e respondeu em http://127.0.0.1:5000 com versão 2.1.0,
441 alunos, 441 crachás e 12 turmas reconciliadas.
