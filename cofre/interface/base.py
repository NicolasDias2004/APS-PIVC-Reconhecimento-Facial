"""Classe base das telas do aplicativo."""

from __future__ import annotations

import customtkinter as ctk

from . import tema


class Tela(ctk.CTkFrame):
    """Cada tela recebe a referência do `App` (banco, pipeline, câmera, status) e
    implementa `ao_mostrar()` / `ao_esconder()` (ligar/desligar câmera etc.) e
    `atualizar()` (chamado ~30x por segundo enquanto visível, na thread do Tk)."""

    TITULO = ""
    ICONE = ""

    def __init__(self, master, app):
        super().__init__(master, fg_color=tema.FUNDO, corner_radius=0)
        self.app = app
        self.construir()

    def construir(self) -> None:
        """Monta os widgets. Chamado uma vez no construtor."""

    def ao_mostrar(self) -> None:
        """Chamado toda vez que a tela passa a ser exibida."""

    def ao_esconder(self) -> None:
        """Chamado quando o usuário troca para outra tela."""

    def atualizar(self) -> None:
        """Chamado periodicamente (~30 Hz) enquanto a tela está visível."""
