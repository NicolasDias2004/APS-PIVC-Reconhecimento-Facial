"""Aba Separação de Resultados (lote L6), no aplicativo Qt completo e com banco temporário."""

from __future__ import annotations

import re

from cofre import base_demo, config
from tests import apoio_qt, apoio_v2
from tests.apoio_interface import FOTO_BIDEN, FOTO_BIDEN_2, FOTO_OBAMA, FOTO_OBAMA_2
from tests.apoio_v2 import _config_isolada  # noqa: F401

_ZERO_SECO = re.compile(r"(^|[^\d,])0(,0+)? ?%")


def _abrir(ctx):
    return apoio_v2.abrir_aba(ctx, "resultados", "separacao")


def _calcular(ctx, vm, protocolo: str) -> str:
    vm.definirProtocolo(protocolo)
    vm.calcular()
    return apoio_v2.esperar_estado(ctx, vm, 60)


def _textos_do_vm(vm) -> list[str]:
    textos: list[str] = []

    def andar(v):
        if isinstance(v, str):
            textos.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                andar(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                andar(x)

    andar(apoio_v2.props_do_vm(vm))
    andar(vm.pontos.itens())
    return textos


def _cadastrar_dois(ctx):
    apoio_v2.cadastrar(ctx, "Fulano Teste", "T-1", 1, [FOTO_BIDEN, FOTO_BIDEN_2])
    apoio_v2.cadastrar(ctx, "Beltrano Teste", "T-2", 2, [FOTO_OBAMA, FOTO_OBAMA_2])


def test_fotos_de_teste_ficam_em_poucos(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        vm = _abrir(ctx)
        assert vm.estado == "vazio"
        assert _calcular(ctx, vm, "fotos_teste") == "poucos"
        assert vm.ficha["paresGenuinos"] == "2" and vm.ficha["paresImpostores"] == "4"
        assert len(vm.cartoes) == 8 and vm.pontos.contagem == len(vm.pontosLinhas) >= 11
        assert "N genuínos = 2" in vm.avisoPoucos and "N impostores = 4" in vm.avisoPoucos
        assert [d["nome"] for d in vm.descritores] == ["SFace", "LBP · cosseno", "LBP · qui-quadrado"]
        assert vm.histograma["n"] and vm.histograma["series"][1]["cor"] == "neutro"
        assert apoio_v2.sem_vetor_128(apoio_v2.props_do_vm(vm))
        assert any("Amostra pequena" in t for t in apoio_v2.textos_visiveis(ctx.janela))
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_limiar_de_estudo_nao_muda_config(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        antes, limiar = apoio_v2.retrato_parametros(), config.LIMIAR_COSSENO
        vm = _abrir(ctx)
        _calcular(ctx, vm, "fotos_teste")
        vm.definirLimiarEstudo(0.42)
        ctx.girar(0.2)
        assert vm.limiarEstudo == 0.42 and vm.limiarVigor == limiar
        assert vm.noEstudo["frase"].startswith("Se o limiar fosse 0,420: FMR ")
        assert [m["estilo"] for m in vm.histograma["marcadoresV"]] == ["vigor", "estudo"]
        assert "Parâmetros de estudo" in vm.histograma["selos"]
        assert apoio_v2.retrato_parametros() == antes and config.LIMIAR_COSSENO == limiar
        assert not (config.DATA_DIR / "config_usuario.json").exists()
        textos = apoio_v2.textos_visiveis(ctx.janela)
        assert any(t.startswith("Simulação. O limiar do sistema continua") for t in textos)
        assert not any("Aplicar" in t for t in textos)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_galeria_carimba_mesma_sessao(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        _cadastrar_dois(ctx)
        antes = apoio_v2.retrato_banco(tmp_path / "t.db")
        vm = _abrir(ctx)
        assert _calcular(ctx, vm, "galeria") == "poucos"
        assert vm.selos == ["Mesma sessão · otimista"]
        assert vm.ficha["paresGenuinos"] == "2" and vm.ficha["paresImpostores"] == "4"
        assert vm.descritores == []
        assert apoio_v2.sem_vetor_128(apoio_v2.props_do_vm(vm))
        assert apoio_v2.retrato_banco(tmp_path / "t.db") == antes
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_galeria_da_base_demo_carimba_demonstracao(qapp, tmp_path, monkeypatch, pipeline):
    raiz = tmp_path / "demo"
    apoio_v2.usar_pastas(monkeypatch, raiz)
    caminho = base_demo.gerar(raiz, raiz_permitida=raiz, pipeline=pipeline)
    ctx = apoio_qt.criar_contexto(qapp, caminho, pipeline=pipeline)
    try:
        assert ctx.apl.extensoes.baseDemonstracao
        vm = _abrir(ctx)
        assert _calcular(ctx, vm, "galeria") == "poucos"
        assert vm.ficha["paresGenuinos"] == "2" and vm.ficha["paresImpostores"] == "4"
        assert vm.selos == ["Base de demonstração"]
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_zero_erro_mostra_teto(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        vm = _abrir(ctx)
        _calcular(ctx, vm, "fotos_teste")
        assert vm.semErro
        assert vm.textoSemErro.startswith("Nenhum erro observado: com 4 pares impostores e 2 genuínos")
        assert "teto de erro é 75,00 %" in vm.textoSemErro
        fmr = next(c for c in vm.cartoes if c["rotulo"] == "FMR no limiar em vigor")
        assert fmr["valor"] == "0 de 4" and fmr["detalhe"] == "teto 75,00 %"
        secos = [t for t in _textos_do_vm(vm) + apoio_v2.textos_visiveis(ctx.janela) if _ZERO_SECO.search(t)]
        assert secos == []
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_sem_avisos(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        vm = _abrir(ctx)
        _calcular(ctx, vm, "fotos_teste")
        vm.definirLimiarEstudo(0.2)
        vm.definirLimiarEstudo(0.9)
        ctx.girar(0.2)
        vm.exportarCsv()
        assert apoio_v2.esperar_ocioso(ctx)
        csvs = list((config.RELATORIOS_DIR).glob("pontos_operacao_*.csv"))
        assert len(csvs) == 1
        texto = csvs[0].read_text(encoding="utf-8")
        assert texto.startswith("# Fotos de teste · 4 imagens") and "# N = 2 pares genuínos" in texto
        assert _calcular(ctx, vm, "galeria") == "vazio"          # galeria sem cadastro
        vm.definirProtocolo("pasta")
        ctx.girar(0.2)
        assert vm.estado == "vazio"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
