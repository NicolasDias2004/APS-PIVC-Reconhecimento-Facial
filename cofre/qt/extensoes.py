"""Registro defensivo dos ViewModels da v2: é o objeto que o QML enxerga como `app.v2`.

Cada ViewModel novo é importado e construído dentro de `try/except`. Um módulo quebrado (o de um
lote pela metade, por exemplo) vira um `VMIndisponivel` com o erro em texto, e o aplicativo, o
terminal e os outros ViewModels seguem normais. Os ViewModels alcançam os vizinhos por
`self.app.extensoes.obter(chave)`, que sempre devolve um objeto.
"""

from __future__ import annotations

import importlib
import traceback

from PySide6.QtCore import Property, QCoreApplication, QEvent, QObject, Signal, Slot

from .. import leitura_ro
from .base_v2 import VMIndisponivel
from .trabalhos import Trabalhos

PAGINAS_V2: tuple[str, ...] = ("painel", "laboratorio", "resultados")

REGISTRO: tuple[tuple[str, str, str], ...] = (          # (chave, módulo, classe), na ordem de criação
    ("privacidade", "cofre.qt.vm_privacidade", "PrivacidadeVM"),
    ("figuras", "cofre.qt.vm_figuras", "FigurasVM"),
    ("painel", "cofre.qt.vm_painel", "PainelVM"),
    ("laboratorio", "cofre.qt.vm_laboratorio", "LaboratorioVM"),
    ("resultados", "cofre.qt.vm_resultados", "ResultadosVM"),
    ("painelGeral", "cofre.qt.vm_painel_geral", "PainelGeralVM"),
    ("painelIncidentes", "cofre.qt.vm_painel_incidentes", "PainelIncidentesVM"),
    ("painelIntegridade", "cofre.qt.vm_painel_integridade", "PainelIntegridadeVM"),
    ("labFases", "cofre.qt.vm_lab_fases", "LabFasesVM"),
    ("labRobustez", "cofre.qt.vm_lab_robustez", "LabRobustezVM"),
    ("labExplicabilidade", "cofre.qt.vm_lab_explicabilidade", "LabExplicabilidadeVM"),
    ("resSeparacao", "cofre.qt.vm_res_separacao", "ResSeparacaoVM"),
    ("resQualidade", "cofre.qt.vm_res_qualidade", "ResQualidadeVM"),
    ("resGaleria", "cofre.qt.vm_res_galeria", "ResGaleriaVM"),
    ("quiosque", "cofre.qt.vm_quiosque", "QuiosqueVM"),
)

ABAS: dict[str, tuple[tuple[str, str, str, str], ...]] = {       # página -> (valor, texto, chave do VM, arquivo QML)
    "painel": (("geral", "Visão geral", "painelGeral", "PainelGeral.qml"),
               ("incidentes", "Incidentes", "painelIncidentes", "PainelIncidentes.qml"),
               ("integridade", "Integridade", "painelIntegridade", "PainelIntegridade.qml")),
    "laboratorio": (("fases", "Fases", "labFases", "LabFases.qml"),
                    ("robustez", "Robustez", "labRobustez", "LabRobustez.qml"),
                    ("explicabilidade", "Explicabilidade", "labExplicabilidade", "LabExplicabilidade.qml")),
    "resultados": (("separacao", "Separação", "resSeparacao", "ResSeparacao.qml"),
                   ("qualidade", "Qualidade", "resQualidade", "ResQualidade.qml"),
                   ("galeria", "Galeria", "resGaleria", "ResGaleria.qml")),
}

ESPERA_ENCERRAMENTO_MS = 3000


class Extensoes(QObject):
    quiosqueUsadoMudou = Signal()
    quiosqueTelaCheiaMudou = Signal()
    sobreposicaoAbertaMudou = Signal()

    def __init__(self, aplicacao, parent=None):
        super().__init__(parent)
        aplicacao.extensoes = self              # os ViewModels alcançam os vizinhos já durante a construção
        self.app = aplicacao
        self.trabalhos = Trabalhos(self)
        self._demo = self._ler_marcador_demo()
        self._vms: dict[str, QObject] = {}
        self._erros: dict[str, str] = {}
        for chave, modulo, classe in REGISTRO:
            self._erros.pop(chave, None)        # um vizinho pode ter pedido esta chave antes da vez dela
            self._vms[chave] = self._carregar(chave, modulo, classe)
        self._ligar_quiosque()
        aplicacao.encerrando.connect(self._ao_encerrar)

    # ------------------------------------------------------------------ carga defensiva
    def _ler_marcador_demo(self) -> bool:
        """Única leitura de banco na thread da interface em toda a v2 (conexão com espera de 0,2 s)."""
        try:
            return bool(leitura_ro.eh_base_demonstracao(self.app.banco.caminho))
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return False

    def _carregar(self, chave: str, modulo: str, classe: str) -> QObject:
        filhos = len(self.children())
        try:
            return getattr(importlib.import_module(modulo), classe)(self.app, self)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._descartar_orfaos(filhos)
            return self._indisponivel(chave, f"{type(e).__name__}: {e}" if str(e) else type(e).__name__)

    def _indisponivel(self, chave: str, erro: str) -> VMIndisponivel:
        self._erros[chave] = erro
        self._vms[chave] = VMIndisponivel(self.app, self, erro)
        return self._vms[chave]

    def _descartar_orfaos(self, a_partir_de: int) -> None:
        """Um construtor que falha no meio deixa o objeto pendurado aqui, com os sinais já ligados:
        ele é destruído na hora, para não reagir a mais nada."""
        registrados = list(self._vms.values())
        for filho in self.children()[a_partir_de:]:
            if not any(filho is vm for vm in registrados):
                filho.deleteLater()
                QCoreApplication.sendPostedEvents(filho, QEvent.Type.DeferredDelete)

    def _quiosque(self):
        """O QuiosqueVM real; `None` se ele não carregou."""
        return None if "quiosque" in self._erros else self._vms.get("quiosque")

    def _ligar_quiosque(self) -> None:
        quiosque = self._quiosque()
        if quiosque is None:
            return
        try:
            quiosque.usadoMudou.connect(self.quiosqueUsadoMudou)
            quiosque.telaCheiaAtivaMudou.connect(self.quiosqueTelaCheiaMudou)
            quiosque.ativoMudou.connect(self.sobreposicaoAbertaMudou)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            filhos = self.children().index(quiosque)
            self._indisponivel("quiosque", f"{type(e).__name__}: {e}")
            self._descartar_orfaos(filhos)

    # ------------------------------------------------------------------ uso pelo Python
    def obter(self, chave: str) -> QObject:
        """ViewModel da chave. Sempre devolve um objeto: o real ou um `VMIndisponivel`."""
        vm = self._vms.get(chave)
        return vm if vm is not None else self._indisponivel(chave, f"ViewModel não carregado: {chave}")

    def paginas(self) -> dict[str, QObject]:
        return {pagina: self.obter(pagina) for pagina in PAGINAS_V2}

    @Slot()
    def _ao_encerrar(self) -> None:
        self.trabalhos.cancelar_tudo()
        self.trabalhos.esperar(ESPERA_ENCERRAMENTO_MS)

    # ------------------------------------------------------------------ uso pelo QML
    @Slot(str, result=str)
    def erroDe(self, chave: str) -> str:
        """Texto do erro de carga do ViewModel da chave; "" se ele carregou."""
        self.obter(chave)
        return self._erros.get(chave, "")

    @Slot(str, result="QVariantList")
    def abasDe(self, pagina: str) -> list[dict]:
        return [{"valor": valor, "texto": texto, "chaveVm": chave, "fonte": fonte, "erro": self._erros.get(chave, "")}
                for valor, texto, chave, fonte in ABAS.get(pagina, ())]

    @Slot(str, str)
    def irPara(self, pagina: str, aba: str) -> None:
        """Ligação entre telas: escolhe a aba da página e navega até ela. Com a sessão aberta o backend
        recusa a navegação (`Aplicacao.navegar`), e a aba escolhida só vale quando a página abrir."""
        if pagina not in PAGINAS_V2:
            return
        try:
            self.obter(pagina).definirAba(aba)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        self.app.navegar(pagina)

    @Slot()
    def entrarQuiosque(self) -> None:
        quiosque = self._quiosque()
        if quiosque is not None:
            quiosque.entrar()

    @Slot()
    def sairQuiosque(self) -> None:
        quiosque = self._quiosque()
        if quiosque is not None:
            quiosque.sair()

    def _get_base_demonstracao(self) -> bool:
        return self._demo

    def _get_quiosque_usado(self) -> bool:
        return bool(getattr(self._quiosque(), "usado", False))

    def _get_quiosque_tela_cheia(self) -> bool:
        return bool(getattr(self._quiosque(), "telaCheiaAtiva", False))

    def _get_sobreposicao_aberta(self) -> bool:
        return bool(getattr(self._quiosque(), "ativo", False))

    baseDemonstracao = Property(bool, _get_base_demonstracao, constant=True)
    quiosqueUsado = Property(bool, _get_quiosque_usado, notify=quiosqueUsadoMudou)
    quiosqueTelaCheia = Property(bool, _get_quiosque_tela_cheia, notify=quiosqueTelaCheiaMudou)
    sobreposicaoAberta = Property(bool, _get_sobreposicao_aberta, notify=sobreposicaoAbertaMudou)

    def _vm(chave):  # noqa: N805 (fábrica de propriedades)
        return Property(QObject, lambda self: self.obter(chave), constant=True)

    privacidade = _vm("privacidade")
    figuras = _vm("figuras")
    painel = _vm("painel")
    laboratorio = _vm("laboratorio")
    resultados = _vm("resultados")
    painelGeral = _vm("painelGeral")
    painelIncidentes = _vm("painelIncidentes")
    painelIntegridade = _vm("painelIntegridade")
    labFases = _vm("labFases")
    labRobustez = _vm("labRobustez")
    labExplicabilidade = _vm("labExplicabilidade")
    resSeparacao = _vm("resSeparacao")
    resQualidade = _vm("resQualidade")
    resGaleria = _vm("resGaleria")
    quiosque = _vm("quiosque")
    del _vm
