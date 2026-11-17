"""Instrumentos das fases do Laboratório (cofre/fases_lab.py): matriz do alinhamento, histogramas,
assinatura como imagem e classificação dos candidatos da galeria."""

import inspect

import cv2
import numpy as np
import pytest

from cofre import amostra_lab, fases_lab
from cofre.leitura_ro import GaleriaRO

COR_BARRA, COR_FUNDO = (192, 208, 53), (31, 26, 21)


@pytest.fixture(scope="module")
def amostras(pipeline):
    fotos = [c for lista in amostra_lab.fotos_de_teste().values() for c in lista]
    return [amostra_lab.preparar(cv2.imread(str(c)), pipeline, origem="foto_teste") for c in fotos]


def test_matriz_reproduz_o_aligncrop(amostras):
    assert len(amostras) == 4
    for a in amostras:
        m = fases_lab.matriz_alinhamento(a.rosto)
        assert m.m.shape == (2, 3)
        refeito = cv2.warpAffine(a.frame, m.m, (112, 112))
        dif = np.abs(refeito.astype(int) - a.alinhado.astype(int))
        assert dif.max() <= 1 or (dif <= 1).mean() >= 0.99


def test_decomposicao_da_matriz(amostras):
    for a in amostras:
        m = fases_lab.matriz_alinhamento(a.rosto)
        assert 0.1 < m.escala < 1
        assert abs(m.rotacao_graus) < 5
        assert len(m.residuos_px) == 5 and max(m.residuos_px) < 8
        assert np.allclose(m.m[:, 2], [m.tx, m.ty])


def test_histogramas_somam_um(amostras):
    h = fases_lab.histogramas(amostras[0])
    assert len(h["bordas"]) == 65 and h["bordas"][0] == 0 and h["bordas"][-1] == 256
    for chave in ("original", "global", "clahe"):
        assert len(h[chave]) == 64
        assert sum(h[chave]) == pytest.approx(1.0, abs=1e-9)
    assert h["global"] != h["original"]


def _galeria(donos, vetores):
    donos = np.array(donos, np.int64)
    return GaleriaRO(donos=donos, matriz=np.array(vetores, np.float32), amostras=np.ones_like(donos),
                     niveis={int(d): 1 for d in donos}, inativos=0)


def test_ranking_maximo_por_dono_e_ordem():
    q = np.array([1.0, 0.0, 0.0], np.float32)
    g = _galeria([1, 1, 2, 3, 3], [[0.2, 1, 0], [0.9, 0.1, 0], [0.5, 0.5, 0], [0.1, 0, 1], [0.3, 0.2, 0]])
    r = fases_lab.ranking(q, g, limiar=0.4)
    assert [c["usuario_id"] for c in r] == [1, 2, 3]
    assert [round(c["similaridade"], 3) for c in r] == [0.9, 0.5, 0.3]
    assert len(fases_lab.ranking(q, g, limiar=0.4, k=2)) == 2
    assert fases_lab.ranking(q, _galeria([], np.zeros((0, 3))), 0.4) == []


def test_ranking_marca_acima_do_limiar_pelo_argumento():
    q = np.array([1.0, 0.0], np.float32)
    g = _galeria([1, 2], [[0.6, 0], [0.3, 0]])
    assert [c["acima"] for c in fases_lab.ranking(q, g, limiar=0.5)] == [True, False]
    assert [c["acima"] for c in fases_lab.ranking(q, g, limiar=0.2)] == [True, True]
    assert [c["acima"] for c in fases_lab.ranking(q, g, limiar=0.7)] == [False, False]


def test_imagem_assinatura_tem_barras_e_none_sem_rosto(amostras, pipeline):
    img = fases_lab.imagem_assinatura(amostras[0], cor_barra=COR_BARRA, cor_fundo=COR_FUNDO)
    assert img.shape == (160, 768, 3) and img.dtype == np.uint8
    cores = np.unique(img.reshape(-1, 3), axis=0)
    assert len(cores) > 1 and (img == COR_BARRA).all(axis=2).any()
    vazia = amostra_lab.preparar(np.full((240, 320, 3), 128, np.uint8), pipeline)
    assert fases_lab.imagem_assinatura(vazia, cor_barra=COR_BARRA, cor_fundo=COR_FUNDO) is None
    # nenhuma função pública devolve os 128 números
    publicas = [n for n, f in inspect.getmembers(fases_lab, inspect.isfunction)
                if f.__module__ == fases_lab.__name__ and not n.startswith("_")]
    assert sorted(publicas) == ["histogramas", "imagem_assinatura", "leituras", "mapa_lbp",
                                "matriz_alinhamento", "ranking"]


def test_sem_rosto_devolve_vazio(pipeline):
    vazia = amostra_lab.preparar(np.full((240, 320, 3), 128, np.uint8), pipeline)
    assert not vazia.tem_rosto
    assert fases_lab.mapa_lbp(vazia) is None
    leituras = fases_lab.leituras(vazia, None)
    assert leituras[3] == [("Rostos detectados", "0")] and leituras[4] == [] and leituras[5] == []
    assert len(fases_lab.histogramas(vazia)["original"]) == 64
