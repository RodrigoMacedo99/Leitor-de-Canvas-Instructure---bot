"""API pública do módulo `conteudo`."""

from cbot.modules.conteudo.domain.diff import ResultadoDiff, calcular_diff, hash_item
from cbot.modules.conteudo.domain.entities import (
    ArquivoRegistro,
    Curso,
    EventoDetalhado,
    EventoMudanca,
    ItemCurso,
    PrazoDetalhado,
)
from cbot.modules.conteudo.domain.repository import ConteudoRepository
from cbot.modules.conteudo.infrastructure.file_storage import ArquivoGravado, FileStorage
from cbot.modules.conteudo.infrastructure.text_extraction import ExtratorDeArquivos, SecaoTexto

__all__ = [
    "ArquivoGravado",
    "ArquivoRegistro",
    "ConteudoRepository",
    "Curso",
    "EventoDetalhado",
    "EventoMudanca",
    "ExtratorDeArquivos",
    "FileStorage",
    "ItemCurso",
    "PrazoDetalhado",
    "ResultadoDiff",
    "SecaoTexto",
    "calcular_diff",
    "hash_item",
]
