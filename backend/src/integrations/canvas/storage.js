const fs = require('fs/promises');
const path = require('path');

async function writeJson(dir, fileName, data) {
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(path.join(dir, fileName), `${JSON.stringify(data, null, 2)}\n`);
}

async function hasSameSize(filePath, size) {
  try {
    return (await fs.stat(filePath)).size === size;
  } catch {
    return false;
  }
}

// A URL de download do Canvas é assinada e não precisa do token, então ela
// é buscada sem o cabeçalho Authorization para não vazar o token ao host de arquivos.
async function downloadFile({ url, size, destPath, fetchImpl }) {
  if (await hasSameSize(destPath, size)) return 'ignorado';
  const response = await fetchImpl(url);
  if (!response.ok) throw new Error(`Download falhou (${response.status}): ${destPath}`);
  await fs.mkdir(path.dirname(destPath), { recursive: true });
  await fs.writeFile(destPath, Buffer.from(await response.arrayBuffer()));
  return 'baixado';
}

module.exports = { writeJson, downloadFile };
