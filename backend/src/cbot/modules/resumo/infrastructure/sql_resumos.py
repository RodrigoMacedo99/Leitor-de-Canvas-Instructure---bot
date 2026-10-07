from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from cbot.modules.resumo.domain.ports import ResumoRegistro


class SqlResumoRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def salvar(self, aluno_id: UUID, ini: datetime, fim: datetime, texto: str) -> UUID:
        resultado = self._s.execute(
            text(
                "INSERT INTO resumos (aluno_id, periodo_ini, periodo_fim, texto) "
                "VALUES (:a, :i, :f, :t) RETURNING id"
            ),
            {"a": aluno_id, "i": ini, "f": fim, "t": texto},
        ).scalar_one()
        return cast(UUID, resultado)

    def marcar_enviado(self, aluno_id: UUID, resumo_id: UUID, canal: str, quando: datetime) -> None:
        self._s.execute(
            text("UPDATE resumos SET canal = :c, enviado_em = :q WHERE id = :i AND aluno_id = :a"),
            {"c": canal, "q": quando, "i": resumo_id, "a": aluno_id},
        )

    def ultimo_enviado_em(self, aluno_id: UUID) -> datetime | None:
        valor = self._s.execute(
            text("SELECT max(enviado_em) FROM resumos WHERE aluno_id = :a"), {"a": aluno_id}
        ).scalar_one()
        return cast(datetime | None, valor)

    def pendente_de_entrega(self, aluno_id: UUID) -> tuple[UUID, str] | None:
        row = self._s.execute(
            text(
                "SELECT id, texto FROM resumos WHERE aluno_id = :a AND enviado_em IS NULL "
                "AND canal IS NOT NULL ORDER BY criado_em DESC LIMIT 1"
            ),
            {"a": aluno_id},
        ).first()
        return (row[0], row[1]) if row else None

    def marcar_entregue(self, aluno_id: UUID, resumo_id: UUID, quando: datetime) -> None:
        self._s.execute(
            text("UPDATE resumos SET enviado_em = :q WHERE id = :i AND aluno_id = :a"),
            {"q": quando, "i": resumo_id, "a": aluno_id},
        )

    def salvar_pendente(
        self, aluno_id: UUID, ini: datetime, fim: datetime, texto: str, canal: str
    ) -> UUID:
        resumo_id = self.salvar(aluno_id, ini, fim, texto)
        self._s.execute(
            text("UPDATE resumos SET canal = :c WHERE id = :i AND aluno_id = :a"),
            {"c": canal, "i": resumo_id, "a": aluno_id},
        )
        return resumo_id

    def listar(
        self, aluno_id: UUID, limite: int, deslocamento: int
    ) -> tuple[list[ResumoRegistro], int]:
        total = self._s.execute(
            text("SELECT count(*) FROM resumos WHERE aluno_id = :a"), {"a": aluno_id}
        ).scalar_one()
        rows = self._s.execute(
            text(
                "SELECT id, periodo_ini, periodo_fim, texto, canal, enviado_em FROM resumos "
                "WHERE aluno_id = :a ORDER BY criado_em DESC LIMIT :l OFFSET :o"
            ),
            {"a": aluno_id, "l": limite, "o": deslocamento},
        ).all()
        return [ResumoRegistro(*r) for r in rows], int(total)
