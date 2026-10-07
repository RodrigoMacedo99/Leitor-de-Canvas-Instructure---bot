from pathlib import Path

from cbot.modules.conteudo.public import ExtratorDeArquivos
from cbot.modules.rag.domain.chunker import SecaoEntrada


class ExtratorConteudoAdapter:
    """Padrão Adapter: o RAG pede `SecaoEntrada`; o módulo conteudo devolve `SecaoTexto`."""

    def __init__(self, extrator: ExtratorDeArquivos | None = None) -> None:
        self._extrator = extrator or ExtratorDeArquivos()

    def extrair(self, caminho: Path, mime: str, nome: str) -> list[SecaoEntrada]:
        return [
            SecaoEntrada(s.texto, pagina=s.pagina, titulo=s.titulo)
            for s in self._extrator.extrair(caminho, mime, nome)
        ]
