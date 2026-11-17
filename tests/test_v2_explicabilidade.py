"""Sensibilidade do descritor por oclusão (cofre/explicabilidade.py)."""

import cv2
import numpy as np
import pytest

from cofre import amostra_lab, explicabilidade
from cofre.qt import tema_v2
from cofre.qt.trabalhos import Cancelado, Sinal


@pytest.fixture(scope="module")
def par(pipeline):
    a_, b_ = next(iter(amostra_lab.fotos_de_teste().values()))[:2]
    return (amostra_lab.preparar(cv2.imread(str(a_)), pipeline), amostra_lab.preparar(cv2.imread(str(b_)), pipeline))


def test_grade_7x7_e_12x12(par):
    a, b = par
    assert explicabilidade.mapa_oclusao(a.alinhado, b.embedding).queda.shape == (7, 7)
    fino = explicabilidade.mapa_oclusao(a.alinhado, b.embedding, janela=24, passo=8)
    assert fino.queda.shape == (12, 12) and (fino.janela, fino.passo) == (24, 8)


def test_queda_nao_negativa_e_conta_aumentos(par):
    a, b = par
    m = explicabilidade.mapa_oclusao(a.alinhado, b.embedding)
    assert m.queda.dtype == np.float32 and (m.queda >= 0).all()
    assert 0 <= m.aumentos <= 49
    assert m.base == pytest.approx(float(a.embedding @ b.embedding), abs=2e-3)
    assert m.queda.max() > 0


def test_regioes_ordenadas_e_frase(par):
    a, b = par
    m = explicabilidade.mapa_oclusao(a.alinhado, b.embedding)
    assert [c for c, _ in m.regioes] and len(m.regioes) == 8
    valores = [v for _, v in m.regioes]
    assert valores == sorted(valores, reverse=True)
    assert set(c for c, _ in m.regioes) == set(explicabilidade.REGIOES)
    assert m.frase.startswith("A região que mais pesa é a ") and "de " in m.frase


def test_colorir_sem_vermelho_e_alfa_zero_onde_zero():
    queda = np.zeros((7, 7), np.float32)
    queda[3, 3] = 0.2
    m = explicabilidade.MapaOclusao(queda=queda, base=0.7, janela=28, passo=14, aumentos=0, regioes=(), frase="")
    img = explicabilidade.colorir(m, tema_v2.CALOR)
    assert img.shape == (448, 448, 4) and img.dtype == np.uint8
    assert img[0, 0, 3] == 0 and img[224, 224, 3] > 200
    visiveis = img[img[..., 3] > 0][:, :3].astype(int)
    b, g, r = visiveis[:, 0], visiveis[:, 1], visiveis[:, 2]
    assert not ((r > 150) & (g < 100) & (b < 100)).any()       # nada de vermelho
    cores = {tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (4, 2, 0)) for c in tema_v2.CALOR}
    assert {tuple(map(int, p)) for p in visiveis[::97]} <= cores


def test_cancelamento(par):
    a, b = par
    sinal = Sinal()
    sinal.cancelar()
    with pytest.raises(Cancelado):
        explicabilidade.mapa_oclusao(a.alinhado, b.embedding, sinal=sinal)
