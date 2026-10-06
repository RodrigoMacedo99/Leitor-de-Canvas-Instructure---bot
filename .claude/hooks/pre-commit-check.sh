#!/usr/bin/env bash
# PreToolUse hook (Bash) — checagens rápidas e universais antes de "git commit",
# sem depender de Docker (funciona pra qualquer colaborador, com ou sem
# ambiente de dev configurado). A checagem pesada de verdade (lint, testes,
# cobertura, audit) roda no CI (.github/workflows/ci.yml) a cada Pull Request
# — essa é a trava que não tem como burlar localmente.
set -uo pipefail

INPUT=$(cat)

CMD=$(node -e "
let d='';
process.stdin.on('data', c => d += c);
process.stdin.on('end', () => {
  try { process.stdout.write(JSON.parse(d).tool_input.command || ''); }
  catch { process.stdout.write(''); }
});
" <<< "$INPUT")

if ! echo "$CMD" | grep -qE '(^|[;&|]|&&)\s*git commit'; then
  exit 0
fi

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$REPO_ROOT" ]; then
  exit 0
fi
cd "$REPO_ROOT" || exit 0

deny() {
  local reason="$1"
  node -e "
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        permissionDecision: 'deny',
        permissionDecisionReason: process.argv[1],
      },
    }));
  " "$reason"
  exit 0
}

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

# 1) Nunca commitar direto em main/develop (GITFLOW.md) — todo trabalho
#    passa por feature/release/hotfix, mesmo que a proteção de branch do
#    lado do GitHub não esteja disponível no plano atual da organização.
if [[ "$BRANCH" == "main" || "$BRANCH" == "develop" ]]; then
  deny "Commit bloqueado: você está em '$BRANCH'. Pelo GITFLOW.md deste projeto, nunca se commita direto em main/develop.
Crie uma branch antes: git checkout -b feature/nome-da-mudanca (a partir de develop) ou hotfix/nome (a partir de main, só pra correção urgente de produção).
Se isso for uma correção urgente e você tem certeza do que está fazendo, peça ao usuário pra confirmar explicitamente antes de rodar 'git commit' de novo — não contorne esta checagem sozinho."
fi

# 2) Aviso (não bloqueia) se a branch local estiver desatualizada em
#    relação ao origin — evita divergência tipo a que já causou colisão de
#    migrations nesta sessão. Só roda fetch se tiver rede; falha silenciosa
#    se não tiver (ex: ambiente sem acesso à internet).
if git fetch origin "$BRANCH" --quiet 2>/dev/null; then
  ATRAS=$(git rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)
  if [ "${ATRAS:-0}" -gt 0 ]; then
    deny "Commit bloqueado: sua branch '$BRANCH' está $ATRAS commit(s) atrás de origin/$BRANCH.
Rode 'git pull origin $BRANCH' e resolva qualquer conflito antes de commitar — evita repetir a colisão de migrations que já aconteceu nesta sessão.
Se já resolveu e ainda aparece este aviso, confirme com 'git log --oneline HEAD..origin/$BRANCH' que está mesmo vazio antes de tentar de novo."
  fi
fi

exit 0
