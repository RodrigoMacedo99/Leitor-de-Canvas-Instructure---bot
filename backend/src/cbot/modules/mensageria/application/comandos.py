from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from cbot.modules.conteudo.public import Curso, PrazoDetalhado
from cbot.modules.mensageria.application.tratar_mensagem import Comando, Contexto
from cbot.modules.sincronizacao.domain.ports import JobQueue
from cbot.shared.errors import ValidationFailed

DEFAULT_DEADLINE_DAYS = 7
MAX_DEADLINE_DAYS = 60
FORGET_CONFIRMATION = "confirmar"
DATE_FMT = "%d/%m %H:%M"


class ConsultasPort(Protocol):
    def cursos(self, aluno_id: UUID) -> list[Curso]: ...

    def prazos(self, aluno_id: UUID, dias: int = 7) -> list[PrazoDetalhado]: ...


class ResumoPort(Protocol):
    def gerar_texto(self, aluno_id: UUID) -> str: ...


class ContaPort(Protocol):
    def excluir_conta(self, aluno_id: UUID) -> None: ...


class FusoPort(Protocol):
    def fuso_do_aluno(self, aluno_id: UUID) -> str: ...


class JobsUow(Protocol):
    @property
    def jobs(self) -> JobQueue: ...


type JobsUowFactory = Callable[[], AbstractContextManager[JobsUow]]


def formatar_data(dt: datetime, fuso: str) -> str:
    return dt.astimezone(ZoneInfo(fuso)).strftime(DATE_FMT)


class ComandoAjuda:
    nome, descricao = "/ajuda", "lista os comandos"

    def __init__(self, listar: Callable[[], str]) -> None:
        self._listar = listar

    def executar(self, ctx: Contexto, argumento: str) -> str:
        return (
            "Posso responder dúvidas sobre o material dos seus cursos (é só escrever a pergunta) "
            f"e também:\n{self._listar()}"
        )


class ComandoCursos:
    nome, descricao = "/cursos", "lista seus cursos sincronizados"

    def __init__(self, consultas: ConsultasPort) -> None:
        self._consultas = consultas

    def executar(self, ctx: Contexto, argumento: str) -> str:
        cursos = self._consultas.cursos(ctx.aluno_id)
        if not cursos:
            return "Ainda não há cursos sincronizados. Use /sync."
        return "Seus cursos:\n" + "\n".join(f"- {c.nome}" for c in cursos)


class ComandoPrazos:
    nome, descricao = "/prazos", "prazos dos próximos dias (ex.: /prazos 14)"

    def __init__(self, consultas: ConsultasPort, fusos: FusoPort) -> None:
        self._consultas = consultas
        self._fusos = fusos

    def executar(self, ctx: Contexto, argumento: str) -> str:
        dias = self._dias(argumento)
        prazos = self._consultas.prazos(ctx.aluno_id, dias)
        if not prazos:
            return f"Nenhum prazo nos próximos {dias} dias."
        fuso = self._fusos.fuso_do_aluno(ctx.aluno_id)
        linhas = [
            f"- {formatar_data(p.prazo_em, fuso)} · {p.titulo} ({p.curso_nome})" for p in prazos
        ]
        return f"Prazos dos próximos {dias} dias:\n" + "\n".join(linhas)

    @staticmethod
    def _dias(argumento: str) -> int:
        if not argumento:
            return DEFAULT_DEADLINE_DAYS
        if not argumento.isdigit() or not 0 < int(argumento) <= MAX_DEADLINE_DAYS:
            raise ValidationFailed(f"Use /prazos com um número de 1 a {MAX_DEADLINE_DAYS}.")
        return int(argumento)


class ComandoResumo:
    nome, descricao = "/resumo", "novidades e prazos agora"

    def __init__(self, resumo: ResumoPort) -> None:
        self._resumo = resumo

    def executar(self, ctx: Contexto, argumento: str) -> str:
        return self._resumo.gerar_texto(ctx.aluno_id)


class ComandoSync:
    nome, descricao = "/sync", "sincroniza os cursos agora"

    def __init__(self, uow: JobsUowFactory) -> None:
        self._uow = uow

    def executar(self, ctx: Contexto, argumento: str) -> str:
        with self._uow() as uow:
            novo = uow.jobs.enfileirar(
                "sync_aluno", ctx.aluno_id, {"gatilho": "manual"}, unico=True
            )
        if novo is None:
            return "Já há uma sincronização em andamento. Aguarde."
        return "Sincronização iniciada. Aviso quando houver novidades."


class ComandoEsquecer:
    nome, descricao = "/esquecer", "apaga todos os seus dados (peça com /esquecer confirmar)"

    def __init__(self, conta: ContaPort) -> None:
        self._conta = conta

    def executar(self, ctx: Contexto, argumento: str) -> str:
        if argumento.lower() != FORGET_CONFIRMATION:
            return "Isso apaga seus dados, arquivos e vínculos de forma definitiva. Para confirmar envie: /esquecer confirmar"
        self._conta.excluir_conta(ctx.aluno_id)
        return "Seus dados foram apagados. Obrigado por usar o CBOT."


def comandos_padrao(
    consultas: ConsultasPort, fusos: FusoPort, resumo: ResumoPort, uow: JobsUowFactory, conta: ContaPort,
) -> list[Comando]:  # fmt: skip
    lista: list[Comando] = []
    ajuda = ComandoAjuda(lambda: "\n".join(f"{c.nome} - {c.descricao}" for c in lista))
    lista.extend(
        [ajuda, ComandoCursos(consultas), ComandoPrazos(consultas, fusos), ComandoResumo(resumo),
         ComandoSync(uow), ComandoEsquecer(conta)]
    )  # fmt: skip
    return lista
