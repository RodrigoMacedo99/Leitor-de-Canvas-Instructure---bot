import base64
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-123")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", base64.b64encode(b"k" * 32).decode())
os.environ.setdefault("DATABASE_URL", "postgresql://unused@localhost:5432/unused")

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testes não podem dormir no backoff do tenacity."""
    from tenacity import wait_none

    from cbot.modules.canvas.infrastructure import client

    monkeypatch.setattr(client, "BACKOFF", wait_none())


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """PostgreSQL real com pgvector: TEST_DATABASE_URL (CI) ou um servidor embutido (pgserver)."""
    external = os.environ.get("TEST_DATABASE_URL")
    if external:
        yield external
        return
    import pgserver

    with tempfile.TemporaryDirectory() as tmp:
        server = pgserver.get_server(tmp, cleanup_mode="stop")
        yield server.get_uri()
        server.cleanup()


@pytest.fixture(scope="session")
def migrated_url(database_url: str) -> str:
    from alembic import command
    from alembic.config import Config

    os.environ["DATABASE_URL"] = database_url
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg, "head")
    return database_url


@pytest.fixture(scope="session")
def database(migrated_url: str) -> Iterator["Database"]:  # noqa: F821
    from cbot.config import DRIVER_URL_PREFIX
    from cbot.shared.db import Database

    db = Database(migrated_url.replace("postgresql://", DRIVER_URL_PREFIX, 1))
    yield db
    db.dispose()


@pytest.fixture
def db(database: "Database"):  # type: ignore[no-untyped-def]  # noqa: F821
    """Banco limpo a cada teste de integração (TRUNCATE em cascata)."""
    from sqlalchemy import text

    with database.session() as s:
        s.execute(text("TRUNCATE alunos, jobs CASCADE"))
    return database
