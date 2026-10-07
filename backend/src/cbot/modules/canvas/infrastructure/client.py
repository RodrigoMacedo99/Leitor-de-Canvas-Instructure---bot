"""Cliente HTTP de baixo nível da API REST do Canvas (paginação, retentativa, redação de token)."""

import ipaddress
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from cbot.shared.errors import LmsAuthorizationError, UpstreamUnavailable, ValidationFailed
from cbot.shared.logging import redact

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"
PAGE_SIZE = 100
MAX_PAGES = 200
MAX_ATTEMPTS = 4
REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
CHUNK_BYTES = 64 * 1024
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY = 429
HTTP_SERVER_ERROR = 500


BACKOFF = wait_exponential(multiplier=0.5, max=8)  # os testes trocam por `wait_none()`


def _wait(state: RetryCallState) -> float:
    return BACKOFF(state)


class TransientLmsError(Exception):
    """Falha temporária (rede, 429, 5xx, limite de taxa do Canvas) — vale retentar."""


class LmsForbidden(Exception):
    """Recurso existe mas o aluno não tem acesso (ex.: aba de Arquivos oculta no curso)."""


def normalizar_url_base(url: str, *, permitir_http_local: bool = False) -> str:
    """Valida a URL informada pelo aluno (defesa contra SSRF) e devolve só a origem."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    local = host in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (permitir_http_local and local):
        raise ValidationFailed("A URL do Canvas deve usar https.")
    if not host or (local and not permitir_http_local):
        raise ValidationFailed("Host do Canvas inválido.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if (ip.is_private or ip.is_loopback or ip.is_link_local) and not permitir_http_local:
            raise ValidationFailed("Endereços de rede interna não são permitidos.")
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}"


class CanvasHttpClient:
    """Fala com `<base>/api/v1`. O token só é enviado ao host informado (httpx remove o
    cabeçalho Authorization em redirecionamentos para outra origem, como o S3 dos downloads)."""

    def __init__(self, base_url: str, token: str, http: httpx.Client | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._http = http or httpx.Client(
            timeout=REQUEST_TIMEOUT, follow_redirects=True, headers={"User-Agent": "cbot/0.1"}
        )
        self._auth = {"Authorization": f"Bearer {token}"}

    @retry(
        retry=retry_if_exception_type(TransientLmsError),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=_wait,
        reraise=True,
    )
    def _request(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        try:
            response = self._http.get(url, params=params, headers=self._auth)
        except httpx.TransportError as exc:
            raise TransientLmsError(redact(str(exc))) from exc
        return self._check(response)

    def _check(self, response: httpx.Response) -> httpx.Response:
        status = response.status_code
        if status == HTTP_UNAUTHORIZED:
            raise LmsAuthorizationError(
                "O Canvas recusou o token (inválido, expirado ou revogado)."
            )
        if status == HTTP_TOO_MANY or (status == HTTP_FORBIDDEN and "Rate Limit" in response.text):
            raise TransientLmsError("limite de taxa do Canvas")
        if status >= HTTP_SERVER_ERROR:
            raise TransientLmsError(f"Canvas respondeu {status}")
        if status in (HTTP_FORBIDDEN, HTTP_NOT_FOUND):
            raise LmsForbidden(f"{status} em {redact(str(response.request.url))}")
        response.raise_for_status()
        return response

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            return self._request(f"{self._base}{API_PREFIX}{path}", params).json()
        except TransientLmsError as exc:
            raise UpstreamUnavailable(f"Canvas indisponível: {exc}") from exc

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        url: str | None = f"{self._base}{API_PREFIX}{path}"
        query: dict[str, Any] | None = {"per_page": PAGE_SIZE, **(params or {})}
        for _ in range(MAX_PAGES):
            if url is None:
                return
            try:
                response = self._request(url, query)
            except TransientLmsError as exc:
                raise UpstreamUnavailable(f"Canvas indisponível: {exc}") from exc
            yield from response.json()
            match = _NEXT_LINK.search(response.headers.get("link", ""))
            url, query = (match.group(1), None) if match else (None, None)

    @contextmanager
    def stream(self, url: str) -> Iterator[Iterator[bytes]]:
        """Download em streaming; o corpo nunca é carregado inteiro em memória."""
        with self._http.stream("GET", url, headers=self._auth) as response:
            self._check_stream(response)
            yield response.iter_bytes(CHUNK_BYTES)

    def _check_stream(self, response: httpx.Response) -> None:
        if response.status_code == HTTP_UNAUTHORIZED:
            raise LmsAuthorizationError("O Canvas recusou o token.")
        if response.status_code >= HTTP_SERVER_ERROR or response.status_code == HTTP_TOO_MANY:
            raise UpstreamUnavailable(f"Canvas respondeu {response.status_code} no download.")
        if response.status_code >= HTTP_FORBIDDEN:
            raise LmsForbidden("sem acesso ao arquivo")
