import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/client', () => ({
  api: { get: vi.fn() },
  mensagemDeErro: e => e.detail ?? 'Erro inesperado.',
}));

import { api } from '../api/client';
import Prazos from './Prazos';

describe('Prazos', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lista os prazos dos próximos 7 dias por padrão', async () => {
    api.get.mockResolvedValue({
      data: [
        { item_id: 'i1', titulo: 'Lista 1', curso: 'Redes', prazo_em: '2026-03-20T12:00:00Z' },
      ],
    });
    render(<Prazos />);
    expect(await screen.findByText('Lista 1')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/prazos', { params: { dias: 7 } });
  });

  it('refaz a consulta ao mudar a janela', async () => {
    api.get.mockResolvedValue({ data: [] });
    render(<Prazos />);
    await userEvent.selectOptions(await screen.findByTestId('janela'), '30');
    await waitFor(() =>
      expect(api.get).toHaveBeenLastCalledWith('/prazos', { params: { dias: 30 } })
    );
    expect(await screen.findByTestId('sem-prazos')).toHaveTextContent('30 dias');
  });

  it('mostra erro da API', async () => {
    api.get.mockRejectedValue({ detail: 'Não autenticado' });
    render(<Prazos />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Não autenticado');
  });
});
