import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { useAuth } from './contexts/AuthContext';
import Configuracoes from './pages/Configuracoes';
import CursoDetalhe from './pages/CursoDetalhe';
import Cursos from './pages/Cursos';
import Login from './pages/Login';
import Perguntas from './pages/Perguntas';
import Prazos from './pages/Prazos';
import Registro from './pages/Registro';
import Sincronizacao from './pages/Sincronizacao';

function Protegida({ children }) {
  const { autenticado, carregando } = useAuth();
  if (carregando) return <p className="carregando">Carregando…</p>;
  return autenticado ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/registro" element={<Registro />} />
      <Route
        element={
          <Protegida>
            <Layout />
          </Protegida>
        }
      >
        <Route index element={<Cursos />} />
        <Route path="cursos/:id" element={<CursoDetalhe />} />
        <Route path="prazos" element={<Prazos />} />
        <Route path="perguntas" element={<Perguntas />} />
        <Route path="sincronizacao" element={<Sincronizacao />} />
        <Route path="configuracoes" element={<Configuracoes />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
