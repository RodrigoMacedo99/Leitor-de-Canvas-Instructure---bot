# modules/_exemplo

Molde de um Bounded Context. Quando o projeto real começar, duplique esta pasta com o
nome do domínio (ex.: `modules/pedidos/`, `modules/usuarios/`) e delete `_exemplo/`.
Todo módulo novo segue as mesmas 4 camadas, sempre na mesma direção de dependência:

```
interfaces/  →  application/  →  domain/  ←  infrastructure/
```

- **`domain/`** — regra de negócio pura, zero import de `express`/`knex`/qualquer infra.
  - `entities/` — Entities e Aggregates (têm identidade e ciclo de vida)
  - `value-objects/` — Value Objects (imutáveis, sem identidade — ex.: `Email`, `Dinheiro`)
  - `events/` — Domain Events (fatos que aconteceram no domínio, ex.: `PedidoCriado`)
  - `<contexto>.repository.js` (na raiz de `domain/`) — interface do repositório: só o contrato
    (`salvar`, `buscarPorId`...), a implementação real fica em `infrastructure/`

- **`application/`** — Use Cases: orquestram entities + repositório pra cumprir 1 caso de uso
  - `use-cases/` — 1 arquivo por caso de uso (ex.: `criar-pedido.use-case.js`). Depende de
    `domain/`, nunca o contrário.

- **`infrastructure/`** — implementa os contratos definidos em `domain/` com infra real
  (ex.: `pedido.knex-repository.js` implementa a interface `PedidoRepository` usando Knex).
  Trocar Knex por outra coisa não deveria tocar em `domain/` nem em `application/`.

- **`interfaces/`** — camada HTTP do módulo: tradução HTTP ↔ Use Case
  (`<contexto>.routes.js`, `<contexto>.controller.js`). É o que `app.js` importa pra plugar
  as rotas do módulo.

Regra que não pode quebrar: nenhum módulo importa direto de `modules/<outro>/domain` ou
`.../infrastructure`. Comunicação entre Bounded Contexts é só via Domain Event ou via a API
pública (`interfaces/`) do outro módulo — é isso que mantém o monólito modular em vez de
virar um emaranhado, e o que permite um módulo virar microsserviço no futuro sem reescrever
regra de negócio.
