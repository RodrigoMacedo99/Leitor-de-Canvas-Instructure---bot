from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cbot.shared.vocab import Canal


@dataclass(frozen=True, slots=True)
class MensagemRecebida:
    canal: Canal
    remetente_id: str  # wa_id (WhatsApp) ou chat_id (Telegram)
    mensagem_id: str
    texto: str
    quando: datetime | None = None


class CanalMensageria(Protocol):
    """Porta de canal. WhatsApp e Telegram são adaptadores; o núcleo não conhece as diferenças."""

    canal: Canal

    def autentico(self, headers: Mapping[str, str], corpo: bytes) -> bool:
        """Valida a assinatura/segredo do webhook (False = descartar com 403)."""
        ...

    def interpretar(self, payload: dict[str, Any]) -> list[MensagemRecebida]: ...

    def enviar_texto(self, destino: str, texto: str) -> None: ...

    def enviar_aviso_resumo(self, destino: str, texto_curto: str) -> None:
        """Envio proativo fora da janela de resposta (template no WhatsApp; texto no Telegram)."""
        ...


class Notificador(Protocol):
    """Usada pelo módulo `resumo` para entregar mensagens ao aluno sem conhecer os canais."""

    def enviar_resumo(
        self, aluno_id: UUID, texto: str, resumo_curto: str
    ) -> tuple[str, bool] | None:
        """(canal, entregue_completo). `entregue_completo=False` = só o aviso foi (aguarda resposta)."""
        ...

    def enviar(self, aluno_id: UUID, texto: str) -> bool: ...
