import httpx
import pytest
import respx

from cbot.modules.canvas.infrastructure.client import (
    CanvasHttpClient,
    LmsForbidden,
    normalizar_url_base,
)
from cbot.shared.errors import LmsAuthorizationError, UpstreamUnavailable, ValidationFailed

BASE = "https://escola.instructure.com"


@pytest.fixture
def client() -> CanvasHttpClient:
    return CanvasHttpClient(BASE, "tok-secreto")


@respx.mock
def test_paginate_follows_link_header(client: CanvasHttpClient) -> None:
    page2 = f"{BASE}/api/v1/courses?page=2"
    respx.get(f"{BASE}/api/v1/courses", params={"per_page": 100}).mock(
        return_value=httpx.Response(
            200, json=[{"id": 1}], headers={"link": f'<{page2}>; rel="next"'}
        )
    )
    respx.get(page2).mock(return_value=httpx.Response(200, json=[{"id": 2}]))
    assert [c["id"] for c in client.paginate("/courses")] == [1, 2]


@respx.mock
def test_sends_bearer_token(client: CanvasHttpClient) -> None:
    route = respx.get(f"{BASE}/api/v1/users/self").mock(return_value=httpx.Response(200, json={}))
    client.get_json("/users/self")
    assert route.calls.last.request.headers["authorization"] == "Bearer tok-secreto"


@respx.mock
def test_401_raises_authorization_error(client: CanvasHttpClient) -> None:
    respx.get(f"{BASE}/api/v1/users/self").mock(return_value=httpx.Response(401))
    with pytest.raises(LmsAuthorizationError):
        client.get_json("/users/self")


@respx.mock
def test_retries_on_rate_limit_then_succeeds(client: CanvasHttpClient) -> None:
    route = respx.get(f"{BASE}/api/v1/x").mock(
        side_effect=[
            httpx.Response(403, text="403 Forbidden (Rate Limit Exceeded)"),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    assert client.get_json("/x") == {"ok": True}
    assert route.call_count == 2


@respx.mock
def test_gives_up_after_repeated_5xx(client: CanvasHttpClient) -> None:
    respx.get(f"{BASE}/api/v1/x").mock(return_value=httpx.Response(503))
    with pytest.raises(UpstreamUnavailable):
        client.get_json("/x")


@respx.mock
def test_forbidden_without_rate_limit_is_not_retried(client: CanvasHttpClient) -> None:
    route = respx.get(f"{BASE}/api/v1/x").mock(return_value=httpx.Response(403, text="nope"))
    with pytest.raises(LmsForbidden):
        client.get_json("/x")
    assert route.call_count == 1


@respx.mock
def test_stream_yields_chunks(client: CanvasHttpClient) -> None:
    respx.get("https://files.example.com/f").mock(return_value=httpx.Response(200, content=b"abc"))
    with client.stream("https://files.example.com/f") as chunks:
        assert b"".join(chunks) == b"abc"


@respx.mock
def test_stream_maps_errors(client: CanvasHttpClient) -> None:
    respx.get("https://files.example.com/401").mock(return_value=httpx.Response(401))
    respx.get("https://files.example.com/403").mock(return_value=httpx.Response(403))
    respx.get("https://files.example.com/500").mock(return_value=httpx.Response(500))
    for url, exc in [
        ("401", LmsAuthorizationError),
        ("403", LmsForbidden),
        ("500", UpstreamUnavailable),
    ]:
        with pytest.raises(exc), client.stream(f"https://files.example.com/{url}"):
            pass


@pytest.mark.parametrize(
    "url",
    [
        "http://escola.instructure.com",
        "https://127.0.0.1",
        "https://10.0.0.5",
        "https://localhost",
        "https://",
    ],
)
def test_url_guard_rejects_unsafe(url: str) -> None:
    with pytest.raises(ValidationFailed):
        normalizar_url_base(url)


def test_url_guard_keeps_only_origin() -> None:
    assert normalizar_url_base("https://Escola.instructure.com/courses/1?x=1") == BASE


def test_url_guard_allows_local_http_when_enabled() -> None:
    assert (
        normalizar_url_base("http://localhost:3000", permitir_http_local=True)
        == "http://localhost:3000"
    )
