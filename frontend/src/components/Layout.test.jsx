import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

const sair = vi.fn();
let aluno = { nome: 'Ana', estado_autorizacao: 'ativa' };
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ aluno, sair }) }));

import Layout from './Layout';

const montar = () =>
  render(
    <MemoryRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<p>conteúdo da página</p>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );

describe('Layout', () => {
  it('mostra navegação, usuário e a página filha', () => {
    montar();
    expect(screen.getByRole('link', { name: 'Prazos' })).toHaveAttribute('href', '/prazos');
    expect(screen.getByText('Ana', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('conteúdo da página')).toBeInTheDocument();
    expect(screen.queryByTestId('alerta-aviso')).not.toBeInTheDocument();
  });

  it('avisa quando o Canvas não está conectado ou o token foi recusado', () => {
    aluno = { nome: 'Ana', estado_autorizacao: 'pendente' };
    const { unmount } = montar();
    expect(screen.getByTestId('alerta-aviso')).toHaveTextContent(/Conecte o seu Canvas/);
    unmount();
    aluno = { nome: 'Ana', estado_autorizacao: 'reautorizar' };
    montar();
    expect(screen.getByTestId('alerta-aviso')).toHaveTextContent(/token do Canvas foi recusado/);
  });

  it('o botão Sair chama sair()', async () => {
    montar();
    await userEvent.click(screen.getByTestId('sair'));
    expect(sair).toHaveBeenCalledOnce();
  });
});
