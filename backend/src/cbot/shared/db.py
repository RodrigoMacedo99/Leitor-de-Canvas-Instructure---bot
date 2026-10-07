from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

POOL_SIZE = 5
MAX_OVERFLOW = 10


class Database:
    """Fábrica de sessões. Cada `session()` é uma transação (commit ao sair, rollback em erro)."""

    def __init__(self, url: str) -> None:
        self.engine: Engine = create_engine(
            url, pool_size=POOL_SIZE, max_overflow=MAX_OVERFLOW, pool_pre_ping=True
        )
        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._factory() as session, session.begin():
            yield session

    def dispose(self) -> None:
        self.engine.dispose()
