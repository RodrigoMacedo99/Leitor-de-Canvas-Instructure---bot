# frontend/src

Vazio de propósito. Estrutura sugerida:

```
src/
  main.jsx           entrypoint (ReactDOM.createRoot)
  App.jsx            rotas (react-router-dom)
  api/client.js       instância do axios (baseURL, interceptor de auth)
  contexts/           AuthContext (usuário logado, token)
  components/         componentes compartilhados entre páginas
  pages/               uma pasta por domínio, um arquivo por tela + Componente.test.jsx ao lado
```

Convenção de teste (reforçada no `.husky/pre-commit`): todo `Componente.jsx` precisa
de um `Componente.test.jsx` no mesmo diretório, staged junto.

Delete este arquivo quando o diretório deixar de estar vazio.
