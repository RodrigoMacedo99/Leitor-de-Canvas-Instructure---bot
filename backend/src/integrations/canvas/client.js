const {
  CANVAS_PER_PAGE,
  CANVAS_MAX_RETRIES,
  CANVAS_BACKOFF_BASE_MS,
  CANVAS_API_PATH,
} = require('./constants');
const { parseNextLink } = require('./pagination');

const RETRYABLE_STATUSES = new Set([429, 500, 502, 503, 504]);

class CanvasApiError extends Error {
  constructor(status, url) {
    super(`Canvas API respondeu ${status} em ${url}`);
    this.name = 'CanvasApiError';
    this.status = status;
  }
}

function defaultSleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Arrays viram chave[] repetida, que é o formato que o Canvas espera.
function buildUrl(root, path, params = {}) {
  const url = new URL(`${root}${path}`);
  for (const [key, value] of Object.entries(params)) {
    const name = Array.isArray(value) ? `${key}[]` : key;
    for (const item of [].concat(value)) url.searchParams.append(name, item);
  }
  return url.toString();
}

function createCanvasClient({ baseUrl, token, fetchImpl = fetch, sleep = defaultSleep }) {
  const apiRoot = `${baseUrl}${CANVAS_API_PATH}`;

  async function request(url) {
    for (let attempt = 0; ; attempt += 1) {
      const response = await fetchImpl(url, { headers: { Authorization: `Bearer ${token}` } });
      if (response.ok) return response;
      if (!RETRYABLE_STATUSES.has(response.status) || attempt >= CANVAS_MAX_RETRIES) {
        throw new CanvasApiError(response.status, url);
      }
      await sleep(CANVAS_BACKOFF_BASE_MS * 2 ** attempt);
    }
  }

  async function getJson(path, params) {
    const response = await request(buildUrl(apiRoot, path, params));
    return response.json();
  }

  async function getAll(path, params = {}) {
    const items = [];
    let url = buildUrl(apiRoot, path, { per_page: CANVAS_PER_PAGE, ...params });
    while (url) {
      const response = await request(url);
      items.push(...(await response.json()));
      url = parseNextLink(response.headers.get('link'));
    }
    return items;
  }

  return { getJson, getAll };
}

module.exports = { createCanvasClient, CanvasApiError };
