const { DEFAULT_OUTPUT_DIR } = require('./constants');

function parseBaseUrl(raw) {
  try {
    return new URL(raw).origin;
  } catch {
    throw new Error(
      `CANVAS_BASE_URL inválida: "${raw}". Use algo como https://sua-instituicao.instructure.com`
    );
  }
}

function readConfig(env) {
  const { CANVAS_BASE_URL: baseUrl, CANVAS_TOKEN: token } = env;
  if (!baseUrl || !token) {
    throw new Error('CANVAS_BASE_URL e CANVAS_TOKEN precisam estar definidos no ambiente.');
  }
  return {
    baseUrl: parseBaseUrl(baseUrl),
    token,
    outputDir: env.CANVAS_OUTPUT_DIR || DEFAULT_OUTPUT_DIR,
  };
}

module.exports = { readConfig };
