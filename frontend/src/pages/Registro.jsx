import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { mensagemDeErro } from '../api/client';
import Alerta from '../components/Alerta';
import { useAuth } from '../contexts/AuthContext';

const MIN_SENHA = 10;

export default function Registro() {
  const { registrar } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ nome: '', email: '', senha: '' });
  const [erro, setErro] = useState('');

  const campo = nome => ({
    value: form[nome],
    onChange: e => setForm({ ...form, [nome]: e.target.value }),
    required: true,
    'data-testid': nome,
  });

  async function enviar(evento) {
    evento.preventDefault();
    setErro('');
    try {
      await registrar(form.nome, form.email, form.senha);
      navigate('/configuracoes');
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  return (
    <main className="cartao-centro">
      <h1>Criar conta</h1>
      <form onSubmit={enviar}>
        <label>
          Nome
          <input type="text" minLength={2} autoComplete="name" {...campo('nome')} />
        </label>
        <label>
          E-mail
          <input type="email" autoComplete="username" {...campo('email')} />
        </label>
        <label>
          Senha (mínimo {MIN_SENHA} caracteres)
          <input
            type="password"
            minLength={MIN_SENHA}
            autoComplete="new-password"
            {...campo('senha')}
          />
        </label>
        <Alerta>{erro}</Alerta>
        <button type="submit" data-testid="criar">
          Criar conta
        </button>
      </form>
      <p>
        Já tem conta? <Link to="/login">Entrar</Link>
      </p>
    </main>
  );
}
