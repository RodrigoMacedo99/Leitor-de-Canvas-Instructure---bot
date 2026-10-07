import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/client', () => ({
  api: { get: vi.fn() },
  mensagemDeErro: e => e.detail ?? 'Erro inesperado.',
}));

import { api } from '../api/client';
import CursoDetalhe from './CursoDetalhe';

const montar = () =>
  render(
    <MemoryRouter initialEntries={['/cursos/c1']}>
      <Routes>
        <Route path="/cursos/:id" element={<CursoDetalhe />} />
      </Routes>
    </MemoryRouter>
  );

function responder({ itens = [], novidades = [] } = {}) {
  api.get.mockImplementation(url => {
    if (url.endsWith('/novidades')) return Promise.resolve({ data: novidades });
    if (url.endsWith('/itens')) return Promise.resolve({ data: { data: itens } });
    return Promise.resolve({ data: { nome: 'Redes de Computadores' } });
  });
}

describe('CursoDetalhe', () => {
  beforeEach(() => vi.clearAllMocks());

  it('mostra curso, novidades e itens com link para o Canvas', async () => {
    responder({
      novidades: [
        { id: 'n1', tipo: 'novo', titulo: 'Lista 1', detectado_em: '2026-03-10T12:00:00Z' },
      ],
      itens: [
        {
          id: 'i1',
          titulo: 'Lista 1',
          secao: 'Unidade 1',
          url: 'https://escola.instructure.com/x',
          prazo_em: null,
        },
      ],
    });
    montar();
    expect(
      await screen.findByRole('heading', { name: 'Redes de Computadores' })
    ).toBeInTheDocument();
    expect(await screen.findByTestId('novidades')).toHaveTextContent('Novo');
    const link = await screen.findByRole('link', { name: 'Lista 1' });
    expect(link).toHaveAttribute('href', 'https://escola.instructure.com/x');
    expect(link).toHaveAttribute('rel', 'noreferrer noopener');
  });

  it('filtra por tipo refazendo a consulta', async () => {
    responder();
    montar();
    await userEvent.selectOptions(await screen.findByTestId('filtro-tipo'), 'tarefa');
    await waitFor(() =>
      expect(api.get).toHaveBeenCalledWith('/cursos/c1/itens', {
        params: { limit: 100, tipo: 'tarefa' },
      })
    );
  });

  it('mostra mensagem quando não há mudanças e exibe erros da API', async () => {
    api.get.mockRejectedValue({ detail: 'Curso não encontrado.' });
    montar();
    expect(await screen.findByRole('alert')).toHaveTextContent('Curso não encontrado.');
    expect(screen.getByText('Sem mudanças registradas.')).toBeInTheDocument();
  });
});
