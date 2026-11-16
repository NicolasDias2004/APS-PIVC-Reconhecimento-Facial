"""Apoio para testar o aplicativo Qt Quick sem tela, sem webcam e sem interação humana.

Roda com a plataforma `offscreen` e o renderizador por software, com banco e pastas temporários.
A webcam real nunca é aberta: a câmera é a `FonteFalsa` (fotos do repositório) ou `SemCamera`.
"""

from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QEventLoop  # noqa: E402

from tests.apoio_interface import FonteFalsa, SemCamera  # noqa: E402,F401

# avisos que não vêm do nosso QML (fonte ausente no modo offscreen)
_AVISOS_IGNORADOS = ("Sans Serif", "propagateSizeHints")


class Contexto:
    """Aplicacao + motor QML + janela, com utilidades para girar o loop de eventos."""

    def __init__(self, qapp, aplicacao, motor, avisos):
        self.qapp = qapp
        self.apl = aplicacao
        self.motor = motor
        self.avisos = avisos
        self.janela = motor.rootObjects()[0] if motor.rootObjects() else None

    def girar(self, segundos: float) -> None:
        fim = time.time() + segundos
        while time.time() < fim:
            self.qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            time.sleep(0.005)

    def esperar(self, condicao, segundos: float = 15.0) -> bool:
        fim = time.time() + segundos
        while time.time() < fim:
            if condicao():
                return True
            self.girar(0.05)
        return bool(condicao())

    def avisos_qml(self) -> list[str]:
        return [a for a in self.avisos if not any(i in a for i in _AVISOS_IGNORADOS)]

    def fechar(self) -> None:
        from cofre.qt.app import destruir_motor
        self.apl.fechar()
        self.girar(0.05)
        self.janela = None
        destruir_motor(self.motor)
        self.motor = None
        self.girar(0.05)


def criar_contexto(qapp, caminho_db, pipeline=None, imagens=None) -> Contexto:
    """Cria a Aplicacao com câmera falsa e carrega o Main.qml. Com `pipeline`, reaproveita o da
    sessão de testes em vez de carregar os modelos de novo."""
    from cofre.qt.aplicacao import Aplicacao
    from cofre.qt.app import criar_motor
    fonte = (lambda: FonteFalsa(imagens)) if imagens is not None else SemCamera
    apl = Aplicacao(str(caminho_db), fonte_camera=fonte, carregar_modelos=pipeline is None)
    avisos: list[str] = []
    motor = criar_motor(apl, avisos)
    ctx = Contexto(qapp, apl, motor, avisos)
    if pipeline is not None:
        apl.usar_pipeline(pipeline)
    else:
        assert ctx.esperar(lambda: apl.pipeline is not None, 30), apl.erroModelos
    ctx.girar(0.1)
    return ctx
