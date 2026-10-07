import hashlib
import secrets
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, time, timedelta
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cbot.modules.alunos.domain.entities import Aluno, IdentidadeCanal
from cbot.modules.alunos.domain.repository import AlunoRepository
from cbot.modules.canvas.public import ConnectorFactory, normalizar_url_base
from cbot.shared.errors import Conflict, Forbidden, NotFound, Unauthorized, ValidationFailed
from cbot.shared.events import ContaExcluida, EventBus
from cbot.shared.security import TokenCipher, hash_password, verify_password
from cbot.shared.vocab import Canal

PAIRING_TTL = timedelta(minutes=15)
PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PAIRING_LENGTH = 8
_DUMMY_HASH = hash_password("senha-fantasma-para-tempo-constante")


class AlunosUow(Protocol):
    @property
    def alunos(self) -> AlunoRepository: ...


type UowFactory = Callable[[], AbstractContextManager[AlunosUow]]


def hash_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.strip().upper().encode()).hexdigest()


class AlunosService:
    """Casos de uso de cadastro, autenticação, credencial do Canvas e vínculo de canais."""

    def __init__(
        self,
        uow: UowFactory,
        cipher: TokenCipher,
        connector_factory: ConnectorFactory,
        *,
        registro_aberto: bool = True,
        permitir_http_local: bool = False,
        bus: EventBus | None = None,
    ) -> None:
        self._uow = uow
        self._cipher = cipher
        self._connector_factory = connector_factory
        self._registro_aberto = registro_aberto
        self._http_local = permitir_http_local
        self._bus = bus

    def registrar(self, email: str, senha: str, nome: str) -> Aluno:
        if not self._registro_aberto:
            raise Forbidden("O cadastro de novos alunos está fechado.")
        Aluno.validar_senha(senha)
        with self._uow() as uow:
            if uow.alunos.obter_por_email(email):
                raise Conflict("Já existe um cadastro com este e-mail.")
            aluno = Aluno(
                email=email.strip().lower(), senha_hash=hash_password(senha), nome=nome.strip()
            )
            uow.alunos.adicionar(aluno)
        return aluno

    def autenticar(self, email: str, senha: str) -> Aluno:
        with self._uow() as uow:
            aluno = uow.alunos.obter_por_email(email)
        # compara sempre um hash para não vazar, pelo tempo, se o e-mail existe
        senha_ok = verify_password(senha, aluno.senha_hash if aluno else _DUMMY_HASH)
        if aluno is None or not senha_ok:
            raise Unauthorized("E-mail ou senha inválidos.")
        return aluno

    def obter(self, aluno_id: UUID) -> Aluno:
        with self._uow() as uow:
            aluno = uow.alunos.obter(aluno_id)
        if aluno is None:
            raise NotFound("Aluno não encontrado.")
        return aluno

    def conectar_canvas(
        self, aluno_id: UUID, url_base: str, token: str, *, consentimento: bool
    ) -> Aluno:
        if not consentimento:
            raise ValidationFailed("É necessário consentir com o tratamento dos dados (LGPD).")
        url = normalizar_url_base(url_base, permitir_http_local=self._http_local)
        perfil = self._connector_factory(url, token.strip()).validar_token()
        with self._uow() as uow:
            aluno = self._obter_ou_falhar(uow, aluno_id)
            aluno.conectar_lms(url, self._cipher.encrypt(token.strip()), perfil.usuario_id)
            uow.alunos.salvar(aluno)
        return aluno

    def atualizar_preferencias(
        self, aluno_id: UUID, *, canal_preferido: Canal | None = None,
        fuso_horario: str | None = None, hora_resumo: time | None = None,
    ) -> Aluno:  # fmt: skip
        if fuso_horario:
            self._validar_fuso(fuso_horario)
        with self._uow() as uow:
            aluno = self._obter_ou_falhar(uow, aluno_id)
            aluno.canal_preferido = canal_preferido or aluno.canal_preferido
            aluno.fuso_horario = fuso_horario or aluno.fuso_horario
            aluno.hora_resumo = hora_resumo or aluno.hora_resumo
            uow.alunos.salvar(aluno)
        return aluno

    @staticmethod
    def _validar_fuso(nome: str) -> None:
        try:
            ZoneInfo(nome)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValidationFailed(f"Fuso horário desconhecido: {nome}") from exc

    def credenciais_lms(self, aluno_id: UUID) -> tuple[str, str]:
        aluno = self.obter(aluno_id)
        if not aluno.sincronizavel or aluno.lms_url_base is None or aluno.token_lms_cifrado is None:
            raise Forbidden("O aluno ainda não autorizou o acesso ao Canvas.")
        return aluno.lms_url_base, self._cipher.decrypt(aluno.token_lms_cifrado)

    def exigir_reautorizacao(self, aluno_id: UUID) -> None:
        with self._uow() as uow:
            aluno = self._obter_ou_falhar(uow, aluno_id)
            aluno.exigir_reautorizacao()
            uow.alunos.salvar(aluno)

    def fuso_do_aluno(self, aluno_id: UUID) -> str:
        return self.obter(aluno_id).fuso_horario

    def listar_sincronizaveis(self) -> list[Aluno]:
        with self._uow() as uow:
            return uow.alunos.listar_sincronizaveis()

    def excluir_conta(self, aluno_id: UUID) -> None:
        with self._uow() as uow:
            uow.alunos.excluir_definitivamente(aluno_id)
        if self._bus:
            self._bus.publish(ContaExcluida(aluno_id))

    # --- canais -----------------------------------------------------------------
    def gerar_codigo_pareamento(self, aluno_id: UUID, canal: Canal) -> tuple[str, datetime]:
        codigo = "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(PAIRING_LENGTH))
        expira = datetime.now(UTC) + PAIRING_TTL
        with self._uow() as uow:
            self._obter_ou_falhar(uow, aluno_id)
            uow.alunos.criar_pareamento(aluno_id, canal, hash_codigo(codigo), expira)
        return codigo, expira

    def vincular_canal(self, canal: Canal, externo_id: str, codigo: str) -> IdentidadeCanal | None:
        with self._uow() as uow:
            return uow.alunos.vincular_por_codigo(
                canal, hash_codigo(codigo), externo_id, datetime.now(UTC)
            )

    def resolver_identidade(self, canal: Canal, externo_id: str) -> IdentidadeCanal | None:
        with self._uow() as uow:
            identidade = uow.alunos.obter_identidade(canal, externo_id)
            if identidade:
                uow.alunos.registrar_mensagem_recebida(identidade.id, datetime.now(UTC))
                identidade.ultima_mensagem_in_em = datetime.now(UTC)
            return identidade

    def identidade_do_aluno(self, aluno_id: UUID, canal: Canal) -> IdentidadeCanal | None:
        with self._uow() as uow:
            return uow.alunos.identidade_do_aluno(aluno_id, canal)

    def listar_identidades(self, aluno_id: UUID) -> list[IdentidadeCanal]:
        with self._uow() as uow:
            return uow.alunos.listar_identidades(aluno_id)

    def remover_identidade(self, aluno_id: UUID, identidade_id: UUID) -> None:
        with self._uow() as uow:
            if not uow.alunos.remover_identidade(aluno_id, identidade_id):
                raise NotFound("Vínculo não encontrado.")

    @staticmethod
    def _obter_ou_falhar(uow: AlunosUow, aluno_id: UUID) -> Aluno:
        aluno = uow.alunos.obter(aluno_id)
        if aluno is None:
            raise NotFound("Aluno não encontrado.")
        return aluno
