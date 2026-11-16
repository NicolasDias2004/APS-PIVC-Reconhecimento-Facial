"""
FASE 2 - PRÉ-PROCESSAMENTO

Melhora a imagem adquirida antes da análise, reduzindo a influência de
iluminação, ruído e resolução no resultado do reconhecimento:

  1. redimensionamento  -> frame menor acelera a detecção;
  2. conversão para escala de cinza -> usada nas métricas de qualidade e no LBP;
  3. suavização gaussiana -> reduz ruído de sensor;
  4. equalização adaptativa de histograma (CLAHE) no canal de luminância (LAB)
     -> corrige contraste/iluminação sem distorcer as cores que o detector usa;
  5. métricas de qualidade (nitidez, brilho) -> rejeitam frames ruins no cadastro.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from . import config


@dataclass
class ResultadoPreprocessamento:
    """Guarda todas as imagens intermediárias (usadas no modo didático)."""

    original: np.ndarray
    reduzida: np.ndarray
    cinza: np.ndarray
    suavizada: np.ndarray
    equalizada: np.ndarray        # BGR, com CLAHE aplicado no canal L
    escala: float                 # fator original -> reduzida
    etapas: dict[str, np.ndarray] = field(default_factory=dict)


def redimensionar(img: np.ndarray, largura: int = config.LARGURA_PROCESSAMENTO) -> tuple[np.ndarray, float]:
    """Reduz a imagem para `largura` px mantendo a proporção. Retorna (imagem, escala)."""
    h, w = img.shape[:2]
    if w <= largura:
        return img.copy(), 1.0
    escala = largura / w
    nova = cv2.resize(img, (largura, int(round(h * escala))), interpolation=cv2.INTER_AREA)
    return nova, escala


def converter_cinza(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def suavizar(img: np.ndarray, kernel: tuple[int, int] = config.GAUSS_KERNEL) -> np.ndarray:
    return cv2.GaussianBlur(img, kernel, 0)


def equalizar_clahe(img_bgr: np.ndarray, clip: float = config.CLAHE_CLIP, grade=config.CLAHE_GRADE) -> np.ndarray:
    """CLAHE aplicado apenas na luminância (espaço LAB). Mantém a imagem colorida."""
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=grade)
    l_eq = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l_eq, a, b)), cv2.COLOR_LAB2BGR)


def equalizar_cinza(img_cinza: np.ndarray) -> np.ndarray:
    """Equalização global clássica (para comparação didática com o CLAHE)."""
    return cv2.equalizeHist(img_cinza)


def medir_nitidez(img: np.ndarray) -> float:
    """Variância do Laplaciano: quanto maior, mais bordas = imagem mais nítida."""
    return float(cv2.Laplacian(converter_cinza(img), cv2.CV_64F).var())


def medir_brilho(img: np.ndarray) -> float:
    return float(converter_cinza(img).mean())


@dataclass
class Qualidade:
    nitidez: float
    brilho: float

    @property
    def aprovada(self) -> bool:
        return (
            self.nitidez >= config.MIN_NITIDEZ
            and config.MIN_BRILHO <= self.brilho <= config.MAX_BRILHO
        )

    @property
    def motivo(self) -> str:
        if self.nitidez < config.MIN_NITIDEZ:
            return "imagem borrada"
        if self.brilho < config.MIN_BRILHO:
            return "muito escura"
        if self.brilho > config.MAX_BRILHO:
            return "muito clara"
        return "ok"


def avaliar_qualidade(recorte: np.ndarray) -> Qualidade:
    return Qualidade(nitidez=medir_nitidez(recorte), brilho=medir_brilho(recorte))


def preprocessar(frame: np.ndarray) -> ResultadoPreprocessamento:
    """Executa a fase 2 completa e devolve as imagens intermediárias."""
    reduzida, escala = redimensionar(frame)
    cinza = converter_cinza(reduzida)
    suavizada = suavizar(reduzida)
    equalizada = equalizar_clahe(suavizada)
    res = ResultadoPreprocessamento(
        original=frame,
        reduzida=reduzida,
        cinza=cinza,
        suavizada=suavizada,
        equalizada=equalizada,
        escala=escala,
    )
    res.etapas = {
        "1 original": frame,
        "2 reduzida": reduzida,
        "2 cinza": cinza,
        "2 suavizada": suavizada,
        "2 CLAHE": equalizada,
    }
    return res
