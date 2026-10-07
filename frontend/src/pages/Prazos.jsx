import { useEffect, useState } from 'react';
import { api, mensagemDeErro } from '../api/client';
import Alerta from '../components/Alerta';
import { formatarDataHora } from './Cursos';

const JANELAS = [7, 14, 30, 60];

export default function Prazos() {
  const [dias, setDias] = useState(JANELAS[0]);
  const [prazos, setPrazos] = useState(null);
  const [erro, setErro] = useState('');

  useEffect(() => {
    setPrazos(null);
    api
      .get('/prazos', { params: { dias } })
      .then(r => setPrazos(r.data))
      .catch(e => setErro(mensagemDeErro(e)));
  }, [dias]);

  return (
    <section>
      <h1>Prazos</h1>
      <label>
        Próximos
        <select value={dias} onChange={e => setDias(Number(e.target.value))} data-testid="janela">
          {JANELAS.map(d => (
            <option key={d} value={d}>
              {d} dias
            </option>
          ))}
        </select>
      </label>
      <Alerta>{erro}</Alerta>
      {prazos?.length === 0 && (
        <p data-testid="sem-prazos">Nenhum prazo nos próximos {dias} dias. 🎉</p>
      )}
      <ul className="cartoes">
        {prazos?.map(p => (
          <li key={p.item_id} className="cartao">
            <strong>{p.titulo}</strong>
            <span>{p.curso}</span>
            <small>{formatarDataHora(p.prazo_em)}</small>
          </li>
        ))}
      </ul>
    </section>
  );
}
