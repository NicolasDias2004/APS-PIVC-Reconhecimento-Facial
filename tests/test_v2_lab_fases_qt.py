"""Aba Fases do Laboratório no aplicativo Qt: estações, parâmetros de estudo e comparação com a galeria."""

import numpy as np

from tests import apoio_v2
from tests.apoio_v2 import _config_isolada  # noqa: F401
from tests.apoio_interface import FOTO_BIDEN, FOTO_OBAMA_2


def _abrir(qapp, tmp_path, pipeline, foto=0):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    vm = apoio_v2.abrir_aba(ctx, "laboratorio", "fases")
    lab = ctx.apl.extensoes.obter("laboratorio")
    if foto is not None:
        lab.usarFotoTeste(foto)
        assert apoio_v2.esperar_ocioso(ctx) and not lab.processando, lab.erro
        apoio_v2.esperar_estado(ctx, vm)
    return ctx, vm, lab


def _nomes(ctx) -> list[str]:
    return [n.lower() for n in apoio_v2.nomes_do_banco(ctx.apl.banco.caminho)]


def test_fases_com_foto_de_teste(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        assert vm.estado == "pronto" and vm.temRosto
        assert [t["fase"] for t in vm.tempos] == [1, 2, 3, 4, 5]
        assert vm.orcamento > 0 and vm.tempos[1]["texto"].endswith(" ms")
        assert set(vm.leituras) == {"1", "2", "3", "4", "5"} and vm.leituras["3"][0][0] == "Rostos detectados"
        assert [s["nome"] for s in vm.histograma["series"]] == ["Original", "Equalização global", "CLAHE"]
        assert len(vm.matriz) == 2 and all(len(linha) == 3 for linha in vm.matriz)
        assert "escala" in vm.matrizDetalhe["texto"] and vm.indiceQualidade >= 0 and len(vm.qualidade) == 8
        assert -1 <= vm.similaridadeReferencia <= 1 and vm.similaridadeReferencia > 0.3
        assert vm.estacao == 2
        for e in (1, 3, 4, 5, 2):
            vm.definirEstacao(e)
            ctx.girar(0.1)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_parametros_de_estudo_nao_mudam_config(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        antes = apoio_v2.retrato_parametros()
        amostra_lab_antes = lab.amostra
        vm.definirParametro("clip", 4.0)
        vm.definirParametro("kernel", 6)           # par vira ímpar
        assert vm.parametros["kernel"] in (5, 7) and vm.foraDoPadrao
        ctx.girar(0.3)
        apoio_v2.esperar_estado(ctx, vm)
        assert vm.estado == "pronto" and "Parâmetros de estudo" in vm.histograma["selos"]
        assert apoio_v2.retrato_parametros() == antes
        assert lab.amostra is amostra_lab_antes and lab.amostra.parametros.padrao
        assert any("Prévia com parâmetros de estudo" in t for t in apoio_v2.textos_visiveis(ctx.janela))
        vm.restaurarPadroes()
        apoio_v2.esperar_estado(ctx, vm)
        assert not vm.foraDoPadrao and vm.parametros == vm.padroes
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_comparacao_so_por_botao(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        apoio_v2.cadastrar(ctx, "Barack Teste", "M1", 3, [FOTO_OBAMA_2])
        apoio_v2.esperar_estado(ctx, vm)
        assert vm.rankingEstado == "nao_pedido" and vm.ranking == []
        lab.usarFotoTeste(1)
        apoio_v2.esperar_ocioso(ctx)
        apoio_v2.esperar_estado(ctx, vm)
        assert vm.rankingEstado == "nao_pedido"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_comparacao_sem_nome_abaixo_do_limiar(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)      # amostra: Pessoa de teste A (biden)
    try:
        apoio_v2.cadastrar(ctx, "Barack Teste", "M1", 3, [FOTO_OBAMA_2])
        apoio_v2.esperar_estado(ctx, vm)
        ctx.apl.extensoes.obter("privacidade").definirMostrarNomes(True)
        vm.definirEstacao(5)
        vm.compararComGaleria()
        apoio_v2.esperar_ocioso(ctx)
        assert vm.rankingEstado == "pronto"
        assert [c["rotulo"] for c in vm.ranking] == ["Candidato 1"] and not vm.ranking[0]["acima"]
        visiveis = " ".join(apoio_v2.textos_visiveis(ctx.janela)).lower()
        assert not any(n in visiveis or n in repr(apoio_v2.props_do_vm(vm)).lower() for n in _nomes(ctx))
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_comparacao_nome_so_com_a_chave(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        apoio_v2.cadastrar(ctx, "Joe Teste", "M2", 2, [FOTO_BIDEN])
        apoio_v2.esperar_estado(ctx, vm)
        vm.compararComGaleria()
        apoio_v2.esperar_ocioso(ctx)
        assert vm.rankingEstado == "pronto" and vm.ranking[0]["acima"]
        assert vm.ranking[0]["rotulo"] == "Pessoa A"
        assert "joe" not in repr(apoio_v2.props_do_vm(vm)).lower()
        ctx.apl.extensoes.obter("privacidade").definirMostrarNomes(True)
        assert vm.rankingEstado == "nao_pedido"           # a chave não dispara a comparação
        vm.compararComGaleria()
        apoio_v2.esperar_ocioso(ctx)
        assert vm.ranking[0]["rotulo"] == "Joe Teste"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_comparacao_bloqueada_com_terminal_bloqueado(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        ctx.apl.navegar("terminal")
        ctx.girar(0.3)
        apoio_v2.bloquear_terminal(ctx)
        vm = apoio_v2.abrir_aba(ctx, "laboratorio", "fases")
        lab = ctx.apl.extensoes.obter("laboratorio")
        lab.usarFotoTeste(0)
        apoio_v2.esperar_ocioso(ctx)
        apoio_v2.esperar_estado(ctx, vm)
        vm.compararComGaleria()
        assert vm.rankingEstado == "indisponivel"
        assert vm.rankingMotivo == "Comparação indisponível: o terminal está bloqueado."
        assert ctx.apl.extensoes.trabalhos.ocioso()
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_comparacao_indisponivel_com_quadro_da_camera(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline, foto=None)
    try:
        apoio_v2.cadastrar(ctx, "Barack Teste", "M1", 3, [FOTO_OBAMA_2])
        lab.usarFotoTeste(1)                            # referência e amostra de foto
        apoio_v2.esperar_ocioso(ctx)
        banco = apoio_v2.retrato_banco(tmp_path / "t.db")
        lab.carregar_frame(apoio_v2.quadro_webcam(FOTO_BIDEN), origem="camera", rotulo="Quadro congelado")
        apoio_v2.esperar_ocioso(ctx)
        apoio_v2.esperar_estado(ctx, vm)
        assert lab.amostraOrigem == "camera" and not vm.comparacaoPermitida
        vm.compararComGaleria()
        assert vm.rankingEstado == "indisponivel" and vm.rankingMotivo.startswith("Quadro da câmera")
        assert ctx.apl.extensoes.trabalhos.ocioso()
        assert apoio_v2.retrato_banco(tmp_path / "t.db") == banco
        assert vm.similaridadeReferencia > 0
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_comparacao_nao_grava(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        apoio_v2.cadastrar(ctx, "Joe Teste", "M2", 2, [FOTO_BIDEN])
        apoio_v2.esperar_estado(ctx, vm)
        antes = apoio_v2.retrato_banco(tmp_path / "t.db")
        vm.compararComGaleria()
        apoio_v2.esperar_ocioso(ctx)
        assert vm.rankingEstado == "pronto"
        assert apoio_v2.retrato_banco(tmp_path / "t.db") == antes
    finally:
        ctx.fechar()


def test_assinatura_e_imagem_e_some_ao_desativar(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        img = apoio_v2.imagem_do_provedor(ctx, "lab/fases/assinatura")
        assert (img.width(), img.height()) == (768, 160) and apoio_v2.cores_distintas(img, 2) > 1
        assert apoio_v2.imagem_do_provedor(ctx, "lab/fases/alinhado").width() == 112
        ctx.apl.extensoes.obter("laboratorio").definirAba("robustez")
        ctx.girar(0.2)
        assert apoio_v2.imagem_do_provedor(ctx, "lab/fases/assinatura").width() == 1
    finally:
        ctx.fechar()


def test_sem_vetor_em_nenhuma_prop(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline)
    try:
        apoio_v2.cadastrar(ctx, "Joe Teste", "M2", 2, [FOTO_BIDEN])
        apoio_v2.esperar_estado(ctx, vm)
        vm.compararComGaleria()
        apoio_v2.esperar_ocioso(ctx)
        props = apoio_v2.props_do_vm(vm)
        assert apoio_v2.sem_vetor_128(props)
        assert not any(isinstance(v, (list, tuple)) and len(v) == 128 for v in props.values())
        assert not any(isinstance(v, np.ndarray) for v in props.values())
    finally:
        ctx.fechar()


def test_sem_avisos(qapp, tmp_path, pipeline):
    ctx, vm, lab = _abrir(qapp, tmp_path, pipeline, foto=None)
    try:
        assert vm.estado == "vazio"
        assert "Nenhuma amostra" in apoio_v2.textos_visiveis(ctx.janela)
        lab.usarFotoTeste(2)
        apoio_v2.esperar_ocioso(ctx)
        apoio_v2.esperar_estado(ctx, vm)
        vm.preparar_captura("estacao3")
        apoio_v2.esperar_estado(ctx, vm)
        assert vm.estacao == 3
        ctx.girar(0.2)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
