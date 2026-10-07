"""Chunking estrutural: respeita parágrafos e fronteiras de página/título, com sobreposição."""

import re
from dataclasses import dataclass
from typing import Protocol

TARGET_CHARS = 2800  # ~700 tokens em português
OVERLAP_RATIO = 0.12
MIN_CHARS = 120
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class SecaoEntrada:
    texto: str
    pagina: int | None = None
    titulo: str | None = None


@dataclass(frozen=True, slots=True)
class ChunkBruto:
    ordem: int
    texto: str
    pagina: int | None
    titulo: str | None


class Chunker(Protocol):
    def dividir(self, secoes: list[SecaoEntrada]) -> list[ChunkBruto]: ...


def _split_long(paragraph: str, limit: int) -> list[str]:
    """Quebra parágrafo gigante em sentenças e, em último caso, em fatias fixas."""
    pieces: list[str] = []
    atual = ""
    for sentence in _SENTENCE_END.split(paragraph):
        for fatia in (sentence[i : i + limit] for i in range(0, len(sentence), limit)):
            if atual and len(atual) + len(fatia) + 1 > limit:
                pieces.append(atual)
                atual = ""
            atual = f"{atual} {fatia}".strip()
    if atual:
        pieces.append(atual)
    return pieces


class StructuralChunker:
    """Agrupa parágrafos até ~`target` caracteres; cada seção (página/slide/título) é chunkeada à parte."""

    def __init__(self, target: int = TARGET_CHARS, overlap_ratio: float = OVERLAP_RATIO) -> None:
        self._target = target
        self._overlap = int(target * overlap_ratio)
        self._limite_parte = target - self._overlap - 1  # cabe junto do prefixo de sobreposição

    def dividir(self, secoes: list[SecaoEntrada]) -> list[ChunkBruto]:
        chunks: list[ChunkBruto] = []
        for secao in secoes:
            for texto in self._dividir_secao(secao.texto):
                chunks.append(ChunkBruto(len(chunks), texto, secao.pagina, secao.titulo))
        return self._absorver_miudos(chunks, self._target)

    def _dividir_secao(self, texto: str) -> list[str]:
        paragrafos = [p.strip() for p in re.split(r"\n\s*\n|\n", texto) if p.strip()]
        partes: list[str] = []
        for p in paragrafos:
            partes.extend(
                _split_long(p, self._limite_parte) if len(p) > self._limite_parte else [p]
            )
        return self._agrupar(partes)

    def _agrupar(self, partes: list[str]) -> list[str]:
        grupos: list[str] = []
        atual = ""
        for parte in partes:
            if atual and len(atual) + len(parte) + 1 > self._target:
                grupos.append(atual)
                atual = atual[-self._overlap :].lstrip() if self._overlap else ""
            atual = f"{atual}\n{parte}".strip()
        if atual:
            grupos.append(atual)
        return grupos

    @staticmethod
    def _absorver_miudos(chunks: list[ChunkBruto], limite: int) -> list[ChunkBruto]:
        """Chunks minúsculos (ex.: slide só com título) se juntam ao anterior da mesma origem."""
        out: list[ChunkBruto] = []
        for chunk in chunks:
            if (
                out
                and len(chunk.texto) < MIN_CHARS
                and out[-1].titulo == chunk.titulo
                and len(out[-1].texto) + len(chunk.texto) + 1 <= limite
            ):
                anterior = out[-1]
                out[-1] = ChunkBruto(
                    anterior.ordem,
                    f"{anterior.texto}\n{chunk.texto}",
                    anterior.pagina,
                    anterior.titulo,
                )
            else:
                out.append(ChunkBruto(len(out), chunk.texto, chunk.pagina, chunk.titulo))
        return out
