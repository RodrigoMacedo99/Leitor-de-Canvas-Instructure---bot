"""Porta de LLM (kernel compartilhado). Os módulos falam com `LlmClient`, nunca com um SDK."""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str
    cache: bool = False  # marca o bloco como cacheável (prompt caching do provedor)


@dataclass(frozen=True, slots=True)
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResultBlock:
    tool_use_id: str
    content: str
    is_error: bool = False


type Block = TextBlock | ToolUseBlock | ToolResultBlock


@dataclass(frozen=True, slots=True)
class LlmMessage:
    role: Literal["user", "assistant"]
    blocks: list[Block]

    @staticmethod
    def user(text: str) -> "LlmMessage":
        return LlmMessage("user", [TextBlock(text)])

    @staticmethod
    def assistant(text: str) -> "LlmMessage":
        return LlmMessage("assistant", [TextBlock(text)])


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LlmResponse:
    blocks: list[Block]
    stop_reason: str
    tokens_in: int = 0
    tokens_out: int = 0
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "".join(b.text for b in self.blocks if isinstance(b, TextBlock)).strip()

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        return [b for b in self.blocks if isinstance(b, ToolUseBlock)]


class LlmClient(Protocol):
    def complete(
        self,
        *,
        system: str,
        messages: list[LlmMessage],
        tools: list[ToolSpec] | None = None,
        fast: bool = False,
        max_tokens: int = 1024,
    ) -> LlmResponse:
        """`fast=True` pede o modelo menor (contextualização, reescrita, resumos intermediários)."""
        ...
