"""Raiz de composição: único lugar que conhece todas as implementações concretas.

Injeção de dependência manual (sem framework): `build_container` monta o grafo e aceita
substituições, o que permite testar o sistema inteiro com um LMS e um LLM falsos.
"""

from dataclasses import dataclass, field
from typing import Any

from cbot.config import Settings
from cbot.modules.alunos.application.service import AlunosService
from cbot.modules.canvas.public import ConnectorFactory, canvas_connector_factory
from cbot.modules.chat.application.orquestrador import Orquestrador
from cbot.modules.conteudo.application.consultas import ConsultasConteudo
from cbot.modules.conteudo.public import FileStorage
from cbot.modules.mensageria.application.comandos import comandos_padrao
from cbot.modules.mensageria.application.notificador import NotificadorDeCanais
from cbot.modules.mensageria.application.tratar_mensagem import (
    EtapaComandos,
    EtapaConversa,
    TratarMensagem,
)
from cbot.modules.mensageria.domain.ports import CanalMensageria
from cbot.modules.mensageria.infrastructure.canais import TelegramCanal, WhatsAppCanal
from cbot.modules.rag.application.busca import BuscaHibrida
from cbot.modules.rag.application.indexador import Indexador
from cbot.modules.rag.application.responder import ResponderPergunta
from cbot.modules.rag.domain.chunker import StructuralChunker
from cbot.modules.rag.domain.ports import Contextualizador, Embedder, Reranker
from cbot.modules.rag.infrastructure.anthropic_llm import AnthropicLlm
from cbot.modules.rag.infrastructure.contextualizers import LlmContextualizer, NoContextualizer
from cbot.modules.rag.infrastructure.embedders import HashingEmbedder, OllamaEmbedder
from cbot.modules.rag.infrastructure.extrator_adapter import ExtratorConteudoAdapter
from cbot.modules.rag.infrastructure.rerankers import NoopReranker
from cbot.modules.resumo.application.servico import ServicoResumo
from cbot.modules.sincronizacao.application.sincronizar import SincronizarAluno
from cbot.modules.sincronizacao.application.worker import (
    JOB_RESUMO,
    JOB_SYNC,
    Agendador,
    JobWorker,
)
from cbot.modules.sincronizacao.domain.ports import Job
from cbot.shared.db import Database
from cbot.shared.events import EventBus, ReautorizacaoNecessaria
from cbot.shared.http import RateLimiter
from cbot.shared.llm import LlmClient
from cbot.shared.security import TokenCipher
from cbot.shared.vocab import Canal, Gatilho
from cbot.uow import make_uow_factory

CHAT_RATE_LIMIT = 20
CHAT_RATE_WINDOW = 60
REAUTH_MESSAGE = (
    "Seu token do Canvas foi recusado (expirou ou foi revogado). Gere um novo token no Canvas "
    "(Conta > Configurações > Novo token de acesso) e atualize no painel do CBOT."
)


@dataclass(slots=True)
class Container:
    settings: Settings
    db: Database
    bus: EventBus
    uow: Any
    storage: FileStorage
    llm: LlmClient | None
    alunos: AlunosService
    consultas: ConsultasConteudo
    sincronizar: SincronizarAluno
    busca: BuscaHibrida
    responder: ResponderPergunta | None
    servico_resumo: ServicoResumo
    tratar_mensagem: TratarMensagem
    canais: dict[Canal, CanalMensageria]
    worker: JobWorker
    agendador: Agendador
    indexador: Indexador
    extras: dict[str, Any] = field(default_factory=dict)


def _criar_llm(settings: Settings) -> LlmClient | None:
    if settings.anthropic_api_key is None:
        return None
    return AnthropicLlm(
        settings.anthropic_api_key.get_secret_value(),
        settings.claude_model_chat,
        settings.claude_model_fast,
    )


def _criar_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "hashing":
        return HashingEmbedder(settings.embedding_dim)
    return OllamaEmbedder(settings.ollama_url, settings.embedding_model, settings.embedding_dim)


def _criar_canais(settings: Settings) -> dict[Canal, CanalMensageria]:
    canais: dict[Canal, CanalMensageria] = {}
    if settings.telegram_bot_token and settings.telegram_webhook_secret:
        canais[Canal.TELEGRAM] = TelegramCanal(
            settings.telegram_bot_token.get_secret_value(),
            settings.telegram_webhook_secret.get_secret_value(),
        )
    if (
        settings.whatsapp_access_token and settings.whatsapp_phone_number_id
        and settings.whatsapp_app_secret and settings.whatsapp_verify_token
    ):  # fmt: skip
        canais[Canal.WHATSAPP] = WhatsAppCanal(
            settings.whatsapp_access_token.get_secret_value(), settings.whatsapp_phone_number_id,
            settings.whatsapp_app_secret.get_secret_value(),
            settings.whatsapp_verify_token.get_secret_value(), settings.whatsapp_summary_template,
        )  # fmt: skip
    return canais


def build_container(
    settings: Settings,
    *,
    db: Database | None = None,
    connector_factory: ConnectorFactory | None = None,
    llm: LlmClient | None = None,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
    canais: dict[Canal, CanalMensageria] | None = None,
) -> Container:
    db = db or Database(settings.database_url)
    bus, uow = EventBus(), make_uow_factory(db)
    llm = llm if llm is not None else _criar_llm(settings)
    connector_factory = connector_factory or canvas_connector_factory
    storage, alunos, consultas = _montar_nucleo(settings, uow, bus, connector_factory)
    indexador, busca, responder = _montar_rag(
        settings, uow, bus, llm, embedder or _criar_embedder(settings), reranker
    )
    sincronizar = SincronizarAluno(
        uow, alunos, connector_factory, storage, bus, max_download_bytes=settings.max_download_bytes
    )
    canais = canais if canais is not None else _criar_canais(settings)
    servico_resumo, tratar = _montar_mensageria(
        settings, uow, bus, llm, alunos, consultas, busca, canais
    )
    worker = _montar_worker(uow, sincronizar, servico_resumo)
    return Container(
        settings=settings,
        db=db,
        bus=bus,
        uow=uow,
        storage=storage,
        llm=llm,
        alunos=alunos,
        consultas=consultas,
        sincronizar=sincronizar,
        busca=busca,
        responder=responder,
        servico_resumo=servico_resumo,
        tratar_mensagem=tratar,
        canais=canais,
        worker=worker,
        agendador=Agendador(uow, alunos),
        indexador=indexador,
    )


def _montar_nucleo(
    settings: Settings, uow: Any, bus: EventBus, connector_factory: ConnectorFactory
) -> tuple[FileStorage, AlunosService, ConsultasConteudo]:
    storage = FileStorage(settings.storage_dir)
    alunos = AlunosService(
        uow,
        TokenCipher(settings.token_encryption_key.get_secret_value()),
        connector_factory,
        registro_aberto=settings.registro_aberto,
        permitir_http_local=settings.allow_local_lms,
        bus=bus,
    )
    consultas = ConsultasConteudo(uow, storage)
    consultas.registrar(bus)
    return storage, alunos, consultas


def _montar_worker(
    uow: Any, sincronizar: SincronizarAluno, servico_resumo: ServicoResumo
) -> JobWorker:
    def sincronizar_job(job: Job) -> None:
        sincronizar.executar(job.aluno_id, Gatilho(job.payload.get("gatilho", "manual")))  # type: ignore[arg-type]

    def resumo_job(job: Job) -> None:
        servico_resumo.enviar_agendado(job.aluno_id)  # type: ignore[arg-type]

    return JobWorker(uow, {JOB_SYNC: sincronizar_job, JOB_RESUMO: resumo_job})


def _montar_rag(
    settings: Settings,
    uow: Any,
    bus: EventBus,
    llm: LlmClient | None,
    embedder: Embedder,
    reranker: Reranker | None,
) -> tuple[Indexador, BuscaHibrida, ResponderPergunta | None]:
    contextualizador: Contextualizador = (
        LlmContextualizer(llm) if llm and settings.contextual_retrieval else NoContextualizer()
    )
    indexador = Indexador(
        uow, ExtratorConteudoAdapter(), StructuralChunker(), contextualizador, embedder, bus
    )
    indexador.registrar(bus)
    busca = BuscaHibrida(uow, embedder, reranker or NoopReranker())
    responder = (
        ResponderPergunta(busca, llm, min_similarity=settings.rag_min_similarity) if llm else None
    )
    return indexador, busca, responder


def _montar_mensageria(
    settings: Settings,
    uow: Any,
    bus: EventBus,
    llm: LlmClient | None,
    alunos: AlunosService,
    consultas: ConsultasConteudo,
    busca: BuscaHibrida,
    canais: dict[Canal, CanalMensageria],
) -> tuple[ServicoResumo, TratarMensagem]:
    notificador = NotificadorDeCanais(alunos, canais)
    servico_resumo = ServicoResumo(uow, alunos, notificador, llm)

    def avisar_reautorizacao(evento: ReautorizacaoNecessaria) -> None:
        notificador.enviar(evento.aluno_id, REAUTH_MESSAGE)

    bus.subscribe(ReautorizacaoNecessaria, avisar_reautorizacao)
    orquestrador = Orquestrador(
        llm, busca, consultas, alunos, uow, min_similarity=settings.rag_min_similarity
    )
    comandos = comandos_padrao(consultas, alunos, servico_resumo, uow, alunos)
    tratar = TratarMensagem(
        alunos,
        canais,
        uow,
        [EtapaComandos(comandos), EtapaConversa(orquestrador)],
        servico_resumo,
        RateLimiter(CHAT_RATE_LIMIT, CHAT_RATE_WINDOW),
    )
    return servico_resumo, tratar
