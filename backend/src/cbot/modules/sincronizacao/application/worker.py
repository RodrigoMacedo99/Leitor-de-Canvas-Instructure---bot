"""Worker de jobs (fila em PostgreSQL) e agendador periódico."""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from cbot.modules.alunos.domain.entities import Aluno
from cbot.modules.sincronizacao.domain.ports import Job, JobQueue
from cbot.shared.vocab import Gatilho

logger = logging.getLogger(__name__)
JOB_SYNC = "sync_aluno"
JOB_RESUMO = "resumo_aluno"
LEASE_SECONDS = 15 * 60
MAX_ATTEMPTS = 3
BATCH = 5

type Handler = Callable[[Job], None]


class JobsUow(Protocol):
    @property
    def jobs(self) -> JobQueue: ...


type JobsUowFactory = Callable[[], AbstractContextManager[JobsUow]]


class AlunosAgendaveis(Protocol):
    def listar_sincronizaveis(self) -> list[Aluno]: ...


class JobWorker:
    """Command: cada tipo de job é um handler registrado. Falhas viram retentativa com backoff."""

    def __init__(self, uow: JobsUowFactory, handlers: dict[str, Handler]) -> None:
        self._uow = uow
        self._handlers = handlers

    def run_once(self) -> int:
        with self._uow() as uow:
            jobs = uow.jobs.reservar(BATCH, LEASE_SECONDS)
        for job in jobs:
            self._executar(job)
        return len(jobs)

    def _executar(self, job: Job) -> None:
        handler = self._handlers.get(job.tipo)
        try:
            if handler is None:
                raise LookupError(f"sem handler para o job {job.tipo}")
            handler(job)
        except Exception as exc:
            logger.exception("job %s (%s) falhou", job.id, job.tipo)
            with self._uow() as uow:
                uow.jobs.falhar(job.id, f"{type(exc).__name__}: {exc}", MAX_ATTEMPTS)
            return
        with self._uow() as uow:
            uow.jobs.concluir(job.id)


class Agendador:
    """Enfileira sincronizações periódicas e o resumo diário no horário de cada aluno."""

    def __init__(self, uow: JobsUowFactory, alunos: AlunosAgendaveis) -> None:
        self._uow = uow
        self._alunos = alunos

    def enfileirar_syncs(self) -> int:
        enfileirados = 0
        for aluno in self._alunos.listar_sincronizaveis():
            with self._uow() as uow:
                criado = uow.jobs.enfileirar(
                    JOB_SYNC, aluno.id, {"gatilho": Gatilho.AGENDADO.value}, unico=True
                )
            enfileirados += criado is not None
        return enfileirados

    def enfileirar_resumos(self, agora: datetime | None = None) -> int:
        agora = agora or datetime.now(UTC)
        enfileirados = 0
        for aluno in self._alunos.listar_sincronizaveis():
            local = agora.astimezone(ZoneInfo(aluno.fuso_horario))
            if local.time() < aluno.hora_resumo:
                continue
            inicio_do_dia = local.replace(hour=0, minute=0, second=0, microsecond=0)
            with self._uow() as uow:
                criado = uow.jobs.enfileirar(
                    JOB_RESUMO, aluno.id, {}, nao_repetir_desde=inicio_do_dia
                )
            enfileirados += criado is not None
        return enfileirados


def iniciar_scheduler(
    agendador: Agendador, worker: JobWorker, sync_interval_hours: float
) -> BackgroundScheduler:  # pragma: no cover - integração com APScheduler
    scheduler = BackgroundScheduler(timezone=UTC)
    scheduler.add_job(agendador.enfileirar_syncs, "interval", hours=sync_interval_hours, id="syncs")
    scheduler.add_job(agendador.enfileirar_resumos, "interval", minutes=1, id="resumos")
    scheduler.add_job(worker.run_once, "interval", seconds=5, id="worker", max_instances=1)
    scheduler.start()
    return scheduler
