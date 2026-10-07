"""Dublês de teste: um LMS roteirizado e um LLM falso."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from cbot.modules.canvas.public import (
    ArquivoLms,
    ColetaCurso,
    Conhecidos,
    CursoLms,
    ItemLms,
    PerfilLms,
)
from cbot.shared.errors import LmsAuthorizationError
from cbot.shared.llm import (
    LlmMessage,
    LlmResponse,
    TextBlock,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)
from cbot.shared.vocab import TipoItem

T0 = datetime(2026, 3, 1, 12, tzinfo=UTC)


@dataclass
class FakeLms:
    """LMS em memória: o teste muda `itens`/`arquivos` entre sincronizações para simular o Canvas."""

    itens: dict[int, list[ItemLms]] = field(default_factory=dict)
    arquivos: dict[int, bytes] = field(default_factory=dict)  # lms_id do arquivo -> bytes
    cursos: list[CursoLms] = field(
        default_factory=lambda: [CursoLms(1, "Redes de Computadores", "RED1", None, None)]
    )
    token_valido: bool = True
    tipos_coletados: frozenset[TipoItem] = frozenset(TipoItem)
    downloads: int = 0

    def validar_token(self) -> PerfilLms:
        if not self.token_valido:
            raise LmsAuthorizationError("token recusado")
        return PerfilLms(42, "Aluno Teste")

    def listar_cursos(self) -> list[CursoLms]:
        return self.cursos

    def listar_itens(self, curso_lms_id: int, conhecidos: Conhecidos) -> ColetaCurso:
        return ColetaCurso(list(self.itens.get(curso_lms_id, [])), self.tipos_coletados)

    @contextmanager
    def baixar_arquivo(self, arquivo: ArquivoLms) -> Iterator[Iterator[bytes]]:
        self.downloads += 1
        data = self.arquivos[arquivo.lms_id]
        yield iter([data[i : i + 7] for i in range(0, len(data), 7)])

    def factory(self, url: str, token: str) -> "FakeLms":
        return self


def item_texto(
    externo: str, titulo: str, texto: str, tipo: TipoItem = TipoItem.PAGINA, **kw: Any
) -> ItemLms:
    base: dict[str, Any] = dict(
        secao="Unidade 1", url=f"https://lms/{externo}", prazo_em=None, modificado_em=T0
    )
    return ItemLms(tipo=tipo, externo_id=externo, titulo=titulo, texto=texto, **{**base, **kw})


def item_arquivo(
    lms_id: int, nome: str, tamanho: int, mime: str = "text/plain", **kw: Any
) -> ItemLms:
    base: dict[str, Any] = dict(
        secao="Unidade 1", url=f"https://lms/files/{lms_id}", prazo_em=None, modificado_em=T0
    )
    return ItemLms(
        tipo=TipoItem.ARQUIVO, externo_id=f"file:{lms_id}", titulo=nome,
        arquivo=ArquivoLms(lms_id, nome, mime, tamanho, f"https://files/{lms_id}"), **{**base, **kw},
    )  # fmt: skip


class ScriptedLlm:
    """LLM falso: devolve respostas na ordem; guarda as chamadas para o teste inspecionar."""

    def __init__(self, *respostas: LlmResponse | str) -> None:
        self._respostas = [
            LlmResponse([TextBlock(r)], "end_turn", 10, 5) if isinstance(r, str) else r
            for r in respostas
        ]
        self.chamadas: list[dict[str, Any]] = []

    def programar(self, *respostas: LlmResponse | str) -> None:
        """Define as próximas respostas e zera o histórico de chamadas (ex.: da indexação)."""
        self.__init__(*respostas)  # type: ignore[misc]

    def complete(
        self, *, system: str, messages: list[LlmMessage], tools: list[ToolSpec] | None = None,
        fast: bool = False, max_tokens: int = 1024,
    ) -> LlmResponse:  # fmt: skip
        self.chamadas.append({"system": system, "messages": messages, "tools": tools, "fast": fast})
        if not self._respostas:
            return LlmResponse([TextBlock("ok")], "end_turn")
        return self._respostas.pop(0)


def tool_call(name: str, **args: Any) -> LlmResponse:
    return LlmResponse([ToolUseBlock("tu_1", name, args)], "tool_use", 20, 8)


def tool_results(chamada: dict[str, Any]) -> list[ToolResultBlock]:
    return [b for m in chamada["messages"] for b in m.blocks if isinstance(b, ToolResultBlock)]


class FakeCanal:
    """Canal em memória: guarda o que o bot enviou e aceita o segredo 'ok'."""

    def __init__(self, canal: "Canal", limite_aviso: bool = False) -> None:
        self.canal = canal
        self.enviados: list[tuple[str, str]] = []
        self.avisos: list[tuple[str, str]] = []

    def autentico(self, headers: Any, corpo: bytes) -> bool:
        return headers.get("x-test-secret") == "ok"

    def interpretar(self, payload: dict[str, Any]) -> list[Any]:
        from cbot.modules.mensageria.domain.ports import MensagemRecebida

        return [
            MensagemRecebida(self.canal, m["de"], m["id"], m["texto"])
            for m in payload.get("mensagens", [])
        ]

    def enviar_texto(self, destino: str, texto: str) -> None:
        self.enviados.append((destino, texto))

    def enviar_aviso_resumo(self, destino: str, texto_curto: str) -> None:
        self.avisos.append((destino, texto_curto))


from cbot.shared.vocab import Canal  # noqa: E402
