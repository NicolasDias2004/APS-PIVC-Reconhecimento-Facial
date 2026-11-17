"""Aba Visão geral do Painel de segurança (v2): o que o terminal decidiu, com que folga em relação ao
limiar e em que estado estão os controles. Só lê o registro (por `leitura_ro`) e os atributos vivos do
backend; nada aqui participa da decisão de acesso.
"""

from __future__ import annotations

import traceback
from datetime import datetime

import cv2
from PySide6.QtCore import Signal, Slot

from .. import amostra_lab, analitica, config, diagnostico, leitura_ro
from ..autenticacao import Confirmador
from ..liveness import ControleTentativas, DesafioMovimento
from . import tema
from .base import prop
from .base_v2 import ViewModelAba
from .formatos import SEM_VALOR, hora, inteiro, num
from .trabalhos import Trabalho

POUCOS = 30
REPETICOES_DIAGNOSTICO = 10
NOMES_FASES = (("fase2", "Fase 2 · pré-processamento"), ("fase3_deteccao", "Fase 3 · detecção"),
               ("fase3_alinhamento", "Fase 3 · alinhamento"), ("fase4", "Fase 4 · descritor"),
               ("total", "Tempo total"))


def _seg(v: float) -> str:
    return f"{num(v, 0 if float(v).is_integer() else 1)} s"


class PainelGeralVM(ViewModelAba):
    SEMPRE_RECALCULA = True         # o terminal não avisa quando grava: recalcula em toda ativação

    totalMudou = Signal()
    mancheteMudou = Signal()
    leiturasMudou = Signal()
    composicaoMudou = Signal()
    fitaMudou = Signal()
    espectroMudou = Signal()
    agoraMudou = Signal()
    posturaMudou = Signal()
    diagnosticoMudou = Signal()
    diagnosticandoMudou = Signal()
    limiarMudou = Signal()

    total = prop(int, "total", totalMudou)
    manchete = prop(str, "manchete", mancheteMudou)
    leituras = prop("QVariantList", "leituras", leiturasMudou)
    composicao = prop("QVariantMap", "composicao", composicaoMudou)
    fita = prop("QVariantMap", "fita", fitaMudou)
    espectro = prop("QVariantMap", "espectro", espectroMudou)
    agora = prop("QVariantList", "agora", agoraMudou)
    postura = prop("QVariantList", "postura", posturaMudou)
    diagnostico = prop("QVariantList", "diagnostico", diagnosticoMudou)
    diagnosticando = prop(bool, "diagnosticando", diagnosticandoMudou)
    limiar = prop(float, "limiar", limiarMudou)

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(total=0, manchete="", leituras=[], composicao={}, fita={}, espectro={}, agora=[],
                      postura=[], diagnostico=[], diagnosticando=False, limiar=float(config.LIMIAR_COSSENO))
        self._trab_diag = Trabalho(aplicacao.extensoes.trabalhos, self)
        self.app.extensoes.obter("painel").atualizarPedido.connect(self.pedir_recarga)

    # ------------------------------------------------------------------ objetos vivos do backend
    def _objetos(self):
        term = getattr(self.app.terminal_vm, "terminal", None)
        if term is not None:
            return term.confirmador, term.tentativas, term.desafio
        return Confirmador(), ControleTentativas(), DesafioMovimento()

    def _ler_postura(self) -> list[dict]:
        confirmador, tentativas, desafio = self._objetos()
        padroes = getattr(self.app.config_vm, "padroes", {}) or {}
        linhas = []
        liveness = bool(self.app.terminal_vm.liveness)
        linhas.append({"chave": "liveness", "rotulo": "Prova de vida no terminal",
                       "valor": "ligada" if liveness else "desligada", "fabrica": "",
                       "situacao": "ok" if liveness else "aviso",
                       "texto": "" if liveness else "Desligada pelo operador: o terminal decide sem o desafio de movimento"})
        limiar = float(config.LIMIAR_COSSENO)
        padrao = padroes.get("LIMIAR_COSSENO")
        if padrao is None or abs(limiar - float(padrao)) < 1e-9:
            sit, texto = "ok", ""
        elif limiar < float(padrao):
            sit, texto = "aviso", "Mais baixo que o padrão: aceita rostos menos parecidos"
        else:
            sit, texto = "info", "Mais alto que o padrão: mais exigente"
        linhas.append({"chave": "limiar", "rotulo": "Limiar de similaridade", "valor": num(limiar),
                       "fabrica": "" if sit == "ok" or padrao is None else num(float(padrao)),
                       "situacao": sit, "texto": texto})
        multiplos = bool(config.BLOQUEAR_MULTIPLOS_ROSTOS)
        linhas.append({"chave": "multiplos", "rotulo": "Bloqueio de mais de um rosto",
                       "valor": "ligado" if multiplos else "desligado", "fabrica": "",
                       "situacao": "ok" if multiplos else "aviso",
                       "texto": "" if multiplos else "Desligado: duas pessoas diante do terminal não impedem a decisão"})

        def info(chave, rotulo, valor, texto, padrao_chave, formatar):
            fab = padroes.get(padrao_chave)
            difere = fab is not None and abs(float(fab) - float(valor)) > 1e-9
            linhas.append({"chave": chave, "rotulo": rotulo, "valor": texto,
                           "fabrica": formatar(fab) if difere else "", "situacao": "info", "texto": ""})

        info("confirmacao", "Quadros de confirmação", confirmador.n, inteiro(confirmador.n), "FRAMES_CONFIRMACAO", inteiro)
        info("falhas", "Negações até o bloqueio", tentativas.max_falhas, inteiro(tentativas.max_falhas),
             "MAX_TENTATIVAS_FALHAS", inteiro)
        info("janela", "Janela das negações", tentativas.janela, _seg(tentativas.janela), "", _seg)
        info("bloqueio", "Duração do bloqueio", tentativas.bloqueio, _seg(tentativas.bloqueio), "BLOQUEIO_SEG", _seg)
        info("giro", "Giro da prova de vida", desafio.limiar, num(desafio.limiar, 2), "LIVENESS_LIMIAR_YAW",
             lambda v: num(v, 2))
        info("tempo", "Tempo da prova de vida", desafio.timeout, _seg(desafio.timeout), "LIVENESS_TIMEOUT_SEG", _seg)
        demo = bool(self.app.extensoes.baseDemonstracao)
        try:
            nome = self.app.nomeBanco()
        except Exception:  # noqa: BLE001
            nome = SEM_VALOR
        linhas.append({"chave": "base", "rotulo": "Base aberta", "valor": nome + (" · demonstração" if demo else ""),
                       "fabrica": "", "situacao": "aviso" if demo else "info",
                       "texto": "Base de demonstração" if demo else ""})
        return linhas

    # ------------------------------------------------------------------ cálculo do registro
    def _limpar_dados(self) -> None:
        self._definir("total", 0)
        self._definir("manchete", "")
        self._definir("leituras", [])
        self._definir("composicao", {})
        self._definir("fita", {})
        self._definir("espectro", {})
        self._definir("agora", [])

    @Slot()
    def recarregar(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        limiar = float(config.LIMIAR_COSSENO)
        self._definir("limiar", limiar)
        self._definir("postura", self._ler_postura())
        caminho = self.caminho_db
        if str(caminho) == ":memory:":
            self._indisponivel("Análise disponível só com banco em arquivo")
            return
        _, tentativas, _ = self._objetos()
        bloqueio = float(tentativas.bloqueio)
        forte = float(config.LIMIAR_COSSENO_FORTE)
        desde = self.app.extensoes.obter("painel").desde_iso()
        self._definir("erro", "")
        self._definir("estado", "carregando")

        def fn(sinal):
            eventos = analitica.ler_eventos(caminho, desde)
            sinal.conferir()
            res = analitica.resumo(eventos)
            fol = analitica.folga(eventos, limiar)
            frase, leituras = analitica.manchete(res, fol, limiar)
            return {"total": res["total"], "manchete": frase, "leituras": leituras,
                    "composicao": analitica.dados_composicao(res),
                    "fita": analitica.dados_fita(eventos, bloqueio),
                    "espectro": analitica.dados_espectro(eventos, limiar, forte),
                    "agora": [self._linha_agora(e) for e in analitica.ultimos(eventos, datetime.now())][::-1]}

        self.trabalho.executar(fn, self._ao_terminar)

    @staticmethod
    def _linha_agora(e: analitica.Evento) -> dict:
        return {"id": e.id, "hora": hora(e.data_hora), "resultado": e.resultado,
                "titulo": tema.ROTULO_CURTO_RESULTADO.get(e.resultado, e.resultado),
                "concedido": e.resultado == "CONCEDIDO", "nivelExigido": e.nivel_exigido,
                "similaridade": num(e.similaridade)}

    def _ao_terminar(self, r, erro: str) -> None:
        if erro or r is None:
            self._falhar(f"Não foi possível ler o registro: {erro or 'sem resultado'}")
            return
        for chave in ("composicao", "fita", "espectro", "leituras", "agora", "manchete"):
            self._definir(chave, r[chave])
        self._definir("total", int(r["total"]))
        total = int(r["total"])
        self._definir("estado", "vazio" if total == 0 else ("poucos" if total < POUCOS else "pronto"))

    # ------------------------------------------------------------------ diagnóstico
    @Slot()
    def executarDiagnostico(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        pipeline = self.app.pipeline
        caminho = self.caminho_db
        camera = str(getattr(self.app.camera, "estado", "") or "")
        self._definir("diagnosticando", True)

        def fn(sinal):
            return _diagnosticar(pipeline, caminho, camera, sinal)

        self._trab_diag.executar(fn, self._ao_diagnosticar)

    def _ao_diagnosticar(self, linhas, erro: str) -> None:
        self._definir("diagnosticando", False)
        if erro or linhas is None:
            self._definir("diagnostico", [{"item": "Diagnóstico", "valor": erro or "sem resultado", "situacao": "falha"}])
            return
        self._definir("diagnostico", linhas)

    def ao_desativar(self) -> None:
        super().ao_desativar()
        self._trab_diag.cancelar()
        self._definir("diagnosticando", False)

    # ------------------------------------------------------------------ navegação
    @Slot()
    def abrirAuditoria(self) -> None:
        self.app.navegar("acessos")

    @Slot()
    def abrirConfiguracoes(self) -> None:
        self.app.navegar("config")


def _diagnosticar(pipeline, caminho, camera: str, sinal) -> list[dict]:
    """Roda no `Trabalho`: só lê arquivos e o banco (somente leitura)."""
    linhas: list[dict] = []
    linhas.append({"item": "Modelos carregados", "valor": "sim" if pipeline is not None else "ainda não",
                   "situacao": "ok" if pipeline is not None else "atencao"})
    for rotulo, arquivo in (("Modelo de detecção", config.MODELO_DETECCAO),
                            ("Modelo de reconhecimento", config.MODELO_RECONHECIMENTO)):
        try:
            linhas.append({"item": rotulo + " · SHA-256", "valor": diagnostico.sha256_arquivo(arquivo)[:8],
                           "situacao": "ok"})
        except OSError:
            linhas.append({"item": rotulo + " · SHA-256", "valor": "arquivo ausente", "situacao": "falha"})
        sinal.conferir()
    fotos = amostra_lab.fotos_de_teste()
    primeira = next((lista[0] for lista in fotos.values() if lista), None)
    if pipeline is None:
        linhas.append({"item": "Tempo por fase", "valor": "modelos não carregados", "situacao": "atencao"})
    elif primeira is None:
        linhas.append({"item": "Tempo por fase", "valor": "sem fotos de teste", "situacao": "atencao"})
    else:
        frame = cv2.imread(str(primeira))
        if frame is None:
            linhas.append({"item": "Tempo por fase", "valor": "foto de teste ilegível", "situacao": "atencao"})
        else:
            tempos = diagnostico.tempos_por_fase(pipeline, frame, REPETICOES_DIAGNOSTICO, sinal)
            for chave, rotulo in NOMES_FASES:
                t = tempos[chave]
                linhas.append({"item": rotulo, "valor": f"{num(t['mediana'], 1)} ms · p95 {num(t['p95'], 1)} ms",
                               "situacao": "ok"})
    try:
        n = int(leitura_ro.consultar(caminho, "SELECT COUNT(*) FROM acessos")[0][0])
        linhas.append({"item": "Banco em somente leitura", "valor": f"abre · {inteiro(n)} registros", "situacao": "ok"})
        referenciadas, ausentes = diagnostico.evidencias_ausentes(caminho)
        linhas.append({"item": "Evidências ausentes", "valor": f"{inteiro(ausentes)} de {inteiro(referenciadas)}",
                       "situacao": "ok" if ausentes == 0 else "atencao"})
        pessoas = int(leitura_ro.consultar(caminho, "SELECT COUNT(*) FROM usuarios WHERE ativo = 1")[0][0])
        amostras = int(leitura_ro.consultar(
            caminho, "SELECT COUNT(*) FROM amostras a JOIN usuarios u ON u.id = a.usuario_id WHERE u.ativo = 1")[0][0])
        linhas.append({"item": "Galeria", "valor": f"{inteiro(pessoas)} pessoas ativas · {inteiro(amostras)} amostras",
                       "situacao": "ok" if pessoas > 0 else "atencao"})
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        linhas.append({"item": "Banco em somente leitura", "valor": f"não abre: {e}", "situacao": "falha"})
    linhas.append({"item": "Câmera", "valor": camera or SEM_VALOR,
                   "situacao": "atencao" if camera == "erro" else "ok"})
    return linhas
