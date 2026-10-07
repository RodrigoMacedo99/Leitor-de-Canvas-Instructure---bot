import { beforeEach, describe, expect, it } from 'vitest';
import { api, getStoredToken, mensagemDeErro, storeToken, TOKEN_STORAGE_KEY } from './client';

describe('api client', () => {
  beforeEach(() => window.localStorage.clear());

  it('guarda e remove o token', () => {
    storeToken('abc');
    expect(getStoredToken()).toBe('abc');
    storeToken(null);
    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
  });

  it('envia o JWT no cabeçalho Authorization', async () => {
    storeToken('meu-jwt');
    const config = await api.interceptors.request.handlers[0].fulfilled({ headers: {} });
    expect(config.headers.Authorization).toBe('Bearer meu-jwt');
  });

  it('não envia cabeçalho quando não há token', async () => {
    const config = await api.interceptors.request.handlers[0].fulfilled({ headers: {} });
    expect(config.headers.Authorization).toBeUndefined();
  });

  it('extrai o detail do erro RFC 7807', () => {
    expect(mensagemDeErro({ response: { data: { detail: 'Token recusado' } } })).toBe(
      'Token recusado'
    );
    expect(mensagemDeErro({ message: 'Network Error' })).toBe('Sem conexão com o servidor.');
    expect(mensagemDeErro({})).toBe('Erro inesperado.');
  });
});
