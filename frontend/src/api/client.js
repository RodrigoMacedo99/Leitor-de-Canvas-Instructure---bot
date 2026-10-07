import axios from 'axios';

export const TOKEN_STORAGE_KEY = 'cbot.token';
const UNAUTHORIZED = 401;

export function getStoredToken() {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function storeToken(token) {
  if (token) window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  else window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

/** Cliente HTTP único: o JWT vai no cabeçalho Authorization (nunca na URL). */
export const api = axios.create({ baseURL: '/api/v1', timeout: 30000 });

api.interceptors.request.use(config => {
  const token = getStoredToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let onUnauthorized = () => {};
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

api.interceptors.response.use(
  response => response,
  error => {
    const isLogin = error.config?.url?.includes('/auth/login');
    if (error.response?.status === UNAUTHORIZED && !isLogin) onUnauthorized();
    return Promise.reject(error);
  }
);

/** Extrai a mensagem de um erro RFC 7807 (`detail`) devolvido pela API. */
export function mensagemDeErro(error) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.title ||
    (error?.message === 'Network Error' ? 'Sem conexão com o servidor.' : 'Erro inesperado.')
  );
}
