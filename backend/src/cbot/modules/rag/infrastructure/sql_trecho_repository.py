import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from cbot.modules.rag.domain.ports import TrechoNovo
from cbot.modules.rag.domain.ranking import Candidato

_WORD = re.compile(r"\w{3,}", re.UNICODE)
MAX_QUERY_TERMS = 12
_CURSO_FILTER = "AND (CAST(:curso AS uuid) IS NULL OR i.curso_id = :curso)"


def vector_literal(vetor: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vetor) + "]"


def or_tsquery(consulta: str) -> str | None:
    """Perguntas em linguagem natural não casam com AND; usa OR dos termos (o ranking separa)."""
    termos = list(dict.fromkeys(w.lower() for w in _WORD.findall(consulta)))[:MAX_QUERY_TERMS]
    return " | ".join(termos) or None


def _candidato(r: Any, sim: float | None) -> Candidato:
    return Candidato(
        trecho_id=r["id"], texto=r["texto"], contexto=r["contexto"],
        metadados=r["metadados"], similaridade=sim,
    )  # fmt: skip


class SqlTrechoRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def substituir_trechos(
        self, aluno_id: UUID, item_id: UUID, arquivo_id: UUID | None, modelo_emb: str,
        trechos: list[TrechoNovo],
    ) -> int:  # fmt: skip
        self.remover_trechos_do_item(aluno_id, item_id)
        for t in trechos:
            self._s.execute(
                text(
                    "INSERT INTO trechos (aluno_id, item_id, arquivo_id, ordem, texto, contexto, "
                    "embedding, modelo_emb, metadados) VALUES (:a, :i, :f, :o, :t, :c, "
                    "CAST(:e AS vector), :m, CAST(:md AS jsonb))"
                ),
                {"a": aluno_id, "i": item_id, "f": arquivo_id, "o": t.ordem, "t": t.texto,
                 "c": t.contexto, "e": vector_literal(t.embedding), "m": modelo_emb,
                 "md": json.dumps(t.metadados)},
            )  # fmt: skip
        return len(trechos)

    def remover_trechos_do_item(self, aluno_id: UUID, item_id: UUID) -> int:
        result = self._s.execute(
            text("DELETE FROM trechos WHERE aluno_id = :a AND item_id = :i"),
            {"a": aluno_id, "i": item_id},
        )
        return int(result.rowcount)  # type: ignore[attr-defined]

    def busca_vetorial(
        self, aluno_id: UUID, vetor: list[float], curso_id: UUID | None, limite: int
    ) -> list[Candidato]:
        rows = self._s.execute(
            text(
                "SELECT t.id, t.texto, t.contexto, t.metadados, "
                "1 - (t.embedding <=> CAST(:v AS vector)) AS sim "
                "FROM trechos t JOIN itens_curso i ON i.id = t.item_id AND i.aluno_id = t.aluno_id "
                f"WHERE t.aluno_id = :a AND i.status = 'ativo' {_CURSO_FILTER} "
                "ORDER BY t.embedding <=> CAST(:v AS vector) LIMIT :lim"
            ),
            {"v": vector_literal(vetor), "a": aluno_id, "curso": curso_id, "lim": limite},
        ).mappings()
        return [_candidato(r, float(r["sim"])) for r in rows]

    def busca_textual(
        self, aluno_id: UUID, consulta: str, curso_id: UUID | None, limite: int
    ) -> list[Candidato]:
        tsquery = or_tsquery(consulta)
        if tsquery is None:
            return []
        rows = self._s.execute(
            text(
                "SELECT t.id, t.texto, t.contexto, t.metadados "
                "FROM trechos t JOIN itens_curso i ON i.id = t.item_id AND i.aluno_id = t.aluno_id, "
                "to_tsquery('portuguese', :q) AS query "
                f"WHERE t.aluno_id = :a AND i.status = 'ativo' AND t.tsv @@ query {_CURSO_FILTER} "
                "ORDER BY ts_rank_cd(t.tsv, query) DESC LIMIT :lim"
            ),
            {"q": tsquery, "a": aluno_id, "curso": curso_id, "lim": limite},
        ).mappings()
        return [_candidato(r, None) for r in rows]
