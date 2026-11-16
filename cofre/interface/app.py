"""Janela principal do aplicativo: barra lateral, área de conteúdo e ciclo de atualização."""

from __future__ import annotations

import importlib
import threading
import traceback

import customtkinter as ctk

from .. import __version__, config
from ..banco import Banco
from . import tema
from .base import Tela
from .camera import ServicoCamera
from .widgets import BarraStatus

# (módulo, classe, rótulo do menu)
TELAS = [
    ("tela_terminal", "TelaTerminal", "Terminal de acesso"),
    ("tela_cadastro", "TelaCadastro", "Cadastro biométrico"),
    ("tela_usuarios", "TelaUsuarios", "Usuários"),
    ("tela_acessos", "TelaAcessos", "Acessos e relatórios"),
    ("tela_ferramentas", "TelaFerramentas", "Avaliação e demo"),
    ("tela_config", "TelaConfig", "Configurações"),
]

INTERVALO_MS = 33  # ~30 atualizações por segundo


class TelaIndisponivel(Tela):
    def __init__(self, master, app, nome: str, erro: str):
        self._nome, self._erro = nome, erro
        super().__init__(master, app)

    def construir(self) -> None:
        ctk.CTkLabel(self, text=f"Tela '{self._nome}' indisponível", font=tema.TITULO,
                     text_color=tema.VERMELHO).pack(padx=24, pady=(24, 8), anchor="w")
        ctk.CTkLabel(self, text=self._erro, font=tema.MONO, text_color=tema.TEXTO_2, justify="left",
                     wraplength=900).pack(padx=24, anchor="w")


class App(ctk.CTk):
    def __init__(self, caminho_db=config.DB_PATH, fonte_camera=None):
        """`fonte_camera`: fábrica da fonte de vídeo (padrão: a webcam). Os testes passam uma
        câmera falsa aqui, porque a primeira tela já liga a câmera durante o construtor."""
        super().__init__(fg_color=tema.FUNDO)
        ctk.set_appearance_mode("dark")
        self.title("Cofre MMA - Autenticação Biométrica")
        self.geometry("1280x800")
        self.minsize(1024, 680)
        self.banco = Banco(caminho_db)
        self.camera = ServicoCamera()
        if fonte_camera is not None:
            self.camera.fonte_fabrica = fonte_camera
        self.pipeline = None            # carregado em thread (modelos ONNX levam ~0,5 s)
        self._erro_pipeline: str | None = None
        self._telas: dict[str, Tela] = {}
        self._botoes: dict[str, ctk.CTkButton] = {}
        self._atual: str | None = None
        self._construir()
        threading.Thread(target=self._carregar_pipeline, daemon=True).start()
        self.after(INTERVALO_MS, self._tick)
        self.protocol("WM_DELETE_WINDOW", self.fechar)

    # ------------------------------------------------------------------ layout
    def _construir(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        lateral = ctk.CTkFrame(self, width=230, fg_color=tema.FUNDO_2, corner_radius=0)
        lateral.grid(row=0, column=0, sticky="nsw")
        lateral.grid_propagate(False)
        ctk.CTkLabel(lateral, text="COFRE MMA", font=(tema.FONTE, 20, "bold"), text_color=tema.ACENTO).pack(
            padx=20, pady=(26, 0), anchor="w")
        ctk.CTkLabel(lateral, text="Autenticação biométrica facial", font=tema.PEQUENO,
                     text_color=tema.TEXTO_2).pack(padx=20, pady=(0, 24), anchor="w")
        for mod, cls, rotulo in TELAS:
            b = ctk.CTkButton(lateral, text=rotulo, anchor="w", height=40, corner_radius=8, font=tema.CORPO,
                              fg_color="transparent", hover_color=tema.CARTAO, text_color=tema.TEXTO,
                              command=lambda m=mod: self.mostrar(m))
            b.pack(fill="x", padx=12, pady=3)
            self._botoes[mod] = b
        ctk.CTkLabel(lateral, text=f"v{__version__}", font=tema.PEQUENO, text_color=tema.TEXTO_2).pack(
            side="bottom", pady=12)
        self.area = ctk.CTkFrame(self, fg_color=tema.FUNDO, corner_radius=0)
        self.area.grid(row=0, column=1, sticky="nsew")
        self.area.grid_rowconfigure(0, weight=1)
        self.area.grid_columnconfigure(0, weight=1)
        self.status = BarraStatus(self)
        self.status.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.status.definir("Carregando modelos...", f"banco: {self.banco.caminho.name}")
        self.mostrar(TELAS[0][0])

    def _carregar_pipeline(self) -> None:
        try:
            from ..pipeline import Pipeline
            self.pipeline = Pipeline()
        except Exception as e:  # noqa: BLE001
            self._erro_pipeline = f"Falha ao carregar os modelos: {e}"

    # ------------------------------------------------------------------ telas
    def _instanciar(self, mod: str) -> Tela:
        _, cls, rotulo = next(t for t in TELAS if t[0] == mod)
        try:
            modulo = importlib.import_module(f"{__package__}.{mod}")
            return getattr(modulo, cls)(self.area, self)
        except Exception:  # noqa: BLE001
            return TelaIndisponivel(self.area, self, rotulo, traceback.format_exc())

    def mostrar(self, mod: str) -> None:
        if mod == self._atual:
            return
        if self._atual is not None:
            atual = self._telas[self._atual]
            atual.ao_esconder()
            atual.grid_forget()
            self._botoes[self._atual].configure(fg_color="transparent", text_color=tema.TEXTO)
        if mod not in self._telas:
            self._telas[mod] = self._instanciar(mod)
        tela = self._telas[mod]
        tela.grid(row=0, column=0, sticky="nsew")
        self._botoes[mod].configure(fg_color=tema.CARTAO, text_color=tema.ACENTO)
        self._atual = mod
        if self.pipeline is not None:   # enquanto carrega, mantém o aviso de "Carregando modelos..."
            self.status.definir(next(t[2] for t in TELAS if t[0] == mod), None)
        tela.ao_mostrar()

    def tela(self, mod: str) -> Tela | None:
        return self._telas.get(mod)

    # ------------------------------------------------------------------ ciclo
    def _tick(self) -> None:
        try:
            if self.pipeline is not None and self.status.esq.cget("text") == "Carregando modelos...":
                self.status.definir("Modelos carregados", None)
            if self._erro_pipeline:
                self.status.definir(self._erro_pipeline, None)
            if self.camera.erro:
                self.status.definir(f"Câmera: {self.camera.erro}", None)
            if self._atual is not None:
                self._telas[self._atual].atualizar()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        self.after(INTERVALO_MS, self._tick)

    def pipeline_pronto(self) -> bool:
        return self.pipeline is not None

    def fechar(self) -> None:
        try:
            if self._atual is not None:
                self._telas[self._atual].ao_esconder()
            self.camera.parar()
            self.banco.fechar()
        finally:
            self.destroy()


def executar(caminho_db=config.DB_PATH) -> None:
    App(caminho_db).mainloop()
