"""Desenho da interface sobre o vídeo (HUD) e painel didático das fases."""

from __future__ import annotations

import unicodedata

import cv2
import numpy as np

# Cores BGR
VERDE = (60, 200, 60)
VERMELHO = (40, 40, 230)
AMARELO = (30, 200, 240)
AZUL = (230, 150, 40)
BRANCO = (255, 255, 255)
PRETO = (0, 0, 0)
CINZA = (90, 90, 90)
LARANJA = (0, 140, 255)

FONTE = cv2.FONT_HERSHEY_SIMPLEX


def sem_acentos(texto: str) -> str:
    """As fontes Hershey do OpenCV não desenham acentos; removemos antes de exibir."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def texto(img, msg: str, pos, escala=0.6, cor=BRANCO, espessura=2, fundo=None, margem=4):
    msg = sem_acentos(msg)
    (tw, th), base = cv2.getTextSize(msg, FONTE, escala, espessura)
    x, y = int(pos[0]), int(pos[1])
    if fundo is not None:
        cv2.rectangle(img, (x - margem, y - th - margem), (x + tw + margem, y + base + margem), fundo, -1)
    cv2.putText(img, msg, (x, y), FONTE, escala, cor, espessura, cv2.LINE_AA)
    return th + base + 2 * margem


def caixa_rosto(img, rosto, cor, rotulo: str | None = None, espessura=2):
    x, y, w, h = rosto.caixa
    cv2.rectangle(img, (x, y), (x + w, y + h), cor, espessura)
    # cantos destacados
    c = max(8, w // 8)
    for (px, py, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        cv2.line(img, (px, py), (px + dx * c, py), cor, espessura + 2)
        cv2.line(img, (px, py), (px, py + dy * c), cor, espessura + 2)
    if rotulo:
        texto(img, rotulo, (x, max(20, y - 8)), 0.6, BRANCO, 2, fundo=cor)


def pontos_faciais(img, rosto, cor=AMARELO):
    for p in (rosto.olho_dir, rosto.olho_esq, rosto.nariz, rosto.boca_dir, rosto.boca_esq):
        cv2.circle(img, (int(p[0]), int(p[1])), 3, cor, -1, cv2.LINE_AA)


def barra_similaridade(img, pos, largura, valor: float, limiar: float):
    """Barra horizontal 0..1 com marcação do limiar."""
    x, y = pos
    h = 14
    cv2.rectangle(img, (x, y), (x + largura, y + h), CINZA, -1)
    v = int(max(0.0, min(1.0, valor)) * largura)
    cv2.rectangle(img, (x, y), (x + v, y + h), VERDE if valor >= limiar else VERMELHO, -1)
    lx = x + int(limiar * largura)
    cv2.line(img, (lx, y - 3), (lx, y + h + 3), BRANCO, 2)
    texto(img, f"{valor:.2f}", (x + largura + 8, y + h - 1), 0.5, BRANCO, 1)


def painel_topo(img, linhas: list[tuple[str, tuple]], altura=None):
    """Faixa escura semitransparente no topo com linhas de texto (msg, cor)."""
    h = altura or (22 * len(linhas) + 16)
    sobre = img.copy()
    cv2.rectangle(sobre, (0, 0), (img.shape[1], h), PRETO, -1)
    cv2.addWeighted(sobre, 0.55, img, 0.45, 0, img)
    y = 24
    for msg, cor in linhas:
        texto(img, msg, (12, y), 0.6, cor, 2)
        y += 22


def faixa_resultado(img, msg: str, cor):
    """Faixa grande no rodapé para o veredito (concedido/negado)."""
    h, w = img.shape[:2]
    sobre = img.copy()
    cv2.rectangle(sobre, (0, h - 70), (w, h), cor, -1)
    cv2.addWeighted(sobre, 0.8, img, 0.2, 0, img)
    texto(img, msg, (16, h - 26), 0.9, BRANCO, 2)


def rodape(img, msg: str):
    h, w = img.shape[:2]
    texto(img, msg, (12, h - 10), 0.5, BRANCO, 1, fundo=PRETO)


def _para_bgr(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img


def mosaico(etapas: dict[str, np.ndarray], lado: int = 220, colunas: int = 4) -> np.ndarray:
    """Monta um painel com miniaturas rotuladas de cada etapa do pipeline."""
    blocos = []
    for nome, img in etapas.items():
        img = _para_bgr(img)
        h, w = img.shape[:2]
        esc = lado / max(h, w)
        mini = cv2.resize(img, (max(1, int(w * esc)), max(1, int(h * esc))))
        tela = np.full((lado + 28, lado, 3), 30, np.uint8)
        oy, ox = (lado - mini.shape[0]) // 2, (lado - mini.shape[1]) // 2
        tela[oy:oy + mini.shape[0], ox:ox + mini.shape[1]] = mini
        texto(tela, nome, (6, lado + 20), 0.5, BRANCO, 1)
        blocos.append(tela)
    if not blocos:
        return np.zeros((lado, lado, 3), np.uint8)
    while len(blocos) % colunas:
        blocos.append(np.full_like(blocos[0], 30))
    linhas = [np.hstack(blocos[i:i + colunas]) for i in range(0, len(blocos), colunas)]
    return np.vstack(linhas)
