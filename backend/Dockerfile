# Imagem de produção do backend (API e Worker usam a mesma imagem; muda só o comando).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Tesseract/poppler não são necessários: a extração de PDF usa pypdf (puro Python).
COPY pyproject.toml ./
COPY src ./src
RUN pip install .

COPY alembic.ini ./
COPY migrations ./migrations

RUN useradd --system --uid 10001 --create-home cbot \
    && mkdir -p /data/arquivos \
    && chown -R cbot:cbot /data /app
USER cbot

ENV STORAGE_DIR=/data/arquivos
EXPOSE 3001

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:3001/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "cbot.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "3001"]
