import base64
import time
from uuid import uuid4

import jwt
import pytest

from cbot.shared.errors import Unauthorized, ValidationFailed
from cbot.shared.http import RateLimiter
from cbot.shared.logging import JsonFormatter, redact
from cbot.shared.security import (
    TokenCipher,
    decode_jwt,
    hash_password,
    issue_jwt,
    verify_password,
)
from cbot.shared.text import html_to_text

KEY = base64.b64encode(b"k" * 32).decode()
SECRET = "s" * 40


def test_cipher_roundtrip_and_randomized_nonce() -> None:
    cipher = TokenCipher(KEY)
    a, b = cipher.encrypt("token-secreto"), cipher.encrypt("token-secreto")
    assert a != b and b"token-secreto" not in a
    assert cipher.decrypt(a) == "token-secreto"


def test_cipher_detects_tampering_and_bad_key() -> None:
    cipher = TokenCipher(KEY)
    blob = bytearray(cipher.encrypt("x"))
    blob[-1] ^= 1
    with pytest.raises(Exception):  # noqa: B017, PT011 - InvalidTag da biblioteca
        cipher.decrypt(bytes(blob))
    with pytest.raises(ValidationFailed):
        TokenCipher(base64.b64encode(b"curta").decode())


def test_password_hashing() -> None:
    hashed = hash_password("minha-senha-longa")
    assert hashed != "minha-senha-longa" and verify_password("minha-senha-longa", hashed)
    assert not verify_password("outra", hashed)


def test_jwt_roundtrip_expiry_and_tampering() -> None:
    aluno = uuid4()
    assert decode_jwt(issue_jwt(aluno, SECRET, 5), SECRET) == aluno
    with pytest.raises(Unauthorized):
        decode_jwt(issue_jwt(aluno, SECRET, -1), SECRET)
    with pytest.raises(Unauthorized):
        decode_jwt(issue_jwt(aluno, SECRET, 5), "outro-segredo-" * 4)
    with pytest.raises(Unauthorized):
        decode_jwt(jwt.encode({"sub": "nao-e-uuid"}, SECRET, algorithm="HS256"), SECRET)


def test_redact_hides_tokens_in_urls_and_headers() -> None:
    texto = "GET https://x/files/1?verifier=abc&token=SEGREDO123 Authorization: Bearer abc.def-ghi"
    saida = redact(texto)
    assert "SEGREDO123" not in saida and "abc.def-ghi" not in saida and "[REDACTED]" in saida


def test_json_log_is_structured_and_redacted() -> None:
    import logging

    record = logging.LogRecord(
        "t", logging.INFO, "f", 1, "baixando %s", ("https://x?token=ZZZ",), None
    )
    saida = JsonFormatter().format(record)
    assert '"level": "INFO"' in saida and "ZZZ" not in saida and "trace_id" in saida


def test_rate_limiter_sliding_window() -> None:
    limiter = RateLimiter(limit=2, window_seconds=1)
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")
    assert limiter.allow("b")
    time.sleep(1.05)
    assert limiter.allow("a")


def test_html_to_text_strips_noise_and_keeps_blocks() -> None:
    html = "<style>x{}</style><h1>Título</h1><p>Linha&nbsp;um<br>dois</p><script>alert(1)</script>"
    assert html_to_text(html) == "Título\nLinha um\ndois"
    assert html_to_text(None) == "" and html_to_text("") == ""
