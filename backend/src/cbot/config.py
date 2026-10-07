from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
POSTGRES_SCHEMES = ("postgresql://", "postgres://")
DRIVER_URL_PREFIX = "postgresql+psycopg://"


class Settings(BaseSettings):
    """Toda configuração vem de variáveis de ambiente (nunca do código)."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(alias="DATABASE_URL")

    jwt_secret: SecretStr = Field(alias="JWT_SECRET")
    jwt_expires_minutes: int = Field(default=480, alias="JWT_EXPIRES_MINUTES")
    cors_origin: str = Field(default="http://localhost:5173", alias="CORS_ORIGIN")
    registro_aberto: bool = Field(default=True, alias="REGISTRO_ABERTO")

    # Chave AES-256 (32 bytes em base64) que cifra o token do Canvas em repouso.
    token_encryption_key: SecretStr = Field(alias="TOKEN_ENCRYPTION_KEY")

    storage_dir: Path = Field(default=Path("./data/arquivos"), alias="STORAGE_DIR")
    max_download_bytes: int = Field(default=200 * 1024 * 1024, alias="MAX_DOWNLOAD_BYTES")
    sync_interval_hours: float = Field(default=6.0, alias="SYNC_INTERVAL_HOURS")

    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    claude_model_chat: str = Field(default="claude-sonnet-5-5", alias="CLAUDE_MODEL_CHAT")
    claude_model_fast: str = Field(default="claude-haiku-4-5-20251001", alias="CLAUDE_MODEL_FAST")

    contextual_retrieval: bool = Field(default=True, alias="CONTEXTUAL_RETRIEVAL")
    rag_min_similarity: float = Field(default=0.35, alias="RAG_MIN_SIMILARITY")
    allow_local_lms: bool = Field(default=False, alias="ALLOW_LOCAL_LMS")

    embedding_provider: str = Field(default="ollama", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="bge-m3", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=1024, alias="EMBEDDING_DIM")
    ollama_url: str = Field(default="http://localhost:11434", alias="OLLAMA_URL")

    telegram_bot_token: SecretStr | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: SecretStr | None = Field(default=None, alias="TELEGRAM_WEBHOOK_SECRET")
    whatsapp_access_token: SecretStr | None = Field(default=None, alias="WHATSAPP_ACCESS_TOKEN")
    whatsapp_phone_number_id: str | None = Field(default=None, alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_app_secret: SecretStr | None = Field(default=None, alias="WHATSAPP_APP_SECRET")
    whatsapp_verify_token: SecretStr | None = Field(default=None, alias="WHATSAPP_VERIFY_TOKEN")
    whatsapp_summary_template: str = Field(
        default="resumo_diario", alias="WHATSAPP_SUMMARY_TEMPLATE"
    )

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        for scheme in POSTGRES_SCHEMES:
            if value.startswith(scheme):
                return DRIVER_URL_PREFIX + value[len(scheme) :]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
