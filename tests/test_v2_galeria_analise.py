"""Geometria da galeria (lote L7): PCA, matriz pessoa × pessoa e situação de cada cadastro.

Os vetores sintéticos ficam só em memória; nada aqui grava banco."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from cofre import galeria_analise
from cofre.fase1_aquisicao import carregar_imagem
from cofre.leitura_ro import GaleriaRO
from tests import apoio_v2
from tests.apoio_interface import FOTO_BIDEN, FOTO_BIDEN_2, FOTO_OBAMA, FOTO_OBAMA_2


def _norm(m: np.ndarray) -> np.ndarray:
    return (m / np.linalg.norm(m, axis=1, keepdims=True)).astype(np.float32)


def _galeria(grupos: list[np.ndarray], ids: list[int] | None = None) -> GaleriaRO:
    ids = ids or list(range(1, len(grupos) + 1))
    donos = np.concatenate([np.full(len(g), i, dtype=np.int64) for i, g in zip(ids, grupos)])
    amostras = np.concatenate([np.arange(1, len(g) + 1, dtype=np.int64) for g in grupos])
    return GaleriaRO(donos=donos, matriz=_norm(np.vstack(grupos)), amostras=amostras,
                     niveis={i: 1 for i in ids}, inativos=0)


def _pessoa(rng, n: int, ruido: float = 0.15) -> np.ndarray:
    base = rng.normal(size=128)
    return base + ruido * rng.normal(size=(n, 128))


def test_pca_deterministica():
    rng = np.random.default_rng(5)
    m = _norm(np.vstack([_pessoa(rng, 8), _pessoa(rng, 8)]))
    p1, v1 = galeria_analise.pca_2d(m)
    p2, v2 = galeria_analise.pca_2d(m.copy())
    assert np.array_equal(p1, p2) and v1 == v2
    ordem = rng.permutation(m.shape[0])
    p3, v3 = galeria_analise.pca_2d(m[ordem])
    assert np.allclose(p3, p1[ordem], atol=1e-3) and v3 == pytest.approx(v1)
    assert galeria_analise.pca_2d(m[:2])[0].tolist() == [[0.0, 0.0], [0.0, 0.0]]


def test_pca_separa_duas_pessoas_de_teste(pipeline):
    vetores = []
    for foto in (FOTO_BIDEN, FOTO_BIDEN_2, FOTO_OBAMA, FOTO_OBAMA_2):
        r = pipeline.processar(carregar_imagem(foto))
        vetores.append(r.principal.embedding)
    pontos, var = galeria_analise.pca_2d(np.vstack(vetores))
    a, b = pontos[:2, 0], pontos[2:, 0]
    assert (a.max() < b.min()) or (b.max() < a.min())      # o primeiro eixo separa as duas pessoas
    assert var[0] > var[1] > 0


def test_matriz_diagonal_e_fora():
    rng = np.random.default_rng(7)
    gal = _galeria([_pessoa(rng, 4), _pessoa(rng, 3)])
    a = galeria_analise.analisar(gal, 0.363)
    m = gal.matriz.astype(np.float64)
    s = m @ m.T
    coesao_1 = s[:4, :4][np.triu_indices(4, 1)].mean()
    assert a.matriz[0, 0] == pytest.approx(coesao_1, abs=1e-4) and a.coesao[1] == pytest.approx(coesao_1, abs=1e-4)
    assert a.matriz[0, 1] == a.matriz[1, 0] == pytest.approx(s[:4, 4:].max(), abs=1e-4)
    assert a.vizinho[1] == (2, pytest.approx(a.matriz[0, 1]))
    assert a.ids == (1, 2) and a.amostras == {1: 4, 2: 3}
    assert a.pontos.shape == (7, 2) and np.array_equal(a.pontos, np.round(a.pontos, 3))


def test_situacoes():
    rng = np.random.default_rng(9)
    gal = _galeria([_pessoa(rng, 2), _pessoa(rng, 8), _pessoa(rng, 8, ruido=3.0)])
    a = galeria_analise.analisar(gal, 0.363)
    assert a.situacao[1] == "poucas" and a.recomendacao[1].startswith("Só 2 amostras")
    assert a.situacao[2] == "boa" and a.recomendacao[2] == "Sem achados."
    assert a.situacao[3] == "dispersa"
    v = rng.normal(size=128)
    gemeos = _galeria([np.vstack([v, v + 0.01 * rng.normal(size=128)]), np.vstack([v, v])])
    b = galeria_analise.analisar(gemeos, 0.363)
    assert b.situacao == {1: "duplicidade", 2: "duplicidade"}
    assert b.recomendacao[1] == "Possível duplicidade com Pessoa B: conferir os dois cadastros."


def test_uma_amostra_sem_coesao():
    rng = np.random.default_rng(13)
    a = galeria_analise.analisar(_galeria([_pessoa(rng, 1), _pessoa(rng, 6)]), 0.363)
    assert a.coesao[1] is None and a.mais_fraca[1] is None
    assert np.isnan(a.matriz[0, 0]) and a.coesao[2] is not None
    assert a.mais_fraca[2][0] in range(1, 7)


def test_saida_so_2d_e_escalares():
    rng = np.random.default_rng(17)
    gal = _galeria([_pessoa(rng, 70), _pessoa(rng, 60)])         # 130 amostras: 128 casaria a regra da lista plana
    a = galeria_analise.analisar(gal, 0.363)
    for campo in dataclasses.fields(a):
        valor = getattr(a, campo.name)
        valor = valor.tolist() if isinstance(valor, np.ndarray) else valor
        assert apoio_v2.sem_vetor_128(valor), campo.name
        if isinstance(getattr(a, campo.name), np.ndarray):
            assert getattr(a, campo.name).ndim <= 2 and getattr(a, campo.name).shape[-1] != 128
