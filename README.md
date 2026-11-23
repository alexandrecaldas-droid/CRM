# Sistema de Cadastro, Controle e Acompanhamento de Leads

Sistema web para a equipe comercial cadastrar leads, conduzi-los pelo funil de vendas e acompanhar cada contato até o fechamento ou a perda — sem planilhas paralelas.

- **Interface**: React + TypeScript (SPA responsiva, pt-BR, acessível por teclado, tema claro/escuro automático).
- **API**: Python 3.12 + FastAPI, documentação OpenAPI em `/api/docs`.
- **Banco**: PostgreSQL 16 com migrações versionadas (Alembic).
- **Worker**: processo separado para importações, envio de e-mails/lembretes e leitura da caixa IMAP.
- **Entrega**: Docker Compose (API, worker, banco, HTTPS via Caddy, backup diário).

Manual de uso por perfil: [`docs/MANUAL.md`](docs/MANUAL.md).

---

## Subir com um comando

Pré-requisitos: Docker e Docker Compose no servidor local da empresa.

```bash
cp .env.example .env        # ajuste senhas, domínio e SMTP
docker compose up -d --build
```

Acesse `https://localhost` (ou o domínio configurado em `DOMINIO`). No primeiro acesso entre com `SEED_ADMIN_EMAIL` / `SEED_ADMIN_SENHA` e **troque a senha** em *Meu perfil*.

Dados de exemplo (usuários fictícios e 60 leads), para demonstração:

```bash
docker compose exec api python -m app.seed --exemplo
```

Usuários de exemplo: `gestor@`, `valeria@`, `victor@`, `vanessa@` e `leitura@tenti.com.br`, senha `Senha@123`.

Para desenvolvimento com uma caixa de e-mail de teste (Mailpit em `http://localhost:8025`):

```bash
docker compose --profile dev up -d --build
```

e no `.env`: `SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_TLS=nenhum`.

### Desenvolvimento sem Docker

```bash
# API (usa SQLite se DATABASE_URL não for definido)
cd backend
pip install -r requirements-dev.txt
alembic upgrade head && python -m app.seed --exemplo
uvicorn app.main:app --reload          # http://localhost:8000/api/docs
python -m app.worker                    # em outro terminal

# Interface
cd frontend
npm install
npm run dev                             # http://localhost:5173 (proxy para a API)
```

### Testes e lint

```bash
cd backend && ruff check . && pytest -q                 # 65 testes (SQLite)
DATABASE_URL=postgresql+psycopg://... pytest -q         # mesmos testes no PostgreSQL
cd frontend && npm run lint && npm test && npm run build
```

O CI (`.github/workflows/ci.yml`) roda lint, os testes em SQLite **e** PostgreSQL, verifica as migrações do zero e compila a interface.

---

## Variáveis de ambiente

Todas em `.env` (modelo em `.env.example`). Credenciais **nunca** ficam no código.

| Variável | Para quê | Padrão |
|---|---|---|
| `DOMINIO` / `APP_URL` | Domínio do HTTPS e base dos links enviados por e-mail | `localhost` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Banco | — (senha obrigatória) |
| `SECRET_KEY` | Reservada para assinaturas | — |
| `SESSAO_HORAS` | Validade do token de sessão | 12 |
| `LOGIN_MAX_TENTATIVAS` / `LOGIN_JANELA_MIN` | Bloqueio após falhas de login | 5 em 15 min |
| `PUBLIC_RATE_LIMIT_MIN` | Limite de envios por minuto por chave de API | 30 |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_SENHA` | Primeiro administrador (só se não houver nenhum) | — |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_TLS` (`starttls`/`ssl`/`nenhum`), `SMTP_USUARIO`, `SMTP_SENHA` | Envio por comercial@tenti.com.br | vazio = só registra em log |
| `EMAIL_REMETENTE` / `EMAIL_REMETENTE_NOME` | Remetente | comercial@tenti.com.br |
| `IMAP_HOST`, `IMAP_PORT`, `IMAP_USUARIO`, `IMAP_SENHA`, `IMAP_PASTA`, `IMAP_INTERVALO_SEG` | Leitura da caixa (Fase 3) | vazio = desativado |
| `MAX_UPLOAD_MB` | Limite por anexo | 10 |
| `BACKUP_DIR` / `BACKUP_HORA` / `BACKUP_RETENCAO_DIAS` | Backup diário | `./backups`, 02h, 30 dias |
| `APP_TIMEZONE` | Fuso para "hoje", relatórios e lembretes | America/Sao_Paulo |

---

## Backup e restauração

O serviço `backup` gera diariamente `banco_AAAA-MM-DD_HHMM.dump` (pg_dump) e `anexos_*.tar.gz` em `BACKUP_DIR`, valida o dump com `pg_restore -l` e apaga arquivos com mais de 30 dias.

- Backup imediato: `docker compose exec backup sh /backup.sh agora`
- Restaurar: `docker compose stop api worker && sh infra/restaurar.sh backups/banco_X.dump backups/anexos_X.tar.gz && docker compose up -d`

> **Responsabilidade do administrador:** copiar a pasta de backups para fora do servidor (disco externo ou nuvem) e testar a restauração periodicamente. O procedimento foi testado durante o desenvolvimento (dump → restauração em banco novo → contagem de leads confere).

---

## Arquitetura

```
Navegador (SPA)  ─┐                     ┌─> PostgreSQL (leads, histórico, auditoria)
                  ├─> Caddy (HTTPS) ─> API REST ─┼─> Disco (anexos até 10 MB)
Site/formulários ─┘   regras, permissões,  └─> tabela job ─> Worker ─> SMTP/IMAP comercial@tenti.com.br
                      auditoria                              (importação, lembretes, e-mails)
```

- `backend/app/models.py` — 11 entidades da especificação + tabelas de apoio (sessão, notificação, job, importação, chave de API, modelo de e-mail, regra de atribuição, visão salva, configuração).
- `backend/app/servicos.py` — regras de negócio (duplicidade, funil, rodízio, filtros, indicadores).
- `backend/app/routers/` — rotas da seção 6 (`/auth`, `/leads`, `/tarefas`, `/importacoes`, `/public/leads`, `/relatorios`, `/exportacoes`, CRUDs de administração, `/auditoria`, `/lgpd`).
- `backend/app/worker.py` — fila, lembretes, leitura IMAP.
- `frontend/src/pages/` — Painel, Leads (quadro/lista), Detalhe do lead, Tarefas, Relatórios, Importar, Administração, Perfil.

Todo acesso passa pela API, que checa a permissão no servidor em cada rota. Um vendedor que tenta abrir lead de outro recebe **404** (não 403), para não revelar a existência do registro.

---

## Decisões técnicas

A especificação pede que, na ambiguidade, se escolha a opção mais simples e se registre aqui.

| Tema | Decisão | Motivo |
|---|---|---|
| Stack da API | **FastAPI** (uma das opções sugeridas) | OpenAPI gerada automaticamente, validação forte com Pydantic, pouco código. |
| Fila | **Tabela `job` no PostgreSQL** + worker com `SELECT … FOR UPDATE SKIP LOCKED`, sem Redis | Volume de 30 leads/mês; a especificação diz "Redis opcional". Um componente a menos para manter. |
| Arquivos | Disco do servidor (volume Docker) | Opção mais simples listada; MinIO pode ser adotado depois sem mudar o modelo. |
| Sessão | Token opaco aleatório, guardado como hash SHA-256 no banco, enviado em `Authorization: Bearer` | Permite revogar (logout, troca de senha, desativação). Por não usar cookie, não há superfície de CSRF. |
| Senhas | Argon2id; mínimo 8 caracteres com letras e números | Requisito de hash forte. |
| Bloqueio de login | 5 falhas por e-mail em 15 min → 429 | "Limite de tentativas de login". |
| 2FA | TOTP (aplicativo autenticador), opcional por usuário; admin pode desativar em caso de perda do celular | "Autenticação em dois fatores opcional". |
| Telefone | Normalizado para E.164 com `phonenumbers`, assumindo Brasil quando sem DDI | Base da detecção de duplicidade. |
| Duplicidade | Mesmo e-mail **ou** telefone em lead não excluído. Cadastro manual devolve 409 com os leads encontrados; o usuário escolhe abrir o existente, mesclar ou "salvar mesmo assim" (`forcar_duplicado`). Se o lead existente for de outro vendedor, o aviso não mostra os dados dele. | "Avisar e oferecer abrir o existente ou mesclar"; "nunca duplicar sem confirmação explícita". |
| Duplicado no webhook / e-mail recebido | Não cria novo lead: registra o novo contato na linha do tempo do lead existente e notifica o responsável | Não há usuário para confirmar; evita duplicidade silenciosa. |
| Permissões do gestor | Vê e **edita** todos os leads, reatribui, exclui (lógico), reabre e exporta. Não gerencia usuários/cadastros | A tabela de perfis não diz se gestor edita; a opção mais simples e útil é sim. |
| Somente leitura | Vê leads e relatórios, **não exporta** | Exportação só foi listada para gestor ("exporta dados"). |
| Vendedor | Leads que cria ficam com ele; vê painel/relatórios só dos próprios leads | "Vê e edita apenas os leads sob sua responsabilidade". |
| Atribuição automática | Regras por origem/UF (por prioridade) e, sem regra, rodízio entre vendedores ativos. Webhook, importação e e-mail recebido sempre usam isso. Sem vendedor ativo, cai para gestor/admin | Seção 3.4. |
| Ganho | Exige valor fechado; data do fechamento padrão hoje, pode ser retroativa (não futura) | "Registrar data e valor fechado". |
| Reabertura | Só gestor/admin; limpa motivo/valor e fica na linha do tempo e auditoria | Seção 3.2. |
| "Lead parado" | Estágio aberto e (último contato, ou criação se nunca houve contato) há mais de N dias (padrão 7) | Seção 3.3. Nota interna **não** conta como contato. |
| "Sem próxima ação" | Lead em estágio aberto sem nenhuma tarefa pendente | Seção 3.3. |
| Conversão por estágio | Coorte de leads criados no período; "chegou ao estágio" = alcançou aquele estágio ou um posterior (exceto Perdido). Conversão geral = ganhos ÷ novos do período | Definição objetiva e estável; documentada na própria tela. |
| Tempo até 1º contato | Da criação até a primeira interação de ligação, e-mail ou reunião | Seção 3.6. |
| Painel = lista | Cada número do painel é calculado pela **mesma função de filtro** da lista, e o cartão leva à lista com os filtros equivalentes. Há teste automatizado que compara | Critério de aceite. |
| Exclusão | Sempre lógica (`excluido_em`); gestor/admin podem excluir; tarefas pendentes são canceladas | "Exclusão lógica" no modelo de dados. |
| LGPD — eliminação | **Anonimização** irreversível (nome, contatos, textos, anexos), preservando números agregados | Atende ao pedido do titular sem quebrar relatórios. |
| Auditoria | Tabela só-inclusão; nenhuma rota edita/exclui; guarda apenas os campos alterados (antes/depois), sem segredos | "Log imutável". |
| Limite do webhook | Janela deslizante de 60 s em memória do processo, por chave | Simples e suficiente no volume previsto; com várias réplicas, o limite vale por réplica. |
| Anexos | Até 10 MB; extensões executáveis/HTML/SVG bloqueadas; download sempre como `attachment` e só para quem pode ver o lead | Segurança (XSS por arquivo). |
| Fuso horário | Banco em UTC; telas, "hoje", relatórios e lembretes em America/Sao_Paulo | Requisito de usabilidade. |
| Busca | `ILIKE` + índices trigram (pg_trgm) em nome, e-mail, empresa e telefone; paginação no servidor | Medido com 100 mil leads: lista e busca entre 0,03 s e 0,35 s (requisito: 2 s). |
| Interface | Componentes próprios + `@dnd-kit` (arrastar e soltar com suporte a teclado e leitor de tela) em vez de uma biblioteca de componentes grande | Menos dependências; controle de contraste/acessibilidade (WCAG 2.1 AA). |

### Fases de entrega

| Fase | Entregue | Verificação automatizada |
|---|---|---|
| 1. Núcleo | Login e perfis, cadastro manual, funil Kanban e lista, histórico de estágios, duplicidade | `tests/test_auth.py`, `tests/test_leads.py` |
| 2. Acompanhamento | Interações e anexos, tarefas/lembretes, atribuição e rodízio, busca e visões salvas, notificações, e-mail pelo lead | `tests/test_acompanhamento.py` |
| 3. Gestão | Importação CSV/XLSX, leitura IMAP, webhook com UTM, painel e relatórios, exportação, auditoria, LGPD | `tests/test_gestao.py` |

Critérios de aceite gerais cobertos por testes: vendedor não acessa lead de outro nem por URL nem pela API; duplicidade nunca sem confirmação; toda mudança aparece na linha do tempo com autor e horário; importação conclui as válidas e devolve relatório das rejeitadas; números do painel batem com a lista; regras de negócio, permissões e fluxos principais passam no CI.

---

## Dúvidas em aberto

Respondidas pelo solicitante na especificação: volume (10 usuários / 30 leads por mês), funil padrão aprovado, integração com e-mail corporativo comercial@tenti.com.br (substitui WhatsApp), hospedagem em servidor local, sem stack obrigatória, base legal = legislação brasileira (LGPD) com o administrador como encarregado.

Ainda pendentes:

1. **Provedor da caixa comercial@tenti.com.br e forma de acesso (SMTP/IMAP com senha de aplicativo ou OAuth).** O sistema foi implementado com SMTP/IMAP por usuário e senha (funciona com senha de aplicativo no Google Workspace e no Microsoft 365, se o SMTP AUTH estiver habilitado). Se o provedor exigir OAuth 2.0, é preciso implementar o fluxo de token — o ponto de troca é `backend/app/emailer.py`.
2. **Prazo e orçamento por fase** — não informados.
3. **Base legal por lead**: o sistema registra a base legal (consentimento, legítimo interesse etc.) e a data do consentimento; o formulário incorporado já pede o aceite. Confirmar com o jurídico qual base usar como padrão para leads importados e se o texto do aceite está adequado à Política de Privacidade da empresa.
4. **Domínio público para o HTTPS**: com um domínio apontado para o servidor, o Caddy emite certificado válido automaticamente. Em rede interna sem domínio, o certificado é interno e os navegadores pedirão para confiar nele uma vez.
