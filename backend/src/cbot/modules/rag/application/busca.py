from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cbot.modules.rag.application.indexador import RagUow
from cbot.modules.rag.domain.ports import Embedder, Reranker
from cbot.modules.rag.domain.ranking import Candidato, reciprocal_rank_fusion

CANDIDATES_PER_SEARCH = 40
RERANK_POOL = 30
DEFAULT_TOP_K = 6


class BuscaUow(RagUow, Protocol): ...


type BuscaUowFactory = Callable[[], AbstractContextManager[RagUow]]


@dataclass(frozen=True, slots=True)
class ResultadoBusca:
    candidatos: list[Candidato]

    @property
    def melhor_similaridade(self) -> float | None:
        sims = [c.similaridade for c in self.candidatos if c.similaridade is not None]
        return max(sims, default=None)

    @property
    def vazio(self) -> bool:
        return not self.candidatos


class BuscaHibrida:
    """Vetorial (cosseno) + textual (FTS) → RRF → reranker. Sempre restrita ao aluno."""

    def __init__(self, uow: BuscaUowFactory, embedder: Embedder, reranker: Reranker) -> None:
        self._uow = uow
        self._embedder = embedder
        self._reranker = reranker

    def buscar(
        self,
        aluno_id: UUID,
        consulta: str,
        *,
        curso_id: UUID | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> ResultadoBusca:
        vetor = self._embedder.embed([consulta])[0]
        with self._uow() as uow:
            vetoriais = uow.trechos.busca_vetorial(aluno_id, vetor, curso_id, CANDIDATES_PER_SEARCH)
            textuais = uow.trechos.busca_textual(
                aluno_id, consulta, curso_id, CANDIDATES_PER_SEARCH
            )
        fundidos = reciprocal_rank_fusion([vetoriais, textuais])[:RERANK_POOL]
        return ResultadoBusca(self._reranker.rerank(consulta, fundidos, top_k))
