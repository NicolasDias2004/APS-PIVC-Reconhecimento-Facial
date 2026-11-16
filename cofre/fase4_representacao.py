"""
FASE 4 - REPRESENTAÇÃO E DESCRIÇÃO

Transforma o rosto segmentado em um descritor numérico compacto:

  * Principal: *embedding* de 128 dimensões gerado pela rede SFace
    (OpenCV FaceRecognizerSF). Rostos da mesma pessoa geram vetores próximos
    (alta similaridade do cosseno); de pessoas diferentes, vetores distantes.
  * Didático: descritor LBP (Local Binary Pattern) + histograma, técnica
    clássica de textura usada em reconhecimento facial antes das redes neurais.
    Serve para o painel didático e para comparação na dissertação.
"""

from __future__ import annotations

import threading

import cv2
import numpy as np

from . import config


class ExtratorCaracteristicas:
    """Encapsula o SFace: alinhamento (fase 3) e extração do embedding (fase 4)."""

    DIMENSAO = 128

    def __init__(self, modelo=config.MODELO_RECONHECIMENTO):
        if not modelo.exists():
            raise FileNotFoundError(f"Modelo de reconhecimento não encontrado: {modelo}")
        self._sf = cv2.FaceRecognizerSF.create(str(modelo), "")
        self._lock = threading.Lock()  # a rede não aceita duas inferências ao mesmo tempo

    @property
    def sface(self):
        return self._sf

    def alinhar(self, img: np.ndarray, rosto) -> np.ndarray:
        return self._sf.alignCrop(img, rosto.bruto)

    def extrair(self, rosto_alinhado: np.ndarray) -> np.ndarray:
        """Embedding L2-normalizado (float32, shape (128,))."""
        with self._lock:
            feat = self._sf.feature(rosto_alinhado)
        feat = feat.astype(np.float32).reshape(-1)
        norma = np.linalg.norm(feat)
        return feat / norma if norma > 0 else feat

    def extrair_de_frame(self, img: np.ndarray, rosto) -> np.ndarray:
        return self.extrair(self.alinhar(img, rosto))


def similaridade_cosseno(a: np.ndarray, b: np.ndarray) -> float:
    """Para vetores normalizados, o cosseno é apenas o produto interno."""
    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def lbp_mapa(cinza: np.ndarray) -> np.ndarray:
    """LBP 3x3 básico, vetorizado em NumPy. Cada pixel vira um código de 8 bits
    comparando-o com os 8 vizinhos (1 se vizinho >= centro)."""
    img = cinza.astype(np.int16)
    centro = img[1:-1, 1:-1]
    vizinhos = [
        img[:-2, :-2], img[:-2, 1:-1], img[:-2, 2:],
        img[1:-1, 2:], img[2:, 2:], img[2:, 1:-1],
        img[2:, :-2], img[1:-1, :-2],
    ]
    codigo = np.zeros_like(centro, dtype=np.uint8)
    for bit, viz in enumerate(vizinhos):
        codigo |= ((viz >= centro).astype(np.uint8) << bit)
    return codigo


def lbp_histograma(cinza: np.ndarray, grade: tuple[int, int] = (4, 4)) -> np.ndarray:
    """Histograma LBP concatenado por blocos (grade x grade), normalizado."""
    mapa = lbp_mapa(cinza)
    h, w = mapa.shape
    gh, gw = grade
    hist = []
    for i in range(gh):
        for j in range(gw):
            bloco = mapa[i * h // gh:(i + 1) * h // gh, j * w // gw:(j + 1) * w // gw]
            hb, _ = np.histogram(bloco, bins=256, range=(0, 256))
            hist.append(hb)
    vetor = np.concatenate(hist).astype(np.float32)
    s = vetor.sum()
    return vetor / s if s > 0 else vetor
