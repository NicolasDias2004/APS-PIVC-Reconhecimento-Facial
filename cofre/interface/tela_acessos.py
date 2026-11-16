"""Tela "Acessos e relatórios": estatísticas, log de auditoria com filtros, evidências e exportação."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from .. import config, relatorios
from ..banco import Acesso, Banco
from . import tema
from .base import Tela
from .widgets import Cartao, Tabela, botao, botao_secundario, titulo

TODOS = "Todos"
LIMITES = ("50", "200", "1000")
# Rótulos curtos para os cartões de negação (os completos estão em tema.ROTULO_RESULTADO)
ROTULO_CARTAO = {
    "NEGADO_NIVEL": "Nível insuficiente",
    "NEGADO_DESCONHECIDO": "Não cadastrados",
    "NEGADO_LIVENESS": "Prova de vida",
    "NEGADO_MULTIPLOS": "Mais de uma pessoa",
    "BLOQUEADO": "Bloqueios",
}


def _abrir_no_sistema(caminho: Path) -> None:
    """Abre um arquivo ou pasta com o aplicativo padrão do sistema operacional."""
    sistema = platform.system()
    if sistema == "Windows":
        os.startfile(str(caminho))  # type: ignore[attr-defined]  # noqa: S606
    elif sistema == "Darwin":
        subprocess.Popen(["open", str(caminho)])  # noqa: S603, S607
    else:
        subprocess.Popen(["xdg-open", str(caminho)])  # noqa: S603, S607


def _tag_resultado(resultado: str) -> str:
    if resultado == "CONCEDIDO":
        return "ok"
    if resultado == "NEGADO_NIVEL":
        return "aviso"
    return "neg"


class TelaAcessos(Tela):
    """Mostra o log de acessos com filtros, cartões de estatísticas, resumo por pessoa e por dia,
    e exporta relatórios CSV/HTML (em thread) com atalho para abrir o arquivo gerado."""

    TITULO = "Acessos e relatórios"

    # ------------------------------------------------------------------ construção
    def construir(self) -> None:
        self._acessos: dict[str, Acesso] = {}
        self._exportando = False
        self._resultado_exportacao: tuple[Path | None, str | None] | None = None  # (caminho, erro)
        self._ultimo_exportado: Path | None = None
        self._busca_agendada: str | None = None
        self._detalhe: ctk.CTkToplevel | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Cabeçalho: título + botões
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 12))
        cab.grid_columnconfigure(0, weight=1)
        titulo(cab, self.TITULO, "Log de auditoria das tentativas de autenticação").grid(row=0, column=0, sticky="w")
        botoes = ctk.CTkFrame(cab, fg_color="transparent")
        botoes.grid(row=0, column=1, sticky="e")
        self.btn_atualizar = botao_secundario(botoes, "Atualizar", self.recarregar, width=110)
        self.btn_atualizar.pack(side="left", padx=(0, 8))
        self.btn_evidencias = botao_secundario(botoes, "Abrir pasta de evidências", self.abrir_pasta_evidencias,
                                               width=190)
        self.btn_evidencias.pack(side="left", padx=(0, 8))
        self.btn_csv = botao(botoes, "Exportar CSV", lambda: self.exportar("csv"), width=120)
        self.btn_csv.pack(side="left", padx=(0, 8))
        self.btn_html = botao(botoes, "Exportar HTML", lambda: self.exportar("html"), width=130)
        self.btn_html.pack(side="left")

        # Cartões de estatísticas (duas fileiras de cinco)
        cartoes = ctk.CTkFrame(self, fg_color="transparent")
        cartoes.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        for c in range(5):
            cartoes.grid_columnconfigure(c, weight=1, uniform="cartao")
        self.cartoes: dict[str, Cartao] = {}
        linha1 = [("total", "Tentativas", tema.TEXTO), ("CONCEDIDO", "Concedidos", tema.VERDE),
                  ("negados", "Negados", tema.VERMELHO), ("usuarios", "Usuários", tema.ACENTO),
                  ("amostras", "Amostras", tema.ACENTO)]
        linha2 = [(k, r, tema.COR_RESULTADO[k]) for k, r in ROTULO_CARTAO.items()]
        for r, linha in enumerate((linha1, linha2)):
            for c, (chave, rotulo, cor) in enumerate(linha):
                cartao = Cartao(cartoes, rotulo, "0", cor)
                cartao.grid(row=r, column=c, sticky="ew", padx=(0 if c == 0 else 6, 0 if c == 4 else 6),
                            pady=(0, 8 if r == 0 else 0))
                self.cartoes[chave] = cartao

        # Filtros
        filtros = ctk.CTkFrame(self, fg_color="transparent")
        filtros.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        ctk.CTkLabel(filtros, text="Resultado", font=tema.PEQUENO, text_color=tema.TEXTO_2).pack(side="left")
        self._rotulo_para_chave = {v: k for k, v in tema.ROTULO_RESULTADO.items()}
        self.var_resultado = ctk.StringVar(value=TODOS)
        self.menu_resultado = ctk.CTkOptionMenu(
            filtros, values=[TODOS, *tema.ROTULO_RESULTADO.values()], variable=self.var_resultado,
            command=lambda _v: self.recarregar(), font=tema.CORPO, width=230, fg_color=tema.CARTAO,
            button_color=tema.BORDA, button_hover_color=tema.ACENTO_HOVER, dropdown_fg_color=tema.CARTAO)
        self.menu_resultado.pack(side="left", padx=(8, 16))
        ctk.CTkLabel(filtros, text="Pessoa", font=tema.PEQUENO, text_color=tema.TEXTO_2).pack(side="left")
        self.var_busca = ctk.StringVar()
        self.entrada_busca = ctk.CTkEntry(filtros, textvariable=self.var_busca, placeholder_text="buscar por nome",
                                          font=tema.CORPO, width=220, fg_color=tema.CARTAO, border_color=tema.BORDA)
        self.entrada_busca.pack(side="left", padx=(8, 16))
        self.entrada_busca.bind("<KeyRelease>", self._agendar_busca)
        ctk.CTkLabel(filtros, text="Limite", font=tema.PEQUENO, text_color=tema.TEXTO_2).pack(side="left")
        self.var_limite = ctk.StringVar(value=LIMITES[1])
        self.menu_limite = ctk.CTkOptionMenu(
            filtros, values=list(LIMITES), variable=self.var_limite, command=lambda _v: self.recarregar(),
            font=tema.CORPO, width=90, fg_color=tema.CARTAO, button_color=tema.BORDA,
            button_hover_color=tema.ACENTO_HOVER, dropdown_fg_color=tema.CARTAO)
        self.menu_limite.pack(side="left", padx=(8, 16))
        self.rotulo_contagem = ctk.CTkLabel(filtros, text="", font=tema.PEQUENO, text_color=tema.TEXTO_2)
        self.rotulo_contagem.pack(side="left")

        # Aviso / resultado da exportação (escondido até ser necessário)
        self.aviso = ctk.CTkFrame(self, fg_color=tema.CARTAO, corner_radius=10)
        self.aviso.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 12))
        self.aviso.grid_columnconfigure(0, weight=1)
        self.rotulo_aviso = ctk.CTkLabel(self.aviso, text="", font=tema.CORPO, text_color=tema.TEXTO, anchor="w",
                                         justify="left", wraplength=800)
        self.rotulo_aviso.grid(row=0, column=0, sticky="ew", padx=16, pady=10)
        self.btn_abrir = botao_secundario(self.aviso, "Abrir", self.abrir_exportado, width=90)
        self.btn_abrir.grid(row=0, column=1, padx=(0, 8), pady=6)
        self.btn_fechar_aviso = botao_secundario(self.aviso, "Fechar", self._esconder_aviso, width=80)
        self.btn_fechar_aviso.grid(row=0, column=2, padx=(0, 8), pady=6)
        self.aviso.grid_remove()

        # Corpo: tabela de acessos à esquerda, resumos à direita
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.grid(row=4, column=0, sticky="nsew", padx=24, pady=(0, 24))
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_columnconfigure(1, weight=0, minsize=330)
        corpo.grid_rowconfigure(0, weight=1)
        self.tabela = Tabela(corpo, [
            ("data", "Data/hora", 140), ("pessoa", "Pessoa", 140), ("nivel", "Nível", 50),
            ("exigido", "Exigido", 60), ("area", "Área", 170), ("simil", "Simil.", 60),
            ("resultado", "Resultado", 180), ("mensagem", "Mensagem", 220),
        ], altura=14, ao_duplo_clique=self._abrir_detalhe, rolagem_horizontal=True)
        # Só a ordem de exibição muda (os valores continuam na ordem acima): o que mais importa
        # aparece sem rolar; área e mensagem ficam à direita (e completas no duplo clique).
        self.tabela.tree.configure(displaycolumns=("data", "pessoa", "resultado", "nivel", "exigido", "simil",
                                                   "area", "mensagem"))
        self.tabela.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.tabela.tree.column("nivel", anchor="center")
        self.tabela.tree.column("exigido", anchor="center")
        self.tabela.tree.column("simil", anchor="e")

        lateral = ctk.CTkFrame(corpo, fg_color="transparent")
        lateral.grid(row=0, column=1, sticky="nsew")
        lateral.grid_columnconfigure(0, weight=1)
        lateral.grid_rowconfigure(1, weight=1)
        lateral.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(lateral, text="Por pessoa", font=tema.SUBTITULO, text_color=tema.TEXTO, anchor="w").grid(
            row=0, column=0, sticky="ew", pady=(0, 6))
        self.tabela_pessoas = Tabela(lateral, [("pessoa", "Pessoa", 150), ("conc", "Concedidos", 80),
                                               ("neg", "Negados", 70)], altura=6)
        self.tabela_pessoas.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        ctk.CTkLabel(lateral, text="Por dia", font=tema.SUBTITULO, text_color=tema.TEXTO, anchor="w").grid(
            row=2, column=0, sticky="ew", pady=(0, 6))
        self.tabela_dias = Tabela(lateral, [("dia", "Dia", 110), ("total", "Tentativas", 90),
                                            ("conc", "Concedidos", 90)], altura=6)
        self.tabela_dias.grid(row=3, column=0, sticky="nsew")
        for t in (self.tabela_pessoas, self.tabela_dias):
            for col in t.tree["columns"][1:]:
                t.tree.column(col, anchor="center")

    # ------------------------------------------------------------------ ciclo
    def ao_mostrar(self) -> None:
        self.recarregar()

    def ao_esconder(self) -> None:
        self._fechar_detalhe()

    def atualizar(self) -> None:
        if self._resultado_exportacao is not None:
            caminho, erro = self._resultado_exportacao
            self._resultado_exportacao = None
            self._exportando = False
            self.btn_csv.configure(state="normal")
            self.btn_html.configure(state="normal")
            if erro:
                self._mostrar_aviso(f"Falha ao exportar: {erro}", erro=True)
                self.app.status.definir("Falha na exportação", None)
            else:
                self._ultimo_exportado = caminho
                self._mostrar_aviso(f"Relatório salvo em {caminho}", abrir=True)
                self.app.status.definir(f"Relatório exportado: {caminho.name}", None)

    # ------------------------------------------------------------------ dados
    def recarregar(self) -> None:
        """Relê o banco e redesenha cartões, tabela e resumos conforme os filtros atuais."""
        self._busca_agendada = None
        try:
            est = self.app.banco.estatisticas()
            chave = self._rotulo_para_chave.get(self.var_resultado.get())
            limite = int(self.var_limite.get())
            acessos = self.app.banco.listar_acessos(limite=limite, resultado=chave)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._mostrar_aviso(f"Não foi possível ler o banco: {e}", erro=True)
            return
        self._preencher_cartoes(est)
        self._preencher_tabela(acessos)
        self._preencher_resumos(est)
        self.app.status.definir(None, f"banco: {self.app.banco.caminho.name} · {est['total']} tentativas")

    def _preencher_cartoes(self, est: dict) -> None:
        por = est["por_resultado"]
        concedidos = por.get("CONCEDIDO", 0)
        self.cartoes["total"].definir(est["total"])
        self.cartoes["CONCEDIDO"].definir(concedidos)
        self.cartoes["negados"].definir(est["total"] - concedidos)
        self.cartoes["usuarios"].definir(est["usuarios"])
        self.cartoes["amostras"].definir(est["amostras"])
        for chave in ROTULO_CARTAO:
            self.cartoes[chave].definir(por.get(chave, 0))

    def _preencher_tabela(self, acessos: list[Acesso]) -> None:
        termo = self.var_busca.get().strip().lower()
        self.tabela.limpar()
        self._acessos = {}
        for a in acessos:
            pessoa = a.nome_detectado or "-"
            if termo and termo not in pessoa.lower():
                continue
            iid = str(a.id)
            self._acessos[iid] = a
            self.tabela.adicionar(iid, [
                a.data_hora.replace("T", " "), pessoa, a.nivel_usuario or "-", a.nivel_exigido, a.area,
                f"{a.similaridade:.2f}" if a.similaridade is not None else "-",
                tema.ROTULO_RESULTADO.get(a.resultado, a.resultado), a.mensagem or "",
            ], tag=_tag_resultado(a.resultado))
        n = len(self._acessos)
        if n == 0:
            self.rotulo_contagem.configure(text="nenhuma tentativa com esses filtros")
        else:
            self.rotulo_contagem.configure(text=f"{n} {'tentativa' if n == 1 else 'tentativas'} listadas")

    def _preencher_resumos(self, est: dict) -> None:
        self.tabela_pessoas.limpar()
        for i, p in enumerate(est["por_usuario"]):
            self.tabela_pessoas.adicionar(f"p{i}", [p["nome"], p["concedidos"] or 0, p["negados"] or 0],
                                          tag="ok" if (p["negados"] or 0) == 0 else None)
        self.tabela_dias.limpar()
        for i, d in enumerate(est["por_dia"]):
            self.tabela_dias.adicionar(f"d{i}", [d["dia"], d["total"], d["concedidos"] or 0])

    def _agendar_busca(self, _evento=None) -> None:
        """Debounce da busca por nome: recarrega 250 ms após a última tecla."""
        if self._busca_agendada is not None:
            try:
                self.after_cancel(self._busca_agendada)
            except Exception:  # noqa: BLE001
                pass
        self._busca_agendada = self.after(250, self.recarregar)

    # ------------------------------------------------------------------ aviso
    def _mostrar_aviso(self, texto: str, erro: bool = False, abrir: bool = False) -> None:
        self.aviso.configure(fg_color=tema.VERMELHO if erro else tema.CARTAO)
        self.rotulo_aviso.configure(text=texto, text_color=tema.TEXTO)
        if abrir:
            self.btn_abrir.grid()
        else:
            self.btn_abrir.grid_remove()
        self.aviso.grid()

    def _esconder_aviso(self) -> None:
        self.aviso.grid_remove()

    # ------------------------------------------------------------------ exportação
    def exportar(self, formato: str) -> None:
        """Gera o relatório CSV ou HTML em uma thread; o resultado é lido em `atualizar()`."""
        if self._exportando:
            return
        formato = formato.lower()
        if formato not in ("csv", "html"):
            self._mostrar_aviso(f"Formato desconhecido: {formato}", erro=True)
            return
        self._exportando = True
        self.btn_csv.configure(state="disabled")
        self.btn_html.configure(state="disabled")
        self._mostrar_aviso(f"Exportando {formato.upper()}...")
        caminho_db = self.app.banco.caminho
        threading.Thread(target=self._exportar_em_thread, args=(formato, caminho_db), daemon=True).start()

    def _exportar_em_thread(self, formato: str, caminho_db: Path) -> None:
        # A conexão SQLite do App pertence à thread do Tk; aqui abrimos outra, só para leitura.
        banco = None
        try:
            banco = Banco(caminho_db)
            fn = relatorios.exportar_csv if formato == "csv" else relatorios.exportar_html
            caminho = fn(banco)
            self._resultado_exportacao = (Path(caminho), None)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._resultado_exportacao = (None, str(e))
        finally:
            if banco is not None:
                banco.fechar()

    def abrir_exportado(self) -> None:
        """Abre o último relatório gerado: HTML no navegador, CSV no aplicativo padrão."""
        caminho = self._ultimo_exportado
        if caminho is None or not caminho.exists():
            self._mostrar_aviso("O arquivo exportado não foi encontrado.", erro=True)
            return
        try:
            if caminho.suffix.lower() in (".html", ".htm"):
                webbrowser.open(caminho.resolve().as_uri())
            else:
                _abrir_no_sistema(caminho.resolve())
        except Exception as e:  # noqa: BLE001
            self._mostrar_aviso(f"Não foi possível abrir {caminho.name}: {e}", erro=True)

    def abrir_pasta_evidencias(self) -> None:
        pasta = Path(config.EVIDENCIAS_DIR)
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            _abrir_no_sistema(pasta.resolve())
        except Exception as e:  # noqa: BLE001
            self._mostrar_aviso(f"Não foi possível abrir a pasta de evidências: {e}", erro=True)

    # ------------------------------------------------------------------ detalhe
    def _abrir_detalhe(self, iid: str) -> None:
        acesso = self._acessos.get(iid)
        if acesso is None:
            return
        try:
            self.abrir_detalhe(acesso)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._mostrar_aviso(f"Não foi possível abrir o detalhe: {e}", erro=True)

    def abrir_detalhe(self, acesso: Acesso) -> ctk.CTkToplevel:
        """Janela com a foto de evidência (se houver) e os dados da tentativa."""
        self._fechar_detalhe()
        jan = ctk.CTkToplevel(self, fg_color=tema.FUNDO)
        jan.title(f"Tentativa #{acesso.id} - {tema.ROTULO_RESULTADO.get(acesso.resultado, acesso.resultado)}")
        jan.grid_columnconfigure(0, weight=1)
        jan.grid_rowconfigure(0, weight=1)
        self._detalhe = jan

        foto = ctk.CTkLabel(jan, text="", fg_color=tema.FUNDO_2, corner_radius=8)
        foto.grid(row=0, column=0, sticky="nsew", padx=24, pady=(24, 12))
        # Foto limitada a 800x600 e também ao que cabe na tela junto com o painel de dados (~420 px)
        maximo = (800, max(240, min(600, self.winfo_screenheight() - 420)))
        imagem = self._carregar_evidencia(acesso.evidencia, maximo)
        if imagem is not None:
            jan._imagem_evidencia = ctk.CTkImage(imagem, size=imagem.size)  # mantém referência
            foto.configure(image=jan._imagem_evidencia)
        else:
            foto.configure(text="Sem foto de evidência" if not acesso.evidencia
                           else f"Evidência não encontrada:\n{acesso.evidencia}",
                           font=tema.SUBTITULO, text_color=tema.TEXTO_2, height=120)

        dados = ctk.CTkFrame(jan, fg_color=tema.CARTAO, corner_radius=10)
        dados.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 24))
        dados.grid_columnconfigure(1, weight=1)
        cor = tema.COR_RESULTADO.get(acesso.resultado, tema.TEXTO)
        linhas = [
            ("Resultado", tema.ROTULO_RESULTADO.get(acesso.resultado, acesso.resultado), cor),
            ("Data/hora", acesso.data_hora.replace("T", " "), tema.TEXTO),
            ("Pessoa", acesso.nome_detectado or "-", tema.TEXTO),
            ("Nível", f"{acesso.nivel_usuario} - {config.NIVEIS.get(acesso.nivel_usuario, '')}"
             if acesso.nivel_usuario else "-", tema.COR_NIVEL.get(acesso.nivel_usuario, tema.TEXTO)),
            ("Nível exigido", f"{acesso.nivel_exigido} - {acesso.area}", tema.COR_NIVEL.get(acesso.nivel_exigido,
                                                                                            tema.TEXTO)),
            ("Similaridade", f"{acesso.similaridade:.2f}" if acesso.similaridade is not None else "-", tema.TEXTO),
            ("Mensagem", acesso.mensagem or "-", tema.TEXTO),
            ("Evidência", acesso.evidencia or "-", tema.TEXTO_2),
        ]
        for i, (rotulo, valor, cor_valor) in enumerate(linhas):
            ctk.CTkLabel(dados, text=rotulo, font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w").grid(
                row=i, column=0, sticky="w", padx=(16, 12), pady=(8 if i == 0 else 2, 8 if i == len(linhas) - 1 else 2))
            ctk.CTkLabel(dados, text=str(valor), font=tema.CORPO, text_color=cor_valor, anchor="w", justify="left",
                         wraplength=720).grid(row=i, column=1, sticky="ew", padx=(0, 16),
                                              pady=(8 if i == 0 else 2, 8 if i == len(linhas) - 1 else 2))
        botao_secundario(jan, "Fechar", self._fechar_detalhe, width=100).grid(row=2, column=0, sticky="e",
                                                                              padx=24, pady=(0, 24))
        jan.protocol("WM_DELETE_WINDOW", self._fechar_detalhe)
        jan.bind("<Escape>", lambda _e: self._fechar_detalhe())
        jan.transient(self.winfo_toplevel())
        jan.update_idletasks()
        raiz = self.winfo_toplevel()
        x = raiz.winfo_rootx() + max(0, (raiz.winfo_width() - jan.winfo_reqwidth()) // 2)
        y = raiz.winfo_rooty() + max(0, (raiz.winfo_height() - jan.winfo_reqheight()) // 2)
        jan.geometry(f"+{max(0, x)}+{max(0, y)}")
        jan.after(50, jan.lift)
        return jan

    def _fechar_detalhe(self) -> None:
        if self._detalhe is not None:
            try:
                self._detalhe.destroy()
            except Exception:  # noqa: BLE001
                pass
            self._detalhe = None

    @staticmethod
    def _carregar_evidencia(caminho: str | None, maximo: tuple[int, int] = (800, 600)) -> Image.Image | None:
        if not caminho:
            return None
        p = Path(caminho)
        if not p.is_absolute():
            p = config.BASE_DIR / p
        if not p.exists():
            return None
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                im.thumbnail(maximo)
                return im.copy()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return None
