import os

from alembic import context
from sqlalchemy import create_engine, pool

DRIVER_PREFIX = "postgresql+psycopg://"


def _database_url() -> str:
    url = os.environ["DATABASE_URL"]
    for scheme in ("postgresql://", "postgres://"):
        if url.startswith(scheme):
            return DRIVER_PREFIX + url[len(scheme) :]
    return url


def run_migrations() -> None:
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
