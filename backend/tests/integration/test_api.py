"""API HTTP + webhooks + comandos do bot, ponta a ponta com PostgreSQL real."""

import json

import pytest
from fastapi.testclient import TestClient

from cbot.container import Container
from cbot.shared.vocab import TipoItem
from tests.fakes import FakeCanal, FakeLms, ScriptedLlm, item_texto, tool_call, tool_results

pytestmark = pytest.mark.integration

from tests.integration.helpers import SENHA, conectar, mensagem, parear  # noqa: E402


def test_register_login_and_profile_never_leaks_secrets(
    client: TestClient, auth: dict[str, str]
) -> None:
    conectar(client, auth)
    perfil = client.get("/api/v1/alunos/me", headers=auth).json()
    assert (
        perfil["estado_autorizacao"] == "ativa"
        and perfil["lms_url_base"] == "https://escola.instructure.com"
    )
    assert "senha_hash" not in perfil and "token" not in json.dumps(perfil).replace(
        "estado_autorizacao", ""
    )


def test_protected_routes_require_jwt(client: TestClient) -> None:
    r = client.get("/api/v1/cursos")
    assert r.status_code == 401 and r.headers["content-type"].startswith("application/problem+json")
    assert client.get("/api/v1/cursos", headers={"Authorization": "Bearer lixo"}).status_code == 401


def test_wrong_password_and_duplicate_email(client: TestClient, auth: dict[str, str]) -> None:
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "ana@exemplo.com", "senha": "senha-errada-123"}
        ).status_code
        == 401
    )
    dup = client.post(
        "/api/v1/auth/registro", json={"email": "ANA@exemplo.com", "senha": SENHA, "nome": "Outra"}
    )
    assert dup.status_code == 409
    fraca = client.post(
        "/api/v1/auth/registro", json={"email": "x@exemplo.com", "senha": "curta", "nome": "X Y"}
    )
    assert fraca.status_code == 422


def test_canvas_connection_requires_consent_and_valid_token(
    client: TestClient, auth: dict[str, str], lms: FakeLms
) -> None:
    corpo = {
        "url_base": "https://escola.instructure.com",
        "token": "token-do-canvas-123",
        "consentimento": False,
    }
    assert client.put("/api/v1/alunos/me/canvas", headers=auth, json=corpo).status_code == 422
    lms.token_valido = False
    r = client.put("/api/v1/alunos/me/canvas", headers=auth, json={**corpo, "consentimento": True})
    assert r.status_code == 422 and "recus" in r.json()["detail"]
    ssrf = client.put(
        "/api/v1/alunos/me/canvas",
        headers=auth,
        json={**corpo, "consentimento": True, "url_base": "https://10.0.0.1"},
    )
    assert ssrf.status_code == 422


def test_sync_endpoint_enqueues_and_worker_runs_it(
    client: TestClient, auth: dict[str, str], container: Container, lms: FakeLms
) -> None:
    conectar(client, auth)
    lms.itens[1] = [
        item_texto("assignment:5", "Lista 1", "Resolva os exercícios.", tipo=TipoItem.TAREFA)
    ]
    assert client.post("/api/v1/sync", headers=auth).status_code == 202
    assert client.post("/api/v1/sync", headers=auth).status_code == 409

    assert container.worker.run_once() == 1

    cursos = client.get("/api/v1/cursos", headers=auth).json()["data"]
    assert [c["nome"] for c in cursos] == ["Redes de Computadores"]
    itens = client.get(f"/api/v1/cursos/{cursos[0]['id']}/itens", headers=auth).json()
    assert itens["total"] == 1 and itens["data"][0]["titulo"] == "Lista 1"
    execucoes = client.get("/api/v1/sync/execucoes", headers=auth).json()
    assert execucoes["data"][0]["status"] == "sucesso"


def test_other_student_cannot_read_my_course(
    client: TestClient, auth: dict[str, str], container: Container, lms: FakeLms
) -> None:
    conectar(client, auth)
    container.sincronizar.executar(container.alunos.autenticar("ana@exemplo.com", SENHA).id)
    curso_id = client.get("/api/v1/cursos", headers=auth).json()["data"][0]["id"]
    client.post(
        "/api/v1/auth/registro",
        json={"email": "bia@exemplo.com", "senha": SENHA, "nome": "Bia Lima"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": "bia@exemplo.com", "senha": SENHA}
    ).json()["access_token"]
    assert (
        client.get(
            f"/api/v1/cursos/{curso_id}", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 404
    )


def test_webhook_rejects_bad_signature(client: TestClient) -> None:
    r = client.post(
        "/api/v1/webhooks/telegram", headers={"x-test-secret": "errado"}, json={"mensagens": []}
    )
    assert r.status_code == 403
    assert (
        client.post(
            "/api/v1/webhooks/whatsapp", headers={"x-test-secret": "errado"}, json={}
        ).status_code
        == 403
    )


def test_pairing_then_commands_and_dedup(
    client: TestClient, auth: dict[str, str], telegram: FakeCanal
) -> None:
    mensagem(client, "oi", "m0", chat="999")
    assert "código de pareamento" in telegram.enviados[-1][1]
    parear(client, auth, telegram)

    mensagem(client, "/ajuda", "m1")
    assert "/prazos" in telegram.enviados[-1][1]
    enviados = len(telegram.enviados)
    mensagem(client, "/ajuda", "m1")  # reentrega do mesmo webhook
    assert len(telegram.enviados) == enviados
    mensagem(client, "/cursos", "m2")
    assert "Ainda não há cursos" in telegram.enviados[-1][1]
    mensagem(client, "/prazos abc", "m3")
    assert "número de 1 a 60" in telegram.enviados[-1][1]


def test_free_text_goes_through_llm_with_rag_tool_and_cites_sources(
    client: TestClient,
    auth: dict[str, str],
    telegram: FakeCanal,
    container: Container,
    lms: FakeLms,
    llm: ScriptedLlm,
) -> None:
    conectar(client, auth)
    lms.itens[1] = [
        item_texto(
            "page:tcp", "TCP e UDP", "O protocolo UDP não estabelece conexão e tem baixa latência."
        )
    ]
    container.sincronizar.executar(container.alunos.autenticar("ana@exemplo.com", SENHA).id)
    parear(client, auth, telegram)
    llm.programar(
        tool_call("buscar_no_material", pergunta="O que é o protocolo UDP?"),
        "UDP não tem conexão [1].",
    )

    mensagem(client, "o que é o protocolo UDP?", "q1")

    resposta = telegram.enviados[-1][1]
    assert (
        "UDP não tem conexão [1]" in resposta and "Fontes:" in resposta and "TCP e UDP" in resposta
    )
    assert "baixa latência" in tool_results(llm.chamadas[1])[0].content
    assert "Hoje é" in llm.chamadas[0]["system"]


def test_no_evidence_makes_tool_return_not_found_marker(
    client: TestClient, auth: dict[str, str], telegram: FakeCanal, llm: ScriptedLlm
) -> None:
    conectar(client, auth)
    parear(client, auth, telegram)
    llm.programar(
        tool_call("buscar_no_material", pergunta="receita de bolo"),
        "Não encontrei isso no material.",
    )

    mensagem(client, "como faço bolo?", "q2")

    assert "NADA_ENCONTRADO" in tool_results(llm.chamadas[1])[0].content
    assert "Fontes:" not in telegram.enviados[-1][1]


def test_forget_command_requires_confirmation_then_erases(
    client: TestClient, auth: dict[str, str], telegram: FakeCanal
) -> None:
    parear(client, auth, telegram)
    mensagem(client, "/esquecer", "e1")
    assert "confirmar" in telegram.enviados[-1][1]
    assert client.get("/api/v1/alunos/me", headers=auth).status_code == 200
    mensagem(client, "/esquecer confirmar", "e2")
    assert client.get("/api/v1/alunos/me", headers=auth).status_code == 404


def test_health_and_security_headers(client: TestClient) -> None:
    r = client.get("/health")
    assert r.json() == {"status": "ok"} and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-request-id"]
