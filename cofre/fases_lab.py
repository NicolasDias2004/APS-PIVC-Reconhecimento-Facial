"""Fases 1 a 5: instrumentos de cada fase.

Leituras do laboratório sobre uma `AmostraLab` (o que o pipeline produziu em cada fase): os
histogramas de luminância antes e depois da equalização (fase 2), a matriz afim 2×3 que leva os
cinco pontos do rosto ao molde do SFace (fase 3), o mapa LBP e a imagem da assinatura de 128
barras (fase 4) e a classificação dos candidatos mais parecidos da galeria (fase 5).

Tudo é consultivo: nada aqui decide acesso nem grava coisa alguma. O vetor de 128 dimensões não sai
deste módulo como número: a assinatura volta como imagem já desenhada.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from . import config
from . import fase2_preprocessamento as f2
from . import fase4_representacao as f4

# molde 112x112 do alignCrop do SFace (olho direito, olho esquerdo, nariz, boca direita, boca esquerda)
PONTOS_CANONICOS = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                             [41.5493, 92.3655], [70.7299, 92.2041]], np.float32)

ORIGENS = {"foto_teste": "Foto de teste", "arquivo": "Arquivo", "camera": "Quadro da câmera"}


@dataclass(frozen=True)
class MatrizAfim:
    """Similaridade (escala, rotação e translação) que leva o rosto ao molde de 112×112."""

    m: np.ndarray                       # (2, 3) float64
    escala: float
    rotacao_graus: float
    tx: float
    ty: float
    residuos_px: tuple[float, ...]      # distância de cada ponto ao molde, depois da transformação


def _num(v: float | None, casas: int = 2) -> str:
    if v is None or v != v:
        return "–"
    texto = f"{float(v):.{casas}f}"
    if float(texto) == 0:
        texto = texto.lstrip("-")
    return texto.replace(".", ",")


def _pontos(rosto) -> np.ndarray:
    return np.array([rosto.olho_dir, rosto.olho_esq, rosto.nariz, rosto.boca_dir, rosto.boca_esq], np.float64)


def matriz_alinhamento(rosto) -> MatrizAfim:
    """Umeyama sem reflexão entre os 5 pontos do rosto (em float) e `PONTOS_CANONICOS`."""
    origem, destino = _pontos(rosto), PONTOS_CANONICOS.astype(np.float64)
    mo, md = origem.mean(axis=0), destino.mean(axis=0)
    oc, dc = origem - mo, destino - md
    cov = dc.T @ oc / len(origem)
    u, s, vt = np.linalg.svd(cov)
    d = np.eye(2)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        d[1, 1] = -1.0
    r = u @ d @ vt
    var_o = float((oc ** 2).sum() / len(origem))
    escala = float(np.trace(np.diag(s) @ d) / var_o) if var_o > 0 else 1.0
    t = md - escala * r @ mo
    m = np.hstack([escala * r, t[:, None]])
    levados = origem @ m[:, :2].T + m[:, 2]
    residuos = tuple(float(x) for x in np.linalg.norm(levados - destino, axis=1))
    rotacao = math.degrees(math.atan2(r[1, 0], r[0, 0]))
    return MatrizAfim(m=m, escala=escala, rotacao_graus=rotacao, tx=float(t[0]), ty=float(t[1]), residuos_px=residuos)


def _fracoes(cinza: np.ndarray, bordas: np.ndarray) -> list[float]:
    contagem, _ = np.histogram(cinza.ravel(), bins=bordas)
    total = max(int(cinza.size), 1)
    return [float(c) / total for c in contagem]


def histogramas(amostra, faixas: int = 64) -> dict:
    """Fração de pixels por faixa de luminância: original, equalização global e CLAHE."""
    bordas = np.linspace(0, 256, faixas + 1)
    cinza = amostra.cinza
    return {"bordas": [float(b) for b in bordas],
            "original": _fracoes(cinza, bordas),
            "global": _fracoes(f2.equalizar_cinza(cinza), bordas),
            "clahe": _fracoes(f2.converter_cinza(amostra.equalizada), bordas)}


def mapa_lbp(amostra) -> np.ndarray | None:
    """Mapa LBP 3×3 do rosto alinhado (uint8 110×110); None sem rosto."""
    if amostra.alinhado is None:
        return None
    return f4.lbp_mapa(f2.converter_cinza(amostra.alinhado)).astype(np.uint8)


def imagem_assinatura(amostra, largura: int = 768, altura: int = 160, *,
                      cor_barra: tuple[int, int, int], cor_fundo: tuple[int, int, int]) -> np.ndarray | None:
    """As 128 barras do descritor (divididas pelo maior módulo, eixo zero no meio) desenhadas numa
    imagem BGR uint8 (altura, largura, 3). None sem rosto."""
    if amostra.embedding is None:
        return None
    v = np.asarray(amostra.embedding, dtype=np.float64).reshape(-1)
    maior = float(np.abs(v).max()) or 1.0
    v = v / maior
    img = np.empty((altura, largura, 3), np.uint8)
    img[:] = cor_fundo
    meio = altura // 2
    eixo = tuple(int(round(0.6 * a + 0.4 * b)) for a, b in zip(cor_fundo, cor_barra))
    cv2.line(img, (0, meio), (largura - 1, meio), eixo, 1)
    passo = largura / v.size
    curso = meio - 4
    for i, valor in enumerate(v):
        x0 = int(round(i * passo))
        x1 = max(x0, int(round((i + 1) * passo)) - 2)
        y = int(round(meio - valor * curso))
        cv2.rectangle(img, (x0, min(meio, y)), (x1, max(meio, y)), cor_barra, -1)
    return img


def ranking(embedding: np.ndarray, galeria, limiar: float, k: int = 3) -> list[dict]:
    """Os `k` donos mais parecidos (máximo por dono do cosseno), em ordem decrescente."""
    if galeria.matriz.shape[0] == 0:
        return []
    q = np.asarray(embedding, dtype=np.float32).reshape(-1)
    sims = galeria.matriz @ q
    ordem = np.argsort(galeria.donos, kind="stable")
    donos, inicio = np.unique(galeria.donos[ordem], return_index=True)
    maximos = np.maximum.reduceat(sims[ordem], inicio)
    pares = sorted(zip(donos.tolist(), maximos.tolist()), key=lambda p: -p[1])[:k]
    return [{"usuario_id": int(u), "similaridade": float(s), "acima": bool(s >= limiar)} for u, s in pares]


def leituras(amostra, matriz: MatrizAfim | None) -> dict[int, list[tuple[str, str]]]:
    """Pares (rótulo, valor) já em texto, por fase. A fase 5 fica vazia até a comparação."""
    h, w = amostra.frame.shape[:2]
    p = amostra.parametros
    saida: dict[int, list[tuple[str, str]]] = {
        1: [("Dimensões", f"{w} × {h} px"), ("Brilho médio", _num(f2.medir_brilho(amostra.frame), 1)),
            ("Origem", ORIGENS.get(amostra.origem, amostra.origem or "–"))],
        2: [("Largura de trabalho", f"{amostra.reduzida.shape[1]} px · escala {_num(amostra.escala, 3)}"),
            ("Núcleo do Gauss", "sem suavização" if p.kernel == 1 else f"{p.kernel} × {p.kernel}"),
            ("CLAHE", f"clip {_num(p.clip, 1)} · grade {p.grade} × {p.grade}")],
        3: [("Rostos detectados", str(amostra.n_rostos))],
        4: [],
        5: [],
    }
    q = amostra.qualidade
    if q is not None:
        saida[2] += [("Nitidez do alinhado", _num(q.nitidez, 1)), ("Brilho do alinhado", _num(q.brilho, 1)),
                     ("Qualidade", "aprovada" if q.aprovada else q.motivo)]
    r = amostra.rosto
    if r is not None:
        saida[3] += [("Confiança", _num(r.confianca, 3)),
                     ("Giro (yaw)", f"{_num(r.yaw(), 2)} · limite {_num(config.POSE_MAX_YAW, 2)}"),
                     ("Inclinação (roll)", f"{_num(r.roll(), 1)}° · limite {_num(config.POSE_MAX_ROLL_GRAUS, 0)}°"),
                     ("Razão do nariz", f"{_num(r.razao_nariz(), 2)} · de {_num(config.POSE_RAZAO_NARIZ_MIN, 2)} "
                                        f"a {_num(config.POSE_RAZAO_NARIZ_MAX, 2)}"),
                     ("Pose", r.problema_pose() or "pose aceita")]
    if matriz is not None:
        saida[3] += [("Escala", _num(matriz.escala, 4)), ("Rotação", f"{_num(matriz.rotacao_graus, 2)}°"),
                     ("Maior resíduo", f"{_num(max(matriz.residuos_px), 1)} px")]
    if amostra.embedding is not None:
        norma = float(np.linalg.norm(amostra.embedding))
        saida[4] = [("Dimensão", "128"), ("Norma do vetor cru", _num(amostra.norma_crua, 3)),
                    ("Norma depois de normalizar", _num(norma, 3))]
    return saida
