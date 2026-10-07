from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from cbot.shared.vocab import TipoEvento, TipoItem


@dataclass(slots=True)
class Curso:
    aluno_id: UUID
    lms_curso_id: int
    nome: str
    id: UUID = field(default_factory=uuid4)
    codigo: str | None = None
    inicio_em: datetime | None = None
    fim_em: datetime | None = None
    ativa: bool = True
    ultimo_sync_em: datetime | None = None


@dataclass(slots=True)
class ItemCurso:
    aluno_id: UUID
    curso_id: UUID
    tipo: TipoItem
    externo_id: str
    titulo: str
    hash_conteudo: str
    id: UUID = field(default_factory=uuid4)
    secao: str | None = None
    url: str | None = None
    prazo_em: datetime | None = None
    modificado_lms_em: datetime | None = None
    conteudo_texto: str | None = None
    status: str = "ativo"


@dataclass(slots=True)
class ArquivoRegistro:
    aluno_id: UUID
    item_id: UUID
    nome: str
    mime: str
    tamanho: int
    sha256: str
    id: UUID = field(default_factory=uuid4)
    versao: int = 1
    texto_extraido_em: datetime | None = None
    erro_extracao: str | None = None


@dataclass(slots=True)
class EventoMudanca:
    aluno_id: UUID
    item_id: UUID
    tipo: TipoEvento
    id: UUID = field(default_factory=uuid4)
    execucao_id: UUID | None = None
    detalhe: dict[str, Any] = field(default_factory=dict)
    detectado_em: datetime | None = None
    notificado_em: datetime | None = None


@dataclass(frozen=True, slots=True)
class EventoDetalhado:
    """Evento já unido ao item e ao curso, pronto para virar resumo."""

    id: UUID
    tipo: TipoEvento
    detalhe: dict[str, Any]
    detectado_em: datetime
    item_id: UUID
    item_tipo: TipoItem
    titulo: str
    secao: str | None
    url: str | None
    prazo_em: datetime | None
    curso_id: UUID
    curso_nome: str


@dataclass(frozen=True, slots=True)
class PrazoDetalhado:
    item_id: UUID
    titulo: str
    tipo: TipoItem
    prazo_em: datetime
    url: str | None
    curso_id: UUID
    curso_nome: str
