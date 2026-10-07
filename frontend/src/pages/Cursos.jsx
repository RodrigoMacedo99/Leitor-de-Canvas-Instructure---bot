import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, mensagemDeErro } from '../api/client';
import Alerta from '../components/Alerta';

export function formatarDataHora(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

export default function Cursos() {
  const [cursos, setCursos] = useState(null);
  const [erro, setErro] = useState('');
  const [info, setInfo] = useState('');

  const carregar = useCallback(async () => {
    try {
      const { data } = await api.get('/cursos');
      setCursos(data.data);
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function sincronizar() {
    setErro('');
    setInfo('');
    try {
      await api.post('/sync');
      setInfo('Sincronização na fila. Os cursos aparecem aqui assim que terminar.');
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  return (
    <section>
      <div className="barra">
        <h1>Meus cursos</h1>
        <button type="button" onClick={sincronizar} data-testid="sincronizar">
          Sincronizar agora
        </button>
      </div>
      <Alerta>{erro}</Alerta>
      <Alerta tipo="sucesso">{info}</Alerta>
      {cursos === null && !erro && <p>Carregando…</p>}
      {cursos?.length === 0 && (
        <p data-testid="sem-cursos">
          Nenhum curso ainda. Conecte o Canvas em Configurações e sincronize.
        </p>
      )}
      <ul className="cartoes">
        {cursos?.map(curso => (
          <li key={curso.id} className="cartao">
            <Link to={`/cursos/${curso.id}`}>
              <strong>{curso.nome}</strong>
            </Link>
            <small>Última sincronização: {formatarDataHora(curso.ultimo_sync_em)}</small>
          </li>
        ))}
      </ul>
    </section>
  );
}
