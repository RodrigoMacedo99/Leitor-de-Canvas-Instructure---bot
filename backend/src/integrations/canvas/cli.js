#!/usr/bin/env node
const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../../../../.env') });
const { readConfig } = require('./config');
const { createCanvasClient } = require('./client');
const { syncAllCourses } = require('./sync');

async function main(env = process.env) {
  const config = readConfig(env);
  const client = createCanvasClient(config);
  const reports = await syncAllCourses(client, config.outputDir);

  const comErros = reports.filter(report => report.erros.length > 0).length;
  console.log(`${reports.length} curso(s) sincronizado(s) em ${path.resolve(config.outputDir)}`);
  if (comErros > 0) {
    console.log(`${comErros} curso(s) com erros parciais — veja sincronizacao.json em cada pasta.`);
  }
  return reports;
}

if (require.main === module) {
  main().catch(error => {
    console.error(`Falha na sincronização: ${error.message}`);
    process.exit(1);
  });
}

module.exports = { main };
