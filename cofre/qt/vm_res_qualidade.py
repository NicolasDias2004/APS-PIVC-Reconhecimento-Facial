"""Aba Qualidade de Resultados (v2): que medida de qualidade prevê o erro, pela curva erro × descarte.

Protocolo sintético sobre imagens rotuladas (as fotos de teste ou uma pasta com uma subpasta por
pessoa), calculado só pelo botão "Calcular". Só escalares saem do cálculo: ficha, curvas, ρ e a frase.
Leitura informativa: nenhuma destas medidas entra no cadastro nem na autenticação.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from .. import amostra_lab, config, qualidade, qualidade_erc
from .base import prop
from .base_v2 import ViewModelAba
from .formatos import caminho_de_url, inteiro, num, pct_valor

SINTETICO = "Sintético"
MINIMO_PARES = 30
SERIES = (("norma", "serie0"), ("nitidez", "serie1"), ("ruido", "serie2"))


class ResQualidadeVM(ViewModelAba):
    fonteMudou = Signal()
    pastaMudou = Signal()
    fichaMudou = Signal()
    curvasMudou = Signal()
    tabelaMudou = Signal()
    leituraMudou = Signal()
    semErroMudou = Signal()

    fonte = prop(str, "fonte", fonteMudou)                  # "fotos_teste" | "pasta"
    pasta = prop(str, "pasta", pastaMudou)
    ficha = prop("QVariantMap", "ficha", fichaMudou)
    curvas = prop("QVariantMap", "curvas", curvasMudou)
    tabela = prop("QVariantList", "tabela", tabelaMudou)
    leitura = prop(str, "leitura", leituraMudou)
    semErro = prop(bool, "semErro", semErroMudou)           # nenhum falso não casamento: não há o que descartar

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(fonte="fotos_teste", pasta="", ficha={}, curvas={}, tabela=[], leitura="", semErro=False)
        self._tem_resultado = False

    @Slot()
    def recarregar(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        if not self._tem_resultado and self._v["estado"] not in ("carregando", "erro", "indisponivel"):
            self._definir("estado", "vazio")

    def ao_banco_alterado(self) -> None:
        """O protocolo não lê o banco."""

    @Slot()
    def usarFotosTeste(self) -> None:
        self._definir("fonte", "fotos_teste")

    @Slot(str)
    def definirPasta(self, url: str) -> None:
        caminho = caminho_de_url(url)
        if caminho is None:
            return
        self._definir("pasta", str(caminho))
        self._definir("fonte", "pasta")

    @Slot()
    def calcular(self) -> None:
        if not self.ativa:
            return
        pipeline = self.app.pipeline
        if pipeline is None:
            self._indisponivel("Os modelos ainda estão carregando.")
            return
        fonte, pasta, limiar = self._v["fonte"], self._v["pasta"], float(config.LIMIAR_COSSENO)

        def calcular(sinal):
            pastas = amostra_lab.fotos_de_teste() if fonte == "fotos_teste" else amostra_lab.pasta_rotulada(pasta)
            if not pastas:
                return None
            conj = qualidade_erc.montar(pastas, pipeline, sinal=sinal)
            sinal.conferir()
            return qualidade_erc.avaliar(conj, limiar)

        self._definir("erro", "")
        self._definir("estado", "carregando")
        self.trabalho.executar(calcular, lambda r, e: self._ao_calcular(r, e, limiar))

    def _ao_calcular(self, r, erro: str, limiar: float) -> None:
        if erro:
            self._falhar(f"Não foi possível calcular: {erro}")
            return
        if r is None or r["ficha"]["pares"] == 0:
            self._limpar_dados()
            self._definir("erro", "Nenhum par genuíno: a fonte precisa de duas imagens com rosto de cada pessoa.")
            self._definir("estado", "indisponivel")
            return
        ficha = r["ficha"]
        self._definir("ficha", {k: inteiro(v) for k, v in ficha.items()})
        self._definir("curvas", self._dados_curvas(r, ficha, limiar))
        self._definir("tabela", [{"componente": qualidade_erc.NOMES[c], "spearman": num(r["spearman"][c], 2),
                                  "fnmr0": pct_valor(r["curvas"][c][0][1]), "fnmr10": pct_valor(r["curvas"][c][2][1]),
                                  "fnmr20": pct_valor(r["curvas"][c][4][1])} for c in qualidade.COMPONENTES])
        self._definir("leitura", r["leitura"])
        self._definir("semErro", r["curvas"]["norma"][0][2] == 0)
        self._tem_resultado = True
        self._definir("estado", "poucos" if ficha["pares"] < MINIMO_PARES else "pronto")

    @staticmethod
    def _dados_curvas(r: dict, ficha: dict, limiar: float) -> dict:
        series = [{"nome": qualidade_erc.NOMES[c], "cor": cor, "estilo": "linha",
                   "pontos": [[f, fnmr] for f, fnmr, _, _ in r["curvas"][c]]} for c, cor in SERIES]
        series.append({"nome": "Descarte ao acaso", "cor": "neutro", "estilo": "linha", "tracejada": True,
                       "pontos": [[f, fnmr] for f, fnmr, _, _ in r["aleatorio"]]})
        maior = max([p[1] for s in series for p in s["pontos"] if p[1] == p[1]] + [0.01])
        return {"titulo": "Erro × descarte", "subtitulo": f"FNMR no limiar em vigor ({num(limiar, 3)})",
                "n": f"N = {inteiro(ficha['pares'])} pares genuínos · {inteiro(ficha['amostras'])} amostras",
                "selos": [SINTETICO], "resumo": r["leitura"],
                "eixoX": {"rotulo": "Pares descartados (%)", "min": 0.0, "max": 0.3, "formato": "%"},
                "eixoY": {"rotulo": "FNMR no limiar em vigor (%)", "min": 0.0, "max": maior * 1.15, "formato": "%"},
                "series": series}

    def _limpar_dados(self) -> None:
        self._tem_resultado = False
        for nome, valor in (("ficha", {}), ("curvas", {}), ("tabela", []), ("leitura", ""), ("semErro", False)):
            self._definir(nome, valor)

    def preparar_captura(self, variante: str = "") -> None:
        self.usarFotosTeste()
        self.calcular()
