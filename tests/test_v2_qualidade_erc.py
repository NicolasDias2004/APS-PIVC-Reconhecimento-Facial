"""Validação das medidas de qualidade pela curva erro × descarte (cofre/qualidade_erc.py) e a aba Qualidade."""

import math

import numpy as np
import pytest

from cofre import amostra_lab, qualidade, qualidade_erc
from tests import apoio_v2
from tests.apoio_v2 import _config_isolada  # noqa: F401

LIMIAR = 0.363


def test_spearman_conhecido():
    x = np.arange(10, dtype=float)
    assert qualidade_erc.spearman(x, x ** 3) == pytest.approx(1.0)
    assert qualidade_erc.spearman(x, -x) == pytest.approx(-1.0)
    assert qualidade_erc.spearman([1, 2, 2, 3], [1, 2, 3, 4]) == pytest.approx(0.9486833, abs=1e-6)
    assert math.isnan(qualidade_erc.spearman([1, 2], [2, 1]))
    assert qualidade_erc.spearman([1, np.nan, 2, 3, 4], [1, 9, 2, 3, 4]) == pytest.approx(1.0)


def test_erc_cai_com_qualidade_perfeita():
    rng = np.random.default_rng(1)
    escores = rng.uniform(0.1, 0.9, 400)
    curva = qualidade_erc.curva_erro_descarte(escores, escores, LIMIAR)
    fnmr = [c[1] for c in curva]
    assert [c[0] for c in curva] == list(qualidade_erc.FRACOES_PADRAO)
    assert all(b <= a + 1e-12 for a, b in zip(fnmr, fnmr[1:]))
    assert fnmr[-1] < fnmr[0] and curva[0][3] == 400


def test_erc_controle_aleatorio_fica_perto_da_base():
    rng = np.random.default_rng(2)
    escores = rng.uniform(0.1, 0.9, 2000)
    base = float((escores < LIMIAR).mean())
    medias = np.mean([[c[1] for c in qualidade_erc.curva_erro_descarte(escores, rng.random(2000), LIMIAR)]
                      for _ in range(20)], axis=0)
    assert np.all(np.abs(medias - base) < 0.03)


@pytest.fixture(scope="module")
def conjunto(pipeline):
    return qualidade_erc.montar(amostra_lab.fotos_de_teste(), pipeline)


def test_montar_nas_fotos_de_teste(conjunto):
    c = conjunto
    assert len(c.pessoa) == 64 and c._embeddings.shape == (64, 128)
    assert c.pessoas == 2 and c.imagens == 4 and set(c.componentes) == set(qualidade.COMPONENTES)
    assert all(v.shape == (64,) for v in c.componentes.values())
    escores, idx = qualidade_erc.pares_genuinos(c)
    assert len(escores) == 512 and idx.shape == (512, 2)
    assert (c.pessoa[idx[:, 0]] == c.pessoa[idx[:, 1]]).all() and (c.imagem[idx[:, 0]] != c.imagem[idx[:, 1]]).all()
    r = qualidade_erc.avaliar(c, LIMIAR)
    assert r["ficha"] == {"pessoas": 2, "imagens": 4, "amostras": 64, "pares": 512, "semente": 0}
    assert set(r) == {"ficha", "curvas", "aleatorio", "spearman", "leitura"} and r["leitura"].startswith("Neste protocolo")
    assert apoio_v2.sem_vetor_128(r) and "_embeddings" not in repr(r)
    assert not any(isinstance(v, np.ndarray) for v in r.values())


def test_aba_qualidade_calcula_e_carimba_sintetico(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        vm = apoio_v2.abrir_aba(ctx, "resultados", "qualidade")
        assert vm.estado == "vazio" and ctx.apl.extensoes.trabalhos.ocioso()
        assert "Escolha a fonte e calcule" in apoio_v2.textos_visiveis(ctx.janela)
        vm.preparar_captura("")
        assert apoio_v2.esperar_estado(ctx, vm, 30) == "pronto"
        assert vm.curvas["selos"] == ["Sintético"] and len(vm.curvas["series"]) == 4
        assert vm.curvas["series"][-1]["tracejada"] and vm.curvas["series"][-1]["cor"] == "neutro"
        assert len(vm.tabela) == 8 and vm.ficha["pares"] == "512" and vm.leitura
        assert apoio_v2.sem_vetor_128(apoio_v2.props_do_vm(vm))
        ctx.girar(0.3)
        assert any("Leitura informativa." in t for t in apoio_v2.textos_visiveis(ctx.janela))
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
