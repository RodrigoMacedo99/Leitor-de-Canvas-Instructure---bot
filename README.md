# CBOT — Leitor de Canvas (Instructure) + bot de WhatsApp/Telegram com RAG

Assistente pessoal para alunos do **Canvas (Instructure)**. Com o **token do próprio aluno**, o sistema:

1. **Sincroniza** os cursos em que ele está matriculado, como rotina (a cada 6 h por padrão): baixa arquivos,
   lê páginas, tarefas, quizzes, avisos e o programa, e detecta o que é **novo, alterado ou removido**.
2. **Resume** as novidades e os prazos próximos e envia por **WhatsApp** (Cloud API da Meta) ou **Telegram**.
3. **Responde dúvidas** pelo mesmo canal com **RAG** (busca híbrida pgvector + texto, reranking, citação de
   arquivo e página, recusa quando não há evidência no material).
4. Tem um **painel web** (React) para conectar o Canvas, vincular canais, ver cursos/prazos e testar perguntas.

> Documentação de arquitetura e decisões (ADRs) em [`docs/`](docs/): `arquitetura-CBOT-v0.1.0.docx` e
> `docs/decisions/`.

## Arquitetura em uma olhada

```
Aluno ──WhatsApp/Telegram──► webhook (HTTPS) ──► API FastAPI ──► PostgreSQL 16 + pgvector
                                                      │                 ▲
Canvas (API REST, token do aluno) ◄── Worker (APScheduler + fila SKIP LOCKED) ──► arquivos (volume, por aluno)
                                                      │
                                    Claude (chat/resumo) · Ollama bge-m3 (embeddings locais)
```

- **Backend Python 3.12** (`backend/`), monólito modular com DDD: `src/cbot/modules/<contexto>/{domain,application,infrastructure,interfaces}`.
  Contextos: `alunos`, `canvas` (adaptador do LMS), `conteudo`, `sincronizacao`, `rag`, `chat`, `mensageria`, `resumo`.
  Módulos só conversam por **eventos de domínio** ou pela `public.py` do outro módulo.
- **Padrões usados:** Ports & Adapters (hexagonal), Repository, Unit of Work, Strategy + Registry (coletores do
  Canvas, extratores de texto, chunker, reranker), Observer (barramento de eventos), Command e Chain of
  Responsibility (comandos e pipeline de mensagens), Template Method (canais), Adapter, Factory, Facade, Null
  Object (reranker/contextualizador desligados), Decorator (retry), injeção de dependência manual (`container.py`).
- **PEPs/idioma moderno:** type hints estritos (`mypy --strict`), `Protocol` (PEP 544), `dataclass(slots=True)`,
  `type` aliases e generics (PEP 695), `match` (PEP 634), `StrEnum`, context managers, `ruff` (PEP 8).
- **Frontend** (`frontend/`): React 18 + Vite + React Router.

## Rodando com Docker

```bash
cp .env.example .env     # preencha JWT_SECRET, TOKEN_ENCRYPTION_KEY, DB_PASSWORD (+ canais/IA)
npm run docker:up        # db (pgvector) + backend (migrations + API) + worker + frontend
```

- Painel: http://localhost:5173 (dev) · API: http://localhost:3001 · Docs da API: http://localhost:3001/api/docs
- Embeddings locais: `ollama pull bge-m3` (ou use `EMBEDDING_PROVIDER=hashing` só para experimentar).

## Rodando sem Docker (desenvolvimento)

```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head                                  # precisa de PostgreSQL com a extensão pgvector
uvicorn cbot.main:create_app --factory --reload --port 3001
python -m cbot.worker                                 # em outro terminal: sync, indexação e resumos

# frontend (Node 20+)
cd frontend && npm install && npm run dev
```

## Como conectar tudo

| Passo | Onde |
|---|---|
| Criar conta no painel | `/registro` (desligue `REGISTRO_ABERTO` depois) |
| Token do Canvas | Canvas → Conta → Configurações → **Novo token de acesso**; informe URL + token em *Configurações* |
| Telegram | `@BotFather` → token em `TELEGRAM_BOT_TOKEN`; `setWebhook` para `https://SEU_DOMINIO/api/v1/webhooks/telegram` com `secret_token=TELEGRAM_WEBHOOK_SECRET` |
| WhatsApp | Meta for Developers → app com WhatsApp; webhook em `/api/v1/webhooks/whatsapp` (verify token + app secret); crie o template `resumo_diario` (utilitário) |
| Vincular canal | *Configurações → Vincular canal* gera um código; envie-o ao bot |

Comandos do bot: `/ajuda`, `/cursos`, `/prazos [dias]`, `/resumo`, `/sync`, `/esquecer`. Texto livre = pergunta ao RAG.

> **WhatsApp:** fora da janela de 24 h só é possível enviar *templates* aprovados. O resumo diário então vai como um
> aviso curto e o texto completo é entregue quando o aluno responde (ver ADR-001). O Telegram não tem essa limitação
> e funciona como alternativa quando o WhatsApp não for viável.

## Qualidade (padrões do `.claude/CLAUDE.md`)

```bash
cd backend
ruff check src tests migrations && ruff format --check src tests migrations
mypy src                       # strict
pytest --cov                   # unitários + integração (PostgreSQL real com pgvector; cobertura mínima 80%)
pip-audit --skip-editable

cd ../frontend
npm run lint && npm run format:check && npm test && npm run build && npm run audit
```

Os testes de integração sobem um PostgreSQL embutido (`pgserver`, com pgvector) automaticamente; no CI usam o
serviço `pgvector/pgvector:pg16` via `TEST_DATABASE_URL`.

## Segurança e privacidade (LGPD)

- Token do Canvas **cifrado** (AES-256-GCM) em repouso; senha com bcrypt; JWT no cabeçalho (nunca na URL).
- Webhooks com **assinatura** (HMAC do WhatsApp, `secret_token` do Telegram) e deduplicação por id de mensagem.
- URL do Canvas validada contra SSRF (https obrigatório, sem IP interno); tokens **redigidos** dos logs/erros.
- Todo acesso a dados filtra por `aluno_id`; arquivos ficam em pasta por aluno; o conteúdo recuperado é tratado
  como **dado não confiável** (defesa contra *prompt injection*) e o LLM só tem ferramentas **somente leitura**.
- `/esquecer` (ou `DELETE /api/v1/alunos/me`) apaga dados, vetores e arquivos do aluno.
- Use apenas com a sua conta e respeitando as políticas da sua instituição; o material é de uso pessoal.

## Estrutura

```
backend/   API + worker (Python)      frontend/  painel (React)      infra/docker/  compose (dev e prod)
docs/      arquitetura e ADRs         scripts/   scanner de segredos .github/       CI e CD
```

Fluxo de branches: [`docs/GITFLOW.md`](docs/GITFLOW.md) · commits no padrão Conventional Commits.
Lições de incidentes e convenções de processo herdadas do template: [`docs/TEMPLATE-ORIGINAL.md`](docs/TEMPLATE-ORIGINAL.md).
