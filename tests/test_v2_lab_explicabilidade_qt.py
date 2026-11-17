"""Aba Explicabilidade do Laboratório no aplicativo Qt: mapa só pelo botão, calor transparente e prefixo limpo."""

import cv2
import numpy as np
from PySide6.QtGui import QImage

from tests import apoio_v2
from tests.apoio_v2 import _config_isolada  # noqa: F401
from tests.apoio_interface import FOTO_BIDEN


def _abrir(qapp, tmp_path, pipeline, foto=0):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    vm = apoio_v2.abrir_aba(ctx, "laboratorio", "explicabilidade")
    lab = ctx.apl.extensoes.obter("laboratorio")
    if foto is not None:
        lab.usarFotoTeste(foto)
        assert apoio_v2.esperar_ocioso(ctx) and not lab.processando, lab.erro
        apoio_v2.esperar_estado(ctx, vm)
    return ctx, vm, lab


def _calcular(ctx, vm):
    vm.calcular()
    apoio_v2.esperar_estado(ctx, vm)


def test_mapa_so_por_botao(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        assert lab.temReferencia and vm.estado == "pronto"
        assert ctx.apl.extensoes.trabalhos.ocioso() and not vm.temMapa
        lab.usarFotoTeste(1)
        apoio_v2.esperar_ocioso(ctx)
        ctx.girar(0.2)
        assert ctx.apl.extensoes.trabalhos.ocioso() and not vm.temMapa
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_calcular_com_foto_de_teste(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        _calcular(ctx, vm)
        assert vm.estado == "pronto" and vm.temMapa and len(vm.regioes) == 8
        assert vm.barras["orientacao"] == "h" and len(vm.barras["categorias"]) == 8
        assert vm.barras["selos"] == ["1 imagem: tendência"] and vm.frase and not vm.mesmaImagem
        vm.definirJanela(24)
        assert vm.variacoes == 144
        _calcular(ctx, vm)
        assert vm.temMapa and vm.barras["n"].endswith("144 variações")
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_calor_no_provedor_tem_transparencia(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        _calcular(ctx, vm)
        img = apoio_v2.imagem_do_provedor(ctx, "lab/oclusao/calor")
        assert img.hasAlphaChannel() and (img.width(), img.height()) == (448, 448)
        copia = img.convertToFormat(QImage.Format.Format_ARGB32)
        px = np.frombuffer(copia.constBits(), dtype=np.uint8).reshape(448, copia.bytesPerLine() // 4, 4)[:, :448]
        alfa = px[..., 3]
        assert (alfa == 0).any() and (alfa > 0).any()
        assert apoio_v2.imagem_do_provedor(ctx, "lab/oclusao/rosto").width() == 112
    finally:
        ctx.fechar()


def test_sem_referencia_avisa(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline, foto=None)
    try:
        lab.carregar_frame(cv2.imread(str(FOTO_BIDEN)), origem="arquivo", rotulo="Arquivo de teste")
        apoio_v2.esperar_ocioso(ctx)
        apoio_v2.esperar_estado(ctx, vm)
        assert vm.semReferencia
        vm.calcular()
        assert ctx.apl.extensoes.trabalhos.ocioso() and not vm.temMapa
        assert any(t.startswith("O mapa precisa de uma referência") for t in apoio_v2.textos_visiveis(ctx.janela))
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_prefixo_removido_ao_desativar(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        _calcular(ctx, vm)
        assert apoio_v2.imagem_do_provedor(ctx, "lab/oclusao/calor").width() == 448
        ctx.apl.navegar("terminal")
        ctx.girar(0.2)
        assert apoio_v2.imagem_do_provedor(ctx, "lab/oclusao/calor").width() == 1
        assert apoio_v2.imagem_do_provedor(ctx, "lab/oclusao/rosto").width() == 1
    finally:
        ctx.fechar()


def test_sem_vetor_e_sem_avisos(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline, foto=None)
    try:
        assert vm.estado == "vazio"
        lab.usarFotoTeste(2)
        apoio_v2.esperar_ocioso(ctx)
        apoio_v2.esperar_estado(ctx, vm)
        vm.preparar_captura("")
        apoio_v2.esperar_estado(ctx, vm)
        assert vm.temMapa
        assert apoio_v2.sem_vetor_128(apoio_v2.props_do_vm(vm))
        ctx.girar(0.2)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
