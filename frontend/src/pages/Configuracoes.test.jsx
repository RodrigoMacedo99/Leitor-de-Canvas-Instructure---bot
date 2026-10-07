import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const atualizarPerfil = vi.fn();
const sair = vi.fn();
const aluno = {
  nome: 'Ana',
  estado_autorizacao: 'pendente',
  canal_preferido: 'telegram',
  fuso_horario: 'America/Bahia',
  hora_resumo: '07:30:00',
};
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ aluno, atualizarPerfil, sair }) }));
vi.mock('../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  mensagemDeErro: e => e.detail ?? 'Erro inesperado.',
}));

import { api } from '../api/client';
import Configuracoes from './Configuracoes';

const montar = () =>
  render(
    <MemoryRouter>
      <Configuracoes />
    </MemoryRouter>
  );

describe('Configuracoes', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: [] });
  });

  it('conecta o Canvas enviando url, token e consentimento', async () => {
    api.put.mockResolvedValue({ data: {} });
    montar();
    await userEvent.type(screen.getByTestId('url-canvas'), 'https://escola.instructure.com');
    await userEvent.type(screen.getByTestId('token-canvas'), 'token-do-canvas-123');
    await userEvent.click(screen.getByTestId('consentimento'));
    await userEvent.click(screen.getByTestId('salvar-canvas'));
    await waitFor(() =>
      expect(api.put).toHaveBeenCalledWith('/alunos/me/canvas', {
        url_base: 'https://escola.instructure.com',
        token: 'token-do-canvas-123',
        consentimento: true,
      })
    );
    expect(await screen.findByText(/Canvas conectado/)).toBeInTheDocument();
    expect(atualizarPerfil).toHaveBeenCalled();
    expect(screen.getByTestId('token-canvas')).toHaveValue('');
  });

  it('mostra o erro quando o Canvas recusa o token', async () => {
    api.put.mockRejectedValue({ detail: 'O Canvas recusou o token' });
    montar();
    await userEvent.type(screen.getByTestId('url-canvas'), 'https://escola.instructure.com');
    await userEvent.type(screen.getByTestId('token-canvas'), 'token-do-canvas-123');
    await userEvent.click(screen.getByTestId('salvar-canvas'));
    expect(await screen.findByRole('alert')).toHaveTextContent('recusou o token');
  });

  it('gera o código de pareamento do Telegram', async () => {
    api.post.mockResolvedValue({
      data: { codigo: 'ABCD2345', instrucao: 'Válido por 15 minutos.' },
    });
    montar();
    await userEvent.click(screen.getByTestId('parear-telegram'));
    expect(await screen.findByTestId('codigo')).toHaveTextContent('ABCD2345');
    expect(api.post).toHaveBeenCalledWith('/alunos/me/canais', { canal: 'telegram' });
  });

  it('lista e remove canais vinculados', async () => {
    api.get.mockResolvedValue({ data: [{ id: 'k1', canal: 'whatsapp', vinculado: true }] });
    api.delete.mockResolvedValue({});
    montar();
    expect(await screen.findByText(/WhatsApp — vinculado/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Remover' }));
    expect(api.delete).toHaveBeenCalledWith('/alunos/me/canais/k1');
  });

  it('salva preferências do resumo', async () => {
    api.patch.mockResolvedValue({ data: {} });
    montar();
    await userEvent.selectOptions(screen.getByTestId('canal-preferido'), 'whatsapp');
    await userEvent.click(screen.getByTestId('salvar-preferencias'));
    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/alunos/me', {
        canal_preferido: 'whatsapp',
        fuso_horario: 'America/Bahia',
        hora_resumo: '07:30',
      })
    );
    expect(await screen.findByText('Preferências salvas.')).toBeInTheDocument();
  });

  it('só exclui a conta após confirmação', async () => {
    api.delete.mockResolvedValue({});
    const confirmar = vi.spyOn(window, 'confirm');
    montar();
    confirmar.mockReturnValueOnce(false);
    await userEvent.click(screen.getByTestId('excluir-conta'));
    expect(api.delete).not.toHaveBeenCalledWith('/alunos/me');
    confirmar.mockReturnValueOnce(true);
    await userEvent.click(screen.getByTestId('excluir-conta'));
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/alunos/me'));
    expect(sair).toHaveBeenCalled();
  });
});
