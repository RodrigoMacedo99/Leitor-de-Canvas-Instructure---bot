// O Canvas limita per_page a 100; pedir mais que isso é silenciosamente truncado.
const CANVAS_PER_PAGE = 100;
const CANVAS_MAX_RETRIES = 3;
const CANVAS_BACKOFF_BASE_MS = 1000;
const CANVAS_API_PATH = '/api/v1';
const DEFAULT_OUTPUT_DIR = 'canvas-data';
const MAX_SEGMENT_LENGTH = 120;
const FALLBACK_SEGMENT = 'sem-nome';
const SYNC_REPORT_FILE = 'sincronizacao.json';

module.exports = {
  CANVAS_PER_PAGE,
  CANVAS_MAX_RETRIES,
  CANVAS_BACKOFF_BASE_MS,
  CANVAS_API_PATH,
  DEFAULT_OUTPUT_DIR,
  MAX_SEGMENT_LENGTH,
  FALLBACK_SEGMENT,
  SYNC_REPORT_FILE,
};
