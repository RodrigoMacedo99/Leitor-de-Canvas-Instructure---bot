"""Cálculo puro (sem I/O) do que mudou entre o banco e o que o LMS devolveu."""

import hashlib
from dataclasses import dataclass, field
from typing import Any

from cbot.modules.canvas.public import ItemLms
from cbot.modules.conteudo.domain.entities import ItemCurso
from cbot.shared.vocab import TipoItem

_SEP = "\x1f"


def hash_item(item: ItemLms) -> str:
    """Hash dos metadados. Sem `modificado_em` (ex.: programa, quiz), o texto entra no hash."""
    partes = [
        item.titulo,
        item.modificado_em.isoformat() if item.modificado_em else "",
        item.prazo_em.isoformat() if item.prazo_em else "",
        str(item.arquivo.tamanho) if item.arquivo else "",
        item.url or "",
    ]
    if item.modificado_em is None and item.texto:
        partes.append(hashlib.sha256(item.texto.encode()).hexdigest())
    return hashlib.sha256(_SEP.join(partes).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Alterado:
    existente: ItemCurso
    recebido: ItemLms
    detalhe: dict[str, Any]


@dataclass(slots=True)
class ResultadoDiff:
    novos: list[ItemLms] = field(default_factory=list)
    alterados: list[Alterado] = field(default_factory=list)
    removidos: list[ItemCurso] = field(default_factory=list)
    inalterados: int = 0


def detalhar_mudanca(antigo: ItemCurso, novo: ItemLms) -> dict[str, Any]:
    detalhe: dict[str, Any] = {}
    if antigo.titulo != novo.titulo:
        detalhe["titulo"] = {"de": antigo.titulo, "para": novo.titulo}
    if antigo.prazo_em != novo.prazo_em:
        detalhe["prazo"] = {
            "de": antigo.prazo_em.isoformat() if antigo.prazo_em else None,
            "para": novo.prazo_em.isoformat() if novo.prazo_em else None,
        }
    return detalhe


def calcular_diff(
    existentes: dict[str, ItemCurso],
    recebidos: list[ItemLms],
    tipos_coletados: frozenset[TipoItem],
) -> ResultadoDiff:
    """Compara por `externo_id`. Só marca remoção em tipos coletados por completo."""
    resultado = ResultadoDiff()
    vistos: set[str] = set()
    for item in recebidos:
        vistos.add(item.externo_id)
        atual = existentes.get(item.externo_id)
        if atual is None or atual.status == "removido":
            resultado.novos.append(item)
        elif atual.hash_conteudo != hash_item(item):
            resultado.alterados.append(Alterado(atual, item, detalhar_mudanca(atual, item)))
        else:
            resultado.inalterados += 1
    resultado.removidos = [
        e for k, e in existentes.items()
        if k not in vistos and e.status == "ativo" and e.tipo in tipos_coletados
    ]  # fmt: skip
    return resultado
