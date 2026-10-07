from datetime import UTC, datetime
from uuid import uuid4

from cbot.modules.conteudo.public import EventoDetalhado, PrazoDetalhado
from cbot.modules.resumo.domain.formatador import fatos_do_resumo, resumo_curto
from cbot.shared.vocab import TipoEvento, TipoItem

AGORA = datetime(2026, 3, 10, 15, 0, tzinfo=UTC)  # 12:00 em America/Bahia (UTC-3)


def evento(
    tipo: TipoEvento,
    titulo: str,
    item_tipo: TipoItem = TipoItem.TAREFA,
    curso: str = "Redes",
    **kw: object,
) -> EventoDetalhado:
    base = dict(
        id=uuid4(),
        tipo=tipo,
        detalhe={},
        detectado_em=AGORA,
        item_id=uuid4(),
        item_tipo=item_tipo,
        titulo=titulo,
        secao=None,
        url=None,
        prazo_em=None,
        curso_id=uuid4(),
        curso_nome=curso,
    )
    return EventoDetalhado(**{**base, **kw})  # type: ignore[arg-type]


def prazo(titulo: str, quando: datetime) -> PrazoDetalhado:
    return PrazoDetalhado(uuid4(), titulo, TipoItem.TAREFA, quando, None, uuid4(), "Redes")


def test_facts_are_grouped_by_course_with_local_dates() -> None:
    eventos = [
        evento(TipoEvento.NOVO, "Lista 1", prazo_em=datetime(2026, 3, 20, 2, 59, tzinfo=UTC)),
        evento(TipoEvento.NOVO, "aula1.pdf", TipoItem.ARQUIVO, secao="Unidade 1"),
        evento(TipoEvento.NOVO, "Cap. 3", TipoItem.PAGINA, curso="Banco de Dados"),
    ]
    texto = fatos_do_resumo(
        eventos, [prazo("Prova", datetime(2026, 3, 12, 15, 0, tzinfo=UTC))], "America/Bahia"
    )
    assert "Redes\n" in texto and "Banco de Dados\n" in texto
    assert (
        "tarefa: Lista 1 — prazo: 19/03 às 23:59" in texto
    )  # 02:59Z = 23:59 do dia anterior em Salvador
    assert (
        "arquivo: aula1.pdf (Unidade 1)" in texto and "⏰ 12/03 às 12:00 · Prova (Redes)" in texto
    )


def test_deadline_change_and_removal_are_described() -> None:
    mudou = evento(
        TipoEvento.ALTERADO,
        "Lista 1",
        detalhe={"prazo": {"de": "2026-03-20T12:00:00+00:00", "para": "2026-03-27T12:00:00+00:00"}},
    )
    sem_prazo = evento(
        TipoEvento.ALTERADO,
        "Quiz",
        TipoItem.QUIZ,
        detalhe={"prazo": {"de": "2026-03-20T12:00:00+00:00", "para": None}},
    )
    removido = evento(TipoEvento.REMOVIDO, "Aviso velho", TipoItem.AVISO)
    texto = fatos_do_resumo([mudou, sem_prazo, removido], [], "America/Bahia")
    assert (
        "novo prazo: 27/03 às 09:00" in texto
        and "prazo removido" in texto
        and "🗑️ aviso: Aviso velho" in texto
    )


def test_nothing_to_say_is_empty_and_short_summary() -> None:
    assert fatos_do_resumo([], [], "America/Bahia") == ""
    assert (
        resumo_curto([evento(TipoEvento.NOVO, "a")], [prazo("p", AGORA)])
        == "1 novidade(s) e 1 prazo(s) próximo(s)"
    )
    assert resumo_curto([], []) == "sem novidades"
