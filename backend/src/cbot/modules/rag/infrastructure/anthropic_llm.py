"""Adaptador da Anthropic API para a porta `LlmClient` (com prompt caching e tool use)."""

from typing import Any

import anthropic

from cbot.shared.errors import UpstreamUnavailable
from cbot.shared.llm import (
    Block,
    LlmMessage,
    LlmResponse,
    TextBlock,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)

CACHE = {"type": "ephemeral"}


def _block_to_api(block: Block) -> dict[str, Any]:
    match block:
        case TextBlock(text=text, cache=cache):
            data: dict[str, Any] = {"type": "text", "text": text}
            if cache:
                data["cache_control"] = CACHE
            return data
        case ToolUseBlock(id=id_, name=name, input=input_):
            return {"type": "tool_use", "id": id_, "name": name, "input": input_}
        case ToolResultBlock(tool_use_id=tid, content=content, is_error=is_error):
            return {
                "type": "tool_result",
                "tool_use_id": tid,
                "content": content,
                "is_error": is_error,
            }


def _block_from_api(block: Any) -> Block | None:
    match block.type:
        case "text":
            return TextBlock(block.text)
        case "tool_use":
            return ToolUseBlock(block.id, block.name, dict(block.input))
        case _:
            return None


class AnthropicLlm:
    def __init__(
        self, api_key: str, model_chat: str, model_fast: str, client: Any | None = None
    ) -> None:
        self._client = client or anthropic.Anthropic(api_key=api_key)
        self._model_chat = model_chat
        self._model_fast = model_fast

    def complete(
        self, *, system: str, messages: list[LlmMessage], tools: list[ToolSpec] | None = None,
        fast: bool = False, max_tokens: int = 1024,
    ) -> LlmResponse:  # fmt: skip
        kwargs: dict[str, Any] = {
            "model": self._model_fast if fast else self._model_chat,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": CACHE}],
            "messages": [
                {"role": m.role, "content": [_block_to_api(b) for b in m.blocks]} for m in messages
            ],
        }
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]
        try:
            response = self._client.messages.create(**kwargs)
        except anthropic.APIError as exc:
            raise UpstreamUnavailable(f"Anthropic API indisponível: {exc}") from exc
        blocks = [b for b in map(_block_from_api, response.content) if b is not None]
        return LlmResponse(
            blocks=blocks, stop_reason=response.stop_reason or "",
            tokens_in=response.usage.input_tokens, tokens_out=response.usage.output_tokens,
        )  # fmt: skip
