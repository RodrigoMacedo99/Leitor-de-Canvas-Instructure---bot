"""Padrão Observer: barramento de eventos de domínio em processo.

Módulos não se importam entre si (regra do monólito modular); eles publicam e
assinam eventos. Handlers falhos são isolados para não derrubar quem publicou.
"""

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    aluno_id: UUID


@dataclass(frozen=True, slots=True)
class ItemSincronizado(DomainEvent):
    """Item novo ou alterado cujo conteúdo precisa (re)entrar no índice de busca."""

    item_id: UUID
    curso_id: UUID
    curso_nome: str
    titulo: str
    texto: str | None
    secao: str | None = None
    url: str | None = None
    arquivo_id: UUID | None = None
    arquivo_caminho: str | None = None
    arquivo_mime: str | None = None
    arquivo_nome: str | None = None


@dataclass(frozen=True, slots=True)
class ItemRemovido(DomainEvent):
    item_id: UUID


@dataclass(frozen=True, slots=True)
class ArquivoProcessado(DomainEvent):
    """O texto do arquivo foi extraído (ou falhou, com `erro`)."""

    arquivo_id: UUID
    erro: str | None = None


@dataclass(frozen=True, slots=True)
class ReautorizacaoNecessaria(DomainEvent):
    """O token do Canvas foi recusado: o aluno precisa gerar outro."""


@dataclass(frozen=True, slots=True)
class ContaExcluida(DomainEvent):
    """Direito de eliminação (LGPD): quem guarda dados do aluno fora do banco deve apagá-los."""


class EventBus:
    """Publica eventos para todos os handlers assinados para o tipo exato."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Callable[[DomainEvent], None]]] = defaultdict(
            list
        )

    def subscribe[E: DomainEvent](self, event_type: type[E], handler: Callable[[E], None]) -> None:
        self._handlers[event_type].append(handler)  # type: ignore[arg-type]

    def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers[type(event)]:
            try:
                handler(event)
            except Exception:
                logger.exception("handler falhou para %s", type(event).__name__)
