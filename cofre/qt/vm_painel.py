"""Página Painel de segurança (v2): período de análise e pedido de atualização das três abas."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Signal, Slot

from .base import prop
from .base_v2 import PaginaAbasVM

PERIODOS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30), "tudo": None}


class PainelVM(PaginaAbasVM):
    CHAVE = "painel"

    periodoMudou = Signal()
    atualizarPedido = Signal()          # as abas ligam isto a pedir_recarga (nunca direto a recarregar)

    periodo = prop(str, "periodo", periodoMudou)          # "24h" | "7d" | "30d" | "tudo"

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(periodo="tudo")

    @Slot(str)
    def definirPeriodo(self, valor: str) -> None:
        if valor in PERIODOS and self._definir("periodo", valor):
            self.atualizarPedido.emit()

    @Slot()
    def atualizar(self) -> None:
        self.atualizarPedido.emit()

    def desde_iso(self) -> str | None:
        """Início do período no formato de `acessos.data_hora` (ISO local de 19 caracteres); `None` para "tudo"."""
        duracao = PERIODOS[self._v["periodo"]]
        return None if duracao is None else (datetime.now() - duracao).isoformat(timespec="seconds")
