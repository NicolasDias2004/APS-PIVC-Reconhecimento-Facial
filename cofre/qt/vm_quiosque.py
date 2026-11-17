"""Modo porta (v2): estado do quiosque.

O quiosque só abre sobre o terminal e com a área liberada fechada. Ele não decide nada: a tela
reflete o `TerminalVM` e o `SessaoVM`. O vídeo vem do `FonteVideo` que o terminal já alimenta a
cada quadro (cópia da referência da imagem, sem as caixas); a câmera não é tocada aqui.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from .base import ViewModel, objeto, prop
from .video import FonteVideo

_SEM_ROSTO = {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}


class QuiosqueVM(ViewModel):
    ativoMudou = Signal()
    usadoMudou = Signal()
    telaCheiaMudou = Signal()
    telaCheiaAtivaMudou = Signal()
    temRostoMudou = Signal()
    rostoMudou = Signal()
    quadroLarguraMudou = Signal()
    quadroAlturaMudou = Signal()

    ativo = prop(bool, "ativo", ativoMudou)                              # quiosque aberto
    usado = prop(bool, "usado", usadoMudou)                              # já foi aberto alguma vez
    telaCheia = prop(bool, "telaCheia", telaCheiaMudou)                  # preferência de sessão
    telaCheiaAtiva = prop(bool, "telaCheiaAtiva", telaCheiaAtivaMudou)   # ativo and telaCheia
    temRosto = prop(bool, "temRosto", temRostoMudou)                     # há caixa principal no quadro
    rosto = prop("QVariantMap", "rosto", rostoMudou)                     # {x, y, w, h} em 0..1
    quadroLargura = prop(int, "quadroLargura", quadroLarguraMudou)
    quadroAltura = prop(int, "quadroAltura", quadroAlturaMudou)
    fonteVideo = objeto("_video")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(ativo=False, usado=False, telaCheia=False, telaCheiaAtiva=False, temRosto=False,
                      rosto=dict(_SEM_ROSTO), quadroLargura=0, quadroAltura=0)
        self._video = FonteVideo("quiosque", self)
        aplicacao.paginaMudou.connect(self._ao_mudar_pagina)
        aplicacao.terminal_vm.video.mudou.connect(self._ao_quadro)

    @Slot()
    def entrar(self) -> None:
        if self.app.sessao_vm.ativa:
            return
        self.app.navegar("terminal")
        if self.app.pagina == "terminal":
            self._definir("ativo", True)
            self._definir("usado", True)
            self._atualizar_tela_cheia()
            self._ao_quadro()

    @Slot()
    def sair(self) -> None:
        self._definir("ativo", False)
        self._limpar_video()
        self._atualizar_tela_cheia()

    @Slot(bool)
    def definirTelaCheia(self, ligada: bool) -> None:
        """Só muda a preferência: a janela só vai a tela cheia com o quiosque aberto."""
        self._definir("telaCheia", bool(ligada))
        self._atualizar_tela_cheia()

    def _atualizar_tela_cheia(self) -> None:
        self._definir("telaCheiaAtiva", self._v["ativo"] and self._v["telaCheia"])

    @Slot()
    def _ao_mudar_pagina(self) -> None:
        if self.app.pagina != "terminal":
            self.sair()

    @Slot()
    def _ao_quadro(self) -> None:
        """Copia o quadro que o terminal acabou de mostrar (sem caixas) e a caixa principal dele."""
        if not self._v["ativo"]:
            return
        origem = self.app.terminal_vm.video
        imagem = origem.imagem
        if imagem.isNull():
            self._limpar_video()
            return
        qw, qh = imagem.width(), imagem.height()
        self._video.definir(imagem, [])
        self._definir("quadroLargura", qw)
        self._definir("quadroAltura", qh)
        principal = next((c for c in origem.caixas if c.get("principal") is True), None)
        if principal is None or qw <= 0 or qh <= 0:
            self._definir("temRosto", False)
            return
        self._definir("rosto", {"x": float(principal["x"]) / qw, "y": float(principal["y"]) / qh,
                                "w": float(principal["w"]) / qw, "h": float(principal["h"]) / qh})
        self._definir("temRosto", True)

    def _limpar_video(self) -> None:
        if self._video.temImagem:
            self._video.limpar()
        self._definir("temRosto", False)
