import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

let estado = { autenticado: false, carregando: false, aluno: { nome: 'Ana' }, sair: vi.fn() };
vi.mock('./contexts/AuthContext', () => ({ useAuth: () => estado }));
vi.mock('./pages/Login', () => ({ default: () => <p>tela de login</p> }));
vi.mock('./pages/Registro', () => ({ default: () => <p>tela de registro</p> }));
vi.mock('./pages/Cursos', () => ({ default: () => <p>tela de cursos</p> }));
vi.mock('./pages/CursoDetalhe', () => ({ default: () => <p>detalhe</p> }));
vi.mock('./pages/Prazos', () => ({ default: () => <p>prazos</p> }));
vi.mock('./pages/Perguntas', () => ({ default: () => <p>perguntas</p> }));
vi.mock('./pages/Sincronizacao', () => ({ default: () => <p>sincronizacao</p> }));
vi.mock('./pages/Configuracoes', () => ({ default: () => <p>configuracoes</p> }));

import App from './App';

const em = rota =>
  render(
    <MemoryRouter initialEntries={[rota]}>
      <App />
    </MemoryRouter>
  );

describe('App', () => {
  it('redireciona anônimos para o login', () => {
    estado = { ...estado, autenticado: false };
    em('/prazos');
    expect(screen.getByText('tela de login')).toBeInTheDocument();
  });

  it('mostra as páginas protegidas dentro do layout quando autenticado', () => {
    estado = { ...estado, autenticado: true };
    em('/prazos');
    expect(screen.getByText('prazos')).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Principal' })).toBeInTheDocument();
  });

  it('aguarda o carregamento do perfil antes de decidir', () => {
    estado = { ...estado, autenticado: true, carregando: true };
    em('/');
    expect(screen.getByText('Carregando…')).toBeInTheDocument();
  });

  it('rota desconhecida volta para a home', () => {
    estado = { ...estado, autenticado: true, carregando: false };
    em('/nao-existe');
    expect(screen.getByText('tela de cursos')).toBeInTheDocument();
  });

  it('registro é público', () => {
    estado = { ...estado, autenticado: false };
    em('/registro');
    expect(screen.getByText('tela de registro')).toBeInTheDocument();
  });
});
