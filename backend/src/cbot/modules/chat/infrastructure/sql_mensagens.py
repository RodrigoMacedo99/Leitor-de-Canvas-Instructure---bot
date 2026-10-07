import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


class SqlMensagemRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def historico(self, aluno_id: UUID, canal: str, limite: int) -> list[tuple[str, str]]:
        rows = self._s.execute(
            text(
                "SELECT direcao, texto FROM mensagens WHERE aluno_id = :a AND canal = :c "
                "ORDER BY criado_em DESC LIMIT :l"
            ),
            {"a": aluno_id, "c": canal, "l": limite},
        ).all()
        return [("aluno" if d == "in" else "bot", t) for d, t in reversed(rows)]

    def registrar(
        self, aluno_id: UUID, canal: str, direcao: str, externo_id: str | None, texto: str,
        fontes: list[dict[str, Any]] | None = None, tokens_in: int | None = None,
        tokens_out: int | None = None, quando: datetime | None = None,
    ) -> bool:  # fmt: skip
        result = self._s.execute(
            text(
                "INSERT INTO mensagens (aluno_id, canal, direcao, externo_id, texto, fontes, "
                "tokens_in, tokens_out, criado_em) VALUES (:a, :c, :d, :x, :t, CAST(:f AS jsonb), "
                ":ti, :to, COALESCE(:q, now())) ON CONFLICT DO NOTHING"
            ),
            {"a": aluno_id, "c": canal, "d": direcao, "x": externo_id, "t": texto,
             "f": json.dumps(fontes) if fontes is not None else None, "ti": tokens_in,
             "to": tokens_out, "q": quando},
        )  # fmt: skip
        return int(result.rowcount) > 0  # type: ignore[attr-defined]
