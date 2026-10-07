"""Aplica no banco o resultado de um diff (novo/alterado/removido) e gera os eventos de domínio."""

from dataclasses import dataclass
from uuid import UUID

from cbot.modules.canvas.public import ItemLms
from cbot.modules.conteudo.domain.diff import Alterado
from cbot.modules.conteudo.public import (
    ArquivoRegistro,
    ConteudoRepository,
    Curso,
    EventoMudanca,
    ItemCurso,
    hash_item,
)
from cbot.modules.sincronizacao.domain.ports import ArquivoArmazenado
from cbot.shared.events import DomainEvent, ItemRemovido, ItemSincronizado
from cbot.shared.vocab import TipoEvento, TipoItem


@dataclass(slots=True)
class Contagens:
    novos: int = 0
    alterados: int = 0
    removidos: int = 0


class Gravador:
    """Cada método persiste uma mudança e devolve o evento que o resto do sistema deve receber
    (ou None quando nada precisa ser reindexado)."""

    def __init__(
        self,
        repo: ConteudoRepository,
        aluno_id: UUID,
        curso: Curso,
        arquivos: dict[str, ArquivoArmazenado],
    ) -> None:
        self._repo = repo
        self._aluno_id = aluno_id
        self._curso = curso
        self._arquivos = arquivos
        self.contagens = Contagens()

    def novo(self, item: ItemLms) -> DomainEvent | None:
        registro = ItemCurso(
            aluno_id=self._aluno_id,
            curso_id=self._curso.id,
            tipo=item.tipo,
            externo_id=item.externo_id,
            titulo=item.titulo,
            hash_conteudo=hash_item(item),
            secao=item.secao,
            url=item.url,
            prazo_em=item.prazo_em,
            modificado_lms_em=item.modificado_em,
            conteudo_texto=item.texto,
        )
        self._repo.inserir_item(registro)
        self._repo.inserir_evento(EventoMudanca(self._aluno_id, registro.id, TipoEvento.NOVO))
        self.contagens.novos += 1
        return self._indexar(registro, item)

    def alterado(self, alteracao: Alterado) -> DomainEvent | None:
        atual, item = alteracao.existente, alteracao.recebido
        atual.titulo, atual.secao, atual.url = item.titulo, item.secao, item.url
        atual.prazo_em, atual.modificado_lms_em = item.prazo_em, item.modificado_em
        atual.hash_conteudo = hash_item(item)
        atual.conteudo_texto = item.texto if item.texto is not None else atual.conteudo_texto
        atual.status = "ativo"
        self._repo.atualizar_item(atual)
        evento = self._indexar(atual, item)
        if evento is not None or alteracao.detalhe:
            self._repo.inserir_evento(
                EventoMudanca(
                    self._aluno_id, atual.id, TipoEvento.ALTERADO, detalhe=alteracao.detalhe
                )
            )
            self.contagens.alterados += 1
        return evento

    def removido(self, item: ItemCurso) -> DomainEvent:
        self._repo.marcar_item_removido(self._aluno_id, item.id)
        self._repo.inserir_evento(EventoMudanca(self._aluno_id, item.id, TipoEvento.REMOVIDO))
        self.contagens.removidos += 1
        return ItemRemovido(self._aluno_id, item.id)

    def _indexar(self, registro: ItemCurso, item: ItemLms) -> ItemSincronizado | None:
        if item.tipo is TipoItem.ARQUIVO:
            return self._indexar_arquivo(registro, item)
        texto = item.texto or registro.conteudo_texto
        return self._evento(registro, texto=texto) if texto else None

    def _indexar_arquivo(self, registro: ItemCurso, item: ItemLms) -> ItemSincronizado | None:
        arquivo = self._arquivos.get(item.externo_id)
        if arquivo is None or item.arquivo is None:
            return None
        anterior = self._repo.ultimo_arquivo(self._aluno_id, registro.id)
        if anterior and anterior.sha256 == arquivo.sha256:
            return None  # só metadados mudaram: o conteúdo é o mesmo, não reindexa
        novo = ArquivoRegistro(
            aluno_id=self._aluno_id,
            item_id=registro.id,
            nome=item.arquivo.nome,
            mime=item.arquivo.mime,
            tamanho=arquivo.tamanho,
            sha256=arquivo.sha256,
            versao=(anterior.versao + 1) if anterior else 1,
        )
        self._repo.inserir_arquivo(novo)
        return self._evento(
            registro,
            texto=None,
            arquivo_id=novo.id,
            arquivo_caminho=str(arquivo.caminho),
            arquivo_mime=novo.mime,
            arquivo_nome=novo.nome,
        )

    def _evento(self, registro: ItemCurso, **extras: object) -> ItemSincronizado:
        return ItemSincronizado(
            aluno_id=self._aluno_id,
            item_id=registro.id,
            curso_id=self._curso.id,
            curso_nome=self._curso.nome,
            titulo=registro.titulo,
            secao=registro.secao,
            url=registro.url,
            **extras,  # type: ignore[arg-type]
        )
