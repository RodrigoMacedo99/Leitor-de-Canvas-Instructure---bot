"""Fusão de rankings (RRF) e tipos de recuperação. Funções puras."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

RRF_K = 60


@dataclass(frozen=True, slots=True)
class Candidato:
    trecho_id: UUID
    texto: str
    contexto: str | None
    metadados: dict[str, Any] = field(default_factory=dict)
    similaridade: float | None = None
    score: float = 0.0


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Candidato]], k: int = RRF_K
) -> list[Candidato]:
    """score(d) = Σ 1/(k + posição). Mantém a maior similaridade vetorial vista para cada trecho."""
    scores: dict[UUID, float] = defaultdict(float)
    melhores: dict[UUID, Candidato] = {}
    for ranking in rankings:
        for posicao, cand in enumerate(ranking, start=1):
            scores[cand.trecho_id] += 1.0 / (k + posicao)
            visto = melhores.get(cand.trecho_id)
            sims = [
                s
                for s in (cand.similaridade, visto.similaridade if visto else None)
                if s is not None
            ]
            melhores[cand.trecho_id] = Candidato(
                cand.trecho_id,
                cand.texto,
                cand.contexto,
                cand.metadados,
                max(sims, default=None),
                0.0,
            )
    fundidos = [
        Candidato(
            c.trecho_id, c.texto, c.contexto, c.metadados, c.similaridade, scores[c.trecho_id]
        )
        for c in melhores.values()
    ]
    return sorted(fundidos, key=lambda c: c.score, reverse=True)
