from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from cbot.modules.conteudo.public import Curso, EventoDetalhado, ItemCurso, PrazoDetalhado
from cbot.shared.auth import AlunoId, ContainerDep
from cbot.shared.pagination import DEFAULT_LIMIT, LimitParam, Page, PageParam
from cbot.shared.vocab import TipoEvento, TipoItem

router = APIRouter(prefix="/api/v1", tags=["conteudo"])


class CursoOut(BaseModel):
    id: UUID
    lms_curso_id: int
    nome: str
    codigo: str | None
    ativa: bool
    ultimo_sync_em: datetime | None

    @classmethod
    def de(cls, c: Curso) -> "CursoOut":
        return cls(
            id=c.id,
            lms_curso_id=c.lms_curso_id,
            nome=c.nome,
            codigo=c.codigo,
            ativa=c.ativa,
            ultimo_sync_em=c.ultimo_sync_em,
        )


class ItemOut(BaseModel):
    id: UUID
    tipo: TipoItem
    titulo: str
    secao: str | None
    url: str | None
    prazo_em: datetime | None
    modificado_lms_em: datetime | None

    @classmethod
    def de(cls, i: ItemCurso) -> "ItemOut":
        return cls(
            id=i.id,
            tipo=i.tipo,
            titulo=i.titulo,
            secao=i.secao,
            url=i.url,
            prazo_em=i.prazo_em,
            modificado_lms_em=i.modificado_lms_em,
        )


class NovidadeOut(BaseModel):
    id: UUID
    tipo: TipoEvento
    item_id: UUID
    item_tipo: TipoItem
    titulo: str
    curso: str
    detalhe: dict[str, Any]
    detectado_em: datetime

    @classmethod
    def de(cls, e: EventoDetalhado) -> "NovidadeOut":
        return cls(
            id=e.id,
            tipo=e.tipo,
            item_id=e.item_id,
            item_tipo=e.item_tipo,
            titulo=e.titulo,
            curso=e.curso_nome,
            detalhe=e.detalhe,
            detectado_em=e.detectado_em,
        )


class PrazoOut(BaseModel):
    item_id: UUID
    titulo: str
    tipo: TipoItem
    prazo_em: datetime
    url: str | None
    curso: str

    @classmethod
    def de(cls, p: PrazoDetalhado) -> "PrazoOut":
        return cls(
            item_id=p.item_id,
            titulo=p.titulo,
            tipo=p.tipo,
            prazo_em=p.prazo_em,
            url=p.url,
            curso=p.curso_nome,
        )


@router.get("/cursos", response_model=Page[CursoOut])
def listar_cursos(aluno_id: AlunoId, c: ContainerDep) -> Page[CursoOut]:
    cursos = c.consultas.cursos(aluno_id)
    return Page(
        data=[CursoOut.de(x) for x in cursos], total=len(cursos), page=1, limit=max(len(cursos), 1)
    )


@router.get("/cursos/{curso_id}", response_model=CursoOut)
def obter_curso(curso_id: UUID, aluno_id: AlunoId, c: ContainerDep) -> CursoOut:
    return CursoOut.de(c.consultas.curso(aluno_id, curso_id))


@router.get("/cursos/{curso_id}/itens", response_model=Page[ItemOut])
def listar_itens(
    curso_id: UUID, aluno_id: AlunoId, c: ContainerDep, tipo: TipoItem | None = None,
    desde: datetime | None = None, page: PageParam = 1, limit: LimitParam = DEFAULT_LIMIT,
) -> Page[ItemOut]:  # fmt: skip
    itens, total = c.consultas.itens(
        aluno_id, curso_id, tipo=tipo, desde=desde, pagina=page, limite=limit
    )
    return Page(data=[ItemOut.de(i) for i in itens], total=total, page=page, limit=limit)


@router.get("/cursos/{curso_id}/novidades", response_model=list[NovidadeOut])
def listar_novidades(
    curso_id: UUID, aluno_id: AlunoId, c: ContainerDep, desde: datetime | None = None
) -> list[NovidadeOut]:
    return [NovidadeOut.de(e) for e in c.consultas.novidades(aluno_id, curso_id, desde)]


@router.get("/prazos", response_model=list[PrazoOut])
def listar_prazos(
    aluno_id: AlunoId, c: ContainerDep, dias: Annotated[int, Query(ge=1, le=60)] = 7
) -> list[PrazoOut]:
    return [PrazoOut.de(p) for p in c.consultas.prazos(aluno_id, dias)]


@router.get("/arquivos/{arquivo_id}/download")
def baixar_arquivo(arquivo_id: UUID, aluno_id: AlunoId, c: ContainerDep) -> FileResponse:
    registro, caminho = c.consultas.arquivo(aluno_id, arquivo_id)
    return FileResponse(caminho, media_type=registro.mime, filename=registro.nome)
