from datetime import datetime, time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, EmailStr, Field, SecretStr

from cbot.modules.alunos.domain.entities import Aluno, IdentidadeCanal
from cbot.shared.auth import AlunoId, ContainerDep
from cbot.shared.errors import ValidationFailed
from cbot.shared.security import issue_jwt
from cbot.shared.vocab import Canal, EstadoAutorizacao

router = APIRouter(prefix="/api/v1", tags=["alunos"])


class RegistroIn(BaseModel):
    email: EmailStr
    senha: Annotated[SecretStr, Field(min_length=10, max_length=128)]
    nome: Annotated[str, Field(min_length=2, max_length=120)]


class LoginIn(BaseModel):
    email: EmailStr
    senha: SecretStr


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


class CanvasIn(BaseModel):
    url_base: Annotated[str, Field(max_length=300)]
    token: Annotated[SecretStr, Field(min_length=10, max_length=500)]
    consentimento: bool


class PreferenciasIn(BaseModel):
    canal_preferido: Canal | None = None
    fuso_horario: str | None = None
    hora_resumo: time | None = None


class AlunoOut(BaseModel):
    id: UUID
    email: str
    nome: str
    lms_url_base: str | None
    estado_autorizacao: EstadoAutorizacao
    canal_preferido: Canal
    fuso_horario: str
    hora_resumo: time
    consentimento_em: datetime | None

    @classmethod
    def de(cls, a: Aluno) -> "AlunoOut":
        """Nunca expõe senha_hash nem o token do Canvas."""
        return cls(
            id=a.id, email=a.email, nome=a.nome, lms_url_base=a.lms_url_base,
            estado_autorizacao=a.estado_autorizacao, canal_preferido=a.canal_preferido,
            fuso_horario=a.fuso_horario, hora_resumo=a.hora_resumo, consentimento_em=a.consentimento_em,
        )  # fmt: skip


class CanalIn(BaseModel):
    canal: Canal


class PareamentoOut(BaseModel):
    codigo: str
    expira_em: datetime
    instrucao: str


class IdentidadeOut(BaseModel):
    id: UUID
    canal: Canal
    vinculado: bool
    ultima_mensagem_em: datetime | None

    @classmethod
    def de(cls, i: IdentidadeCanal) -> "IdentidadeOut":
        return cls(
            id=i.id,
            canal=i.canal,
            vinculado=i.verificado_em is not None,
            ultima_mensagem_em=i.ultima_mensagem_in_em,
        )


@router.post("/auth/registro", response_model=AlunoOut, status_code=status.HTTP_201_CREATED)
def registrar(body: RegistroIn, c: ContainerDep) -> AlunoOut:
    aluno = c.alunos.registrar(body.email, body.senha.get_secret_value(), body.nome)
    return AlunoOut.de(aluno)


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, c: ContainerDep) -> TokenOut:
    aluno = c.alunos.autenticar(body.email, body.senha.get_secret_value())
    token = issue_jwt(
        aluno.id, c.settings.jwt_secret.get_secret_value(), c.settings.jwt_expires_minutes
    )
    return TokenOut(access_token=token)


@router.get("/alunos/me", response_model=AlunoOut)
def meu_perfil(aluno_id: AlunoId, c: ContainerDep) -> AlunoOut:
    return AlunoOut.de(c.alunos.obter(aluno_id))


@router.patch("/alunos/me", response_model=AlunoOut)
def atualizar_preferencias(body: PreferenciasIn, aluno_id: AlunoId, c: ContainerDep) -> AlunoOut:
    aluno = c.alunos.atualizar_preferencias(
        aluno_id,
        canal_preferido=body.canal_preferido,
        fuso_horario=body.fuso_horario,
        hora_resumo=body.hora_resumo,
    )
    return AlunoOut.de(aluno)


@router.put("/alunos/me/canvas", response_model=AlunoOut)
def conectar_canvas(body: CanvasIn, aluno_id: AlunoId, c: ContainerDep) -> AlunoOut:
    aluno = c.alunos.conectar_canvas(
        aluno_id, body.url_base, body.token.get_secret_value(), consentimento=body.consentimento
    )
    return AlunoOut.de(aluno)


@router.delete("/alunos/me", status_code=status.HTTP_204_NO_CONTENT)
def excluir_conta(aluno_id: AlunoId, c: ContainerDep) -> Response:
    c.alunos.excluir_conta(aluno_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/alunos/me/canais", response_model=list[IdentidadeOut])
def listar_canais(aluno_id: AlunoId, c: ContainerDep) -> list[IdentidadeOut]:
    return [IdentidadeOut.de(i) for i in c.alunos.listar_identidades(aluno_id)]


@router.post("/alunos/me/canais", response_model=PareamentoOut, status_code=status.HTTP_201_CREATED)
def gerar_pareamento(body: CanalIn, aluno_id: AlunoId, c: ContainerDep) -> PareamentoOut:
    if body.canal not in c.canais:
        raise ValidationFailed(f"O canal {body.canal.value} não está configurado neste servidor.")
    codigo, expira = c.alunos.gerar_codigo_pareamento(aluno_id, body.canal)
    return PareamentoOut(
        codigo=codigo, expira_em=expira,
        instrucao=f"Envie este código ao bot do {body.canal.value} nos próximos 15 minutos.",
    )  # fmt: skip


@router.delete("/alunos/me/canais/{identidade_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_canal(identidade_id: UUID, aluno_id: AlunoId, c: ContainerDep) -> Response:
    c.alunos.remover_identidade(aluno_id, identidade_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
