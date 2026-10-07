from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from cbot.modules.rag.domain.ranking import Candidato


@dataclass(frozen=True, slots=True)
class TrechoNovo:
    ordem: int
    texto: str
    contexto: str | None
    embedding: list[float]
    metadados: dict[str, Any] = field(default_factory=dict)


class Embedder(Protocol):
    model_id: str
    dim: int

    def embed(self, textos: list[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    def rerank(self, consulta: str, candidatos: list[Candidato], top_k: int) -> list[Candidato]: ...


class Contextualizador(Protocol):
    """Contextual Retrieval: devolve 1-2 frases que situam o trecho no documento (ou None)."""

    def contextualizar(self, titulo: str, documento: str, trecho: str) -> str | None: ...


class TrechoRepository(Protocol):
    def substituir_trechos(
        self, aluno_id: UUID, item_id: UUID, arquivo_id: UUID | None, modelo_emb: str,
        trechos: list[TrechoNovo],
    ) -> int: ...  # fmt: skip

    def remover_trechos_do_item(self, aluno_id: UUID, item_id: UUID) -> int: ...

    def busca_vetorial(
        self, aluno_id: UUID, vetor: list[float], curso_id: UUID | None, limite: int
    ) -> list[Candidato]: ...

    def busca_textual(
        self, aluno_id: UUID, consulta: str, curso_id: UUID | None, limite: int
    ) -> list[Candidato]: ...
