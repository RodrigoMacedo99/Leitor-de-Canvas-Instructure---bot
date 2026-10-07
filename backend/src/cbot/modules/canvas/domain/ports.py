from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from cbot.shared.vocab import TipoItem


@dataclass(frozen=True, slots=True)
class PerfilLms:
    usuario_id: int
    nome: str


@dataclass(frozen=True, slots=True)
class CursoLms:
    lms_id: int
    nome: str
    codigo: str | None
    inicio_em: datetime | None
    fim_em: datetime | None


@dataclass(frozen=True, slots=True)
class ArquivoLms:
    lms_id: int
    nome: str
    mime: str
    tamanho: int
    url_download: str


@dataclass(frozen=True, slots=True)
class ItemLms:
    tipo: TipoItem
    externo_id: str
    titulo: str
    secao: str | None
    url: str | None
    prazo_em: datetime | None
    modificado_em: datetime | None
    texto: str | None = None
    arquivo: ArquivoLms | None = None


@dataclass(frozen=True, slots=True)
class ColetaCurso:
    """Resultado da coleta de um curso. `tipos_coletados` diz quais tipos foram lidos por completo:
    um tipo que falhou (ex.: aba de Arquivos oculta) não pode gerar eventos falsos de remoção."""

    itens: list[ItemLms]
    tipos_coletados: frozenset[TipoItem]


# externo_id -> modificado_em já conhecido; evita rebaixar o corpo de páginas inalteradas.
type Conhecidos = dict[str, datetime | None]


class LmsConnector(Protocol):
    """Porta do LMS (PEP 544). Hoje implementada para o Canvas; outro LMS = outro adaptador."""

    def validar_token(self) -> PerfilLms: ...

    def listar_cursos(self) -> list[CursoLms]: ...

    def listar_itens(self, curso_lms_id: int, conhecidos: Conhecidos) -> ColetaCurso: ...

    def baixar_arquivo(self, arquivo: ArquivoLms) -> AbstractContextManager[Iterator[bytes]]: ...


type ConnectorFactory = Callable[[str, str], LmsConnector]
"""Padrão Factory: (url_base, token) -> LmsConnector."""
