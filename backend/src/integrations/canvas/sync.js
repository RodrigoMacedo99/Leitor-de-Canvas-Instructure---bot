const path = require('path');
const { courseDirName, safeSegment } = require('./paths');
const { writeJson, downloadFile } = require('./storage');
const { COURSE_RESOURCES, pageBodyPath } = require('./resources');
const { SYNC_REPORT_FILE } = require('./constants');

const AUTH_FAILURE_STATUS = 401;
const NOT_FOUND_STATUS = 404;

// Um recurso indisponível (aba desativada, 403, 404) não deve derrubar o
// curso inteiro. Token rejeitado é diferente: aí não adianta continuar.
// 404 costuma ser aba desativada pelo professor, não falha de sincronização.
async function attempt(name, load, report) {
  try {
    return await load();
  } catch (error) {
    if (error.status === AUTH_FAILURE_STATUS) throw error;
    if (error.status === NOT_FOUND_STATUS) {
      report.desativados.push(name);
      return undefined;
    }
    report.erros.push({ recurso: name, status: error.status, mensagem: error.message });
    return undefined;
  }
}

async function saveResources(client, base, courseDir, report) {
  const loaded = {};
  for (const [name, load] of Object.entries(COURSE_RESOURCES)) {
    const data = await attempt(name, () => load(client, base), report);
    if (data === undefined) continue;
    loaded[name] = data;
    await writeJson(courseDir, `${name}.json`, data);
  }
  return loaded;
}

async function savePageBodies(client, base, courseDir, pages, report) {
  for (const page of pages) {
    await attempt(
      `pagina:${page.url}`,
      async () => {
        const body = await client.getJson(pageBodyPath(base, page.url));
        await writeJson(path.join(courseDir, 'pages'), `${safeSegment(page.url)}.json`, body);
      },
      report
    );
  }
}

// Arquivo de módulo não publicado chega sem URL e com locked_for_user: não há o que baixar.
function isDownloadable(file) {
  return Boolean(file.url) && !file.locked_for_user;
}

async function downloadCourseFiles(courseDir, files, fetchImpl, report) {
  const counts = { baixados: 0, ignorados: 0, falhas: 0, bloqueados: 0 };
  for (const file of files) {
    if (!isDownloadable(file)) {
      counts.bloqueados += 1;
      continue;
    }
    const destPath = path.join(courseDir, 'arquivos', `${file.id}-${safeSegment(file.filename)}`);
    const outcome = await attempt(
      `arquivo:${file.id}`,
      () => downloadFile({ url: file.url, size: file.size, destPath, fetchImpl }),
      report
    );
    if (outcome === 'baixado') counts.baixados += 1;
    else if (outcome === 'ignorado') counts.ignorados += 1;
    else counts.falhas += 1;
  }
  return counts;
}

async function syncCourse(client, course, outputDir, fetchImpl) {
  const courseDir = path.join(outputDir, courseDirName(course));
  const base = `/courses/${course.id}`;
  const report = { curso: course.name, erros: [], desativados: [], arquivos: {} };

  await writeJson(courseDir, 'curso.json', course);
  const loaded = await saveResources(client, base, courseDir, report);
  await savePageBodies(client, base, courseDir, loaded.pages || [], report);
  report.arquivos = await downloadCourseFiles(courseDir, loaded.files || [], fetchImpl, report);
  await writeJson(courseDir, SYNC_REPORT_FILE, report);

  return report;
}

async function syncAllCourses(client, outputDir, { fetchImpl = fetch } = {}) {
  const courses = await client.getAll('/courses', { enrollment_state: 'active' });
  const reports = [];
  for (const course of courses) {
    reports.push(await syncCourse(client, course, outputDir, fetchImpl));
  }
  return reports;
}

module.exports = { syncAllCourses };
