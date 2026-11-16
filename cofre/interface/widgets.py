"""Widgets reutilizáveis do aplicativo."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence

import customtkinter as ctk
import numpy as np

from . import tema


class VideoWidget(ctk.CTkLabel):
    """Exibe frames BGR do OpenCV, ajustando à área disponível."""

    def __init__(self, master, largura=640, altura=360, **kw):
        super().__init__(master, text="", fg_color=tema.FUNDO, corner_radius=8, **kw)
        self._largura, self._altura = largura, altura
        self._img: ctk.CTkImage | None = None
        self.configure(width=largura, height=altura)
        self.mensagem("Câmera desligada")

    def mostrar(self, frame: np.ndarray | None) -> None:
        if frame is None:
            return
        w = max(self.winfo_width(), 2)
        h = max(self.winfo_height(), 2)
        if w < 50 or h < 50:
            w, h = self._largura, self._altura
        red = tema.ajustar(frame, w - 4, h - 4)
        pil = tema.bgr_para_pil(red)
        self._img = ctk.CTkImage(pil, size=(red.shape[1], red.shape[0]))
        self.configure(image=self._img, text="")

    def mensagem(self, texto: str) -> None:
        self._img = None
        self.configure(image=None, text=texto, font=tema.SUBTITULO, text_color=tema.TEXTO_2)


class Cartao(ctk.CTkFrame):
    """Cartão com valor grande e rótulo pequeno (estatísticas)."""

    def __init__(self, master, rotulo: str, valor: str = "-", cor: str = tema.TEXTO, **kw):
        super().__init__(master, fg_color=tema.CARTAO, corner_radius=10, **kw)
        self.valor = ctk.CTkLabel(self, text=valor, font=(tema.FONTE, 26, "bold"), text_color=cor)
        self.valor.pack(padx=16, pady=(12, 0))
        self.rotulo = ctk.CTkLabel(self, text=rotulo, font=tema.PEQUENO, text_color=tema.TEXTO_2, justify="center")
        self.rotulo.pack(padx=16, pady=(0, 12))
        self.bind("<Configure>", self._ajustar_rotulo, add="+")

    def _ajustar_rotulo(self, evento) -> None:
        # Rótulos longos ("Nível 3 - Ministro do Meio Ambiente") quebram em vez de sair cortados.
        self.rotulo.configure(wraplength=max(60, evento.width - 32))

    def definir(self, valor, cor: str | None = None) -> None:
        self.valor.configure(text=str(valor), **({"text_color": cor} if cor else {}))


class Faixa(ctk.CTkFrame):
    """Faixa colorida de status com texto (veredito, instrução, aviso)."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=tema.CARTAO, corner_radius=10, height=64, **kw)
        self.pack_propagate(False)
        self.texto = ctk.CTkLabel(self, text="", font=(tema.FONTE, 16, "bold"), text_color=tema.TEXTO,
                                  wraplength=900, justify="left")
        self.texto.pack(fill="both", expand=True, padx=16, pady=8)

    def definir(self, texto: str, cor: str = tema.CARTAO, cor_texto: str = tema.TEXTO) -> None:
        self.configure(fg_color=cor)
        self.texto.configure(text=texto, text_color=cor_texto)


def estilo_tabela_escura() -> None:
    """Aplica tema escuro ao ttk.Treeview (uma vez por aplicativo)."""
    st = ttk.Style()
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure("Escura.Treeview", background=tema.CARTAO, fieldbackground=tema.CARTAO, foreground=tema.TEXTO,
                 rowheight=28, borderwidth=0, font=tema.CORPO, bordercolor=tema.CARTAO,
                 lightcolor=tema.CARTAO, darkcolor=tema.CARTAO)
    # O tema clam desenha uma moldura clara em volta do Treeview; o layout abaixo deixa só a área das linhas.
    st.layout("Escura.Treeview", [("Escura.Treeview.treearea", {"sticky": "nswe"})])
    st.configure("Escura.Treeview.Heading", background=tema.FUNDO_2, foreground=tema.TEXTO_2, relief="flat",
                 font=(tema.FONTE, 12, "bold"))
    st.map("Escura.Treeview", background=[("selected", tema.ACENTO)], foreground=[("selected", tema.FUNDO)])
    st.map("Escura.Treeview.Heading", background=[("active", tema.BORDA)])


class Tabela(ctk.CTkFrame):
    """ttk.Treeview com tema escuro, barra de rolagem e API simples."""

    def __init__(self, master, colunas: Sequence[tuple[str, str, int]], altura: int = 12,
                 ao_selecionar: Callable[[str], None] | None = None,
                 ao_duplo_clique: Callable[[str], None] | None = None,
                 rolagem_horizontal: bool = False, **kw):
        """colunas: lista de (id, título, largura_px). Com `rolagem_horizontal`, as colunas mantêm
        a largura dada e o que não couber fica acessível pela barra horizontal."""
        super().__init__(master, fg_color=tema.CARTAO, corner_radius=10, **kw)
        estilo_tabela_escura()
        ids = [c[0] for c in colunas]
        self.tree = ttk.Treeview(self, columns=ids, show="headings", height=altura, style="Escura.Treeview",
                                 selectmode="browse")
        for cid, titulo, larg in colunas:
            self.tree.heading(cid, text=titulo)
            self.tree.column(cid, width=larg, minwidth=40, anchor="w", stretch=not rolagem_horizontal)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        barra = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=barra.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 0 if rolagem_horizontal else 8))
        barra.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=8)
        if rolagem_horizontal:
            barra_h = ctk.CTkScrollbar(self, orientation="horizontal", command=self.tree.xview)
            self.tree.configure(xscrollcommand=barra_h.set)
            barra_h.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=(0, 4))
        self.tree.tag_configure("ok", foreground=tema.VERDE)
        self.tree.tag_configure("neg", foreground=tema.VERMELHO)
        self.tree.tag_configure("aviso", foreground=tema.LARANJA)
        self.tree.tag_configure("inativo", foreground=tema.TEXTO_2)
        if ao_selecionar:
            self.tree.bind("<<TreeviewSelect>>", lambda e: self._emitir(ao_selecionar))
        if ao_duplo_clique:
            self.tree.bind("<Double-1>", lambda e: self._emitir(ao_duplo_clique))

    def _emitir(self, fn):
        sel = self.tree.selection()
        if sel:
            fn(sel[0])

    def limpar(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def adicionar(self, iid: str, valores: Sequence, tag: str | None = None) -> None:
        self.tree.insert("", "end", iid=iid, values=list(valores), tags=(tag,) if tag else ())

    def selecionado(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None


class BarraStatus(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=tema.FUNDO_2, corner_radius=0, height=28, **kw)
        self.pack_propagate(False)
        self.esq = ctk.CTkLabel(self, text="", font=tema.PEQUENO, text_color=tema.TEXTO_2)
        self.esq.pack(side="left", padx=12)
        self.dir = ctk.CTkLabel(self, text="", font=tema.PEQUENO, text_color=tema.TEXTO_2)
        self.dir.pack(side="right", padx=12)

    def definir(self, esquerda: str | None = None, direita: str | None = None) -> None:
        if esquerda is not None:
            self.esq.configure(text=esquerda)
        if direita is not None:
            self.dir.configure(text=direita)


def titulo(master, texto: str, subtitulo: str | None = None) -> ctk.CTkFrame:
    f = ctk.CTkFrame(master, fg_color="transparent")
    ctk.CTkLabel(f, text=texto, font=tema.TITULO, text_color=tema.TEXTO, anchor="w").pack(fill="x")
    if subtitulo:
        ctk.CTkLabel(f, text=subtitulo, font=tema.CORPO, text_color=tema.TEXTO_2, anchor="w").pack(fill="x")
    return f


def botao(master, texto: str, comando, cor: str | None = None, **kw) -> ctk.CTkButton:
    extra = {"fg_color": cor, "hover_color": cor} if cor else {"fg_color": tema.ACENTO, "hover_color": tema.ACENTO_HOVER}
    return ctk.CTkButton(master, text=texto, command=comando, font=tema.CORPO, corner_radius=8,
                         text_color=tema.FUNDO if not cor else tema.TEXTO, **extra, **kw)


def botao_secundario(master, texto: str, comando, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=texto, command=comando, font=tema.CORPO, corner_radius=8,
                         fg_color=tema.CARTAO, hover_color=tema.BORDA, border_width=1, border_color=tema.BORDA,
                         text_color=tema.TEXTO, **kw)
