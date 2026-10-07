import { useCallback, useEffect, useState } from 'react';
import { api, mensagemDeErro } from '../api/client';
import Alerta from '../components/Alerta';
import { formatarDataHora } from './Cursos';

const ROTULO_STATUS = {
  executando: 'Executando',
  sucesso: 'Sucesso',
  parcial: 'Parcial',
  falha: 'Falha',
};

export default function Sincronizacao() {
  const [execucoes, setExecucoes] = useState([]);
  const [resumo, setResumo] = useState('');
  const [erro, setErro] = useState('');
  const [info, setInfo] = useState('');

  const carregar = useCallback(() => {
    api
      .get('/sync/execucoes', { params: { limit: 10 } })
      .then(r => setExecucoes(r.data.data))
      .catch(e => setErro(mensagemDeErro(e)));
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function disparar() {
    setErro('');
    setInfo('');
    try {
      await api.post('/sync');
      setInfo('Sincronização na fila.');
      carregar();
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  async function gerarResumo() {
    setErro('');
    try {
      const { data } = await api.post('/resumos', { enviar: false });
      setResumo(data.texto);
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  return (
    <section>
      <div className="barra">
        <h1>Sincronização e resumo</h1>
        <button type="button" onClick={disparar} data-testid="disparar">
          Sincronizar agora
        </button>
      </div>
      <Alerta>{erro}</Alerta>
      <Alerta tipo="sucesso">{info}</Alerta>

      <table>
        <thead>
          <tr>
            <th>Início</th>
            <th>Origem</th>
            <th>Status</th>
            <th>Novos</th>
            <th>Alterados</th>
            <th>Removidos</th>
            <th>Arquivos</th>
          </tr>
        </thead>
        <tbody data-testid="execucoes">
          {execucoes.map(e => (
            <tr key={e.id}>
              <td>{formatarDataHora(e.iniciada_em)}</td>
              <td>{e.gatilho}</td>
              <td>{ROTULO_STATUS[e.status] ?? e.status}</td>
              <td>{e.estatisticas.novos ?? 0}</td>
              <td>{e.estatisticas.alterados ?? 0}</td>
              <td>{e.estatisticas.removidos ?? 0}</td>
              <td>{e.estatisticas.arquivos_baixados ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Resumo de novidades</h2>
      <button type="button" onClick={gerarResumo} data-testid="gerar-resumo">
        Gerar resumo agora
      </button>
      {resumo && (
        <pre className="resumo" data-testid="resumo">
          {resumo}
        </pre>
      )}
    </section>
  );
}
