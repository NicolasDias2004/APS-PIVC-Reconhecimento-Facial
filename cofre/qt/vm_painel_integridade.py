"""Aba Integridade do Painel de segurança (v2): as 13 regras do registro, contadas, e o selo encadeado
que detecta alteração e remoção de registros antigos. Só lê o banco; "Selar agora" grava um JSON novo
em `config.RELATORIOS_DIR` e nada mais.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal, Slot

from .. import config, integridade
from ..liveness import ControleTentativas
from . import vm_figuras
from .base import prop
from .base_v2 import ViewModelAba
from .formatos import inteiro
from .trabalhos import Trabalho


def _plural(n: int, um: str, varios: str) -> str:
    return f"{inteiro(n)} {um if n == 1 else varios}"


def _pasta_selos() -> Path:
    return Path(config.RELATORIOS_DIR)


class PainelIntegridadeVM(ViewModelAba):
    SEMPRE_RECALCULA = True         # o terminal não avisa quando grava: recalcula em toda ativação

    regrasMudou = Signal()
    resumoMudou = Signal()
    seloMudou = Signal()
    selosMudou = Signal()
    estruturaMudou = Signal()
    selandoMudou = Signal()
    demonstracaoMudou = Signal()

    regras = prop("QVariantList", "regras", regrasMudou)
    resumo = prop(str, "resumo", resumoMudou)
    selo = prop("QVariantMap", "selo", seloMudou)
    selos = prop("QVariantMap", "selos", selosMudou)
    estrutura = prop("QVariantMap", "estrutura", estruturaMudou)
    selando = prop(bool, "selando", selandoMudou)
    demonstracao = prop(bool, "demonstracao", demonstracaoMudou)

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(regras=[], resumo="", selo={}, selos={}, estrutura={}, selando=False,
                      demonstracao=bool(aplicacao.extensoes.baseDemonstracao))
        self._trab_selo = Trabalho(aplicacao.extensoes.trabalhos, self)
        self.app.extensoes.obter("painel").atualizarPedido.connect(self.pedir_recarga)

    def _tentativas(self):
        term = getattr(self.app.terminal_vm, "terminal", None)
        return term.tentativas if term is not None else ControleTentativas()

    def _limpar_dados(self) -> None:
        self._definir("regras", [])
        self._definir("resumo", "")
        self._definir("selo", {})
        self._definir("selos", {})
        self._definir("estrutura", {})

    @Slot()
    def recarregar(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        caminho = self.caminho_db
        if str(caminho) == ":memory:":
            self._indisponivel("Análise disponível só com banco em arquivo")
            return
        tentativas = self._tentativas()
        janela, max_falhas = float(tentativas.janela), int(tentativas.max_falhas)
        limiar = float(config.LIMIAR_COSSENO)
        demo = self._v["demonstracao"]
        pasta = _pasta_selos()
        self._definir("erro", "")
        self._definir("estado", "carregando")

        def fn(sinal):
            regras = integridade.conferir(caminho, limiar=limiar, janela_seg=janela, max_falhas=max_falhas,
                                          demonstracao=demo, sinal=sinal)
            selo = integridade.selar(caminho, sinal=sinal)
            selos = integridade.conferir_selos(caminho, pasta, sinal=sinal)
            return regras, selo, selos, integridade.estrutura(caminho)

        self.trabalho.executar(fn, self._ao_terminar)

    def _ao_terminar(self, r, erro: str) -> None:
        if erro or r is None:
            self._falhar(f"Não foi possível conferir o registro: {erro or 'sem resultado'}")
            return
        regras, selo, selos, estrutura = r
        itens, violam, observar = [], 0, 0
        for res in regras:
            if res.violacoes == 0:
                situacao, marca = "confere", "confere"
            elif res.regra.consultiva:
                situacao, marca = "observar", f"{inteiro(res.violacoes)} a observar"
                observar += 1
            else:
                situacao = "viola"
                marca = _plural(res.violacoes, "violação", "violações")
                violam += 1
            exemplos = ", ".join(f"nº {i}" for i in res.ids[:5])
            itens.append({"id": res.regra.id, "titulo": res.regra.titulo, "consultiva": res.regra.consultiva,
                          "violacoes": int(res.violacoes), "situacao": situacao, "marca": marca,
                          "garantia": res.regra.garantia, "observacao": res.observacao,
                          "exemplos": exemplos})
        self._definir("regras", itens)
        registros = _plural(selo.registros, "registro", "registros")
        if violam == 0 and observar == 0:
            fecho = "nenhuma violação"
        else:
            partes = []
            if violam:
                partes.append(_plural(violam, "regra violada", "regras violadas"))
            if observar:
                partes.append(f"{inteiro(observar)} a observar")
            fecho = " e ".join(partes)
        self._definir("resumo", f"{len(itens)} regras conferidas em {registros}: {fecho}")
        grupos = [selo.sha256[i:i + 4] for i in range(0, len(selo.sha256), 4)]
        self._definir("selo", {"sha256": selo.sha256, "grupos": grupos, "registros": int(selo.registros),
                               "ultimoId": int(selo.ultimo_id),
                               "texto": f"{registros}, até o nº {inteiro(selo.ultimo_id)}"})
        self._definir("selos", {"total": int(selos["total"]), "conferem": int(selos["conferem"]),
                                "divergentes": len(selos["divergentes"]), "ultimoTexto": self._texto_ultimo(selos),
                                "ultimoConfere": bool(selos["ultimo"] and selos["ultimo"]["confere"])})
        self._definir("estrutura", {
            "lacunas": int(estrutura["lacunas_id"]), "seqMenosMax": int(estrutura["seq_menos_max"]),
            "modo": str(estrutura["modo_diario"]),
            "linhas": [{"rotulo": "Números faltando na sequência", "valor": inteiro(estrutura["lacunas_id"]),
                        "ok": estrutura["lacunas_id"] == 0},
                       {"rotulo": "Contador do banco menos o maior número", "valor": inteiro(estrutura["seq_menos_max"]),
                        "ok": estrutura["seq_menos_max"] == 0},
                       {"rotulo": "Modo do diário do SQLite", "valor": str(estrutura["modo_diario"]), "ok": True}]})
        self._definir("estado", "vazio" if selo.registros == 0 else "pronto")

    @staticmethod
    def _texto_ultimo(selos: dict) -> str:
        ultimo = selos.get("ultimo")
        if not ultimo:
            return "Nenhum selo gravado ainda"
        if ultimo["confere"]:
            return "Último selo gravado: confere"
        try:
            quando = datetime.fromisoformat(ultimo["gerado_em"]).strftime("%d/%m")
        except (TypeError, ValueError):
            quando = "–"
        return (f"Último selo gravado: diverge: registros até o nº {inteiro(ultimo['ultimo_id'])} "
                f"foram alterados depois de {quando}")

    # ------------------------------------------------------------------ selo
    @Slot()
    def selarAgora(self) -> None:
        if not self.ativa:
            self._sujo = True
            return
        caminho = self.caminho_db
        if str(caminho) == ":memory:":
            self.app.notificar("erro", "O selo precisa de um banco em arquivo.")
            return
        pasta = _pasta_selos()
        base = Path(str(caminho)).name
        demo = self._v["demonstracao"]
        self._definir("selando", True)

        def fn(sinal):
            selo = integridade.selar(caminho, sinal=sinal)
            return integridade.gravar_selo(selo, pasta, base=base, demonstracao=demo)

        self._trab_selo.executar(fn, self._ao_selar)

    def _ao_selar(self, destino, erro: str) -> None:
        self._definir("selando", False)
        if erro or destino is None:
            self.app.notificar("erro", f"Não foi possível gravar o selo: {erro or 'sem resultado'}")
            return
        self.app.notificar("info", f"Selo salvo em {Path(destino).name}")
        self.pedir_recarga()

    @Slot()
    def abrirPastaSelos(self) -> None:
        pasta = _pasta_selos()
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        vm_figuras.abrir_no_sistema(pasta)

    def ao_desativar(self) -> None:
        super().ao_desativar()
        self._trab_selo.cancelar()
        self._definir("selando", False)
