"""Trabalho pesado fora da thread da interface (QThreadPool), com resposta por sinal.

O `Banco` usa uma conexão SQLite presa à thread que a criou; tarefas que precisam do
banco abrem a própria conexão (`Banco(caminho)`) dentro da função executada.
"""

from __future__ import annotations

import itertools
import traceback
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, QRunnable, QThreadPool, Signal, Slot


class _Sinais(QObject):
    terminou = Signal(int, object, str)


class _Executavel(QRunnable):
    def __init__(self, ident: int, fn: Callable[[], Any], sinais: _Sinais):
        super().__init__()
        self.ident, self.fn, self.sinais = ident, fn, sinais
        self.setAutoDelete(True)

    def run(self) -> None:  # roda em uma thread do pool
        try:
            resultado, erro = self.fn(), ""
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            resultado, erro = None, (str(e) or e.__class__.__name__)
        self.sinais.terminou.emit(self.ident, resultado, erro)


class Tarefas(QObject):
    """Executa funções em segundo plano e chama `ao_terminar(resultado, erro)` na thread da interface."""

    ocupadaMudou = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self._sinais = _Sinais(self)
        self._sinais.terminou.connect(self._terminou)
        self._callbacks: dict[int, Callable[[Any, str], None]] = {}
        self._ids = itertools.count(1)

    def executar(self, fn: Callable[[], Any], ao_terminar: Callable[[Any, str], None]) -> int:
        ident = next(self._ids)
        self._callbacks[ident] = ao_terminar
        self._pool.start(_Executavel(ident, fn, self._sinais))
        self.ocupadaMudou.emit()
        return ident

    @Slot(int, object, str)
    def _terminou(self, ident: int, resultado: Any, erro: str) -> None:
        cb = self._callbacks.pop(ident, None)
        self.ocupadaMudou.emit()
        if cb is None:
            return
        try:
            cb(resultado, erro)
        except Exception:  # noqa: BLE001
            traceback.print_exc()

    def esperar(self, ms: int = 5000) -> bool:
        return self._pool.waitForDone(ms)

    def _ocupada(self) -> bool:
        return bool(self._callbacks)

    ocupada = Property(bool, _ocupada, notify=ocupadaMudou)
