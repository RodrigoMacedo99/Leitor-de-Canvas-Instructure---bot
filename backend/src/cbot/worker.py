"""Processo Worker: agenda e executa sincronizações, indexação e resumos diários.

Executa em um contêiner separado da API (mesma base de código). `python -m cbot.worker`.
"""

import logging
import signal
import threading

from cbot.config import get_settings
from cbot.container import build_container
from cbot.modules.sincronizacao.application.worker import iniciar_scheduler
from cbot.shared.logging import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    settings = get_settings()
    container = build_container(settings)
    scheduler = iniciar_scheduler(
        container.agendador, container.worker, settings.sync_interval_hours
    )
    logger.info("worker iniciado (sync a cada %sh)", settings.sync_interval_hours)
    parar = threading.Event()
    for sinal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sinal, lambda *_: parar.set())
    parar.wait()
    scheduler.shutdown()
    container.db.dispose()


if __name__ == "__main__":
    main()
