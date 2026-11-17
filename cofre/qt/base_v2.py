"""Bases dos ViewModels da v2: a aba (estado, erro, progresso e um trabalho cancelável), a página
que troca de aba e o substituto de um ViewModel que não carregou.

Contrato de recálculo, igual para todas as abas:
  - sinal externo (banco alterado, período do painel, amostra do laboratório, chave "Mostrar
    nomes") é ligado a `pedir_recarga`, nunca direto a `recarregar`: com a aba inativa ele só
    marca `_sujo`, sem trabalho nenhum;
  - `recarregar()` e todo slot que dispara trabalho começam com
    `if not self.ativa: self._sujo = True; return`;
  - ao ser ativada, a aba recalcula se estiver suja (ou sempre, com `SEMPRE_RECALCULA = True`).
"""

from __future__ import annotations

import traceback
from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from .base import ViewModel, prop
from .trabalhos import Trabalho

ESTADOS = ("vazio", "carregando", "pronto", "poucos", "erro", "indisponivel")


class VMIndisponivel(ViewModel):
    """Substituto de um ViewModel que falhou ao carregar: ganchos vazios, erro em texto."""

    def __init__(self, aplicacao, parent=None, erro: str = ""):
        super().__init__(aplicacao, parent)
        self._erro_carga = erro

    def _get_erro_carga(self) -> str:
        return self._erro_carga

    erroCarga = Property(str, _get_erro_carga, constant=True)


class ViewModelAba(ViewModel):
    """Base de toda aba nova. A subclasse sobrescreve `recarregar`, `_limpar_dados` e, se precisar,
    `ao_ativar`, `ao_desativar` e `preparar_captura`; `ativar`, `desativar` e `pedir_recarga` são
    chamados pela página e pelos sinais externos e não são sobrescritos."""

    SEMPRE_RECALCULA = False                    # True nas três abas do Painel: o terminal não avisa quando grava
    VARIANTES_CAPTURA: tuple[str, ...] = ()     # variantes extras de captura desta aba (ferramentas/capturar_telas.py)

    estadoMudou = Signal()
    erroMudou = Signal()
    progressoMudou = Signal()

    estado = prop(str, "estado", estadoMudou)              # um de ESTADOS
    erro = prop(str, "erro", erroMudou)                    # texto pronto para a tela ("" = sem erro)
    progresso = prop(float, "progresso", progressoMudou)   # 0..1; -1 = indeterminado

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(estado="vazio", erro="", progresso=-1.0)
        self._ativa = False
        self._sujo = True
        self._estado_anterior = "vazio"         # para onde `cancelar` volta
        self._ultimo_erro = ""
        self.trabalho = Trabalho(aplicacao.extensoes.trabalhos, self)
        self.trabalho.progresso.connect(self._ao_progresso)
        self.trabalho.ocupadoMudou.connect(self._ao_ocupado)

    # ------------------------------------------------------------------ a subclasse sobrescreve
    @Slot()
    def recarregar(self) -> None:
        """Dispara o cálculo da aba."""

    def ao_ativar(self) -> None:
        if self._sujo or self.SEMPRE_RECALCULA:
            self._sujo = False
            self.recarregar()

    def ao_desativar(self) -> None:
        self.trabalho.cancelar()

    def _limpar_dados(self) -> None:
        """Zera as propriedades de dado (chamado por `_falhar` e `_indisponivel`)."""

    def preparar_captura(self, variante: str = "") -> None:
        """Deixa a aba no ponto para a foto. Usado só por ferramentas/capturar_telas.py."""

    # ------------------------------------------------------------------ página e sinais externos
    def ativar(self) -> None:
        self._ativa = True
        self.ao_ativar()

    def desativar(self) -> None:
        self._ativa = False
        self.ao_desativar()
        if self._v["estado"] == "carregando" and not self.trabalho.ocupado:
            self._sair_do_carregando()          # cálculo interrompido pela saída: refaz ao voltar
            self._sujo = True

    @Slot()
    def pedir_recarga(self) -> None:
        """Destino de todo sinal externo: recalcula se a aba está na tela; senão só a marca como suja."""
        if self._ativa:
            self.recarregar()
        else:
            self._sujo = True

    @Slot()
    def ao_mudar_nomes(self) -> None:
        """Destino da chave "Mostrar nomes" nas abas que mostram pessoas. Ao desligar, os dados com
        nome saem na hora (com a aba fora da tela, ou se o recálculo for cancelado, eles ficariam)."""
        if not bool(getattr(self.app.extensoes.obter("privacidade"), "mostrarNomes", False)):
            self.trabalho.cancelar()
            self._limpar_dados()
            self._estado_anterior = "vazio"
            self._definir("estado", "vazio")
        self.pedir_recarga()

    def ao_banco_alterado(self) -> None:
        self.pedir_recarga()

    def ao_pipeline_pronto(self) -> None:
        if self._v["estado"] == "indisponivel":
            self.pedir_recarga()

    # ------------------------------------------------------------------ utilitários
    def _falhar(self, texto: str) -> None:
        self._limpar_dados()                    # nenhum número antigo fica na tela
        self._definir("erro", texto)
        self._definir("estado", "erro")

    def _indisponivel(self, texto: str) -> None:
        self._limpar_dados()
        self._definir("erro", texto)
        self._definir("estado", "indisponivel")

    @property
    def ativa(self) -> bool:
        return self._ativa

    @property
    def caminho_db(self):
        return self.app.banco.caminho

    @Slot()
    def cancelar(self) -> None:
        """Cancela o cálculo em andamento; a aba volta ao estado em que estava antes dele."""
        self.trabalho.cancelar()
        self._sair_do_carregando()

    def _definir(self, nome: str, valor: Any) -> bool:
        if nome == "estado" and valor == "carregando" and self._v["estado"] != "carregando":
            self._estado_anterior = self._v["estado"]
            super()._definir("progresso", -1.0)
        elif nome == "erro" and valor:
            self._ultimo_erro = valor
        return super()._definir(nome, valor)

    def _sair_do_carregando(self) -> None:
        if self._v["estado"] != "carregando":
            return
        if self._estado_anterior in ("erro", "indisponivel"):
            self._definir("erro", self._ultimo_erro)       # o texto que a subclasse limpou ao recalcular
        self._definir("estado", self._estado_anterior)

    @Slot(float)
    def _ao_progresso(self, fracao: float) -> None:
        self._definir("progresso", fracao)

    @Slot()
    def _ao_ocupado(self) -> None:
        if not self.trabalho.ocupado:
            self._definir("progresso", -1.0)


class PaginaAbasVM(ViewModel):
    """Base das três páginas novas: guarda a aba atual e repassa os ganchos da Aplicacao aos
    ViewModels das abas, que ficam no registro de `Extensoes`."""

    CHAVE = ""                                  # "painel" | "laboratorio" | "resultados"

    abaMudou = Signal()

    aba = prop(str, "aba", abaMudou)            # valor da aba atual; inicial = a primeira da página

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        valores = self._valores()
        self._iniciar(aba=valores[0] if valores else "")
        self._ativo = False

    def _valores(self) -> list[str]:
        return [a["valor"] for a in self.abas()]

    def _vms_das_abas(self) -> list[ViewModel]:
        return [self.app.extensoes.obter(a["chaveVm"]) for a in self.abas()]

    # ------------------------------------------------------------------ uso pelo QML
    @Slot(result="QVariantList")
    def abas(self) -> list[dict]:
        return self.app.extensoes.abasDe(self.CHAVE)

    @Slot(str)
    def definirAba(self, valor: str) -> None:
        if valor == self._v["aba"] or valor not in self._valores():
            return
        if self._ativo:
            try:
                self.vm_aba().desativar()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        self._definir("aba", valor)
        if self._ativo:
            try:
                self.vm_aba().ativar()
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self.app.notificar("erro", f"Falha ao abrir a aba: {e}")

    # ------------------------------------------------------------------ ganchos da Aplicacao
    def vm_aba(self, valor: str | None = None):
        """ViewModel da aba (a atual por padrão); `None` se o valor não é uma aba desta página."""
        valor = self._v["aba"] if valor is None else valor
        for a in self.abas():
            if a["valor"] == valor:
                return self.app.extensoes.obter(a["chaveVm"])
        return None

    def ativar(self) -> None:
        self._ativo = True
        self.vm_aba().ativar()

    def desativar(self) -> None:
        try:
            self.vm_aba().desativar()
        finally:
            self._ativo = False

    def ao_banco_alterado(self) -> None:
        for vm in self._vms_das_abas():         # a exceção na aba de um lote não corta o repasse às outras
            try:
                vm.ao_banco_alterado()
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    def ao_pipeline_pronto(self) -> None:
        for vm in self._vms_das_abas():
            try:
                vm.ao_pipeline_pronto()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
