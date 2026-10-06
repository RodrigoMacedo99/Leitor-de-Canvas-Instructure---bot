# Gitflow — SisGOA

Este projeto usa o modelo Gitflow.

## Branches permanentes

| Branch    | Proposito                                        |
|-----------|--------------------------------------------------|
| `main`    | Codigo em producao. Nunca commitar direto.       |
| `develop` | Integracao de features. Base para novas features.|

## Branches temporarios

| Prefixo    | A partir de | Merge em           | Quando usar              |
|------------|-------------|--------------------|--------------------------|
| `feature/` | `develop`   | `develop`          | Nova funcionalidade       |
| `release/` | `develop`   | `main` + `develop` | Prepara nova versao       |
| `hotfix/`  | `main`      | `main` + `develop` | Correcao urgente producao |
| `support/` | `main`      | ---                | Manutencao versao antiga  |

## Feature nova

```bash
git checkout develop
git checkout -b feature/nome-da-feature
# ...commits...
git checkout develop
git merge --no-ff feature/nome-da-feature -m "feat: merge feature/nome-da-feature"
git branch -d feature/nome-da-feature
```

## Release

```bash
git checkout develop
git checkout -b release/1.2.0
git checkout main
git merge --no-ff release/1.2.0 -m "chore(release): v1.2.0"
git tag -a v1.2.0 -m "v1.2.0"
git checkout develop
git merge --no-ff release/1.2.0 -m "chore(release): sync v1.2.0"
git branch -d release/1.2.0
```

## Hotfix

```bash
git checkout main
git checkout -b hotfix/descricao-do-bug
git checkout main
git merge --no-ff hotfix/descricao-do-bug -m "fix: hotfix descricao-do-bug"
git tag -a v1.2.1 -m "v1.2.1"
git checkout develop
git merge --no-ff hotfix/descricao-do-bug -m "fix: sync hotfix"
git branch -d hotfix/descricao-do-bug
```

## Tags de versao (SemVer)

- MAJOR: quebra de compatibilidade
- MINOR: nova funcionalidade
- PATCH: correcao de bug

## Branch protection (GitHub)

Settings > Branches:
- main: require PR, 1 review, no force push, status checks (ci)
- develop: require PR, status checks (ci)
