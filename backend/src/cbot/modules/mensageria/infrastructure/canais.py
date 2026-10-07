"""Adaptadores de canal. `CanalBase` é o Template Method: divide textos longos e delega o envio."""

import hashlib
import hmac
import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from cbot.modules.mensageria.domain.ports import MensagemRecebida
from cbot.shared.errors import UpstreamUnavailable
from cbot.shared.logging import redact
from cbot.shared.vocab import Canal

logger = logging.getLogger(__name__)
HTTP_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
TELEGRAM_LIMIT = 4096
WHATSAPP_LIMIT = 4096
GRAPH_VERSION = "v21.0"


def dividir_texto(texto: str, limite: int) -> list[str]:
    """Quebra em partes ≤ limite, preferindo fronteiras de parágrafo/linha."""
    partes: list[str] = []
    restante = texto.strip()
    while len(restante) > limite:
        corte = max(restante.rfind("\n\n", 0, limite), restante.rfind("\n", 0, limite))
        corte = corte if corte > limite // 2 else limite
        partes.append(restante[:corte].rstrip())
        restante = restante[corte:].lstrip()
    if restante:
        partes.append(restante)
    return partes


class CanalBase(ABC):
    canal: Canal
    limite: int

    def __init__(self, http: httpx.Client | None = None) -> None:
        self._http = http or httpx.Client(timeout=HTTP_TIMEOUT)

    def enviar_texto(self, destino: str, texto: str) -> None:
        for parte in dividir_texto(texto, self.limite):
            self._enviar_parte(destino, parte)

    @abstractmethod
    def _enviar_parte(self, destino: str, parte: str) -> None: ...

    def _post(self, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._http.post(url, **kwargs)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable(
                f"Falha ao enviar pelo {self.canal}: {redact(str(exc))}"
            ) from exc
        return response


class TelegramCanal(CanalBase):
    canal = Canal.TELEGRAM
    limite = TELEGRAM_LIMIT
    SECRET_HEADER = "x-telegram-bot-api-secret-token"  # noqa: S105

    def __init__(
        self, bot_token: str, webhook_secret: str, http: httpx.Client | None = None
    ) -> None:
        super().__init__(http)
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._secret = webhook_secret

    def autentico(self, headers: Mapping[str, str], corpo: bytes) -> bool:
        recebido = {k.lower(): v for k, v in headers.items()}.get(self.SECRET_HEADER, "")
        return hmac.compare_digest(recebido, self._secret)

    def interpretar(self, payload: dict[str, Any]) -> list[MensagemRecebida]:
        msg = payload.get("message") or {}
        texto = msg.get("text")
        chat_id = (msg.get("chat") or {}).get("id")
        if not texto or chat_id is None or (msg.get("chat") or {}).get("type") != "private":
            return []
        return [
            MensagemRecebida(
                canal=self.canal, remetente_id=str(chat_id), mensagem_id=str(payload.get("update_id")),
                texto=texto, quando=datetime.fromtimestamp(msg.get("date", 0), UTC),
            )
        ]  # fmt: skip

    def _enviar_parte(self, destino: str, parte: str) -> None:
        self._post(
            self._url, json={"chat_id": destino, "text": parte, "disable_web_page_preview": True}
        )

    def enviar_aviso_resumo(self, destino: str, texto_curto: str) -> None:
        self.enviar_texto(destino, texto_curto)


class WhatsAppCanal(CanalBase):
    canal = Canal.WHATSAPP
    limite = WHATSAPP_LIMIT

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        app_secret: str,
        verify_token: str,
        template_resumo: str,
        http: httpx.Client | None = None,
    ) -> None:
        super().__init__(http)
        self._url = f"https://graph.facebook.com/{GRAPH_VERSION}/{phone_number_id}/messages"
        self._auth = {"Authorization": f"Bearer {access_token}"}
        self._app_secret = app_secret.encode()
        self._verify_token = verify_token
        self._template = template_resumo

    def verificar_assinatura_get(
        self, mode: str | None, token: str | None, challenge: str | None
    ) -> str | None:
        """Handshake de configuração do webhook (GET). Devolve o challenge se o token confere."""
        if mode == "subscribe" and token and hmac.compare_digest(token, self._verify_token):
            return challenge
        return None

    def autentico(self, headers: Mapping[str, str], corpo: bytes) -> bool:
        recebido = {k.lower(): v for k, v in headers.items()}.get("x-hub-signature-256", "")
        esperado = "sha256=" + hmac.new(self._app_secret, corpo, hashlib.sha256).hexdigest()
        return hmac.compare_digest(recebido, esperado)

    def interpretar(self, payload: dict[str, Any]) -> list[MensagemRecebida]:
        recebidas = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                for msg in (change.get("value") or {}).get("messages", []):
                    if msg.get("type") != "text":
                        continue
                    recebidas.append(
                        MensagemRecebida(
                            canal=self.canal, remetente_id=msg["from"], mensagem_id=msg["id"],
                            texto=msg["text"]["body"],
                            quando=datetime.fromtimestamp(int(msg.get("timestamp", 0)), UTC),
                        )
                    )  # fmt: skip
        return recebidas

    def _enviar_parte(self, destino: str, parte: str) -> None:
        self._post(self._url, headers=self._auth, json={
            "messaging_product": "whatsapp", "to": destino, "type": "text",
            "text": {"body": parte, "preview_url": False},
        })  # fmt: skip

    def enviar_aviso_resumo(self, destino: str, texto_curto: str) -> None:
        """Fora da janela de 24 h só vale template aprovado; o parâmetro é um resumo de uma linha."""
        parametro = " ".join(texto_curto.split())[:200]
        self._post(self._url, headers=self._auth, json={
            "messaging_product": "whatsapp", "to": destino, "type": "template",
            "template": {
                "name": self._template, "language": {"code": "pt_BR"},
                "components": [{"type": "body", "parameters": [{"type": "text", "text": parametro}]}],
            },
        })  # fmt: skip
