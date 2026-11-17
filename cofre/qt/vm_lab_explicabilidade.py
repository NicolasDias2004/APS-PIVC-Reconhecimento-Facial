"""Aba Explicabilidade do Laboratório PIVC (v2): onde o descritor olha, pelo mapa de oclusão.

O mapa só é calculado pelo botão "Calcular mapa", nunca por quadro nem ao trocar de amostra. Ele
compara a amostra coberta, posição a posição, com a referência do laboratório (outra imagem da mesma
pessoa). As duas imagens vão ao provedor com o prefixo `lab/oclusao/` e saem dele quando a aba sai
da tela; o calor vai com transparência (BGRA), para o rosto continuar visível por baixo.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Signal, Slot

from .. import explicabilidade
from . import tema_v2
from .base import prop
from .base_v2 import ViewModelAba
from .formatos import bgra_para_qimage, num
from .imagens import bgr_para_qimage

PREFIXO = "lab/oclusao/"
GRADES = {28: 14, 24: 8}                # janela -> passo (7×7 e 12×12)
SELO_TENDENCIA = "1 imagem: tendência"


class LabExplicabilidadeVM(ViewModelAba):
    temMapaMudou = Signal()
    baseMudou = Signal()
    regioesMudou = Signal()
    barrasMudou = Signal()
    fraseMudou = Signal()
    aumentosMudou = Signal()
    janelaMudou = Signal()
    opacidadeMudou = Signal()
    mesmaImagemMudou = Signal()
    revisaoMudou = Signal()
    semReferenciaMudou = Signal()
    variacoesMudou = Signal()

    temMapa = prop(bool, "temMapa", temMapaMudou)
    base = prop(float, "base", baseMudou)
    regioes = prop("QVariantList", "regioes", regioesMudou)
    barras = prop("QVariantMap", "barras", barrasMudou)
    frase = prop(str, "frase", fraseMudou)
    aumentos = prop(int, "aumentos", aumentosMudou)
    janela = prop(int, "janela", janelaMudou)
    opacidade = prop(float, "opacidade", opacidadeMudou)
    mesmaImagem = prop(bool, "mesmaImagem", mesmaImagemMudou)
    revisao = prop(int, "revisao", revisaoMudou)
    semReferencia = prop(bool, "semReferencia", semReferenciaMudou)
    variacoes = prop(int, "variacoes", variacoesMudou)

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(temMapa=False, base=-1.0, regioes=[], barras={}, frase="", aumentos=0, janela=28,
                      opacidade=0.65, mesmaImagem=False, revisao=0, semReferencia=False, variacoes=49)
        self.lab = aplicacao.extensoes.obter("laboratorio")
        self.lab.amostraMudou.connect(self.pedir_recarga)
        self.lab.referenciaMudou.connect(self.pedir_recarga)

    # ------------------------------------------------------------------ situação da amostra
    @Slot()
    def recarregar(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        self.trabalho.cancelar()
        self._limpar_dados()
        amostra = getattr(self.lab, "amostra", None)
        referencia = getattr(self.lab, "referencia", None)
        self._definir("erro", "")
        if amostra is None or amostra.alinhado is None:
            self._definir("estado", "vazio")
            return
        self._definir("semReferencia", referencia is None or referencia.embedding is None)
        self.app.imagens.guardar(PREFIXO + "rosto", bgr_para_qimage(amostra.alinhado))
        self._definir("revisao", self._v["revisao"] + 1)
        self._definir("estado", "pronto")

    def _limpar_dados(self) -> None:
        self.app.imagens.remover_prefixo(PREFIXO)
        for nome, valor in (("temMapa", False), ("base", -1.0), ("regioes", []), ("barras", {}), ("frase", ""),
                            ("aumentos", 0), ("mesmaImagem", False), ("semReferencia", False)):
            self._definir(nome, valor)

    # ------------------------------------------------------------------ mapa (só pelo botão)
    @Slot()
    def calcular(self) -> None:
        if not self.ativa:
            return
        amostra = getattr(self.lab, "amostra", None)
        referencia = getattr(self.lab, "referencia", None)
        if amostra is None or amostra.alinhado is None or referencia is None or referencia.embedding is None:
            return
        alinhado = np.array(amostra.alinhado, copy=True)
        ref = np.array(referencia.embedding, copy=True)
        janela = self._v["janela"]
        passo = GRADES[janela]
        rampa = tema_v2.CALOR

        def calcular(sinal):
            mapa = explicabilidade.mapa_oclusao(alinhado, ref, janela, passo, sinal=sinal)
            sinal.conferir()
            calor = bgra_para_qimage(explicabilidade.colorir(mapa, rampa))
            return mapa, calor, bgr_para_qimage(alinhado)

        self._definir("estado", "carregando")
        self.trabalho.executar(calcular, self._ao_calcular)

    def _ao_calcular(self, resultado, erro: str) -> None:
        if erro:
            self._falhar(f"Não foi possível calcular o mapa: {erro}")
            return
        mapa, calor, rosto = resultado
        self.app.imagens.guardar(PREFIXO + "rosto", rosto)
        self.app.imagens.guardar(PREFIXO + "calor", calor)
        regioes = [{"chave": c, "nome": explicabilidade.NOMES[c], "queda": float(q), "texto": num(q, 3)}
                   for c, q in mapa.regioes]
        maior = max([r["queda"] for r in regioes] + [0.01])
        g = mapa.queda.shape[0]
        self._definir("regioes", regioes)
        self._definir("barras", {
            "titulo": "Queda de similaridade ao cobrir cada região", "n": f"1 imagem · {g * g} variações",
            "selos": [SELO_TENDENCIA], "orientacao": "h", "rotulosValor": True,
            "resumo": mapa.frase,
            "categorias": [r["nome"] for r in regioes],
            "eixoX": {"rotulo": "queda de similaridade", "min": 0.0, "max": maior * 1.15, "formato": "0.000"},
            "series": [{"nome": "Queda de similaridade", "cor": "serie0", "valores": [r["queda"] for r in regioes]}]})
        self._definir("base", float(mapa.base))
        self._definir("frase", mapa.frase)
        self._definir("aumentos", int(mapa.aumentos))
        self._definir("mesmaImagem", mapa.base > 0.98)
        self._definir("temMapa", True)
        self._definir("revisao", self._v["revisao"] + 1)
        self._definir("estado", "pronto")

    @Slot(int)
    def definirJanela(self, janela: int) -> None:
        if int(janela) in GRADES and int(janela) != self._v["janela"]:
            self._definir("janela", int(janela))
            self._definir("variacoes", 49 if int(janela) == 28 else 144)

    @Slot(float)
    def definirOpacidade(self, opacidade: float) -> None:
        self._definir("opacidade", float(min(1.0, max(0.0, opacidade))))

    # ------------------------------------------------------------------ ciclo da aba
    def ao_desativar(self) -> None:
        super().ao_desativar()
        self.app.imagens.remover_prefixo(PREFIXO)
        self._sujo = True

    def preparar_captura(self, variante: str = "") -> None:
        if self._v["estado"] != "pronto":
            self.recarregar()
        self.calcular()
