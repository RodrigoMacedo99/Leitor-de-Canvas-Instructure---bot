"""Adaptador Canvas -> porta `LmsConnector`.

Cada tipo de conteúdo é um *Collector* (padrão Strategy); o conector só os orquestra.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cbot.modules.canvas.domain.ports import (
    ArquivoLms,
    ColetaCurso,
    Conhecidos,
    CursoLms,
    ItemLms,
    PerfilLms,
)
from cbot.modules.canvas.infrastructure.client import CanvasHttpClient, LmsForbidden
from cbot.shared.text import html_to_text
from cbot.shared.vocab import TipoItem

logger = logging.getLogger(__name__)
ANNOUNCEMENTS_SINCE = "2000-01-01"
DEFAULT_MIME = "application/octet-stream"


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


@dataclass(frozen=True, slots=True)
class CollectContext:
    client: CanvasHttpClient
    base_url: str
    curso_id: int
    conhecidos: Conhecidos
    secoes: dict[str, str]

    def web_url(self, path: str) -> str:
        return f"{self.base_url}/courses/{self.curso_id}{path}"


class Collector(ABC):
    """Strategy: coleta um tipo de item de um curso."""

    tipo: TipoItem

    @abstractmethod
    def coletar(self, ctx: CollectContext) -> Iterator[ItemLms]: ...

    def safe(self, ctx: CollectContext) -> list[ItemLms] | None:
        """Itens do tipo, ou None se o aluno não tem acesso (coleta incompleta)."""
        try:
            return list(self.coletar(ctx))
        except LmsForbidden:
            logger.info("sem acesso a %s no curso %s", type(self).__name__, ctx.curso_id)
            return None


class ProgramaCollector(Collector):
    tipo = TipoItem.PROGRAMA

    def coletar(self, ctx: CollectContext) -> Iterator[ItemLms]:
        data = ctx.client.get_json(f"/courses/{ctx.curso_id}", {"include[]": "syllabus_body"})
        texto = html_to_text(data.get("syllabus_body"))
        if texto:
            yield ItemLms(
                tipo=TipoItem.PROGRAMA,
                externo_id="syllabus",
                titulo="Programa da disciplina",
                secao=None,
                url=ctx.web_url("/assignments/syllabus"),
                prazo_em=None,
                modificado_em=None,
                texto=texto,
            )


class ArquivosCollector(Collector):
    tipo = TipoItem.ARQUIVO

    def coletar(self, ctx: CollectContext) -> Iterator[ItemLms]:
        for f in ctx.client.paginate(f"/courses/{ctx.curso_id}/files"):
            if f.get("locked_for_user") or f.get("hidden_for_user"):
                continue
            arquivo = ArquivoLms(
                lms_id=f["id"],
                nome=f.get("display_name") or f["filename"],
                mime=f.get("content-type") or DEFAULT_MIME,
                tamanho=int(f.get("size") or 0),
                url_download=f["url"],
            )
            yield ItemLms(
                tipo=TipoItem.ARQUIVO,
                externo_id=f"file:{f['id']}",
                titulo=arquivo.nome,
                secao=ctx.secoes.get(f"file:{f['id']}"),
                url=ctx.web_url(f"/files/{f['id']}"),
                prazo_em=None,
                modificado_em=parse_dt(f.get("modified_at") or f.get("updated_at")),
                arquivo=arquivo,
            )


class PaginasCollector(Collector):
    tipo = TipoItem.PAGINA

    def coletar(self, ctx: CollectContext) -> Iterator[ItemLms]:
        for page in ctx.client.paginate(f"/courses/{ctx.curso_id}/pages"):
            slug, externo_id = page["url"], f"page:{page['url']}"
            modificado = parse_dt(page.get("updated_at"))
            texto = None
            if ctx.conhecidos.get(externo_id) != modificado:
                body = ctx.client.get_json(f"/courses/{ctx.curso_id}/pages/{slug}")
                texto = html_to_text(body.get("body"))
            yield ItemLms(
                tipo=TipoItem.PAGINA,
                externo_id=externo_id,
                titulo=page["title"],
                secao=ctx.secoes.get(externo_id),
                url=page.get("html_url"),
                prazo_em=None,
                modificado_em=modificado,
                texto=texto,
            )


class TarefasCollector(Collector):
    tipo = TipoItem.TAREFA

    def coletar(self, ctx: CollectContext) -> Iterator[ItemLms]:
        for a in ctx.client.paginate(f"/courses/{ctx.curso_id}/assignments"):
            externo_id = f"assignment:{a['id']}"
            yield ItemLms(
                tipo=TipoItem.TAREFA,
                externo_id=externo_id,
                titulo=a["name"],
                secao=ctx.secoes.get(externo_id),
                url=a.get("html_url"),
                prazo_em=parse_dt(a.get("due_at")),
                modificado_em=parse_dt(a.get("updated_at")),
                texto=html_to_text(a.get("description")),
            )


class QuizzesCollector(Collector):
    tipo = TipoItem.QUIZ

    def coletar(self, ctx: CollectContext) -> Iterator[ItemLms]:
        for q in ctx.client.paginate(f"/courses/{ctx.curso_id}/quizzes"):
            externo_id = f"quiz:{q['id']}"
            yield ItemLms(
                tipo=TipoItem.QUIZ,
                externo_id=externo_id,
                titulo=q["title"],
                secao=ctx.secoes.get(externo_id),
                url=q.get("html_url"),
                prazo_em=parse_dt(q.get("due_at")),
                modificado_em=None,
                texto=html_to_text(q.get("description")),
            )


class AvisosCollector(Collector):
    tipo = TipoItem.AVISO

    def coletar(self, ctx: CollectContext) -> Iterator[ItemLms]:
        end = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
        params = {
            "context_codes[]": f"course_{ctx.curso_id}",
            "start_date": ANNOUNCEMENTS_SINCE,
            "end_date": end,
        }
        for n in ctx.client.paginate("/announcements", params):
            yield ItemLms(
                tipo=TipoItem.AVISO,
                externo_id=f"announcement:{n['id']}",
                titulo=n["title"],
                secao=None,
                url=n.get("html_url"),
                prazo_em=None,
                modificado_em=parse_dt(n.get("posted_at") or n.get("created_at")),
                texto=html_to_text(n.get("message")),
            )


DEFAULT_COLLECTORS: tuple[Collector, ...] = (
    ProgramaCollector(), ArquivosCollector(), PaginasCollector(),
    TarefasCollector(), QuizzesCollector(), AvisosCollector(),
)  # fmt: skip

_MODULE_ITEM_KEYS = {
    "File": lambda i: f"file:{i.get('content_id')}",
    "Page": lambda i: f"page:{i.get('page_url')}",
    "Assignment": lambda i: f"assignment:{i.get('content_id')}",
    "Quiz": lambda i: f"quiz:{i.get('content_id')}",
}


class CanvasConnector:
    """Implementa `LmsConnector` sobre `CanvasHttpClient`."""

    def __init__(
        self,
        client: CanvasHttpClient,
        base_url: str,
        collectors: tuple[Collector, ...] = DEFAULT_COLLECTORS,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._collectors = collectors

    def validar_token(self) -> PerfilLms:
        perfil = self._client.get_json("/users/self")
        return PerfilLms(usuario_id=int(perfil["id"]), nome=perfil.get("name", ""))

    def listar_cursos(self) -> list[CursoLms]:
        params = {"enrollment_state": "active", "include[]": "term"}
        cursos = []
        for c in self._client.paginate("/courses", params):
            if c.get("access_restricted_by_date") or "name" not in c:
                continue
            cursos.append(
                CursoLms(
                    lms_id=c["id"], nome=c["name"], codigo=c.get("course_code"),
                    inicio_em=parse_dt(c.get("start_at")), fim_em=parse_dt(c.get("end_at")),
                )
            )  # fmt: skip
        return cursos

    def listar_itens(self, curso_lms_id: int, conhecidos: Conhecidos) -> ColetaCurso:
        ctx = CollectContext(
            client=self._client, base_url=self._base_url, curso_id=curso_lms_id,
            conhecidos=conhecidos, secoes=self._mapa_secoes(curso_lms_id),
        )  # fmt: skip
        itens: list[ItemLms] = []
        coletados: set[TipoItem] = set()
        for collector in self._collectors:
            resultado = collector.safe(ctx)
            if resultado is not None:
                itens.extend(resultado)
                coletados.add(collector.tipo)
        return ColetaCurso(itens=itens, tipos_coletados=frozenset(coletados))

    def _mapa_secoes(self, curso_lms_id: int) -> dict[str, str]:
        secoes: dict[str, str] = {}
        try:
            modulos: Any = self._client.paginate(
                f"/courses/{curso_lms_id}/modules", {"include[]": "items"}
            )
            for modulo in modulos:
                for item in modulo.get("items") or []:
                    key_fn = _MODULE_ITEM_KEYS.get(item.get("type", ""))
                    if key_fn:
                        secoes[key_fn(item)] = modulo["name"]
        except LmsForbidden:
            logger.info("módulos indisponíveis no curso %s", curso_lms_id)
        return secoes

    def baixar_arquivo(self, arquivo: ArquivoLms) -> AbstractContextManager[Iterator[bytes]]:
        return self._client.stream(arquivo.url_download)
