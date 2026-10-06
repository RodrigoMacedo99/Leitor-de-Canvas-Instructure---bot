# backend/src

Vazio de propósito. Arquitetura: **monólito modular com DDD** — um processo/deploy só,
mas o código é organizado em módulos por domínio (Bounded Context), não por camada técnica.
Estrutura sugerida (já referenciada no `.gitignore`/hooks):

```
src/
  index.js               bootstrap do Express (helmet, cors, rate-limit, error handler global)
  app.js                 app Express exportado (separado do index.js pra facilitar testes com supertest);
                         é aqui que as rotas de cada módulo são plugadas

  modules/               um diretório por Bounded Context — comece duplicando modules/_exemplo/
                         (ex.: modules/pedidos/, modules/usuarios/) e apague o _exemplo
    <contexto>/
      domain/            regra de negócio pura — zero import de express/knex/qualquer infra
        entities/        Entities e Aggregates (identidade + ciclo de vida)
        value-objects/   Value Objects (imutáveis, sem identidade — ex.: Email, Dinheiro)
        events/          Domain Events (fatos que aconteceram no domínio)
        <contexto>.repository.js   interface do repositório (contrato, não implementação)
      application/       Use Cases — orquestram entities/repositório pra cumprir um caso de uso
        use-cases/       1 arquivo por caso de uso (ex.: criar-pedido.use-case.js)
      infrastructure/    implementação dos contratos do domain/ com infra real
        <contexto>.knex-repository.js   implementa a interface de domain/ usando Knex
      interfaces/        camada HTTP do módulo — tradução HTTP <-> Use Case
        <contexto>.routes.js
        <contexto>.controller.js

  shared/                kernel compartilhado entre módulos — nunca lógica de negócio aqui
    middleware/          auth.js (JWT), rbac.js (permissões por módulo/ação)
    errors/              classes de erro compartilhadas (DomainError, NotFoundError...)
    constants/           valores compartilhados (ex.: upload.js já vem pronto)

  db/
    knexfile.js          já vem pronto
    migrations/
    seeds/
```

Regras de dependência (o que faz isso ser DDD e não só pastas com nome bonito):

- `domain/` não importa nada de `infrastructure/`, `interfaces/` ou de outro módulo — só regra de negócio e as
  interfaces que a própria camada define. É o que permite testar regra de negócio sem banco, sem HTTP, sem mock de framework.
- `infrastructure/` implementa as interfaces definidas em `domain/` (ex.: `PedidoRepository` é a interface,
  `PedidoKnexRepository` é quem sabe falar com Postgres) — trocar Knex por outra coisa não deveria tocar em `domain/`.
- `application/` depende de `domain/`, nunca o contrário.
- Um módulo nunca importa direto de `modules/<outro>/domain` ou `.../infrastructure` — comunicação entre
  Bounded Contexts é só via evento de domínio ou via a API pública (`interfaces/`) do outro módulo. Isso é o que
  mantém o monólito modular em vez de virar um emaranhado; também é o que faz, no futuro, um módulo virar
  microsserviço sem reescrever regra de negócio.

Delete este arquivo quando o diretório deixar de estar vazio.
