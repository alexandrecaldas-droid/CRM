# Manual de uso — Sistema de Leads

Guia curto para cada perfil. Para instalação, veja o [README](../README.md).

## Para todos

- **Entrar**: e-mail e senha. Após 5 tentativas erradas, o acesso fica bloqueado por 15 minutos. *Esqueci a senha* envia um link válido por 1 hora.
- **Verificação em duas etapas (opcional)**: *Meu perfil* (ícone com suas iniciais) → *Configurar* → escaneie o QR code no Google/Microsoft Authenticator e digite o código.
- **Busca global**: a barra no topo procura por nome, e-mail, telefone ou empresa.
- **Notificações** (sino): novos leads atribuídos a você, tarefas do dia, tarefas atrasadas, e-mails recebidos de leads e importações concluídas. Também chegam por e-mail.
- **No celular**: o sistema funciona no navegador; o menu fica no botão ☰.

## Vendedor

Você vê e edita **apenas os seus leads**.

1. **Cadastrar**: *Leads* → *Novo lead*. Obrigatórios: nome, e-mail **ou** telefone, e origem. Se o contato já existir, o sistema avisa — abra o existente em vez de duplicar. Só use *Salvar mesmo assim* se forem pessoas diferentes.
2. **Mover no funil**: no *Quadro*, arraste o cartão para outro estágio (ou, pelo teclado, foque o cartão, pressione espaço, use as setas e espaço de novo). Na página do lead, clique no estágio desejado.
   - **Ganho** pede o valor fechado e a data.
   - **Perdido** pede o motivo.
   - Lead ganho ou perdido só pode ser reaberto pelo gestor.
3. **Registrar contato**: na página do lead, escolha *Ligação*, *E-mail*, *Reunião* ou *Nota interna*, descreva e clique em *Registrar*. Pode anexar arquivo de até 10 MB.
4. **Enviar e-mail**: botão *Enviar e-mail* → escolha um modelo (os campos como nome e empresa já vêm preenchidos), ajuste e envie. A mensagem sai por comercial@tenti.com.br e fica na linha do tempo.
5. **Próxima ação**: todo lead em aberto precisa de uma tarefa. Leads sem tarefa aparecem com o selo **Sem próxima ação**; use *Agendar agora*.
6. **Tarefas**: menu *Tarefas* mostra *Atrasadas*, *Hoje* e *Próximas*. Marque a caixa para concluir.
7. **Lead parado**: selo vermelho quando não há contato há mais de 7 dias (configurável). Registre uma interação para retomar.
8. **Filtros e visões**: na lista, combine estágio, origem, etiqueta, datas e valor. *Salvar como visão* guarda o filtro com um nome.
9. **Importar planilha**: menu *Importar* → envie CSV/XLSX → confira as colunas → escolha a origem → *Importar*. Linhas com problema voltam em um relatório para download.

## Gestor

Tudo do vendedor, para **todos os leads**, e mais:

- **Painel**: escolha o período e, se quiser, um vendedor. Clique em qualquer indicador para abrir a lista exatamente com aqueles leads.
- **Reatribuir**: na página do lead (*Reatribuir*) ou em lote na *Lista* (marque os leads → *Reatribuir*). Escolha uma pessoa ou *Distribuir por rodízio/regras*.
- **Reabrir** leads ganhos ou perdidos clicando em um estágio aberto.
- **Excluir** lead (exclusão lógica, registrada na auditoria).
- **Relatórios**: por origem, por vendedor (inclui tempo até o 1º contato e tarefas atrasadas), motivos de perda e funil (tempo médio em cada estágio).
- **Exportar**: botão *Exportar* na lista de leads (respeita os filtros aplicados) e *XLSX/CSV* em Relatórios. Toda exportação fica na auditoria.
- **Tarefas da equipe**: em *Tarefas*, alterne para *Equipe*.

## Administrador

Tudo do gestor, e o menu **Administração**:

- **Usuários**: criar, mudar perfil, redefinir senha, desativar (usuários não são excluídos), desativar 2FA de quem perdeu o celular.
- **Funil**: renomear, reordenar (↑ ↓), criar e desativar estágios. Precisa existir ao menos um estágio de cada tipo: aberto, ganho e perdido. Estágios em uso não podem ser excluídos.
- **Origens, Motivos de perda, Etiquetas, Modelos de e-mail**: cadastros simples. Nos modelos, use `{{nome}}`, `{{primeiro_nome}}`, `{{empresa}}`, `{{interesse}}`, `{{vendedor}}`.
- **Atribuição**: liga/desliga a distribuição automática e cria regras (ex.: origem *Evento* → Victor; UF *RS* → Valéria). Regras são avaliadas por prioridade antes do rodízio.
- **Captura (site/webhook)**: gere uma chave de API por site/formulário (a origem do lead vem da chave). Copie o HTML pronto do formulário para o site — ele já envia as UTMs da URL. Revogue chaves que não forem mais usadas.
- **Parâmetros**: dias para considerar lead parado; envio de notificações por e-mail.
- **Auditoria**: quem criou, alterou, exportou, excluiu ou entrou, quando e de qual IP; *Detalhes* mostra antes/depois.
- **LGPD** (você é o encarregado):
  - Localize o titular por e-mail/telefone.
  - Na página do lead, *Exportar dados do titular* gera um arquivo JSON com tudo o que existe sobre a pessoa (acesso/portabilidade).
  - *Anonimizar* apaga de forma irreversível nome, contatos, textos e anexos (eliminação), mantendo apenas números para estatística.
- **Backup**: é automático todo dia às 2h, com 30 dias de retenção. **Copie a pasta `backups` para fora do servidor** regularmente e teste a restauração (instruções no README).

## Somente leitura

Consulta leads, painel e relatórios, sem editar, cadastrar ou exportar.
