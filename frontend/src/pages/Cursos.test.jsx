import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
  mensagemDeErro: e => e.detail ?? 'Erro inesperado.',
}));

import { api } from '../api/client';
import Cursos, { formatarDataHora } from './Cursos';

const montar = () =>
  render(
    <MemoryRouter>
      <Cursos />
    </MemoryRouter>
  );

describe('Cursos', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lista os cursos com link para o detalhe', async () => {
    api.get.mockResolvedValue({
      data: {
        data: [{ id: 'c1', nome: 'Redes de Computadores', ultimo_sync_em: '2026-03-10T12:00:00Z' }],
      },
    });
    montar();
    const link = await screen.findByRole('link', { name: 'Redes de Computadores' });
    expect(link).toHaveAttribute('href', '/cursos/c1');
  });

  it('orienta quando não há cursos', async () => {
    api.get.mockResolvedValue({ data: { data: [] } });
    montar();
    expect(await screen.findByTestId('sem-cursos')).toHaveTextContent(/Conecte o Canvas/);
  });

  it('mostra erro da API ao carregar', async () => {
    api.get.mockRejectedValue({ detail: 'Servidor fora do ar' });
    montar();
    expect(await screen.findByRole('alert')).toHaveTextContent('Servidor fora do ar');
  });

  it('dispara a sincronização manual e confirma', async () => {
    api.get.mockResolvedValue({ data: { data: [] } });
    api.post.mockResolvedValue({ data: { job_id: 'j1' } });
    montar();
    await userEvent.click(await screen.findByTestId('sincronizar'));
    expect(api.post).toHaveBeenCalledWith('/sync');
    expect(await screen.findByRole('status')).toHaveTextContent(/na fila/);
  });

  it('mostra conflito quando já há sincronização em andamento', async () => {
    api.get.mockResolvedValue({ data: { data: [] } });
    api.post.mockRejectedValue({ detail: 'Já existe uma sincronização em andamento.' });
    montar();
    await userEvent.click(await screen.findByTestId('sincronizar'));
    expect(await screen.findByRole('alert')).toHaveTextContent('em andamento');
  });

  it('formata datas vazias e válidas', () => {
    expect(formatarDataHora(null)).toBe('—');
    expect(formatarDataHora('2026-03-10T12:00:00Z')).toMatch(/2026|26/);
  });
});
