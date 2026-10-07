import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from cbot.config import get_settings
from cbot.container import Container, build_container
from cbot.modules.alunos.interfaces.routes import router as alunos_router
from cbot.modules.conteudo.interfaces.routes import router as conteudo_router
from cbot.modules.mensageria.interfaces.webhooks import router as webhooks_router
from cbot.modules.resumo.interfaces.routes import router as resumo_router
from cbot.modules.sincronizacao.interfaces.routes import router as sync_router
from cbot.shared.http import (
    CorrelationIdMiddleware,
    RateLimiter,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    register_error_handlers,
)
from cbot.shared.logging import configure_logging

logger = logging.getLogger(__name__)
API_RATE_LIMIT = 120
API_RATE_WINDOW = 60
RATE_LIMIT_EXEMPT = ("/api/v1/webhooks", "/health")


def _adicionar_middlewares(app: FastAPI, cors_origin: str) -> None:
    """Ordem importa: o último adicionado é o mais externo (CORS responde antes de tudo)."""
    app.add_middleware(
        RateLimitMiddleware,
        limiter=RateLimiter(API_RATE_LIMIT, API_RATE_WINDOW),
        exempt_prefixes=RATE_LIMIT_EXEMPT,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[cors_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


def create_app(container: Container | None = None) -> FastAPI:
    """Fábrica da aplicação; os testes passam um `Container` com dublês."""
    if container is None:
        configure_logging()
    settings = container.settings if container else get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = container or build_container(settings)
        yield
        app.state.container.db.dispose()

    app = FastAPI(
        title="CBOT",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    if container is not None:
        app.state.container = container
    _adicionar_middlewares(app, settings.cors_origin)
    register_error_handlers(app)
    for router in (alunos_router, conteudo_router, sync_router, resumo_router, webhooks_router):
        app.include_router(router)

    @app.get("/health", tags=["saude"])
    def health() -> dict[str, str]:
        with app.state.container.db.session() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app
