"""
FASE 1 - AQUISIÇÃO DA IMAGEM

Responsável por obter a imagem digital que entra no pipeline. Duas fontes:
  * `FonteCamera`  : captura em tempo real pela webcam (requisito do enunciado);
  * `FonteImagens` : leitura de arquivos (scanner/câmera externa/testes).

A saída de ambas é sempre um frame BGR (padrão do OpenCV) em `numpy.ndarray`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Iterator

import cv2
import numpy as np

from . import config

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class ErroAquisicao(RuntimeError):
    """Falha ao abrir a câmera ou ler o arquivo."""


class FonteCamera:
    """Captura frames da webcam. Uso como *context manager*:

        with FonteCamera() as cam:
            for frame in cam.frames():
                ...
    """

    def __init__(self, indice: int = config.CAMERA_INDEX, espelhar: bool = config.ESPELHAR_CAMERA):
        self.indice = indice
        self.espelhar = espelhar
        self._cap: cv2.VideoCapture | None = None
        self.fps_medido = 0.0

    def preparar(self) -> "FonteCamera":
        """Cria o dispositivo de captura sem ler frames.

        No macOS, a primeira abertura da câmera pede permissão ao sistema, e o OpenCV só
        consegue mostrar esse pedido se estiver na thread principal. Quem lê os frames em
        outra thread (o aplicativo desktop) chama `preparar()` antes, na thread principal."""
        if self._cap is None:
            self._cap = cv2.VideoCapture(self.indice)
        return self

    def abrir(self) -> "FonteCamera":
        cap = self._cap if self._cap is not None else cv2.VideoCapture(self.indice)
        self._cap = None
        if not cap.isOpened():
            cap.release()
            raise ErroAquisicao(
                f"Não foi possível abrir a câmera {self.indice}. No macOS, autorize o aplicativo que "
                "abriu o programa (Terminal, VS Code, Claude...) em Ajustes > Privacidade e Segurança > Câmera "
                "e abra o programa de novo."
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_LARGURA)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_ALTURA)
        # Primeiras leituras costumam vir pretas enquanto o sensor ajusta a exposição.
        inicio = time.time()
        while time.time() - inicio < 5.0:
            ok, frame = cap.read()
            if ok and frame is not None and frame.mean() > 2:
                break
            time.sleep(0.05)
        self._cap = cap
        return self

    def ler(self) -> np.ndarray:
        if self._cap is None:
            raise ErroAquisicao("Câmera não aberta. Chame abrir() ou use `with`.")
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise ErroAquisicao("Falha ao ler frame da câmera.")
        if self.espelhar:
            frame = cv2.flip(frame, 1)
        return frame

    def frames(self) -> Iterator[np.ndarray]:
        """Gerador infinito de frames (mede FPS no caminho)."""
        anterior = time.time()
        alpha = 0.1
        while True:
            frame = self.ler()
            agora = time.time()
            dt = agora - anterior
            anterior = agora
            if dt > 0:
                fps = 1.0 / dt
                self.fps_medido = fps if self.fps_medido == 0 else (1 - alpha) * self.fps_medido + alpha * fps
            yield frame

    def fechar(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "FonteCamera":
        return self.abrir()

    def __exit__(self, *exc) -> None:
        self.fechar()


def carregar_imagem(caminho: str | Path) -> np.ndarray:
    """Lê uma imagem do disco em BGR. Lança ErroAquisicao se não conseguir."""
    caminho = Path(caminho)
    img = cv2.imread(str(caminho), cv2.IMREAD_COLOR)
    if img is None:
        raise ErroAquisicao(f"Não foi possível ler a imagem: {caminho}")
    return img


def listar_imagens(pasta: str | Path) -> list[Path]:
    pasta = Path(pasta)
    return sorted(p for p in pasta.iterdir() if p.suffix.lower() in EXTENSOES_IMAGEM)


class FonteImagens:
    """Itera sobre arquivos de imagem como se fossem frames (útil em testes e demos)."""

    def __init__(self, caminhos: Iterable[str | Path]):
        self.caminhos = [Path(c) for c in caminhos]

    def frames(self) -> Iterator[tuple[Path, np.ndarray]]:
        for caminho in self.caminhos:
            yield caminho, carregar_imagem(caminho)
