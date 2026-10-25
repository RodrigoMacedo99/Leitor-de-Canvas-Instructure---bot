const { MAX_SEGMENT_LENGTH, FALLBACK_SEGMENT } = require('./constants');

// Nomes vêm de professores e alunos no Canvas: não confie neles para montar
// caminho. Qualquer caractere fora de letras, números, espaço, ponto, hífen
// e underline vira "_", e pontos iniciais saem para barrar "..".
const UNSAFE_CHARS = /[^\p{L}\p{N} ._-]+/gu;
const LEADING_DOTS = /^\.+/;

function safeSegment(name) {
  const cleaned = String(name ?? '')
    .replace(UNSAFE_CHARS, '_')
    .replace(LEADING_DOTS, '')
    .trim()
    .slice(0, MAX_SEGMENT_LENGTH);
  return cleaned || FALLBACK_SEGMENT;
}

function courseDirName(course) {
  return `${course.id}-${safeSegment(course.name)}`;
}

module.exports = { safeSegment, courseDirName };
