import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
  mensagemDeErro: e => e.detail ?? 'Erro inesperado.',
}));

import { api } from '../api/client';
import Sincronizacao from './Sincronizacao';

const EXECUCAO = {
  id: 'e1',
  gatilho: 'manual',
  status: 'sucesso',
  iniciada_em: '2026-03-10T12:00:00Z',
  estatisticas: { novos: 3, alterados: 1, removidos: 0, arquivos_baixados: 2 },
};

describe('Sincronizacao', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: { data: [EXECUCAO] } });
  });

  it('mostra o histórico de execuções com as contagens', async () => {
    render(<Sincronizacao />);
    const linha = (await screen.findByTestId('execucoes')).querySelector('tr');
    expect(linha).toHaveTextContent('Sucesso');
    expect(linha).toHaveTextContent('3');
    expect(api.get).toHaveBeenCalledWith('/sync/execucoes', { params: { limit: 10 } });
  });

  it('dispara a sincronização e recarrega a lista', async () => {
    api.post.mockResolvedValue({ data: { job_id: 'j1' } });
    render(<Sincronizacao />);
    await userEvent.click(await screen.findByTestId('disparar'));
    expect(api.post).toHaveBeenCalledWith('/sync');
    expect(await screen.findByRole('status')).toHaveTextContent('na fila');
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it('gera e exibe o resumo sob demanda', async () => {
    api.post.mockResolvedValue({ data: { texto: 'Redes\n🆕 tarefa: Lista 1' } });
    render(<Sincronizacao />);
    await userEvent.click(await screen.findByTestId('gerar-resumo'));
    expect(await screen.findByTestId('resumo')).toHaveTextContent('tarefa: Lista 1');
    expect(api.post).toHaveBeenCalledWith('/resumos', { enviar: false });
  });

  it('exibe erros da API', async () => {
    api.post.mockRejectedValue({ detail: 'Já existe uma sincronização em andamento.' });
    render(<Sincronizacao />);
    await userEvent.click(await screen.findByTestId('disparar'));
    expect(await screen.findByRole('alert')).toHaveTextContent('em andamento');
  });
});
