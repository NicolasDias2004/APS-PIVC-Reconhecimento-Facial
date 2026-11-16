"""
Serviço de câmera em thread separada.

A thread captura frames, roda um `processador(frame) -> resultado` (normalmente o
pipeline + a lógica da tela) e guarda só o último resultado. A interface, na thread
principal do Tk, chama `ultimo()` periodicamente. Tk não é thread-safe, por isso a
thread nunca toca em widgets.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from ..fase1_aquisicao import ErroAquisicao, FonteCamera


class ServicoCamera:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._lock = threading.Lock()
        self._ultimo: Any = None
        self._processador: Callable[[Any], Any] | None = None
        self.erro: str | None = None
        self.fps = 0.0
        self.ativo = False
        # Fábrica da fonte de vídeo: trocável por uma fonte falsa nos testes
        # (qualquer context manager com `.frames()` e `.fps_medido`).
        self.fonte_fabrica: Callable[[], Any] = FonteCamera

    def definir_processador(self, fn: Callable[[Any], Any] | None) -> None:
        with self._lock:
            self._processador = fn
            self._ultimo = None

    def iniciar(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._parar.clear()
        self.erro = None
        try:
            fonte = self.fonte_fabrica()
            if isinstance(fonte, FonteCamera):
                fonte.preparar()  # thread principal: no macOS é o que permite o pedido de permissão
        except Exception as e:  # noqa: BLE001
            self.erro = f"Falha na câmera: {e}"
            return
        self._thread = threading.Thread(target=self._loop, args=(fonte,), name="camera", daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self._thread = None
        self.ativo = False
        with self._lock:
            self._ultimo = None

    def ultimo(self) -> Any:
        with self._lock:
            return self._ultimo

    def _loop(self, fonte) -> None:
        try:
            with fonte as cam:
                self.ativo = True
                for frame in cam.frames():
                    if self._parar.is_set():
                        break
                    with self._lock:
                        fn = self._processador
                    try:
                        saida = fn(frame) if fn is not None else frame
                    except Exception as e:  # noqa: BLE001
                        self.erro = f"Erro no processamento: {e}"
                        saida = frame
                    self.fps = cam.fps_medido
                    with self._lock:
                        self._ultimo = saida
                    time.sleep(0.001)
        except ErroAquisicao as e:
            self.erro = str(e)
        except Exception as e:  # noqa: BLE001
            self.erro = f"Falha na câmera: {e}"
        finally:
            self.ativo = False
