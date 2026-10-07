"""Montagem determinística dos fatos do resumo (sem LLM): evita inventar informação."""

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from cbot.modules.conteudo.public import EventoDetalhado, PrazoDetalhado
from cbot.shared.vocab import TipoEvento, TipoItem

DATE_FMT = "%d/%m às %H:%M"
ROTULO_TIPO = {
    TipoItem.PROGRAMA: "programa", TipoItem.ARQUIVO: "arquivo", TipoItem.PAGINA: "página",
    TipoItem.TAREFA: "tarefa", TipoItem.AVISO: "aviso", TipoItem.QUIZ: "quiz",
}  # fmt: skip
SIMBOLO = {TipoEvento.NOVO: "🆕", TipoEvento.ALTERADO: "✏️", TipoEvento.REMOVIDO: "🗑️"}


def _data(dt: datetime, fuso: str) -> str:
    return dt.astimezone(ZoneInfo(fuso)).strftime(DATE_FMT)


def _linha_evento(e: EventoDetalhado, fuso: str) -> str:
    rotulo = ROTULO_TIPO[e.item_tipo]
    base = f"{SIMBOLO[e.tipo]} {rotulo}: {e.titulo}"
    if e.secao:
        base += f" ({e.secao})"
    prazo = e.detalhe.get("prazo")
    if e.tipo is TipoEvento.ALTERADO and prazo:
        novo = datetime.fromisoformat(prazo["para"]) if prazo.get("para") else None
        base += f" — novo prazo: {_data(novo, fuso)}" if novo else " — prazo removido"
    elif e.prazo_em and e.tipo is TipoEvento.NOVO:
        base += f" — prazo: {_data(e.prazo_em, fuso)}"
    return base


def fatos_do_resumo(eventos: list[EventoDetalhado], prazos: list[PrazoDetalhado], fuso: str) -> str:
    """Texto-base do resumo, agrupado por curso. Vazio se não há nada a dizer."""
    por_curso: dict[str, list[str]] = defaultdict(list)
    for e in eventos:
        por_curso[e.curso_nome].append(_linha_evento(e, fuso))
    blocos = [f"{curso}\n" + "\n".join(linhas) for curso, linhas in por_curso.items()]
    if prazos:
        linhas = [f"⏰ {_data(p.prazo_em, fuso)} · {p.titulo} ({p.curso_nome})" for p in prazos]
        blocos.append("Prazos dos próximos dias\n" + "\n".join(linhas))
    return "\n\n".join(blocos)


def resumo_curto(eventos: list[EventoDetalhado], prazos: list[PrazoDetalhado]) -> str:
    """Uma linha para o aviso do WhatsApp (parâmetro do template)."""
    partes = []
    if eventos:
        partes.append(f"{len(eventos)} novidade(s)")
    if prazos:
        partes.append(f"{len(prazos)} prazo(s) próximo(s)")
    return " e ".join(partes) or "sem novidades"
