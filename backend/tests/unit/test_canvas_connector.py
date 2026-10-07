from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from cbot.modules.canvas.infrastructure.client import LmsForbidden
from cbot.modules.canvas.infrastructure.connector import CanvasConnector, parse_dt
from cbot.shared.vocab import TipoItem

BASE = "https://escola.instructure.com"


class FakeClient:
    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append(path)
        value = self.routes[path]
        if isinstance(value, Exception):
            raise value
        return value

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        self.calls.append(path)
        value = self.routes.get(path, [])
        if isinstance(value, Exception):
            raise value
        yield from value

    def stream(self, url: str) -> str:
        return f"stream:{url}"


def make(routes: dict[str, Any]) -> tuple[CanvasConnector, FakeClient]:
    client = FakeClient(routes)
    return CanvasConnector(client, BASE), client  # type: ignore[arg-type]


def test_validar_token_returns_profile() -> None:
    connector, _ = make({"/users/self": {"id": 7, "name": "Ana"}})
    perfil = connector.validar_token()
    assert (perfil.usuario_id, perfil.nome) == (7, "Ana")


def test_listar_cursos_skips_restricted_and_unnamed() -> None:
    connector, _ = make(
        {
            "/courses": [
                {
                    "id": 1,
                    "name": "Redes",
                    "course_code": "RED1",
                    "start_at": "2026-02-01T00:00:00Z",
                },
                {"id": 2, "access_restricted_by_date": True},
                {"id": 3},
            ]
        }
    )
    cursos = connector.listar_cursos()
    assert [(c.lms_id, c.nome, c.codigo) for c in cursos] == [(1, "Redes", "RED1")]
    assert cursos[0].inicio_em == datetime(2026, 2, 1, tzinfo=UTC)


def routes_for_course() -> dict[str, Any]:
    return {
        "/courses/1": {"syllabus_body": "<p>Ementa de <b>Redes</b></p>"},
        "/courses/1/modules": [
            {
                "name": "Unidade 1",
                "items": [
                    {"type": "File", "content_id": 10},
                    {"type": "Page", "page_url": "intro"},
                    {"type": "Assignment", "content_id": 5},
                    {"type": "SubHeader"},
                ],
            }
        ],
        "/courses/1/files": [
            {
                "id": 10,
                "display_name": "aula1.pdf",
                "filename": "aula1.pdf",
                "size": 99,
                "content-type": "application/pdf",
                "url": "https://f/10",
                "updated_at": "2026-03-01T10:00:00Z",
            },
            {
                "id": 11,
                "display_name": "x",
                "filename": "x",
                "url": "https://f/11",
                "locked_for_user": True,
            },
        ],
        "/courses/1/pages": [
            {
                "url": "intro",
                "title": "Intro",
                "updated_at": "2026-03-02T10:00:00Z",
                "html_url": f"{BASE}/courses/1/pages/intro",
            }
        ],
        "/courses/1/pages/intro": {"body": "<h1>Bem-vindo</h1>"},
        "/courses/1/assignments": [
            {
                "id": 5,
                "name": "Lista 1",
                "due_at": "2026-04-01T02:59:00Z",
                "updated_at": "2026-03-03T10:00:00Z",
                "description": "<p>Resolva</p>",
            }
        ],
        "/courses/1/quizzes": [{"id": 6, "title": "Quiz 1", "due_at": None, "description": None}],
        "/announcements": [
            {
                "id": 9,
                "title": "Aviso",
                "message": "<p>Prova dia 10</p>",
                "posted_at": "2026-03-04T10:00:00Z",
            }
        ],
    }


def test_listar_itens_collects_every_type_with_sections() -> None:
    connector, _ = make(routes_for_course())
    coleta = connector.listar_itens(1, {})
    itens = {i.externo_id: i for i in coleta.itens}
    assert set(coleta.tipos_coletados) == set(TipoItem)
    assert set(itens) == {
        "syllabus",
        "file:10",
        "page:intro",
        "assignment:5",
        "quiz:6",
        "announcement:9",
    }
    assert (
        itens["file:10"].tipo is TipoItem.ARQUIVO
        and itens["file:10"].arquivo.url_download == "https://f/10"
    )
    assert itens["file:10"].secao == "Unidade 1"
    assert itens["page:intro"].texto == "Bem-vindo"
    assert itens["assignment:5"].prazo_em == datetime(2026, 4, 1, 2, 59, tzinfo=UTC)
    assert itens["syllabus"].texto == "Ementa de\nRedes"


def test_unchanged_page_body_is_not_refetched() -> None:
    connector, client = make(routes_for_course())
    conhecidos = {"page:intro": parse_dt("2026-03-02T10:00:00Z")}
    itens = {i.externo_id: i for i in connector.listar_itens(1, conhecidos).itens}
    assert itens["page:intro"].texto is None
    assert "/courses/1/pages/intro" not in client.calls


def test_forbidden_collector_is_skipped_not_fatal() -> None:
    routes = routes_for_course()
    routes["/courses/1/files"] = LmsForbidden("sem aba de arquivos")
    routes["/courses/1/modules"] = LmsForbidden("sem módulos")
    connector, _ = make(routes)
    coleta = connector.listar_itens(1, {})
    ids = {i.externo_id for i in coleta.itens}
    assert "file:10" not in ids and "assignment:5" in ids
    assert TipoItem.ARQUIVO not in coleta.tipos_coletados


def test_baixar_arquivo_delegates_to_client_stream() -> None:
    connector, _ = make({})
    arquivo = next(
        i for i in make(routes_for_course())[0].listar_itens(1, {}).itens if i.arquivo
    ).arquivo
    assert connector.baixar_arquivo(arquivo) == f"stream:{arquivo.url_download}"
