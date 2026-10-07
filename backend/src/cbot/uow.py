"""Padrão Unit of Work: uma sessão/transação que entrega todos os repositórios SQL.

Os casos de uso declaram só o pedaço que usam (Protocols por módulo); esta classe, na raiz de
composição, satisfaz todos eles estruturalmente.
"""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy.orm import Session

from cbot.modules.alunos.infrastructure.sql_repository import SqlAlunoRepository
from cbot.modules.chat.infrastructure.sql_mensagens import SqlMensagemRepository
from cbot.modules.conteudo.infrastructure.sql_repository import SqlConteudoRepository
from cbot.modules.rag.infrastructure.sql_trecho_repository import SqlTrechoRepository
from cbot.modules.resumo.infrastructure.sql_resumos import SqlResumoRepository
from cbot.modules.sincronizacao.infrastructure.sql_repositories import (
    SqlExecucaoRepository,
    SqlJobQueue,
)
from cbot.shared.db import Database


class SqlUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.alunos = SqlAlunoRepository(session)
        self.conteudo = SqlConteudoRepository(session)
        self.trechos = SqlTrechoRepository(session)
        self.execucoes = SqlExecucaoRepository(session)
        self.jobs = SqlJobQueue(session)
        self.mensagens = SqlMensagemRepository(session)
        self.resumos = SqlResumoRepository(session)


def make_uow_factory(db: Database) -> Callable[[], AbstractContextManager[SqlUnitOfWork]]:
    """Padrão Factory: cada chamada abre uma transação e entrega um `SqlUnitOfWork`."""

    @contextmanager
    def factory() -> Iterator[SqlUnitOfWork]:
        with db.session() as session:
            yield SqlUnitOfWork(session)

    return factory
