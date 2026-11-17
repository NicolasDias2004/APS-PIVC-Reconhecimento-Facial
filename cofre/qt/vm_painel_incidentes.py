"""Aba Incidentes do Painel de segurança (v2): o registro transformado em fatos com nome (bloqueio,
tentativa acima do nível, prova de vida com identidade forte, mais de uma pessoa). Consultivo: descreve
padrões, não acusa pessoas, e nada é gravado. Anônimo por padrão ("Pessoa A"); o nome só aparece com
a chave "Mostrar nomes" ligada.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from .. import config, incidentes
from ..liveness import ControleTentativas
from . import tema
from .base import objeto, prop
from .base_v2 import ViewModelAba
from .formatos import dia_hora, hora
from .modelos import ModeloLista
from .vm_privacidade import PESSOA_REMOVIDA, rotulo_de, rotulos_para

PAPEIS = ["id", "tipo", "titulo", "gravidade", "inicio", "fim", "tentativas", "nivelExigido", "pessoa", "resumo"]
RESULTADO_DO_TIPO = {"bloqueio": "BLOQUEADO", "acima_do_nivel": "NEGADO_NIVEL", "prova_de_vida": "NEGADO_LIVENESS",
                     "multiplos": "NEGADO_MULTIPLOS"}


class PainelIncidentesVM(ViewModelAba):
    SEMPRE_RECALCULA = True         # o terminal não avisa quando grava: recalcula em toda ativação

    contagensMudou = Signal()
    filtroTipoMudou = Signal()
    selecionadoMudou = Signal()
    linhaTempoMudou = Signal()
    regrasMudou = Signal()
    limiarMudou = Signal()

    incidentes = objeto("lista")
    contagens = prop("QVariantMap", "contagens", contagensMudou)
    filtroTipo = prop(str, "filtroTipo", filtroTipoMudou)
    selecionado = prop(str, "selecionado", selecionadoMudou)
    linhaTempo = prop("QVariantList", "linhaTempo", linhaTempoMudou)
    regras = prop("QVariantList", "regras", regrasMudou)
    limiar = prop(float, "limiar", limiarMudou)          # limiar em vigor, só para exibir a marca

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self.lista = ModeloLista(PAPEIS, self)
        self._iniciar(contagens=self._contagens_zero(), filtroTipo="", selecionado="", linhaTempo=[], regras=[],
                      limiar=float(config.LIMIAR_COSSENO))
        self._todos: list[dict] = []
        self._por_chave: dict[str, incidentes.Incidente] = {}
        self._linhas: list[incidentes.Linha] = []
        self.app.extensoes.obter("painel").atualizarPedido.connect(self.pedir_recarga)
        self.app.extensoes.obter("privacidade").mostrarNomesMudou.connect(self.ao_mudar_nomes)

    @staticmethod
    def _contagens_zero() -> dict:
        return {**{t: 0 for t in incidentes.TIPOS}, "todos": 0}

    def _tentativas(self):
        term = getattr(self.app.terminal_vm, "terminal", None)
        return term.tentativas if term is not None else ControleTentativas()

    # ------------------------------------------------------------------ cálculo
    def _limpar_dados(self) -> None:
        self._todos, self._por_chave, self._linhas = [], {}, []
        self.lista.definir([])
        self._definir("contagens", self._contagens_zero())
        self._definir("selecionado", "")
        self._definir("linhaTempo", [])

    @Slot()
    def recarregar(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        tentativas = self._tentativas()
        janela, max_falhas = float(tentativas.janela), int(tentativas.max_falhas)
        forte = float(config.LIMIAR_COSSENO_FORTE)
        self._definir("limiar", float(config.LIMIAR_COSSENO))
        self._definir("regras", incidentes.regras_em_texto(janela, max_falhas, forte))
        caminho = self.caminho_db
        if str(caminho) == ":memory:":
            self._indisponivel("Análise disponível só com banco em arquivo")
            return
        desde = self.app.extensoes.obter("painel").desde_iso()
        com_nomes = bool(self.app.extensoes.obter("privacidade").mostrarNomes)
        self._definir("erro", "")
        self._definir("estado", "carregando")

        def fn(sinal):
            linhas = incidentes.ler_linhas(caminho, desde)
            sinal.conferir()
            achados = incidentes.detectar(linhas, janela_seg=janela, limiar_forte=forte)
            precisa = any(i.tipo in incidentes.TIPOS_COM_PESSOA and i.usuario_id is not None for i in achados)
            mapa = rotulos_para(caminho, com_nomes) if precisa else {}
            return linhas, achados, mapa

        self.trabalho.executar(fn, self._ao_terminar)

    def _ao_terminar(self, r, erro: str) -> None:
        if erro or r is None:
            self._falhar(f"Não foi possível ler o registro: {erro or 'sem resultado'}")
            return
        linhas, achados, mapa = r
        self._linhas = linhas
        self._por_chave = {i.chave: i for i in achados}
        self._todos = [self._item(i, mapa) for i in achados]
        contagens = self._contagens_zero()
        for i in achados:
            contagens[i.tipo] += 1
        contagens["todos"] = len(achados)
        self._definir("contagens", contagens)
        self._aplicar_filtro()
        self._definir("estado", "pronto" if achados else "vazio")

    @staticmethod
    def _item(i: incidentes.Incidente, mapa: dict) -> dict:
        if i.tipo in incidentes.TIPOS_COM_PESSOA:
            pessoa = PESSOA_REMOVIDA if i.usuario_id is None else rotulo_de(mapa, i.usuario_id)
        else:
            pessoa = ""
        mesmo_dia = i.inicio[:10] == i.fim[:10]
        return {"id": i.chave, "tipo": i.tipo, "titulo": incidentes.TITULOS[i.tipo], "gravidade": i.gravidade,
                "inicio": dia_hora(i.inicio), "fim": i.fim[11:16] if mesmo_dia and len(i.fim) >= 16 else dia_hora(i.fim),
                "tentativas": len(i.ids), "nivelExigido": i.nivel_exigido, "pessoa": pessoa, "resumo": i.resumo}

    def _aplicar_filtro(self) -> None:
        filtro = self._v["filtroTipo"]
        visiveis = [i for i in self._todos if not filtro or i["tipo"] == filtro]
        self.lista.definir(visiveis)
        chaves = [i["id"] for i in visiveis]
        atual = self._v["selecionado"]
        self._selecionar(atual if atual in chaves else (chaves[0] if chaves else ""))

    def _selecionar(self, chave: str) -> None:
        self._definir("selecionado", chave)
        inc = self._por_chave.get(chave)
        if inc is None:
            self._definir("linhaTempo", [])
            return
        ids = set(inc.ids)
        self._definir("linhaTempo", [
            {"id": l.id, "hora": hora(l.data_hora), "resultado": l.resultado,
             "titulo": tema.ROTULO_CURTO_RESULTADO.get(l.resultado, l.resultado),
             "concedido": l.resultado == "CONCEDIDO",
             "similaridade": -1.0 if l.similaridade is None else float(l.similaridade),
             "similaridadeTexto": "–" if l.similaridade is None else f"{l.similaridade:.3f}".replace(".", ","),
             "nivelExigido": l.nivel_exigido, "doIncidente": l.id in ids}
            for l in incidentes.contexto(self._linhas, inc)[:60]])

    # ------------------------------------------------------------------ uso pelo QML
    @Slot(str)
    def definirFiltroTipo(self, tipo: str) -> None:
        tipo = tipo or ""
        if tipo and tipo not in incidentes.TIPOS:
            return
        if self._definir("filtroTipo", tipo):
            self._aplicar_filtro()

    @Slot(str)
    def selecionar(self, chave: str) -> None:
        if chave in self._por_chave or chave == "":
            self._selecionar(chave)

    @Slot()
    def abrirNaAuditoria(self) -> None:
        inc = self._por_chave.get(self._v["selecionado"])
        acessos = self.app.acessos_vm
        acessos.limparFiltros()
        if inc is not None:
            acessos.definirFiltroResultado(RESULTADO_DO_TIPO[inc.tipo])
        self.app.navegar("acessos")
