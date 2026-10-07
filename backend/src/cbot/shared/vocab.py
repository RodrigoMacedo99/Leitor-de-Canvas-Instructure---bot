"""Vocabulário compartilhado (shared kernel): enums sem lógica de negócio."""

from enum import StrEnum


class TipoItem(StrEnum):
    PROGRAMA = "programa"
    ARQUIVO = "arquivo"
    PAGINA = "pagina"
    TAREFA = "tarefa"
    AVISO = "aviso"
    QUIZ = "quiz"


class TipoEvento(StrEnum):
    NOVO = "novo"
    ALTERADO = "alterado"
    REMOVIDO = "removido"


class Canal(StrEnum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class EstadoAutorizacao(StrEnum):
    PENDENTE = "pendente"
    ATIVA = "ativa"
    REAUTORIZAR = "reautorizar"


class StatusExecucao(StrEnum):
    EXECUTANDO = "executando"
    SUCESSO = "sucesso"
    PARCIAL = "parcial"
    FALHA = "falha"


class Gatilho(StrEnum):
    AGENDADO = "agendado"
    MANUAL = "manual"
