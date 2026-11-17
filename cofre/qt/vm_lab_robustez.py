"""Aba Robustez do Laboratório PIVC (v2): o medidor ao vivo de uma degradação, as curvas das oito
famílias com o ponto de quebra e a ablação (o que cada fase segura), tudo sintético.

A rede usada é a do `LoteSFace`, fora de qualquer caminho do terminal. As imagens degradadas ficam só
em memória e no provedor (`lab/robustez/`), que é limpo quando a aba sai da tela. O CSV leva só
família, intensidade, rótulo e similaridade.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Signal, Slot

from .. import amostra_lab, config, degradacoes, robustez
from .. import fase2_preprocessamento as f2
from . import vm_figuras
from .base import prop
from .base_v2 import ViewModelAba
from .formatos import carimbo_arquivo, num
from .imagens import bgr_para_qimage
from .trabalhos import Trabalho
from .vm_laboratorio import ler_imagem

PREFIXO = "lab/robustez/"
NOTA_RUIDO = "O ruído aumentou a nitidez medida (variância do Laplaciano): esta medida não enxerga ruído."
SINTETICO = "Sintético"


def _texto_quebra(c: robustez.CurvaRobustez) -> str:
    if c.quebra_nivel is None:
        return "não cruzou o limiar"
    if c.quebra_nivel <= c.niveis[0]:
        return "abaixo do limiar já sem degradação"
    rotulo = c.quebra_rotulo
    return "deixa de reconhecer com " + rotulo.replace(" = ", " ≥ ") if " = " in rotulo \
        else "deixa de reconhecer a partir de " + rotulo


class LabRobustezVM(ViewModelAba):
    familiasMudou = Signal()
    familiaMudou = Signal()
    intensidadeMudou = Signal()
    rotuloIntensidadeMudou = Signal()
    similaridadeMudou = Signal()
    limiarMudou = Signal()
    semReferenciaMudou = Signal()
    curvasMudou = Signal()
    quebrasMudou = Signal()
    varrendoMudou = Signal()
    ablacaoMudou = Signal()
    ablacaoEstadoMudou = Signal()
    notaMudou = Signal()
    revisaoMudou = Signal()
    referenciaRotuloMudou = Signal()

    familias = prop("QVariantList", "familias", familiasMudou)
    familia = prop(str, "familia", familiaMudou)
    intensidade = prop(float, "intensidade", intensidadeMudou)
    rotuloIntensidade = prop(str, "rotuloIntensidade", rotuloIntensidadeMudou)
    similaridade = prop(float, "similaridade", similaridadeMudou)
    limiar = prop(float, "limiar", limiarMudou)
    semReferencia = prop(bool, "semReferencia", semReferenciaMudou)
    curvas = prop("QVariantList", "curvas", curvasMudou)
    quebras = prop("QVariantList", "quebras", quebrasMudou)
    varrendo = prop(bool, "varrendo", varrendoMudou)
    ablacao = prop("QVariantList", "ablacao", ablacaoMudou)
    ablacaoEstado = prop(str, "ablacaoEstado", ablacaoEstadoMudou)
    nota = prop(str, "nota", notaMudou)
    revisao = prop(int, "revisao", revisaoMudou)
    referenciaRotulo = prop(str, "referenciaRotulo", referenciaRotuloMudou)

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        fam = degradacoes.FAMILIAS["desfoque"]
        self._iniciar(familias=[{"chave": f.chave, "nome": f.nome} for f in degradacoes.FAMILIAS.values()],
                      familia="desfoque", intensidade=0.0, rotuloIntensidade=fam.rotulo(0.0), similaridade=-1.0,
                      limiar=float(config.LIMIAR_COSSENO), semReferencia=False, curvas=[], quebras=[], varrendo=False,
                      ablacao=[], ablacaoEstado="nao_pedida", nota="", revisao=0, referenciaRotulo="")
        self._alinhado: np.ndarray | None = None
        self._referencia: np.ndarray | None = None
        self._brutas: list[robustez.CurvaRobustez] = []
        self._medidor = Trabalho(aplicacao.extensoes.trabalhos, self)
        self._trab_ablacao = Trabalho(aplicacao.extensoes.trabalhos, self)
        self._trab_csv = Trabalho(aplicacao.extensoes.trabalhos, self)
        self.trabalho.ocupadoMudou.connect(self._ao_varrer_ocupado)
        self.lab = aplicacao.extensoes.obter("laboratorio")
        self.lab.amostraMudou.connect(self.pedir_recarga)
        self.lab.referenciaMudou.connect(self.pedir_recarga)

    # ------------------------------------------------------------------ amostra e medidor
    @Slot()
    def recarregar(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        self.trabalho.cancelar()
        self._definir("limiar", float(config.LIMIAR_COSSENO))
        amostra = getattr(self.lab, "amostra", None)
        if amostra is None or amostra.alinhado is None:
            self._limpar_dados()
            self._definir("erro", "")
            self._definir("estado", "vazio")
            return
        referencia = getattr(self.lab, "referencia", None)
        sem_ref = referencia is None or referencia.embedding is None
        self._alinhado = np.array(amostra.alinhado, copy=True)
        self._referencia = np.array(amostra.embedding if sem_ref else referencia.embedding, copy=True)
        self._definir("semReferencia", sem_ref)
        self._definir("referenciaRotulo", "a própria imagem" if sem_ref else (referencia.rotulo or "referência"))
        self._brutas = []
        self._definir("curvas", [])
        self._definir("quebras", [])
        self._definir("erro", "")
        self._definir("estado", "pronto")
        self._medir()

    def _medir(self) -> None:
        if self._alinhado is None:
            return
        alinhado, ref = self._alinhado, self._referencia
        familia, nivel = self._v["familia"], self._v["intensidade"]

        def medir(sinal):
            img = degradacoes.aplicar(alinhado, familia, nivel)
            sinal.conferir()
            sim = robustez.similaridade_degradada(alinhado, ref, familia, nivel)
            nota = ""
            if familia == "ruido" and nivel > 0 and f2.medir_nitidez(img) > f2.medir_nitidez(alinhado):
                nota = NOTA_RUIDO
            return sim, nota, bgr_para_qimage(img)

        self._medidor.executar(medir, self._ao_medir)

    def _ao_medir(self, resultado, erro: str) -> None:
        if erro or self._alinhado is None:
            self._definir("similaridade", -1.0)
            return
        sim, nota, imagem = resultado
        self.app.imagens.guardar(PREFIXO + "previa", imagem)
        self._definir("similaridade", float(sim))
        self._definir("nota", nota)
        self._definir("revisao", self._v["revisao"] + 1)

    @Slot(str)
    def definirFamilia(self, chave: str) -> None:
        if chave not in degradacoes.FAMILIAS or chave == self._v["familia"]:
            return
        self._definir("familia", chave)
        self._definir("rotuloIntensidade", degradacoes.FAMILIAS[chave].rotulo(self._v["intensidade"]))
        if self.ativa:
            self._medir()

    @Slot(float)
    def definirIntensidade(self, valor: float) -> None:
        valor = float(min(1.0, max(0.0, valor)))
        self._definir("intensidade", valor)
        self._definir("rotuloIntensidade", degradacoes.FAMILIAS[self._v["familia"]].rotulo(valor))
        if self.ativa:
            self._medir()

    # ------------------------------------------------------------------ varredura
    @Slot()
    def varrer(self) -> None:
        if not self.ativa or self._alinhado is None:
            return
        alinhado, ref, limiar = self._alinhado, self._referencia, float(config.LIMIAR_COSSENO)
        self._definir("progresso", 0.0)
        self.trabalho.executar(lambda sinal: robustez.varrer(alinhado, ref, limiar, sinal=sinal), self._ao_varrer)

    @Slot()
    def _ao_varrer_ocupado(self) -> None:
        self._definir("varrendo", self.trabalho.ocupado)

    def _ao_varrer(self, curvas, erro: str) -> None:
        if erro:
            self.app.notificar("erro", f"Não foi possível varrer: {erro}")
            return
        self._brutas = list(curvas)
        self._definir("curvas", [self._dados_curva(c) for c in curvas])
        self._definir("quebras", [{"familia": c.familia, "nome": c.nome, "texto": _texto_quebra(c)} for c in curvas])

    def _dados_curva(self, c: robustez.CurvaRobustez) -> dict:
        limiar = self._v["limiar"]
        marcas = [c.niveis[i] for i in (0, len(c.niveis) // 2, len(c.niveis) - 1)]
        fam = degradacoes.FAMILIAS[c.familia]
        menor = min(0.0, float(np.floor(min(c.similaridade) * 10) / 10))
        dados = {"titulo": c.nome, "n": "1 imagem", "selos": [SINTETICO],
                 "resumo": f"{c.nome}: similaridade com a referência em 12 intensidades.",
                 "eixoX": {"rotulo": "intensidade", "min": 0.0, "max": 1.0, "formato": "0.00", "marcas": marcas,
                           "marcasTexto": [fam.rotulo(m) for m in marcas]},
                 "eixoY": {"rotulo": "similaridade", "min": menor, "max": 1.0, "formato": "0.00"},
                 "series": [{"nome": c.nome, "cor": "serie0", "estilo": "linha",
                             "pontos": [[n, s] for n, s in zip(c.niveis, c.similaridade)], "rotulos": list(c.rotulos)}],
                 "marcadoresH": [{"y": limiar, "rotulo": f"limiar em vigor {num(limiar, 3)}", "estilo": "vigor"}]}
        if c.quebra_nivel is not None:
            dados["anotacoes"] = [{"x": c.quebra_nivel, "y": limiar, "texto": c.quebra_rotulo}]
        return dados

    @Slot()
    def cancelar(self) -> None:
        self.trabalho.cancelar()
        self._trab_ablacao.cancelar()
        if self._v["ablacaoEstado"] == "calculando":
            self._definir("ablacaoEstado", "nao_pedida")
        super().cancelar()

    # ------------------------------------------------------------------ ablação
    @Slot()
    def executarAblacao(self) -> None:
        if not self.ativa:
            return
        pipeline = self.app.pipeline
        fotos = amostra_lab.fotos_de_teste()
        if not fotos or pipeline is None:
            self._definir("ablacao", [])
            self._definir("ablacaoEstado", "sem_fotos")
            return
        limiar = float(config.LIMIAR_COSSENO)

        def medir(sinal):
            quadros = {p: [ler_imagem(c) for c in caminhos] for p, caminhos in fotos.items()}
            pares = [(q[0], q[1]) for q in quadros.values() if len(q) >= 2]
            alinh = robustez.ablacao_alinhamento(pares, pipeline, limiar, sinal=sinal)
            clahe = robustez.ablacao_clahe([f for q in quadros.values() for f in q], pipeline, sinal=sinal)
            return alinh, clahe

        self._definir("ablacaoEstado", "calculando")
        self._trab_ablacao.executar(medir, self._ao_ablacao)

    def _ao_ablacao(self, resultado, erro: str) -> None:
        if erro:
            self._definir("ablacao", [])
            self._definir("ablacaoEstado", "nao_pedida")
            self.app.notificar("erro", f"Não foi possível medir a ablação: {erro}")
            return
        alinh, clahe = resultado
        linhas = []
        cenario = f"Cabeça inclinada {num(alinh['graus'], 0)}°"
        for variante, chave, abaixo in (("com alinhamento", "com", "abaixo_com"), ("sem alinhamento", "sem", "abaixo_sem")):
            sims = alinh[chave]
            valor = f"{num(min(sims), 2)} a {num(max(sims), 2)}" if sims else "–"
            linhas.append({"cenario": cenario, "variante": variante, "valor": valor, "n": f"{alinh['n']} pares",
                           "leitura": f"{alinh[abaixo]} de {alinh['n']} abaixo do limiar"})
        for i, ganho in enumerate(clahe["ganhos"]):
            for variante, chave in (("fase 2 completa", "completa"), ("só redução", "reducao")):
                linhas.append({"cenario": f"Cena escura (ganho × {num(ganho, 2)})", "variante": variante,
                               "valor": f"detectados {clahe[chave][i]} de {clahe['n']}", "n": f"{clahe['n']} fotos",
                               "leitura": ""})
        self._definir("ablacao", linhas)
        self._definir("ablacaoEstado", "pronta")

    # ------------------------------------------------------------------ CSV
    @Slot()
    def exportarCsv(self) -> None:
        if not self._brutas:
            return
        curvas = list(self._brutas)
        destino = vm_figuras.pasta_figuras() / f"robustez_{carimbo_arquivo()}.csv"
        demo = bool(self.app.extensoes.baseDemonstracao)

        def gravar(sinal) -> Path:
            linhas = [f"# {SINTETICO}", "# N = 1 imagem"] + (["# Base de demonstração"] if demo else [])
            linhas.append("família;nível;rótulo;similaridade")
            for c in curvas:
                for n, r, s in zip(c.niveis, c.rotulos, c.similaridade):
                    linhas.append(f"{c.nome};{num(n, 3)};{r};{num(s, 4)}")
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text("\n".join(linhas) + "\n", encoding="utf-8-sig")
            return destino

        self._trab_csv.executar(gravar, self._ao_csv)

    def _ao_csv(self, caminho, erro: str) -> None:
        if erro:
            self.app.notificar("erro", f"Não foi possível salvar o CSV: {erro}")
            return
        self.app.notificar("info", f"CSV salvo em figuras/{caminho.name}")

    # ------------------------------------------------------------------ ciclo da aba
    def _limpar_dados(self) -> None:
        self._alinhado = self._referencia = None
        self._brutas = []
        self.app.imagens.remover_prefixo(PREFIXO)
        for nome, valor in (("similaridade", -1.0), ("semReferencia", False), ("curvas", []), ("quebras", []),
                            ("nota", ""), ("referenciaRotulo", "")):
            self._definir(nome, valor)

    def ao_desativar(self) -> None:
        super().ao_desativar()
        self._medidor.cancelar()
        self._trab_ablacao.cancelar()
        if self._v["ablacaoEstado"] == "calculando":
            self._definir("ablacaoEstado", "nao_pedida")
        self.app.imagens.remover_prefixo(PREFIXO)
        self._sujo = True

    def preparar_captura(self, variante: str = "") -> None:
        if self._alinhado is None:
            self.recarregar()
        self.varrer()
        self.executarAblacao()
