from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


class MensagemRepository(Protocol):
    def historico(self, aluno_id: UUID, canal: str, limite: int) -> list[tuple[str, str]]:
        """Últimas mensagens em ordem cronológica, como (papel, texto): papel é 'aluno' ou 'bot'."""
        ...

    def registrar(
        self,
        aluno_id: UUID,
        canal: str,
        direcao: str,
        externo_id: str | None,
        texto: str,
        fontes: list[dict[str, Any]] | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        quando: datetime | None = None,
    ) -> bool:
        """False se `externo_id` já existia (reentrega de webhook): o chamador deve ignorar."""
        ...
