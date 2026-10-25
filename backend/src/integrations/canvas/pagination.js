const NEXT_LINK = /<([^>]+)>;\s*rel="next"/;

// O Canvas pagina por cabeçalho Link, não por número de página: a próxima
// URL já vem pronta e deve ser seguida tal como veio.
function parseNextLink(linkHeader) {
  if (!linkHeader) return null;
  const match = linkHeader.match(NEXT_LINK);
  return match ? match[1] : null;
}

module.exports = { parseNextLink };
