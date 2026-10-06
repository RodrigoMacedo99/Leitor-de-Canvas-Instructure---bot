import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Fora de Docker (front e back no mesmo host) o alvo é localhost. Dentro do
// docker-compose, "localhost" no container do frontend é o próprio container
// — não alcança o backend — então o compose sobrescreve isso via
// VITE_PROXY_TARGET=http://backend:3001 (nome do serviço na rede do compose).
const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:3001';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': proxyTarget,
      '/uploads': proxyTarget,
    },
    // Bind mount do Docker Desktop no Windows não propaga eventos nativos de
    // arquivo (inotify) pro container — sem polling, o Vite nunca percebe
    // edições feitas no host e serve conteúdo desatualizado indefinidamente.
    watch: process.env.VITE_PROXY_TARGET ? { usePolling: true, interval: 1000 } : undefined,
  },
});
