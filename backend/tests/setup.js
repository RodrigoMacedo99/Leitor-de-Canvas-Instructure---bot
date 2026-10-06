const db = require('../src/db/knexfile');
const knex = require('knex')(db);

/**
 * Padrão de teste de integração deste projeto: banco Postgres REAL (via
 * DATABASE_URL/DB_NAME apontando pra um banco de teste — ver knexfile.js),
 * nunca mocks. Rode as migrations, semeie o mínimo necessário, e
 * TRUNCATE tudo no fim pra deixar o próximo teste isolado.
 *
 * Adapte setupTestDb() pra semear os dados base do SEU domínio (ex.: tipos
 * de usuário, papéis, permissões) — isto aqui é só o esqueleto.
 */
async function setupTestDb() {
  await knex.migrate.latest();
  await teardownTestDb();

  // Semeie aqui os dados mínimos que toda suíte precisa (ex.: um usuário
  // de teste, papéis/permissões padrão) e devolva os ids relevantes.
  return {};
}

async function teardownTestDb() {
  // TRUNCATE ... CASCADE em todas as tabelas do schema (exceto controle de
  // migrations) evita que uma lista de tabelas mantida à mão fique
  // desatualizada. RESTART IDENTITY zera as sequências, então os ids
  // voltam a ser determinísticos entre execuções.
  const { rows } = await knex.raw(`
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tablename NOT LIKE 'knex_migrations%'
  `);
  if (rows.length === 0) return;
  const tables = rows.map(r => `"${r.tablename}"`).join(', ');
  await knex.raw(`TRUNCATE TABLE ${tables} RESTART IDENTITY CASCADE`);
}

module.exports = { setupTestDb, teardownTestDb };
