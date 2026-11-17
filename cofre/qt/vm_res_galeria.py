"""Aba Galeria de Resultados (v2): a fase 4 como geometria e o cadastro auditável.

Mostra o mapa das amostras gravadas (PCA em 2D), a matriz pessoa × pessoa e a saúde de cada
cadastro. Os alertas são texto consultivo: esta aba não desativa, não remove e não bloqueia ninguém.
Rótulos de pessoa só por `vm_privacidade` (anônimos por padrão), lidos dentro do Trabalho.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from cofre import config, galeria_analise, leitura_ro

from . import formatos, vm_privacidade
from .base import objeto, prop
from .base_v2 import ViewModelAba
from .modelos import ModeloLista

MAX_GRUPOS = 16
SITUACAO_TEXTO = {"boa": "Boa", "poucas": "Poucas amostras", "dispersa": "Dispersa",
                  "proxima": "Perto de outra pessoa", "duplicidade": "Possível duplicidade"}
PAPEIS_SAUDE = ["id", "rotulo", "nivel", "amostras", "coesao", "maisFraca", "vizinho", "folga", "situacao",
                "situacaoTexto", "recomendacao"]


class ResGaleriaVM(ViewModelAba):
    resumoMudou = Signal()
    dispersaoMudou = Signal()
    matrizMudou = Signal()
    limiarMudou = Signal()
    limiarTextoMudou = Signal()
    saudeLinhasMudou = Signal()
    notaInativosMudou = Signal()

    resumo = prop("QVariantMap", "resumo", resumoMudou)
    dispersao = prop("QVariantMap", "dispersao", dispersaoMudou)
    matriz = prop("QVariantMap", "matriz", matrizMudou)
    limiar = prop(float, "limiar", limiarMudou)
    limiarTexto = prop(str, "limiarTexto", limiarTextoMudou)
    saudeLinhas = prop("QVariantList", "saudeLinhas", saudeLinhasMudou)
    notaInativos = prop(str, "notaInativos", notaInativosMudou)
    saude = objeto("_saude")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        limiar = float(config.LIMIAR_COSSENO)
        self._iniciar(resumo={}, dispersao={}, matriz={}, limiar=limiar, limiarTexto=formatos.num(limiar),
                      saudeLinhas=[], notaInativos="")
        self._saude = ModeloLista(PAPEIS_SAUDE, self)
        self._privacidade = aplicacao.extensoes.obter("privacidade")
        sinal = getattr(self._privacidade, "mostrarNomesMudou", None)
        if sinal is not None:
            sinal.connect(self.ao_mudar_nomes)

    # ------------------------------------------------------------------ slots
    @Slot()
    def recarregar(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        limiar = float(config.LIMIAR_COSSENO)
        self._definir("limiar", limiar)
        self._definir("limiarTexto", formatos.num(limiar))
        caminho = self.caminho_db
        com_nomes = bool(getattr(self._privacidade, "mostrarNomes", False))

        def fn(sinal):
            try:
                gal = leitura_ro.galeria(caminho, apenas_ativos=True)
                rotulos = vm_privacidade.rotulos_para(caminho, com_nomes)
            except leitura_ro.BancoIndisponivel:
                return {"indisponivel": "Análise disponível só com banco em arquivo."}
            sinal.conferir()
            pessoas = len(set(int(d) for d in gal.donos))
            if pessoas < 2:
                return {"vazio": True, "inativos": gal.inativos}
            analise = galeria_analise.analisar(gal, limiar, {p: vm_privacidade.rotulo_de(rotulos, p)
                                                              for p in set(int(d) for d in gal.donos)})
            return {"analise": analise, "rotulos": rotulos, "niveis": dict(gal.niveis), "inativos": gal.inativos}

        self._definir("erro", "")
        self._definir("estado", "carregando")
        self.trabalho.executar(fn, self._ao_terminar)

    @Slot()
    def abrirUsuarios(self) -> None:
        self.app.navegar("usuarios")

    @Slot()
    def abrirCadastro(self) -> None:
        self.app.navegar("cadastro")

    def preparar_captura(self, variante: str = "") -> None:
        self.recarregar()

    # ------------------------------------------------------------------ estado
    def _limpar_dados(self) -> None:
        for nome, valor in (("resumo", {}), ("dispersao", {}), ("matriz", {}), ("saudeLinhas", []),
                            ("notaInativos", "")):
            self._definir(nome, valor)
        self._saude.definir([])

    def _ao_terminar(self, res, erro: str) -> None:
        if erro:
            self._falhar(f"Não foi possível analisar a galeria: {erro}")
            return
        if "indisponivel" in res:
            self._indisponivel(res["indisponivel"])
            return
        self._limpar_dados()
        if res.get("vazio"):
            self._definir("estado", "vazio")
            return
        a = res["analise"]
        rotulos = res["rotulos"]
        limiar = self._v["limiar"]
        nome = {p: vm_privacidade.rotulo_de(rotulos, p) for p in a.ids}
        com_achado = sum(1 for p in a.ids if a.situacao[p] != "boa")
        pares_risco = 0
        destaques = []
        pp = len(a.ids)
        for i in range(pp):
            for j in range(pp):
                v = a.matriz[i, j]
                if i != j and v == v and v >= limiar - galeria_analise.MARGEM_PROXIMA:
                    if j > i:
                        pares_risco += 1
                if i != j and v == v and v >= limiar:
                    destaques.append([i, j])
        inativos = int(res["inativos"])
        self._definir("resumo", {"pessoas": formatos.inteiro(pp), "amostras": formatos.inteiro(int(a.donos.size)),
                                 "comAchado": formatos.inteiro(com_achado), "paresDeRisco": formatos.inteiro(pares_risco),
                                 "inativos": formatos.inteiro(inativos)})
        if inativos:
            self._definir("notaInativos", f"{formatos.inteiro(inativos)} pessoa(s) inativa(s) ficam fora: "
                                          "a galeria é a mesma que o terminal usa.")
        self._definir("dispersao", self._dados_dispersao(a, nome))
        self._definir("matriz", self._dados_matriz(a, nome, limiar, destaques))
        linhas = []
        for p in a.ids:
            viz = a.vizinho[p]
            fraca = a.mais_fraca[p]
            linhas.append({
                "id": p, "rotulo": nome[p], "nivel": formatos.inteiro(res["niveis"].get(p)),
                "amostras": formatos.inteiro(a.amostras[p]), "coesao": formatos.num(a.coesao[p], 2),
                "maisFraca": f"nº {fraca[0]} · {formatos.num(fraca[1], 2)}" if fraca else formatos.SEM_VALOR,
                "vizinho": f"{nome.get(viz[0], vm_privacidade.rotulo_de(rotulos, viz[0]))} · {formatos.num(viz[1], 2)}" if viz else formatos.SEM_VALOR,
                "folga": formatos.num(limiar - viz[1], 2) if viz else formatos.SEM_VALOR,
                "situacao": a.situacao[p], "situacaoTexto": SITUACAO_TEXTO[a.situacao[p]],
                "recomendacao": a.recomendacao[p]})
        self._saude.definir(linhas)
        self._definir("saudeLinhas", linhas)
        self._definir("estado", "poucos" if pp < 3 else "pronto")

    @staticmethod
    def _dados_dispersao(a, nome: dict) -> dict:
        grupos, outros = [], []
        for k, p in enumerate(a.ids):
            idx = [int(i) for i in range(a.donos.size) if int(a.donos[i]) == p]
            pts = [[float(a.pontos[i, 0]), float(a.pontos[i, 1])] for i in idx]
            if k >= MAX_GRUPOS:
                outros.extend(pts)
                continue
            grupos.append({"nome": nome[p], "cor": k % 4, "forma": (k // 4) % 4, "pontos": pts,
                           "rotulos": [f"{nome[p]} · amostra {int(a.numeros[i])}" for i in idx],
                           "centro": list(a.centros[p])})
        v1, v2 = a.variancia
        dados = {"titulo": "Mapa de identidades",
                 "subtitulo": "Projeção em duas dimensões das amostras gravadas (PCA) · cada marca é uma amostra",
                 "n": f"N = {formatos.inteiro(int(a.donos.size))} amostras · {formatos.inteiro(len(a.ids))} pessoas",
                 "resumo": f"Mapa com {len(a.ids)} pessoas e {int(a.donos.size)} amostras.",
                 "vazio": "Poucas amostras para o mapa.",
                 "eixoX": {"rotulo": f"Componente 1 ({formatos.pct_valor(v1, 0)})", "formato": "0.00"},
                 "eixoY": {"rotulo": f"Componente 2 ({formatos.pct_valor(v2, 0)})", "formato": "0.00"},
                 "grupos": grupos, "rotularCentros": True}
        if outros:
            dados["outros"] = outros
        return dados

    @staticmethod
    def _dados_matriz(a, nome: dict, limiar: float, destaques: list) -> dict:
        rot = [nome[p] for p in a.ids]
        valores = [[None if v != v else round(float(v), 3) for v in linha] for linha in a.matriz]
        return {"titulo": "Similaridade entre pessoas",
                "subtitulo": "Diagonal = coesão da própria pessoa · fora = par mais parecido",
                "n": f"{formatos.inteiro(len(rot))} pessoas", "resumo": "Matriz de similaridade entre as pessoas da galeria.",
                "linhas": rot, "colunas": rot, "valores": valores, "min": 0.0, "max": 1.0,
                "mostrarValores": len(rot) <= 12, "formato": "0.00", "destaques": destaques, "marcaEscala": limiar}
