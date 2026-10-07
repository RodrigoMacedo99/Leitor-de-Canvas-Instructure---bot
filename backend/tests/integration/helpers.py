from fastapi.testclient import TestClient

from tests.fakes import FakeCanal

SENHA = "uma-senha-bem-longa"
HEADERS_OK = {"x-test-secret": "ok"}


def conectar(client: TestClient, auth: dict[str, str]) -> None:
    r = client.put("/api/v1/alunos/me/canvas", headers=auth, json={
        "url_base": "https://escola.instructure.com", "token": "token-do-canvas-123", "consentimento": True,
    })  # fmt: skip
    assert r.status_code == 200, r.text


def parear(client: TestClient, auth: dict[str, str], canal: FakeCanal, chat: str = "777") -> None:
    nome = canal.canal.value
    codigo = client.post("/api/v1/alunos/me/canais", headers=auth, json={"canal": nome}).json()[
        "codigo"
    ]
    client.post(
        f"/api/v1/webhooks/{nome}",
        headers=HEADERS_OK,
        json={"mensagens": [{"de": chat, "id": "p1", "texto": codigo}]},
    )
    assert "vinculado" in canal.enviados[-1][1].lower()


def mensagem(
    client: TestClient, texto: str, msg_id: str, chat: str = "777", canal: str = "telegram"
) -> None:
    r = client.post(
        f"/api/v1/webhooks/{canal}",
        headers=HEADERS_OK,
        json={"mensagens": [{"de": chat, "id": msg_id, "texto": texto}]},
    )
    assert r.status_code == 200
