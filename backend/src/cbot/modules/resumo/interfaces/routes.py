from dataclasses import asdict
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from cbot.modules.rag.public import Fonte
from cbot.shared.auth import AlunoId, ContainerDep
from cbot.shared.errors import ValidationFailed
from cbot.shared.pagination import DEFAULT_LIMIT, LimitParam, Page, PageParam

router = APIRouter(prefix="/api/v1", tags=["resumos"])


class ResumoOut(BaseModel):
    id: UUID
    periodo_ini: datetime
    periodo_fim: datetime
    texto: str
    canal: str | None
    enviado_em: datetime | None


class ResumoIn(BaseModel):
    enviar: bool = False


class ResumoGeradoOut(BaseModel):
    texto: str


class PerguntaIn(BaseModel):
    pergunta: Annotated[str, Field(min_length=3, max_length=2000)]
    curso_id: UUID | None = None


class FonteOut(BaseModel):
    n: int
    curso: str | None
    item: str | None
    arquivo: str | None
    pagina: int | None
    url: str | None

    @classmethod
    def de(cls, f: Fonte) -> "FonteOut":
        return cls(
            n=f.numero, curso=f.curso, item=f.item, arquivo=f.arquivo, pagina=f.pagina, url=f.url
        )


class RespostaOut(BaseModel):
    resposta: str
    fundamentada: bool
    fontes: list[FonteOut]


@router.get("/resumos", response_model=Page[ResumoOut])
def listar_resumos(
    aluno_id: AlunoId, c: ContainerDep, page: PageParam = 1, limit: LimitParam = DEFAULT_LIMIT
) -> Page[ResumoOut]:
    with c.uow() as uow:
        registros, total = uow.resumos.listar(aluno_id, limit, (page - 1) * limit)
    return Page(
        data=[ResumoOut(**asdict(r)) for r in registros], total=total, page=page, limit=limit
    )


@router.post("/resumos", response_model=ResumoGeradoOut, status_code=status.HTTP_201_CREATED)
def gerar_resumo(body: ResumoIn, aluno_id: AlunoId, c: ContainerDep) -> ResumoGeradoOut:
    if body.enviar:
        resultado = c.servico_resumo.enviar_agendado(aluno_id)
        return ResumoGeradoOut(texto=f"Envio: {resultado.value}")
    return ResumoGeradoOut(texto=c.servico_resumo.gerar_texto(aluno_id))


@router.post("/perguntas", response_model=RespostaOut)
def perguntar(body: PerguntaIn, aluno_id: AlunoId, c: ContainerDep) -> RespostaOut:
    """Faz uma pergunta ao RAG sem passar pelo WhatsApp/Telegram (testes e painel)."""
    if c.responder is None:
        raise ValidationFailed("Configure ANTHROPIC_API_KEY para usar perguntas com IA.")
    resposta = c.responder.responder(aluno_id, body.pergunta, curso_id=body.curso_id)
    return RespostaOut(
        resposta=resposta.texto, fundamentada=resposta.fundamentada,
        fontes=[FonteOut.de(f) for f in resposta.fontes],
    )  # fmt: skip
