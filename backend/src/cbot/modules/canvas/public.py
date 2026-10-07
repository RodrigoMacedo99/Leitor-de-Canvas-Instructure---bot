"""API pública do módulo `canvas` (único ponto que outros módulos podem importar)."""

from cbot.modules.canvas.domain.ports import (
    ArquivoLms,
    ColetaCurso,
    Conhecidos,
    ConnectorFactory,
    CursoLms,
    ItemLms,
    LmsConnector,
    PerfilLms,
)
from cbot.modules.canvas.infrastructure.client import CanvasHttpClient, normalizar_url_base
from cbot.modules.canvas.infrastructure.connector import CanvasConnector


def canvas_connector_factory(url_base: str, token: str) -> LmsConnector:
    return CanvasConnector(CanvasHttpClient(url_base, token), url_base)


__all__ = [
    "ArquivoLms",
    "ColetaCurso",
    "ConnectorFactory",
    "Conhecidos",
    "CursoLms",
    "ItemLms",
    "LmsConnector",
    "PerfilLms",
    "canvas_connector_factory",
    "normalizar_url_base",
]
