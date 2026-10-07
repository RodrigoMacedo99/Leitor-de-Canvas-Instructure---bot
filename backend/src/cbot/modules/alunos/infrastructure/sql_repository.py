from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from cbot.modules.alunos.domain.entities import Aluno, IdentidadeCanal
from cbot.shared.vocab import Canal, EstadoAutorizacao

_ALUNO_COLS = (
    "id, email, senha_hash, nome, lms_url_base, token_lms_cifrado, lms_usuario_id, "
    "estado_autorizacao, canal_preferido, fuso_horario, hora_resumo, consentimento_em"
)
_IDENT_COLS = "id, aluno_id, canal, externo_id, verificado_em, ultima_mensagem_in_em"


def _aluno(row: RowMapping) -> Aluno:
    return Aluno(
        id=row["id"], email=row["email"], senha_hash=row["senha_hash"], nome=row["nome"],
        lms_url_base=row["lms_url_base"],
        token_lms_cifrado=bytes(row["token_lms_cifrado"]) if row["token_lms_cifrado"] else None,
        lms_usuario_id=row["lms_usuario_id"],
        estado_autorizacao=EstadoAutorizacao(row["estado_autorizacao"]),
        canal_preferido=Canal(row["canal_preferido"]), fuso_horario=row["fuso_horario"],
        hora_resumo=row["hora_resumo"], consentimento_em=row["consentimento_em"],
    )  # fmt: skip


def _identidade(row: RowMapping) -> IdentidadeCanal:
    return IdentidadeCanal(
        id=row["id"], aluno_id=row["aluno_id"], canal=Canal(row["canal"]),
        externo_id=row["externo_id"], verificado_em=row["verificado_em"],
        ultima_mensagem_in_em=row["ultima_mensagem_in_em"],
    )  # fmt: skip


class SqlAlunoRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def adicionar(self, aluno: Aluno) -> None:
        self._s.execute(
            text(
                f"INSERT INTO alunos ({_ALUNO_COLS}) VALUES (:id, :email, :senha_hash, :nome, "
                ":lms_url_base, :token_lms_cifrado, :lms_usuario_id, :estado, :canal, :fuso, "
                ":hora, :consentimento)"
            ),
            self._params(aluno),
        )

    def salvar(self, aluno: Aluno) -> None:
        self._s.execute(
            text(
                "UPDATE alunos SET nome = :nome, senha_hash = :senha_hash, lms_url_base = :lms_url_base, "
                "token_lms_cifrado = :token_lms_cifrado, lms_usuario_id = :lms_usuario_id, "
                "estado_autorizacao = :estado, canal_preferido = :canal, fuso_horario = :fuso, "
                "hora_resumo = :hora, consentimento_em = :consentimento, atualizado_em = now() "
                "WHERE id = :id"
            ),
            self._params(aluno),
        )

    @staticmethod
    def _params(a: Aluno) -> dict[str, Any]:
        return {
            "id": a.id, "email": a.email.lower(), "senha_hash": a.senha_hash, "nome": a.nome,
            "lms_url_base": a.lms_url_base, "token_lms_cifrado": a.token_lms_cifrado,
            "lms_usuario_id": a.lms_usuario_id, "estado": a.estado_autorizacao.value,
            "canal": a.canal_preferido.value, "fuso": a.fuso_horario, "hora": a.hora_resumo,
            "consentimento": a.consentimento_em,
        }  # fmt: skip

    def obter(self, aluno_id: UUID) -> Aluno | None:
        row = (
            self._s.execute(
                text(f"SELECT {_ALUNO_COLS} FROM alunos WHERE id = :id AND deletado_em IS NULL"),
                {"id": aluno_id},
            )
            .mappings()
            .first()
        )
        return _aluno(row) if row else None

    def obter_por_email(self, email: str) -> Aluno | None:
        row = (
            self._s.execute(
                text(
                    f"SELECT {_ALUNO_COLS} FROM alunos WHERE lower(email) = lower(:e) AND deletado_em IS NULL"
                ),
                {"e": email},
            )
            .mappings()
            .first()
        )
        return _aluno(row) if row else None

    def listar_sincronizaveis(self) -> list[Aluno]:
        rows = self._s.execute(
            text(
                f"SELECT {_ALUNO_COLS} FROM alunos WHERE deletado_em IS NULL "
                "AND estado_autorizacao = 'ativa' AND token_lms_cifrado IS NOT NULL"
            )
        ).mappings()
        return [_aluno(r) for r in rows]

    def excluir_definitivamente(self, aluno_id: UUID) -> None:
        self._s.execute(text("DELETE FROM alunos WHERE id = :id"), {"id": aluno_id})

    def criar_pareamento(
        self, aluno_id: UUID, canal: Canal, codigo_hash: str, expira_em: datetime
    ) -> None:
        self._s.execute(
            text(
                "DELETE FROM identidades_canal WHERE aluno_id = :a AND canal = :c AND verificado_em IS NULL"
            ),
            {"a": aluno_id, "c": canal.value},
        )
        self._s.execute(
            text(
                "INSERT INTO identidades_canal (aluno_id, canal, codigo_pareamento_hash, codigo_expira_em) "
                "VALUES (:a, :c, :h, :e)"
            ),
            {"a": aluno_id, "c": canal.value, "h": codigo_hash, "e": expira_em},
        )

    def vincular_por_codigo(
        self, canal: Canal, codigo_hash: str, externo_id: str, agora: datetime
    ) -> IdentidadeCanal | None:
        row = (
            self._s.execute(
                text(
                    "UPDATE identidades_canal SET externo_id = :x, verificado_em = :now, "
                    "codigo_pareamento_hash = NULL, codigo_expira_em = NULL, "
                    "ultima_mensagem_in_em = :now, atualizado_em = now() "
                    "WHERE canal = :c AND codigo_pareamento_hash = :h AND verificado_em IS NULL "
                    f"AND codigo_expira_em > :now RETURNING {_IDENT_COLS}"
                ),
                {"x": externo_id, "now": agora, "c": canal.value, "h": codigo_hash},
            )
            .mappings()
            .first()
        )
        return _identidade(row) if row else None

    def obter_identidade(self, canal: Canal, externo_id: str) -> IdentidadeCanal | None:
        row = (
            self._s.execute(
                text(
                    f"SELECT {_IDENT_COLS} FROM identidades_canal "
                    "WHERE canal = :c AND externo_id = :x AND verificado_em IS NOT NULL"
                ),
                {"c": canal.value, "x": externo_id},
            )
            .mappings()
            .first()
        )
        return _identidade(row) if row else None

    def identidade_do_aluno(self, aluno_id: UUID, canal: Canal) -> IdentidadeCanal | None:
        row = (
            self._s.execute(
                text(
                    f"SELECT {_IDENT_COLS} FROM identidades_canal "
                    "WHERE aluno_id = :a AND canal = :c AND verificado_em IS NOT NULL"
                ),
                {"a": aluno_id, "c": canal.value},
            )
            .mappings()
            .first()
        )
        return _identidade(row) if row else None

    def listar_identidades(self, aluno_id: UUID) -> list[IdentidadeCanal]:
        rows = self._s.execute(
            text(
                f"SELECT {_IDENT_COLS} FROM identidades_canal WHERE aluno_id = :a ORDER BY criado_em"
            ),
            {"a": aluno_id},
        ).mappings()
        return [_identidade(r) for r in rows]

    def remover_identidade(self, aluno_id: UUID, identidade_id: UUID) -> bool:
        result = self._s.execute(
            text("DELETE FROM identidades_canal WHERE id = :i AND aluno_id = :a"),
            {"i": identidade_id, "a": aluno_id},
        )
        return result.rowcount > 0  # type: ignore[attr-defined,no-any-return]

    def registrar_mensagem_recebida(self, identidade_id: UUID, agora: datetime) -> None:
        self._s.execute(
            text(
                "UPDATE identidades_canal SET ultima_mensagem_in_em = :n, atualizado_em = now() WHERE id = :i"
            ),
            {"n": agora, "i": identidade_id},
        )
