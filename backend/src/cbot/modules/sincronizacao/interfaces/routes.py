from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel

from cbot.modules.sincronizacao.application.worker import JOB_SYNC
from cbot.modules.sincronizacao.domain.ports import ExecucaoSync
from cbot.shared.auth import AlunoId, ContainerDep
from cbot.shared.errors import Conflict, NotFound
from cbot.shared.pagination import DEFAULT_LIMIT, LimitParam, Page, PageParam
from cbot.shared.vocab import Gatilho, StatusExecucao

router = APIRouter(prefix="/api/v1", tags=["sincronizacao"])


class ExecucaoOut(BaseModel):
    id: UUID
    gatilho: Gatilho
    status: StatusExecucao
    iniciada_em: datetime | None
    finalizada_em: datetime | None
    estatisticas: dict[str, Any]

    @classmethod
    def de(cls, e: ExecucaoSync) -> "ExecucaoOut":
        return cls(
            id=e.id,
            gatilho=e.gatilho,
            status=e.status,
            iniciada_em=e.iniciada_em,
            finalizada_em=e.finalizada_em,
            estatisticas=e.estatisticas,
        )


class JobOut(BaseModel):
    job_id: UUID


@router.post("/sync", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def disparar_sync(aluno_id: AlunoId, c: ContainerDep) -> JobOut:
    with c.uow() as uow:
        if uow.execucoes.em_andamento(aluno_id):
            raise Conflict("Já existe uma sincronização em andamento.")
        job_id = uow.jobs.enfileirar(
            JOB_SYNC, aluno_id, {"gatilho": Gatilho.MANUAL.value}, unico=True
        )
    if job_id is None:
        raise Conflict("Já existe uma sincronização na fila.")
    return JobOut(job_id=job_id)


@router.get("/sync/execucoes", response_model=Page[ExecucaoOut])
def listar_execucoes(
    aluno_id: AlunoId, c: ContainerDep, page: PageParam = 1, limit: LimitParam = DEFAULT_LIMIT
) -> Page[ExecucaoOut]:
    with c.uow() as uow:
        execucoes, total = uow.execucoes.listar(aluno_id, limit, (page - 1) * limit)
    return Page(data=[ExecucaoOut.de(e) for e in execucoes], total=total, page=page, limit=limit)


@router.get("/sync/execucoes/{execucao_id}", response_model=ExecucaoOut)
def obter_execucao(execucao_id: UUID, aluno_id: AlunoId, c: ContainerDep) -> ExecucaoOut:
    with c.uow() as uow:
        execucao = uow.execucoes.obter(aluno_id, execucao_id)
    if execucao is None:
        raise NotFound("Execução não encontrada.")
    return ExecucaoOut.de(execucao)
