import logging

from cbot.shared.llm import LlmClient, LlmMessage, TextBlock

logger = logging.getLogger(__name__)
MAX_DOC_CHARS = 12_000
MAX_CONTEXT_CHARS = 400

_SYSTEM = (
    "Você situa trechos de material didático dentro do documento de origem. "
    "Responda SOMENTE com 1 ou 2 frases em português, curtas, que expliquem de que parte do "
    "documento o trecho vem e sobre o que ele trata, para melhorar a busca. Sem preâmbulo."
)


class NoContextualizer:
    """Null Object: indexa o trecho sem contexto extra (zero custo de LLM)."""

    def contextualizar(self, titulo: str, documento: str, trecho: str) -> str | None:
        return None


class LlmContextualizer:
    """Contextual Retrieval com o modelo pequeno. O documento vai num bloco cacheável, então
    os N trechos do mesmo arquivo pagam o documento uma só vez."""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def contextualizar(self, titulo: str, documento: str, trecho: str) -> str | None:
        mensagem = LlmMessage(
            "user",
            [
                TextBlock(
                    f"<documento titulo={titulo!r}>\n{documento[:MAX_DOC_CHARS]}\n</documento>",
                    cache=True,
                ),
                TextBlock(f"<trecho>\n{trecho}\n</trecho>"),
            ],
        )
        try:
            resposta = self._llm.complete(
                system=_SYSTEM, messages=[mensagem], fast=True, max_tokens=150
            )
        except Exception:
            logger.warning("contextualização falhou; trecho segue sem contexto", exc_info=True)
            return None
        return resposta.text[:MAX_CONTEXT_CHARS] or None
