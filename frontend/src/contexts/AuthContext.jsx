import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, getStoredToken, setUnauthorizedHandler, storeToken } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(getStoredToken());
  const [aluno, setAluno] = useState(null);
  const [carregando, setCarregando] = useState(Boolean(getStoredToken()));

  const sair = useCallback(() => {
    storeToken(null);
    setToken(null);
    setAluno(null);
  }, []);

  const atualizarPerfil = useCallback(async () => {
    const { data } = await api.get('/alunos/me');
    setAluno(data);
    return data;
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(sair);
  }, [sair]);

  useEffect(() => {
    if (!token) {
      setCarregando(false);
      return;
    }
    setCarregando(true);
    atualizarPerfil()
      .catch(sair)
      .finally(() => setCarregando(false));
  }, [token, atualizarPerfil, sair]);

  const entrar = useCallback(async (email, senha) => {
    const { data } = await api.post('/auth/login', { email, senha });
    storeToken(data.access_token);
    setToken(data.access_token);
  }, []);

  const registrar = useCallback(
    async (nome, email, senha) => {
      await api.post('/auth/registro', { nome, email, senha });
      await entrar(email, senha);
    },
    [entrar]
  );

  const value = useMemo(
    () => ({
      aluno,
      autenticado: Boolean(token),
      carregando,
      entrar,
      registrar,
      sair,
      atualizarPerfil,
    }),
    [aluno, token, carregando, entrar, registrar, sair, atualizarPerfil]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth precisa estar dentro de <AuthProvider>');
  return ctx;
}
