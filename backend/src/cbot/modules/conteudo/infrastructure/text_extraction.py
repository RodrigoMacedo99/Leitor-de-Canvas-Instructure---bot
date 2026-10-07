"""Extração de texto de arquivos (padrão Strategy + Registry).

Cada formato é um `TextExtractor`; o `ExtractorRegistry` escolhe pelo MIME ou pela extensão.
Adicionar um formato novo = escrever uma classe e registrá-la, sem tocar nos demais.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from bs4 import BeautifulSoup
from docx import Document
from pptx import Presentation
from pypdf import PdfReader

from cbot.shared.text import html_to_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SecaoTexto:
    """Pedaço de documento com sua origem (página/slide e título), usado nas citações."""

    texto: str
    pagina: int | None = None
    titulo: str | None = None


class TextExtractor(Protocol):
    def extrair(self, caminho: Path) -> list[SecaoTexto]: ...


class Registry[T]:
    """Mapeia chaves (MIME/extensão) para estratégias."""

    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    def register(self, keys: Iterable[str], value: T) -> None:
        for key in keys:
            self._items[key.lower()] = value

    def get(self, key: str) -> T | None:
        return self._items.get(key.lower())


class PdfExtractor:
    def extrair(self, caminho: Path) -> list[SecaoTexto]:
        reader = PdfReader(str(caminho))
        secoes = []
        for numero, pagina in enumerate(reader.pages, start=1):
            texto = (pagina.extract_text() or "").strip()
            if texto:
                secoes.append(SecaoTexto(texto, pagina=numero))
        return secoes


class DocxExtractor:
    def extrair(self, caminho: Path) -> list[SecaoTexto]:
        doc = Document(str(caminho))
        secoes: list[SecaoTexto] = []
        titulo: str | None = None
        buffer: list[str] = []

        def fechar() -> None:
            texto = "\n".join(buffer).strip()
            if texto:
                secoes.append(SecaoTexto(texto, titulo=titulo))
            buffer.clear()

        for paragrafo in doc.paragraphs:
            estilo = (paragrafo.style.name or "") if paragrafo.style else ""
            if (
                estilo.lower().startswith(("heading", "título", "titulo"))
                and paragrafo.text.strip()
            ):
                fechar()
                titulo = paragrafo.text.strip()
            buffer.append(paragrafo.text)
        fechar()
        return secoes


class PptxExtractor:
    def extrair(self, caminho: Path) -> list[SecaoTexto]:
        secoes = []
        for numero, slide in enumerate(Presentation(str(caminho)).slides, start=1):
            partes = [
                shape.text_frame.text for shape in slide.shapes
                if shape.has_text_frame and shape.text_frame.text.strip()
            ]  # fmt: skip
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                partes.append(slide.notes_slide.notes_text_frame.text)
            texto = "\n".join(p.strip() for p in partes if p.strip())
            if texto:
                secoes.append(SecaoTexto(texto, pagina=numero))
        return secoes


class HtmlExtractor:
    def extrair(self, caminho: Path) -> list[SecaoTexto]:
        html = caminho.read_text(encoding="utf-8", errors="replace")
        titulo_tag = BeautifulSoup(html, "lxml").find("title")
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else None
        texto = html_to_text(html)
        return [SecaoTexto(texto, titulo=titulo)] if texto else []


class PlainTextExtractor:
    def extrair(self, caminho: Path) -> list[SecaoTexto]:
        texto = caminho.read_text(encoding="utf-8", errors="replace").strip()
        return [SecaoTexto(texto)] if texto else []


def default_registry() -> Registry[TextExtractor]:
    registry: Registry[TextExtractor] = Registry()
    registry.register(["application/pdf", ".pdf"], PdfExtractor())
    registry.register(
        ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"],
        DocxExtractor(),
    )
    registry.register(
        ["application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"],
        PptxExtractor(),
    )
    registry.register(["text/html", ".html", ".htm"], HtmlExtractor())
    registry.register(
        ["text/plain", "text/markdown", "text/csv", ".txt", ".md", ".csv"], PlainTextExtractor()
    )
    return registry


class ExtratorDeArquivos:
    """Fachada: dado MIME e nome, devolve as seções de texto ou levanta `FormatoNaoSuportado`."""

    def __init__(self, registry: Registry[TextExtractor] | None = None) -> None:
        self._registry = registry or default_registry()

    def extrair(self, caminho: Path, mime: str, nome: str) -> list[SecaoTexto]:
        extractor = self._registry.get(mime) or self._registry.get(Path(nome).suffix)
        if extractor is None:
            raise FormatoNaoSuportado(f"Sem extrator para {mime or Path(nome).suffix}")
        return extractor.extrair(caminho)


class FormatoNaoSuportado(Exception):
    pass
