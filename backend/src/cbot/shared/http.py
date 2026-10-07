import logging
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from cbot.shared.errors import DomainError
from cbot.shared.logging import correlation_id

logger = logging.getLogger(__name__)
PROBLEM_JSON = "application/problem+json"
ERROR_BASE_URL = "https://cbot.local/erros"


def problem(status: int, slug: str, title: str, detail: str, instance: str) -> JSONResponse:
    body = {
        "type": f"{ERROR_BASE_URL}/{slug}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        correlation_id.set(trace_id)
        response = await call_next(request)
        response.headers["x-request-id"] = trace_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response


class RateLimiter:
    """Janela deslizante em memória, por chave (IP ou identidade). Suficiente para 1 processo."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: ASGIApp, limiter: RateLimiter, exempt_prefixes: tuple[str, ...]
    ) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._exempt = exempt_prefixes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client = request.client.host if request.client else "unknown"
        if not request.url.path.startswith(self._exempt) and not self._limiter.allow(client):
            response = problem(
                429,
                "limite-de-taxa",
                "Muitas requisições",
                "Tente novamente em instantes.",
                request.url.path,
            )
            response.headers["Retry-After"] = str(self._limiter.window)
            return response
        return await call_next(request)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        return problem(exc.status, exc.slug, exc.title, exc.detail, request.url.path)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()
        )
        return problem(422, "validacao", "Erro de validação", detail, request.url.path)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("erro não tratado em %s", request.url.path)
        return problem(500, "erro-interno", "Erro interno", "Erro inesperado.", request.url.path)
