import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from cbot.modules.canvas.public import ConnectorFactory, LmsConnector
from cbot.modules.conteudo.public import (
    ConteudoRepository,
    Curso,
    ResultadoDiff,
    calcular_diff,
)
from cbot.modules.sincronizacao.application.gravador import Gravador
from cbot.modules.sincronizacao.domain.ports import (
    Armazenamento,
    ArquivoArmazenado,
    CredenciaisLms,
    ExecucaoRepository,
    ExecucaoSync,
)
from cbot.shared.errors import DomainError, LmsAuthorizationError
from cbot.shared.events import (
    DomainEvent,
    EventBus,
    ReautorizacaoNecessaria,
)
from cbot.shared.vocab import Gatilho, StatusExecucao, TipoItem

logger = logging.getLogger(__name__)


class SyncUow(Protocol):
    @property
    def conteudo(self) -> ConteudoRepository: ...
    @property
    def execucoes(self) -> ExecucaoRepository: ...


type SyncUowFactory = Callable[[], AbstractContextManager[SyncUow]]


@dataclass(slots=True)
class Estatisticas:
    cursos: int = 0
    novos: int = 0
    alterados: int = 0
    removidos: int = 0
    inalterados: int = 0
    arquivos_baixados: int = 0
    arquivos_ignorados: int = 0
    erros: list[str] = field(default_factory=list)

    def como_dict(self) -> dict[str, object]:
        return {
            "cursos": self.cursos, "novos": self.novos, "alterados": self.alterados,
            "removidos": self.removidos, "inalterados": self.inalterados,
            "arquivos_baixados": self.arquivos_baixados,
            "arquivos_ignorados": self.arquivos_ignorados, "erros": self.erros[:20],
        }  # fmt: skip


class SincronizarAluno:
    """Caso de uso central: traz do Canvas o que mudou, baixa arquivos e avisa o resto do sistema
    por eventos de domínio (indexação, notificação) — sem conhecê-los."""

    def __init__(
        self, uow: SyncUowFactory, credenciais: CredenciaisLms, connector_factory: ConnectorFactory,
        armazenamento: Armazenamento, bus: EventBus, *, max_download_bytes: int,
    ) -> None:  # fmt: skip
        self._uow = uow
        self._credenciais = credenciais
        self._connector_factory = connector_factory
        self._armazenamento = armazenamento
        self._bus = bus
        self._max_bytes = max_download_bytes

    def executar(self, aluno_id: UUID, gatilho: Gatilho = Gatilho.MANUAL) -> ExecucaoSync:
        execucao = ExecucaoSync(aluno_id=aluno_id, gatilho=gatilho)
        with self._uow() as uow:
            uow.execucoes.iniciar(execucao)
        stats = Estatisticas()
        try:
            conector = self._conectar(aluno_id)
            self._sincronizar_cursos(aluno_id, conector, stats)
            execucao.status = StatusExecucao.PARCIAL if stats.erros else StatusExecucao.SUCESSO
        except LmsAuthorizationError as exc:
            self._credenciais.exigir_reautorizacao(aluno_id)
            self._bus.publish(ReautorizacaoNecessaria(aluno_id))
            stats.erros.append(exc.detail)
            execucao.status = StatusExecucao.FALHA
        except DomainError as exc:
            stats.erros.append(exc.detail)
            execucao.status = StatusExecucao.FALHA
        execucao.estatisticas = stats.como_dict()
        with self._uow() as uow:
            uow.execucoes.finalizar(execucao)
        return execucao

    def _conectar(self, aluno_id: UUID) -> LmsConnector:
        url, token = self._credenciais.credenciais_lms(aluno_id)
        conector = self._connector_factory(url, token)
        conector.validar_token()
        return conector

    def _sincronizar_cursos(
        self, aluno_id: UUID, conector: LmsConnector, stats: Estatisticas
    ) -> None:
        cursos_lms = conector.listar_cursos()
        with self._uow() as uow:
            cursos = [uow.conteudo.upsert_curso(aluno_id, c) for c in cursos_lms]
            uow.conteudo.desativar_cursos_ausentes(aluno_id, [c.lms_id for c in cursos_lms])
        stats.cursos = len(cursos)
        for curso in cursos:
            try:
                self._sincronizar_curso(aluno_id, conector, curso, stats)
            except LmsAuthorizationError:
                raise
            except DomainError as exc:
                logger.warning("falha no curso %s: %s", curso.lms_curso_id, exc.detail)
                stats.erros.append(f"{curso.nome}: {exc.detail}")

    def _sincronizar_curso(
        self, aluno_id: UUID, conector: LmsConnector, curso: Curso, stats: Estatisticas
    ) -> None:
        with self._uow() as uow:
            existentes = uow.conteudo.itens_por_externo(aluno_id, curso.id)
        conhecidos = {k: v.modificado_lms_em for k, v in existentes.items()}
        coleta = conector.listar_itens(curso.lms_curso_id, conhecidos)
        diff = calcular_diff(existentes, coleta.itens, coleta.tipos_coletados)
        arquivos = self._baixar_arquivos(aluno_id, conector, diff, stats)
        eventos = self._gravar(aluno_id, curso, diff, arquivos, stats)
        for evento in eventos:  # só depois do commit: os handlers leem o que acabou de ser gravado
            self._bus.publish(evento)

    def _baixar_arquivos(
        self, aluno_id: UUID, conector: LmsConnector, diff: ResultadoDiff, stats: Estatisticas
    ) -> dict[str, ArquivoArmazenado]:
        itens = [*diff.novos, *(a.recebido for a in diff.alterados)]
        baixados: dict[str, ArquivoArmazenado] = {}
        for item in itens:
            if item.tipo is not TipoItem.ARQUIVO or item.arquivo is None:
                continue
            if item.arquivo.tamanho > self._max_bytes:
                stats.arquivos_ignorados += 1
                continue
            try:
                with conector.baixar_arquivo(item.arquivo) as chunks:
                    baixados[item.externo_id] = self._armazenamento.gravar(
                        aluno_id, chunks, self._max_bytes
                    )
                stats.arquivos_baixados += 1
            except DomainError as exc:
                if isinstance(exc, LmsAuthorizationError):
                    raise
                stats.arquivos_ignorados += 1
                stats.erros.append(f"{item.titulo}: {exc.detail}")
        return baixados

    def _gravar(
        self,
        aluno_id: UUID,
        curso: Curso,
        diff: ResultadoDiff,
        arquivos: dict[str, ArquivoArmazenado],
        stats: Estatisticas,
    ) -> list[DomainEvent]:
        with self._uow() as uow:
            gravador = Gravador(uow.conteudo, aluno_id, curso, arquivos)
            eventos = [
                *map(gravador.novo, diff.novos),
                *map(gravador.alterado, diff.alterados),
                *map(gravador.removido, diff.removidos),
            ]
            uow.conteudo.marcar_curso_sincronizado(aluno_id, curso.id, datetime.now(UTC))
        stats.novos += gravador.contagens.novos
        stats.alterados += gravador.contagens.alterados
        stats.removidos += gravador.contagens.removidos
        stats.inalterados += diff.inalterados
        return [e for e in eventos if e is not None]
