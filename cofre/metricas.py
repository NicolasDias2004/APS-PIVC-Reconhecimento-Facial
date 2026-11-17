"""Fase 5: métricas biométricas com incerteza.

Curva de erro exata por ordenação, AUC (Mann-Whitney), EER, d′, intervalo de Wilson e a regra de três
para zero erro observado. Só NumPy, vetorizado: O((G + I) log(G + I)), sem laço Python sobre pares.
Convenção: um par é aceito quando a similaridade é maior ou igual ao limiar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FAIXA_HISTOGRAMA = (-0.2, 1.0)       # o cosseno entre pessoas diferentes pode ser negativo
_SEPARADOR_MILHAR = " "         # o mesmo espaço fino de cofre/qt/formatos.py


@dataclass(frozen=True)
class Curva:
    limiares: np.ndarray             # um ponto por escore distinto, em ordem crescente
    fmr: np.ndarray                  # falso casamento: impostores com escore >= limiar
    fnmr: np.ndarray                 # falso não casamento: genuínos com escore < limiar


def _vetor(v) -> np.ndarray:
    a = np.asarray(v, dtype=np.float64).reshape(-1)
    return a[np.isfinite(a)]


def curva(genuinos, impostores) -> Curva:
    g, i = np.sort(_vetor(genuinos)), np.sort(_vetor(impostores))
    limiares = np.unique(np.concatenate([g, i]))
    fmr = (i.size - np.searchsorted(i, limiares, side="left")) / i.size if i.size else np.full(limiares.size, np.nan)
    fnmr = np.searchsorted(g, limiares, side="left") / g.size if g.size else np.full(limiares.size, np.nan)
    return Curva(limiares, np.asarray(fmr, dtype=np.float64), np.asarray(fnmr, dtype=np.float64))


def taxas(genuinos, impostores, limiar: float) -> dict:
    g, i = _vetor(genuinos), _vetor(impostores)
    k_fm, k_fnm = int(np.count_nonzero(i >= limiar)), int(np.count_nonzero(g < limiar))
    return {"fmr": k_fm / i.size if i.size else math.nan, "fnmr": k_fnm / g.size if g.size else math.nan,
            "k_fm": k_fm, "n_imp": int(i.size), "k_fnm": k_fnm, "n_gen": int(g.size)}


def auc(genuinos, impostores) -> float:
    g, i = _vetor(genuinos), np.sort(_vetor(impostores))
    if g.size == 0 or i.size == 0:
        return math.nan
    abaixo = np.searchsorted(i, g, side="left")
    iguais = np.searchsorted(i, g, side="right") - abaixo
    return float((abaixo.sum() + 0.5 * iguais.sum()) / (g.size * i.size))


def eer(c: Curva) -> tuple[float, float]:
    if c.limiares.size == 0 or np.isnan(c.fmr).any() or np.isnan(c.fnmr).any():
        return math.nan, math.nan
    d = c.fmr - c.fnmr                                   # começa >= 0 e só desce
    k = int(np.argmax(d <= 0)) if (d <= 0).any() else -1
    if k < 0:
        return float(c.limiares[-1]), float((c.fmr[-1] + c.fnmr[-1]) / 2)
    if k == 0:
        return float(c.limiares[0]), float((c.fmr[0] + c.fnmr[0]) / 2)
    f = d[k - 1] / (d[k - 1] - d[k])
    limiar = c.limiares[k - 1] + f * (c.limiares[k] - c.limiares[k - 1])
    taxa = c.fmr[k - 1] + f * (c.fmr[k] - c.fmr[k - 1])
    return float(limiar), float(taxa)


def d_prime(genuinos, impostores) -> float:
    g, i = _vetor(genuinos), _vetor(impostores)
    if g.size < 2 or i.size < 2:
        return math.nan
    den = math.sqrt((g.var(ddof=1) + i.var(ddof=1)) / 2)
    return float((g.mean() - i.mean()) / den) if den > 0 else math.nan


def fnmr_em_fmr(c: Curva, alvo: float) -> float | None:
    ok = c.fmr <= alvo
    if c.limiares.size == 0 or not ok.any():
        return None
    return float(c.fnmr[int(np.argmax(ok))])


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n <= 0:
        return math.nan, math.nan
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centro - meia), min(1.0, centro + meia)


def teto(k: int, n: int) -> float:
    if n <= 0:
        return math.nan
    return min(1.0, 3 / n) if k == 0 else wilson(k, n)[1]


def histograma(genuinos, impostores, faixas: int = 50) -> dict:
    bordas = np.linspace(FAIXA_HISTOGRAMA[0], FAIXA_HISTOGRAMA[1], faixas + 1)
    lim = (FAIXA_HISTOGRAMA[0], FAIXA_HISTOGRAMA[1])
    hg, _ = np.histogram(np.clip(_vetor(genuinos), *lim), bins=bordas)
    hi, _ = np.histogram(np.clip(_vetor(impostores), *lim), bins=bordas)
    return {"bordas": [round(float(b), 6) for b in bordas], "genuinos": [int(v) for v in hg],
            "impostores": [int(v) for v in hi]}


def roc(c: Curva, n_imp: int, n_gen: int) -> list[list[float]]:
    """[[fmr, 1 - fnmr]] em FMR crescente, com piso de FMR em 1 / (2 · n_imp) para o eixo log."""
    if c.limiares.size == 0 or n_imp <= 0 or n_gen <= 0:
        return []
    piso = 1 / (2 * n_imp)
    fmr = np.maximum(c.fmr[::-1], piso)
    tar = 1 - c.fnmr[::-1]
    return [[round(float(x), 6), round(float(y), 6)] for x, y in zip(fmr, tar)]


# ---------------------------------------------------------------------------- texto
def _decimal(v: float, casas: int) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def _inteiro(n: int) -> str:
    return f"{int(n):,}".replace(",", _SEPARADOR_MILHAR)


def _pct(f: float, casas: int) -> str:
    return f"{_decimal(100 * f, casas)} %"


def texto_taxa(k: int, n: int) -> str:
    """"0 de 2 236 · teto 0,13 %" ou "43 de 882 · 4,88 % (3,6 a 6,5 %)"; sem pares, "–"."""
    if n <= 0:
        return "–"
    if k == 0:
        return f"0 de {_inteiro(n)} · teto {_pct(teto(0, n), 2)}"
    lo, hi = wilson(k, n)
    return f"{_inteiro(k)} de {_inteiro(n)} · {_pct(k / n, 2)} ({_decimal(100 * lo, 1)} a {_decimal(100 * hi, 1)} %)"
