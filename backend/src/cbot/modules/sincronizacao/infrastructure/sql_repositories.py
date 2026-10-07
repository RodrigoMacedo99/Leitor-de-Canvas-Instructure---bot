import json
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from cbot.modules.sincronizacao.domain.ports import ExecucaoSync, Job
from cbot.shared.vocab import Gatilho, StatusExecucao

BACKOFF_BASE_SECONDS = 30
_EXEC_COLS = "id, aluno_id, gatilho, status, iniciada_em, finalizada_em, estatisticas"


def _execucao(r: Any) -> ExecucaoSync:
    return ExecucaoSync(
        id=r["id"], aluno_id=r["aluno_id"], gatilho=Gatilho(r["gatilho"]),
        status=StatusExecucao(r["status"]), iniciada_em=r["iniciada_em"],
        finalizada_em=r["finalizada_em"], estatisticas=r["estatisticas"],
    )  # fmt: skip


class SqlExecucaoRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def iniciar(self, execucao: ExecucaoSync) -> None:
        self._s.execute(
            text("INSERT INTO execucoes_sync (id, aluno_id, gatilho) VALUES (:i, :a, :g)"),
            {"i": execucao.id, "a": execucao.aluno_id, "g": execucao.gatilho.value},
        )

    def finalizar(self, execucao: ExecucaoSync) -> None:
        self._s.execute(
            text(
                "UPDATE execucoes_sync SET status = :s, finalizada_em = now(), "
                "estatisticas = CAST(:e AS jsonb) WHERE id = :i AND aluno_id = :a"
            ),
            {"s": execucao.status.value, "e": json.dumps(execucao.estatisticas),
             "i": execucao.id, "a": execucao.aluno_id},
        )  # fmt: skip

    def listar(
        self, aluno_id: UUID, limite: int, deslocamento: int
    ) -> tuple[list[ExecucaoSync], int]:
        total = self._s.execute(
            text("SELECT count(*) FROM execucoes_sync WHERE aluno_id = :a"), {"a": aluno_id}
        ).scalar_one()
        rows = self._s.execute(
            text(
                f"SELECT {_EXEC_COLS} FROM execucoes_sync WHERE aluno_id = :a "
                "ORDER BY iniciada_em DESC LIMIT :l OFFSET :o"
            ),
            {"a": aluno_id, "l": limite, "o": deslocamento},
        ).mappings()
        return [_execucao(r) for r in rows], int(total)

    def obter(self, aluno_id: UUID, execucao_id: UUID) -> ExecucaoSync | None:
        row = (
            self._s.execute(
                text(f"SELECT {_EXEC_COLS} FROM execucoes_sync WHERE id = :i AND aluno_id = :a"),
                {"i": execucao_id, "a": aluno_id},
            )
            .mappings()
            .first()
        )
        return _execucao(row) if row else None

    def em_andamento(self, aluno_id: UUID) -> bool:
        return bool(
            self._s.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM execucoes_sync WHERE aluno_id = :a "
                    "AND status = 'executando' AND iniciada_em > now() - interval '2 hours')"
                ),
                {"a": aluno_id},
            ).scalar_one()
        )


class SqlJobQueue:
    """Fila em PostgreSQL: `FOR UPDATE SKIP LOCKED` permite vários workers sem duplicar job."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def enfileirar(
        self, tipo: str, aluno_id: UUID | None, payload: dict[str, Any],
        executar_em: datetime | None = None, *, unico: bool = False,
        nao_repetir_desde: datetime | None = None,
    ) -> UUID | None:  # fmt: skip
        if unico and self._existe_ativo(tipo, aluno_id):
            return None
        if nao_repetir_desde and self._existe_desde(tipo, aluno_id, nao_repetir_desde):
            return None
        job_id = self._s.execute(
            text(
                "INSERT INTO jobs (tipo, aluno_id, payload, executar_em) "
                "VALUES (:t, :a, CAST(:p AS jsonb), COALESCE(:e, now())) RETURNING id"
            ),
            {"t": tipo, "a": aluno_id, "p": json.dumps(payload), "e": executar_em},
        ).scalar_one()
        return cast(UUID, job_id)

    def _existe_ativo(self, tipo: str, aluno_id: UUID | None) -> bool:
        return bool(
            self._s.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM jobs WHERE tipo = :t AND aluno_id IS NOT DISTINCT FROM CAST(:a AS uuid) "
                    "AND estado IN ('pendente', 'executando'))"
                ),
                {"t": tipo, "a": aluno_id},
            ).scalar_one()
        )

    def _existe_desde(self, tipo: str, aluno_id: UUID | None, desde: datetime) -> bool:
        return bool(
            self._s.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM jobs WHERE tipo = :t "
                    "AND aluno_id IS NOT DISTINCT FROM CAST(:a AS uuid) AND criado_em >= :d)"
                ),
                {"t": tipo, "a": aluno_id, "d": desde},
            ).scalar_one()
        )

    def reservar(self, limite: int, lease_segundos: int) -> list[Job]:
        rows = self._s.execute(
            text(
                "UPDATE jobs SET estado = 'executando', tentativas = tentativas + 1, "
                "bloqueado_ate = now() + make_interval(secs => :lease), atualizado_em = now() "
                "WHERE id IN (SELECT id FROM jobs WHERE (estado = 'pendente' AND executar_em <= now()) "
                "OR (estado = 'executando' AND bloqueado_ate < now()) "
                "ORDER BY executar_em FOR UPDATE SKIP LOCKED LIMIT :n) "
                "RETURNING id, tipo, aluno_id, payload, tentativas"
            ),
            {"lease": lease_segundos, "n": limite},
        ).mappings()
        return [Job(r["id"], r["tipo"], r["aluno_id"], r["payload"], r["tentativas"]) for r in rows]

    def concluir(self, job_id: UUID) -> None:
        self._s.execute(
            text(
                "UPDATE jobs SET estado = 'concluido', bloqueado_ate = NULL, atualizado_em = now() WHERE id = :i"
            ),
            {"i": job_id},
        )

    def falhar(self, job_id: UUID, erro: str, max_tentativas: int) -> None:
        self._s.execute(
            text(
                "UPDATE jobs SET erro = :e, bloqueado_ate = NULL, atualizado_em = now(), "
                "estado = CASE WHEN tentativas >= :m THEN 'morto' ELSE 'pendente' END, "
                "executar_em = now() + make_interval(secs => :base * power(2, tentativas)) "
                "WHERE id = :i"
            ),
            {"e": erro[:500], "m": max_tentativas, "base": BACKOFF_BASE_SECONDS, "i": job_id},
        )
