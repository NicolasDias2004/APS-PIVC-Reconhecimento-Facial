"""Fase 4: sensibilidade do descritor por oclusão.

Uma janela da cor média do rosto percorre o rosto alinhado (112×112); para cada posição, o descritor
da imagem coberta é comparado com a referência (outra imagem da mesma pessoa). A queda de
similaridade mostra onde o descritor "olha". É só visualização: nada aqui entra no pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np

from .lote_sface import LoteSFace

LADO = 112

REGIOES: dict[str, tuple[int, int, int, int]] = {           # (x0, y0, x1, y1) no rosto alinhado 112x112
    "testa": (20, 6, 92, 34), "olho_direito": (20, 38, 54, 64), "olho_esquerdo": (58, 38, 92, 64),
    "nariz": (42, 56, 70, 84), "boca": (34, 80, 78, 104), "bochecha_direita": (6, 60, 36, 92),
    "bochecha_esquerda": (76, 60, 106, 92), "queixo": (36, 98, 76, 112)}

NOMES: dict[str, str] = {
    "testa": "Testa", "olho_direito": "Olho (à esquerda da imagem)", "olho_esquerdo": "Olho (à direita da imagem)",
    "nariz": "Nariz", "boca": "Boca", "bochecha_direita": "Bochecha (à esquerda da imagem)",
    "bochecha_esquerda": "Bochecha (à direita da imagem)", "queixo": "Queixo"}

_FRASE_REGIAO = {"testa": "da testa", "olho_direito": "dos olhos", "olho_esquerdo": "dos olhos", "nariz": "do nariz",
                 "boca": "da boca", "bochecha_direita": "das bochechas", "bochecha_esquerda": "das bochechas",
                 "queixo": "do queixo"}


@dataclass(frozen=True)
class MapaOclusao:
    queda: np.ndarray             # (G, G) float32, >= 0: similaridade base menos a similaridade com a janela coberta
    base: float
    janela: int
    passo: int
    aumentos: int                 # células em que cobrir AUMENTOU a similaridade (cortadas em zero)
    regioes: tuple[tuple[str, float], ...]   # (chave, queda média), decrescente
    frase: str


def _num(v: float, casas: int = 2) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def mapa_oclusao(alinhado: np.ndarray, referencia: np.ndarray, janela: int = 28, passo: int = 14,
                 sinal=None) -> MapaOclusao:
    """Queda de similaridade com a janela coberta em cada posição da grade."""
    if alinhado.shape[:2] != (LADO, LADO):
        raise ValueError("mapa_oclusao espera o rosto alinhado 112x112")
    ref = np.asarray(referencia, dtype=np.float32).reshape(-1)
    ref = ref / (float(np.linalg.norm(ref)) or 1.0)
    posicoes = list(range(0, LADO - janela + 1, passo))
    g = len(posicoes)
    media = np.rint(alinhado.reshape(-1, alinhado.shape[2]).mean(axis=0)).astype(np.uint8)
    copias = np.repeat(alinhado[None], g * g + 1, axis=0)           # a primeira fica limpa (base)
    k = 1
    for y in posicoes:
        for x in posicoes:
            copias[k, y:y + janela, x:x + janela] = media
            k += 1
    if sinal is not None:
        sinal.conferir()
    lote = LoteSFace.instancia()
    e, _ = lote.embeddings(list(copias), sinal=sinal)
    sims = e @ ref
    base = float(sims[0])
    bruta = (base - sims[1:]).reshape(g, g)
    aumentos = int((bruta < 0).sum())
    queda = np.maximum(bruta, 0).astype(np.float32)
    ampliado = np.maximum(cv2.resize(queda, (LADO, LADO), interpolation=cv2.INTER_CUBIC), 0)
    medias = {chave: float(ampliado[y0:y1, x0:x1].mean()) for chave, (x0, y0, x1, y1) in REGIOES.items()}
    regioes = tuple(sorted(medias.items(), key=lambda kv: -kv[1]))
    chave, valor = regioes[0]
    pico = float(queda.max()) if queda.size else 0.0
    frase = (f"A região que mais pesa é a {_FRASE_REGIAO[chave]}: cobrir derruba {_num(pico)} de {_num(base)}."
             if pico > 0 else "Cobrir partes do rosto não derrubou a similaridade nesta imagem.")
    return MapaOclusao(queda=queda, base=base, janela=janela, passo=passo, aumentos=aumentos, regioes=regioes, frase=frase)


def _cor_hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[4:6], 16), int(c[2:4], 16), int(c[0:2], 16)


def colorir(mapa: MapaOclusao, escala: Sequence[str], lado: int = 448) -> np.ndarray:
    """Mapa ampliado em BGRA uint8 (lado, lado, 4): cor pela rampa recebida e alfa proporcional ao valor."""
    rampa = np.array([_cor_hex(c) for c in escala], np.float32)
    v = np.maximum(cv2.resize(mapa.queda, (lado, lado), interpolation=cv2.INTER_CUBIC), 0)
    maior = float(v.max())
    f = v / maior if maior > 0 else np.zeros_like(v)
    indice = np.clip(np.floor(f * len(rampa)), 0, len(rampa) - 1).astype(np.int64)
    saida = np.zeros((lado, lado, 4), np.uint8)
    saida[..., :3] = rampa[indice].astype(np.uint8)
    saida[..., 3] = np.rint(f * 255).astype(np.uint8)
    return saida
