import hashlib
import math
import re

import httpx

from cbot.shared.errors import UpstreamUnavailable

_TOKEN = re.compile(r"\w+", re.UNICODE)
EMBED_TIMEOUT = httpx.Timeout(120.0, connect=5.0)
BATCH_SIZE = 16


class OllamaEmbedder:
    """Embeddings locais (ex.: bge-m3) via Ollama — o corpus não sai da máquina."""

    def __init__(
        self, base_url: str, model: str, dim: int, http: httpx.Client | None = None
    ) -> None:
        self.model_id = f"ollama:{model}"
        self.dim = dim
        self._url = f"{base_url.rstrip('/')}/api/embed"
        self._model = model
        self._http = http or httpx.Client(timeout=EMBED_TIMEOUT)

    def embed(self, textos: list[str]) -> list[list[float]]:
        vetores: list[list[float]] = []
        for i in range(0, len(textos), BATCH_SIZE):
            vetores.extend(self._embed_batch(textos[i : i + BATCH_SIZE]))
        return vetores

    def _embed_batch(self, lote: list[str]) -> list[list[float]]:
        try:
            response = self._http.post(self._url, json={"model": self._model, "input": lote})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable(f"Ollama indisponível para embeddings: {exc}") from exc
        embeddings: list[list[float]] = response.json()["embeddings"]
        if any(len(v) != self.dim for v in embeddings):
            raise UpstreamUnavailable(f"Dimensão de embedding diferente de {self.dim}.")
        return embeddings


class HashingEmbedder:
    """Embedder determinístico (feature hashing de palavras), sem modelo e sem rede.

    Serve para testes e para rodar o sistema sem Ollama; textos com palavras em comum ficam
    próximos. Para produção use um modelo real (bge-m3 via Ollama).
    """

    model_id = "hashing-v1"

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim

    def embed(self, textos: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in textos]

    def _vector(self, texto: str) -> list[float]:
        vetor = [0.0] * self.dim
        for palavra in _TOKEN.findall(texto.lower()):
            digest = hashlib.blake2b(palavra.encode(), digest_size=8).digest()
            indice = int.from_bytes(digest[:4], "big") % self.dim
            sinal = 1.0 if digest[4] % 2 == 0 else -1.0
            vetor[indice] += sinal
        norma = math.sqrt(sum(v * v for v in vetor)) or 1.0
        return [v / norma for v in vetor]
