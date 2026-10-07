from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cbot.container import Container
from cbot.shared.errors import Unauthorized
from cbot.shared.security import decode_jwt

_bearer = HTTPBearer(auto_error=False)


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


def aluno_atual(
    container: ContainerDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UUID:
    """Identifica o aluno pelo JWT (`Authorization: Bearer`). Nunca aceita token na URL."""
    if credentials is None:
        raise Unauthorized("Envie o cabeçalho Authorization: Bearer <token>.")
    return decode_jwt(credentials.credentials, container.settings.jwt_secret.get_secret_value())


AlunoId = Annotated[UUID, Depends(aluno_atual)]
