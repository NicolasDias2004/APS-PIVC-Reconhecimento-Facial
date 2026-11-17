"""Métricas biométricas com incerteza (lote L6): curva exata, AUC, EER, d′, Wilson e regra de três."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cofre import metricas


def test_curva_exata_em_caso_pequeno():
    # conferido à mão: aceita quando escore >= limiar
    c = metricas.curva([0.9, 0.8, 0.7], [0.1, 0.75, 0.2, 0.3])
    assert c.limiares.tolist() == [0.1, 0.2, 0.3, 0.7, 0.75, 0.8, 0.9]
    assert c.fmr.tolist() == [1.0, 0.75, 0.5, 0.25, 0.25, 0.0, 0.0]
    assert np.allclose(c.fnmr, [0, 0, 0, 0, 1 / 3, 1 / 3, 2 / 3])
    t = metricas.taxas([0.9, 0.8, 0.7], [0.1, 0.75, 0.2, 0.3], 0.75)
    assert (t["k_fm"], t["n_imp"], t["k_fnm"], t["n_gen"]) == (1, 4, 1, 3)
    lim, taxa = metricas.eer(c)
    assert lim == pytest.approx(0.7375) and taxa == pytest.approx(0.25)
    assert metricas.fnmr_em_fmr(c, 0.01) == pytest.approx(1 / 3)


def test_auc_um_e_meio():
    assert metricas.auc([0.8, 0.9], [0.1, 0.2, 0.3]) == 1.0
    assert metricas.auc([0.5, 0.5], [0.5, 0.5]) == 0.5
    assert metricas.auc([0.3, 0.6], [0.3, 0.6]) == 0.5
    assert math.isnan(metricas.auc([], [0.1]))


def test_eer_distribuicoes_sinteticas():
    rng = np.random.default_rng(3)
    d = 2.0
    g, i = rng.normal(d, 1, 30_000), rng.normal(0, 1, 30_000)
    _, taxa = metricas.eer(metricas.curva(g, i))
    teorico = 0.5 * (1 + math.erf(-(d / 2) / math.sqrt(2)))       # Φ(−d′/2)
    assert abs(taxa - teorico) < 0.01


def test_d_prime():
    g, i = np.array([1.0, 3.0]), np.array([-1.0, 1.0])
    assert metricas.d_prime(g, i) == pytest.approx((2 - 0) / math.sqrt((2 + 2) / 2))
    assert math.isnan(metricas.d_prime([1.0], [0.0, 0.1]))


def test_wilson_e_regra_de_tres():
    assert metricas.teto(0, 4) == pytest.approx(0.75)
    assert metricas.teto(0, 2236) == pytest.approx(0.0013, abs=1e-4)
    lo, hi = metricas.wilson(43, 882)
    assert lo == pytest.approx(0.0364, abs=5e-4) and hi == pytest.approx(0.0650, abs=5e-4)
    assert metricas.teto(43, 882) == pytest.approx(hi)
    assert all(math.isnan(v) for v in metricas.wilson(0, 0))


def test_taxas_vazias_dao_nan():
    t = metricas.taxas([], [], 0.5)
    assert math.isnan(t["fmr"]) and math.isnan(t["fnmr"]) and t["n_imp"] == 0 and t["n_gen"] == 0
    assert all(math.isnan(v) for v in metricas.eer(metricas.curva([], [])))


def test_roc_tem_piso():
    c = metricas.curva([0.9, 0.8], [0.1, 0.2, 0.3, 0.4])
    pontos = metricas.roc(c, 4, 2)
    assert min(p[0] for p in pontos) == pytest.approx(1 / 8)
    assert [p[0] for p in pontos] == sorted(p[0] for p in pontos)
    assert pontos[-1] == [1.0, 1.0]
    h = metricas.histograma([0.9, -0.5], [0.1], faixas=50)
    assert len(h["bordas"]) == 51 and h["bordas"][0] == -0.2 and h["bordas"][-1] == 1.0
    assert sum(h["genuinos"]) == 2 and h["genuinos"][0] == 1        # abaixo de -0,2 entra na primeira faixa


def test_texto_taxa():
    assert metricas.texto_taxa(0, 2236) == "0 de 2 236 · teto 0,13 %"
    assert metricas.texto_taxa(43, 882) == "43 de 882 · 4,88 % (3,6 a 6,5 %)"
    assert metricas.texto_taxa(0, 0) == "–"
