"""Resumo diário (inclusive o fluxo do template do WhatsApp), agendador e fila de jobs."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from cbot.container import Container
from cbot.modules.resumo.application.servico import NOTHING_NEW, ResultadoEnvio
from cbot.modules.sincronizacao.application.worker import JOB_RESUMO, JOB_SYNC
from cbot.shared.errors import UpstreamUnavailable
from cbot.shared.vocab import TipoItem
from tests.fakes import FakeCanal, FakeLms, ScriptedLlm, item_texto
from tests.integration.helpers import SENHA, conectar, mensagem, parear

pytestmark = pytest.mark.integration


@pytest.fixture
def aluno_id(container: Container, client: TestClient, auth: dict[str, str]) -> UUID:
    conectar(client, auth)
    return container.alunos.autenticar("ana@exemplo.com", SENHA).id


def com_novidade(
    container: Container, lms: FakeLms, aluno_id: UUID, prazo: datetime | None = None
) -> None:
    lms.itens[1] = [
        item_texto("assignment:5", "Lista 1", "Resolva.", tipo=TipoItem.TAREFA, prazo_em=prazo)
    ]
    container.sincronizar.executar(aluno_id)


def test_scheduled_summary_is_polished_by_llm_sent_and_marks_events(
    container: Container,
    client: TestClient,
    auth: dict[str, str],
    telegram: FakeCanal,
    lms: FakeLms,
    llm: ScriptedLlm,
    aluno_id: UUID,
) -> None:
    parear(client, auth, telegram)
    com_novidade(container, lms, aluno_id)
    llm.programar("Bom dia, Ana! Há uma tarefa nova: Lista 1.")

    resultado = container.servico_resumo.enviar_agendado(aluno_id)

    assert resultado is ResultadoEnvio.ENVIADO
    assert telegram.enviados[-1][1] == "Bom dia, Ana! Há uma tarefa nova: Lista 1."
    assert "Lista 1" in llm.chamadas[0]["messages"][0].blocks[0].text and llm.chamadas[0]["fast"]
    assert container.servico_resumo.enviar_agendado(aluno_id) is ResultadoEnvio.SEM_NOVIDADES
    with container.db.session() as s:
        assert (
            s.execute(
                text("SELECT count(*) FROM resumos WHERE enviado_em IS NOT NULL")
            ).scalar_one()
            == 1
        )


def test_summary_falls_back_to_deterministic_facts_when_llm_is_down(
    container: Container,
    client: TestClient,
    auth: dict[str, str],
    telegram: FakeCanal,
    lms: FakeLms,
    aluno_id: UUID,
) -> None:
    parear(client, auth, telegram)
    com_novidade(container, lms, aluno_id)

    class Fora:
        def complete(self, **_: object) -> None:
            raise UpstreamUnavailable("fora do ar")

    container.servico_resumo._llm = Fora()  # type: ignore[assignment]
    assert container.servico_resumo.enviar_agendado(aluno_id) is ResultadoEnvio.ENVIADO
    assert "tarefa: Lista 1" in telegram.enviados[-1][1]


def test_summary_without_linked_channel_keeps_events_pending(
    container: Container, lms: FakeLms, aluno_id: UUID
) -> None:
    com_novidade(container, lms, aluno_id)
    assert container.servico_resumo.enviar_agendado(aluno_id) is ResultadoEnvio.SEM_CANAL
    with container.db.session() as s:
        assert (
            s.execute(
                text("SELECT count(*) FROM eventos_mudanca WHERE notificado_em IS NULL")
            ).scalar_one()
            == 1
        )


def test_upcoming_deadline_alone_triggers_a_summary(
    container: Container,
    client: TestClient,
    auth: dict[str, str],
    telegram: FakeCanal,
    lms: FakeLms,
    aluno_id: UUID,
) -> None:
    parear(client, auth, telegram)
    com_novidade(container, lms, aluno_id, prazo=datetime.now(UTC) + timedelta(days=2))
    container.servico_resumo._llm = None  # texto determinístico, sem redação por LLM
    container.servico_resumo.gerar_texto(aluno_id)  # consome os eventos pendentes
    texto = container.servico_resumo.gerar_texto(aluno_id)
    assert "⏰" in texto and "Lista 1" in texto and texto != NOTHING_NEW


def test_whatsapp_outside_window_sends_template_then_full_text_on_reply(
    container: Container,
    client: TestClient,
    auth: dict[str, str],
    whatsapp: FakeCanal,
    lms: FakeLms,
    aluno_id: UUID,
) -> None:
    parear(client, auth, whatsapp)
    client.patch("/api/v1/alunos/me", headers=auth, json={"canal_preferido": "whatsapp"})
    with (
        container.db.session() as s
    ):  # a última mensagem do aluno foi há 2 dias: janela de 24 h fechada
        s.execute(
            text("UPDATE identidades_canal SET ultima_mensagem_in_em = now() - interval '2 days'")
        )
    com_novidade(container, lms, aluno_id)
    container.llm = None  # type: ignore[assignment]
    container.servico_resumo._llm = None

    resultado = container.servico_resumo.enviar_agendado(aluno_id)

    assert resultado is ResultadoEnvio.AGUARDANDO_RESPOSTA
    assert (
        whatsapp.avisos == [("777", "1 novidade(s)")] and "Lista 1" not in whatsapp.enviados[-1][1]
    )
    mensagem(client, "/cursos", "r1", canal="whatsapp")  # o aluno responde: abre a janela
    assert any("tarefa: Lista 1" in t for _, t in whatsapp.enviados)
    antes = len(whatsapp.enviados)
    mensagem(client, "/cursos", "r2", canal="whatsapp")
    assert (
        sum("tarefa: Lista 1" in t for _, t in whatsapp.enviados[antes:]) == 0
    )  # entregue uma única vez


def test_scheduler_enqueues_syncs_once_and_summaries_once_per_day(
    container: Container, aluno_id: UUID
) -> None:
    assert (
        container.agendador.enfileirar_syncs() == 1 and container.agendador.enfileirar_syncs() == 0
    )
    cedo = datetime(2026, 3, 10, 9, 0, tzinfo=UTC)  # 06:00 em Salvador, antes das 07:30
    assert container.agendador.enfileirar_resumos(cedo) == 0
    na_hora = datetime(2026, 3, 10, 11, 0, tzinfo=UTC)  # 08:00 em Salvador
    assert container.agendador.enfileirar_resumos(na_hora) == 1
    assert container.agendador.enfileirar_resumos(na_hora + timedelta(minutes=1)) == 0
    with container.db.session() as s:
        s.execute(
            text("UPDATE jobs SET criado_em = :t WHERE tipo = :tipo"),
            {"t": cedo - timedelta(days=1), "tipo": JOB_RESUMO},
        )
    assert (
        container.agendador.enfileirar_resumos(na_hora + timedelta(minutes=2)) == 1
    )  # o job é de ontem


def test_worker_runs_handlers_and_retries_failures_with_backoff_until_dead(
    container: Container, aluno_id: UUID
) -> None:
    chamadas: list[str] = []
    container.worker._handlers["falha"] = lambda job: (_ for _ in ()).throw(RuntimeError("boom"))
    container.worker._handlers["ok"] = lambda job: chamadas.append(job.tipo)
    with container.uow() as uow:
        uow.jobs.enfileirar("ok", aluno_id, {})
        uow.jobs.enfileirar("falha", aluno_id, {})
        uow.jobs.enfileirar("sem-handler", aluno_id, {})

    assert container.worker.run_once() == 3 and chamadas == ["ok"]
    with container.db.session() as s:
        estados = dict(s.execute(text("SELECT tipo, estado FROM jobs")).all())
        assert estados == {"ok": "concluido", "falha": "pendente", "sem-handler": "pendente"}
        assert s.execute(
            text(
                "SELECT executar_em > now() + interval '20 seconds' FROM jobs WHERE tipo = 'falha'"
            )
        ).scalar_one()
    assert container.worker.run_once() == 0  # em backoff

    for _ in range(2):  # esgota as tentativas
        with container.db.session() as s:
            s.execute(text("UPDATE jobs SET executar_em = now() WHERE estado = 'pendente'"))
        container.worker.run_once()
    with container.db.session() as s:
        assert s.execute(
            text("SELECT estado, tentativas, erro FROM jobs WHERE tipo = 'falha'")
        ).one() == ("morto", 3, "RuntimeError: boom")


def test_two_reservations_never_return_the_same_job(container: Container, aluno_id: UUID) -> None:
    with container.uow() as uow:
        for i in range(4):
            uow.jobs.enfileirar(f"t{i}", aluno_id, {})
    with container.uow() as uow:
        primeiros = uow.jobs.reservar(2, 60)
    with container.uow() as uow:
        segundos = uow.jobs.reservar(5, 60)
    ids = [j.id for j in primeiros] + [j.id for j in segundos]
    assert len(ids) == 4 == len(set(ids))


def test_expired_lease_makes_a_stuck_job_available_again(
    container: Container, aluno_id: UUID
) -> None:
    with container.uow() as uow:
        uow.jobs.enfileirar(JOB_SYNC, aluno_id, {})
        assert len(uow.jobs.reservar(1, 60)) == 1
    with container.uow() as uow:
        assert uow.jobs.reservar(1, 60) == []
    with container.db.session() as s:
        s.execute(text("UPDATE jobs SET bloqueado_ate = now() - interval '1 minute'"))
    with container.uow() as uow:
        assert len(uow.jobs.reservar(1, 60)) == 1
