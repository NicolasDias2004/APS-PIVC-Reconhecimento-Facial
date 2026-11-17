"""Aba Fases do Laboratório PIVC (v2): a amostra do laboratório em cinco estações, com imagem,
medida e tempo de cada fase.

Com os parâmetros do sistema a aba examina a própria amostra do laboratório. Com parâmetros de
estudo ela refaz o preparo só para si (a amostra do laboratório, que as outras abas usam, continua
com os valores do sistema) e tudo o que sai disso é hipotético. A comparação com a galeria só roda
pelo botão, em imagem parada, e é recusada com o terminal bloqueado ou com quadro da câmera.
A assinatura de 128 barras só existe como imagem no provedor; nenhuma propriedade traz o vetor.
"""

from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QTimer, Signal, Slot

from .. import amostra_lab, config, fases_lab, leitura_ro, qualidade
from . import tema_v2, vm_privacidade
from .base import objeto, prop
from .base_v2 import ViewModelAba
from .formatos import num
from .imagens import bgr_para_qimage
from .trabalhos import Trabalho
from .video import FonteVideo

PREFIXO = "lab/fases/"
ESPERA_MS = 120
FAIXAS = {"largura": (320, 960), "kernel": (1, 15), "clip": (0.5, 8.0), "grade": (4, 16)}
GRADES = (4, 8, 16)
ROTULOS_QUALIDADE = {"nitidez": "Nitidez", "exposicao": "Exposição", "ruido": "Ruído", "simetria": "Simetria",
                     "pose": "Pose", "resolucao": "Resolução", "confianca": "Confiança do detector",
                     "norma": "Norma do vetor"}
ESTACOES = ((1, "Aquisição", "fase1_aquisicao.py"),
            (2, "Pré-processamento", "fase2_preprocessamento.py · equalizar_clahe()"),
            (3, "Segmentação", "fase3_segmentacao.py · DetectorFacial"),
            (4, "Representação", "fase4_representacao.py · ExtratorCaracteristicas"),
            (5, "Reconhecimento", "fase5_reconhecimento.py"))
MOTIVO_CAMERA = "Quadro da câmera: compare com uma referência. A galeria é consultada pelo Terminal."
MOTIVO_BLOQUEIO = "Comparação indisponível: o terminal está bloqueado."
MOTIVO_BANCO = "Análise disponível só com banco em arquivo."


def _padroes() -> dict:
    p = amostra_lab.ParametrosEstudo()
    return {"largura": p.largura, "kernel": p.kernel, "clip": float(p.clip), "grade": p.grade}


def _ajustar(chave: str, valor: float) -> float | int:
    menor, maior = FAIXAS[chave]
    v = min(maior, max(menor, float(valor)))
    if chave == "largura":
        return int(min(maior, max(menor, round(v / 40) * 40)))
    if chave == "kernel":
        k = int(round(v))
        return k if k % 2 else (k + 1 if k < maior else k - 1)
    if chave == "grade":
        return min(GRADES, key=lambda g: (abs(g - v), g))
    return round(v, 1)


def _bgr(hexa: str) -> tuple[int, int, int]:
    return int(hexa[5:7], 16), int(hexa[3:5], 16), int(hexa[1:3], 16)


def _montar(amostra, referencia) -> dict:
    """Tudo o que a aba mostra de uma amostra (roda no Trabalho)."""
    r: dict = {"imagens": {}}
    img = r["imagens"]
    img["original"] = bgr_para_qimage(amostra.frame)
    img["cinza"] = bgr_para_qimage(amostra.cinza)
    img["suavizada"] = bgr_para_qimage(amostra.suavizada)
    img["clahe"] = bgr_para_qimage(amostra.equalizada)
    img["global"] = bgr_para_qimage(fases_lab.f2.equalizar_cinza(amostra.cinza))
    h = fases_lab.histogramas(amostra)
    r["histograma"] = h
    r["matriz"] = fases_lab.matriz_alinhamento(amostra.rosto) if amostra.rosto is not None else None
    r["leituras"] = fases_lab.leituras(amostra, r["matriz"])
    r["comp"], r["brutos"], r["indice"] = {}, {}, None
    if amostra.alinhado is not None:
        img["recorte"] = bgr_para_qimage(amostra.recorte)
        img["alinhado"] = bgr_para_qimage(amostra.alinhado)
        img["lbp"] = bgr_para_qimage(fases_lab.mapa_lbp(amostra))
        assinatura = fases_lab.imagem_assinatura(amostra, cor_barra=_bgr(tema_v2.ACENTO), cor_fundo=_bgr(tema_v2.SUPERFICIE))
        if assinatura is not None:
            img["assinatura"] = bgr_para_qimage(assinatura)
        r["comp"] = qualidade.componentes(amostra.alinhado, amostra.rosto, amostra.norma_crua)
        r["brutos"] = qualidade.brutos(amostra.alinhado, amostra.rosto, amostra.norma_crua)
        r["indice"] = qualidade.indice(r["comp"])
    r["ref"] = -1.0
    if amostra.embedding is not None and referencia is not None and referencia.embedding is not None:
        r["ref"] = float(np.dot(amostra.embedding, referencia.embedding))
    r["equalizada"] = bgr_para_qimage(amostra.equalizada)
    return r


class LabFasesVM(ViewModelAba):
    VARIANTES_CAPTURA = ("estacao3",)

    estacaoMudou = Signal()
    temposMudou = Signal()
    orcamentoMudou = Signal()
    leiturasMudou = Signal()
    histogramaMudou = Signal()
    matrizMudou = Signal()
    matrizDetalheMudou = Signal()
    similaridadeReferenciaMudou = Signal()
    comparacaoPermitidaMudou = Signal()
    qualidadeMudou = Signal()
    indiceQualidadeMudou = Signal()
    parametrosMudou = Signal()
    padroesMudou = Signal()
    foraDoPadraoMudou = Signal()
    rankingMudou = Signal()
    rankingPadraoMudou = Signal()
    rankingEstadoMudou = Signal()
    rankingMotivoMudou = Signal()
    limiarMudou = Signal()
    revisaoMudou = Signal()
    temRostoMudou = Signal()
    nRostosMudou = Signal()

    estacao = prop(int, "estacao", estacaoMudou)
    tempos = prop("QVariantList", "tempos", temposMudou)
    orcamento = prop(float, "orcamento", orcamentoMudou)
    leituras = prop("QVariantMap", "leituras", leiturasMudou)
    histograma = prop("QVariantMap", "histograma", histogramaMudou)
    matriz = prop("QVariantList", "matriz", matrizMudou)
    matrizDetalhe = prop("QVariantMap", "matrizDetalhe", matrizDetalheMudou)
    similaridadeReferencia = prop(float, "similaridadeReferencia", similaridadeReferenciaMudou)
    comparacaoPermitida = prop(bool, "comparacaoPermitida", comparacaoPermitidaMudou)
    qualidade = prop("QVariantList", "qualidade", qualidadeMudou)
    indiceQualidade = prop(int, "indiceQualidade", indiceQualidadeMudou)
    parametros = prop("QVariantMap", "parametros", parametrosMudou)
    padroes = prop("QVariantMap", "padroes", padroesMudou)
    foraDoPadrao = prop(bool, "foraDoPadrao", foraDoPadraoMudou)
    ranking = prop("QVariantList", "ranking", rankingMudou)
    rankingPadrao = prop("QVariantList", "rankingPadrao", rankingPadraoMudou)
    rankingEstado = prop(str, "rankingEstado", rankingEstadoMudou)
    rankingMotivo = prop(str, "rankingMotivo", rankingMotivoMudou)
    limiar = prop(float, "limiar", limiarMudou)
    revisao = prop(int, "revisao", revisaoMudou)
    temRosto = prop(bool, "temRosto", temRostoMudou)
    nRostos = prop(int, "nRostos", nRostosMudou)
    fonteDeteccao = objeto("_fonte")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        padroes = _padroes()
        self._iniciar(estacao=2, tempos=[], orcamento=0.0, leituras={}, histograma={}, matriz=[], matrizDetalhe={},
                      similaridadeReferencia=-1.0, comparacaoPermitida=True, qualidade=[], indiceQualidade=-1,
                      parametros=dict(padroes), padroes=padroes, foraDoPadrao=False, ranking=[], rankingPadrao=[],
                      rankingEstado="nao_pedido", rankingMotivo="", limiar=float(config.LIMIAR_COSSENO), revisao=0,
                      temRosto=False, nRostos=0)
        self._fonte = FonteVideo("labFases", self)
        self._estudo = None                 # amostra examinada (a do laboratório ou a refeita com parâmetros de estudo)
        self._trab_ranking = Trabalho(aplicacao.extensoes.trabalhos, self)
        self._espera = QTimer(self)
        self._espera.setSingleShot(True)
        self._espera.setInterval(ESPERA_MS)
        self._espera.timeout.connect(self.recarregar)
        self.lab = aplicacao.extensoes.obter("laboratorio")
        self.lab.amostraMudou.connect(self.pedir_recarga)
        self.lab.referenciaMudou.connect(self.pedir_recarga)
        privacidade = aplicacao.extensoes.obter("privacidade")
        if hasattr(privacidade, "mostrarNomesMudou"):
            privacidade.mostrarNomesMudou.connect(self._ao_mudar_nomes)

    # ------------------------------------------------------------------ cálculo
    def _params(self) -> amostra_lab.ParametrosEstudo:
        p = self._v["parametros"]
        return amostra_lab.ParametrosEstudo(int(p["largura"]), int(p["kernel"]), float(p["clip"]), int(p["grade"]))

    @Slot()
    def recarregar(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        self._espera.stop()
        self._trab_ranking.cancelar()
        self._sem_ranking()
        self._definir("limiar", float(config.LIMIAR_COSSENO))
        self._definir("padroes", _padroes())
        self._definir("foraDoPadrao", self._v["parametros"] != self._v["padroes"])
        amostra = getattr(self.lab, "amostra", None)
        self._definir("comparacaoPermitida", getattr(self.lab, "amostraOrigem", "") != "camera")
        if not self._v["comparacaoPermitida"]:
            self._definir("rankingMotivo", MOTIVO_CAMERA)
        if amostra is None:
            self.trabalho.cancelar()
            self._limpar_dados()
            self._definir("erro", "")
            self._definir("estado", "vazio")
            return
        referencia = getattr(self.lab, "referencia", None)
        estudo = self._v["foraDoPadrao"]
        pipeline = self.app.pipeline
        if estudo and pipeline is None:
            self._indisponivel("Os modelos ainda estão carregando.")
            return
        params = self._params()

        def calcular(sinal):
            alvo = amostra
            if estudo:
                sinal.conferir()
                alvo = amostra_lab.preparar(amostra.frame, pipeline, params, origem=amostra.origem, rotulo=amostra.rotulo)
            sinal.conferir()
            return alvo, _montar(alvo, referencia)

        self._definir("erro", "")
        self._definir("estado", "carregando")
        self.trabalho.executar(calcular, self._ao_calcular)

    def _ao_calcular(self, resultado, erro: str) -> None:
        if erro:
            self._falhar(f"Não foi possível examinar a amostra: {erro}")
            return
        alvo, r = resultado
        self._estudo = alvo
        self.app.imagens.remover_prefixo(PREFIXO)
        for chave, imagem in r["imagens"].items():
            self.app.imagens.guardar(PREFIXO + chave, imagem)
        self._publicar_tempos(alvo, -1.0)
        self._definir("leituras", {str(k): [[a, b] for a, b in v] for k, v in r["leituras"].items()})
        self._definir("histograma", self._dados_histograma(r["histograma"], alvo))
        m = r["matriz"]
        if m is not None:
            self._definir("matriz", [[num(v, 4) for v in linha] for linha in m.m.tolist()])
            detalhe = {"escala": num(m.escala, 4), "rotacao": f"{num(m.rotacao_graus, 2)}°",
                       "tx": num(m.tx, 1), "ty": num(m.ty, 1), "residuo": f"{num(max(m.residuos_px), 1)} px"}
            detalhe["texto"] = (f"escala {detalhe['escala']} · rotação {detalhe['rotacao']} · translação "
                                f"({detalhe['tx']}; {detalhe['ty']}) · maior resíduo {detalhe['residuo']}")
            self._definir("matrizDetalhe", detalhe)
        else:
            self._definir("matriz", [])
            self._definir("matrizDetalhe", {})
        self._definir("qualidade", [{"chave": c, "rotulo": ROTULOS_QUALIDADE[c],
                                      "nota": -1.0 if r["comp"].get(c) is None else float(r["comp"][c]),
                                      "bruto": num(r["brutos"].get(c), 2)} for c in qualidade.COMPONENTES] if r["comp"] else [])
        self._definir("indiceQualidade", -1 if r["indice"] is None else int(r["indice"]))
        self._definir("similaridadeReferencia", r["ref"])
        self._definir("temRosto", alvo.tem_rosto)
        self._definir("nRostos", int(alvo.n_rostos))
        caixas = []
        if alvo.rosto_reduzido is not None:
            q = alvo.rosto_reduzido
            caixas.append({"x": q.x, "y": q.y, "w": q.w, "h": q.h, "cor": tema_v2.ACENTO, "rotulo": "",
                           "pontos": [q.olho_dir, q.olho_esq, q.nariz, q.boca_dir, q.boca_esq],
                           "principal": True, "malha": True})
        self._fonte.definir(r["equalizada"], caixas)
        self._definir("revisao", self._v["revisao"] + 1)
        self._definir("estado", "pronto")

    def _publicar_tempos(self, alvo, ms_fase5: float) -> None:
        t = alvo.tempos_ms if alvo is not None else {}
        valores = {1: -1.0, 2: t.get("fase2", -1.0), 3: t.get("fase3_deteccao", 0.0) + t.get("fase3_alinhamento", 0.0),
                   4: t.get("fase4", -1.0) if alvo is not None and alvo.tem_rosto else -1.0, 5: ms_fase5}
        maior = max([v for v in valores.values() if v > 0] or [1.0])
        self._definir("tempos", [{"fase": f, "nome": nome, "arquivo": arq, "ms": float(valores[f]),
                                  "texto": "–" if valores[f] < 0 else f"{num(valores[f], 1)} ms",
                                  "fracao": max(0.0, valores[f]) / maior} for f, nome, arq in ESTACOES])
        self._definir("orcamento", float(sum(v for v in valores.values() if v > 0)))

    def _dados_histograma(self, h: dict, alvo) -> dict:
        bordas = h["bordas"]

        def pontos(fracoes):
            return [[bordas[i], fracoes[i]] for i in range(len(fracoes))] + [[bordas[-1], fracoes[-1]]]

        maior = max(max(h["original"]), max(h["global"]), max(h["clahe"]), 0.01)
        selos = ["Parâmetros de estudo"] if self._v["foraDoPadrao"] else []
        alt, larg = alvo.cinza.shape[:2]
        return {"titulo": "Histograma de luminância", "n": f"N = {larg} × {alt} pixels", "selos": selos,
                "resumo": "Distribuição da luminância antes e depois da equalização global e do CLAHE.",
                "eixoX": {"rotulo": "luminância", "min": 0, "max": 256, "formato": "int"},
                "eixoY": {"rotulo": "fração de pixels", "min": 0, "max": float(maior) * 1.1, "formato": "%"},
                "series": [{"nome": "Original", "cor": "neutro", "estilo": "degrau", "pontos": pontos(h["original"])},
                           {"nome": "Equalização global", "cor": "serie1", "estilo": "degrau", "pontos": pontos(h["global"])},
                           {"nome": "CLAHE", "cor": "serie0", "estilo": "degrau", "pontos": pontos(h["clahe"])}]}

    def _limpar_dados(self) -> None:
        self._estudo = None
        self.app.imagens.remover_prefixo(PREFIXO)
        self._fonte.limpar()
        for nome, valor in (("tempos", []), ("orcamento", 0.0), ("leituras", {}), ("histograma", {}), ("matriz", []),
                            ("matrizDetalhe", {}), ("similaridadeReferencia", -1.0), ("qualidade", []),
                            ("indiceQualidade", -1), ("temRosto", False), ("nRostos", 0)):
            self._definir(nome, valor)
        self._sem_ranking()

    def _sem_ranking(self) -> None:
        self._definir("ranking", [])
        self._definir("rankingPadrao", [])
        self._definir("rankingMotivo", "")
        self._definir("rankingEstado", "nao_pedido")

    def ao_desativar(self) -> None:
        super().ao_desativar()
        self._espera.stop()
        self._trab_ranking.cancelar()
        if self._v["rankingEstado"] == "calculando":
            self._sem_ranking()
        self.app.imagens.remover_prefixo(PREFIXO)
        self._sujo = True                   # as imagens saíram do provedor: voltar recalcula

    def preparar_captura(self, variante: str = "") -> None:
        self.definirEstacao(3 if variante == "estacao3" else 2)
        self.recarregar()

    # ------------------------------------------------------------------ slots
    @Slot(int)
    def definirEstacao(self, estacao: int) -> None:
        if 1 <= int(estacao) <= 5:
            self._definir("estacao", int(estacao))

    @Slot(str, float)
    def definirParametro(self, chave: str, valor: float) -> None:
        if chave not in FAIXAS:
            return
        novos = dict(self._v["parametros"])
        novos[chave] = _ajustar(chave, valor)
        if novos == self._v["parametros"]:
            return
        self._definir("parametros", novos)
        self._definir("foraDoPadrao", novos != self._v["padroes"])
        if not self.ativa:
            self._sujo = True
            return
        self._espera.start()                # o último movimento vence

    @Slot()
    def restaurarPadroes(self) -> None:
        self._definir("parametros", _padroes())
        self._definir("foraDoPadrao", False)
        self._espera.stop()
        self.recarregar()

    def _ao_mudar_nomes(self) -> None:
        if self._v["rankingEstado"] in ("pronto", "calculando"):
            self._trab_ranking.cancelar()
            self._sem_ranking()

    @Slot()
    def compararComGaleria(self) -> None:
        if not self.ativa or self._estudo is None or self._v["estado"] != "pronto":
            return
        self._definir("ranking", [])
        self._definir("rankingPadrao", [])
        if getattr(self.lab, "amostraOrigem", "") == "camera" or self._estudo.origem == "camera":
            self._recusar(MOTIVO_CAMERA)
            return
        terminal = getattr(self.app.terminal_vm, "terminal", None)
        if terminal is not None and terminal.tentativas.bloqueado:
            self._recusar(MOTIVO_BLOQUEIO)
            return
        if self._estudo.embedding is None:
            self._recusar("Nenhum rosto detectado nesta imagem.")
            return
        caminho = self.caminho_db
        com_nomes = bool(getattr(self.app.extensoes.obter("privacidade"), "mostrarNomes", False))
        limiar = float(config.LIMIAR_COSSENO)
        q = np.array(self._estudo.embedding, copy=True)
        base = getattr(self.lab, "amostra", None)
        q_padrao = np.array(base.embedding, copy=True) if self._v["foraDoPadrao"] and base is not None \
            and base.embedding is not None else None

        def comparar(sinal):
            try:
                galeria = leitura_ro.galeria(caminho)
            except leitura_ro.BancoIndisponivel:
                return None
            sinal.conferir()
            t0 = time.perf_counter()
            r = fases_lab.ranking(q, galeria, limiar)
            ms = (time.perf_counter() - t0) * 1e3
            rp = fases_lab.ranking(q_padrao, galeria, limiar) if q_padrao is not None else []
            mapa = vm_privacidade.rotulos_para(caminho, com_nomes) if any(c["acima"] for c in r + rp) else {}
            return r, rp, mapa, ms, galeria.matriz.shape[0]

        self._definir("rankingMotivo", "")
        self._definir("rankingEstado", "calculando")
        self._trab_ranking.executar(comparar, self._ao_comparar)

    def _recusar(self, motivo: str) -> None:
        self._definir("rankingMotivo", motivo)
        self._definir("rankingEstado", "indisponivel")

    @staticmethod
    def _linhas(candidatos: list[dict], mapa: dict) -> list[dict]:
        linhas = []
        for i, c in enumerate(candidatos, start=1):
            rotulo = vm_privacidade.rotulo_de(mapa, c["usuario_id"]) if c["acima"] else f"Candidato {i}"
            linhas.append({"rotulo": rotulo, "similaridade": float(c["similaridade"]), "texto": num(c["similaridade"], 3),
                           "acima": bool(c["acima"]),
                           "leitura": "acima do limiar em vigor" if c["acima"] else "abaixo do limiar em vigor"})
        return linhas

    def _ao_comparar(self, resultado, erro: str) -> None:
        if erro:
            self._recusar(f"Não foi possível consultar a galeria: {erro}")
            return
        if resultado is None:
            self._recusar(MOTIVO_BANCO)
            return
        r, rp, mapa, ms, n_amostras = resultado
        if n_amostras == 0:
            self._definir("rankingEstado", "galeria_vazia")
            return
        linhas = self._linhas(r, mapa)
        self._definir("ranking", linhas)
        self._definir("rankingPadrao", self._linhas(rp, mapa))
        self._publicar_tempos(self._estudo, ms)
        leituras = dict(self._v["leituras"])
        leituras["5"] = [["Amostras na galeria", str(n_amostras)], ["Candidatos", str(len(linhas))],
                         ["Maior similaridade", linhas[0]["texto"] if linhas else "–"],
                         ["Limiar em vigor", num(self._v["limiar"], 3)], ["Tempo da comparação", f"{num(ms, 2)} ms"]]
        self._definir("leituras", leituras)
        self._definir("rankingEstado", "pronto")
