"""ViewModel da área liberada: a tela que abre DEPOIS de uma autenticação concedida no terminal.

Só abre a partir de uma `Decisao` do backend (`TerminalAutenticacao.decisao_atual`) com
`concedido=True`, e ainda reconfere no banco que a pessoa existe, está ativa e tem nível
suficiente para a área pedida. O QML não consegue abrir a sessão nem ler conteúdo de uma área
acima do nível: `conteudo(n)` devolve vazio para o que não foi liberado."""

from __future__ import annotations

import traceback
from datetime import datetime

from PySide6.QtCore import QTimer, Signal, Slot

from .. import areas, config
from .base import ViewModel, prop


class SessaoVM(ViewModel):
    ativaMudou = Signal()
    nomeMudou = Signal()
    cargoMudou = Signal()
    nivelUsuarioMudou = Signal()
    nivelDescricaoMudou = Signal()
    areaSolicitadaMudou = Signal()
    areasMudou = Signal()
    tempoRestanteMudou = Signal()
    tempoTotalMudou = Signal()
    abertaEmMudou = Signal()
    similaridadeMudou = Signal()
    aberta = Signal()
    encerrada = Signal(str)          # motivo: "usuario" | "tempo" | "sistema"

    ativa = prop(bool, "ativa", ativaMudou)
    nome = prop(str, "nome", nomeMudou)
    cargo = prop(str, "cargo", cargoMudou)
    nivelUsuario = prop(int, "nivelUsuario", nivelUsuarioMudou)
    nivelDescricao = prop(str, "nivelDescricao", nivelDescricaoMudou)
    areaSolicitada = prop(int, "areaSolicitada", areaSolicitadaMudou)
    areas = prop("QVariantList", "areas", areasMudou)
    tempoRestante = prop(int, "tempoRestante", tempoRestanteMudou)
    tempoTotal = prop(int, "tempoTotal", tempoTotalMudou)
    abertaEm = prop(str, "abertaEm", abertaEmMudou)
    similaridade = prop(float, "similaridade", similaridadeMudou)

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(ativa=False, nome="", cargo="", nivelUsuario=0, nivelDescricao="", areaSolicitada=0,
                      areas=[], tempoRestante=0, tempoTotal=int(config.SESSAO_LIBERADA_SEG), abertaEm="",
                      similaridade=-1.0)
        self._liberadas: list[int] = []
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tique)

    # ------------------------------------------------------------------ abertura (só pelo backend)
    def abrir(self, decisao, nivel_exigido: int) -> bool:
        """Chamado pelo TerminalVM quando o terminal entra em RESULTADO. Negação por padrão:
        qualquer dado faltando ou inconsistente mantém a sessão fechada."""
        if self._v["ativa"] or decisao is None or not getattr(decisao, "concedido", False):
            return False
        ident = decisao.identificacao
        if ident is None or not ident.reconhecido or ident.usuario is None:
            return False
        try:
            u = self.app.banco.obter_usuario(ident.usuario.id)     # relê: nível e situação atuais
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return False
        nivel_exigido = int(nivel_exigido)
        if u is None or not u.ativo or nivel_exigido not in config.NIVEIS or u.nivel < nivel_exigido:
            return False
        self._liberadas = areas.areas_liberadas(u.nivel)
        if nivel_exigido not in self._liberadas:
            return False
        self._definir("nome", u.nome)
        self._definir("cargo", u.cargo or "")
        self._definir("nivelUsuario", int(u.nivel))
        self._definir("nivelDescricao", config.NIVEIS.get(u.nivel, ""))
        self._definir("areaSolicitada", nivel_exigido)
        self._definir("areas", areas.resumo_areas(u.nivel))
        self._definir("similaridade", round(float(ident.similaridade), 3))
        self._definir("abertaEm", datetime.now().strftime("%H:%M:%S"))
        self._definir("tempoTotal", int(config.SESSAO_LIBERADA_SEG))
        self._definir("tempoRestante", int(config.SESSAO_LIBERADA_SEG))
        self._definir("ativa", True)
        self._timer.start()
        self.aberta.emit()
        return True

    # ------------------------------------------------------------------ uso pelo QML
    @Slot(int, result="QVariantMap")
    def conteudo(self, nivel: int) -> dict:
        """Conteúdo da área, só se a sessão estiver ativa e a área liberada para este usuário."""
        if not self._v["ativa"] or int(nivel) not in self._liberadas:
            return {}
        try:
            return areas.conteudo(int(nivel))
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return {}

    @Slot(int, result=bool)
    def liberada(self, nivel: int) -> bool:
        return self._v["ativa"] and int(nivel) in self._liberadas

    @Slot()
    def renovar(self) -> None:
        """Qualquer interação na área renova o tempo de inatividade."""
        if self._v["ativa"]:
            self._definir("tempoRestante", int(config.SESSAO_LIBERADA_SEG))

    @Slot()
    def encerrar(self) -> None:
        self._fechar("usuario")

    def _tique(self) -> None:
        restante = self._v["tempoRestante"] - 1
        if restante <= 0:
            self._fechar("tempo")
            return
        self._definir("tempoRestante", restante)

    def _fechar(self, motivo: str) -> None:
        if not self._v["ativa"]:
            return
        self._timer.stop()
        self._liberadas = []
        self._definir("ativa", False)
        self._definir("tempoRestante", 0)
        if motivo == "tempo":
            self.app.notificar("info", f"Sessão de {self._v['nome']} encerrada por inatividade.")
        self.encerrada.emit(motivo)
