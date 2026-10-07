import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from cbot.modules.alunos.domain.entities import Aluno
from cbot.modules.conteudo.public import ConteudoRepository, EventoDetalhado, PrazoDetalhado
from cbot.modules.mensageria.domain.ports import Notificador
from cbot.modules.resumo.domain.formatador import fatos_do_resumo, resumo_curto
from cbot.modules.resumo.domain.ports import ResumoRepository
from cbot.shared.errors import DomainError
from cbot.shared.llm import LlmClient, LlmMessage

logger = logging.getLogger(__name__)
LOOKAHEAD_DAYS = 7
NOTHING_NEW = "Sem novidades nos seus cursos e nenhum prazo nos próximos 7 dias. 🎉"
SYSTEM_PROMPT = (
    "Você escreve o resumo diário de um aluno para WhatsApp/Telegram, em português do Brasil. "
    "Use EXCLUSIVAMENTE os fatos fornecidos: não invente itens, datas nem prazos, e mantenha "
    "datas e emojis exatamente como estão. Seja breve, em tom amigável, com uma saudação curta "
    "no início e os itens agrupados por curso."
)


class ResultadoEnvio(StrEnum):
    SEM_NOVIDADES = "sem_novidades"
    ENVIADO = "enviado"
    AGUARDANDO_RESPOSTA = "aguardando_resposta"
    SEM_CANAL = "sem_canal"


class ResumoUow(Protocol):
    @property
    def conteudo(self) -> ConteudoRepository: ...
    @property
    def resumos(self) -> ResumoRepository: ...


type ResumoUowFactory = Callable[[], AbstractContextManager[ResumoUow]]


class AlunosLookup(Protocol):
    def obter(self, aluno_id: UUID) -> Aluno: ...


class ServicoResumo:
    """Compõe o resumo (fatos determinísticos + redação opcional por LLM) e o entrega ao aluno."""

    def __init__(
        self, uow: ResumoUowFactory, alunos: AlunosLookup, notificador: Notificador, llm: LlmClient | None = None
    ) -> None:  # fmt: skip
        self._uow = uow
        self._alunos = alunos
        self._notificador = notificador
        self._llm = llm

    def gerar_texto(self, aluno_id: UUID) -> str:
        """Sob demanda (/resumo): devolve o texto e marca os eventos como notificados."""
        agora = datetime.now(UTC)
        eventos, prazos, texto = self._compor(aluno_id, agora)
        if not texto:
            return NOTHING_NEW
        with self._uow() as uow:
            resumo_id = uow.resumos.salvar(aluno_id, self._inicio(eventos, agora), agora, texto)
            uow.resumos.marcar_enviado(aluno_id, resumo_id, "sob-demanda", agora)
            uow.conteudo.marcar_eventos_notificados(aluno_id, [e.id for e in eventos], agora)
        return texto

    def enviar_agendado(self, aluno_id: UUID) -> ResultadoEnvio:
        agora = datetime.now(UTC)
        eventos, prazos, texto = self._compor(aluno_id, agora)
        if not texto:
            return ResultadoEnvio.SEM_NOVIDADES
        envio = self._notificador.enviar_resumo(aluno_id, texto, resumo_curto(eventos, prazos))
        if envio is None:
            return ResultadoEnvio.SEM_CANAL
        canal, completo = envio
        with self._uow() as uow:
            inicio = self._inicio(eventos, agora)
            if completo:
                resumo_id = uow.resumos.salvar(aluno_id, inicio, agora, texto)
                uow.resumos.marcar_enviado(aluno_id, resumo_id, canal, agora)
            else:
                uow.resumos.salvar_pendente(aluno_id, inicio, agora, texto, canal)
            uow.conteudo.marcar_eventos_notificados(aluno_id, [e.id for e in eventos], agora)
        return ResultadoEnvio.ENVIADO if completo else ResultadoEnvio.AGUARDANDO_RESPOSTA

    def entregar_pendente(self, aluno_id: UUID) -> str | None:
        """Chamado quando o aluno responde: entrega o resumo cujo template já foi enviado."""
        with self._uow() as uow:
            pendente = uow.resumos.pendente_de_entrega(aluno_id)
            if pendente is None:
                return None
            uow.resumos.marcar_entregue(aluno_id, pendente[0], datetime.now(UTC))
            return pendente[1]

    def _compor(
        self, aluno_id: UUID, agora: datetime
    ) -> tuple[list[EventoDetalhado], list[PrazoDetalhado], str]:
        fuso = self._alunos.obter(aluno_id).fuso_horario
        with self._uow() as uow:
            eventos = uow.conteudo.eventos_pendentes(aluno_id)
            prazos = uow.conteudo.prazos(aluno_id, agora, agora + timedelta(days=LOOKAHEAD_DAYS))
        fatos = fatos_do_resumo(eventos, prazos, fuso)
        return eventos, prazos, (self._redigir(fatos) if fatos else "")

    def _redigir(self, fatos: str) -> str:
        if self._llm is None:
            return fatos
        try:
            resposta = self._llm.complete(
                system=SYSTEM_PROMPT, messages=[LlmMessage.user(fatos)], fast=True, max_tokens=900
            )
        except DomainError:
            logger.warning("LLM indisponível; usando o resumo determinístico")
            return fatos
        return resposta.text or fatos

    @staticmethod
    def _inicio(eventos: list[EventoDetalhado], agora: datetime) -> datetime:
        return min((e.detectado_em for e in eventos), default=agora - timedelta(days=1))
