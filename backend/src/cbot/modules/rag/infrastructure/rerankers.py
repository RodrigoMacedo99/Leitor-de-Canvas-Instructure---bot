from cbot.modules.rag.domain.ranking import Candidato


class NoopReranker:
    """Null Object: mantém a ordem da fusão RRF e só corta em `top_k`."""

    def rerank(self, consulta: str, candidatos: list[Candidato], top_k: int) -> list[Candidato]:
        return candidatos[:top_k]


class CrossEncoderReranker:
    """Cross-encoder local (ex.: BAAI/bge-reranker-v2-m3). Requer `sentence-transformers`
    (extra opcional, pesado: PyTorch); por isso o import é tardio."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover - dependência opcional
            raise RuntimeError("Instale sentence-transformers para usar o reranker.") from exc
        self._model = CrossEncoder(model_name)

    def rerank(
        self, consulta: str, candidatos: list[Candidato], top_k: int
    ) -> list[Candidato]:  # pragma: no cover - requer o modelo baixado
        if not candidatos:
            return []
        scores = self._model.predict(
            [(consulta, f"{c.contexto or ''} {c.texto}") for c in candidatos]
        )
        ordenados = sorted(
            zip(candidatos, scores, strict=True), key=lambda p: float(p[1]), reverse=True
        )
        return [
            Candidato(c.trecho_id, c.texto, c.contexto, c.metadados, c.similaridade, float(s))
            for c, s in ordenados[:top_k]
        ]
