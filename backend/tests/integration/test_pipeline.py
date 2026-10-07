"""Pipeline completo contra PostgreSQL real: sincronizar -> baixar -> indexar -> buscar."""

import base64
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import text

from cbot.config import Settings
from cbot.container import Container, build_container
from cbot.modules.rag.infrastructure.embedders import HashingEmbedder
from cbot.shared.events import ItemSincronizado
from cbot.shared.vocab import Gatilho, StatusExecucao
from tests.fakes import FakeLms, ScriptedLlm, item_arquivo, item_texto

pytestmark = pytest.mark.integration

APOSTILA = (
    "O protocolo TCP é orientado a conexão e garante entrega ordenada dos segmentos.\n\n"
    "O protocolo UDP não estabelece conexão e não garante entrega, mas tem baixa latência."
).encode()


@pytest.fixture
def lms() -> FakeLms:
    return FakeLms()


@pytest.fixture
def app(db, lms: FakeLms, tmp_path) -> Container:  # type: ignore[no-untyped-def]
    settings = Settings(
        DATABASE_URL="postgresql://x:x@localhost/x",
        JWT_SECRET="s" * 40,
        TOKEN_ENCRYPTION_KEY=base64.b64encode(b"k" * 32).decode(),
        STORAGE_DIR=tmp_path,
        EMBEDDING_PROVIDER="hashing",
    )  # type: ignore[call-arg]
    return build_container(
        settings, db=db, connector_factory=lms.factory, llm=ScriptedLlm(), embedder=HashingEmbedder(1024),
        canais={},
    )  # fmt: skip


@pytest.fixture
def aluno_id(app: Container) -> UUID:
    aluno = app.alunos.registrar("ana@exemplo.com", "senha-bem-longa", "Ana Souza")
    app.alunos.conectar_canvas(
        aluno.id, "https://escola.instructure.com", "token-do-canvas", consentimento=True
    )
    return aluno.id


def contar(app: Container, tabela: str, aluno_id: UUID) -> int:
    with app.db.session() as s:
        return int(
            s.execute(
                text(f"SELECT count(*) FROM {tabela} WHERE aluno_id = :a"), {"a": aluno_id}
            ).scalar_one()
        )  # noqa: S608


def test_first_sync_downloads_indexes_and_records_events(
    app: Container, lms: FakeLms, aluno_id: UUID
) -> None:
    lms.itens[1] = [
        item_arquivo(10, "apostila.txt", len(APOSTILA)),
        item_texto("page:intro", "Introdução", "Bem-vindo à disciplina de redes."),
    ]
    lms.arquivos[10] = APOSTILA

    execucao = app.sincronizar.executar(aluno_id, Gatilho.MANUAL)

    assert execucao.status is StatusExecucao.SUCESSO
    assert execucao.estatisticas["novos"] == 2 and execucao.estatisticas["arquivos_baixados"] == 1
    assert contar(app, "itens_curso", aluno_id) == 2
    assert contar(app, "trechos", aluno_id) >= 2
    assert contar(app, "eventos_mudanca", aluno_id) == 2
    with app.db.session() as s:
        row = s.execute(
            text("SELECT texto_extraido_em, erro_extracao FROM arquivos WHERE aluno_id = :a"),
            {"a": aluno_id},
        ).one()
    assert row.texto_extraido_em is not None and row.erro_extracao is None


def test_second_sync_without_changes_does_nothing(
    app: Container, lms: FakeLms, aluno_id: UUID
) -> None:
    lms.itens[1] = [item_arquivo(10, "apostila.txt", len(APOSTILA))]
    lms.arquivos[10] = APOSTILA
    app.sincronizar.executar(aluno_id)

    segunda = app.sincronizar.executar(aluno_id)

    assert segunda.estatisticas["novos"] == 0 and segunda.estatisticas["alterados"] == 0
    assert segunda.estatisticas["inalterados"] == 1
    assert lms.downloads == 1
    assert contar(app, "eventos_mudanca", aluno_id) == 1


def test_changed_deadline_creates_event_with_old_and_new_values(
    app: Container, lms: FakeLms, aluno_id: UUID
) -> None:
    prazo = datetime(2026, 4, 1, 12, tzinfo=UTC)
    lms.itens[1] = [item_texto("assignment:5", "Lista 1", "Resolva", prazo_em=prazo)]
    app.sincronizar.executar(aluno_id)
    lms.itens[1] = [
        item_texto(
            "assignment:5",
            "Lista 1",
            "Resolva",
            prazo_em=prazo + timedelta(days=7),
            modificado_em=prazo,
        )
    ]

    app.sincronizar.executar(aluno_id)

    with app.db.session() as s:
        detalhe = s.execute(
            text("SELECT detalhe FROM eventos_mudanca WHERE tipo = 'alterado'")
        ).scalar_one()
    assert detalhe["prazo"]["para"].startswith("2026-04-08")


def test_removed_item_leaves_the_index(app: Container, lms: FakeLms, aluno_id: UUID) -> None:
    lms.itens[1] = [item_texto("page:a", "Página A", "Conteúdo sobre roteamento IP.")]
    app.sincronizar.executar(aluno_id)
    assert contar(app, "trechos", aluno_id) >= 1

    lms.itens[1] = []
    execucao = app.sincronizar.executar(aluno_id)

    assert execucao.estatisticas["removidos"] == 1
    assert contar(app, "trechos", aluno_id) == 0


def test_incomplete_collection_does_not_fake_removals(
    app: Container, lms: FakeLms, aluno_id: UUID
) -> None:
    lms.itens[1] = [item_arquivo(10, "apostila.txt", len(APOSTILA))]
    lms.arquivos[10] = APOSTILA
    app.sincronizar.executar(aluno_id)

    lms.itens[1], lms.tipos_coletados = [], frozenset()  # aba de Arquivos ficou inacessível
    execucao = app.sincronizar.executar(aluno_id)

    assert execucao.estatisticas["removidos"] == 0


def test_hybrid_search_finds_relevant_chunk_and_isolates_students(
    app: Container, lms: FakeLms, aluno_id: UUID
) -> None:
    lms.itens[1] = [item_arquivo(10, "apostila.txt", len(APOSTILA))]
    lms.arquivos[10] = APOSTILA
    app.sincronizar.executar(aluno_id)
    outro = app.alunos.registrar("bia@exemplo.com", "outra-senha-longa", "Bia")

    meu = app.busca.buscar(aluno_id, "O que é o protocolo UDP?")
    dele = app.busca.buscar(outro.id, "O que é o protocolo UDP?")

    assert "UDP" in meu.candidatos[0].texto
    assert meu.candidatos[0].metadados["arquivo"] == "apostila.txt"
    assert dele.vazio


def test_revoked_token_marks_reauthorization_and_publishes_event(
    app: Container, lms: FakeLms, aluno_id: UUID
) -> None:
    avisos: list[object] = []
    from cbot.shared.events import ReautorizacaoNecessaria

    app.bus.subscribe(ReautorizacaoNecessaria, avisos.append)
    lms.token_valido = False

    execucao = app.sincronizar.executar(aluno_id)

    assert execucao.status is StatusExecucao.FALHA and len(avisos) == 1
    assert app.alunos.obter(aluno_id).estado_autorizacao.value == "reautorizar"


def test_oversized_files_are_skipped_not_downloaded(
    app: Container, lms: FakeLms, aluno_id: UUID
) -> None:
    lms.itens[1] = [item_arquivo(10, "video.mp4", 10**12, mime="video/mp4")]

    execucao = app.sincronizar.executar(aluno_id)

    assert execucao.estatisticas["arquivos_ignorados"] == 1 and lms.downloads == 0


def test_account_deletion_removes_everything(
    app: Container, lms: FakeLms, aluno_id: UUID, tmp_path
) -> None:  # type: ignore[no-untyped-def]
    lms.itens[1] = [item_arquivo(10, "apostila.txt", len(APOSTILA))]
    lms.arquivos[10] = APOSTILA
    app.sincronizar.executar(aluno_id)
    assert (tmp_path / str(aluno_id)).exists()

    app.alunos.excluir_conta(aluno_id)

    assert not (tmp_path / str(aluno_id)).exists()
    for tabela in ("itens_curso", "trechos", "arquivos", "eventos_mudanca", "execucoes_sync"):
        assert contar(app, tabela, aluno_id) == 0


def test_indexer_event_carries_citation_metadata(
    app: Container, lms: FakeLms, aluno_id: UUID
) -> None:
    capturados: list[ItemSincronizado] = []
    app.bus.subscribe(ItemSincronizado, capturados.append)
    lms.itens[1] = [item_texto("page:x", "Camada de enlace", "Quadros e endereços MAC.")]

    app.sincronizar.executar(aluno_id)

    assert (
        capturados[0].curso_nome == "Redes de Computadores" and capturados[0].secao == "Unidade 1"
    )
