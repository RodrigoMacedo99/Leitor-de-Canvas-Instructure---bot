import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const entrar = vi.fn();
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ entrar }) }));

import Login from './Login';

/** Erro no formato do axios: Error com `response.data` (RFC 7807). */
const erroDaApi = detail => Object.assign(new Error(detail), { response: { data: { detail } } });

const montar = () =>
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<p>home</p>} />
      </Routes>
    </MemoryRouter>
  );

describe('Login', () => {
  beforeEach(() => {
    entrar.mockReset();
  });

  it('entra e vai para a home', async () => {
    entrar.mockResolvedValue();
    montar();
    await userEvent.type(screen.getByTestId('email'), 'ana@x.com');
    await userEvent.type(screen.getByTestId('senha'), 'senha-longa-123');
    await userEvent.click(screen.getByTestId('entrar'));
    await waitFor(() => expect(screen.getByText('home')).toBeInTheDocument());
    expect(entrar).toHaveBeenCalledWith('ana@x.com', 'senha-longa-123');
  });

  it('mostra o detail do erro da API', async () => {
    entrar.mockRejectedValue(erroDaApi('E-mail ou senha inválidos.'));
    montar();
    await userEvent.type(screen.getByTestId('email'), 'ana@x.com');
    await userEvent.type(screen.getByTestId('senha'), 'errada-errada');
    await userEvent.click(screen.getByTestId('entrar'));
    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha inválidos.');
    expect(screen.getByTestId('entrar')).toBeEnabled();
  });

  it('tem link para criar conta', () => {
    montar();
    expect(screen.getByRole('link', { name: 'Criar conta' })).toHaveAttribute('href', '/registro');
  });
});
