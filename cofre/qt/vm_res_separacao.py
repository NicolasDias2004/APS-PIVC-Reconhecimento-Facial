"""Aba Separação de Resultados (v2): genuíno × impostor com N, teto de erro e um limiar de estudo.

O limiar de estudo é só uma propriedade deste ViewModel e um argumento das funções de métrica:
não existe botão de aplicar, e `config` e `config_usuario.json` ficam como estavam.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
from PySide6.QtCore import Signal, Slot

from cofre import amostra_lab, config, leitura_ro, metricas, protocolos

from . import formatos
from .base import objeto, prop
from .base_v2 import ViewModelAba
from .modelos import ModeloLista
from .trabalhos import Trabalho

PROTOCOLOS = ("fotos_teste", "pasta", "galeria")
MINIMO_PARES = 30
LIMIARES_TABELA = tuple(round(0.20 + 0.05 * k, 2) for k in range(11))     # 0,20 a 0,70
FMR_ALVO = 0.01
_VAZIO_PADRAO = "Escolha a fonte dos pares e calcule a separação entre genuínos e impostores."


def _limiar_vigor() -> float:
    return float(config.LIMIAR_COSSENO)


def _taxa_cartao(k: int, n: int) -> tuple[str, str]:
    """Valor e detalhe de um cartão de taxa; zero observado nunca vira "0 %"."""
    if n <= 0:
        return formatos.SEM_VALOR, "sem pares"
    if k == 0:
        return f"0 de {formatos.inteiro(n)}", f"teto {formatos.pct_valor(metricas.teto(0, n))}"
    lo, hi = metricas.wilson(k, n)
    return formatos.pct(k, n), f"{formatos.inteiro(k)} de {formatos.inteiro(n)} · {formatos.num(100 * lo, 1)} a {formatos.num(100 * hi, 1)} %"


def _taxa_curta(k: int, n: int) -> str:
    if n <= 0:
        return formatos.SEM_VALOR
    return f"0 de {formatos.inteiro(n)}" if k == 0 else f"{formatos.pct(k, n)} ({formatos.inteiro(k)} de {formatos.inteiro(n)})"


def _resumo_descritor(nome: str, g: np.ndarray, i: np.ndarray) -> dict:
    a = metricas.auc(g, i)
    lim, taxa = metricas.eer(metricas.curva(g, i))
    eer_texto = "nenhum erro" if taxa == 0 else formatos.pct_valor(taxa)      # zero observado nunca vira "0 %"
    return {"nome": nome, "auc": formatos.num(a, 3), "eer": eer_texto,
            "dprime": formatos.num(metricas.d_prime(g, i), 2), "_auc": a}


def calcular_resultado(prot: protocolos.Protocolo) -> dict:
    """Tudo o que não depende do limiar de estudo, já em tipos do Python (roda no Trabalho)."""
    g = np.sort(np.asarray(prot.genuinos, dtype=np.float64))
    i = np.sort(np.asarray(prot.impostores, dtype=np.float64))
    c = metricas.curva(g, i)
    eer_lim, eer_taxa = metricas.eer(c)
    descritores = [_resumo_descritor("SFace", g, i)] if prot.descritores else []
    for nome in protocolos.DESCRITORES_LBP:
        if nome in prot.descritores:
            descritores.append(_resumo_descritor(nome, *prot.descritores[nome]))
    return {"chave": prot.chave, "g": g, "i": i, "ficha": dict(prot.ficha), "selos": list(prot.selos),
            "auc": metricas.auc(g, i), "eer": (eer_lim, eer_taxa), "dprime": metricas.d_prime(g, i),
            "fnmr_1": metricas.fnmr_em_fmr(c, FMR_ALVO), "hist": metricas.histograma(g, i),
            "roc": metricas.roc(c, int(i.size), int(g.size)), "descritores": descritores}


class ResSeparacaoVM(ViewModelAba):
    VARIANTES_CAPTURA = ("galeria",)

    protocoloMudou = Signal()
    pastaMudou = Signal()
    fichaMudou = Signal()
    selosMudou = Signal()
    histogramaMudou = Signal()
    rocMudou = Signal()
    cartoesMudou = Signal()
    limiarVigorMudou = Signal()
    limiarEstudoMudou = Signal()
    limiarVigorTextoMudou = Signal()
    noEstudoMudou = Signal()
    descritoresMudou = Signal()
    fraseDescritoresMudou = Signal()
    semErroMudou = Signal()
    textoSemErroMudou = Signal()
    pontosLinhasMudou = Signal()
    vazioTextoMudou = Signal()
    avisoPoucosMudou = Signal()

    protocolo = prop(str, "protocolo", protocoloMudou)
    pasta = prop(str, "pasta", pastaMudou)
    ficha = prop("QVariantMap", "ficha", fichaMudou)
    selos = prop("QVariantList", "selos", selosMudou)
    histograma = prop("QVariantMap", "histograma", histogramaMudou)
    roc = prop("QVariantMap", "roc", rocMudou)
    cartoes = prop("QVariantList", "cartoes", cartoesMudou)
    limiarVigor = prop(float, "limiarVigor", limiarVigorMudou)
    limiarEstudo = prop(float, "limiarEstudo", limiarEstudoMudou)
    limiarVigorTexto = prop(str, "limiarVigorTexto", limiarVigorTextoMudou)
    noEstudo = prop("QVariantMap", "noEstudo", noEstudoMudou)
    descritores = prop("QVariantList", "descritores", descritoresMudou)
    fraseDescritores = prop(str, "fraseDescritores", fraseDescritoresMudou)
    semErro = prop(bool, "semErro", semErroMudou)
    textoSemErro = prop(str, "textoSemErro", textoSemErroMudou)
    pontosLinhas = prop("QVariantList", "pontosLinhas", pontosLinhasMudou)
    vazioTexto = prop(str, "vazioTexto", vazioTextoMudou)
    avisoPoucos = prop(str, "avisoPoucos", avisoPoucosMudou)
    pontos = objeto("_pontos")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        vigor = _limiar_vigor()
        self._iniciar(protocolo="", pasta="", ficha={}, selos=[], histograma={}, roc={}, cartoes=[],
                      limiarVigor=vigor, limiarEstudo=vigor, limiarVigorTexto=formatos.num(vigor),
                      noEstudo={}, descritores=[], fraseDescritores="", semErro=False, textoSemErro="",
                      pontosLinhas=[], vazioTexto=_VAZIO_PADRAO, avisoPoucos="")
        self._pontos = ModeloLista(["id", "limiar", "fmr", "fnmr", "tetoFmr", "tetoFnmr"], self)
        self._res: dict | None = None
        self._exportacao = Trabalho(aplicacao.extensoes.trabalhos, self)

    # ------------------------------------------------------------------ slots
    @Slot(str)
    def definirProtocolo(self, valor: str) -> None:
        if valor not in PROTOCOLOS or valor == self._v["protocolo"]:
            return
        self.trabalho.cancelar()
        self._definir("protocolo", valor)
        self._limpar_dados()
        self._vazio(_VAZIO_PADRAO if valor != "pasta" or self._v["pasta"] else
                    "Escolha uma pasta com uma subpasta por pessoa.")

    @Slot(str)
    def definirPasta(self, url: str) -> None:
        caminho = formatos.caminho_de_url(url)
        self._definir("pasta", str(caminho) if caminho is not None else "")
        self._definir("protocolo", "pasta")
        self._limpar_dados()
        self._vazio(_VAZIO_PADRAO)

    @Slot()
    def recarregar(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        if self._v["protocolo"] == "":
            self._vazio(_VAZIO_PADRAO)
            return
        self.calcular()

    @Slot()
    def calcular(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        protocolo = self._v["protocolo"]
        if protocolo == "":
            self._vazio(_VAZIO_PADRAO)
            return
        if protocolo == "pasta" and not self._v["pasta"]:
            self._vazio("Escolha uma pasta com uma subpasta por pessoa.")
            return
        pipeline = self.app.pipeline
        if protocolo != "galeria" and pipeline is None:
            self._indisponivel("Os modelos ainda estão carregando.")
            return
        vigor = _limiar_vigor()
        self._definir("limiarVigor", vigor)
        self._definir("limiarVigorTexto", formatos.num(vigor))
        caminho = self.caminho_db
        demo = bool(self.app.extensoes.baseDemonstracao)
        pasta = self._v["pasta"]

        def fn(sinal):
            try:
                if protocolo == "galeria":
                    prot = protocolos.de_galeria(caminho, demonstracao=demo, sinal=sinal)
                elif protocolo == "fotos_teste":
                    prot = protocolos.de_pasta(amostra_lab.PASTA_FOTOS_TESTE, pipeline, chave="fotos_teste", sinal=sinal)
                else:
                    prot = protocolos.de_pasta(pasta, pipeline, chave="pasta", sinal=sinal)
            except leitura_ro.BancoIndisponivel:
                return {"indisponivel": "Análise disponível só com banco em arquivo."}
            sinal.conferir()
            return calcular_resultado(prot)

        self._definir("erro", "")
        self._definir("estado", "carregando")
        self.trabalho.executar(fn, self._ao_terminar)

    @Slot(float)
    def definirLimiarEstudo(self, valor: float) -> None:
        if valor != valor:
            return
        valor = round(min(1.0, max(0.0, float(valor))), 3)
        self._definir("limiarEstudo", valor)
        if self._res is not None:
            self._publicar_estudo()

    @Slot()
    def exportarCsv(self) -> None:
        linhas = self._pontos.itens()
        if not linhas or self._res is None:
            return
        ficha = self._res["ficha"]
        selos = list(self._res["selos"])
        if self.app.extensoes.baseDemonstracao and protocolos.SELO_DEMONSTRACAO not in selos:
            selos.append(protocolos.SELO_DEMONSTRACAO)
        cabecalho = [f"# {s}" for s in selos]
        cabecalho.append(f"# N = {ficha.get('pares_genuinos', 0)} pares genuínos · {ficha.get('pares_impostores', 0)} pares impostores")
        cabecalho.append(f"# limiar em vigor {formatos.num(self._v['limiarVigor'])}")
        corpo = ["limiar;fmr;fnmr;teto_fmr;teto_fnmr"]
        corpo += [";".join(str(l[k]) for k in ("limiar", "fmr", "fnmr", "tetoFmr", "tetoFnmr")) for l in linhas]
        texto = "\n".join(cabecalho + corpo) + "\n"
        destino = config.RELATORIOS_DIR / f"pontos_operacao_{formatos.carimbo_arquivo(datetime.now())}.csv"

        def fn(sinal):
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(texto, encoding="utf-8")
            return destino

        def fim(resultado, erro):
            if erro:
                self.app.notificar("erro", f"Não foi possível salvar o CSV: {erro}")
            else:
                self.app.notificar("info", f"Pontos de operação salvos em {resultado.name}")

        self._exportacao.executar(fn, fim)

    def preparar_captura(self, variante: str = "") -> None:
        self.definirProtocolo("galeria" if variante == "galeria" else "fotos_teste")
        self.calcular()

    def ao_pipeline_pronto(self) -> None:
        if self._v["estado"] == "indisponivel" and self._v["protocolo"] != "galeria":
            self.pedir_recarga()

    # ------------------------------------------------------------------ estado
    def _vazio(self, texto: str) -> None:
        self._definir("vazioTexto", texto)
        self._definir("erro", "")
        self._definir("estado", "vazio")

    def _limpar_dados(self) -> None:
        self._res = None
        for nome, valor in (("ficha", {}), ("selos", []), ("histograma", {}), ("roc", {}), ("cartoes", []),
                            ("noEstudo", {}), ("descritores", []), ("fraseDescritores", ""), ("semErro", False),
                            ("textoSemErro", ""), ("pontosLinhas", []), ("avisoPoucos", "")):
            self._definir(nome, valor)
        self._pontos.definir([])

    def _ao_terminar(self, res, erro: str) -> None:
        if erro:
            self._falhar(f"Não foi possível calcular a separação: {erro}")
            return
        if "indisponivel" in res:
            self._indisponivel(res["indisponivel"])
            return
        self._limpar_dados()
        ficha = res["ficha"]
        if ficha["imagens"] == 0:
            self._vazio("Não há imagens nesta fonte." if res["chave"] != "galeria" else
                        "Não há amostras na galeria: cadastre ao menos duas pessoas.")
            return
        if res["g"].size == 0:
            self._vazio("Não há duas amostras da mesma pessoa.")
            return
        self._res = res
        self._publicar_fixos()
        self._publicar_estudo()
        n_g, n_i = int(res["g"].size), int(res["i"].size)
        if n_g < MINIMO_PARES or n_i < MINIMO_PARES:
            self._definir("avisoPoucos", f"Amostra pequena (N genuínos = {formatos.inteiro(n_g)}, "
                                         f"N impostores = {formatos.inteiro(n_i)}): os números são ilustrativos.")
            self._definir("estado", "poucos")
        else:
            self._definir("estado", "pronto")

    def _publicar_fixos(self) -> None:
        res = self._res
        g, i, ficha = res["g"], res["i"], res["ficha"]
        n_g, n_i = int(g.size), int(i.size)
        vigor = self._v["limiarVigor"]
        amostras = ficha.get("amostras_por_pessoa", [])
        self._definir("ficha", {
            "pessoas": formatos.inteiro(ficha["pessoas"]), "imagens": formatos.inteiro(ficha["imagens"]),
            "semRosto": formatos.inteiro(ficha["sem_rosto"]), "paresGenuinos": formatos.inteiro(n_g),
            "paresImpostores": formatos.inteiro(n_i),
            "amostrasPorPessoa": " · ".join(formatos.inteiro(a) for a in amostras) if amostras else formatos.SEM_VALOR})
        self._definir("selos", list(res["selos"]))
        t = metricas.taxas(g, i, vigor)
        eer_lim, eer_taxa = res["eer"]
        cartoes = [
            {"rotulo": "Pares genuínos", "valor": formatos.inteiro(n_g), "detalhe": f"{formatos.inteiro(ficha['pessoas'])} pessoas"},
            {"rotulo": "Pares impostores", "valor": formatos.inteiro(n_i), "detalhe": "pessoas diferentes"},
            {"rotulo": "AUC", "valor": formatos.num(res["auc"], 3), "detalhe": "1 = separação perfeita · 0,5 = acaso"},
        ]
        if eer_taxa == eer_taxa and eer_taxa <= 0:
            teto_eer = metricas.teto(0, min(n_g, n_i))
            cartoes.append({"rotulo": "EER", "valor": "nenhum erro", "detalhe": f"teto {formatos.pct_valor(teto_eer)}"})
        else:
            cartoes.append({"rotulo": "EER", "valor": formatos.pct_valor(eer_taxa), "detalhe": f"no limiar {formatos.num(eer_lim)}"})
        cartoes.append({"rotulo": "d′", "valor": formatos.num(res["dprime"], 2), "detalhe": "distância entre as médias"})
        valor, detalhe = _taxa_cartao(t["k_fnm"], n_g)
        cartoes.append({"rotulo": "FNMR no limiar em vigor", "valor": valor, "detalhe": detalhe})
        valor, detalhe = _taxa_cartao(t["k_fm"], n_i)
        cartoes.append({"rotulo": "FMR no limiar em vigor", "valor": valor, "detalhe": detalhe})
        f1 = res["fnmr_1"]
        if f1 is None:
            cartoes.append({"rotulo": "FNMR com FMR de 1 %", "valor": formatos.SEM_VALOR, "detalhe": "FMR de 1 % não alcançada"})
        else:
            valor, detalhe = _taxa_cartao(int(round(f1 * n_g)), n_g)
            cartoes.append({"rotulo": "FNMR com FMR de 1 %", "valor": valor, "detalhe": detalhe})
        self._definir("cartoes", cartoes)
        sem_erro = t["k_fm"] == 0 and t["k_fnm"] == 0
        self._definir("semErro", sem_erro)
        self._definir("textoSemErro", (
            f"Nenhum erro observado: com {formatos.inteiro(n_i)} pares impostores e {formatos.inteiro(n_g)} genuínos, "
            f"o teto de erro é {formatos.pct_valor(metricas.teto(0, n_i))} (FMR) e "
            f"{formatos.pct_valor(metricas.teto(0, n_g))} (FNMR).") if sem_erro else "")
        pontos = []
        for k, lim in enumerate(sorted(set(LIMIARES_TABELA) | {round(vigor, 3)})):
            tt = metricas.taxas(g, i, lim)
            texto_lim = formatos.num(lim, 3) + (" · em vigor" if abs(lim - vigor) < 5e-4 else "")
            pontos.append({"id": k, "limiar": texto_lim, "fmr": _taxa_curta(tt["k_fm"], n_i),
                           "fnmr": _taxa_curta(tt["k_fnm"], n_g),
                           "tetoFmr": formatos.pct_valor(metricas.teto(tt["k_fm"], n_i)),
                           "tetoFnmr": formatos.pct_valor(metricas.teto(tt["k_fnm"], n_g))})
        self._pontos.definir(pontos)
        self._definir("pontosLinhas", pontos)
        desc = res["descritores"]
        self._definir("descritores", [{k: v for k, v in d.items() if not k.startswith("_")} for d in desc])
        self._definir("fraseDescritores", self._frase_descritores(desc))

    @staticmethod
    def _frase_descritores(desc: list[dict]) -> str:
        if len(desc) < 3:
            return ""
        s, a, b = (d["_auc"] for d in desc[:3])
        if s == s and a == a and b == b and s >= 0.9 and max(a, b) < 0.75:
            return (f"Só o SFace separa as pessoas neste protocolo: AUC {formatos.num(s, 2)} contra "
                    f"{formatos.num(a, 2)} e {formatos.num(b, 2)}.")
        return (f"AUC neste protocolo: SFace {formatos.num(s, 2)}, LBP · cosseno {formatos.num(a, 2)}, "
                f"LBP · qui-quadrado {formatos.num(b, 2)}.")

    def _publicar_estudo(self) -> None:
        res = self._res
        g, i = res["g"], res["i"]
        n_g, n_i = int(g.size), int(i.size)
        vigor, estudo = self._v["limiarVigor"], self._v["limiarEstudo"]
        # searchsorted nos escores já ordenados: abaixo de 1 ms mesmo com milhares de pares
        k_fm = n_i - int(np.searchsorted(i, estudo, side="left"))
        k_fnm = int(np.searchsorted(g, estudo, side="left"))
        fmr_t, fnmr_t = metricas.texto_taxa(k_fm, n_i), metricas.texto_taxa(k_fnm, n_g)
        self._definir("noEstudo", {"fmr": fmr_t, "fnmr": fnmr_t,
                                   "frase": f"Se o limiar fosse {formatos.num(estudo)}: FMR {fmr_t} · FNMR {fnmr_t}"})
        marcadores = [{"x": vigor, "rotulo": f"limiar em vigor {formatos.num(vigor)}", "estilo": "vigor"}]
        if abs(estudo - vigor) > 5e-4:
            marcadores.append({"x": estudo, "rotulo": f"estudo {formatos.num(estudo)}", "estilo": "estudo"})
        h = res["hist"]
        selos = list(res["selos"])
        if abs(estudo - vigor) > 5e-4:
            selos.append("Parâmetros de estudo")
        n_texto = f"N = {formatos.inteiro(n_g)} genuínos · {formatos.inteiro(n_i)} impostores"
        self._definir("histograma", {
            "titulo": "Genuínos × impostores", "subtitulo": "Similaridade (cosseno do SFace) por par",
            "n": n_texto, "selos": selos,
            "resumo": f"Histograma de {n_g} pares genuínos e {n_i} impostores entre -0,2 e 1,0.",
            "eixoX": {"rotulo": "similaridade", "min": metricas.FAIXA_HISTOGRAMA[0], "max": metricas.FAIXA_HISTOGRAMA[1],
                      "formato": "0.0"},
            "eixoY": {"rotulo": "pares", "formato": "int"},
            "bordas": h["bordas"],
            "series": [{"nome": "Genuínos", "cor": "serie0", "contagens": h["genuinos"], "sentido": 1},
                       {"nome": "Impostores", "cor": "neutro", "contagens": h["impostores"], "sentido": 1}],
            "marcadoresV": marcadores})
        piso = 1 / (2 * n_i) if n_i else 0.0
        anotacoes = []
        for nome, lim in (("em vigor", vigor), ("estudo", estudo)):
            if nome == "estudo" and abs(estudo - vigor) <= 5e-4:
                continue
            tt = metricas.taxas(g, i, lim)
            anotacoes.append({"x": max(tt["fmr"], piso), "y": 1 - tt["fnmr"], "texto": nome})
        self._definir("roc", {
            "titulo": "Curva ROC", "subtitulo": "Taxa de genuínos aceitos contra a de falso casamento (eixo log)",
            "n": n_texto, "selos": selos,
            "resumo": "Curva ROC do SFace neste protocolo.",
            "vazio": "Sem pares para a curva.",
            "eixoX": {"rotulo": "FMR", "escala": "log", "min": piso if piso > 0 else 1e-4, "max": 1.0, "formato": "%"},
            "eixoY": {"rotulo": "TAR", "min": 0.0, "max": 1.0, "formato": "%"},
            "series": [{"nome": "SFace", "cor": "serie0", "pontos": res["roc"], "estilo": "degrau"}],
            "anotacoes": anotacoes})

