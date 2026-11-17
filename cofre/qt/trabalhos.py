"""Trabalho cancelável da v2, fora da thread da interface (QThreadPool próprio de 2 threads).

Cada ViewModel novo tem um `Trabalho` (ou mais de um). `executar(fn, ao_terminar)` roda `fn(sinal)`
numa thread do pool e chama `ao_terminar(resultado, erro)` de volta na thread da interface. O último
pedido vence: pedir de novo cancela o que está rodando e toma o lugar do que esperava a vez. O
cancelamento é cooperativo: `fn` chama `sinal.conferir()` a cada lote de no máximo ~100 ms e avisa
o andamento por `sinal.progresso(feito, total)`.

O pool antigo (`tarefas.py`) segue só com o que já fazia (carga dos modelos, exportações): a v2 não
disputa as duas vagas dele. Como lá, quem precisa do banco abre a própria conexão dentro de `fn`.
"""

from __future__ import annotations

import itertools
import threading
import time
import traceback
import weakref
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot

THREADS = 2
INTERVALO_PROGRESSO_SEG = 0.05          # no máximo ~20 avisos de progresso por segundo chegam à interface


class Cancelado(Exception):
    """Levantada por `Sinal.conferir()` dentro de um trabalho cancelado ou substituído."""


class Sinal:
    """Entregue a fn(sinal). Seguro para usar na thread de trabalho."""

    def __init__(self, avisar: Callable[[float], None] | None = None):
        self._cancelado = threading.Event()
        self._avisar = avisar
        self._ultimo_aviso = 0.0
        self._ultima_fracao = 0.0

    def cancelado(self) -> bool:
        return self._cancelado.is_set()

    def conferir(self) -> None:
        """Levanta `Cancelado` se o pedido foi cancelado: o trabalho para ali, sem resultado."""
        if self._cancelado.is_set():
            raise Cancelado()

    def progresso(self, feito: int, total: int) -> None:
        """Avisa o andamento (vira uma fração de 0 a 1). Pode ser chamado a cada item: só passam
        ~20 avisos por segundo, mais o aviso de conclusão (`feito == total`)."""
        if self._avisar is None or total <= 0 or self._cancelado.is_set():
            return
        fracao = min(1.0, max(0.0, feito / total))
        agora = time.monotonic()
        concluiu = fracao >= 1.0 > self._ultima_fracao
        if not concluiu and agora - self._ultimo_aviso < INTERVALO_PROGRESSO_SEG:
            return
        self._ultimo_aviso, self._ultima_fracao = agora, fracao
        self._avisar(fracao)

    def cancelar(self) -> None:
        """Marca o pedido como cancelado. Quem chama é o `Trabalho` (ou um teste de função de técnica)."""
        self._cancelado.set()


@dataclass(eq=False)
class _Pedido:
    ident: int
    fn: Callable[[Sinal], Any]
    ao_terminar: Callable[[Any, str], None]
    sinal: Sinal


class _Executavel(QRunnable):
    def __init__(self, trabalho: "Trabalho", pedido: _Pedido):
        super().__init__()
        self.trabalho, self.pedido = trabalho, pedido
        self.setAutoDelete(True)

    def run(self) -> None:  # roda em uma thread do pool
        pedido = self.pedido
        resultado, erro, cancelado = None, "", False
        try:
            pedido.sinal.conferir()                # cancelado antes de começar: nem roda
            resultado = pedido.fn(pedido.sinal)
        except Cancelado:
            cancelado = True
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            erro = str(e) or e.__class__.__name__
        try:
            self.trabalho._terminou.emit(resultado, erro, cancelado)
        except RuntimeError:                       # o Trabalho foi destruído com o pedido ainda rodando:
            self.trabalho._atual = self.trabalho._no_pool = None     # não há a quem entregar


class Trabalhos(QObject):
    """Pool da v2 (QThreadPool próprio, 2 threads). Um por aplicativo, em Extensoes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(THREADS)
        self._ids = itertools.count(1)
        self._trabalhos: weakref.WeakSet[Trabalho] = weakref.WeakSet()
        self._encerrado = False

    def cancelar_tudo(self) -> None:
        """Encerramento: cancela todos os pedidos e deixa de aceitar novos. Depois disto nenhum
        `ao_terminar` é chamado, nem dos pedidos em andamento nem de um `executar()` tardio (que é ignorado)."""
        self._encerrado = True
        for trabalho in list(self._trabalhos):
            try:
                trabalho.cancelar()
            except RuntimeError:
                pass                               # Trabalho de um ViewModel já destruído: já ficou cancelado

    def esperar(self, ms: int = 3000) -> bool:
        """Espera as threads do pool pararem, por até `ms`. Não gira o loop de eventos: nenhum
        `ao_terminar` roda aqui dentro (para esperar resultado, gire o loop até `ocioso()`)."""
        return self._pool.waitForDone(ms)

    def ocioso(self) -> bool:
        """Nenhum pedido em andamento em nenhum Trabalho. Um pedido conta desde `executar()` até
        o `ao_terminar` dele ter rodado na thread da interface, ou até ser cancelado ou substituído."""
        return not any(trabalho.ocupado for trabalho in list(self._trabalhos))


class Trabalho(QObject):
    """Uma atividade de um ViewModel: o último pedido vence.

    No máximo um pedido roda e um espera a vez. Pedir de novo cancela o que roda e toma o lugar do
    que esperava; resultado de pedido cancelado ou substituído é descartado sem `ao_terminar`.
    Todos os métodos são chamados na thread da interface."""

    progresso = Signal(float)                # 0..1, na thread da interface
    ocupadoMudou = Signal()

    # sinais internos emitidos pela thread do pool (entregues na thread da interface)
    _terminou = Signal(object, str, bool)    # (resultado, erro, cancelado)
    _avisou = Signal(int, float)             # (pedido, fração)

    def __init__(self, trabalhos: Trabalhos, parent=None):
        super().__init__(parent)
        self._trabalhos = trabalhos
        self._atual: _Pedido | None = None       # pedido válido: rodando ou esperando a vez
        self._no_pool: _Pedido | None = None     # pedido entregue ao pool (pode já estar cancelado)
        self._terminou.connect(self._ao_terminar_no_pool, Qt.ConnectionType.QueuedConnection)
        self._avisou.connect(self._ao_avisar, Qt.ConnectionType.QueuedConnection)
        trabalhos._trabalhos.add(self)

    @property
    def ocupado(self) -> bool:
        return self._atual is not None

    def executar(self, fn: Callable[[Sinal], Any], ao_terminar: Callable[[Any, str], None]) -> None:
        """Roda `fn(sinal)` no pool e chama `ao_terminar(resultado, erro)` na thread da interface
        (`erro == ""` é sucesso; exceção em `fn` vira o texto dela)."""
        if self._trabalhos._encerrado:
            return
        estava_ocupado = self._atual is not None
        if estava_ocupado:
            self._atual.sinal.cancelar()
        ident = next(self._trabalhos._ids)
        self._atual = _Pedido(ident, fn, ao_terminar, Sinal(lambda fracao: self._avisar(ident, fracao)))
        if self._no_pool is None:
            self._lancar()
        if not estava_ocupado:
            self.ocupadoMudou.emit()

    def cancelar(self) -> None:
        """Cancela o pedido em andamento, se houver: o `ao_terminar` dele não é chamado."""
        if self._atual is None:
            return
        self._atual.sinal.cancelar()
        self._atual = None
        self.ocupadoMudou.emit()

    def _lancar(self) -> None:
        self._no_pool = self._atual
        self._trabalhos._pool.start(_Executavel(self, self._atual))

    def _avisar(self, ident: int, fracao: float) -> None:  # roda em uma thread do pool
        try:
            self._avisou.emit(ident, fracao)
        except RuntimeError:
            pass                                   # o Trabalho foi destruído com o pedido ainda rodando

    @Slot(int, float)
    def _ao_avisar(self, ident: int, fracao: float) -> None:
        if self._atual is not None and self._atual.ident == ident:
            self.progresso.emit(fracao)

    @Slot(object, str, bool)
    def _ao_terminar_no_pool(self, resultado: Any, erro: str, cancelado: bool) -> None:
        pedido, self._no_pool = self._no_pool, None
        if pedido is not self._atual:
            if self._atual is not None:
                self._lancar()                     # o pedido que esperava a vez começa agora
            return
        if not cancelado:
            try:
                pedido.ao_terminar(resultado, erro)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        if self._atual is pedido:                  # o ao_terminar não pediu outro trabalho
            self._atual = None
            self.ocupadoMudou.emit()
