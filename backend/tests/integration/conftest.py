"""Fixtures compartilhadas pelos testes de integração (PostgreSQL real, LMS/LLM/canais falsos)."""

import base64

import pytest
from fastapi.testclient import TestClient

from cbot.config import Settings
from cbot.container import Container, build_container
from cbot.main import create_app
from cbot.modules.rag.infrastructure.embedders import HashingEmbedder
from cbot.shared.vocab import Canal
from tests.fakes import FakeCanal, FakeLms, ScriptedLlm
from tests.integration.helpers import SENHA


@pytest.fixture
def lms() -> FakeLms:
    return FakeLms()


@pytest.fixture
def telegram() -> FakeCanal:
    return FakeCanal(Canal.TELEGRAM)


@pytest.fixture
def whatsapp() -> FakeCanal:
    return FakeCanal(Canal.WHATSAPP)


@pytest.fixture
def llm() -> ScriptedLlm:
    return ScriptedLlm()


@pytest.fixture
def container(
    db, lms: FakeLms, telegram: FakeCanal, whatsapp: FakeCanal, llm: ScriptedLlm, tmp_path
) -> Container:  # type: ignore[no-untyped-def]
    settings = Settings(
        DATABASE_URL="postgresql://x:x@localhost/x",
        JWT_SECRET="s" * 40,
        STORAGE_DIR=tmp_path,
        TOKEN_ENCRYPTION_KEY=base64.b64encode(b"k" * 32).decode(),
        EMBEDDING_PROVIDER="hashing",
        RAG_MIN_SIMILARITY=0.2,  # o embedder de hashing é bem menos preciso que o bge-m3
    )  # type: ignore[call-arg]
    return build_container(
        settings, db=db, connector_factory=lms.factory, llm=llm, embedder=HashingEmbedder(1024),
        canais={Canal.TELEGRAM: telegram, Canal.WHATSAPP: whatsapp},
    )  # fmt: skip


@pytest.fixture
def client(container: Container) -> TestClient:
    return TestClient(create_app(container))


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    client.post(
        "/api/v1/auth/registro",
        json={"email": "ana@exemplo.com", "senha": SENHA, "nome": "Ana Souza"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": "ana@exemplo.com", "senha": SENHA}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
