from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import UUID

from cbot.modules.conteudo.domain.entities import (
    ArquivoRegistro,
    Curso,
    EventoDetalhado,
    ItemCurso,
    PrazoDetalhado,
)
from cbot.modules.conteudo.domain.repository import ConteudoRepository
from cbot.modules.conteudo.infrastructure.file_storage import FileStorage
from cbot.shared.errors import NotFound
from cbot.shared.events import ArquivoProcessado, ContaExcluida, EventBus
from cbot.shared.vocab import TipoItem

MAX_PAGE_SIZE = 100


class ConteudoUow(Protocol):
    @property
    def conteudo(self) -> ConteudoRepository: ...


type ConteudoUowFactory = Callable[[], AbstractContextManager[ConteudoUow]]


class ConsultasConteudo:
    """Casos de uso de leitura (API REST e ferramentas do chat). Todo acesso é por aluno."""

    def __init__(self, uow: ConteudoUowFactory, storage: FileStorage) -> None:
        self._uow = uow
        self._storage = storage

    def registrar(self, bus: EventBus) -> None:
        bus.subscribe(ArquivoProcessado, self._ao_processar_arquivo)
        bus.subscribe(ContaExcluida, lambda e: self._storage.apagar_aluno(e.aluno_id))

    def _ao_processar_arquivo(self, evento: ArquivoProcessado) -> None:
        with self._uow() as uow:
            uow.conteudo.registrar_extracao(
                evento.aluno_id, evento.arquivo_id, datetime.now(UTC), evento.erro
            )

    def cursos(self, aluno_id: UUID) -> list[Curso]:
        with self._uow() as uow:
            return uow.conteudo.listar_cursos(aluno_id)

    def curso(self, aluno_id: UUID, curso_id: UUID) -> Curso:
        with self._uow() as uow:
            curso = uow.conteudo.obter_curso(aluno_id, curso_id)
        if curso is None:
            raise NotFound("Curso não encontrado.")
        return curso

    def itens(
        self, aluno_id: UUID, curso_id: UUID, *, tipo: TipoItem | None = None,
        desde: datetime | None = None, pagina: int = 1, limite: int = 20,
    ) -> tuple[list[ItemCurso], int]:  # fmt: skip
        self.curso(aluno_id, curso_id)
        limite = max(1, min(limite, MAX_PAGE_SIZE))
        with self._uow() as uow:
            return uow.conteudo.listar_itens(
                aluno_id, curso_id, tipo=tipo, desde=desde, limite=limite,
                deslocamento=(max(pagina, 1) - 1) * limite,
            )  # fmt: skip

    def novidades(
        self, aluno_id: UUID, curso_id: UUID, desde: datetime | None = None
    ) -> list[EventoDetalhado]:
        self.curso(aluno_id, curso_id)
        with self._uow() as uow:
            return uow.conteudo.eventos_do_curso(aluno_id, curso_id, desde)

    def prazos(self, aluno_id: UUID, dias: int = 7) -> list[PrazoDetalhado]:
        agora = datetime.now(UTC)
        with self._uow() as uow:
            return uow.conteudo.prazos(aluno_id, agora, agora + timedelta(days=dias))

    def arquivo(self, aluno_id: UUID, arquivo_id: UUID) -> tuple[ArquivoRegistro, Path]:
        with self._uow() as uow:
            registro = uow.conteudo.obter_arquivo(aluno_id, arquivo_id)
        caminho = self._storage.caminho(aluno_id, registro.sha256) if registro else None
        if registro is None or caminho is None or not caminho.is_file():
            raise NotFound("Arquivo não encontrado.")
        return registro, caminho
