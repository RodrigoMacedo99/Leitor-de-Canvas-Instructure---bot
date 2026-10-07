"""Pipeline de mensagens recebidas.

Padrões: Chain of Responsibility (`Etapa`s em ordem; a primeira que responde encerra) e
Command (cada `/comando` é um objeto registrado por nome).
"""

import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cbot.modules.alunos.domain.entities import IdentidadeCanal
from cbot.modules.chat.domain.ports import MensagemRepository
from cbot.modules.mensageria.domain.ports import CanalMensageria, MensagemRecebida
from cbot.shared.errors import DomainError
from cbot.shared.http import RateLimiter
from cbot.shared.vocab import Canal

logger = logging.getLogger(__name__)
PAIRING_CODE = re.compile(r"^[A-Za-z2-9]{8}$")
GENERIC_ERROR = "Tive um problema para responder agora. Tente de novo em instantes."
RATE_LIMITED = "Você enviou muitas mensagens seguidas. Aguarde um minuto."
ONBOARDING = (
    "Olá! Para usar este bot, gere um código de pareamento no painel do CBOT "
    "(Canais > Vincular) e envie o código aqui."
)
PAIRED = "Pronto! Canal vinculado. Envie /ajuda para ver o que posso fazer."


@dataclass(frozen=True, slots=True)
class Contexto:
    aluno_id: UUID
    identidade: IdentidadeCanal
    texto: str

    @property
    def comando(self) -> tuple[str, str] | None:
        if not self.texto.startswith("/"):
            return None
        nome, _, argumento = self.texto.partition(" ")
        return nome.split("@")[0].lower(), argumento.strip()


class Comando(Protocol):
    """Command: uma ação do bot disparada por `/nome`."""

    nome: str
    descricao: str

    def executar(self, ctx: Contexto, argumento: str) -> str: ...


class Etapa(ABC):
    """Elo da cadeia: devolve a resposta ou None para passar ao próximo."""

    registra_saida = True  # False quando a própria etapa já persiste a mensagem enviada

    @abstractmethod
    def tratar(self, ctx: Contexto) -> str | None: ...


class EtapaComandos(Etapa):
    def __init__(self, comandos: list[Comando]) -> None:
        self._por_nome = {c.nome: c for c in comandos}
        self._ajuda = "\n".join(f"{c.nome} - {c.descricao}" for c in comandos)

    def tratar(self, ctx: Contexto) -> str | None:
        analisado = ctx.comando
        if analisado is None:
            return None
        nome, argumento = analisado
        if nome == "/start":
            return PAIRED
        comando = self._por_nome.get(nome)
        if comando is None:
            return f"Não conheço esse comando. Comandos disponíveis:\n{self._ajuda}"
        return comando.executar(ctx, argumento)

    @property
    def ajuda(self) -> str:
        return self._ajuda


class Conversador(Protocol):
    def conversar(self, aluno_id: UUID, canal: str, texto: str) -> str: ...


class EtapaConversa(Etapa):
    """Último elo: texto livre vai para o orquestrador do chat (RAG + ferramentas)."""

    registra_saida = False

    def __init__(self, conversador: Conversador) -> None:
        self._conversador = conversador

    def tratar(self, ctx: Contexto) -> str | None:
        return self._conversador.conversar(ctx.aluno_id, ctx.identidade.canal.value, ctx.texto)


class VinculadorDeCanal(Protocol):
    def vincular_canal(
        self, canal: Canal, externo_id: str, codigo: str
    ) -> IdentidadeCanal | None: ...

    def resolver_identidade(self, canal: Canal, externo_id: str) -> IdentidadeCanal | None: ...


class EntregadorDePendentes(Protocol):
    def entregar_pendente(self, aluno_id: UUID) -> str | None: ...


class MensagensUow(Protocol):
    @property
    def mensagens(self) -> MensagemRepository: ...


type MensagensUowFactory = Callable[[], AbstractContextManager[MensagensUow]]


class TratarMensagem:
    def __init__(
        self, alunos: VinculadorDeCanal, canais: dict[Canal, CanalMensageria], uow: MensagensUowFactory,
        etapas: list[Etapa], pendentes: EntregadorDePendentes, limiter: RateLimiter,
    ) -> None:  # fmt: skip
        self._alunos = alunos
        self._canais = canais
        self._uow = uow
        self._etapas = etapas
        self._pendentes = pendentes
        self._limiter = limiter

    def tratar(self, msg: MensagemRecebida) -> None:
        canal = self._canais[msg.canal]
        try:
            resposta = self._processar(msg)
        except DomainError as exc:
            logger.warning("erro de domínio ao tratar mensagem: %s", exc.detail)
            resposta = exc.detail
        except Exception:
            logger.exception("falha inesperada ao tratar mensagem")
            resposta = GENERIC_ERROR
        if resposta:
            canal.enviar_texto(msg.remetente_id, resposta)

    def _processar(self, msg: MensagemRecebida) -> str | None:
        identidade = self._alunos.resolver_identidade(msg.canal, msg.remetente_id)
        if identidade is None:
            return self._parear(msg)
        if not self._limiter.allow(f"{msg.canal}:{msg.remetente_id}"):
            return RATE_LIMITED
        with self._uow() as uow:
            nova = uow.mensagens.registrar(
                identidade.aluno_id,
                msg.canal.value,
                "in",
                msg.mensagem_id,
                msg.texto,
                quando=msg.quando,
            )
        if not nova:
            return None  # reentrega do webhook: já tratada
        pendente = self._pendentes.entregar_pendente(identidade.aluno_id)
        if pendente:
            self._canais[msg.canal].enviar_texto(msg.remetente_id, pendente)
        resposta, etapa = self._executar_cadeia(
            Contexto(identidade.aluno_id, identidade, msg.texto.strip())
        )
        if resposta and etapa and etapa.registra_saida:
            with self._uow() as uow:
                uow.mensagens.registrar(identidade.aluno_id, msg.canal.value, "out", None, resposta)
        return resposta

    def _executar_cadeia(self, ctx: Contexto) -> tuple[str | None, Etapa | None]:
        for etapa in self._etapas:
            resposta = etapa.tratar(ctx)
            if resposta is not None:
                return resposta, etapa
        return None, None

    def _parear(self, msg: MensagemRecebida) -> str:
        codigo = msg.texto.strip().removeprefix("/start").strip()
        if PAIRING_CODE.match(codigo):
            vinculada = self._alunos.vincular_canal(msg.canal, msg.remetente_id, codigo)
            if vinculada:
                return PAIRED
        return ONBOARDING
