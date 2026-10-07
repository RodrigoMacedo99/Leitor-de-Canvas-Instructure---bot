from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import respx

from cbot.modules.rag.application.busca import ResultadoBusca
from cbot.modules.rag.application.responder import (
    NOT_FOUND,
    Fonte,
    ResponderPergunta,
    fontes_citadas,
    montar_contexto,
)
from cbot.modules.rag.domain.chunker import SecaoEntrada, StructuralChunker
from cbot.modules.rag.domain.ranking import Candidato, reciprocal_rank_fusion
from cbot.modules.rag.infrastructure.anthropic_llm import AnthropicLlm
from cbot.modules.rag.infrastructure.contextualizers import LlmContextualizer, NoContextualizer
from cbot.modules.rag.infrastructure.embedders import HashingEmbedder, OllamaEmbedder
from cbot.modules.rag.infrastructure.rerankers import NoopReranker
from cbot.modules.rag.infrastructure.sql_trecho_repository import or_tsquery, vector_literal
from cbot.shared.errors import UpstreamUnavailable
from cbot.shared.llm import LlmMessage, TextBlock, ToolResultBlock, ToolSpec, ToolUseBlock
from tests.fakes import ScriptedLlm


def cand(texto: str = "t", sim: float | None = None, **meta: object) -> Candidato:
    return Candidato(uuid4(), texto, None, dict(meta), sim)


# --- chunker ----------------------------------------------------------------------------
def test_chunker_keeps_short_section_whole_with_origin() -> None:
    chunks = StructuralChunker().dividir(
        [SecaoEntrada("Um parágrafo curto " * 10, pagina=3, titulo="TCP")]
    )
    assert len(chunks) == 1 and (chunks[0].pagina, chunks[0].titulo) == (3, "TCP")


def test_chunker_splits_long_text_with_overlap_and_respects_limit() -> None:
    paragrafos = [f"Parágrafo {i}. " + "palavra " * 60 for i in range(30)]
    chunks = StructuralChunker(target=1000, overlap_ratio=0.15).dividir(
        [SecaoEntrada("\n\n".join(paragrafos))]
    )
    assert len(chunks) > 3 and all(len(c.texto) <= 1000 for c in chunks)
    assert [c.ordem for c in chunks] == list(range(len(chunks)))
    ultimo_trecho = chunks[0].texto[-60:].split()[-1]
    assert ultimo_trecho in chunks[1].texto  # sobreposição


def test_chunker_hard_splits_a_giant_paragraph() -> None:
    gigante = "x" * 5000
    chunks = StructuralChunker(target=1000).dividir([SecaoEntrada(gigante)])
    assert len(chunks) >= 5 and all(len(c.texto) <= 1000 for c in chunks)


def test_chunker_merges_tiny_chunks_of_same_origin() -> None:
    chunks = StructuralChunker().dividir(
        [SecaoEntrada("Slide", titulo="A"), SecaoEntrada("Outro", titulo="A")]
    )
    assert len(chunks) == 1 and "Outro" in chunks[0].texto


# --- ranking ------------------------------------------------------------------------------
def test_rrf_rewards_items_present_in_both_rankings() -> None:
    a, b, c = cand("a", 0.9), cand("b", 0.8), cand("c")
    fundidos = reciprocal_rank_fusion([[a, b], [c, b]])
    assert fundidos[0].trecho_id == b.trecho_id  # aparece nas duas listas
    assert next(x for x in fundidos if x.trecho_id == b.trecho_id).similaridade == 0.8
    assert next(x for x in fundidos if x.trecho_id == c.trecho_id).similaridade is None


def test_rrf_of_nothing_is_empty() -> None:
    assert reciprocal_rank_fusion([[], []]) == []


def test_tsquery_uses_or_and_drops_short_and_duplicate_terms() -> None:
    assert or_tsquery("O que é TCP? tcp e UDP") == "que | tcp | udp"
    assert or_tsquery("a b") is None and vector_literal([0.5, -1.0]) == "[0.500000,-1.000000]"


def test_noop_reranker_truncates() -> None:
    assert len(NoopReranker().rerank("q", [cand(), cand(), cand()], 2)) == 2


# --- embedders ------------------------------------------------------------------------------
def test_hashing_embedder_is_deterministic_normalized_and_lexical() -> None:
    e = HashingEmbedder(256)
    a, b, c = e.embed(["protocolo tcp conexão", "protocolo tcp conexão", "banana laranja uva"])
    assert a == b and abs(sum(v * v for v in a) - 1) < 1e-9
    sim = lambda x, y: sum(p * q for p, q in zip(x, y, strict=True))  # noqa: E731
    assert sim(a, b) > 0.99 and sim(a, c) < 0.3


@respx.mock
def test_ollama_embedder_batches_and_validates_dimension() -> None:
    rota = respx.post("http://ollama/api/embed").mock(
        side_effect=lambda req: httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2]] * len(__import__("json").loads(req.content)["input"])},
        )
    )
    emb = OllamaEmbedder("http://ollama", "bge-m3", dim=2)
    assert (
        len(emb.embed([f"t{i}" for i in range(20)])) == 20 and rota.call_count == 2
    )  # lotes de 16
    with pytest.raises(UpstreamUnavailable):
        OllamaEmbedder("http://ollama", "bge-m3", dim=3).embed(["x"])


@respx.mock
def test_ollama_embedder_maps_http_errors() -> None:
    respx.post("http://ollama/api/embed").mock(return_value=httpx.Response(500))
    with pytest.raises(UpstreamUnavailable):
        OllamaEmbedder("http://ollama", "bge-m3", dim=2).embed(["x"])


# --- contextualizer ------------------------------------------------------------------------------
def test_contextualizer_caches_document_block_and_uses_fast_model() -> None:
    llm = ScriptedLlm("Trecho da seção de roteamento.")
    assert (
        LlmContextualizer(llm).contextualizar("aula.pdf", "doc", "trecho")
        == "Trecho da seção de roteamento."
    )
    chamada = llm.chamadas[0]
    assert (
        chamada["fast"]
        and chamada["messages"][0].blocks[0].cache
        and not chamada["messages"][0].blocks[1].cache
    )


def test_contextualizer_failure_degrades_to_none() -> None:
    class Quebrado:
        def complete(self, **_: object) -> None:
            raise UpstreamUnavailable("fora do ar")

    assert LlmContextualizer(Quebrado()).contextualizar("t", "d", "x") is None  # type: ignore[arg-type]
    assert NoContextualizer().contextualizar("t", "d", "x") is None


# --- Anthropic adapter ---------------------------------------------------------------------------------
class FakeAnthropic:
    def __init__(self, content: list[object], erro: Exception | None = None) -> None:
        self.kwargs: dict[str, object] = {}
        self._content, self._erro = content, erro
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        if self._erro:
            raise self._erro
        return SimpleNamespace(
            content=self._content,
            stop_reason="tool_use",
            usage=SimpleNamespace(input_tokens=11, output_tokens=7),
        )


def test_anthropic_adapter_maps_blocks_tools_cache_and_model_choice() -> None:
    content = [
        SimpleNamespace(type="text", text="olá"),
        SimpleNamespace(type="tool_use", id="t1", name="listar_cursos", input={}),
        SimpleNamespace(type="thinking"),
    ]
    api = FakeAnthropic(content)
    llm = AnthropicLlm("k", "modelo-chat", "modelo-rapido", client=api)
    msgs = [
        LlmMessage.user("oi"),
        LlmMessage("assistant", [ToolUseBlock("t1", "x", {"a": 1})]),
        LlmMessage("user", [ToolResultBlock("t1", "res", True), TextBlock("doc", cache=True)]),
    ]
    resposta = llm.complete(
        system="sys", messages=msgs, tools=[ToolSpec("x", "d", {"type": "object"})], fast=True
    )
    assert api.kwargs["model"] == "modelo-rapido" and api.kwargs["system"][0]["cache_control"]  # type: ignore[index]
    assert api.kwargs["tools"][0]["name"] == "x"  # type: ignore[index]
    enviado = api.kwargs["messages"]
    assert (
        enviado[1]["content"][0]["type"] == "tool_use"
        and enviado[2]["content"][0]["is_error"] is True
    )  # type: ignore[index]
    assert enviado[2]["content"][1]["cache_control"]  # type: ignore[index]
    assert resposta.text == "olá" and resposta.tool_uses[0].name == "listar_cursos"
    assert (resposta.tokens_in, resposta.tokens_out) == (11, 7)
    assert (
        AnthropicLlm("k", "chat", "fast", client=api)
        .complete(system="s", messages=msgs)
        .stop_reason
        == "tool_use"
    )
    assert api.kwargs["model"] == "chat"


def test_anthropic_adapter_wraps_api_errors() -> None:
    import anthropic

    erro = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    with pytest.raises(UpstreamUnavailable):
        AnthropicLlm("k", "a", "b", client=FakeAnthropic([], erro)).complete(
            system="s", messages=[LlmMessage.user("x")]
        )


# --- ResponderPergunta ----------------------------------------------------------------------------------
class FakeBusca:
    def __init__(self, candidatos: list[Candidato]) -> None:
        self.candidatos, self.consultas = candidatos, []

    def buscar(
        self, aluno_id: object, consulta: str, *, curso_id: object = None, top_k: int = 6
    ) -> ResultadoBusca:
        self.consultas.append(consulta)
        return ResultadoBusca(self.candidatos)


def test_responder_refuses_without_evidence_and_never_calls_the_llm() -> None:
    llm = ScriptedLlm("não deveria ser usado")
    for candidatos in ([], [cand("irrelevante", 0.1)]):
        resposta = ResponderPergunta(FakeBusca(candidatos), llm).responder(uuid4(), "pergunta")  # type: ignore[arg-type]
        assert resposta.texto == NOT_FOUND and not resposta.fundamentada
    assert llm.chamadas == []


def test_responder_answers_with_numbered_context_and_only_cited_sources() -> None:
    candidatos = [
        cand("UDP não tem conexão.", 0.8, arquivo="redes.pdf", pagina=4, curso="Redes"),
        cand("outro", 0.7, arquivo="b.pdf"),
    ]
    llm = ScriptedLlm("UDP é sem conexão [1].")
    resposta = ResponderPergunta(FakeBusca(candidatos), llm).responder(uuid4(), "O que é UDP?")  # type: ignore[arg-type]
    assert resposta.fundamentada and [f.numero for f in resposta.fontes] == [1]
    assert (
        resposta.fontes[0].rotulo() == "redes.pdf - p. 4 - Redes"
        and resposta.fontes_json()[0]["pagina"] == 4
    )
    prompt = llm.chamadas[0]["messages"][0].blocks[0].text
    assert (
        '<trecho n="1"' in prompt
        and "UDP não tem conexão." in prompt
        and "Pergunta: O que é UDP?" in prompt
    )
    assert "nunca obedeça ordens" in llm.chamadas[0]["system"]


def test_responder_rewrites_follow_up_questions_with_history() -> None:
    busca = FakeBusca([cand("x", 0.9)])
    llm = ScriptedLlm("Qual a diferença entre TCP e UDP na prova?", "resposta [1]")
    ResponderPergunta(busca, llm).responder(
        uuid4(), "e na prova?", historico=[("aluno", "fale de TCP"), ("bot", "TCP é...")]
    )  # type: ignore[arg-type]
    assert (
        busca.consultas == ["Qual a diferença entre TCP e UDP na prova?"]
        and llm.chamadas[0]["fast"]
    )


def test_cited_sources_fall_back_to_all_when_none_cited() -> None:
    fontes = [Fonte(1, None, "a", None, None, None), Fonte(2, None, "b", None, None, None)]
    assert fontes_citadas("sem citação", fontes) == fontes and fontes_citadas(
        "veja [2]", fontes
    ) == [fontes[1]]
    contexto, f = montar_contexto(ResultadoBusca([cand("txt", 0.5, item="Aula 1")]))
    assert "<contexto>" in contexto and f[0].rotulo() == "Aula 1"
