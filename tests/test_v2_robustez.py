"""Robustez e ablação (cofre/robustez.py): curvas por família, ponto de quebra, cancelamento e ablação."""

import cv2
import pytest

from cofre import amostra_lab, robustez
from cofre.qt.trabalhos import Cancelado, Sinal

LIMIAR = 0.363


@pytest.fixture(scope="module")
def par(pipeline):
    fotos = amostra_lab.fotos_de_teste()
    a_, b_ = next(iter(fotos.values()))[:2]
    a = amostra_lab.preparar(cv2.imread(str(a_)), pipeline)
    b = amostra_lab.preparar(cv2.imread(str(b_)), pipeline)
    return a, b


def test_nivel_zero_da_a_similaridade_limpa(par):
    a, b = par
    limpa = float(a.embedding @ b.embedding)
    for familia in ("desfoque", "ruido", "oclusao_olhos", "resolucao"):
        assert robustez.similaridade_degradada(a.alinhado, b.embedding, familia, 0.0) == pytest.approx(limpa, abs=2e-3)


def test_curva_nao_cresce_com_desfoque_forte(par):
    a, b = par
    for familia in ("desfoque", "ruido", "resolucao"):
        zero = robustez.similaridade_degradada(a.alinhado, b.embedding, familia, 0.0)
        um = robustez.similaridade_degradada(a.alinhado, b.embedding, familia, 1.0)
        assert um < zero


def test_ponto_de_quebra_interpolado():
    niveis = [0.0, 0.25, 0.5, 0.75, 1.0]
    assert robustez.ponto_de_quebra(niveis, [0.9, 0.8, 0.6, 0.2, 0.1], 0.4) == pytest.approx(0.625)
    assert robustez.ponto_de_quebra(niveis, [0.9, 0.8, 0.7, 0.6, 0.5], 0.4) is None
    assert robustez.ponto_de_quebra(niveis, [0.3, 0.2, 0.1, 0.1, 0.1], 0.4) == 0.0
    assert robustez.ponto_de_quebra(niveis, [0.9, 0.4, 0.3, 0.2, 0.1], 0.4) == pytest.approx(0.25)


def test_varredura_tem_8_curvas_de_12_pontos(par):
    a, b = par
    curvas = robustez.varrer(a.alinhado, b.embedding, LIMIAR)
    assert len(curvas) == 8 and len({c.familia for c in curvas}) == 8
    for c in curvas:
        assert len(c.niveis) == len(c.similaridade) == len(c.rotulos) == 12
        assert (c.quebra_rotulo == "") == (c.quebra_nivel is None)
    assert any(c.quebra_nivel is not None for c in curvas)


def test_varredura_cancela(par):
    a, b = par
    sinal = Sinal(lambda fracao: sinal.cancelar())    # o primeiro aviso (fim da primeira família) cancela
    with pytest.raises(Cancelado):
        robustez.varrer(a.alinhado, b.embedding, LIMIAR, sinal=sinal)
    assert sinal.cancelado()


def test_ablacao_alinhamento_com_supera_sem(pipeline):
    fotos = amostra_lab.fotos_de_teste()
    pares = [(cv2.imread(str(c[0])), cv2.imread(str(c[1]))) for c in fotos.values()]
    r = robustez.ablacao_alinhamento(pares, pipeline, LIMIAR)
    assert r["n"] == len(pares) and len(r["com"]) == len(r["sem"]) == r["n"]
    assert sum(r["com"]) / r["n"] > sum(r["sem"]) / r["n"]
    assert 0 <= r["abaixo_com"] <= r["abaixo_sem"] <= r["n"]


def test_ablacao_clahe_formato(pipeline):
    fotos = [cv2.imread(str(c)) for lista in amostra_lab.fotos_de_teste().values() for c in lista]
    r = robustez.ablacao_clahe(fotos, pipeline, ganhos=(0.05, 0.2))
    assert r["n"] == 4 and r["ganhos"] == [0.05, 0.2]
    assert len(r["completa"]) == len(r["reducao"]) == 2
    assert all(0 <= k <= 4 for k in r["completa"] + r["reducao"])
    assert r["completa"][0] >= r["reducao"][0]
