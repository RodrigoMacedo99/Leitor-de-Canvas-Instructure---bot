const fs = require('fs/promises');
const os = require('os');
const path = require('path');
const { syncAllCourses } = require('../../../src/integrations/canvas/sync');
const { CanvasApiError } = require('../../../src/integrations/canvas/client');

const COURSE = { id: 7, name: 'Física II' };
const COURSE_DIR = '7-Física II';

function fakeClient({ lists = {}, pages = {}, failures = {} } = {}) {
  return {
    getAll: jest.fn(path => {
      if (path === '/courses') return Promise.resolve([COURSE]);
      const key = Object.keys(failures).find(k => path.endsWith(k));
      if (key) return Promise.reject(failures[key]);
      const listKey = Object.keys(lists).find(k => path.endsWith(k));
      return Promise.resolve(listKey ? lists[listKey] : []);
    }),
    getJson: jest.fn(path => Promise.resolve(pages[path.split('/pages/')[1]])),
  };
}

function fakeFetch(content = 'conteudo') {
  return jest.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      arrayBuffer: () => Promise.resolve(Buffer.from(content)),
    })
  );
}

async function readJson(file) {
  return JSON.parse(await fs.readFile(file, 'utf8'));
}

describe('syncAllCourses', () => {
  let outputDir;

  beforeEach(async () => {
    outputDir = await fs.mkdtemp(path.join(os.tmpdir(), 'canvas-sync-'));
  });

  afterEach(async () => {
    await fs.rm(outputDir, { recursive: true, force: true });
  });

  it('grava um JSON por recurso dentro da pasta do curso', async () => {
    const client = fakeClient({
      lists: { '/assignments': [{ id: 1, name: 'Prova' }], '/pages': [{ url: 'aula-1' }] },
      pages: { 'aula-1': { url: 'aula-1', body: '<p>oi</p>' } },
    });

    await syncAllCourses(client, outputDir, { fetchImpl: fakeFetch() });

    const dir = path.join(outputDir, COURSE_DIR);
    expect(await readJson(path.join(dir, 'curso.json'))).toEqual(COURSE);
    expect(await readJson(path.join(dir, 'assignments.json'))).toEqual([{ id: 1, name: 'Prova' }]);
    expect(await readJson(path.join(dir, 'pages.json'))).toEqual([{ url: 'aula-1' }]);
    expect(await readJson(path.join(dir, 'pages', 'aula-1.json'))).toEqual({
      url: 'aula-1',
      body: '<p>oi</p>',
    });
  });

  it('baixa os arquivos do curso com o id no nome e pula os já baixados com o mesmo tamanho', async () => {
    const file = {
      id: 99,
      filename: 'slides.pdf',
      size: 'conteudo'.length,
      url: 'https://files/99',
    };
    const client = fakeClient({ lists: { '/files': [file] } });
    const fetchImpl = fakeFetch('conteudo');

    await syncAllCourses(client, outputDir, { fetchImpl });
    await syncAllCourses(client, outputDir, { fetchImpl });

    const saved = path.join(outputDir, COURSE_DIR, 'arquivos', '99-slides.pdf');
    expect(await fs.readFile(saved, 'utf8')).toBe('conteudo');
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('registra erros de um recurso e continua com os demais', async () => {
    const client = fakeClient({
      lists: { '/assignments': [{ id: 1 }] },
      failures: { '/quizzes': new CanvasApiError(403, '/quizzes') },
    });

    await syncAllCourses(client, outputDir, { fetchImpl: fakeFetch() });

    const dir = path.join(outputDir, COURSE_DIR);
    const report = await readJson(path.join(dir, 'sincronizacao.json'));
    expect(report.erros).toEqual([expect.objectContaining({ recurso: 'quizzes', status: 403 })]);
    expect(await readJson(path.join(dir, 'assignments.json'))).toEqual([{ id: 1 }]);
  });

  it('registra recurso desativado no curso (404) como aviso, não como erro', async () => {
    const client = fakeClient({
      failures: { '/quizzes': new CanvasApiError(404, '/quizzes') },
    });

    await syncAllCourses(client, outputDir, { fetchImpl: fakeFetch() });

    const report = await readJson(path.join(outputDir, COURSE_DIR, 'sincronizacao.json'));
    expect(report.erros).toEqual([]);
    expect(report.desativados).toEqual(['quizzes']);
  });

  it('pula arquivos sem URL ou bloqueados para o usuário, sem registrar erro', async () => {
    const blocked = { id: 1, filename: 'a.pdf', size: 3, url: '', locked_for_user: true };
    const noUrl = { id: 2, filename: 'b.pdf', size: 3, url: '' };
    const client = fakeClient({ lists: { '/files': [blocked, noUrl] } });
    const fetchImpl = fakeFetch();

    await syncAllCourses(client, outputDir, { fetchImpl });

    const report = await readJson(path.join(outputDir, COURSE_DIR, 'sincronizacao.json'));
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(report.erros).toEqual([]);
    expect(report.arquivos).toEqual({ baixados: 0, ignorados: 0, falhas: 0, bloqueados: 2 });
  });

  it('aborta a sincronização inteira quando o token é rejeitado (401)', async () => {
    const client = fakeClient({
      failures: { '/assignments': new CanvasApiError(401, '/assignments') },
    });

    await expect(
      syncAllCourses(client, outputDir, { fetchImpl: fakeFetch() })
    ).rejects.toMatchObject({ status: 401 });
  });
});
