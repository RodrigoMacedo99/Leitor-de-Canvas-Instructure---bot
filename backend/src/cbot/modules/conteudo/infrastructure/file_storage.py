import hashlib
import os
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from cbot.shared.errors import ValidationFailed

SHA_PREFIX_LEN = 2


@dataclass(frozen=True, slots=True)
class ArquivoGravado:
    sha256: str
    tamanho: int
    caminho: Path


class FileStorage:
    """Armazenamento endereçado por conteúdo, isolado por aluno: `<raiz>/<aluno>/ab/cd/<sha256>`.

    O isolamento por pasta evita deduplicar entre alunos (nenhum acesso cruzado) e permite
    eliminar tudo de um aluno de uma vez (LGPD).
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def caminho(self, aluno_id: UUID, sha256: str) -> Path:
        shard = Path(sha256[:SHA_PREFIX_LEN], sha256[SHA_PREFIX_LEN : 2 * SHA_PREFIX_LEN])
        return self._root / str(aluno_id) / shard / sha256

    def gravar(self, aluno_id: UUID, chunks: Iterator[bytes], max_bytes: int) -> ArquivoGravado:
        """Grava em streaming calculando o sha256; aborta sem deixar resíduo se passar de `max_bytes`."""
        base = self._root / str(aluno_id)
        base.mkdir(parents=True, exist_ok=True)
        digest, tamanho = hashlib.sha256(), 0
        fd, tmp_name = tempfile.mkstemp(dir=base, suffix=".part")
        try:
            with os.fdopen(fd, "wb") as out:
                for chunk in chunks:
                    tamanho += len(chunk)
                    if tamanho > max_bytes:
                        raise ValidationFailed("Arquivo maior que o limite configurado.")
                    digest.update(chunk)
                    out.write(chunk)
            sha = digest.hexdigest()
            destino = self.caminho(aluno_id, sha)
            destino.parent.mkdir(parents=True, exist_ok=True)
            os.replace(tmp_name, destino)
            return ArquivoGravado(sha, tamanho, destino)
        finally:
            Path(tmp_name).unlink(missing_ok=True)

    def existe(self, aluno_id: UUID, sha256: str) -> bool:
        return self.caminho(aluno_id, sha256).is_file()

    def apagar_aluno(self, aluno_id: UUID) -> None:
        shutil.rmtree(self._root / str(aluno_id), ignore_errors=True)
