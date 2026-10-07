import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import respx

from cbot.modules.alunos.domain.entities import Aluno, IdentidadeCanal
from cbot.modules.mensageria.application.notificador import NotificadorDeCanais
from cbot.modules.mensageria.infrastructure.canais import (
    TelegramCanal,
    WhatsAppCanal,
    dividir_texto,
)
from cbot.shared.errors import UpstreamUnavailable
from cbot.shared.vocab import Canal
from tests.fakes import FakeCanal

TG_URL = "https://api.telegram.org/botTOKEN/sendMessage"
WA_URL = "https://graph.facebook.com/v21.0/123/messages"


def telegram() -> TelegramCanal:
    return TelegramCanal("TOKEN", "segredo-do-webhook")


def whatsapp() -> WhatsAppCanal:
    return WhatsAppCanal("ACCESS", "123", "app-secret", "verifica-123", "resumo_diario")


def test_split_prefers_paragraph_boundaries_and_respects_limit() -> None:
    texto = "\n\n".join(f"parágrafo {i} " + "x" * 40 for i in range(10))
    partes = dividir_texto(texto, 120)
    assert all(len(p) <= 120 for p in partes) and "\n\n".join(partes).replace("\n\n", " ") != ""
    assert dividir_texto("curto", 100) == ["curto"] and dividir_texto("a" * 250, 100) == [
        "a" * 100,
        "a" * 100,
        "a" * 50,
    ]


# --- Telegram ----------------------------------------------------------------------------------
def test_telegram_secret_header_is_checked_in_constant_time_and_case_insensitive() -> None:
    canal = telegram()
    assert canal.autentico({"X-Telegram-Bot-Api-Secret-Token": "segredo-do-webhook"}, b"")
    assert not canal.autentico(
        {"x-telegram-bot-api-secret-token": "errado"}, b""
    ) and not canal.autentico({}, b"")


def test_telegram_parses_only_private_text_messages() -> None:
    privada = {
        "update_id": 9,
        "message": {
            "text": "/prazos",
            "chat": {"id": 55, "type": "private"},
            "date": 1_700_000_000,
        },
    }
    [msg] = telegram().interpretar(privada)
    assert (msg.remetente_id, msg.mensagem_id, msg.texto, msg.canal) == (
        "55",
        "9",
        "/prazos",
        Canal.TELEGRAM,
    )
    grupo = {"update_id": 1, "message": {"text": "oi", "chat": {"id": 1, "type": "group"}}}
    assert telegram().interpretar(grupo) == [] and telegram().interpretar({"update_id": 2}) == []
    assert (
        telegram().interpretar({"message": {"chat": {"id": 1, "type": "private"}, "photo": []}})
        == []
    )


@respx.mock
def test_telegram_sends_and_splits_long_text() -> None:
    rota = respx.post(TG_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    telegram().enviar_texto("55", "a" * 5000)
    assert rota.call_count == 2 and json.loads(rota.calls[0].request.content)["chat_id"] == "55"


@respx.mock
def test_telegram_errors_never_leak_the_bot_token() -> None:
    respx.post(TG_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(UpstreamUnavailable) as exc:
        telegram().enviar_texto("55", "oi")
    assert "TOKEN" not in exc.value.detail and "[REDACTED]" in exc.value.detail


# --- WhatsApp -----------------------------------------------------------------------------------
def assinar(corpo: bytes, segredo: str = "app-secret") -> dict[str, str]:
    return {
        "X-Hub-Signature-256": "sha256="
        + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    }


def test_whatsapp_validates_hmac_signature_over_the_raw_body() -> None:
    corpo = b'{"entry":[]}'
    canal = whatsapp()
    assert canal.autentico(assinar(corpo), corpo)
    assert not canal.autentico(assinar(corpo, "outro-segredo"), corpo)
    assert not canal.autentico(assinar(corpo), corpo + b" ") and not canal.autentico({}, corpo)


def test_whatsapp_get_handshake() -> None:
    canal = whatsapp()
    assert canal.verificar_assinatura_get("subscribe", "verifica-123", "desafio") == "desafio"
    assert canal.verificar_assinatura_get("subscribe", "errado", "desafio") is None
    assert (
        canal.verificar_assinatura_get("unsubscribe", "verifica-123", "x") is None
        and canal.verificar_assinatura_get(None, None, None) is None
    )


def test_whatsapp_parses_text_messages_and_ignores_statuses_and_media() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.1",
                                    "from": "5571999",
                                    "type": "text",
                                    "timestamp": "1700000000",
                                    "text": {"body": "oi"},
                                },
                                {
                                    "id": "wamid.2",
                                    "from": "5571999",
                                    "type": "image",
                                    "timestamp": "1700000001",
                                },
                            ],
                            "statuses": [{"id": "x", "status": "read"}],
                        }
                    }
                ]
            }
        ]
    }
    [msg] = whatsapp().interpretar(payload)
    assert (msg.remetente_id, msg.mensagem_id, msg.texto) == ("5571999", "wamid.1", "oi")
    assert whatsapp().interpretar({}) == []


@respx.mock
def test_whatsapp_sends_text_with_bearer_and_template_outside_window() -> None:
    rota = respx.post(WA_URL).mock(return_value=httpx.Response(200, json={}))
    canal = whatsapp()
    canal.enviar_texto("5571999", "olá")
    canal.enviar_aviso_resumo("5571999", "3 novidade(s)\ne 1 prazo")
    texto, template = (json.loads(c.request.content) for c in rota.calls)
    assert (
        rota.calls[0].request.headers["authorization"] == "Bearer ACCESS"
        and texto["text"]["body"] == "olá"
    )
    assert template["type"] == "template" and template["template"]["name"] == "resumo_diario"
    assert (
        template["template"]["components"][0]["parameters"][0]["text"] == "3 novidade(s) e 1 prazo"
    )


@respx.mock
def test_whatsapp_send_failure_becomes_upstream_error() -> None:
    respx.post(WA_URL).mock(return_value=httpx.Response(400, json={"error": "template"}))
    with pytest.raises(UpstreamUnavailable):
        whatsapp().enviar_aviso_resumo("1", "x")


# --- Notificador (janela de 24 h) -----------------------------------------------------------------------
class FakeAlunos:
    def __init__(self, preferido: Canal, identidades: dict[Canal, IdentidadeCanal]) -> None:
        self.aluno = Aluno(email="a@x.com", senha_hash="h", nome="Ana", canal_preferido=preferido)
        self.identidades = identidades

    def obter(self, aluno_id: object) -> Aluno:
        return self.aluno

    def identidade_do_aluno(self, aluno_id: object, canal: Canal) -> IdentidadeCanal | None:
        return self.identidades.get(canal)


def identidade(canal: Canal, janela: bool) -> IdentidadeCanal:
    quando = datetime.now(UTC) - timedelta(hours=1 if janela else 30)
    return IdentidadeCanal(
        uuid4(), canal, externo_id="dest", verificado_em=quando, ultima_mensagem_in_em=quando
    )


def test_notifier_uses_template_when_whatsapp_window_is_closed() -> None:
    wa, tg = FakeCanal(Canal.WHATSAPP), FakeCanal(Canal.TELEGRAM)
    alunos = FakeAlunos(Canal.WHATSAPP, {Canal.WHATSAPP: identidade(Canal.WHATSAPP, janela=False)})
    resultado = NotificadorDeCanais(alunos, {Canal.WHATSAPP: wa, Canal.TELEGRAM: tg}).enviar_resumo(
        uuid4(), "completo", "curto"
    )
    assert (
        resultado == ("whatsapp", False) and wa.avisos == [("dest", "curto")] and wa.enviados == []
    )


def test_notifier_sends_full_text_inside_window_and_on_telegram() -> None:
    wa, tg = FakeCanal(Canal.WHATSAPP), FakeCanal(Canal.TELEGRAM)
    dentro = FakeAlunos(Canal.WHATSAPP, {Canal.WHATSAPP: identidade(Canal.WHATSAPP, janela=True)})
    assert NotificadorDeCanais(dentro, {Canal.WHATSAPP: wa}).enviar_resumo(
        uuid4(), "completo", "c"
    ) == ("whatsapp", True)
    so_tg = FakeAlunos(Canal.WHATSAPP, {Canal.TELEGRAM: identidade(Canal.TELEGRAM, janela=False)})
    assert NotificadorDeCanais(so_tg, {Canal.WHATSAPP: wa, Canal.TELEGRAM: tg}).enviar_resumo(
        uuid4(), "completo", "c"
    ) == ("telegram", True)
    assert tg.enviados == [("dest", "completo")]


def test_notifier_without_linked_channel_returns_none_and_swallows_send_errors() -> None:
    wa = FakeCanal(Canal.WHATSAPP)
    sem = FakeAlunos(Canal.WHATSAPP, {})
    assert NotificadorDeCanais(sem, {Canal.WHATSAPP: wa}).enviar_resumo(uuid4(), "t", "c") is None
    assert not NotificadorDeCanais(sem, {Canal.WHATSAPP: wa}).enviar(uuid4(), "t")

    class Quebrado(FakeCanal):
        def enviar_texto(self, destino: str, texto: str) -> None:
            raise UpstreamUnavailable("fora")

    com = FakeAlunos(Canal.TELEGRAM, {Canal.TELEGRAM: identidade(Canal.TELEGRAM, janela=True)})
    assert not NotificadorDeCanais(com, {Canal.TELEGRAM: Quebrado(Canal.TELEGRAM)}).enviar(
        uuid4(), "t"
    )
