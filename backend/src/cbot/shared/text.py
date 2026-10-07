import re

from bs4 import BeautifulSoup

_SPACES = re.compile(r"[ \t ]+")
_NOISE_TAGS = ("script", "style", "noscript", "iframe", "head")


def html_to_text(html: str | None) -> str:
    """Converte HTML do Canvas em texto simples: uma linha por bloco, sem linhas vazias."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_NOISE_TAGS):
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    lines = (_SPACES.sub(" ", line).strip() for line in soup.get_text(separator="\n").splitlines())
    return "\n".join(line for line in lines if line)
