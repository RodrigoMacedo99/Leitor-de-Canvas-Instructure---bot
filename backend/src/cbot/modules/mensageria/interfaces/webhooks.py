import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response
from fastapi.responses import PlainTextResponse

from cbot.modules.mensageria.domain.ports import CanalMensageria
from cbot.modules.mensageria.infrastructure.canais import WhatsAppCanal
from cbot.shared.auth import ContainerDep
from cbot.shared.errors import Forbidden, NotFound
from cbot.shared.vocab import Canal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


def _canal(c: ContainerDep, canal: Canal) -> CanalMensageria:
    adaptador = c.canais.get(canal)
    if adaptador is None:
        raise NotFound(f"Canal {canal.value} não configurado.")
    return adaptador


async def _receber(
    request: Request, c: ContainerDep, canal: Canal, tasks: BackgroundTasks
) -> Response:
    """Valida a assinatura, responde 200 na hora e processa em segundo plano (as plataformas
    reenviam o webhook se a resposta demorar)."""
    adaptador = _canal(c, canal)
    corpo = await request.body()
    if not adaptador.autentico(request.headers, corpo):
        raise Forbidden("Assinatura do webhook inválida.")
    try:
        payload: dict[str, Any] = json.loads(corpo)
    except json.JSONDecodeError:
        return Response(status_code=200)
    for mensagem in adaptador.interpretar(payload):
        tasks.add_task(c.tratar_mensagem.tratar, mensagem)
    return Response(status_code=200)


@router.post("/telegram")
async def webhook_telegram(request: Request, c: ContainerDep, tasks: BackgroundTasks) -> Response:
    return await _receber(request, c, Canal.TELEGRAM, tasks)


@router.get("/whatsapp", response_class=PlainTextResponse)
def verificar_whatsapp(
    c: ContainerDep,
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    adaptador = _canal(c, Canal.WHATSAPP)
    assert isinstance(adaptador, WhatsAppCanal)
    resposta = adaptador.verificar_assinatura_get(mode, token, challenge)
    if resposta is None:
        raise Forbidden("Token de verificação inválido.")
    return resposta


@router.post("/whatsapp")
async def webhook_whatsapp(request: Request, c: ContainerDep, tasks: BackgroundTasks) -> Response:
    return await _receber(request, c, Canal.WHATSAPP, tasks)
