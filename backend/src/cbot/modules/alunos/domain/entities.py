from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from uuid import UUID, uuid4

from cbot.shared.errors import ValidationFailed
from cbot.shared.vocab import Canal, EstadoAutorizacao

MIN_PASSWORD_LENGTH = 10


@dataclass(slots=True)
class Aluno:
    """Aggregate root: dono dos dados, da credencial do Canvas e das preferências de envio."""

    email: str
    senha_hash: str
    nome: str
    id: UUID = field(default_factory=uuid4)
    lms_url_base: str | None = None
    token_lms_cifrado: bytes | None = None
    lms_usuario_id: int | None = None
    estado_autorizacao: EstadoAutorizacao = EstadoAutorizacao.PENDENTE
    canal_preferido: Canal = Canal.TELEGRAM
    fuso_horario: str = "America/Bahia"
    hora_resumo: time = time(7, 30)
    consentimento_em: datetime | None = None

    @staticmethod
    def validar_senha(senha: str) -> None:
        if len(senha) < MIN_PASSWORD_LENGTH:
            raise ValidationFailed(f"A senha deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres.")

    def conectar_lms(self, url_base: str, token_cifrado: bytes, usuario_id: int) -> None:
        self.lms_url_base = url_base
        self.token_lms_cifrado = token_cifrado
        self.lms_usuario_id = usuario_id
        self.estado_autorizacao = EstadoAutorizacao.ATIVA
        self.consentimento_em = self.consentimento_em or datetime.now(UTC)

    def exigir_reautorizacao(self) -> None:
        self.estado_autorizacao = EstadoAutorizacao.REAUTORIZAR

    @property
    def sincronizavel(self) -> bool:
        return (
            self.estado_autorizacao is EstadoAutorizacao.ATIVA
            and self.token_lms_cifrado is not None
        )


@dataclass(slots=True)
class IdentidadeCanal:
    aluno_id: UUID
    canal: Canal
    id: UUID = field(default_factory=uuid4)
    externo_id: str | None = None
    verificado_em: datetime | None = None
    ultima_mensagem_in_em: datetime | None = None

    @property
    def janela_24h_aberta(self) -> bool:
        if self.ultima_mensagem_in_em is None:
            return False
        return (datetime.now(UTC) - self.ultima_mensagem_in_em).total_seconds() < 24 * 3600
