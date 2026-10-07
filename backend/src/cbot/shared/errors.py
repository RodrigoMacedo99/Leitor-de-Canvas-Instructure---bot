class DomainError(Exception):
    """Violação de regra de negócio. Vira HTTP 422 (ou o status da subclasse)."""

    status = 422
    slug = "regra-de-negocio"
    title = "Regra de negócio violada"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ValidationFailed(DomainError):
    status = 422
    slug = "validacao"
    title = "Erro de validação"


class NotFound(DomainError):
    status = 404
    slug = "nao-encontrado"
    title = "Recurso não encontrado"


class Unauthorized(DomainError):
    status = 401
    slug = "nao-autenticado"
    title = "Não autenticado"


class Forbidden(DomainError):
    status = 403
    slug = "proibido"
    title = "Acesso negado"


class Conflict(DomainError):
    status = 409
    slug = "conflito"
    title = "Conflito de estado"


class UpstreamUnavailable(DomainError):
    status = 502
    slug = "servico-externo-indisponivel"
    title = "Serviço externo indisponível"


class LmsAuthorizationError(DomainError):
    """Token do Canvas inválido, expirado ou revogado."""

    status = 422
    slug = "token-lms-invalido"
    title = "Token do Canvas recusado"
