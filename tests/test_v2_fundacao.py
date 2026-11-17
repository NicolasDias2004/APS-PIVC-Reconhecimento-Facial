"""Fundação da versão 2: trabalhos em segundo plano, registro defensivo dos ViewModels novos, contrato
de recálculo das abas, privacidade, as três páginas novas e as nove abas no QML, guarda de teclas do
modo porta, Laboratório (fotos de teste, arquivo e câmera só em pré-visualização), exportação de figuras
e selo da base de demonstração. Câmera falsa, banco temporário e pipeline real."""

from __future__ import annotations

import importlib
import sqlite3
import threading
import time
from datetime import datetime, timedelta

import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, Qt, QUrl
from PySide6.QtQml import QQmlComponent

from cofre import base_demo, leitura_ro
from cofre.banco import Banco
from cofre.qt import aplicacao as mod_aplicacao
from cofre.qt import extensoes as mod_extensoes
from cofre.qt.base_v2 import ESTADOS, PaginaAbasVM, ViewModelAba, VMIndisponivel
from cofre.qt.camera import ServicoCamera
from cofre.qt import vm_figuras, vm_laboratorio
from cofre.qt.trabalhos import Cancelado, Trabalho, Trabalhos
from cofre.qt.vm_privacidade import rotulo_de, rotulos_para
from tests import apoio_v2
from tests.apoio_interface import FOTO_OBAMA, FOTO_OBAMA_2
from tests.apoio_v2 import _config_isolada  # noqa: F401

SEIS = ("terminal", "cadastro", "usuarios", "acessos", "avaliacao", "config")
CHAVES = tuple(chave for chave, _, _ in mod_extensoes.REGISTRO)
CHAVES_DE_ABA = tuple(chave for abas in mod_extensoes.ABAS.values() for _, _, chave, _ in abas)
ERRO_CARGA = "Esta tela não pôde ser carregada"         # título do ErroCarga.qml
PAGINAS_QML = {"painel": "paginaPainel", "laboratorio": "paginaLaboratorio", "resultados": "paginaResultados"}


# ---------------------------------------------------------------------------- apoio deste arquivo
class AbaContadora(ViewModelAba):
    """Aba de teste: conta toda chamada a `recarregar`, sem a conferência de ativação que as abas de
    verdade fazem. Assim o contador mostra o que a base chamou."""

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self.recargas = 0

    def recarregar(self) -> None:
        self.recargas += 1


class AbaSempre(AbaContadora):
    SEMPRE_RECALCULA = True


class AbaComTrabalho(ViewModelAba):
    """Aba de teste com um cálculo de verdade no pool: roda até `solta` ou até ser cancelado."""

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self.solta = threading.Event()
        self.falha = ""
        self.limpezas = 0
        self.resultados: list[int] = []

    def recarregar(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        self._definir("erro", "")
        self._definir("estado", "carregando")
        self.trabalho.executar(self._calcular, self._ao_calcular)

    def _calcular(self, sinal) -> int:
        for i in range(1000):                       # 10 s se ninguém soltar nem cancelar
            sinal.conferir()
            sinal.progresso(i, 1000)
            if self.solta.wait(0.01):
                break
        if self.falha:
            raise RuntimeError(self.falha)
        return 42

    def _ao_calcular(self, resultado, erro: str) -> None:
        if erro:
            self._falhar(erro)
            return
        self.resultados.append(resultado)
        self._definir("estado", "pronto")

    def _limpar_dados(self) -> None:
        self.limpezas += 1


PAGINAS_VISTAS_POR_ORFAO: list[str] = []


class AbaQueFalhaAoConstruir(ViewModelAba):
    """Liga um sinal do aplicativo e só então falha: o registro tem de destruir o que sobrou."""

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        aplicacao.paginaMudou.connect(self._ao_mudar_pagina)
        raise RuntimeError("construtor quebrado de propósito")

    def _ao_mudar_pagina(self) -> None:
        PAGINAS_VISTAS_POR_ORFAO.append(self.app.pagina)


def _trocar_no_registro(monkeypatch, chave: str, modulo: str, classe: str) -> None:
    """Põe outra classe no lugar de uma linha de REGISTRO (vale para a próxima Aplicacao criada)."""
    assert chave in CHAVES
    linhas = tuple((c, modulo, classe) if c == chave else (c, m, k) for c, m, k in mod_extensoes.REGISTRO)
    monkeypatch.setattr(mod_extensoes, "REGISTRO", linhas)


def _visivel(ctx, nome: str) -> bool:
    """Há na árvore visual da janela um item visível com esse `objectName`."""
    return any(item.isVisible() for item in apoio_v2.itens(ctx.janela, lambda item: item.objectName() == nome))


def _sem_avisos(ctx) -> None:
    """Nenhum aviso de QML até aqui; se houver, a falha mostra o texto inteiro de cada um."""
    avisos = ctx.avisos_qml()
    assert avisos == [], "\n".join(avisos)


def _girar(qapp, segundos: float) -> None:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
        time.sleep(0.002)


def _esperar(qapp, condicao, segundos: float = 5.0) -> bool:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        if condicao():
            return True
        _girar(qapp, 0.01)
    return bool(condicao())


@pytest.fixture
def trabalhos(qapp):
    """Pool da v2 sozinho, sem o aplicativo; ao fim nada fica rodando."""
    pool = Trabalhos()
    yield pool
    pool.cancelar_tudo()
    assert pool.esperar(5000)
    _girar(qapp, 0.05)


def _varredura(iniciou: threading.Event, parou: threading.Event):
    """Trabalho longo e cooperativo (30 s se ninguém cancelar), como uma varredura de robustez."""
    def fn(sinal):
        iniciou.set()
        try:
            for i in range(3000):
                sinal.conferir()
                sinal.progresso(i, 3000)
                time.sleep(0.01)
        finally:
            parou.set()
        return "fim"
    return fn


# ---------------------------------------------------------------------------- trabalhos
def test_trabalhos_ocioso(qapp, trabalhos):
    um, outro = Trabalho(trabalhos), Trabalho(trabalhos)
    mudancas = []
    um.ocupadoMudou.connect(lambda: mudancas.append(um.ocupado))
    assert trabalhos.ocioso() and not um.ocupado
    interface = threading.get_ident()
    solta, vistos = threading.Event(), []

    def fn(sinal):
        solta.wait(5)
        return threading.get_ident()

    def ao_terminar(resultado, erro):
        vistos.append((resultado != interface, erro, threading.get_ident() == interface, trabalhos.ocioso()))

    um.executar(fn, ao_terminar)
    assert not trabalhos.ocioso() and um.ocupado and not outro.ocupado
    _girar(qapp, 0.1)
    assert not trabalhos.ocioso() and vistos == []
    solta.set()
    assert trabalhos.esperar(3000)                  # fn acabou no pool, mas o ao_terminar ainda não rodou:
    assert not trabalhos.ocioso() and vistos == []  # o pedido continua em andamento
    assert _esperar(qapp, lambda: vistos)
    # fn rodou fora da thread da interface, o ao_terminar nela, e dentro dele o pedido ainda contava
    assert vistos == [(True, "", True, False)]
    assert trabalhos.ocioso() and not um.ocupado and mudancas == [True, False]


def test_trabalho_erro_vira_texto(qapp, trabalhos, capfd):
    trabalho, vistos = Trabalho(trabalhos), []

    class SemTexto(Exception):
        pass

    def com_texto(sinal):
        raise ValueError("deu ruim")

    def sem_texto(sinal):
        raise SemTexto()

    def callback_quebrado(resultado, erro):
        raise RuntimeError("callback quebrado de propósito")

    trabalho.executar(com_texto, lambda r, e: vistos.append((r, e)))
    assert _esperar(qapp, lambda: len(vistos) == 1)
    trabalho.executar(sem_texto, lambda r, e: vistos.append((r, e)))
    assert _esperar(qapp, lambda: len(vistos) == 2)
    assert vistos == [(None, "deu ruim"), (None, "SemTexto")]
    assert capfd.readouterr().err.count("Traceback") == 2
    trabalho.executar(lambda sinal: 1, callback_quebrado)       # exceção no ao_terminar não prende o Trabalho
    assert _esperar(qapp, trabalhos.ocioso)
    assert "callback quebrado de propósito" in capfd.readouterr().err
    trabalho.executar(lambda sinal: 2, lambda r, e: vistos.append((r, e)))
    assert _esperar(qapp, lambda: len(vistos) == 3) and vistos[-1] == (2, "")


def test_trabalho_avisa_progresso_sem_inundar_a_interface(qapp, trabalhos):
    trabalho, fracoes, vistos = Trabalho(trabalhos), [], []
    trabalho.progresso.connect(fracoes.append)

    def fn(sinal):
        inicio = time.perf_counter()
        for i in range(400):
            sinal.progresso(i, 400)
            time.sleep(0.0005)
        sinal.progresso(400, 400)
        return time.perf_counter() - inicio

    trabalho.executar(fn, lambda r, e: vistos.append((r, e)))
    assert _esperar(qapp, lambda: vistos)
    duracao, erro = vistos[0]
    assert erro == ""
    assert fracoes[0] == 0.0 and fracoes[-1] == 1.0 and fracoes == sorted(fracoes)
    assert 2 <= len(fracoes) <= duracao * 20 + 2    # ~20 avisos por segundo, mais o de conclusão


def test_trabalho_o_ultimo_vence(qapp, trabalhos):
    trabalho = Trabalho(trabalhos)
    solta, rodou, vistos, sinais = threading.Event(), [], [], {}

    def a(sinal):
        sinais["a"] = sinal
        rodou.append("a")
        solta.wait(5)
        return "a"

    def b(sinal):
        rodou.append("b")
        return "b"

    def c(sinal):
        rodou.append("c")
        return "c"

    trabalho.executar(a, lambda r, e: vistos.append(r))
    assert _esperar(qapp, lambda: rodou == ["a"])
    trabalho.executar(b, lambda r, e: vistos.append(r))     # cancela `a` e fica esperando a vez
    trabalho.executar(c, lambda r, e: vistos.append(r))     # toma o lugar de `b`, que nem começa
    assert sinais["a"].cancelado() and trabalho.ocupado
    with pytest.raises(Cancelado):
        sinais["a"].conferir()
    _girar(qapp, 0.15)
    assert rodou == ["a"] and vistos == []          # um rodando e um pendente, mesmo com thread livre no pool
    solta.set()
    assert _esperar(qapp, lambda: vistos)
    _girar(qapp, 0.1)
    assert vistos == ["c"] and rodou == ["a", "c"]  # o resultado de `a` foi descartado
    assert trabalhos.ocioso()


def test_trabalho_cancelado_nao_chama_callback(qapp, trabalhos):
    trabalho, vistos = Trabalho(trabalhos), []
    iniciou, parou = threading.Event(), threading.Event()
    trabalho.executar(_varredura(iniciou, parou), lambda r, e: vistos.append((r, e)))
    assert iniciou.wait(3)
    trabalho.cancelar()
    assert not trabalho.ocupado and trabalhos.ocioso()
    assert parou.wait(3) and trabalhos.esperar(3000)        # cooperativo: parou no conferir() seguinte
    _girar(qapp, 0.2)
    assert vistos == []
    trabalho.cancelar()                                     # cancelar sem pedido não faz nada
    trabalho.executar(lambda sinal: 7, lambda r, e: vistos.append((r, e)))
    assert _esperar(qapp, lambda: vistos) and vistos == [(7, "")]   # o Trabalho segue utilizável
    trabalhos.cancelar_tudo()                               # depois do encerramento, pedido tardio é ignorado
    trabalho.executar(lambda sinal: 8, lambda r, e: vistos.append((r, e)))
    assert not trabalho.ocupado and trabalhos.ocioso()
    _girar(qapp, 0.1)
    assert vistos == [(7, "")]


# ---------------------------------------------------------------------------- registro defensivo
def test_registro_carrega_e_expoe_cada_chave(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        assert apl.v2 is x and x.trabalhos.parent() is x
        assert tuple(apl._vms) == mod_aplicacao.PAGINAS
        for chave, modulo, classe in mod_extensoes.REGISTRO:
            vm = x.obter(chave)
            assert getattr(x, chave) is vm                  # a propriedade que o QML lê como app.v2.<chave>
            assert x.erroDe(chave) == "", (chave, x.erroDe(chave))
            assert (type(vm).__module__, type(vm).__name__) == (modulo, classe)
        assert x.paginas() == {pagina: apl._vms[pagina] for pagina in mod_extensoes.PAGINAS_V2}
        assert all(isinstance(x.obter(chave), ViewModelAba) for chave in CHAVES_DE_ABA)
        # as abas de cada página, como o QML recebe
        for pagina, linhas in mod_extensoes.ABAS.items():
            assert x.abasDe(pagina) == [{"valor": valor, "texto": texto, "chaveVm": chave, "fonte": fonte, "erro": ""}
                                        for valor, texto, chave, fonte in linhas]
        assert [(a["valor"], a["texto"], a["chaveVm"], a["fonte"]) for a in x.abasDe("painel")] == [
            ("geral", "Visão geral", "painelGeral", "PainelGeral.qml"),
            ("incidentes", "Incidentes", "painelIncidentes", "PainelIncidentes.qml"),
            ("integridade", "Integridade", "painelIntegridade", "PainelIntegridade.qml")]
        assert [(a["valor"], a["chaveVm"]) for a in x.abasDe("laboratorio")] == [
            ("fases", "labFases"), ("robustez", "labRobustez"), ("explicabilidade", "labExplicabilidade")]
        assert [(a["valor"], a["chaveVm"]) for a in x.abasDe("resultados")] == [
            ("separacao", "resSeparacao"), ("qualidade", "resQualidade"), ("galeria", "resGaleria")]
        assert x.abasDe("terminal") == []
        # chave que ninguém registrou: sempre vem um objeto, com o erro em texto
        fantasma = x.obter("naoExiste")
        assert isinstance(fantasma, VMIndisponivel) and x.obter("naoExiste") is fantasma
        assert x.erroDe("naoExiste") != "" and fantasma.erroCarga == x.erroDe("naoExiste")
        fantasma.ativar()                           # ganchos vazios: nada acontece, nada levanta
        fantasma.desativar()
        fantasma.ao_banco_alterado()
        fantasma.ao_pipeline_pronto()
    finally:
        ctx.fechar()


def test_vm_quebrado_nao_derruba_o_app(qapp, tmp_path, pipeline, monkeypatch, capfd):
    pasta = tmp_path / "modulos"
    pasta.mkdir()
    (pasta / "vm_quebrado_de_teste.py").write_text('raise RuntimeError("módulo quebrado de propósito")\n',
                                                    encoding="utf-8")
    monkeypatch.syspath_prepend(str(pasta))
    _trocar_no_registro(monkeypatch, "painelIncidentes", "vm_quebrado_de_teste", "PainelIncidentesVM")
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        assert ctx.janela is not None, ctx.avisos
        erro = x.erroDe("painelIncidentes")
        assert "RuntimeError" in erro and "módulo quebrado de propósito" in erro
        quebrado = x.obter("painelIncidentes")
        assert isinstance(quebrado, VMIndisponivel) and quebrado.erroCarga == erro
        assert [a["erro"] for a in x.abasDe("painel")] == ["", erro, ""]
        assert "módulo quebrado de propósito" in capfd.readouterr().err         # o traceback foi impresso
        # a página da aba quebrada abre, mostra a aba quebrada e sai dela sem exceção
        painel = x.obter("painel")
        apl.navegar("painel")
        painel.definirAba("incidentes")
        ctx.girar(0.2)
        assert apl.pagina == "painel" and painel.aba == "incidentes"
        textos = apoio_v2.textos_visiveis(ctx.janela)
        assert ERRO_CARGA in textos and erro in textos              # o ErroCarga no lugar da aba, com o texto
        assert not _visivel(ctx, "abaPainelIncidentes")
        apl.banco_alterado()
        apl.usar_pipeline(pipeline)
        painel.definirAba("integridade")
        ctx.girar(0.2)
        assert x.obter("painelIntegridade").ativa and _visivel(ctx, "abaPainelIntegridade")
        assert ERRO_CARGA not in apoio_v2.textos_visiveis(ctx.janela)
        apl.navegar("usuarios")
        # as outras 8 abas carregaram e funcionam
        for chave in CHAVES_DE_ABA:
            if chave == "painelIncidentes":
                continue
            vm = x.obter(chave)
            assert isinstance(vm, ViewModelAba) and x.erroDe(chave) == "", chave
            vm.ativar()
            assert vm.ativa and vm.estado in ESTADOS, chave
            vm.desativar()
            assert not vm.ativa
        # o terminal e as páginas antigas seguem normais
        for pagina in SEIS:
            apl.navegar(pagina)
            ctx.girar(0.2)
            assert apl.pagina == pagina
        assert "Traceback" not in capfd.readouterr().err
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_construtor_quebrado_e_classe_ausente_viram_indisponivel(qapp, tmp_path, pipeline, monkeypatch):
    PAGINAS_VISTAS_POR_ORFAO.clear()
    _trocar_no_registro(monkeypatch, "resQualidade", __name__, "AbaQueFalhaAoConstruir")
    _trocar_no_registro(monkeypatch, "resGaleria", __name__, "ClasseQueNaoExiste")
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        assert "construtor quebrado de propósito" in x.erroDe("resQualidade")
        assert "AttributeError" in x.erroDe("resGaleria")
        assert isinstance(x.obter("resQualidade"), VMIndisponivel) and isinstance(x.obter("resGaleria"), VMIndisponivel)
        assert x.erroDe("resSeparacao") == "" and x.erroDe("resultados") == ""
        # o objeto que falhou no meio do construtor foi destruído: não reage mais ao aplicativo
        resultados = x.obter("resultados")
        for valor in ("qualidade", "galeria", "separacao"):
            resultados.definirAba(valor)
        apl.navegar("resultados")
        apl.navegar("usuarios")
        ctx.girar(0.1)
        assert apl.pagina == "usuarios" and PAGINAS_VISTAS_POR_ORFAO == []
        assert x.trabalhos.ocioso()
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_app_v2_no_qml_sem_avisos(qapp, tmp_path, pipeline, monkeypatch):
    _trocar_no_registro(monkeypatch, "painelGeral", __name__, "AbaContadora")
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    obj = None
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        componente = QQmlComponent(ctx.motor)
        componente.setData(b"""
import QtQml
QtObject {
    property var chaves: []
    property int objetos: { var n = 0; for (var i = 0; i < chaves.length; ++i) if (app.v2[chaves[i]]) n += 1; return n }
    property bool demo: app.v2.baseDemonstracao
    property bool usado: app.v2.quiosqueUsado
    property bool telaCheia: app.v2.quiosqueTelaCheia
    property bool sobreposicao: app.v2.sobreposicaoAberta
    property bool quiosqueAtivo: app.v2.quiosque.ativo
    property string erroPainel: app.v2.erroDe("painel")
    property string abaPainel: app.v2.painel.aba
    property string periodo: app.v2.painel.periodo
    property var abasPainel: app.v2.painel.abas()
    property var abasResultados: app.v2.abasDe("resultados")
    property bool nomes: app.v2.privacidade.mostrarNomes
    property string estadoGeral: app.v2.painelGeral.estado
    property string erroGeral: app.v2.painelGeral.erro
    property real progressoGeral: app.v2.painelGeral.progresso
    function mexer() {
        app.v2.painelGeral.recarregar()
        app.v2.painelGeral.pedir_recarga()
        app.v2.painelGeral.cancelar()
        app.v2.privacidade.definirMostrarNomes(true)
        app.v2.painel.definirPeriodo("24h")
        app.v2.painel.atualizar()
        app.v2.painel.definirAba("integridade")
        app.v2.quiosque.definirTelaCheia(true)
        app.v2.entrarQuiosque()
    }
    function sair() { app.v2.sairQuiosque() }
}
""", QUrl())
        obj = componente.createWithInitialProperties({"chaves": list(CHAVES)})
        assert obj is not None, [e.toString() for e in componente.errors()]
        assert obj.property("objetos") == len(CHAVES)
        assert obj.property("demo") is False and obj.property("erroPainel") == ""
        assert (obj.property("abaPainel"), obj.property("periodo"), obj.property("nomes")) == ("geral", "tudo", False)
        assert (obj.property("estadoGeral"), obj.property("erroGeral"), obj.property("progressoGeral")) == ("vazio", "", -1.0)
        assert [a["valor"] for a in obj.property("abasPainel")] == ["geral", "incidentes", "integridade"]
        assert [a["fonte"] for a in obj.property("abasResultados")] == ["ResSeparacao.qml", "ResQualidade.qml", "ResGaleria.qml"]
        geral = x.obter("painelGeral")
        apl.navegar("painel")
        assert geral.recargas == 1
        obj.metaObject().invokeMethod(obj, "mexer")
        ctx.girar(0.3)
        assert geral.recargas == 3                  # recarregar() e pedir_recarga() chamados pelo QML
        assert (obj.property("abaPainel"), obj.property("periodo"), obj.property("nomes")) == ("integridade", "24h", True)
        assert apl.pagina == "terminal"
        assert (obj.property("usado"), obj.property("sobreposicao"), obj.property("telaCheia")) == (True, True, True)
        assert obj.property("quiosqueAtivo") is True
        obj.metaObject().invokeMethod(obj, "sair")
        ctx.girar(0.1)
        assert (obj.property("usado"), obj.property("sobreposicao"), obj.property("telaCheia")) == (True, False, False)
        _sem_avisos(ctx)
    finally:
        if obj is not None:
            obj.deleteLater()
            ctx.girar(0.05)
        ctx.fechar()


def test_construir_nao_trabalha(qapp, tmp_path, pipeline, monkeypatch):
    caminho = tmp_path / "t.db"
    Banco(caminho).fechar()
    apoio_v2.semear_acessos(caminho, [
        {"data_hora": "2026-01-05T10:00:00", "resultado": "NEGADO_DESCONHECIDO", "similaridade": 0.21},
        {"data_hora": "2026-01-05T10:00:09", "resultado": "NEGADO_MULTIPLOS"}])
    antes = apoio_v2.retrato_banco(caminho)
    abrir_de_verdade, aberturas = leitura_ro.abrir, []

    def abrir(caminho_db, timeout=2.0):
        aberturas.append(timeout)
        return abrir_de_verdade(caminho_db, timeout)

    executar_de_verdade, pedidos = Trabalho.executar, []

    def executar(self, fn, ao_terminar):
        pedidos.append(type(self.parent()).__name__)
        executar_de_verdade(self, fn, ao_terminar)

    iniciar_de_verdade, cameras = ServicoCamera.iniciar, []

    def iniciar(self, processador):
        cameras.append(processador)
        iniciar_de_verdade(self, processador)

    monkeypatch.setattr(leitura_ro, "abrir", abrir)
    monkeypatch.setattr(Trabalho, "executar", executar)
    monkeypatch.setattr(ServicoCamera, "iniciar", iniciar)
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        ctx.girar(0.3)
        na_construcao = list(aberturas)
        # no máximo a leitura do marcador de demonstração, com espera curta
        assert len(na_construcao) <= 1 and all(timeout <= 0.2 for timeout in na_construcao)
        assert pedidos == [] and cameras == []      # nenhum trabalho pedido, câmera nunca ligada
        assert x.baseDemonstracao is False
        assert x.trabalhos.ocioso()
        assert apl.camera.estado == "desligada" and apl.pagina == ""
        for chave in CHAVES_DE_ABA:
            vm = x.obter(chave)
            assert not vm.ativa and not vm.trabalho.ocupado and (vm.estado, vm.erro) == ("vazio", ""), chave
        assert (x.sobreposicaoAberta, x.quiosqueUsado, x.quiosqueTelaCheia) == (False, False, False)
        assert x.obter("privacidade").mostrarNomes is False
        assert apoio_v2.retrato_banco(caminho) == antes
        assert apl.imagens.requestImage("lab/fases/assinatura", None, None).width() <= 1    # nada publicado
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- navegação e páginas
def test_seis_primeiras_paginas_e_atalhos_iguais(qapp, tmp_path, pipeline):
    assert mod_aplicacao.PAGINAS[:6] == SEIS
    assert mod_aplicacao.PAGINAS[6:] == mod_extensoes.PAGINAS_V2 == ("painel", "laboratorio", "resultados")
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        ctx.apl.navegar("usuarios")
        ctx.girar(0.2)
        apoio_v2.tecla(ctx, Qt.Key.Key_4, Qt.KeyboardModifier.ControlModifier)
        assert ctx.apl.pagina == "acessos"
        apoio_v2.tecla(ctx, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
        assert ctx.apl.pagina == "cadastro"
        for tecla, pagina in ((Qt.Key.Key_7, "painel"), (Qt.Key.Key_8, "laboratorio"), (Qt.Key.Key_9, "resultados")):
            apoio_v2.tecla(ctx, tecla, Qt.KeyboardModifier.ControlModifier)
            assert ctx.apl.pagina == pagina
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_pagina_troca_de_aba_ativa_e_desativa(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        resultados = x.obter("resultados")
        separacao, qualidade, galeria = (x.obter(c) for c in ("resSeparacao", "resQualidade", "resGaleria"))
        assert isinstance(resultados, PaginaAbasVM) and resultados.CHAVE == "resultados"
        assert resultados.aba == "separacao" and resultados.abas() == x.abasDe("resultados")
        assert resultados.vm_aba() is separacao and resultados.vm_aba("galeria") is galeria
        assert resultados.vm_aba("naoexiste") is None
        trocas = []
        resultados.abaMudou.connect(lambda: trocas.append(resultados.aba))
        resultados.definirAba("qualidade")          # página fora da tela: só troca o valor
        assert resultados.aba == "qualidade" and not qualidade.ativa
        resultados.definirAba("naoexiste")
        resultados.definirAba("qualidade")
        assert resultados.aba == "qualidade" and trocas == ["qualidade"]
        apl.navegar("resultados")                   # só a aba atual é ativada
        assert apl.pagina == "resultados"
        assert (separacao.ativa, qualidade.ativa, galeria.ativa) == (False, True, False)
        resultados.definirAba("galeria")
        assert (separacao.ativa, qualidade.ativa, galeria.ativa) == (False, False, True)
        apl.navegar("painel")                       # sair da página desativa a aba; a do painel entra
        assert apl.pagina == "painel" and not galeria.ativa and x.obter("painelGeral").ativa
        apl.navegar("laboratorio")
        assert apl.pagina == "laboratorio" and not x.obter("painelGeral").ativa
        apl.navegar("naoexiste")
        assert apl.pagina == "laboratorio"
        apl.navegar("terminal")
        assert apl.pagina == "terminal" and not any(x.obter(chave).ativa for chave in CHAVES_DE_ABA)
        assert x.trabalhos.ocioso()
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_painel_periodo_e_pedido_de_atualizacao(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        painel = ctx.apl.extensoes.obter("painel")
        periodos, pedidos = [], []
        painel.periodoMudou.connect(lambda: periodos.append(painel.periodo))
        painel.atualizarPedido.connect(lambda: pedidos.append(painel.periodo))
        assert painel.CHAVE == "painel" and painel.aba == "geral"
        assert painel.periodo == "tudo" and painel.desde_iso() is None
        for valor, duracao in (("24h", timedelta(hours=24)), ("7d", timedelta(days=7)), ("30d", timedelta(days=30))):
            painel.definirPeriodo(valor)
            desde = painel.desde_iso()
            assert painel.periodo == valor and len(desde) == 19     # o formato de acessos.data_hora
            assert abs((datetime.now() - duracao) - datetime.fromisoformat(desde)) < timedelta(seconds=5)
        painel.definirPeriodo("ontem")              # inválido: ignorado
        assert painel.periodo == "30d" and periodos == ["24h", "7d", "30d"] and pedidos == ["24h", "7d", "30d"]
        painel.atualizar()
        assert pedidos[-1] == "30d" and len(pedidos) == 4 and len(periodos) == 3
        painel.definirPeriodo("tudo")
        assert painel.desde_iso() is None and len(pedidos) == 5
    finally:
        ctx.fechar()


def test_navegacao_travada_com_sessao_aberta_vale_para_as_novas(qapp, tmp_path, pipeline):
    imagens = [FOTO_OBAMA]
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline, imagens=imagens)
    try:
        apoio_v2.cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA_2])
        apl, x = ctx.apl, ctx.apl.extensoes
        t, s = apl.terminal, apl.sessao
        t.definirLiveness(False)
        t.definirNivel(1)
        apl.navegar("terminal")
        assert ctx.esperar(lambda: s.ativa, 25), (t.estado, t.resultadoTipo)    # sessão aberta pelo backend
        assert ctx.esperar(lambda: apl.camera.estado == "desligada", 5)         # terminal pausado sob a área
        for pagina in mod_extensoes.PAGINAS_V2:
            apl.navegar(pagina)
            assert apl.pagina == "terminal"
        assert not any(x.obter(chave).ativa for chave in CHAVES_DE_ABA)
        x.entrarQuiosque()                          # o modo porta também não abre por cima da área liberada
        assert (x.sobreposicaoAberta, x.quiosqueUsado) == (False, False)
        ctx.girar(0.1)
        assert x.trabalhos.ocioso()
        imagens[0] = np.zeros((480, 640, 3), np.uint8)      # ninguém na frente da câmera ao encerrar
        s.encerrar()
        apl.navegar("painel")
        assert apl.pagina == "painel" and x.obter("painelGeral").ativa
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_quiosque_esqueleto_regra_de_entrada(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        q = x.obter("quiosque")
        sinais = []
        x.sobreposicaoAbertaMudou.connect(lambda: sinais.append(("sobreposicao", x.sobreposicaoAberta)))
        x.quiosqueUsadoMudou.connect(lambda: sinais.append(("usado", x.quiosqueUsado)))
        x.quiosqueTelaCheiaMudou.connect(lambda: sinais.append(("telaCheia", x.quiosqueTelaCheia)))
        assert (q.ativo, q.usado, q.telaCheia, q.telaCheiaAtiva) == (False, False, False, False)
        apl.navegar("usuarios")
        x.entrarQuiosque()                          # leva ao terminal e só então abre
        assert apl.pagina == "terminal" and (q.ativo, q.usado) == (True, True)
        assert (x.sobreposicaoAberta, x.quiosqueUsado, x.quiosqueTelaCheia) == (True, True, False)
        assert sinais == [("sobreposicao", True), ("usado", True)]
        q.definirTelaCheia(True)                    # preferência: vale porque o quiosque está aberto
        assert (q.telaCheia, q.telaCheiaAtiva, x.quiosqueTelaCheia) == (True, True, True)
        assert sinais[-1] == ("telaCheia", True)
        apl.navegar("usuarios")                     # a página deixou de ser o terminal: o quiosque fecha
        assert (q.ativo, q.usado, q.telaCheia, q.telaCheiaAtiva) == (False, True, True, False)
        assert (x.sobreposicaoAberta, x.quiosqueUsado, x.quiosqueTelaCheia) == (False, True, False)
        x.entrarQuiosque()                          # a preferência de tela cheia continua valendo na sessão
        assert apl.pagina == "terminal" and (q.ativo, q.telaCheiaAtiva) == (True, True)
        q.definirTelaCheia(False)
        assert (q.telaCheia, q.telaCheiaAtiva, x.quiosqueTelaCheia) == (False, False, False)
        x.sairQuiosque()
        assert apl.pagina == "terminal" and (q.ativo, x.sobreposicaoAberta, q.usado) == (False, False, True)
        q.definirTelaCheia(True)                    # fechado: só a preferência muda
        assert (q.telaCheia, q.telaCheiaAtiva, x.quiosqueTelaCheia) == (True, False, False)
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_nove_paginas_carregam_sem_avisos(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl = ctx.apl
        for pagina in mod_aplicacao.PAGINAS:
            apl.navegar(pagina)
            ctx.girar(0.3)
            assert apl.pagina == pagina
            if pagina in PAGINAS_QML:
                assert _visivel(ctx, PAGINAS_QML[pagina]), pagina
            assert ERRO_CARGA not in apoio_v2.textos_visiveis(ctx.janela), pagina
        rotulos = apoio_v2.textos_visiveis(ctx.janela)       # a lateral: grupo "Análise", 9 itens e o modo porta
        assert all(texto in rotulos for texto in ("Análise", "Painel de segurança", "Laboratório PIVC",
                                                  "Resultados", "Modo porta"))
        assert len(apoio_v2.itens(ctx.janela, lambda i: i.metaObject().className().startswith("ItemNavegacao"))) == 9
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_todas_as_abas_carregam_sem_avisos(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x, vistas = ctx.apl, ctx.apl.extensoes, []
        for pagina, linhas in mod_extensoes.ABAS.items():
            apl.navegar("usuarios")
            for valor, texto, chave, _ in linhas:
                vm = apoio_v2.abrir_aba(ctx, pagina, valor)
                nome = "aba" + chave[0].upper() + chave[1:]
                assert vm is x.obter(chave) and vm.ativa, chave
                assert _visivel(ctx, nome), nome
                outras = [c for _, _, c, _ in linhas if c != chave]
                assert not any(_visivel(ctx, "aba" + c[0].upper() + c[1:]) for c in outras), chave
                assert texto in apoio_v2.textos_visiveis(ctx.janela)     # o rótulo da aba, na barra de abas
                assert ERRO_CARGA not in apoio_v2.textos_visiveis(ctx.janela), chave
                vistas.append(chave)
        assert tuple(vistas) == CHAVES_DE_ABA and len(vistas) == 9
        apl.navegar("terminal")
        assert apoio_v2.esperar_ocioso(ctx)
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_qml_quebrado_fica_no_lugar(qapp, tmp_path, pipeline, monkeypatch):
    quebrado = tmp_path / "AbaQuebrada.qml"
    quebrado.write_text("import QtQuick\nItem { propriedadeQueNaoExiste: 1 }\n", encoding="utf-8")
    url_quebrado = QUrl.fromLocalFile(str(quebrado)).toString()
    linhas = []
    for valor, texto, chave, fonte in mod_extensoes.ABAS["painel"]:
        fonte = {"geral": "AbaQueNaoExiste.qml", "integridade": url_quebrado}.get(valor, fonte)
        linhas.append((valor, texto, chave, fonte))
    monkeypatch.setitem(mod_extensoes.ABAS, "painel", tuple(linhas))
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, painel = ctx.apl, ctx.apl.extensoes.obter("painel")
        apl.navegar("painel")                       # aba geral: arquivo que não existe
        ctx.girar(0.3)
        textos = apoio_v2.textos_visiveis(ctx.janela)
        assert ERRO_CARGA in textos and "O arquivo AbaQueNaoExiste.qml tem um erro." in textos
        assert _visivel(ctx, "paginaPainel") and "Painel de segurança" in textos   # a página continua de pé
        painel.definirAba("incidentes")             # a aba boa carrega normalmente
        ctx.girar(0.3)
        assert _visivel(ctx, "abaPainelIncidentes") and ERRO_CARGA not in apoio_v2.textos_visiveis(ctx.janela)
        painel.definirAba("integridade")            # aba com erro de QML
        ctx.girar(0.3)
        assert f"O arquivo {url_quebrado} tem um erro." in apoio_v2.textos_visiveis(ctx.janela)
        for pagina in SEIS:                         # a janela segue viva e as outras páginas abrem
            apl.navegar(pagina)
            ctx.girar(0.2)
            assert apl.pagina == pagina
        assert ctx.janela is not None and ctx.janela.isVisible()
        avisos = ctx.avisos_qml()                   # só os avisos dos dois arquivos quebrados
        assert avisos and all("AbaQueNaoExiste.qml" in a or "AbaQuebrada.qml" in a for a in avisos), avisos
    finally:
        ctx.fechar()


def test_guarda_de_teclas_com_sobreposicao(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        apl.navegar("terminal")
        ctx.girar(0.3)
        t = apl.terminal
        t.definirNivel(1)
        t.definirLiveness(False)
        antes = (t.nivel, t.liveness, t.didatico)
        x.entrarQuiosque()
        ctx.girar(0.2)
        assert x.sobreposicaoAberta and _visivel(ctx, "quiosque")
        navegacao = apoio_v2.itens(ctx.janela, lambda i: i.metaObject().className().startswith("ItemNavegacao"))
        navegacao[0].forceActiveFocus()             # o foco fora da sobreposição, num item da lateral
        ctx.girar(0.1)
        # o quiosque (L8) prende o foco e o puxa de volta; com o foco em qualquer um dos dois, nada pode mudar
        foco = apoio_v2.foco_atual(ctx)
        assert foco.startswith("ItemNavegacao") or foco == "quiosque", foco
        for tecla in (Qt.Key.Key_L, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_D):
            apoio_v2.tecla(ctx, tecla)
            assert (t.nivel, t.liveness, t.didatico) == antes, tecla
        x.sairQuiosque()                            # controle: sem a sobreposição, as teclas voltam a valer
        ctx.girar(0.1)
        assert not x.sobreposicaoAberta
        apoio_v2.tecla(ctx, Qt.Key.Key_2)
        assert t.nivel == 2
        apoio_v2.tecla(ctx, Qt.Key.Key_L)
        assert t.liveness is True
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- contrato de recálculo
def test_sinal_externo_com_aba_inativa_nao_trabalha(qapp, tmp_path, pipeline, monkeypatch):
    _trocar_no_registro(monkeypatch, "painelGeral", __name__, "AbaContadora")
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        aba, painel, privacidade = x.obter("painelGeral"), x.obter("painel"), x.obter("privacidade")
        laboratorio = x.obter("laboratorio")
        assert type(aba) is AbaContadora
        painel.atualizarPedido.connect(aba.pedir_recarga)
        laboratorio.amostraMudou.connect(aba.pedir_recarga)
        privacidade.mostrarNomesMudou.connect(aba.pedir_recarga)
        assert not aba.ativa and aba._sujo
        laboratorio.usarFotoTeste(0)                # a amostra nova sai do Laboratório por amostraMudou
        assert apoio_v2.esperar_ocioso(ctx) and laboratorio.temAmostra
        painel.atualizar()
        painel.definirPeriodo("7d")
        privacidade.definirMostrarNomes(True)
        apl.banco_alterado()
        ctx.girar(0.1)
        assert aba.recargas == 0 and aba._sujo and x.trabalhos.ocioso()
        apl.navegar("painel")                       # ao ativar, uma chamada só
        assert aba.ativa and aba.recargas == 1 and not aba._sujo
        apl.navegar("usuarios")                     # calculada e de novo fora da tela: cada aviso, sozinho, só suja
        avisos = (painel.atualizar, lambda: painel.definirPeriodo("30d"), laboratorio.limpar,
                  lambda: privacidade.definirMostrarNomes(False), apl.banco_alterado, aba.pedir_recarga)
        for avisar in avisos:
            aba._sujo = False
            avisar()
            assert aba._sujo and aba.recargas == 1 and x.trabalhos.ocioso()
        aba._sujo = False
        apl.navegar("painel")                       # limpa e sem SEMPRE_RECALCULA: não recalcula ao voltar
        assert aba.recargas == 1
        painel.atualizar()                          # na tela, o aviso recalcula na hora
        assert aba.recargas == 2 and not aba._sujo
        privacidade.definirMostrarNomes(True)
        apl.banco_alterado()
        assert aba.recargas == 4
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_sempre_recalcula_recarrega_em_toda_ativacao(qapp, tmp_path, pipeline, monkeypatch):
    for chave, modulo, classe in mod_extensoes.REGISTRO:    # as três abas do Painel, e só elas
        if chave in CHAVES_DE_ABA:
            vm = getattr(importlib.import_module(modulo), classe)
            assert vm.SEMPRE_RECALCULA is chave.startswith("painel"), chave
    _trocar_no_registro(monkeypatch, "painelGeral", __name__, "AbaSempre")
    _trocar_no_registro(monkeypatch, "painelIncidentes", __name__, "AbaContadora")
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        painel, sempre, comum = x.obter("painel"), x.obter("painelGeral"), x.obter("painelIncidentes")
        apl.navegar("painel")
        assert (sempre.recargas, comum.recargas) == (1, 0)
        painel.definirAba("incidentes")
        painel.definirAba("geral")
        painel.definirAba("incidentes")
        assert (sempre.recargas, comum.recargas) == (2, 1)  # a comum só recalculou na primeira vez (estava suja)
        apl.navegar("usuarios")
        apl.navegar("painel")
        assert (sempre.recargas, comum.recargas) == (2, 1)
        painel.definirAba("geral")
        apl.navegar("terminal")                     # o terminal grava sem avisar: ao voltar, o painel recalcula
        apl.navegar("painel")
        assert (sempre.recargas, comum.recargas) == (4, 1)
    finally:
        ctx.fechar()


def test_repasse_sobrevive_a_aba_com_excecao(qapp, tmp_path, pipeline, monkeypatch, capfd):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        recebidos = []

        def levanta():
            raise RuntimeError("aba quebrada de propósito")

        monkeypatch.setattr(x.obter("painelGeral"), "ao_banco_alterado", levanta, raising=False)
        monkeypatch.setattr(x.obter("painelGeral"), "ao_pipeline_pronto", levanta, raising=False)
        for chave in ("painelIncidentes", "painelIntegridade", "resSeparacao"):
            vm = x.obter(chave)
            monkeypatch.setattr(vm, "ao_banco_alterado", lambda c=chave: recebidos.append((c, "banco")), raising=False)
            monkeypatch.setattr(vm, "ao_pipeline_pronto", lambda c=chave: recebidos.append((c, "modelos")), raising=False)
        capfd.readouterr()
        apl.banco_alterado()
        assert recebidos == [("painelIncidentes", "banco"), ("painelIntegridade", "banco"), ("resSeparacao", "banco")]
        recebidos.clear()
        apl.usar_pipeline(pipeline)
        assert recebidos == [("painelIncidentes", "modelos"), ("painelIntegridade", "modelos"),
                             ("resSeparacao", "modelos")]
        assert capfd.readouterr().err.count("RuntimeError: aba quebrada de propósito") == 2     # um traceback por repasse
    finally:
        ctx.fechar()


def test_aba_estado_cancelar_e_falha(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        x = ctx.apl.extensoes
        aba = AbaComTrabalho(ctx.apl, x)
        estados = []
        aba.estadoMudou.connect(lambda: estados.append(aba.estado))
        assert (aba.estado, aba.erro, aba.progresso) == ("vazio", "", -1.0) and aba.caminho_db == ctx.apl.banco.caminho
        aba.ativar()
        assert aba.estado == "carregando" and aba.trabalho.ocupado and not x.trabalhos.ocioso()
        assert ctx.esperar(lambda: aba.progresso >= 0.0, 3)
        aba.cancelar()                              # volta ao estado em que estava antes do cálculo
        assert (aba.estado, aba.progresso) == ("vazio", -1.0) and x.trabalhos.ocioso()
        ctx.girar(0.2)
        assert aba.resultados == []
        aba.solta.set()
        aba.recarregar()
        assert apoio_v2.esperar_estado(ctx, aba) == "pronto" and aba.resultados == [42]
        aba.solta.clear()
        aba.recarregar()
        assert aba.estado == "carregando"
        aba.cancelar()
        assert aba.estado == "pronto"
        # falha dentro do trabalho: os dados antigos somem e o texto vai para a tela
        aba.falha = "leitura falhou"
        aba.solta.set()
        aba.recarregar()
        assert apoio_v2.esperar_estado(ctx, aba) == "erro"
        assert aba.erro == "leitura falhou" and aba.limpezas == 1
        aba.falha = ""
        aba.solta.clear()
        aba.recarregar()
        assert (aba.estado, aba.erro) == ("carregando", "")
        aba.cancelar()                              # o erro que estava na tela volta junto com o estado
        assert (aba.estado, aba.erro) == ("erro", "leitura falhou")
        aba._indisponivel("Análise disponível só com banco em arquivo")
        assert (aba.estado, aba.erro, aba.limpezas) == ("indisponivel", "Análise disponível só com banco em arquivo", 2)
        aba.ao_pipeline_pronto()                    # na tela e indisponível: os modelos chegaram, recalcula
        assert aba.estado == "carregando" and aba.trabalho.ocupado
        aba.desativar()                             # sair no meio cancela, e a aba fica suja para refazer
        assert not aba.trabalho.ocupado and aba.estado == "indisponivel" and aba._sujo
        aba._sujo = False
        aba.ao_pipeline_pronto()                    # fora da tela: só fica suja
        assert aba._sujo and x.trabalhos.ocioso() and aba.estado == "indisponivel"
        aba.solta.set()
        aba.ativar()
        assert apoio_v2.esperar_estado(ctx, aba) == "pronto" and aba.resultados == [42, 42]
        aba.ao_pipeline_pronto()                    # pronta: a chegada dos modelos não refaz nada
        assert aba.estado == "pronto" and x.trabalhos.ocioso()
        assert set(estados) <= set(ESTADOS)
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- privacidade
def test_privacidade_anonima_por_padrao_e_nao_grava(qapp, tmp_path, pipeline, monkeypatch):
    caminho = tmp_path / "t.db"
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        ctx.apl.banco.criar_usuario("Ana Souza", "A1", "", 2)
        privacidade = ctx.apl.extensoes.obter("privacidade")
        assert privacidade.mostrarNomes is False
        arquivos = {arquivo: arquivo.stat().st_size for arquivo in tmp_path.rglob("*") if arquivo.is_file()}
        banco_antes = apoio_v2.retrato_banco(caminho)
        conectar_de_verdade, conexoes, emissoes = sqlite3.connect, [], []

        def conectar(*args, **kwargs):
            conexoes.append(args)
            return conectar_de_verdade(*args, **kwargs)

        privacidade.mostrarNomesMudou.connect(lambda: emissoes.append(privacidade.mostrarNomes))
        monkeypatch.setattr(sqlite3, "connect", conectar)
        privacidade.definirMostrarNomes(True)
        privacidade.definirMostrarNomes(True)
        ctx.girar(0.2)
        monkeypatch.setattr(sqlite3, "connect", conectar_de_verdade)
        assert privacidade.mostrarNomes is True and emissoes == [True]
        assert conexoes == []                       # ligar a chave não abre o banco
        assert {a: a.stat().st_size for a in tmp_path.rglob("*") if a.is_file()} == arquivos    # nada gravado
        assert apoio_v2.retrato_banco(caminho) == banco_antes
    finally:
        ctx.fechar()
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)       # a chave vale só até fechar: abre anônimo de novo
    try:
        assert ctx.apl.extensoes.obter("privacidade").mostrarNomes is False
    finally:
        ctx.fechar()


def test_rotulos_para_anonimo_e_com_nomes(tmp_path):
    caminho = tmp_path / "rotulos.db"
    with Banco(caminho) as banco:
        ana = banco.criar_usuario("Ana Souza", "A1", "", 1)
        caio = banco.criar_usuario("Caio Lima", "C1", "", 2)
        davi = banco.criar_usuario("Davi Reis", "D1", "", 3)
        banco.definir_ativo(caio.id, False)         # inativo continua com o mesmo rótulo
        banco.remover_usuario(davi.id)
    antes = apoio_v2.retrato_banco(caminho)
    anonimos = rotulos_para(caminho, com_nomes=False)
    assert anonimos == {ana.id: "Pessoa A", caio.id: "Pessoa B"}
    com_nomes = rotulos_para(caminho, com_nomes=True)
    assert com_nomes == {ana.id: "Ana Souza", caio.id: "Caio Lima"}
    assert rotulo_de(anonimos, ana.id) == "Pessoa A" and rotulo_de(anonimos, np.int64(caio.id)) == "Pessoa B"
    assert rotulo_de(com_nomes, caio.id) == "Caio Lima"
    assert rotulo_de(anonimos, davi.id) == "Pessoa removida" and rotulo_de(com_nomes, davi.id) == "Pessoa removida"
    assert rotulo_de(anonimos, None) == "Sem identidade" and rotulo_de(com_nomes, None) == "Sem identidade"
    assert rotulo_de({}, ana.id) == "Pessoa removida"
    with pytest.raises(leitura_ro.BancoIndisponivel):
        rotulos_para(":memory:", com_nomes=False)
    assert apoio_v2.retrato_banco(caminho) == antes


# ---------------------------------------------------------------------------- banco e encerramento
def test_visitar_tudo_nao_altera_banco_nem_parametros(qapp, tmp_path, pipeline):
    caminho = tmp_path / "t.db"
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        obama = apoio_v2.cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA, FOTO_OBAMA_2])
        apoio_v2.semear_acessos(caminho, [
            {"data_hora": "2026-01-05T10:00:00", "resultado": "CONCEDIDO", "usuario_id": obama.id,
             "nome_detectado": "Barack Obama", "nivel_usuario": 3, "nivel_exigido": 2, "similaridade": 0.71},
            {"data_hora": "2026-01-05T10:02:00", "resultado": "NEGADO_DESCONHECIDO", "similaridade": 0.2},
            {"data_hora": "2026-01-05T10:02:30", "resultado": "NEGADO_NIVEL", "usuario_id": obama.id,
             "nome_detectado": "Barack Obama", "nivel_usuario": 3, "nivel_exigido": 3, "similaridade": 0.66}])
        apl.banco_alterado()
        banco_antes, parametros_antes = apoio_v2.retrato_banco(caminho), apoio_v2.retrato_parametros()
        arquivos_antes = sorted(arquivo for arquivo in tmp_path.rglob("*") if arquivo.is_file())
        for com_nomes in (False, True):
            x.obter("privacidade").definirMostrarNomes(com_nomes)
            for pagina in mod_extensoes.PAGINAS_V2:
                apl.navegar(pagina)
                ctx.girar(0.2)
                assert apl.pagina == pagina
            apl.navegar("usuarios")
            for chave in CHAVES_DE_ABA:             # cada análise roda uma vez, com a aba na tela
                vm = x.obter(chave)
                vm.ativar()
                vm.recarregar()
                assert apoio_v2.esperar_estado(ctx, vm) in ESTADOS and vm.estado != "carregando", chave
                vm.desativar()
        assert apoio_v2.esperar_ocioso(ctx)
        assert apoio_v2.retrato_banco(caminho) == banco_antes
        assert apoio_v2.retrato_parametros() == parametros_antes
        assert sorted(arquivo for arquivo in tmp_path.rglob("*") if arquivo.is_file()) == arquivos_antes
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_fechar_no_meio_de_trabalho_longo(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    fechado = False
    try:
        trabalhos = ctx.apl.extensoes.trabalhos
        aba = apoio_v2.abrir_aba(ctx, "painel", "geral")
        outro, terceiro = Trabalho(trabalhos, aba), Trabalho(trabalhos, aba)
        iniciou = [threading.Event() for _ in range(3)]
        parou = [threading.Event() for _ in range(3)]
        vistos = []
        for trabalho, i in ((aba.trabalho, 0), (outro, 1), (terceiro, 2)):     # dois rodando e um na fila do pool
            trabalho.executar(_varredura(iniciou[i], parou[i]), lambda r, e: vistos.append((r, e)))
        assert iniciou[0].wait(3) and iniciou[1].wait(3)
        ctx.girar(0.1)
        assert not trabalhos.ocioso() and not iniciou[2].is_set()
        inicio = time.perf_counter()
        ctx.fechar()
        fechado = True
        duracao = time.perf_counter() - inicio
        assert duracao < 4.0, duracao
        assert trabalhos.esperar(0)                 # o pool já parou: as varreduras saíram no conferir() seguinte
        assert parou[0].is_set() and parou[1].is_set() and not iniciou[2].is_set()
        ctx.girar(0.2)
        assert vistos == [] and trabalhos.ocioso()  # depois de cancelar tudo, nenhum ao_terminar
        aba.trabalho.executar(lambda sinal: 1, lambda r, e: vistos.append((r, e)))      # pedido tardio: ignorado
        ctx.girar(0.1)
        assert vistos == [] and trabalhos.ocioso()
    finally:
        if not fechado:
            ctx.fechar()


def test_fechar_nao_fica_preso_em_trabalho_que_ignora_o_cancelamento(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(mod_extensoes, "ESPERA_ENCERRAMENTO_MS", 300)
    iniciou, solta = threading.Event(), threading.Event()

    def teimoso(sinal):
        iniciou.set()
        solta.wait(10)                              # não confere o cancelamento
        return "tarde demais"

    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    fechado = False
    try:
        trabalhos = ctx.apl.extensoes.trabalhos
        trabalho, vistos = Trabalho(trabalhos), []
        trabalho.executar(teimoso, lambda r, e: vistos.append((r, e)))
        assert iniciou.wait(3)
        inicio = time.perf_counter()
        ctx.fechar()
        fechado = True
        duracao = time.perf_counter() - inicio
        assert 0.3 <= duracao < 2.0, duracao        # esperou o prazo e seguiu em frente
        assert not trabalhos.esperar(0)             # o trabalho ainda roda, mas o aplicativo já fechou
        solta.set()
        assert trabalhos.esperar(3000)
        ctx.girar(0.2)
        assert vistos == []                         # o resultado que chegou depois foi descartado
    finally:
        solta.set()
        if not fechado:
            ctx.fechar()


# ---------------------------------------------------------------------------- laboratório
def _esperar_lab(ctx, lab) -> None:
    assert apoio_v2.esperar_ocioso(ctx) and not lab.processando, lab.erro


def _registrar_camera(monkeypatch) -> list:
    """Anota o processador de cada `ServicoCamera.iniciar` e deixa a câmera (falsa) ligar."""
    iniciar_de_verdade, processadores = ServicoCamera.iniciar, []

    def iniciar(self, processador):
        processadores.append(processador)
        iniciar_de_verdade(self, processador)

    monkeypatch.setattr(ServicoCamera, "iniciar", iniciar)
    return processadores


def test_laboratorio_foto_de_teste_e_referencia_automatica(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        lab = x.obter("laboratorio")
        banco_antes = apoio_v2.retrato_banco(tmp_path / "t.db")
        assert [f["rotulo"] for f in lab.fotosTeste] == ["Pessoa de teste A · foto 1", "Pessoa de teste A · foto 2",
                                                         "Pessoa de teste B · foto 1", "Pessoa de teste B · foto 2"]
        assert (lab.temAmostra, lab.temReferencia, lab.amostraOrigem, lab.revisao) == (False, False, "", 0)
        apl.navegar("laboratorio")
        ctx.girar(0.2)
        mudancas = []
        lab.amostraMudou.connect(lambda: mudancas.append("amostra"))
        lab.referenciaMudou.connect(lambda: mudancas.append("referencia"))
        lab.usarFotoTeste(0)                        # a amostra e, de brinde, a outra foto da mesma pessoa
        assert lab.processando
        _esperar_lab(ctx, lab)
        assert (lab.temAmostra, lab.amostraOrigem, lab.amostraRotulo) == (True, "foto_teste", "Pessoa de teste A · foto 1")
        assert (lab.temRosto, lab.nRostos) == (True, 1)
        assert (lab.temReferencia, lab.referenciaRotulo, lab.referenciaTemRosto) == (True, "Pessoa de teste A · foto 2", True)
        assert sorted(mudancas) == ["amostra", "referencia"] and lab.revisao == 2
        assert lab.amostra.embedding.shape == (128,) and lab.referencia.embedding.shape == (128,)
        lab.usarFotoTeste(3)
        _esperar_lab(ctx, lab)
        assert (lab.amostraRotulo, lab.referenciaRotulo) == ("Pessoa de teste B · foto 2", "Pessoa de teste B · foto 1")
        lab.usarFotoTesteComoReferencia(0)          # escolhida à mão: a automática não a troca mais
        lab.usarFotoTeste(2)
        _esperar_lab(ctx, lab)
        assert (lab.amostraRotulo, lab.referenciaRotulo) == ("Pessoa de teste B · foto 1", "Pessoa de teste A · foto 1")
        lab.limparReferencia()                      # sem referência à mão, a automática volta
        assert not lab.temReferencia
        lab.usarFotoTeste(1)
        _esperar_lab(ctx, lab)
        assert (lab.amostraRotulo, lab.referenciaRotulo) == ("Pessoa de teste A · foto 2", "Pessoa de teste A · foto 1")
        revisao = lab.revisao
        lab.usarFotoTeste(9)                        # índice fora da lista: ignorado
        lab.usarFotoTesteComoReferencia(-1)
        assert lab.revisao == revisao and x.trabalhos.ocioso()
        # arquivo: o rótulo não leva o nome do arquivo (pode ser o nome de alguém)
        lab.abrirArquivo(QUrl.fromLocalFile(str(FOTO_OBAMA)).toString())
        _esperar_lab(ctx, lab)
        assert lab.amostraOrigem == "arquivo" and lab.amostraRotulo.startswith("Arquivo aberto às ") and lab.temRosto
        assert "obama" not in lab.amostraRotulo.lower()
        texto = tmp_path / "nao_e_imagem.jpg"
        texto.write_text("isto não é uma imagem", encoding="utf-8")
        lab.abrirArquivo(QUrl.fromLocalFile(str(texto)).toString())
        _esperar_lab(ctx, lab)
        assert lab.erro.startswith("Não foi possível abrir a imagem") and lab.amostraOrigem == "arquivo"
        lab.limpar()
        assert (lab.temAmostra, lab.amostraRotulo, lab.nRostos, lab.temReferencia) == (False, "", 0, True)
        assert "Nenhuma imagem" in apoio_v2.textos_visiveis(ctx.janela)
        # nada de nome de pessoa nem de vetor no que o QML lê, e o banco intacto
        props = apoio_v2.props_do_vm(lab)
        assert not any(n in repr(props).lower() for n in ("obama", "biden")) and apoio_v2.sem_vetor_128(props)
        assert apoio_v2.retrato_banco(tmp_path / "t.db") == banco_antes
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_laboratorio_congela_quadro_da_camera_falsa(qapp, tmp_path, pipeline, monkeypatch):
    processadores = _registrar_camera(monkeypatch)
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline, imagens=[apoio_v2.quadro_webcam(FOTO_OBAMA_2)])
    try:
        apl, lab = ctx.apl, ctx.apl.extensoes.obter("laboratorio")
        apl.navegar("laboratorio")
        ctx.girar(0.2)
        assert apl.camera.estado == "desligada" and processadores == []    # abrir a página não liga a câmera
        lab.iniciarPrevia("amostra")
        assert lab.previa and lab.alvoPrevia == "amostra"
        assert processadores == [vm_laboratorio.processar_previa]          # só converte o quadro: nenhum pipeline
        assert ctx.esperar(lambda: apl.camera.estado == "ativa" and apl.camera.ultimo() is not None, 10)
        ctx.girar(0.2)
        assert _visivel(ctx, "previaCamera") and "Posicione o rosto e congele o quadro" in apoio_v2.textos_visiveis(ctx.janela)
        assert not lab.temAmostra and apl.extensoes.trabalhos.ocioso()
        apoio_v2.tecla(ctx, Qt.Key.Key_Space)       # o atalho da tela congela
        assert not lab.previa
        assert ctx.esperar(lambda: apl.camera.estado == "desligada", 5)
        _esperar_lab(ctx, lab)
        assert (lab.temAmostra, lab.amostraOrigem, lab.temRosto, lab.nRostos) == (True, "camera", True, 1)
        assert lab.amostraRotulo.startswith("Quadro congelado ")
        assert not _visivel(ctx, "previaCamera")
        lab.iniciarPrevia("referencia")             # a referência também pode vir da câmera
        assert ctx.esperar(lambda: apl.camera.estado == "ativa" and apl.camera.ultimo() is not None, 10)
        lab.congelar()
        _esperar_lab(ctx, lab)
        assert apl.camera.estado == "desligada" and lab.temReferencia
        assert lab.referenciaRotulo.startswith("Quadro congelado ") and lab.referencia.origem == "camera"
        lab.iniciarPrevia("amostra")                # Esc cancela sem trocar a amostra
        assert ctx.esperar(lambda: apl.camera.estado == "ativa", 10)
        revisao = lab.revisao
        apoio_v2.tecla(ctx, Qt.Key.Key_Escape)
        assert not lab.previa and ctx.esperar(lambda: apl.camera.estado == "desligada", 5)
        assert lab.revisao == revisao and lab.amostraOrigem == "camera"
        assert len(processadores) == 3 and set(processadores) == {vm_laboratorio.processar_previa}
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_quadro_congelado_some_ao_sair(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline, imagens=[apoio_v2.quadro_webcam(FOTO_OBAMA_2)])
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        lab = x.obter("laboratorio")
        apl.navegar("laboratorio")
        lab.usarFotoTesteComoReferencia(0)          # referência de foto: fica
        lab.iniciarPrevia("amostra")
        assert ctx.esperar(lambda: apl.camera.ultimo() is not None, 10)
        lab.congelar()
        _esperar_lab(ctx, lab)
        assert lab.amostraOrigem == "camera" and lab.temReferencia
        apl.navegar("usuarios")                     # o quadro só existia em memória: some com a página
        assert (lab.temAmostra, lab.amostraOrigem, lab.amostraRotulo) == (False, "", "")
        assert lab.amostra is None and lab.temReferencia and lab.referencia.origem == "foto_teste"
        apl.navegar("laboratorio")                  # sair no meio do preparo também descarta o quadro
        lab.iniciarPrevia("amostra")
        assert ctx.esperar(lambda: apl.camera.ultimo() is not None, 10)
        lab.congelar()
        assert lab.processando
        apl.navegar("usuarios")
        _esperar_lab(ctx, lab)
        ctx.girar(0.2)
        assert not lab.temAmostra and lab.amostra is None
        apl.navegar("laboratorio")                  # a prévia aberta para ao sair e a câmera desliga
        lab.iniciarPrevia("amostra")
        assert ctx.esperar(lambda: apl.camera.estado == "ativa", 10)
        apl.navegar("usuarios")
        assert not lab.previa and ctx.esperar(lambda: apl.camera.estado == "desligada", 5)
        lab.iniciarPrevia("amostra")                # fora da tela: recusada
        assert not lab.previa and apl.camera.estado == "desligada"
        apl.navegar("laboratorio")                  # amostra de foto de teste continua depois de sair
        lab.usarFotoTeste(2)
        _esperar_lab(ctx, lab)
        apl.navegar("usuarios")
        assert lab.temAmostra and lab.amostraOrigem == "foto_teste"
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


def test_previa_recusada_com_sessao_aberta(qapp, tmp_path, pipeline, monkeypatch):
    imagens = [FOTO_OBAMA]
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline, imagens=imagens)
    try:
        apoio_v2.cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA_2])
        apl, x = ctx.apl, ctx.apl.extensoes
        lab, t, s = x.obter("laboratorio"), apl.terminal, apl.sessao
        t.definirLiveness(False)
        t.definirNivel(1)
        apl.navegar("terminal")
        assert ctx.esperar(lambda: s.ativa, 25), (t.estado, t.resultadoTipo)    # sessão aberta pelo backend
        assert ctx.esperar(lambda: apl.camera.estado == "desligada", 5)
        processadores = _registrar_camera(monkeypatch)
        apl.navegar("laboratorio")                  # a navegação está travada
        assert apl.pagina == "terminal"
        lab.ativar()                                # mesmo com a página dada como ativa, a sessão aberta recusa
        lab.iniciarPrevia("amostra")
        ctx.girar(0.2)
        assert not lab.previa and processadores == [] and apl.camera.estado == "desligada"
        lab.desativar()
        imagens[0] = np.zeros((480, 640, 3), np.uint8)      # ninguém na frente da câmera ao encerrar
        s.encerrar()
        apl.navegar("laboratorio")                  # controle: com a sessão encerrada, a prévia liga
        assert apl.pagina == "laboratorio"
        lab.iniciarPrevia("amostra")
        assert lab.previa and processadores[-1] is vm_laboratorio.processar_previa
        lab.cancelarPrevia()
        assert ctx.esperar(lambda: apl.camera.estado == "desligada", 5)
        _sem_avisos(ctx)
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- figuras
def test_abrir_pasta_usa_abrir_no_sistema(qapp, tmp_path, pipeline, monkeypatch):
    pastas = apoio_v2.usar_pastas(monkeypatch, tmp_path / "pastas")
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, figuras = ctx.apl, ctx.apl.extensoes.obter("figuras")
        notas = []
        monkeypatch.setattr(apl, "notificar", lambda tipo, texto: notas.append((tipo, texto)))
        destino = pastas["RELATORIOS_DIR"] / "figuras"
        assert vm_figuras.pasta_figuras() == destino and not destino.exists()
        figuras.abrirPasta()
        assert apoio_v2.ABERTOS == [destino] and destino.is_dir() and notas == []
        dados = {"categorias": ["Fase 1", "Fase 2"], "series": [{"nome": "Mediana", "valores": [1.5, 2.0]}]}
        figuras.exportar("barras", dados, "Fases · Laboratório")
        assert apoio_v2.esperar_ocioso(ctx)
        salvos = sorted(p.name for p in destino.iterdir())
        assert len(salvos) == 3 and all(n.startswith("fases_laboratorio_") for n in salvos)
        assert {n.rsplit(".", 1)[1] for n in salvos} == {"png", "svg", "csv"}
        assert figuras.ultimaPasta == str(destino)
        assert notas == [("info", f"Figura salva em figuras/{next(n for n in salvos if n.endswith('.png'))} (com SVG e CSV)")]
        assert "Base de demonstração" not in (destino / next(n for n in salvos if n.endswith(".svg"))).read_text(encoding="utf-8")
        vetor = np.random.default_rng(3).random(128)
        figuras.exportar("barras", {**dados, "extra": (vetor / np.linalg.norm(vetor)).tolist()}, "vetor")
        assert apoio_v2.esperar_ocioso(ctx)
        assert notas[-1][0] == "erro" and notas[-1][1].startswith("Não foi possível exportar a figura")
        assert len(list(destino.iterdir())) == 3    # nada gravado com o vetor
        monkeypatch.setattr(vm_figuras, "abrir_no_sistema", lambda caminho: False)
        figuras.abrirPasta()
        assert notas[-1] == ("erro", "O sistema não abriu a pasta de figuras.")
        assert apoio_v2.ABERTOS == [destino]
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- base de demonstração
def _banco_com(caminho, *, tabela: bool, identificacao: bool) -> None:
    """Banco temporário com o esquema do núcleo e, se pedido, as duas partes do marcador de demonstração."""
    Banco(caminho).fechar()
    con = sqlite3.connect(str(caminho))
    try:
        if tabela:
            con.execute("CREATE TABLE demonstracao (chave TEXT PRIMARY KEY, valor TEXT)")
            con.execute("INSERT INTO demonstracao (chave, valor) VALUES ('versao', '1')")
        if identificacao:
            con.execute(f"PRAGMA application_id = {base_demo.APPLICATION_ID}")
        con.commit()
    finally:
        con.close()


def test_selo_demo_so_com_marcador(qapp, tmp_path, pipeline):
    casos = (("comum", False, False, False), ("so_tabela", True, False, False),
             ("so_identificacao", False, True, False), ("demo", True, True, True))
    for nome, tabela, identificacao, esperado in casos:
        pasta = tmp_path / nome
        pasta.mkdir()
        _banco_com(pasta / "t.db", tabela=tabela, identificacao=identificacao)
        ctx = apoio_v2.contexto(qapp, pasta, pipeline)
        try:
            apl = ctx.apl
            assert apl.extensoes.baseDemonstracao is esperado, nome
            apl.navegar("painel")
            ctx.girar(0.3)
            selos = apoio_v2.textos_visiveis(ctx.janela).count("Base de demonstração")
            # o da lateral, o do cabeçalho e a linha "Base aberta" da postura (aba Visão geral, L1)
            assert selos == (3 if esperado else 0), (nome, selos)
            apl.navegar("usuarios")                 # nas páginas antigas, só o da lateral
            ctx.girar(0.2)
            assert apoio_v2.textos_visiveis(ctx.janela).count("Base de demonstração") == (1 if esperado else 0), nome
            _sem_avisos(ctx)
        finally:
            ctx.fechar()
