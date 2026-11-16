"""Modelo de lista genérico (QAbstractListModel) para tabelas e listas do QML."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QPersistentModelIndex, Qt, Property, Signal, Slot

_ModelIndex = QModelIndex | QPersistentModelIndex


class ModeloLista(QAbstractListModel):
    """Lista de dicionários; cada chave vira um papel (role) acessível no delegate do QML."""

    contagemMudou = Signal()

    def __init__(self, papeis: list[str], parent=None):
        super().__init__(parent)
        self._papeis = list(papeis)
        self._roles = {Qt.ItemDataRole.UserRole + 1 + i: p for i, p in enumerate(self._papeis)}
        self._itens: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ API Python
    def definir(self, itens: list[dict[str, Any]]) -> None:
        """Troca o conteúdo. Se nada mudou, não mexe no modelo (evita redesenhar a lista)."""
        itens = [dict(i) for i in itens]
        if itens == self._itens:
            return
        mudou_contagem = len(itens) != len(self._itens)
        if len(itens) == len(self._itens) and [i.get("id") for i in itens] == [i.get("id") for i in self._itens]:
            # mesmas linhas, valores diferentes: atualiza no lugar (mantém rolagem e seleção)
            self._itens = itens
            if itens:
                self.dataChanged.emit(self.index(0), self.index(len(itens) - 1))
            return
        self.beginResetModel()
        self._itens = itens
        self.endResetModel()
        if mudou_contagem:
            self.contagemMudou.emit()

    def itens(self) -> list[dict[str, Any]]:
        return [dict(i) for i in self._itens]

    # ------------------------------------------------------------------ Qt
    def rowCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._itens)

    def data(self, index: _ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._itens):
            return None
        papel = self._roles.get(role)
        return None if papel is None else self._itens[index.row()].get(papel)

    def roleNames(self) -> dict[int, QByteArray]:
        return {r: QByteArray(p.encode()) for r, p in self._roles.items()}

    def _contagem(self) -> int:
        return len(self._itens)

    contagem = Property(int, _contagem, notify=contagemMudou)

    @Slot(int, result="QVariantMap")
    def item(self, linha: int) -> dict:
        return dict(self._itens[linha]) if 0 <= linha < len(self._itens) else {}
