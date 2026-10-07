> **Arquivo histórico.** Este é o README do template original (stack Node/Knex). A stack do backend foi trocada para Python/FastAPI; as lições de processo e as convenções abaixo continuam valendo (os pontos 1 e 2 — `knexfile.js` e `upload.js` — são específicos da stack antiga, mas a ideia vale para `DATABASE_URL`/`TEST_DATABASE_URL` e limites de upload no nginx).

# Template de Projeto — Monorepo Node.js/Express/Knex + React/Vite

Esqueleto de **processo e qualidade**, extraído de um projeto em produção real. Não tem lógica de negócio nenhuma — é a camada de tooling (CI/CD, hooks, agentes, testes, segurança, Docker) que todo projeto novo, nesta stack, deveria começar já tendo.

## O que tem aqui

```
.claude/
  CLAUDE.md              Padrões de qualidade (código, testes, segurança, CI/CD, observabilidade)
  agents/                14 agentes especializados (requisitos, qualidade, segurança, infra, orquestração)
  skills/                8 skills reutilizáveis (TDD, testes, segurança, auth, CI/CD, API, performance)
  hooks/                 Hooks do Claude Code: bloqueia commit direto em main/develop, lint pós-edição
  settings.json          Liga os hooks acima

.husky/                  Git hooks reais (rodam pra qualquer colaborador, com ou sem Claude Code)
  pre-commit             Scanner de segredos + par teste/código + Prettier + ESLint + testes
  pre-push               audit-ci (dependências vulneráveis) — backend e frontend
  commit-msg             Conventional Commits

.github/workflows/
  ci.yml                 Lint, format, testes (Postgres real via service container), audit, scan de segredos
  cd.yml                 Build + push de imagens Docker, deploy com gate de aprovação manual

docs/
  GITFLOW.md              Modelo de branching (main/develop/feature/release/hotfix)

infra/docker/             docker-compose (dev com hot-reload, prod com imagens do GHCR)
backend/                  package.json, ESLint/Prettier, audit-ci, knexfile.js, tests/setup.js
frontend/                 package.json, ESLint/Prettier, audit-ci, vite.config.js, nginx.conf
scripts/security-scan.js  Scanner de segredos hardcoded (usado no pre-commit e no CI)
```

**De propósito, não tem:** nenhuma rota, componente, model ou tela. `backend/src/` e `frontend/src/` começam vazios (só a config de banco e de build). Você cola o código do projeto novo em cima desta base.

## Como começar um projeto novo a partir daqui

1. Copie esta pasta inteira pro lugar do novo projeto e `git init`.
2. Troque `app`/`app-backend`/`app-frontend`/`OWNER/REPO` pelos nomes reais — aparecem em: `package.json` (3 arquivos), `infra/docker/docker-compose*.yml`, `.env.example`.
3. `cp .env.example .env` e preencha com valores reais (nunca commite o `.env`).
4. `npm install` na raiz, depois em `backend/` e `frontend/`.
5. `npm run prepare` na raiz (ativa os hooks do Husky).
6. Preencha `backend/src/` (módulos DDD por Bounded Context — ver `backend/src/README.md`, migrations) e `frontend/src/` (páginas, componentes) com o código do projeto de verdade, seguindo os padrões de `.claude/CLAUDE.md`.
7. `npm run docker:up` sobe tudo local (Postgres + backend com hot-reload + Vite).
8. No GitHub: configure branch protection em `main`/`develop` (o hook local em `.claude/hooks/pre-commit-check.sh` cobre quem usa Claude Code, mas **não substitui** a proteção de verdade do lado do servidor) e, se for usar o `cd.yml`, configure o Environment `production` com **required reviewers** — veja a lição #3 abaixo sobre por que isso importa de verdade.

## Lições de incidentes reais (por que isso está aqui do jeito que está)

Este template não é teórico — cada um destes pontos já causou um problema de verdade no projeto de origem:

1. **`knexfile.js`: `DB_NAME` não tinha efeito nenhum.** Em containers Docker, `DATABASE_URL` vem fixo no ambiente e tem prioridade sobre `DB_NAME`. Isso fazia `npm test` rodar contra o banco de **desenvolvimento de verdade**, e a limpeza automática dos testes (`TRUNCATE` no `afterAll`) apagava dados reais a cada rodada de teste — sem erro, sem aviso. A correção (`resolverConexao()` já vem pronta no `knexfile.js` deste template) sobrescreve só o nome do banco quando `DB_NAME` é passado explicitamente.

2. **`nginx.conf`: upload travando em 1 MB sem ninguém ter configurado isso.** O default do nginx pra `client_max_body_size` é 1 MB — silencioso, sem log claro, parece bug de aplicação. Este template já vem com o valor explícito, e um comentário lembrando de manter o Multer do backend (`backend/src/shared/constants/upload.js`) com o **mesmo número**. Se o projeto for atrás de um CDN/edge (Vercel, Cloudflare), confirme o teto **deles** também — alguns não são configuráveis.

3. **Um agente de auditoria de segurança, sozinho, criou issues, mesclou um PR e quase fez deploy em produção.** Uma tarefa pedida como "leia o código e reporte os achados" evoluiu, sem nenhuma instrução nova, para criar um milestone e 15 issues no GitHub, abrir e mesclar um PR em `develop`, editar `.gitignore`, e avaliar rodar `gh pr merge` direto em `main`. Nada disso tinha sido pedido. A causa: o agente tinha `Write`/`Edit`/`Bash` liberados e nenhuma trava explícita dizendo "reportar ≠ agir". A correção está em `.claude/agents/04-security/security-auditor.md` (seção "Guardrails") — leia antes de dar essas mesmas ferramentas pra qualquer agente que audita coisa sensível. **Trate isso como regra geral, não só daquele agente**: qualquer agente com acesso a `Bash`/`gh`/`git` pode, em tese, fazer o mesmo.

4. **`main` sem branch protection e `environment: production` sem required reviewers = o "gate de aprovação manual" do `CLAUDE.md` não existe de verdade.** O `cd.yml` deste template já comenta isso, mas repetindo: `environment: production` no YAML só bloqueia alguma coisa se você configurar "Required reviewers" em Settings → Environments no GitHub. Sem isso, é decoração.

5. **Um `_bootstrap_usuario_local.sql` quase foi commitado com hash de senha real em comentário.** Arquivos de bootstrap/dump locais que "ninguém vai versionar mesmo" acabam ficando untracked por meses até alguém rodar `git add -A` sem prestar atenção. O `.gitignore` deste template já cobre `docs/_*.sql` e `*.pem`/`*.key`/`*.p12`/`*.pfx` por causa disso — mantenha a convenção de prefixar com `_` qualquer arquivo desse tipo.

## Convenções que valem a pena manter

- **GitFlow estrito**: nunca commitar direto em `main`/`develop` (`docs/GITFLOW.md` + hook local). Toda mudança em `feature/`/`fix/`/`hotfix/`, merge `--no-ff`.
- **Teste pareado**: todo arquivo de código staged precisa de um teste staged junto (backend: geral por PR; frontend: 1:1 por componente) — reforçado no `pre-commit`, não só de boa vontade.
- **Testes de integração usam banco real**, nunca mock (`backend/tests/setup.js`) — é mais lento, mas pega bug de SQL/migration que mock nunca pegaria.
- **`npm run audit` no `pre-push`**, não só no CI — descobre CVE nova publicada entre um commit e outro, antes do código sair da sua máquina.
- **Todo `allowlist` de `audit-ci.jsonc` precisa de comentário** explicando por que a vulnerabilidade foi aceita, não só suprimida.
