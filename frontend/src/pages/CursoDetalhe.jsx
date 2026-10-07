import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, mensagemDeErro } from '../api/client';
import Alerta from '../components/Alerta';
import { formatarDataHora } from './Cursos';

const TIPOS = {
  '': 'Todos',
  arquivo: 'Arquivos',
  pagina: 'Páginas',
  tarefa: 'Tarefas',
  quiz: 'Quizzes',
  aviso: 'Avisos',
  programa: 'Programa',
};
const ROTULO_EVENTO = { novo: 'Novo', alterado: 'Alterado', removido: 'Removido' };
const ITENS_POR_PAGINA = 100;

export default function CursoDetalhe() {
  const { id } = useParams();
  const [curso, setCurso] = useState(null);
  const [itens, setItens] = useState([]);
  const [novidades, setNovidades] = useState([]);
  const [tipo, setTipo] = useState('');
  const [erro, setErro] = useState('');

  useEffect(() => {
    Promise.all([api.get(`/cursos/${id}`), api.get(`/cursos/${id}/novidades`)])
      .then(([c, n]) => {
        setCurso(c.data);
        setNovidades(n.data);
      })
      .catch(e => setErro(mensagemDeErro(e)));
  }, [id]);

  useEffect(() => {
    const params = { limit: ITENS_POR_PAGINA, ...(tipo && { tipo }) };
    api
      .get(`/cursos/${id}/itens`, { params })
      .then(r => setItens(r.data.data))
      .catch(e => setErro(mensagemDeErro(e)));
  }, [id, tipo]);

  return (
    <section>
      <p>
        <Link to="/">← Cursos</Link>
      </p>
      <h1>{curso?.nome ?? 'Curso'}</h1>
      <Alerta>{erro}</Alerta>

      <h2>Novidades</h2>
      {novidades.length === 0 ? (
        <p>Sem mudanças registradas.</p>
      ) : (
        <ul data-testid="novidades">
          {novidades.slice(0, 15).map(n => (
            <li key={n.id}>
              <span className={`selo selo-${n.tipo}`}>{ROTULO_EVENTO[n.tipo]}</span> {n.titulo}{' '}
              <small>{formatarDataHora(n.detectado_em)}</small>
            </li>
          ))}
        </ul>
      )}

      <h2>Conteúdo</h2>
      <label>
        Tipo
        <select value={tipo} onChange={e => setTipo(e.target.value)} data-testid="filtro-tipo">
          {Object.entries(TIPOS).map(([valor, rotulo]) => (
            <option key={valor} value={valor}>
              {rotulo}
            </option>
          ))}
        </select>
      </label>
      <table>
        <thead>
          <tr>
            <th>Título</th>
            <th>Seção</th>
            <th>Prazo</th>
          </tr>
        </thead>
        <tbody data-testid="itens">
          {itens.map(i => (
            <tr key={i.id}>
              <td>
                {i.url ? (
                  <a href={i.url} target="_blank" rel="noreferrer noopener">
                    {i.titulo}
                  </a>
                ) : (
                  i.titulo
                )}
              </td>
              <td>{i.secao ?? '—'}</td>
              <td>{formatarDataHora(i.prazo_em)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
