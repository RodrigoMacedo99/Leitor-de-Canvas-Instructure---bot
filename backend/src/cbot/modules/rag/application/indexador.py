import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

from cbot.modules.rag.domain.chunker import Chunker, SecaoEntrada
from cbot.modules.rag.domain.ports import Contextualizador, Embedder, TrechoNovo, TrechoRepository
from cbot.shared.events import ArquivoProcessado, EventBus, ItemRemovido, ItemSincronizado

logger = logging.getLogger(__name__)
DOC_CONTEXT_CHARS = 12_000


class ExtratorPort(Protocol):
    def extrair(self, caminho: Path, mime: str, nome: str) -> list[SecaoEntrada]: ...


class RagUow(Protocol):
    @property
    def trechos(self) -> TrechoRepository: ...


type RagUowFactory = Callable[[], AbstractContextManager[RagUow]]


class Indexador:
    """Observer: reage a `ItemSincronizado`/`ItemRemovido` e mantém o índice de busca em dia."""

    def __init__(
        self, uow: RagUowFactory, extrator: ExtratorPort, chunker: Chunker,
        contextualizador: Contextualizador, embedder: Embedder, bus: EventBus,
    ) -> None:  # fmt: skip
        self._uow = uow
        self._extrator = extrator
        self._chunker = chunker
        self._contextualizador = contextualizador
        self._embedder = embedder
        self._bus = bus

    def registrar(self, bus: EventBus) -> None:
        bus.subscribe(ItemSincronizado, self.ao_sincronizar)
        bus.subscribe(ItemRemovido, self.ao_remover)

    def ao_remover(self, evento: ItemRemovido) -> None:
        with self._uow() as uow:
            uow.trechos.remover_trechos_do_item(evento.aluno_id, evento.item_id)

    def ao_sincronizar(self, evento: ItemSincronizado) -> None:
        secoes, erro = self._secoes(evento)
        if evento.arquivo_id:
            self._bus.publish(ArquivoProcessado(evento.aluno_id, evento.arquivo_id, erro))
        if not secoes:
            self.ao_remover(ItemRemovido(evento.aluno_id, evento.item_id))
            return
        trechos = self._montar_trechos(evento, secoes)
        with self._uow() as uow:
            uow.trechos.substituir_trechos(
                evento.aluno_id, evento.item_id, evento.arquivo_id, self._embedder.model_id, trechos
            )
        logger.info("indexados %d trechos do item %s", len(trechos), evento.item_id)

    def _secoes(self, evento: ItemSincronizado) -> tuple[list[SecaoEntrada], str | None]:
        if evento.arquivo_caminho:
            try:
                secoes = self._extrator.extrair(
                    Path(evento.arquivo_caminho),
                    evento.arquivo_mime or "",
                    evento.arquivo_nome or "",
                )
            except Exception as exc:
                logger.warning(
                    "extração falhou para %s: %s", evento.arquivo_nome, type(exc).__name__
                )
                return [], f"{type(exc).__name__}: {exc}"[:300]
            return secoes, (None if secoes else "Arquivo sem texto extraível (talvez escaneado).")
        texto = (evento.texto or "").strip()
        return ([SecaoEntrada(texto, titulo=evento.titulo)] if texto else []), None

    def _montar_trechos(
        self, evento: ItemSincronizado, secoes: list[SecaoEntrada]
    ) -> list[TrechoNovo]:
        chunks = self._chunker.dividir(secoes)
        documento = "\n".join(s.texto for s in secoes)[:DOC_CONTEXT_CHARS]
        titulo = evento.arquivo_nome or evento.titulo
        contextos = [
            self._contextualizador.contextualizar(titulo, documento, c.texto) for c in chunks
        ]
        entradas = [
            f"{ctx}\n{c.texto}" if ctx else c.texto
            for c, ctx in zip(chunks, contextos, strict=True)
        ]
        vetores = self._embedder.embed(entradas)
        return [
            TrechoNovo(
                ordem=c.ordem, texto=c.texto, contexto=ctx, embedding=vec,
                metadados={
                    "curso": evento.curso_nome, "item": evento.titulo, "arquivo": evento.arquivo_nome,
                    "pagina": c.pagina, "titulo_secao": c.titulo, "secao_curso": evento.secao,
                    "url": evento.url,
                },
            )
            for c, ctx, vec in zip(chunks, contextos, vetores, strict=True)
        ]  # fmt: skip
