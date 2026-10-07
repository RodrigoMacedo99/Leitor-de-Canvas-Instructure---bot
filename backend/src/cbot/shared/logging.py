import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")

_TOKEN_QUERY = re.compile(r"(?i)([?&](?:access_token|token|verifier)=)[^&\s\"']+")
_TELEGRAM_BOT_URL = re.compile(r"(api\.telegram\.org/bot)[^/\s\"']+")
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")
REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    """Remove tokens de URLs e cabeçalhos antes de qualquer log (o Canvas exige token na URL de
    download e o Telegram, na rota do bot)."""
    text = _TELEGRAM_BOT_URL.sub(rf"\1{REDACTED}", text)
    return _BEARER.sub(rf"\1{REDACTED}", _TOKEN_QUERY.sub(rf"\1{REDACTED}", text))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
            "trace_id": correlation_id.get(),
        }
        extra = getattr(record, "ctx", None)
        if isinstance(extra, dict):
            payload.update({k: redact(str(v)) for k, v in extra.items()})
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
