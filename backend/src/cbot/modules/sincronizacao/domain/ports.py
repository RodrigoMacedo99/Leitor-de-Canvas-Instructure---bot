from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from cbot.modules.conteudo.public import ArquivoGravado as ArquivoArmazenado
from cbot.shared.vocab import Gatilho, StatusExecucao


@dataclass(slots=True)
class ExecucaoSync:
    aluno_id: UUID
    gatilho: Gatilho
    id: UUID = field(default_factory=uuid4)
    status: StatusExecucao = StatusExecucao.EXECUTANDO
    iniciada_em: datetime | None = None
    finalizada_em: datetime | None = None
    estatisticas: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Job:
    id: UUID
    tipo: str
    aluno_id: UUID | None
    payload: dict[str, Any]
    tentativas: int


class CredenciaisLms(Protocol):
    """Fornecida pelo módulo `alunos`: nunca expõe o token cifrado, só o decifrado em memória."""

    def credenciais_lms(self, aluno_id: UUID) -> tuple[str, str]: ...

    def exigir_reautorizacao(self, aluno_id: UUID) -> None: ...


class Armazenamento(Protocol):
    def gravar(
        self, aluno_id: UUID, chunks: Iterator[bytes], max_bytes: int
    ) -> ArquivoArmazenado: ...


class ExecucaoRepository(Protocol):
    def iniciar(self, execucao: ExecucaoSync) -> None: ...

    def finalizar(self, execucao: ExecucaoSync) -> None: ...

    def listar(
        self, aluno_id: UUID, limite: int, deslocamento: int
    ) -> tuple[list[ExecucaoSync], int]: ...

    def obter(self, aluno_id: UUID, execucao_id: UUID) -> ExecucaoSync | None: ...

    def em_andamento(self, aluno_id: UUID) -> bool: ...


class JobQueue(Protocol):
    def enfileirar(
        self,
        tipo: str,
        aluno_id: UUID | None,
        payload: dict[str, Any],
        executar_em: datetime | None = None,
        *,
        unico: bool = False,
        nao_repetir_desde: datetime | None = None,
    ) -> UUID | None:
        """`unico`: não duplica job ativo; `nao_repetir_desde`: não cria se já houve um desde então."""
        ...  # fmt: skip

    def reservar(self, limite: int, lease_segundos: int) -> list[Job]: ...

    def concluir(self, job_id: UUID) -> None: ...

    def falhar(self, job_id: UUID, erro: str, max_tentativas: int) -> None: ...


__all__ = [
    "ArquivoArmazenado",
    "Armazenamento",
    "CredenciaisLms",
    "ExecucaoRepository",
    "ExecucaoSync",
    "Job",
    "JobQueue",
]
