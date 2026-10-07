import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Alerta from './Alerta';

const LINKS = [
  { to: '/', label: 'Cursos', end: true },
  { to: '/prazos', label: 'Prazos' },
  { to: '/perguntas', label: 'Perguntas' },
  { to: '/sincronizacao', label: 'Sincronização' },
  { to: '/configuracoes', label: 'Configurações' },
];

const AVISOS = {
  pendente: 'Conecte o seu Canvas em Configurações para começar a sincronizar os cursos.',
  reautorizar: 'O token do Canvas foi recusado. Gere um novo e atualize em Configurações.',
};

export default function Layout() {
  const { aluno, sair } = useAuth();
  return (
    <div className="app">
      <header className="topo">
        <strong className="marca">CBOT</strong>
        <nav aria-label="Principal">
          {LINKS.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end}>
              {label}
            </NavLink>
          ))}
        </nav>
        <span className="usuario">
          {aluno?.nome}{' '}
          <button type="button" className="link" onClick={sair} data-testid="sair">
            Sair
          </button>
        </span>
      </header>
      <main className="conteudo">
        <Alerta tipo="aviso">{AVISOS[aluno?.estado_autorizacao]}</Alerta>
        <Outlet />
      </main>
    </div>
  );
}
