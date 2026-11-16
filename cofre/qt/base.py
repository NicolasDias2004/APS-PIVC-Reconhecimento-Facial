"""Apoio aos ViewModels: propriedades observáveis pelo QML sem repetição de código.

Cada ViewModel guarda o estado em `self._v` e declara, no corpo da classe:

    estadoMudou = Signal()
    estado = prop(str, "estado", estadoMudou)

`self._definir("estado", valor)` só emite o sinal quando o valor muda de fato, o que
evita reavaliar bindings do QML a cada quadro da câmera sem necessidade.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal


def objeto(atributo: str) -> Property:
    """Expõe ao QML um objeto Python guardado em `self.<atributo>` (modelos, fontes de vídeo)."""
    return Property(QObject, lambda self: getattr(self, atributo), constant=True)


def prop(tipo: Any, nome: str, sinal: Signal) -> Property:
    """Propriedade somente leitura do QML ligada a `self._v[nome]`."""
    return Property(tipo, lambda self: self._v[nome], notify=sinal)


class ViewModel(QObject):
    """Base: estado em dicionário, emissão só quando muda e ganchos de ativação de página."""

    def __init__(self, aplicacao=None, parent: QObject | None = None):
        super().__init__(parent)
        self.app = aplicacao
        self._v: dict[str, Any] = {}

    def _definir(self, nome: str, valor: Any) -> bool:
        if nome in self._v and self._v[nome] == valor:
            return False
        self._v[nome] = valor
        getattr(self, nome + "Mudou").emit()
        return True

    def _iniciar(self, **valores: Any) -> None:
        self._v.update(valores)

    # Ganchos chamados pela Aplicacao quando a página aparece / some / os modelos carregam.
    def ativar(self) -> None:
        pass

    def desativar(self) -> None:
        pass

    def ao_pipeline_pronto(self) -> None:
        pass

    def ao_banco_alterado(self) -> None:
        """Outro ponto do aplicativo (ou outro processo) gravou no banco."""
