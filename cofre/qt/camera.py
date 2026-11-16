"""
Câmera em QThread, entregando à interface só o quadro mais recente.

Fluxo:
  thread da câmera:  lê o quadro -> roda o `processador(frame)` (parte cara: pipeline,
                     conversão para QImage) -> guarda o pacote e avisa por sinal
  thread da interface: recebe `quadroDisponivel`, pega o pacote com `ultimo()`

Se a interface atrasar, os quadros antigos são descartados (não há fila crescendo).
Cada abertura recebe um número de "geração"; avisos de uma thread antiga que ainda
esteja terminando são ignorados.

No macOS o dispositivo é criado na thread principal (`FonteCamera.preparar`): é a
única forma de o sistema mostrar o pedido de permissão da câmera.
"""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot

from .. import config
from ..fase1_aquisicao import ErroAquisicao, FonteCamera

DESLIGADA, ABRINDO, ATIVA, ERRO = "desligada", "abrindo", "ativa", "erro"


def fabrica_padrao() -> FonteCamera:
    """Lê índice e espelhamento de `config` a cada abertura (a tela de configurações pode mudar)."""
    return FonteCamera(config.CAMERA_INDEX, config.ESPELHAR_CAMERA)


@dataclass
class Pacote:
    frame: Any
    saida: Any
    seq: int
    fps: float


class _ThreadCaptura(QThread):
    def __init__(self, fonte, servico: "ServicoCamera", geracao: int):
        super().__init__()
        self.fonte, self.servico, self.geracao = fonte, servico, geracao
        self.setObjectName(f"camera-{geracao}")

    def run(self) -> None:
        s, g = self.servico, self.geracao
        try:
            with self.fonte as cam:
                s._sinalAberta.emit(g)
                for frame in cam.frames():
                    if self.isInterruptionRequested():
                        break
                    proc = s._processador
                    erro = ""
                    try:
                        saida = proc(frame) if proc is not None else None
                    except Exception as e:  # noqa: BLE001
                        traceback.print_exc()
                        saida, erro = None, f"Erro no processamento: {e}"
                    s._entregar(g, frame, saida, float(getattr(cam, "fps_medido", 0.0)), erro)
                    if self.isInterruptionRequested():
                        break
        except ErroAquisicao as e:
            s._sinalFalha.emit(g, str(e))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            s._sinalFalha.emit(g, f"Falha na câmera: {e}")
        finally:
            s._sinalEncerrada.emit(g)


class ServicoCamera(QObject):
    estadoMudou = Signal()
    erroMudou = Signal()
    fpsMudou = Signal()
    quadroDisponivel = Signal()
    erroProcessamento = Signal(str)

    # sinais internos emitidos pela thread de captura (entregues na thread da interface)
    _sinalAberta = Signal(int)
    _sinalFalha = Signal(int, str)
    _sinalEncerrada = Signal(int)

    def __init__(self, fonte_fabrica: Callable[[], Any] | None = None, parent=None):
        super().__init__(parent)
        self.fonte_fabrica: Callable[[], Any] = fonte_fabrica or fabrica_padrao
        self._estado = DESLIGADA
        self._erro = ""
        self._fps = 0.0
        self._processador: Callable[[Any], Any] | None = None
        self._thread: _ThreadCaptura | None = None
        self._encerrando: list[_ThreadCaptura] = []   # threads paradas que ainda não terminaram
        self._geracao = 0
        self._lock = threading.Lock()
        self._pacote: Pacote | None = None
        self._avisado = False
        self._seq = 0
        self._sinalAberta.connect(self._aberta)
        self._sinalFalha.connect(self._falha)
        self._sinalEncerrada.connect(self._encerrada)

    # ------------------------------------------------------------------ propriedades
    def _get_estado(self) -> str:
        return self._estado

    def _get_erro(self) -> str:
        return self._erro

    def _get_fps(self) -> float:
        return self._fps

    estado = Property(str, _get_estado, notify=estadoMudou)
    erro = Property(str, _get_erro, notify=erroMudou)
    fps = Property(float, _get_fps, notify=fpsMudou)

    @property
    def ativa(self) -> bool:
        return self._estado == ATIVA

    def _mudar_estado(self, estado: str, erro: str | None = None) -> None:
        if erro is not None and erro != self._erro:
            self._erro = erro
            self.erroMudou.emit()
        if estado != self._estado:
            self._estado = estado
            self.estadoMudou.emit()

    # ------------------------------------------------------------------ controle
    def iniciar(self, processador: Callable[[Any], Any] | None) -> None:
        """Abre a câmera (fechando a anterior) com o processador dado. Erros viram estado ERRO."""
        self.parar()
        self._processador = processador
        self._geracao += 1
        self._mudar_estado(ABRINDO, "")
        try:
            fonte = self.fonte_fabrica()
            if isinstance(fonte, FonteCamera):
                fonte.preparar()       # thread principal: permite o pedido de permissão no macOS
        except Exception as e:  # noqa: BLE001
            self._mudar_estado(ERRO, f"Falha na câmera: {e}")
            return
        self._thread = _ThreadCaptura(fonte, self, self._geracao)
        self._thread.start()

    def definir_processador(self, processador: Callable[[Any], Any] | None) -> None:
        self._processador = processador
        with self._lock:
            self._pacote = None

    def parar(self, espera_ms: int = 3000) -> None:
        t, self._thread = self._thread, None
        self._geracao += 1                 # avisos atrasados da thread antiga passam a ser ignorados
        if t is not None:
            t.requestInterruption()
            if not t.wait(espera_ms):
                self._encerrando.append(t)  # mantém a referência até terminar (evita destruir thread viva)
        with self._lock:
            self._pacote = None
            self._avisado = False
        if self._fps:
            self._fps = 0.0
            self.fpsMudou.emit()
        self._mudar_estado(DESLIGADA, "")

    def ultimo(self) -> Pacote | None:
        with self._lock:
            self._avisado = False
            return self._pacote

    # ------------------------------------------------------------------ vindo da thread de captura
    def _entregar(self, geracao: int, frame, saida, fps: float, erro: str) -> None:
        if geracao != self._geracao:
            return
        with self._lock:
            self._seq += 1
            self._pacote = Pacote(frame, saida, self._seq, fps)
            avisar = not self._avisado
            self._avisado = True
        if erro:
            self.erroProcessamento.emit(erro)
        if avisar:
            self.quadroDisponivel.emit()

    @Slot(int)
    def _aberta(self, geracao: int) -> None:
        if geracao == self._geracao:
            self._mudar_estado(ATIVA, "")

    @Slot(int, str)
    def _falha(self, geracao: int, erro: str) -> None:
        if geracao == self._geracao:
            self._thread = None
            self._mudar_estado(ERRO, erro)

    @Slot(int)
    def _encerrada(self, geracao: int) -> None:
        self._encerrando = [t for t in self._encerrando if t.isRunning()]
        if geracao == self._geracao and self._estado in (ABRINDO, ATIVA):
            # a fonte acabou sozinha (gerador terminou): trata como câmera desligada
            self._thread = None
            self._mudar_estado(DESLIGADA)

    def atualizar_fps(self, fps: float) -> None:
        fps = round(fps, 1)
        if abs(fps - self._fps) >= 0.5 or (fps == 0) != (self._fps == 0):
            self._fps = fps
            self.fpsMudou.emit()
