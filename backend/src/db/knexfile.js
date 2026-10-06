require('dotenv').config({ path: require('path').resolve(__dirname, '../../../.env') });

const isProd = process.env.NODE_ENV === 'production';

// Sem DATABASE_URL (uso fora do docker-compose), exige DB_PASSWORD explícito —
// nada de fallback previsível indo pra produção sem querer.
if (!process.env.DATABASE_URL && !process.env.DB_PASSWORD) {
  throw new Error('DB_PASSWORD (ou DATABASE_URL) precisa estar definido — sem fallback.');
}

// LIÇÃO DE UM BUG REAL: em containers Docker (dev e prod), DATABASE_URL vem
// fixo no ambiente. Sem esta função, "DB_NAME=algo_test npm test" não tinha
// efeito nenhum dentro do container — os testes rodavam contra o banco de
// DEV de verdade, e o TRUNCATE do afterAll apagava dados reais a cada
// rodada. DB_NAME, quando setado explicitamente, agora sobrescreve só o
// nome do banco dentro da DATABASE_URL, sem tocar em host/porta/credenciais.
function resolverConexao() {
  if (process.env.DATABASE_URL) {
    if (process.env.DB_NAME) {
      const url = new URL(process.env.DATABASE_URL);
      url.pathname = `/${process.env.DB_NAME}`;
      return url.toString();
    }
    return process.env.DATABASE_URL;
  }
  return {
    host: process.env.DB_HOST || 'localhost',
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || 'app',
    user: process.env.DB_USER || 'app',
    password: process.env.DB_PASSWORD,
  };
}

module.exports = {
  client: 'pg',
  connection: resolverConexao(),
  pool: { min: 2, max: isProd ? 20 : 5 },
  migrations: {
    directory: __dirname + '/migrations',
  },
  seeds: {
    directory: __dirname + '/seeds',
  },
  searchPath: ['public'],
};
