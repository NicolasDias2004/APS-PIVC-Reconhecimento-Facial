"""Fases 4 e 5: geometria da galeria.

Cada pessoa cadastrada vira um agrupamento de amostras. Daqui saem só escalares, pontos 2D
arredondados (PCA) e a matriz pessoa × pessoa; os vetores gravados nunca saem do Python.
Os achados são consultivos: nada aqui desativa, remove ou bloqueia alguém.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .leitura_ro import GaleriaRO, rotulos_anonimos

AMOSTRAS_PADRAO = 18          # o cadastro pela câmera grava 18 amostras
MINIMO_AMOSTRAS = 6
COESAO_MINIMA = 0.50
MARGEM_PROXIMA = 0.10
SITUACOES = ("boa", "poucas", "dispersa", "proxima", "duplicidade")


@dataclass(frozen=True)
class AnaliseGaleria:
    ids: tuple[int, ...]                                  # pessoas, em ordem crescente de id
    amostras: dict[int, int]
    pontos: np.ndarray                                    # (N, 2) float, arredondado a 3 casas
    donos: np.ndarray                                     # (N,)
    numeros: np.ndarray                                   # (N,) número da amostra dentro da pessoa
    variancia: tuple[float, float]                        # fração explicada por eixo
    centros: dict[int, tuple[float, float]]
    coesao: dict[int, float | None]                       # média das similaridades internas; None com 1 amostra
    mais_fraca: dict[int, tuple[int, float] | None]       # (número da amostra, similaridade ao centróide)
    matriz: np.ndarray                                    # (P, P): diagonal = coesão; fora = maior similaridade do par
    vizinho: dict[int, tuple[int, float] | None]
    situacao: dict[int, str]
    recomendacao: dict[int, str]


def pca_2d(matriz: np.ndarray) -> tuple[np.ndarray, tuple[float, float]]:
    """Projeção nas duas primeiras componentes, com sinal fixo (determinística entre processos)."""
    m = np.asarray(matriz, dtype=np.float64)
    n = m.shape[0] if m.ndim == 2 else 0
    if n < 3:
        return np.zeros((n, 2), dtype=np.float64), (0.0, 0.0)
    c = m - m.mean(axis=0)
    _, s, vt = np.linalg.svd(c, full_matrices=False)
    comp = vt[:2].copy()
    for k in range(comp.shape[0]):
        if comp[k, int(np.argmax(np.abs(comp[k])))] < 0:
            comp[k] = -comp[k]
    pontos = c @ comp.T
    if pontos.shape[1] < 2:
        pontos = np.hstack([pontos, np.zeros((n, 2 - pontos.shape[1]))])
    total = float((s ** 2).sum())
    frac = [float(v) / total if total > 0 else 0.0 for v in (s[:2] ** 2)] + [0.0, 0.0]
    return np.round(pontos, 3), (round(frac[0], 4), round(frac[1], 4))


def _situacao(maior_outro: float | None, n: int, coesao: float | None, limiar: float) -> str:
    if maior_outro is not None and maior_outro >= limiar:
        return "duplicidade"
    if maior_outro is not None and maior_outro >= limiar - MARGEM_PROXIMA:
        return "proxima"
    if n < MINIMO_AMOSTRAS:
        return "poucas"
    if coesao is not None and coesao < COESAO_MINIMA:
        return "dispersa"
    return "boa"


def _recomendacao(situacao: str, n: int, vizinho: str) -> str:
    if situacao == "duplicidade":
        return f"Possível duplicidade com {vizinho}: conferir os dois cadastros."
    if situacao == "proxima":
        return f"Perto de {vizinho}: margem estreita até o limiar."
    if situacao == "poucas":
        return f"Só {n} amostras: refazer o cadastro pela câmera (o padrão é {AMOSTRAS_PADRAO})."
    if situacao == "dispersa":
        return "Amostras pouco parecidas entre si: refazer o cadastro com luz uniforme."
    return "Sem achados."


def analisar(galeria: GaleriaRO, limiar: float, rotulos: dict[int, str] | None = None) -> AnaliseGaleria:
    """`rotulos` só entra no texto das recomendações (padrão: "Pessoa A", "Pessoa B"... pelos ids)."""
    m = np.asarray(galeria.matriz, dtype=np.float64)
    donos = np.asarray(galeria.donos, dtype=np.int64)
    numeros = np.asarray(galeria.amostras, dtype=np.int64)
    ids = tuple(int(v) for v in np.unique(donos))
    rotulos = rotulos if rotulos is not None else rotulos_anonimos(ids)
    pontos, variancia = pca_2d(m)
    s = m @ m.T if m.shape[0] else np.zeros((0, 0))
    grupos = {p: np.flatnonzero(donos == p) for p in ids}
    amostras = {p: int(idx.size) for p, idx in grupos.items()}
    centros, coesao, mais_fraca = {}, {}, {}
    for p, idx in grupos.items():
        centros[p] = (round(float(pontos[idx, 0].mean()), 3), round(float(pontos[idx, 1].mean()), 3))
        if idx.size < 2:
            coesao[p], mais_fraca[p] = None, None
            continue
        bloco = s[np.ix_(idx, idx)]
        a, b = np.triu_indices(idx.size, k=1)
        coesao[p] = round(float(bloco[a, b].mean()), 4)
        centro = m[idx].mean(axis=0)
        norma = np.linalg.norm(centro)
        sims = m[idx] @ (centro / norma if norma > 0 else centro)
        k = int(np.argmin(sims))
        mais_fraca[p] = (int(numeros[idx[k]]), round(float(sims[k]), 4))
    pp = len(ids)
    matriz = np.full((pp, pp), np.nan)
    for a_, p in enumerate(ids):
        matriz[a_, a_] = np.nan if coesao[p] is None else coesao[p]
        for b_ in range(a_ + 1, pp):
            maior = float(s[np.ix_(grupos[p], grupos[ids[b_]])].max())
            matriz[a_, b_] = matriz[b_, a_] = round(maior, 4)
    vizinho, situacao, recomendacao = {}, {}, {}
    for a_, p in enumerate(ids):
        fora = [(matriz[a_, b_], ids[b_]) for b_ in range(pp) if b_ != a_]
        if fora:
            valor, outro = max(fora, key=lambda t: (t[0], -t[1]))
            vizinho[p] = (int(outro), float(valor))
        else:
            vizinho[p] = None
        maior = vizinho[p][1] if vizinho[p] is not None else None
        situacao[p] = _situacao(maior, amostras[p], coesao[p], limiar)
        nome_viz = rotulos.get(vizinho[p][0], "outra pessoa") if vizinho[p] is not None else ""
        recomendacao[p] = _recomendacao(situacao[p], amostras[p], nome_viz)
    return AnaliseGaleria(ids, amostras, pontos, donos, numeros, variancia, centros, coesao, mais_fraca,
                          matriz, vizinho, situacao, recomendacao)
