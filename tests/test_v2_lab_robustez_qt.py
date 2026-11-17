"""Aba Robustez do Laboratório no aplicativo Qt: medidor ao vivo, varredura, CSV e avisos."""

import cv2

from tests import apoio_v2
from tests.apoio_v2 import _config_isolada  # noqa: F401
from tests.apoio_interface import FOTO_BIDEN

from cofre import config


def _abrir(qapp, tmp_path, pipeline, foto=0):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    vm = apoio_v2.abrir_aba(ctx, "laboratorio", "robustez")
    lab = ctx.apl.extensoes.obter("laboratorio")
    if foto is not None:
        lab.usarFotoTeste(foto)
        assert apoio_v2.esperar_ocioso(ctx) and not lab.processando, lab.erro
        apoio_v2.esperar_estado(ctx, vm)
        apoio_v2.esperar_ocioso(ctx)
    return ctx, vm, lab


def test_medidor_ao_vivo_responde(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        assert vm.estado == "pronto" and not vm.semReferencia
        limpa = vm.similaridade
        assert 0.3 < limpa <= 1
        vm.definirIntensidade(1.0)
        apoio_v2.esperar_ocioso(ctx)
        assert vm.similaridade < limpa and vm.rotuloIntensidade == "σ = 8,0"
        vm.definirFamilia("rotacao")
        apoio_v2.esperar_ocioso(ctx)
        assert vm.rotuloIntensidade == "40°" and vm.similaridade < limpa
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_varrer_preenche_curvas_e_quebras(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        vm.varrer()
        assert vm.varrendo
        apoio_v2.esperar_ocioso(ctx)
        assert not vm.varrendo and len(vm.curvas) == 8 and len(vm.quebras) == 8
        c = vm.curvas[0]
        assert c["selos"] == ["Sintético"] and c["n"] == "1 imagem"
        assert len(c["series"][0]["pontos"]) == 12 and c["marcadoresH"][0]["estilo"] == "vigor"
        assert all(q["texto"] for q in vm.quebras)
        vm.executarAblacao()
        apoio_v2.esperar_ocioso(ctx)
        assert vm.ablacaoEstado == "pronta" and len(vm.ablacao) == 10
        ctx.girar(0.3)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_cancelar_volta_ao_estado_anterior(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        estado = vm.estado
        vm.varrer()
        vm.cancelar()
        assert not vm.varrendo and vm.estado == estado and vm.curvas == []
        apoio_v2.esperar_ocioso(ctx)
        ctx.girar(0.2)
        assert vm.curvas == [] and vm.estado == estado
    finally:
        ctx.fechar()


def test_csv_sem_vetor_e_com_selo(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        vm.varrer()
        apoio_v2.esperar_ocioso(ctx)
        vm.exportarCsv()
        apoio_v2.esperar_ocioso(ctx)
        arquivos = list((config.RELATORIOS_DIR / "figuras").glob("robustez_*.csv"))
        assert len(arquivos) == 1
        linhas = arquivos[0].read_text(encoding="utf-8-sig").splitlines()
        assert linhas[0] == "# Sintético" and linhas[1] == "# N = 1 imagem"
        assert linhas[2] == "família;nível;rótulo;similaridade"
        dados = linhas[3:]
        assert len(dados) == 96 and all(len(l.split(";")) == 4 for l in dados)
        assert apoio_v2.sem_vetor_128(apoio_v2.props_do_vm(vm))
    finally:
        ctx.fechar()


def test_sem_referencia_avisa(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline, foto=None)
    try:
        lab.carregar_frame(cv2.imread(str(FOTO_BIDEN)), origem="arquivo", rotulo="Arquivo de teste")
        apoio_v2.esperar_ocioso(ctx)
        apoio_v2.esperar_estado(ctx, vm)
        apoio_v2.esperar_ocioso(ctx)
        assert vm.semReferencia and vm.similaridade > 0.99
        assert any(t.startswith("Sem referência:") for t in apoio_v2.textos_visiveis(ctx.janela))
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_previa_removida_ao_desativar(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        assert apoio_v2.imagem_do_provedor(ctx, "lab/robustez/previa").width() == 112
        lab.definirAba("fases")
        ctx.girar(0.2)
        assert apoio_v2.imagem_do_provedor(ctx, "lab/robustez/previa").width() == 1
    finally:
        ctx.fechar()


def test_sem_avisos(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline, foto=None)
    try:
        assert vm.estado == "vazio"
        lab.usarFotoTeste(2)
        apoio_v2.esperar_ocioso(ctx)
        vm.preparar_captura("")
        apoio_v2.esperar_estado(ctx, vm)
        apoio_v2.esperar_ocioso(ctx)
        assert len(vm.curvas) == 8 and vm.ablacaoEstado == "pronta"
        ctx.girar(0.3)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
