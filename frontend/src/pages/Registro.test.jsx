import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const registrar = vi.fn();
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ registrar }) }));

import Registro from './Registro';

/** Erro no formato do axios: Error com `response.data` (RFC 7807). */
const erroDaApi = detail => Object.assign(new Error(detail), { response: { data: { detail } } });

const montar = () =>
  render(
    <MemoryRouter initialEntries={['/registro']}>
      <Routes>
        <Route path="/registro" element={<Registro />} />
        <Route path="/configuracoes" element={<p>configurações</p>} />
      </Routes>
    </MemoryRouter>
  );

async function preencher() {
  await userEvent.type(screen.getByTestId('nome'), 'Ana Souza');
  await userEvent.type(screen.getByTestId('email'), 'ana@x.com');
  await userEvent.type(screen.getByTestId('senha'), 'uma-senha-bem-longa');
}

describe('Registro', () => {
  beforeEach(() => {
    registrar.mockReset();
  });

  it('cria a conta e leva para as configurações (conectar o Canvas)', async () => {
    registrar.mockResolvedValue();
    montar();
    await preencher();
    await userEvent.click(screen.getByTestId('criar'));
    await waitFor(() => expect(screen.getByText('configurações')).toBeInTheDocument());
    expect(registrar).toHaveBeenCalledWith('Ana Souza', 'ana@x.com', 'uma-senha-bem-longa');
  });

  it('mostra erro de e-mail duplicado', async () => {
    registrar.mockRejectedValue(erroDaApi('Já existe um cadastro com este e-mail.'));
    montar();
    await preencher();
    await userEvent.click(screen.getByTestId('criar'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Já existe um cadastro');
  });
});
