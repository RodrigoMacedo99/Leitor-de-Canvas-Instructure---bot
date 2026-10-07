import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from cbot.modules.canvas.public import CursoLms
from cbot.modules.conteudo.domain.entities import (
    ArquivoRegistro,
    Curso,
    EventoDetalhado,
    EventoMudanca,
    ItemCurso,
    PrazoDetalhado,
)
from cbot.shared.vocab import TipoEvento, TipoItem

_CURSO_COLS = "id, aluno_id, lms_curso_id, nome, codigo, inicio_em, fim_em, ativa, ultimo_sync_em"
_ITEM_COLS = (
    "id, aluno_id, curso_id, tipo, externo_id, secao, titulo, url, prazo_em, "
    "modificado_lms_em, hash_conteudo, conteudo_texto, status"
)
_ARQ_COLS = (
    "id, aluno_id, item_id, nome, mime, tamanho, sha256, versao, texto_extraido_em, erro_extracao"
)
_EVENTO_SELECT = """
    SELECT e.id, e.tipo, e.detalhe, e.detectado_em, i.id AS item_id, i.tipo AS item_tipo,
           i.titulo, i.secao, i.url, i.prazo_em, c.id AS curso_id, c.nome AS curso_nome
    FROM eventos_mudanca e
    JOIN itens_curso i ON i.id = e.item_id AND i.aluno_id = e.aluno_id
    JOIN cursos c ON c.id = i.curso_id AND c.aluno_id = e.aluno_id
"""


def _curso(r: RowMapping) -> Curso:
    return Curso(**{k: r[k] for k in _CURSO_COLS.split(", ")})


def _item(r: RowMapping) -> ItemCurso:
    data = {k: r[k] for k in _ITEM_COLS.split(", ")}
    data["tipo"] = TipoItem(data["tipo"])
    data["modificado_lms_em"] = data["modificado_lms_em"]
    return ItemCurso(**data)


def _arquivo(r: RowMapping) -> ArquivoRegistro:
    return ArquivoRegistro(**{k: r[k] for k in _ARQ_COLS.split(", ")})


def _evento(r: RowMapping) -> EventoDetalhado:
    return EventoDetalhado(
        id=r["id"], tipo=TipoEvento(r["tipo"]), detalhe=r["detalhe"], detectado_em=r["detectado_em"],
        item_id=r["item_id"], item_tipo=TipoItem(r["item_tipo"]), titulo=r["titulo"],
        secao=r["secao"], url=r["url"], prazo_em=r["prazo_em"], curso_id=r["curso_id"],
        curso_nome=r["curso_nome"],
    )  # fmt: skip


class SqlConteudoRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # --- cursos -------------------------------------------------------------------
    def upsert_curso(self, aluno_id: UUID, curso: CursoLms) -> Curso:
        row = self._s.execute(
            text(
                "INSERT INTO cursos (aluno_id, lms_curso_id, nome, codigo, inicio_em, fim_em) "
                "VALUES (:a, :l, :n, :c, :i, :f) "
                "ON CONFLICT (aluno_id, lms_curso_id) DO UPDATE SET nome = EXCLUDED.nome, "
                "codigo = EXCLUDED.codigo, inicio_em = EXCLUDED.inicio_em, fim_em = EXCLUDED.fim_em, "
                "ativa = TRUE, deletado_em = NULL, atualizado_em = now() "
                f"RETURNING {_CURSO_COLS}"
            ),
            {"a": aluno_id, "l": curso.lms_id, "n": curso.nome, "c": curso.codigo,
             "i": curso.inicio_em, "f": curso.fim_em},
        ).mappings().one()  # fmt: skip
        return _curso(row)

    def desativar_cursos_ausentes(self, aluno_id: UUID, lms_ids_ativos: Sequence[int]) -> int:
        result = self._s.execute(
            text(
                "UPDATE cursos SET ativa = FALSE, atualizado_em = now() "
                "WHERE aluno_id = :a AND ativa AND NOT (lms_curso_id = ANY(:ids))"
            ),
            {"a": aluno_id, "ids": list(lms_ids_ativos)},
        )
        return int(result.rowcount)  # type: ignore[attr-defined]

    def marcar_curso_sincronizado(self, aluno_id: UUID, curso_id: UUID, quando: datetime) -> None:
        self._s.execute(
            text("UPDATE cursos SET ultimo_sync_em = :q WHERE id = :c AND aluno_id = :a"),
            {"q": quando, "c": curso_id, "a": aluno_id},
        )

    def listar_cursos(self, aluno_id: UUID, *, somente_ativos: bool = True) -> list[Curso]:
        filtro = "AND ativa" if somente_ativos else ""
        rows = self._s.execute(
            text(f"SELECT {_CURSO_COLS} FROM cursos WHERE aluno_id = :a {filtro} ORDER BY nome"),
            {"a": aluno_id},
        ).mappings()
        return [_curso(r) for r in rows]

    def obter_curso(self, aluno_id: UUID, curso_id: UUID) -> Curso | None:
        row = (
            self._s.execute(
                text(f"SELECT {_CURSO_COLS} FROM cursos WHERE id = :c AND aluno_id = :a"),
                {"c": curso_id, "a": aluno_id},
            )
            .mappings()
            .first()
        )
        return _curso(row) if row else None

    # --- itens --------------------------------------------------------------------
    def itens_por_externo(self, aluno_id: UUID, curso_id: UUID) -> dict[str, ItemCurso]:
        rows = self._s.execute(
            text(f"SELECT {_ITEM_COLS} FROM itens_curso WHERE aluno_id = :a AND curso_id = :c"),
            {"a": aluno_id, "c": curso_id},
        ).mappings()
        return {r["externo_id"]: _item(r) for r in rows}

    def listar_itens(
        self, aluno_id: UUID, curso_id: UUID, *, tipo: TipoItem | None, desde: datetime | None,
        limite: int, deslocamento: int,
    ) -> tuple[list[ItemCurso], int]:  # fmt: skip
        where = "aluno_id = :a AND curso_id = :c AND status = 'ativo'"
        params: dict[str, Any] = {"a": aluno_id, "c": curso_id, "lim": limite, "off": deslocamento}
        if tipo:
            where += " AND tipo = :t"
            params["t"] = tipo.value
        if desde:
            where += " AND atualizado_em >= :d"
            params["d"] = desde
        total = self._s.execute(
            text(f"SELECT count(*) FROM itens_curso WHERE {where}"), params
        ).scalar_one()
        rows = self._s.execute(
            text(
                f"SELECT {_ITEM_COLS} FROM itens_curso WHERE {where} "
                "ORDER BY secao NULLS LAST, titulo LIMIT :lim OFFSET :off"
            ),
            params,
        ).mappings()
        return [_item(r) for r in rows], int(total)

    def obter_item(self, aluno_id: UUID, item_id: UUID) -> ItemCurso | None:
        row = (
            self._s.execute(
                text(f"SELECT {_ITEM_COLS} FROM itens_curso WHERE id = :i AND aluno_id = :a"),
                {"i": item_id, "a": aluno_id},
            )
            .mappings()
            .first()
        )
        return _item(row) if row else None

    def inserir_item(self, item: ItemCurso) -> None:
        self._s.execute(
            text(
                f"INSERT INTO itens_curso ({_ITEM_COLS}) VALUES (:id, :aluno_id, :curso_id, :tipo, "
                ":externo_id, :secao, :titulo, :url, :prazo_em, :modificado_lms_em, :hash_conteudo, "
                ":conteudo_texto, :status) "
                "ON CONFLICT (curso_id, externo_id) DO UPDATE SET status = 'ativo', titulo = EXCLUDED.titulo, "
                "secao = EXCLUDED.secao, url = EXCLUDED.url, prazo_em = EXCLUDED.prazo_em, "
                "modificado_lms_em = EXCLUDED.modificado_lms_em, hash_conteudo = EXCLUDED.hash_conteudo, "
                "conteudo_texto = EXCLUDED.conteudo_texto, atualizado_em = now()"
            ),
            self._item_params(item),
        )

    def atualizar_item(self, item: ItemCurso) -> None:
        self._s.execute(
            text(
                "UPDATE itens_curso SET secao = :secao, titulo = :titulo, url = :url, prazo_em = :prazo_em, "
                "modificado_lms_em = :modificado_lms_em, hash_conteudo = :hash_conteudo, "
                "conteudo_texto = COALESCE(:conteudo_texto, conteudo_texto), status = :status, "
                "atualizado_em = now() WHERE id = :id AND aluno_id = :aluno_id"
            ),
            self._item_params(item),
        )

    @staticmethod
    def _item_params(i: ItemCurso) -> dict[str, Any]:
        return {
            "id": i.id, "aluno_id": i.aluno_id, "curso_id": i.curso_id, "tipo": i.tipo.value,
            "externo_id": i.externo_id, "secao": i.secao, "titulo": i.titulo, "url": i.url,
            "prazo_em": i.prazo_em, "modificado_lms_em": i.modificado_lms_em,
            "hash_conteudo": i.hash_conteudo, "conteudo_texto": i.conteudo_texto, "status": i.status,
        }  # fmt: skip

    def marcar_item_removido(self, aluno_id: UUID, item_id: UUID) -> None:
        self._s.execute(
            text(
                "UPDATE itens_curso SET status = 'removido', atualizado_em = now() WHERE id = :i AND aluno_id = :a"
            ),
            {"i": item_id, "a": aluno_id},
        )

    # --- arquivos -----------------------------------------------------------------
    def ultimo_arquivo(self, aluno_id: UUID, item_id: UUID) -> ArquivoRegistro | None:
        row = (
            self._s.execute(
                text(
                    f"SELECT {_ARQ_COLS} FROM arquivos WHERE aluno_id = :a AND item_id = :i ORDER BY versao DESC LIMIT 1"
                ),
                {"a": aluno_id, "i": item_id},
            )
            .mappings()
            .first()
        )
        return _arquivo(row) if row else None

    def obter_arquivo(self, aluno_id: UUID, arquivo_id: UUID) -> ArquivoRegistro | None:
        row = (
            self._s.execute(
                text(f"SELECT {_ARQ_COLS} FROM arquivos WHERE id = :f AND aluno_id = :a"),
                {"f": arquivo_id, "a": aluno_id},
            )
            .mappings()
            .first()
        )
        return _arquivo(row) if row else None

    def inserir_arquivo(self, arquivo: ArquivoRegistro) -> None:
        self._s.execute(
            text(
                f"INSERT INTO arquivos ({_ARQ_COLS}) VALUES (:id, :aluno_id, :item_id, :nome, :mime, "
                ":tamanho, :sha256, :versao, :texto_extraido_em, :erro_extracao)"
            ),
            {c: getattr(arquivo, c) for c in _ARQ_COLS.split(", ")},
        )

    def registrar_extracao(
        self, aluno_id: UUID, arquivo_id: UUID, quando: datetime, erro: str | None
    ) -> None:
        self._s.execute(
            text(
                "UPDATE arquivos SET texto_extraido_em = :q, erro_extracao = :e, atualizado_em = now() "
                "WHERE id = :f AND aluno_id = :a"
            ),
            {"q": quando, "e": erro, "f": arquivo_id, "a": aluno_id},
        )

    # --- eventos ------------------------------------------------------------------
    def inserir_evento(self, evento: EventoMudanca) -> None:
        self._s.execute(
            text(
                "INSERT INTO eventos_mudanca (id, aluno_id, item_id, execucao_id, tipo, detalhe) "
                "VALUES (:id, :a, :i, :x, :t, CAST(:d AS jsonb))"
            ),
            {"id": evento.id, "a": evento.aluno_id, "i": evento.item_id, "x": evento.execucao_id,
             "t": evento.tipo.value, "d": json.dumps(evento.detalhe)},
        )  # fmt: skip

    def eventos_pendentes(self, aluno_id: UUID) -> list[EventoDetalhado]:
        rows = self._s.execute(
            text(
                _EVENTO_SELECT
                + " WHERE e.aluno_id = :a AND e.notificado_em IS NULL ORDER BY c.nome, e.detectado_em"
            ),
            {"a": aluno_id},
        ).mappings()
        return [_evento(r) for r in rows]

    def eventos_do_curso(
        self, aluno_id: UUID, curso_id: UUID, desde: datetime | None
    ) -> list[EventoDetalhado]:
        rows = self._s.execute(
            text(
                _EVENTO_SELECT
                + " WHERE e.aluno_id = :a AND c.id = :c AND (CAST(:d AS timestamptz) IS NULL "
                "OR e.detectado_em >= :d) ORDER BY e.detectado_em DESC LIMIT 200"
            ),
            {"a": aluno_id, "c": curso_id, "d": desde},
        ).mappings()
        return [_evento(r) for r in rows]

    def marcar_eventos_notificados(
        self, aluno_id: UUID, ids: Sequence[UUID], quando: datetime
    ) -> None:
        if not ids:
            return
        self._s.execute(
            text(
                "UPDATE eventos_mudanca SET notificado_em = :q WHERE aluno_id = :a AND id = ANY(:ids)"
            ),
            {"q": quando, "a": aluno_id, "ids": list(ids)},
        )

    def prazos(self, aluno_id: UUID, de: datetime, ate: datetime) -> list[PrazoDetalhado]:
        rows = self._s.execute(
            text(
                "SELECT i.id, i.titulo, i.tipo, i.prazo_em, i.url, c.id AS curso_id, c.nome AS curso_nome "
                "FROM itens_curso i JOIN cursos c ON c.id = i.curso_id AND c.aluno_id = i.aluno_id "
                "WHERE i.aluno_id = :a AND i.status = 'ativo' AND c.ativa "
                "AND i.prazo_em BETWEEN :de AND :ate ORDER BY i.prazo_em"
            ),
            {"a": aluno_id, "de": de, "ate": ate},
        ).mappings()
        return [
            PrazoDetalhado(
                item_id=r["id"], titulo=r["titulo"], tipo=TipoItem(r["tipo"]), prazo_em=r["prazo_em"],
                url=r["url"], curso_id=r["curso_id"], curso_nome=r["curso_nome"],
            )
            for r in rows
        ]  # fmt: skip
