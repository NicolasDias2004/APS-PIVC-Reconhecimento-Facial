"""Fases 2 a 4: medidas informativas de qualidade do rosto.

Oito componentes, cada um com a medida física (`brutos`) e uma nota de 0 a 1 em que 1 é o melhor
(`componentes`), mais um índice composto de 0 a 100 (`indice`):

    nitidez    variância do Laplaciano do rosto alinhado (fase 2)
    exposicao  distância do brilho médio ao meio da escala (fase 2)
    ruido      desvio do ruído estimado pelo método de Immerkaer (fase 2)
    simetria   diferença de brilho entre as metades esquerda e direita (fase 2)
    pose       giro e inclinação da cabeça em relação ao máximo que o terminal aceita (fase 3)
    resolucao  distância entre os olhos, em pixels do quadro original (fase 3)
    confianca  confiança do detector de rostos (fase 3)
    norma      norma da saída crua da rede SFace, antes da normalização (fase 4)

São medidas para exibir e estudar. Não são critério de autorização nem de cadastro: o terminal e o
cadastro continuam usando só `fase2_preprocessamento.avaliar_qualidade` e a checagem de pose do núcleo.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from . import config
from . import fase2_preprocessamento as f2

COMPONENTES = ("nitidez", "exposicao", "ruido", "simetria", "pose", "resolucao", "confianca", "norma")

NITIDEZ_PLENA = 600.0           # variância do Laplaciano que já vale nota 1
RUIDO_MAXIMO = 30.0             # desvio do ruído (níveis de cinza) que vale nota 0
OLHOS_PLENO = 90.0              # distância entre os olhos (px) que já vale nota 1
NORMA_MINIMA, NORMA_FAIXA = 6.0, 7.0    # a norma crua vai de nota 0 (6) a nota 1 (13)

_NUCLEO_IMMERKAER = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float32)


def _limitar(v: float) -> float:
    return float(min(1.0, max(0.0, v)))


def _ruido_immerkaer(cinza: np.ndarray) -> float:
    """Desvio padrão do ruído estimado pela resposta a um núcleo que anula bordas e rampas suaves."""
    resposta = cv2.filter2D(cinza.astype(np.float32), -1, _NUCLEO_IMMERKAER)[1:-1, 1:-1]
    return float(math.sqrt(math.pi / 2) * np.abs(resposta).mean() / 6)


def brutos(alinhado: np.ndarray, rosto=None, norma_crua: float | None = None) -> dict[str, float | None]:
    """As medidas físicas de cada componente; None quando falta o insumo (rosto ou norma).

    nitidez: variância do Laplaciano; exposicao: brilho médio (0 a 255); ruido: desvio em níveis de
    cinza; simetria: diferença relativa entre as metades (0 = iguais); pose: fração do limite de giro
    ou de inclinação, a maior das duas (1 = no limite); resolucao: pixels entre os olhos;
    confianca: 0 a 1; norma: norma L2 da saída crua."""
    cinza = f2.converter_cinza(alinhado)
    meio = cinza.shape[1] // 2
    esquerda, direita = float(cinza[:, :meio].mean()), float(cinza[:, meio:].mean())
    medidas: dict[str, float | None] = {
        "nitidez": f2.medir_nitidez(alinhado),
        "exposicao": f2.medir_brilho(alinhado),
        "ruido": _ruido_immerkaer(cinza),
        "simetria": abs(esquerda - direita) / max(esquerda, direita, 1.0),
        "pose": None, "resolucao": None, "confianca": None,
        "norma": None if norma_crua is None else float(norma_crua),
    }
    if rosto is not None:
        # fração do giro e da inclinação máximos que o terminal aceita, lidos de `config` na hora
        medidas["pose"] = max(abs(rosto.yaw()) / config.POSE_MAX_YAW, abs(rosto.roll()) / config.POSE_MAX_ROLL_GRAUS)
        medidas["resolucao"] = math.hypot(rosto.olho_esq[0] - rosto.olho_dir[0], rosto.olho_esq[1] - rosto.olho_dir[1])
        medidas["confianca"] = float(rosto.confianca)
    return medidas


def componentes(alinhado: np.ndarray, rosto=None, norma_crua: float | None = None) -> dict[str, float | None]:
    """Nota de 0 a 1 de cada componente (1 = melhor); None quando falta o insumo (rosto ou norma)."""
    b = brutos(alinhado, rosto, norma_crua)
    return {
        "nitidez": _limitar(b["nitidez"] / NITIDEZ_PLENA),
        "exposicao": _limitar(1 - abs(b["exposicao"] - 128) / 128),
        "ruido": _limitar(1 - b["ruido"] / RUIDO_MAXIMO),
        "simetria": _limitar(1 - b["simetria"]),
        "pose": None if b["pose"] is None else _limitar(1 - b["pose"]),
        "resolucao": None if b["resolucao"] is None else _limitar(b["resolucao"] / OLHOS_PLENO),
        "confianca": None if b["confianca"] is None else _limitar(b["confianca"]),
        "norma": None if b["norma"] is None else _limitar((b["norma"] - NORMA_MINIMA) / NORMA_FAIXA),
    }


def indice(comp: dict[str, float | None]) -> int | None:
    """Índice composto de 0 a 100: a média das notas disponíveis. None se não houver nenhuma."""
    notas = [v for v in comp.values() if v is not None]
    if not notas:
        return None
    return int(round(100 * sum(notas) / len(notas)))
