"""API pública do módulo `rag`."""

from cbot.modules.rag.application.busca import BuscaHibrida, ResultadoBusca
from cbot.modules.rag.application.responder import (
    Fonte,
    ResponderPergunta,
    Resposta,
    fontes_citadas,
    montar_contexto,
)

__all__ = [
    "BuscaHibrida",
    "Fonte",
    "ResponderPergunta",
    "Resposta",
    "ResultadoBusca",
    "fontes_citadas",
    "montar_contexto",
]
