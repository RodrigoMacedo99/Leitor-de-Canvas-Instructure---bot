from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ResumoRegistro:
    id: UUID
    periodo_ini: datetime
    periodo_fim: datetime
    texto: str
    canal: str | None
    enviado_em: datetime | None


class ResumoRepository(Protocol):
    def salvar(self, aluno_id: UUID, ini: datetime, fim: datetime, texto: str) -> UUID: ...

    def marcar_enviado(
        self, aluno_id: UUID, resumo_id: UUID, canal: str, quando: datetime
    ) -> None: ...

    def ultimo_enviado_em(self, aluno_id: UUID) -> datetime | None: ...

    def pendente_de_entrega(self, aluno_id: UUID) -> tuple[UUID, str] | None:
        """Resumo cujo aviso (template) foi enviado mas o texto completo ainda não."""
        ...

    def marcar_entregue(self, aluno_id: UUID, resumo_id: UUID, quando: datetime) -> None: ...

    def salvar_pendente(
        self, aluno_id: UUID, ini: datetime, fim: datetime, texto: str, canal: str
    ) -> UUID: ...

    def listar(
        self, aluno_id: UUID, limite: int, deslocamento: int
    ) -> tuple[list[ResumoRegistro], int]: ...
