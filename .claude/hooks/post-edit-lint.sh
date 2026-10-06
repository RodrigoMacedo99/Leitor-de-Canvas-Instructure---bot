#!/usr/bin/env bash
# PostToolUse hook (Write|Edit) — lint rápido do arquivo .js/.jsx que acabou de
# ser editado. Nunca bloqueia a edição (sempre sai 0): é só feedback imediato
# devolvido ao contexto do Claude, pra pegar bug óbvio de sintaxe/lint antes
# de rodar a suíte de testes inteira. Cada subprojeto (frontend/backend) tem
# seu próprio eslint config, então a checagem roda isolada por pasta.
set -uo pipefail

INPUT=$(cat)

FILE=$(node -e "
let d='';
process.stdin.on('data', c => d += c);
process.stdin.on('end', () => {
  try {
    const j = JSON.parse(d);
    process.stdout.write(j.tool_response?.filePath || j.tool_input?.file_path || '');
  } catch { process.stdout.write(''); }
});
" <<< "$INPUT")

[ -z "$FILE" ] && exit 0

case "$FILE" in
  *.js|*.jsx) ;;
  *) exit 0 ;;
esac

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_ROOT" ] && exit 0

# Normaliza barras (paths do Windows vêm com \) pra comparar com segurança.
NORM_FILE=$(echo "$FILE" | sed 's#\\#/#g')
NORM_ROOT=$(echo "$REPO_ROOT" | sed 's#\\#/#g')

case "$NORM_FILE" in
  "$NORM_ROOT"/frontend/src/*) PROJECT_DIR="$REPO_ROOT/frontend" ;;
  "$NORM_ROOT"/backend/src/*) PROJECT_DIR="$REPO_ROOT/backend" ;;
  *) exit 0 ;;
esac

cd "$PROJECT_DIR" || exit 0

LINT_OUTPUT=$(npx eslint "$FILE" 2>&1)
LINT_EXIT=$?

[ "$LINT_EXIT" -eq 0 ] && exit 0

node -e "
process.stdout.write(JSON.stringify({
  hookSpecificOutput: {
    hookEventName: 'PostToolUse',
    additionalContext: 'ESLint encontrou problema(s) em ' + process.argv[1] + ':\n' + process.argv[2],
  },
}));
" "$FILE" "$LINT_OUTPUT"

exit 0
