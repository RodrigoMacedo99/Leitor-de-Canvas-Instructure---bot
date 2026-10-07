import logging
from typing import Protocol
from uuid import UUID

from cbot.modules.alunos.domain.entities import Aluno, IdentidadeCanal
from cbot.modules.mensageria.domain.ports import CanalMensageria
from cbot.shared.errors import DomainError
from cbot.shared.vocab import Canal

logger = logging.getLogger(__name__)


class AlunosParaCanais(Protocol):
    def obter(self, aluno_id: UUID) -> Aluno: ...

    def identidade_do_aluno(self, aluno_id: UUID, canal: Canal) -> IdentidadeCanal | None: ...


class NotificadorDeCanais:
    """Escolhe o canal do aluno (preferido, senão o outro) e respeita a janela de 24 h do WhatsApp."""

    def __init__(self, alunos: AlunosParaCanais, canais: dict[Canal, CanalMensageria]) -> None:
        self._alunos = alunos
        self._canais = canais

    def _destino(self, aluno_id: UUID) -> tuple[CanalMensageria, IdentidadeCanal] | None:
        aluno = self._alunos.obter(aluno_id)
        ordem = [aluno.canal_preferido, *(c for c in Canal if c is not aluno.canal_preferido)]
        for canal in ordem:
            identidade = self._alunos.identidade_do_aluno(aluno_id, canal)
            if canal in self._canais and identidade and identidade.externo_id:
                return self._canais[canal], identidade
        return None

    def enviar(self, aluno_id: UUID, texto: str) -> bool:
        destino = self._destino(aluno_id)
        if destino is None:
            return False
        canal, identidade = destino
        try:
            canal.enviar_texto(identidade.externo_id or "", texto)
        except DomainError:
            logger.exception("falha ao notificar aluno %s", aluno_id)
            return False
        return True

    def enviar_resumo(
        self, aluno_id: UUID, texto: str, resumo_curto: str
    ) -> tuple[str, bool] | None:
        destino = self._destino(aluno_id)
        if destino is None:
            return None
        canal, identidade = destino
        externo = identidade.externo_id or ""
        if canal.canal is Canal.WHATSAPP and not identidade.janela_24h_aberta:
            canal.enviar_aviso_resumo(externo, resumo_curto)
            return canal.canal.value, False
        canal.enviar_texto(externo, texto)
        return canal.canal.value, True
