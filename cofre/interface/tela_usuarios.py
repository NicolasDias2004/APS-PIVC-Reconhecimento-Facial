"""Tela "Usuários": lista, busca e administra as pessoas cadastradas no banco.

Toda operação age sobre a linha selecionada na tabela. Depois de qualquer alteração a
tabela e os cartões são recarregados e, se a tela do terminal já existir e expuser
`recarregar_galeria()`, ela é avisada para o reconhecedor refletir a mudança.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from .. import config
from ..banco import Usuario
from . import tema, widgets
from .base import Tela

MARGEM = 24
ESPACO = 12
MINIATURA = 120
MINIATURAS_POR_LINHA = 4

COLUNAS = [
    ("id", "ID", 50),
    ("nome", "Nome", 220),
    ("matricula", "Matrícula", 110),
    ("cargo", "Cargo", 160),
    ("nivel", "Nível", 210),
    ("amostras", "Amostras", 80),
    ("ativo", "Ativo", 70),
    ("cadastro", "Cadastro", 140),
]


def _nivel_texto(nivel: int) -> str:
    return f"{nivel} - {config.NIVEIS.get(nivel, '?')}"


def _data_curta(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return iso or "-"


class TelaUsuarios(Tela):
    TITULO = "Usuários"

    # ------------------------------------------------------------------ construção
    def construir(self) -> None:
        self._usuarios: list[Usuario] = []
        self._amostras: dict[int, int] = {}
        self._selecionado: int | None = None
        self._janela_fotos: ctk.CTkToplevel | None = None
        self._janela_nivel: ctk.CTkToplevel | None = None
        self._precisa_recarregar = True

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        widgets.titulo(self, self.TITULO, "Pessoas autorizadas, nível de acesso e amostras biométricas").grid(
            row=0, column=0, sticky="ew", padx=MARGEM, pady=(MARGEM, ESPACO))

        # Cartões de resumo
        cartoes = ctk.CTkFrame(self, fg_color="transparent")
        cartoes.grid(row=1, column=0, sticky="ew", padx=MARGEM, pady=(0, ESPACO))
        self.cartao_total = widgets.Cartao(cartoes, "Usuários cadastrados", "0")
        self.cartao_ativos = widgets.Cartao(cartoes, "Ativos", "0", cor=tema.VERDE)
        self.cartoes_nivel = {
            n: widgets.Cartao(cartoes, f"Nível {n} - {config.NIVEIS[n]}", "0", cor=tema.COR_NIVEL[n])
            for n in sorted(config.NIVEIS)
        }
        for i, c in enumerate([self.cartao_total, self.cartao_ativos, *self.cartoes_nivel.values()]):
            cartoes.grid_columnconfigure(i, weight=1, uniform="cartao")
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else ESPACO, 0))

        # Busca e ações gerais
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=2, column=0, sticky="ew", padx=MARGEM, pady=(0, ESPACO))
        barra.grid_columnconfigure(0, weight=1)
        self.busca_var = tk.StringVar()
        self.busca_var.trace_add("write", lambda *_: self._filtrar())
        # Sem textvariable: com ela o CTkEntry não mostra o placeholder. A tecla copia o texto para busca_var.
        self.busca = ctk.CTkEntry(barra, placeholder_text="Buscar por nome ou matrícula",
                                  height=36, font=tema.CORPO, fg_color=tema.CARTAO, border_color=tema.BORDA)
        self.busca.grid(row=0, column=0, sticky="ew")
        self.busca.bind("<KeyRelease>", lambda _e: self.busca_var.set(self.busca.get()))
        self.btn_atualizar = widgets.botao_secundario(barra, "Atualizar", self.recarregar, height=36)
        self.btn_atualizar.grid(row=0, column=1, padx=(ESPACO, 0))
        self.btn_novo = widgets.botao(barra, "Novo cadastro", self.novo_cadastro, height=36)
        self.btn_novo.grid(row=0, column=2, padx=(ESPACO, 0))

        # Tabela
        self.tabela = widgets.Tabela(self, COLUNAS, altura=14, ao_selecionar=self._ao_selecionar,
                                     ao_duplo_clique=lambda iid: self.ver_fotos())
        self.tabela.grid(row=3, column=0, sticky="nsew", padx=MARGEM, pady=(0, ESPACO))
        self.tabela.tree.column("id", anchor="center")
        self.tabela.tree.column("amostras", anchor="center")
        self.tabela.tree.column("ativo", anchor="center")

        # Ações sobre a linha selecionada
        acoes = ctk.CTkFrame(self, fg_color="transparent")
        acoes.grid(row=4, column=0, sticky="ew", padx=MARGEM, pady=(0, MARGEM))
        acoes.grid_columnconfigure(4, weight=1)
        self.btn_nivel = widgets.botao_secundario(acoes, "Alterar nível", self.alterar_nivel)
        self.btn_ativo = widgets.botao_secundario(acoes, "Ativar/Desativar", self.ativar_desativar)
        self.btn_fotos = widgets.botao_secundario(acoes, "Ver fotos", self.ver_fotos)
        self.btn_remover = widgets.botao(acoes, "Remover", self.remover, cor=tema.VERMELHO)
        for i, b in enumerate([self.btn_nivel, self.btn_ativo, self.btn_fotos, self.btn_remover]):
            b.grid(row=0, column=i, padx=(0 if i == 0 else ESPACO, 0))
        self.mensagem = ctk.CTkLabel(acoes, text="", font=tema.CORPO, text_color=tema.TEXTO_2, anchor="e",
                                     wraplength=520, justify="right")
        self.mensagem.grid(row=0, column=4, sticky="ew", padx=(ESPACO, 0))
        self._atualizar_botoes()

    # ------------------------------------------------------------------ ciclo da tela
    def ao_mostrar(self) -> None:
        self._precisa_recarregar = True

    def ao_esconder(self) -> None:
        self._fechar_janelas()

    def atualizar(self) -> None:
        if self._precisa_recarregar:
            self._precisa_recarregar = False
            self.recarregar()

    # ------------------------------------------------------------------ dados
    def recarregar(self) -> None:
        """Relê o banco e redesenha cartões e tabela (mantém a seleção quando possível)."""
        try:
            self._usuarios = self.app.banco.listar_usuarios()
            self._amostras = {u.id: self.app.banco.contar_amostras(u.id) for u in self._usuarios}
        except Exception as e:  # noqa: BLE001
            self._usuarios, self._amostras = [], {}
            self._avisar(f"Falha ao ler o banco: {e}", erro=True)
        self._preencher_cartoes()
        self._filtrar()

    def _preencher_cartoes(self) -> None:
        self.cartao_total.definir(len(self._usuarios))
        self.cartao_ativos.definir(sum(1 for u in self._usuarios if u.ativo))
        for n, c in self.cartoes_nivel.items():
            c.definir(sum(1 for u in self._usuarios if u.nivel == n))

    def _filtrar(self) -> None:
        termo = self.busca_var.get().strip().casefold()
        anterior = self._selecionado
        self.tabela.limpar()
        for u in self._usuarios:
            if termo and termo not in u.nome.casefold() and termo not in u.matricula.casefold():
                continue
            self.tabela.adicionar(str(u.id), [
                u.id, u.nome, u.matricula, u.cargo or "-", _nivel_texto(u.nivel),
                self._amostras.get(u.id, 0), "Sim" if u.ativo else "Não", _data_curta(u.criado_em),
            ], tag=None if u.ativo else "inativo")
        self._selecionado = None
        if anterior is not None and self.tabela.tree.exists(str(anterior)):
            self.tabela.tree.selection_set(str(anterior))
            self._selecionado = anterior
        self._atualizar_botoes()

    def _ao_selecionar(self, iid: str) -> None:
        try:
            self._selecionado = int(iid)
        except ValueError:
            self._selecionado = None
        self._atualizar_botoes()

    def _atualizar_botoes(self) -> None:
        estado = "normal" if self._selecionado is not None else "disabled"
        for b in (self.btn_nivel, self.btn_ativo, self.btn_fotos, self.btn_remover):
            b.configure(state=estado)

    def usuario_selecionado(self) -> Usuario | None:
        """Usuário da linha selecionada (relido do banco, para não agir sobre dado velho)."""
        if self._selecionado is None:
            return None
        try:
            u = self.app.banco.obter_usuario(self._selecionado)
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Falha ao ler o usuário: {e}", erro=True)
            return None
        if u is None:
            self._avisar("O usuário selecionado não existe mais.", erro=True)
            self.recarregar()
        return u

    # ------------------------------------------------------------------ ações
    def novo_cadastro(self) -> None:
        self.app.mostrar("tela_cadastro")

    def alterar_nivel(self, nivel: int | None = None) -> None:
        """Abre o diálogo com os 3 níveis; com `nivel` informado aplica direto (sem diálogo)."""
        u = self.usuario_selecionado()
        if u is None:
            return
        if nivel is None:
            self._dialogo_nivel(u)
            return
        if nivel == u.nivel:
            self._avisar(f"{u.nome} já está no nível {nivel}.")
            return
        try:
            self.app.banco.alterar_nivel(u.id, int(nivel))
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Não foi possível alterar o nível: {e}", erro=True)
            return
        self._apos_alteracao(f"{u.nome}: nível alterado para {_nivel_texto(int(nivel))}.")

    def ativar_desativar(self) -> None:
        u = self.usuario_selecionado()
        if u is None:
            return
        try:
            self.app.banco.definir_ativo(u.id, not u.ativo)
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Não foi possível alterar o status: {e}", erro=True)
            return
        self._apos_alteracao(f"{u.nome} {'reativado' if not u.ativo else 'desativado'}.")

    def remover(self) -> None:
        u = self.usuario_selecionado()
        if u is None:
            return
        n = self._amostras.get(u.id, 0)
        if not messagebox.askyesno(
                "Remover usuário",
                f"Remover {u.nome} (matrícula {u.matricula})?\n\n"
                f"As {n} amostras biométricas serão apagadas do banco. Esta ação não pode ser desfeita.",
                icon="warning", parent=self.winfo_toplevel()):
            return
        try:
            self.app.banco.remover_usuario(u.id)
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Não foi possível remover: {e}", erro=True)
            return
        self._selecionado = None
        self._apos_alteracao(f"{u.nome} removido do banco.")

    def ver_fotos(self) -> None:
        u = self.usuario_selecionado()
        if u is None:
            return
        try:
            caminhos = self.app.banco.fotos_do_usuario(u.id)
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Não foi possível listar as fotos: {e}", erro=True)
            return
        self._fechar_janela_fotos()
        self._janela_fotos = self._montar_janela_fotos(u, caminhos)

    def _apos_alteracao(self, texto: str) -> None:
        self._avisar(texto)
        self.recarregar()
        self._avisar_terminal()

    def _avisar_terminal(self) -> None:
        """Pede ao terminal (se já instanciado) que recarregue a galeria do reconhecedor."""
        try:
            terminal = self.app.tela("tela_terminal")
            fn = getattr(terminal, "recarregar_galeria", None)
            if callable(fn):
                fn()
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Alteração salva, mas o terminal não recarregou a galeria: {e}", erro=True)

    def _avisar(self, texto: str, erro: bool = False) -> None:
        self.mensagem.configure(text=texto, text_color=tema.VERMELHO if erro else tema.TEXTO_2)

    # ------------------------------------------------------------------ janelas auxiliares
    def _nova_janela(self, titulo: str, largura: int, altura: int) -> ctk.CTkToplevel:
        jan = ctk.CTkToplevel(self, fg_color=tema.FUNDO)
        jan.title(titulo)
        raiz = self.winfo_toplevel()
        x = raiz.winfo_rootx() + max(0, (raiz.winfo_width() - largura) // 2)
        y = raiz.winfo_rooty() + max(0, (raiz.winfo_height() - altura) // 2)
        jan.geometry(f"{largura}x{altura}+{x}+{y}")
        jan.transient(raiz)
        return jan

    def _dialogo_nivel(self, u: Usuario) -> None:
        self._fechar_janela_nivel()
        jan = self._nova_janela("Alterar nível de acesso", 460, 300)
        self._janela_nivel = jan
        ctk.CTkLabel(jan, text=f"Nível de acesso de {u.nome}", font=tema.SUBTITULO, text_color=tema.TEXTO,
                     anchor="w").pack(fill="x", padx=MARGEM, pady=(MARGEM, 4))
        ctk.CTkLabel(jan, text=f"Atual: {_nivel_texto(u.nivel)}", font=tema.PEQUENO, text_color=tema.TEXTO_2,
                     anchor="w").pack(fill="x", padx=MARGEM, pady=(0, ESPACO))
        var = tk.IntVar(master=jan, value=u.nivel)
        for n in sorted(config.NIVEIS):
            ctk.CTkRadioButton(jan, text=f"{_nivel_texto(n)}  (acesso: {config.AREAS.get(n, '')})",
                               variable=var, value=n, font=tema.CORPO, fg_color=tema.COR_NIVEL[n],
                               hover_color=tema.COR_NIVEL[n]).pack(anchor="w", padx=MARGEM, pady=4)
        rodape = ctk.CTkFrame(jan, fg_color="transparent")
        rodape.pack(fill="x", side="bottom", padx=MARGEM, pady=MARGEM)

        def confirmar() -> None:
            nivel = var.get()
            self._fechar_janela_nivel()
            self.alterar_nivel(nivel)

        widgets.botao(rodape, "Salvar", confirmar).pack(side="right")
        widgets.botao_secundario(rodape, "Cancelar", self._fechar_janela_nivel).pack(side="right", padx=(0, ESPACO))
        jan.protocol("WM_DELETE_WINDOW", self._fechar_janela_nivel)
        jan.bind("<Escape>", lambda e: self._fechar_janela_nivel())
        jan.bind("<Return>", lambda e: confirmar())
        jan.after(50, lambda: self._focar(jan))

    def _montar_janela_fotos(self, u: Usuario, caminhos: list[str]) -> ctk.CTkToplevel:
        largura = MINIATURAS_POR_LINHA * (MINIATURA + ESPACO) + 2 * MARGEM + 24
        jan = self._nova_janela(f"Fotos de {u.nome}", largura, 560)
        ctk.CTkLabel(jan, text=f"{u.nome}  -  matrícula {u.matricula}", font=tema.SUBTITULO, text_color=tema.TEXTO,
                     anchor="w").pack(fill="x", padx=MARGEM, pady=(MARGEM, 0))
        ctk.CTkLabel(jan, text=f"{len(caminhos)} foto(s) de referência em {config.FOTOS_DIR}", font=tema.PEQUENO,
                     text_color=tema.TEXTO_2, anchor="w", wraplength=largura - 2 * MARGEM,
                     justify="left").pack(fill="x", padx=MARGEM, pady=(0, ESPACO))
        area = ctk.CTkScrollableFrame(jan, fg_color=tema.FUNDO_2, corner_radius=10)
        area.pack(fill="both", expand=True, padx=MARGEM, pady=(0, ESPACO))
        jan.miniaturas = []  # referência viva das imagens (o Tk não as retém)
        if not caminhos:
            ctk.CTkLabel(area, text="Este usuário não tem fotos de referência salvas.", font=tema.CORPO,
                         text_color=tema.TEXTO_2).pack(padx=ESPACO, pady=ESPACO)
        for i, caminho in enumerate(caminhos):
            celula = ctk.CTkFrame(area, fg_color=tema.CARTAO, corner_radius=8, width=MINIATURA + 8)
            celula.grid(row=i // MINIATURAS_POR_LINHA, column=i % MINIATURAS_POR_LINHA, padx=ESPACO // 2,
                        pady=ESPACO // 2, sticky="n")
            img = self._miniatura(caminho)
            if img is None:
                ctk.CTkLabel(celula, text="arquivo\nnão encontrado", font=tema.PEQUENO, text_color=tema.VERMELHO,
                             width=MINIATURA, height=MINIATURA).pack(padx=4, pady=(4, 0))
            else:
                jan.miniaturas.append(img)
                ctk.CTkLabel(celula, text="", image=img, width=MINIATURA, height=MINIATURA).pack(padx=4, pady=(4, 0))
            ctk.CTkLabel(celula, text=Path(caminho).name, font=tema.PEQUENO, text_color=tema.TEXTO_2,
                         width=MINIATURA, wraplength=MINIATURA).pack(padx=4, pady=(2, 4))
        widgets.botao_secundario(jan, "Fechar", self._fechar_janela_fotos).pack(side="bottom", anchor="e",
                                                                                 padx=MARGEM, pady=(0, MARGEM))
        jan.protocol("WM_DELETE_WINDOW", self._fechar_janela_fotos)
        jan.bind("<Escape>", lambda e: self._fechar_janela_fotos())
        jan.after(50, lambda: self._focar(jan))
        return jan

    @staticmethod
    def _miniatura(caminho: str) -> ctk.CTkImage | None:
        try:
            with Image.open(caminho) as im:
                im = im.convert("RGB")
                im.thumbnail((MINIATURA, MINIATURA))
                return ctk.CTkImage(im.copy(), size=im.size)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _focar(jan: ctk.CTkToplevel) -> None:
        try:
            if jan.winfo_exists():
                jan.lift()
                jan.focus_force()
        except tk.TclError:
            pass

    def _fechar_janela_fotos(self) -> None:
        jan, self._janela_fotos = self._janela_fotos, None
        if jan is not None:
            try:
                jan.destroy()
            except tk.TclError:
                pass

    def _fechar_janela_nivel(self) -> None:
        jan, self._janela_nivel = self._janela_nivel, None
        if jan is not None:
            try:
                jan.destroy()
            except tk.TclError:
                pass

    def _fechar_janelas(self) -> None:
        self._fechar_janela_fotos()
        self._fechar_janela_nivel()
