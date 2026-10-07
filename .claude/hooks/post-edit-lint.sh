#!/usr/bin/env bash
# PostToolUse hook (Write|Edit) — lint rápido do arquivo que acabou de ser editado:
#   - backend/**/*.py   -> ruff check (venv do projeto)
#   - frontend/src/*.js(x) -> ESLint
# Nunca bloqueia a edição (sempre sai 0): é só feedback imediato devolvido ao contexto do
# Claude, pra pegar bug óbvio de sintaxe/lint antes de rodar a suíte de testes inteira.
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

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_ROOT" ] && exit 0

# Normaliza barras (paths do Windows vêm com \) pra comparar com segurança.
NORM_FILE=$(echo "$FILE" | sed 's#\\#/#g')
NORM_ROOT=$(echo "$REPO_ROOT" | sed 's#\\#/#g')

feedback() {
  node -e "
process.stdout.write(JSON.stringify({
  hookSpecificOutput: {
    hookEventName: 'PostToolUse',
    additionalContext: process.argv[1] + ' encontrou problema(s) em ' + process.argv[2] + ':\n' + process.argv[3],
  },
}));
" "$1" "$FILE" "$2"
}

case "$NORM_FILE" in
  "$NORM_ROOT"/backend/*.py)
    PYB="$REPO_ROOT/backend/.venv"
    if [ -x "$PYB/Scripts/python" ]; then PY="$PYB/Scripts/python"
    elif [ -x "$PYB/bin/python" ]; then PY="$PYB/bin/python"
    else PY=python; fi
    cd "$REPO_ROOT/backend" || exit 0
    OUTPUT=$("$PY" -m ruff check "$FILE" 2>&1)
    [ $? -eq 0 ] && exit 0
    feedback "ruff" "$OUTPUT"
    ;;
  "$NORM_ROOT"/frontend/src/*.js|"$NORM_ROOT"/frontend/src/*.jsx)
    cd "$REPO_ROOT/frontend" || exit 0
    OUTPUT=$(npx eslint "$FILE" 2>&1)
    [ $? -eq 0 ] && exit 0
    feedback "ESLint" "$OUTPUT"
    ;;
  *) exit 0 ;;
esac

exit 0
