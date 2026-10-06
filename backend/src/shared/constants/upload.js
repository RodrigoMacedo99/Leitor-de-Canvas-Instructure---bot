// Fonte única de verdade pro limite de tamanho de upload. Reaproveite esta
// constante em TODO multer({ limits: { fileSize: ... } }) do projeto —
// nunca escreva o número literal de novo num outro arquivo.
//
// LIÇÃO DE UM BUG REAL: o nginx tem um default de client_max_body_size de
// 1 MB. Se esse valor mudar aqui, mude também em:
//   - frontend/nginx.conf (client_max_body_size)
//   - o proxy real de produção, se houver um fora deste repo (VPS, Vercel
//     e outros CDNs/edges têm tetos próprios e não-configuráveis — confirme
//     o teto real da sua plataforma de deploy antes de subir este número).
const UPLOAD_MAX_BYTES = 4 * 1024 * 1024; // 4 MB

module.exports = { UPLOAD_MAX_BYTES };
