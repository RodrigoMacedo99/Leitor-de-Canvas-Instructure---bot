from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cbot.modules.canvas.public import CursoLms
from cbot.modules.conteudo.domain.entities import (
    ArquivoRegistro,
    Curso,
    EventoDetalhado,
    EventoMudanca,
    ItemCurso,
    PrazoDetalhado,
)
from cbot.shared.vocab import TipoItem


class ConteudoRepository(Protocol):
    """Porta de persistência de cursos, itens, arquivos e eventos. Todo método filtra por aluno."""

    def upsert_curso(self, aluno_id: UUID, curso: CursoLms) -> Curso: ...

    def desativar_cursos_ausentes(self, aluno_id: UUID, lms_ids_ativos: Sequence[int]) -> int: ...

    def marcar_curso_sincronizado(
        self, aluno_id: UUID, curso_id: UUID, quando: datetime
    ) -> None: ...

    def listar_cursos(self, aluno_id: UUID, *, somente_ativos: bool = True) -> list[Curso]: ...

    def obter_curso(self, aluno_id: UUID, curso_id: UUID) -> Curso | None: ...

    def itens_por_externo(self, aluno_id: UUID, curso_id: UUID) -> dict[str, ItemCurso]: ...

    def listar_itens(
        self, aluno_id: UUID, curso_id: UUID, *, tipo: TipoItem | None, desde: datetime | None,
        limite: int, deslocamento: int,
    ) -> tuple[list[ItemCurso], int]: ...  # fmt: skip

    def obter_item(self, aluno_id: UUID, item_id: UUID) -> ItemCurso | None: ...

    def inserir_item(self, item: ItemCurso) -> None: ...

    def atualizar_item(self, item: ItemCurso) -> None: ...

    def marcar_item_removido(self, aluno_id: UUID, item_id: UUID) -> None: ...

    def ultimo_arquivo(self, aluno_id: UUID, item_id: UUID) -> ArquivoRegistro | None: ...

    def obter_arquivo(self, aluno_id: UUID, arquivo_id: UUID) -> ArquivoRegistro | None: ...

    def inserir_arquivo(self, arquivo: ArquivoRegistro) -> None: ...

    def registrar_extracao(
        self, aluno_id: UUID, arquivo_id: UUID, quando: datetime, erro: str | None
    ) -> None: ...

    def inserir_evento(self, evento: EventoMudanca) -> None: ...

    def eventos_pendentes(self, aluno_id: UUID) -> list[EventoDetalhado]: ...

    def eventos_do_curso(
        self, aluno_id: UUID, curso_id: UUID, desde: datetime | None
    ) -> list[EventoDetalhado]: ...

    def marcar_eventos_notificados(
        self, aluno_id: UUID, ids: Sequence[UUID], quando: datetime
    ) -> None: ...

    def prazos(self, aluno_id: UUID, de: datetime, ate: datetime) -> list[PrazoDetalhado]: ...
