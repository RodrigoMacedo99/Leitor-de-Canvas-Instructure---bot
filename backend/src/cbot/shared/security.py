import base64
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from cbot.shared.errors import Unauthorized, ValidationFailed

NONCE_BYTES = 12
KEY_BYTES = 32
JWT_ALGORITHM = "HS256"
BCRYPT_MAX_BYTES = 72


class TokenCipher:
    """AES-256-GCM para o token do Canvas em repouso (nonce || ciphertext+tag)."""

    def __init__(self, key_b64: str) -> None:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = base64.b64decode(key_b64)
        if len(key) != KEY_BYTES:
            raise ValidationFailed("TOKEN_ENCRYPTION_KEY deve ter 32 bytes em base64.")
        self._aead = AESGCM(key)

    def encrypt(self, plaintext: str) -> bytes:
        nonce = os.urandom(NONCE_BYTES)
        return nonce + self._aead.encrypt(nonce, plaintext.encode("utf-8"), None)

    def decrypt(self, blob: bytes) -> str:
        nonce, data = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
        return self._aead.decrypt(nonce, data, None).decode("utf-8")


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    raw = password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(raw, hashed.encode("ascii"))


def issue_jwt(aluno_id: UUID, secret: str, expires_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {"sub": str(aluno_id), "iat": now, "exp": now + timedelta(minutes=expires_minutes)}
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str, secret: str) -> UUID:
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise Unauthorized("Token inválido ou expirado.") from exc
