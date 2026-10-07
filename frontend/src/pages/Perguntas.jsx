import { useEffect, useState } from 'react';
import { api, mensagemDeErro } from '../api/client';
import Alerta from '../components/Alerta';

export default function Perguntas() {
  const [cursos, setCursos] = useState([]);
  const [cursoId, setCursoId] = useState('');
  const [pergunta, setPergunta] = useState('');
  const [conversa, setConversa] = useState([]);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState('');

  useEffect(() => {
    api
      .get('/cursos')
      .then(r => setCursos(r.data.data))
      .catch(() => setCursos([]));
  }, []);

  async function perguntar(evento) {
    evento.preventDefault();
    const texto = pergunta.trim();
    if (!texto) return;
    setErro('');
    setEnviando(true);
    setConversa(c => [...c, { papel: 'aluno', texto }]);
    setPergunta('');
    try {
      const { data } = await api.post('/perguntas', {
        pergunta: texto,
        ...(cursoId && { curso_id: cursoId }),
      });
      setConversa(c => [
        ...c,
        {
          papel: 'bot',
          texto: data.resposta,
          fontes: data.fontes,
          fundamentada: data.fundamentada,
        },
      ]);
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section>
      <h1>Perguntas sobre o material</h1>
      <p className="ajuda">
        O assistente responde só com base nos arquivos, páginas, tarefas e avisos dos seus cursos e
        cita as fontes.
      </p>
      <label>
        Curso (opcional)
        <select value={cursoId} onChange={e => setCursoId(e.target.value)} data-testid="curso">
          <option value="">Todos</option>
          {cursos.map(c => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </select>
      </label>
      <ol className="conversa" data-testid="conversa">
        {conversa.map((m, i) => (
          <li key={i} className={`balao balao-${m.papel}`}>
            <p>{m.texto}</p>
            {m.fontes?.length > 0 && (
              <ul className="fontes">
                {m.fontes.map(f => (
                  <li key={f.n}>
                    [{f.n}] {f.arquivo ?? f.item}
                    {f.pagina ? ` — p. ${f.pagina}` : ''}
                    {f.curso ? ` (${f.curso})` : ''}
                  </li>
                ))}
              </ul>
            )}
            {m.papel === 'bot' && !m.fundamentada && (
              <small>Sem evidência suficiente no material.</small>
            )}
          </li>
        ))}
      </ol>
      <Alerta>{erro}</Alerta>
      <form onSubmit={perguntar} className="linha">
        <input
          type="text"
          value={pergunta}
          onChange={e => setPergunta(e.target.value)}
          placeholder="Ex.: qual a diferença entre TCP e UDP?"
          maxLength={2000}
          aria-label="Sua pergunta"
          data-testid="pergunta"
        />
        <button type="submit" disabled={enviando} data-testid="enviar">
          {enviando ? 'Pensando…' : 'Perguntar'}
        </button>
      </form>
    </section>
  );
}
