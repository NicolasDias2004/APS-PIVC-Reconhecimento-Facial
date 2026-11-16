"""Cores, fontes e utilitários visuais do aplicativo."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

# Paleta (hex) - fundo escuro, acento verde-água institucional
FUNDO = "#0f1419"
FUNDO_2 = "#161c24"
CARTAO = "#1d2530"
BORDA = "#2a3440"
TEXTO = "#e6edf3"
TEXTO_2 = "#8b98a5"
ACENTO = "#2bb0a0"
ACENTO_HOVER = "#239184"
VERDE = "#2ecc71"
VERMELHO = "#e74c3c"
AMARELO = "#f1c40f"
LARANJA = "#f39c12"
AZUL = "#3498db"

FONTE = "Helvetica"
TITULO = (FONTE, 22, "bold")
SUBTITULO = (FONTE, 15, "bold")
CORPO = (FONTE, 13)
PEQUENO = (FONTE, 11)
MONO = ("Menlo", 12)

COR_RESULTADO = {
    "CONCEDIDO": VERDE,
    "NEGADO_NIVEL": LARANJA,
    "NEGADO_DESCONHECIDO": VERMELHO,
    "NEGADO_LIVENESS": VERMELHO,
    "NEGADO_MULTIPLOS": VERMELHO,
    "BLOQUEADO": VERMELHO,
}

ROTULO_RESULTADO = {
    "CONCEDIDO": "Acesso concedido",
    "NEGADO_NIVEL": "Negado: nível insuficiente",
    "NEGADO_DESCONHECIDO": "Negado: não cadastrado",
    "NEGADO_LIVENESS": "Negado: prova de vida",
    "NEGADO_MULTIPLOS": "Negado: mais de uma pessoa",
    "BLOQUEADO": "Terminal bloqueado",
}

COR_NIVEL = {1: AZUL, 2: LARANJA, 3: VERMELHO}


def bgr_para_pil(img: np.ndarray) -> Image.Image:
    """Converte um frame BGR/cinza do OpenCV em imagem PIL (RGB)."""
    if img.ndim == 2:
        return Image.fromarray(img)
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def ajustar(img: np.ndarray, largura: int, altura: int) -> np.ndarray:
    """Redimensiona mantendo a proporção para caber em largura x altura."""
    h, w = img.shape[:2]
    if w == 0 or h == 0 or largura <= 1 or altura <= 1:
        return img
    esc = min(largura / w, altura / h)
    return cv2.resize(img, (max(1, int(w * esc)), max(1, int(h * esc))),
                      interpolation=cv2.INTER_AREA if esc < 1 else cv2.INTER_LINEAR)
