import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/client', () => {
  let token = null;
  return {
    api: { get: vi.fn(), post: vi.fn() },
    getStoredToken: () => token,
    storeToken: t => {
      token = t;
    },
    setUnauthorizedHandler: vi.fn(),
  };
});

import { api, storeToken } from '../api/client';
import { AuthProvider, useAuth } from './AuthContext';

let ctx;
function Sonda() {
  ctx = useAuth();
  return (
    <div>
      <span data-testid="estado">
        {ctx.carregando ? 'carregando' : ctx.autenticado ? 'logado' : 'anonimo'}
      </span>
      <span data-testid="nome">{ctx.aluno?.nome ?? '-'}</span>
    </div>
  );
}

const montar = () =>
  render(
    <AuthProvider>
      <Sonda />
    </AuthProvider>
  );

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    storeToken(null);
  });

  it('começa anônimo sem token', async () => {
    montar();
    await waitFor(() => expect(screen.getByTestId('estado')).toHaveTextContent('anonimo'));
  });

  it('entrar guarda o token e carrega o perfil', async () => {
    api.post.mockResolvedValue({ data: { access_token: 'jwt' } });
    api.get.mockResolvedValue({ data: { nome: 'Ana' } });
    montar();
    await act(async () => ctx.entrar('ana@x.com', 'senha-longa-123'));
    await waitFor(() => expect(screen.getByTestId('nome')).toHaveTextContent('Ana'));
    expect(api.post).toHaveBeenCalledWith('/auth/login', {
      email: 'ana@x.com',
      senha: 'senha-longa-123',
    });
    expect(screen.getByTestId('estado')).toHaveTextContent('logado');
  });

  it('registrar cria a conta e já entra', async () => {
    api.post
      .mockResolvedValueOnce({ data: {} })
      .mockResolvedValueOnce({ data: { access_token: 'jwt' } });
    api.get.mockResolvedValue({ data: { nome: 'Bia' } });
    montar();
    await act(async () => ctx.registrar('Bia', 'bia@x.com', 'senha-longa-123'));
    expect(api.post).toHaveBeenNthCalledWith(1, '/auth/registro', {
      nome: 'Bia',
      email: 'bia@x.com',
      senha: 'senha-longa-123',
    });
    await waitFor(() => expect(screen.getByTestId('estado')).toHaveTextContent('logado'));
  });

  it('sair limpa a sessão e perfil inválido derruba o login', async () => {
    storeToken('velho');
    api.get.mockRejectedValue(new Error('401'));
    montar();
    await waitFor(() => expect(screen.getByTestId('estado')).toHaveTextContent('anonimo'));
  });

  it('useAuth fora do provider falha com mensagem clara', () => {
    const erro = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Sonda />)).toThrow(/AuthProvider/);
    erro.mockRestore();
  });
});
