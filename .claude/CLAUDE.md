# Quality Standards — Padrões de Qualidade de Software

Este projeto segue um pipeline completo de qualidade: da coleta de requisitos ao deploy em produção.
Agentes e skills disponíveis em `agents/` e `skills/`.

---

## Código

- Todo código deve ser tipado: TypeScript strict / Python type hints / Go interfaces
- Funções puras onde possível; side effects isolados nas bordas do sistema
- Nenhuma função com mais de 40 linhas; extraia se ultrapassar
- Sem números ou strings mágicas; extraia para constantes nomeadas
- Sem comentários que explicam O QUÊ — nomes devem fazer isso. Comente apenas o PORQUÊ não-óbvio

## Testes

- TDD: escreva o teste com falha primeiro, depois a implementação
- Cobertura mínima de 80% de linhas e branches — obrigatório no CI
- Testes unitários: < 100ms cada, sem I/O, mock nas bordas
- Testes de integração: banco de dados real via testcontainers, sem mocks
- Testes E2E: Playwright, page object pattern, apenas seletores data-testid
- Pirâmide: 70% unit / 20% integration / 10% e2e

## Segurança

- Validar todos os inputs com Zod / Pydantic / class-validator na borda da API
- Apenas queries parametrizadas — nunca concatenação de strings em SQL
- Secrets somente via variáveis de ambiente — nunca no código nem commitados
- `npm audit` / `pip-audit` / `govulncheck` no CI — bloquear em Critical/High
- Security headers via Helmet (ou equivalente) em todas as respostas
- Rate limiting em todos os endpoints públicos
- OWASP Top 10 verificado antes de todo deploy

## CI/CD

- Lint + typecheck + test + security-scan obrigatoriamente passando antes do merge
- Coverage report gerado e tracking de delta por PR
- Deploy para produção requer aprovação manual
- Canary para mudanças de risco médio/alto; blue-green para infraestrutura

## Observabilidade

- Logs estruturados em JSON com trace_id em cada request
- Métricas RED expostas em /metrics (formato Prometheus)
- Traces OpenTelemetry em todas as chamadas externas (DB, HTTP, filas)
- SLOs mínimos: availability 99.9% / error_rate < 0.1% / p99_latency < 2s
- Alertas sobre: error_rate > 0.1%, p99 > 2s, availability < 99.9%

## Code Review

- Correctness: o código faz o que pretende?
- Design: responsabilidades separadas? Sem god classes?
- Security: inputs validados, sem secrets, sem SQL por concatenação?
- Performance: sem N+1, sem bloqueio sync em path async?
- Tests: happy path + pelo menos 1 caminho de erro cobertos?
- Readability: nomes revelam intenção?

---

## Agentes disponíveis

### Requisitos
- `agents/01-requirements/business-analyst.md` — Mapeamento de processos, análise de gaps
- `agents/01-requirements/product-manager.md` — PRDs, user stories, acceptance criteria

### Qualidade
- `agents/03-quality/code-reviewer.md` — Revisão de código completa
- `agents/03-quality/test-architect.md` — Estratégia de testes, TDD, mutation testing
- `agents/03-quality/qa-automation.md` — Automação E2E, frameworks, CI integration
- `agents/03-quality/performance-engineer.md` — Profiling, benchmarking, load testing

### Segurança
- `agents/04-security/security-auditor.md` — OWASP Top 10, CVE scanning
- `agents/04-security/penetration-tester.md` — Pen test autorizado, report de vulnerabilidades
- `agents/04-security/compliance-auditor.md` — SOC2, LGPD/GDPR, HIPAA, PCI-DSS

### Infraestrutura
- `agents/05-infrastructure/devops-engineer.md` — CI/CD, Docker, Kubernetes, GitOps
- `agents/05-infrastructure/deployment-engineer.md` — Blue-green, canary, feature flags
- `agents/05-infrastructure/sre-engineer.md` — SLOs, error budgets, incident response

### Orquestração
- `agents/06-orchestration/workflow-director.md` — Pipeline completo com checkpoints
- `agents/06-orchestration/multi-agent-coordinator.md` — Execução paralela de agentes

## Skills disponíveis

| Skill | Arquivo | Uso |
|---|---|---|
| TDD | `skills/tdd-mastery.md` | Red-Green-Refactor em qualquer linguagem |
| Testes | `skills/testing-strategies.md` | Contract, snapshot, property-based, containers |
| Segurança | `skills/security-hardening.md` | Input validation, CSP, JWT, rate limiting |
| Auth | `skills/authentication-patterns.md` | OAuth2, PKCE, JWT, RBAC |
| CI/CD | `skills/ci-cd-pipelines.md` | GitHub Actions, GitLab CI, matrix builds |
| Monitoring | `skills/monitoring-observability.md` | OpenTelemetry, Prometheus, Grafana |
| API | `skills/api-design-patterns.md` | REST, pagination, versioning, OpenAPI |
| Performance | `skills/performance-optimization.md` | Bundle, caching, Core Web Vitals, virtual lists |
