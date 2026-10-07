from datetime import UTC, datetime
from uuid import uuid4

from cbot.modules.canvas.public import ArquivoLms, ItemLms
from cbot.modules.conteudo.domain.diff import calcular_diff, hash_item
from cbot.modules.conteudo.domain.entities import ItemCurso
from cbot.shared.vocab import TipoItem

T1 = datetime(2026, 3, 1, tzinfo=UTC)
T2 = datetime(2026, 3, 9, tzinfo=UTC)
ALUNO, CURSO = uuid4(), uuid4()


def lms(externo: str = "assignment:1", tipo: TipoItem = TipoItem.TAREFA, **kw) -> ItemLms:
    base = dict(
        tipo=tipo,
        externo_id=externo,
        titulo="Lista 1",
        secao=None,
        url="u",
        prazo_em=T2,
        modificado_em=T1,
    )
    return ItemLms(**{**base, **kw})


def stored(item: ItemLms, **kw) -> ItemCurso:
    base = dict(
        aluno_id=ALUNO,
        curso_id=CURSO,
        tipo=item.tipo,
        externo_id=item.externo_id,
        titulo=item.titulo,
        hash_conteudo=hash_item(item),
        prazo_em=item.prazo_em,
    )
    return ItemCurso(**{**base, **kw})


ALL = frozenset(TipoItem)


def test_new_item_is_detected() -> None:
    d = calcular_diff({}, [lms()], ALL)
    assert len(d.novos) == 1 and not d.alterados and not d.removidos


def test_identical_item_is_unchanged() -> None:
    item = lms()
    d = calcular_diff({item.externo_id: stored(item)}, [item], ALL)
    assert d.inalterados == 1 and not d.novos and not d.alterados


def test_deadline_change_records_old_and_new() -> None:
    antigo = lms()
    novo = lms(prazo_em=datetime(2026, 3, 20, tzinfo=UTC), modificado_em=T2)
    d = calcular_diff({antigo.externo_id: stored(antigo)}, [novo], ALL)
    assert d.alterados[0].detalhe["prazo"]["para"].startswith("2026-03-20")
    assert d.alterados[0].detalhe["prazo"]["de"].startswith("2026-03-09")


def test_title_change_is_detailed() -> None:
    antigo = lms()
    novo = lms(titulo="Lista 1 (revisada)", modificado_em=T2)
    d = calcular_diff({antigo.externo_id: stored(antigo)}, [novo], ALL)
    assert d.alterados[0].detalhe["titulo"] == {"de": "Lista 1", "para": "Lista 1 (revisada)"}


def test_missing_item_is_removed_only_for_fully_collected_types() -> None:
    item = lms()
    existentes = {item.externo_id: stored(item)}
    assert len(calcular_diff(existentes, [], ALL).removidos) == 1
    assert calcular_diff(existentes, [], frozenset({TipoItem.ARQUIVO})).removidos == []


def test_removed_item_that_returns_counts_as_new() -> None:
    item = lms()
    d = calcular_diff({item.externo_id: stored(item, status="removido")}, [item], ALL)
    assert len(d.novos) == 1


def test_file_size_change_changes_hash() -> None:
    a = ArquivoLms(1, "a.pdf", "application/pdf", 10, "u")
    b = ArquivoLms(1, "a.pdf", "application/pdf", 11, "u")
    base = dict(
        tipo=TipoItem.ARQUIVO,
        externo_id="file:1",
        titulo="a.pdf",
        secao=None,
        url="u",
        prazo_em=None,
        modificado_em=T1,
    )
    assert hash_item(ItemLms(**base, arquivo=a)) != hash_item(ItemLms(**base, arquivo=b))


def test_text_counts_in_hash_only_without_modified_date() -> None:
    sem_data = dict(
        tipo=TipoItem.PROGRAMA,
        externo_id="syllabus",
        titulo="P",
        secao=None,
        url=None,
        prazo_em=None,
        modificado_em=None,
    )
    assert hash_item(ItemLms(**sem_data, texto="a")) != hash_item(ItemLms(**sem_data, texto="b"))
    com_data = {**sem_data, "modificado_em": T1}
    assert hash_item(ItemLms(**com_data, texto="a")) == hash_item(ItemLms(**com_data, texto="b"))
