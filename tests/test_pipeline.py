"""Fases 2-4: pré-processamento, detecção, alinhamento e embedding."""
import numpy as np

from cofre import config
from cofre import fase2_preprocessamento as f2
from cofre import fase4_representacao as f4
from cofre.fase1_aquisicao import carregar_imagem


def test_preprocessamento_gera_todas_etapas():
    img = carregar_imagem(__import__("tests.conftest", fromlist=["FIX"]).FIX / "obama" / "obama_2012.jpg")
    pre = f2.preprocessar(img)
    assert pre.reduzida.shape[1] == config.LARGURA_PROCESSAMENTO
    assert pre.cinza.ndim == 2
    assert pre.equalizada.shape == pre.reduzida.shape
    assert set(pre.etapas) >= {"1 original", "2 cinza", "2 CLAHE"}


def test_qualidade_rejeita_borrado_e_escuro():
    nitida = np.random.default_rng(0).integers(0, 255, (112, 112), np.uint8)
    assert f2.avaliar_qualidade(nitida).aprovada
    escura = np.zeros((112, 112), np.uint8)
    q = f2.avaliar_qualidade(escura)
    assert not q.aprovada and q.motivo in ("imagem borrada", "muito escura")


def test_detecta_um_rosto_e_embedding_normalizado(pipeline, fotos):
    res = pipeline.processar(carregar_imagem(fotos["obama"][0]))
    assert len(res.rostos) == 1
    p = res.principal
    assert p.alinhado.shape == (112, 112, 3)
    assert p.embedding.shape == (128,)
    assert abs(np.linalg.norm(p.embedding) - 1.0) < 1e-4
    assert p.rosto.confianca >= config.DETECCAO_SCORE_MIN
    assert abs(p.rosto.yaw()) < 0.3  # retrato frontal


def test_sem_rosto_em_imagem_vazia(pipeline):
    res = pipeline.processar(np.zeros((480, 640, 3), np.uint8))
    assert res.rostos == []


def test_mesma_pessoa_acima_do_limiar_e_outra_abaixo(pipeline, fotos):
    emb = {n: [pipeline.processar(carregar_imagem(c)).principal.embedding for c in cs] for n, cs in fotos.items()}
    genuino = f4.similaridade_cosseno(emb["obama"][0], emb["obama"][1])
    impostor = f4.similaridade_cosseno(emb["obama"][0], emb["biden"][0])
    assert genuino >= config.LIMIAR_COSSENO
    assert impostor < config.LIMIAR_COSSENO
    assert genuino - impostor > 0.3


def test_lbp_codigos_e_histograma():
    img = np.random.default_rng(1).integers(0, 255, (64, 64), np.uint8)
    mapa = f4.lbp_mapa(img)
    assert mapa.shape == (62, 62) and mapa.dtype == np.uint8
    hist = f4.lbp_histograma(img, (2, 2))
    assert hist.shape == (4 * 256,) and abs(hist.sum() - 1.0) < 1e-5


def test_etapas_didaticas_incluem_as_cinco_fases(pipeline, fotos):
    etapas = pipeline.processar(carregar_imagem(fotos["biden"][0])).etapas_didaticas()
    assert any(k.startswith("3 ") for k in etapas) and any(k.startswith("4 ") for k in etapas)
