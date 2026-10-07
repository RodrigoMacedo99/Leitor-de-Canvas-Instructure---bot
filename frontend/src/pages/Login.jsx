import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { mensagemDeErro } from '../api/client';
import Alerta from '../components/Alerta';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const { entrar } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento) {
    evento.preventDefault();
    setErro('');
    setEnviando(true);
    try {
      await entrar(email, senha);
      navigate('/');
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="cartao-centro">
      <h1>Entrar no CBOT</h1>
      <form onSubmit={enviar}>
        <label>
          E-mail
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            autoComplete="username"
            data-testid="email"
          />
        </label>
        <label>
          Senha
          <input
            type="password"
            value={senha}
            onChange={e => setSenha(e.target.value)}
            required
            autoComplete="current-password"
            data-testid="senha"
          />
        </label>
        <Alerta>{erro}</Alerta>
        <button type="submit" disabled={enviando} data-testid="entrar">
          {enviando ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
      <p>
        Primeira vez? <Link to="/registro">Criar conta</Link>
      </p>
    </main>
  );
}
