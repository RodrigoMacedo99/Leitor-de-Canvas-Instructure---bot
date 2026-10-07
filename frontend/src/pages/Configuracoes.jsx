import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, mensagemDeErro } from '../api/client';
import Alerta from '../components/Alerta';
import { useAuth } from '../contexts/AuthContext';

const CANAIS = { telegram: 'Telegram', whatsapp: 'WhatsApp' };

function CanvasForm({ onSalvo }) {
  const [form, setForm] = useState({ url_base: '', token: '', consentimento: false });
  const [erro, setErro] = useState('');
  const [ok, setOk] = useState('');

  async function salvar(evento) {
    evento.preventDefault();
    setErro('');
    setOk('');
    try {
      await api.put('/alunos/me/canvas', form);
      setForm({ ...form, token: '' });
      setOk('Canvas conectado. Clique em "Sincronizar agora" na página de Cursos.');
      await onSalvo();
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  return (
    <form onSubmit={salvar}>
      <h2>Conectar o Canvas</h2>
      <p className="ajuda">
        No Canvas: Conta &gt; Configurações &gt; <em>Novo token de acesso</em>. O token fica cifrado
        no servidor e é usado apenas para ler os seus cursos.
      </p>
      <label>
        URL do Canvas
        <input
          type="url"
          placeholder="https://suaescola.instructure.com"
          required
          value={form.url_base}
          onChange={e => setForm({ ...form, url_base: e.target.value })}
          data-testid="url-canvas"
        />
      </label>
      <label>
        Token de acesso
        <input
          type="password"
          required
          minLength={10}
          autoComplete="off"
          value={form.token}
          onChange={e => setForm({ ...form, token: e.target.value })}
          data-testid="token-canvas"
        />
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={form.consentimento}
          onChange={e => setForm({ ...form, consentimento: e.target.checked })}
          data-testid="consentimento"
        />
        Autorizo o tratamento dos meus dados dos cursos para esta finalidade (LGPD).
      </label>
      <Alerta>{erro}</Alerta>
      <Alerta tipo="sucesso">{ok}</Alerta>
      <button type="submit" data-testid="salvar-canvas">
        Conectar
      </button>
    </form>
  );
}

function Canais() {
  const [canais, setCanais] = useState([]);
  const [pareamento, setPareamento] = useState(null);
  const [erro, setErro] = useState('');

  const carregar = useCallback(() => {
    api
      .get('/alunos/me/canais')
      .then(r => setCanais(r.data))
      .catch(e => setErro(mensagemDeErro(e)));
  }, []);
  useEffect(() => {
    carregar();
  }, [carregar]);

  async function gerar(canal) {
    setErro('');
    try {
      const { data } = await api.post('/alunos/me/canais', { canal });
      setPareamento({ ...data, canal });
      carregar();
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  async function remover(id) {
    await api.delete(`/alunos/me/canais/${id}`);
    carregar();
  }

  return (
    <div>
      <h2>Canais (WhatsApp e Telegram)</h2>
      <ul>
        {canais.map(c => (
          <li key={c.id}>
            {CANAIS[c.canal]} — {c.vinculado ? 'vinculado' : 'aguardando código'}{' '}
            <button type="button" className="link" onClick={() => remover(c.id)}>
              Remover
            </button>
          </li>
        ))}
      </ul>
      {Object.entries(CANAIS).map(([valor, rotulo]) => (
        <button
          key={valor}
          type="button"
          onClick={() => gerar(valor)}
          data-testid={`parear-${valor}`}
        >
          Vincular {rotulo}
        </button>
      ))}
      <Alerta>{erro}</Alerta>
      {pareamento && (
        <p className="codigo" data-testid="codigo">
          Envie <strong>{pareamento.codigo}</strong> ao bot do {CANAIS[pareamento.canal]}.{' '}
          {pareamento.instrucao}
        </p>
      )}
    </div>
  );
}

function Preferencias({ aluno, onSalvo }) {
  const [form, setForm] = useState({
    canal_preferido: aluno.canal_preferido,
    fuso_horario: aluno.fuso_horario,
    hora_resumo: aluno.hora_resumo.slice(0, 5),
  });
  const [erro, setErro] = useState('');
  const [ok, setOk] = useState('');

  async function salvar(evento) {
    evento.preventDefault();
    setErro('');
    setOk('');
    try {
      await api.patch('/alunos/me', form);
      setOk('Preferências salvas.');
      await onSalvo();
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  return (
    <form onSubmit={salvar}>
      <h2>Resumo diário</h2>
      <label>
        Canal preferido
        <select
          value={form.canal_preferido}
          onChange={e => setForm({ ...form, canal_preferido: e.target.value })}
          data-testid="canal-preferido"
        >
          {Object.entries(CANAIS).map(([v, r]) => (
            <option key={v} value={v}>
              {r}
            </option>
          ))}
        </select>
      </label>
      <label>
        Horário
        <input
          type="time"
          value={form.hora_resumo}
          onChange={e => setForm({ ...form, hora_resumo: e.target.value })}
          data-testid="hora-resumo"
        />
      </label>
      <label>
        Fuso horário
        <input
          type="text"
          value={form.fuso_horario}
          onChange={e => setForm({ ...form, fuso_horario: e.target.value })}
        />
      </label>
      <Alerta>{erro}</Alerta>
      <Alerta tipo="sucesso">{ok}</Alerta>
      <button type="submit" data-testid="salvar-preferencias">
        Salvar
      </button>
    </form>
  );
}

export default function Configuracoes() {
  const { aluno, atualizarPerfil, sair } = useAuth();
  const navigate = useNavigate();

  async function excluirConta() {
    if (!window.confirm('Isso apaga TODOS os seus dados, arquivos e vínculos. Continuar?')) return;
    await api.delete('/alunos/me');
    sair();
    navigate('/login');
  }

  if (!aluno) return null;
  return (
    <section>
      <h1>Configurações</h1>
      <p>
        Estado do Canvas: <strong data-testid="estado-canvas">{aluno.estado_autorizacao}</strong>
      </p>
      <CanvasForm onSalvo={atualizarPerfil} />
      <Preferencias aluno={aluno} onSalvo={atualizarPerfil} />
      <Canais />
      <h2>Privacidade</h2>
      <button type="button" className="perigo" onClick={excluirConta} data-testid="excluir-conta">
        Excluir minha conta e meus dados
      </button>
    </section>
  );
}
