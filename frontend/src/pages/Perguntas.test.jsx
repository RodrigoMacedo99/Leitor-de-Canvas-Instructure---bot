import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
  mensagemDeErro: e => e.detail ?? 'Erro inesperado.',
}));

import { api } from '../api/client';
import Perguntas from './Perguntas';

describe('Perguntas', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: { data: [{ id: 'c1', nome: 'Redes' }] } });
  });

  it('envia a pergunta e mostra resposta com fontes', async () => {
    api.post.mockResolvedValue({
      data: {
        resposta: 'UDP não tem conexão [1].',
        fundamentada: true,
        fontes: [{ n: 1, arquivo: 'redes.pdf', pagina: 4, curso: 'Redes' }],
      },
    });
    render(<Perguntas />);
    await userEvent.type(screen.getByTestId('pergunta'), 'O que é UDP?');
    await userEvent.click(screen.getByTestId('enviar'));
    expect(await screen.findByText('UDP não tem conexão [1].')).toBeInTheDocument();
    expect(screen.getByText(/redes\.pdf — p\. 4 \(Redes\)/)).toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith('/perguntas', { pergunta: 'O que é UDP?' });
    expect(screen.getByTestId('pergunta')).toHaveValue('');
  });

  it('filtra por curso quando escolhido', async () => {
    api.post.mockResolvedValue({ data: { resposta: 'ok', fundamentada: true, fontes: [] } });
    render(<Perguntas />);
    await userEvent.selectOptions(await screen.findByTestId('curso'), 'c1');
    await userEvent.type(screen.getByTestId('pergunta'), 'oi?');
    await userEvent.click(screen.getByTestId('enviar'));
    await screen.findByText('ok');
    expect(api.post).toHaveBeenCalledWith('/perguntas', { pergunta: 'oi?', curso_id: 'c1' });
  });

  it('sinaliza resposta sem evidência e erros da API', async () => {
    api.post.mockResolvedValueOnce({
      data: { resposta: 'Não encontrei isso no material.', fundamentada: false, fontes: [] },
    });
    render(<Perguntas />);
    await userEvent.type(screen.getByTestId('pergunta'), 'receita de bolo');
    await userEvent.click(screen.getByTestId('enviar'));
    expect(await screen.findByText(/Sem evidência suficiente/)).toBeInTheDocument();

    api.post.mockRejectedValueOnce({ detail: 'Configure ANTHROPIC_API_KEY' });
    await userEvent.type(screen.getByTestId('pergunta'), 'outra');
    await userEvent.click(screen.getByTestId('enviar'));
    expect(await screen.findByRole('alert')).toHaveTextContent('ANTHROPIC_API_KEY');
  });

  it('ignora envio vazio', async () => {
    render(<Perguntas />);
    await userEvent.click(screen.getByTestId('enviar'));
    expect(api.post).not.toHaveBeenCalled();
  });
});
