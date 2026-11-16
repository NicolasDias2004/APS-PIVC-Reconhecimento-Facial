"""
FASE 3 - SEGMENTAÇÃO

Separa a região de interesse (o rosto) do restante da cena:

  * Detecção com a rede YuNet (OpenCV FaceDetectorYN): devolve caixa delimitadora,
    5 pontos de referência (olhos, nariz, cantos da boca) e confiança.
  * Recorte + alinhamento geométrico: uma transformação afim leva os pontos de
    referência a posições canônicas em uma imagem 112x112, para que todos os
    rostos entrem na fase 4 com a mesma pose/escala.
  * Estimativa simples de pose (yaw) a partir dos pontos, usada no anti-fraude.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass

import cv2
import numpy as np

from . import config


@dataclass
class Rosto:
    """Um rosto detectado no frame (coordenadas no frame onde foi detectado)."""

    x: int
    y: int
    w: int
    h: int
    olho_dir: tuple[float, float]
    olho_esq: tuple[float, float]
    nariz: tuple[float, float]
    boca_dir: tuple[float, float]
    boca_esq: tuple[float, float]
    confianca: float
    bruto: np.ndarray  # linha original do YuNet (necessária para alignCrop)

    @property
    def caixa(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.w, self.h

    @property
    def area(self) -> int:
        return self.w * self.h

    @property
    def centro(self) -> tuple[float, float]:
        return self.x + self.w / 2, self.y + self.h / 2

    def escalar(self, fator: float) -> "Rosto":
        """Converte as coordenadas para outra escala (ex.: frame reduzido -> original)."""
        bruto = self.bruto.copy()
        bruto[:14] *= fator
        return rosto_de_linha(bruto)

    def yaw(self) -> float:
        """Razão horizontal nariz/olhos. ~0 = frontal, negativo = virado para a
        esquerda da imagem, positivo = para a direita. Independe da escala."""
        meio_x = (self.olho_dir[0] + self.olho_esq[0]) / 2
        dist_olhos = abs(self.olho_esq[0] - self.olho_dir[0]) or 1.0
        return (self.nariz[0] - meio_x) / dist_olhos

    def roll(self) -> float:
        """Inclinação da linha dos olhos, em graus. ~0 = cabeça reta."""
        return math.degrees(math.atan2(self.olho_esq[1] - self.olho_dir[1], self.olho_esq[0] - self.olho_dir[0]))

    def razao_nariz(self) -> float:
        """Posição vertical do nariz entre os olhos (0) e a boca (1). De frente fica em ~0,5-0,6;
        cabeça baixa empurra o nariz para a boca (sobe), cabeça erguida afasta (desce)."""
        olhos_y = (self.olho_dir[1] + self.olho_esq[1]) / 2
        boca_y = (self.boca_dir[1] + self.boca_esq[1]) / 2
        return (self.nariz[1] - olhos_y) / ((boca_y - olhos_y) or 1.0)

    def problema_pose(self) -> str:
        """'' se a pose serve para autenticar; senão, a instrução para a pessoa (lê `config` na hora)."""
        if abs(self.yaw()) > config.POSE_MAX_YAW:
            return "Vire o rosto para a câmera"
        if abs(self.roll()) > config.POSE_MAX_ROLL_GRAUS:
            return "Endireite a cabeça"
        razao = self.razao_nariz()
        if razao > config.POSE_RAZAO_NARIZ_MAX:
            return "Levante a cabeça e olhe para a câmera"
        if razao < config.POSE_RAZAO_NARIZ_MIN:
            return "Abaixe o queixo e olhe para a câmera"
        return ""


def rosto_de_linha(linha: np.ndarray) -> Rosto:
    l = linha.astype(np.float32)
    return Rosto(
        x=int(l[0]), y=int(l[1]), w=int(l[2]), h=int(l[3]),
        olho_dir=(float(l[4]), float(l[5])),
        olho_esq=(float(l[6]), float(l[7])),
        nariz=(float(l[8]), float(l[9])),
        boca_dir=(float(l[10]), float(l[11])),
        boca_esq=(float(l[12]), float(l[13])),
        confianca=float(l[14]),
        bruto=l,
    )


class DetectorFacial:
    """Encapsula o YuNet. A rede do OpenCV não aceita duas inferências ao mesmo tempo, então
    `detectar` usa um lock: o aplicativo desktop processa a câmera em uma thread e, ao mesmo
    tempo, pode processar fotos (cadastro por arquivo, demonstração) em outra."""

    def __init__(self, modelo=config.MODELO_DETECCAO, score_min=config.DETECCAO_SCORE_MIN):
        if not modelo.exists():
            raise FileNotFoundError(f"Modelo de detecção não encontrado: {modelo}")
        self._det = cv2.FaceDetectorYN.create(
            str(modelo), "", (320, 320), score_min, config.DETECCAO_NMS, config.DETECCAO_TOP_K
        )
        self._tamanho = (320, 320)
        self._lock = threading.Lock()

    def detectar(self, img_bgr: np.ndarray, tamanho_min: int = config.TAMANHO_MIN_ROSTO) -> list[Rosto]:
        h, w = img_bgr.shape[:2]
        with self._lock:  # o tamanho de entrada e a inferência precisam ficar juntos
            if (w, h) != self._tamanho:
                self._det.setInputSize((w, h))
                self._tamanho = (w, h)
            _, faces = self._det.detect(img_bgr)
        if faces is None:
            return []
        rostos = [rosto_de_linha(f) for f in faces]
        rostos = [r for r in rostos if min(r.w, r.h) >= tamanho_min]
        # maior rosto primeiro (mais próximo da câmera)
        rostos.sort(key=lambda r: r.area, reverse=True)
        return rostos


def recortar(img: np.ndarray, rosto: Rosto, margem: float = 0.15) -> np.ndarray:
    """Recorte simples (sem alinhamento) com margem, para salvar fotos e evidências."""
    h, w = img.shape[:2]
    mx, my = int(rosto.w * margem), int(rosto.h * margem)
    x0, y0 = max(0, rosto.x - mx), max(0, rosto.y - my)
    x1, y1 = min(w, rosto.x + rosto.w + mx), min(h, rosto.y + rosto.h + my)
    return img[y0:y1, x0:x1].copy()


def alinhar(img: np.ndarray, rosto: Rosto, reconhecedor_sf) -> np.ndarray:
    """Recorte alinhado 112x112 via transformação afim pelos 5 pontos (SFace.alignCrop)."""
    return reconhecedor_sf.alignCrop(img, rosto.bruto)


def desenhar_pontos(img: np.ndarray, rosto: Rosto) -> np.ndarray:
    saida = img.copy()
    for p in (rosto.olho_dir, rosto.olho_esq, rosto.nariz, rosto.boca_dir, rosto.boca_esq):
        cv2.circle(saida, (int(p[0]), int(p[1])), 3, (0, 255, 255), -1)
    return saida
