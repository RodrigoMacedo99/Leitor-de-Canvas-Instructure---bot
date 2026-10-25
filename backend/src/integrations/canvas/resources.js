// Cada entrada busca um tipo de dado de um curso. Ordem = ordem de gravação.
// Páginas e arquivos têm passo extra depois da listagem (ver sync.js).
const COURSE_RESOURCES = {
  assignments: (client, base) => client.getAll(`${base}/assignments`),
  modules: (client, base) => client.getAll(`${base}/modules`, { include: ['items'] }),
  announcements: (client, base) =>
    client.getAll(`${base}/discussion_topics`, { only_announcements: true }),
  discussions: (client, base) => client.getAll(`${base}/discussion_topics`),
  pages: (client, base) => client.getAll(`${base}/pages`),
  quizzes: (client, base) => client.getAll(`${base}/quizzes`),
  files: (client, base) => client.getAll(`${base}/files`),
};

function pageBodyPath(base, pageUrl) {
  return `${base}/pages/${encodeURIComponent(pageUrl)}`;
}

module.exports = { COURSE_RESOURCES, pageBodyPath };
