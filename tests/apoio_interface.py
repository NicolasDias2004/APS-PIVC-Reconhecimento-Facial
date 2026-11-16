"""Apoio para testar o aplicativo desktop sem webcam e sem interação humana.

    from tests.apoio_interface import criar_app, FonteFalsa, girar
    app = criar_app(tmp_path / "t.db", imagens=[...])   # câmera falsa com as fotos dadas
    app.mostrar("tela_terminal"); girar(app, 1.0)       # roda o loop do Tk por 1 s
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2

FIX = Path(__file__).resolve().parent / "fixtures" / "pessoas"
FOTO_OBAMA = FIX / "obama" / "obama_2012.jpg"
FOTO_OBAMA_2 = FIX / "obama" / "obama_2009.jpg"
FOTO_BIDEN = FIX / "biden" / "biden_2021.jpg"
FOTO_BIDEN_2 = FIX / "biden" / "biden_2013.jpg"


class FonteFalsa:
    """Substitui `FonteCamera`: repete as imagens dadas como se fossem frames (~30 fps)."""

    fps_medido = 30.0

    def __init__(self, imagens, intervalo=1 / 30):
        self.imagens = [cv2.imread(str(c)) if isinstance(c, (str, Path)) else c for c in imagens]
        self.intervalo = intervalo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def frames(self):
        while True:
            for im in self.imagens:
                time.sleep(self.intervalo)
                yield im.copy()


class SemCamera:
    """Fonte que falha como uma câmera ausente (para testes que não passam imagens)."""

    fps_medido = 0.0

    def __enter__(self):
        from cofre.fase1_aquisicao import ErroAquisicao
        raise ErroAquisicao("Sem câmera (teste)")

    def __exit__(self, *exc):
        return False


def criar_app(caminho_db, imagens=None, esperar_pipeline=True):
    """Cria o App com banco temporário e câmera falsa; espera os modelos carregarem.
    A webcam real nunca é aberta: sem `imagens`, a câmera se comporta como ausente."""
    from cofre.interface.app import App
    fonte = (lambda: FonteFalsa(imagens)) if imagens is not None else SemCamera
    app = App(caminho_db, fonte_camera=fonte)
    app.update()
    if esperar_pipeline:
        inicio = time.time()
        while app.pipeline is None and time.time() - inicio < 20:
            app.update()
            time.sleep(0.02)
        assert app.pipeline is not None, app._erro_pipeline
    return app


def girar(app, segundos: float) -> None:
    """Processa eventos do Tk por `segundos` (equivalente a deixar o mainloop rodar)."""
    fim = time.time() + segundos
    while time.time() < fim:
        app.update()
        time.sleep(0.01)
