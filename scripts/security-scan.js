#!/usr/bin/env node
/**
 * Security scanner — executado no pre-commit (e no CI com --all).
 * Detecta segredos, padrões perigosos e dependências vulneráveis.
 */
const { execSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';
const GREEN = '\x1b[32m';
const RESET = '\x1b[0m';
const BOLD = '\x1b[1m';

const CHECAR_TUDO = process.argv.includes('--all');

let issues = [];
let warnings = [];

function error(msg) {
  issues.push(msg);
  console.error(`${RED}  ✖ ${msg}${RESET}`);
}
function warn(msg) {
  warnings.push(msg);
  console.warn(`${YELLOW}  ⚠ ${msg}${RESET}`);
}
function ok(msg) {
  console.log(`${GREEN}  ✔ ${msg}${RESET}`);
}

// ── 1. Listar arquivos a checar ─────────────────────────────────────────────
let arquivos = [];
if (CHECAR_TUDO) {
  const out = execSync('git ls-files', { encoding: 'utf8' });
  arquivos = out.trim().split('\n').filter(Boolean);
} else {
  try {
    const out = execSync('git diff --cached --name-only --diff-filter=ACMR', { encoding: 'utf8' });
    arquivos = out.trim().split('\n').filter(Boolean);
  } catch {
    console.error('Não foi possível listar arquivos staged.');
    process.exit(1);
  }
}

if (arquivos.length === 0) {
  console.log('Nenhum arquivo para checar.');
  process.exit(0);
}

// ── 2. Padrões de segredos hardcoded ─────────────────────────────────────
const SECRET_PATTERNS = [
  { name: 'JWT secret hardcoded', re: /jwt[_-]?secret\s*[:=]\s*['"`][^'"`]{8,}/i },
  { name: 'senha/password hardcoded', re: /password\s*[:=]\s*['"`][^'"`]{4,}/i },
  { name: 'API Key', re: /api[_-]?key\s*[:=]\s*['"`][A-Za-z0-9_\-]{16,}/i },
  { name: 'Token Bearer hardcoded', re: /Bearer\s+[A-Za-z0-9\-_]{20,}/i },
  { name: 'Private key PEM', re: /-----BEGIN (RSA |EC )?PRIVATE KEY-----/ },
  { name: 'AWS access key', re: /AKIA[0-9A-Z]{16}/ },
  // `skipIf` evita falso positivo em strings de conexão que usam interpolação
  // de variável de ambiente (`${DB_PASSWORD:-...}`) — o segredo real vem do
  // ambiente, não está hardcoded no arquivo (ex.: docker-compose).
  { name: 'Conexão DB com senha', re: /postgresql?:\/\/[^:]+:[^@]{4,}@/, skipIf: /\$\{/ },
];

const CHECKABLE_EXT = ['.js', '.jsx', '.ts', '.tsx', '.py', '.toml', '.json', '.yml', '.yaml', '.env', '.sh'];
const ALLOW_LIST = ['.env.example', '.env.test'];

console.log(`\n${BOLD}🔐 Scanner de Segurança${RESET}\n`);
console.log(`Analisando ${arquivos.length} arquivo(s)...\n`);

for (const file of arquivos) {
  if (!CHECKABLE_EXT.includes(path.extname(file))) continue;

  if (path.basename(file) === '.env') {
    error(`Arquivo .env detectado: "${file}" — nunca commitar variáveis de ambiente reais!`);
    continue;
  }

  let content;
  try {
    content = CHECAR_TUDO
      ? fs.readFileSync(file, 'utf8')
      : execSync(`git show :${file}`, { encoding: 'utf8' });
  } catch {
    continue; // arquivo binário, removido, ou não rastreado
  }

  const lines = content.split('\n');
  const isAllowListed = ALLOW_LIST.includes(path.basename(file));

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    for (const { name, re, skipIf } of SECRET_PATTERNS) {
      if (skipIf && skipIf.test(line)) continue;
      if (re.test(line)) {
        const msg = `${name} em "${file}":${i + 1}`;
        if (isAllowListed) warn(`(exemplo) ${msg}`);
        else error(msg);
      }
    }
  }
}

// ── 3. Padrões de código inseguros ─────────────────────────────────────────
const DANGEROUS_PATTERNS = [
  { name: 'eval()', re: /\beval\s*\(/, ext: ['.js', '.jsx', '.ts', '.tsx'] },
  { name: 'innerHTML =', re: /\.innerHTML\s*=/, ext: ['.js', '.jsx', '.ts', '.tsx'] },
  { name: 'dangerouslySetInnerHTML', re: /dangerouslySetInnerHTML/, ext: ['.jsx', '.tsx'] },
  { name: 'console.log em src', re: /console\.log\(/, ext: ['.js', '.jsx', '.ts', '.tsx'] },
  { name: 'TODO de segurança', re: /TODO.*auth|FIXME.*security|HACK.*bypass/i, ext: CHECKABLE_EXT },
];

for (const file of arquivos) {
  if (!CHECKABLE_EXT.includes(path.extname(file))) continue; // binários (docx, imagens) não são texto
  const isTest = file.includes('/tests/') || file.includes('.test.') || file.includes('.spec.');
  const isScript = file.startsWith('scripts/');

  let content;
  try {
    content = CHECAR_TUDO
      ? fs.readFileSync(file, 'utf8')
      : execSync(`git show :${file}`, { encoding: 'utf8' });
  } catch {
    continue;
  }

  const lines = content.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    for (const { name, re, ext } of DANGEROUS_PATTERNS) {
      if (!ext.includes(path.extname(file))) continue;
      if (name.includes('console.log') && (isTest || isScript)) continue;
      if (re.test(line)) warn(`${name} em "${file}":${i + 1}`);
    }
  }
}

// ── 4. Dependências ────────────────────────────────────────────────────────
// A auditoria de dependências (pip-audit no backend, audit-ci no frontend) roda no
// pre-push e no job "Security Audit" do CI — aqui só os segredos e padrões perigosos.
ok('Auditoria de dependências: executada no pre-push e no CI (pip-audit / audit-ci).');

// ── 5. Resultado ───────────────────────────────────────────────────────────
console.log('');
if (issues.length > 0) {
  console.error(`${RED}${BOLD}✖ BLOQUEADO — ${issues.length} problema(s) de segurança encontrado(s):${RESET}`);
  issues.forEach(i => console.error(`  ${RED}• ${i}${RESET}`));
  console.error(`\n${YELLOW}Corrija os problemas acima antes de continuar.${RESET}\n`);
  process.exit(1);
}

if (warnings.length > 0) {
  console.warn(`${YELLOW}⚠ ${warnings.length} aviso(s) (não bloqueado):${RESET}`);
  warnings.forEach(w => console.warn(`  ${YELLOW}• ${w}${RESET}`));
}

console.log(`\n${GREEN}${BOLD}✔ Nenhum problema crítico de segurança encontrado.${RESET}\n`);
process.exit(0);
