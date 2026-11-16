"""
Tela "Terminal de acesso": o terminal na porta do cofre, em tempo real.

À esquerda, o vídeo da câmera com o HUD desenhado por `TerminalAutenticacao.desenhar()`
(e, opcionalmente, o painel didático com as 5 fases do pipeline). À direita, o painel de
controle: área/nível exigido, prova de vida, estado atual, similaridade, galeria, FPS,
últimos acessos e botões de manutenção. Atalhos de teclado iguais aos da versão CLI:
1/2/3 (área), l (prova de vida), d (painel didático) e r (recarregar galeria).

Divisão de trabalho entre threads
---------------------------------
A thread da câmera roda apenas a parte cara (`pipeline.processar`) e entrega
`(frame, resultado, sequencial)`. A máquina de estados (`passo`), o HUD (`desenhar`) e
o `status()` rodam na thread do Tk, dentro de `atualizar()`, porque `passo()` grava o
log de acessos no SQLite e a conexão do `Banco` só pode ser usada na thread que a criou
(a principal). Cada frame é processado uma única vez (controle pelo sequencial).
"""

from __future__ import annotations

import time
import tkinter as tk
import traceback
from typing import Any

import customtkinter as ctk

from .. import config, hud
from ..autenticacao import Estado, TerminalAutenticacao
from . import tema
from .base import Tela
from .widgets import Cartao, Faixa, Tabela, VideoWidget, botao, botao_secundario, titulo

# A cada quantos segundos o terminal confere se outro processo gravou no banco
# (cadastro feito em outra janela ou pela linha de comando).
INTERVALO_CHECAGEM_BANCO_SEG = 1.0

# Rótulos curtos do seletor de área (nível exigido -> rótulo) e o inverso.
ROTULO_NIVEL = {1: "1 Área comum", 2: "2 Diretores", 3: "3 Cofre do Ministro"}
NIVEL_DO_ROTULO = {v: k for k, v in ROTULO_NIVEL.items()}

AJUDA_CAMERA_MAC = "No macOS, permita o acesso à câmera em Ajustes > Privacidade e Segurança > Câmera."


def _mensagem(video: VideoWidget, texto: str) -> None:
    """Troca a imagem do VideoWidget por um texto.

    Contorna um problema de `VideoWidget.mensagem()`: ela zera a referência da imagem antes de
    tirá-la do `tk.Label` (e `configure(image=None)` é ignorado pelo tkinter), o que deixa o
    rótulo apontando para uma imagem já destruída e estoura `TclError` no próximo redesenho.
    """
    rotulo = getattr(video, "_label", None)
    if rotulo is not None:
        try:
            rotulo.configure(image="")
        except tk.TclError:
            pass
    video.mensagem(texto)


class TelaTerminal(Tela):
    """Terminal de autenticação facial com seleção de área, prova de vida e painel didático."""

    TITULO = "Terminal de acesso"

    def __init__(self, master, app):
        # Estado da tela (definido antes de `construir()` ser chamado pela base).
        self.terminal: TerminalAutenticacao | None = None
        self.nivel: int = 3
        self.liveness: bool = bool(config.LIVENESS_ATIVO)
        self.didatico: bool = False
        self.status: dict[str, Any] = {}       # último snapshot de terminal.status() (+ similaridade, fps, n_rostos)
        self._quer_camera = False
        self._iniciada = False
        self._seq = 0                          # contador incrementado na thread da câmera
        self._seq_visto = -1
        self._estado_anterior: str | None = None
        self._erro_mostrado: str | None = None
        self._funcid_tecla: str | None = None
        self._cache_cfg: dict[int, dict] = {}  # evita reconfigurar widgets com os mesmos valores a 30 Hz
        self._versao_banco: int | None = None  # PRAGMA data_version visto na última checagem
        self._ultima_checagem_banco = 0.0
        super().__init__(master, app)

    # ------------------------------------------------------------------ layout
    def construir(self) -> None:
        self.grid_columnconfigure(0, weight=65, uniform="colunas")
        self.grid_columnconfigure(1, weight=35, uniform="colunas")
        self.grid_rowconfigure(1, weight=1)

        titulo(self, self.TITULO, "Autenticação facial em tempo real com três níveis de permissão").grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(24, 12))

        # ---- esquerda: vídeo + painel didático
        esq = ctk.CTkFrame(self, fg_color="transparent")
        esq.grid(row=1, column=0, sticky="nsew", padx=(24, 6), pady=(0, 24))
        esq.grid_columnconfigure(0, weight=1)
        esq.grid_rowconfigure(0, weight=1)
        self.video = VideoWidget(esq, largura=640, altura=360)
        self.video.grid(row=0, column=0, sticky="nsew")
        self.video_didatico = VideoWidget(esq, largura=640, altura=220)
        self.video_didatico.configure(height=220)
        self.video_didatico.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.video_didatico.grid_remove()
        self._mensagem(self.video_didatico, "Painel didático: as 5 fases do pipeline aparecem aqui")
        # Botão sobreposto ao vídeo, exibido só quando a câmera falha.
        self.botao_tentar = botao(esq, "Tentar novamente", self.tentar_camera, width=180)

        # ---- direita: painel de controle
        painel = ctk.CTkFrame(self, fg_color="transparent")
        painel.grid(row=1, column=1, sticky="nsew", padx=(6, 24), pady=(0, 24))
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_rowconfigure(8, weight=1)

        ctk.CTkLabel(painel, text="Área / nível exigido", font=tema.PEQUENO, text_color=tema.TEXTO_2,
                     anchor="w").grid(row=0, column=0, sticky="ew")
        self.seletor_nivel = ctk.CTkSegmentedButton(
            painel, values=list(ROTULO_NIVEL.values()), command=self._ao_escolher_nivel, font=tema.CORPO,
            fg_color=tema.FUNDO_2, selected_color=tema.ACENTO, selected_hover_color=tema.ACENTO_HOVER,
            unselected_color=tema.CARTAO, unselected_hover_color=tema.BORDA, text_color=tema.TEXTO)
        self.seletor_nivel.set(ROTULO_NIVEL[self.nivel])
        self.seletor_nivel.grid(row=1, column=0, sticky="ew", pady=(2, 12))

        chaves = ctk.CTkFrame(painel, fg_color="transparent")
        chaves.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self._var_liveness = tk.BooleanVar(value=self.liveness)
        self._var_didatico = tk.BooleanVar(value=self.didatico)
        self.chave_liveness = ctk.CTkSwitch(chaves, text="Prova de vida", variable=self._var_liveness,
                                            onvalue=True, offvalue=False, command=self._ao_alternar_liveness,
                                            font=tema.CORPO, progress_color=tema.ACENTO)
        self.chave_liveness.pack(side="left", padx=(0, 20))
        self.chave_didatico = ctk.CTkSwitch(chaves, text="Painel didático", variable=self._var_didatico,
                                            onvalue=True, offvalue=False, command=self._ao_alternar_didatico,
                                            font=tema.CORPO, progress_color=tema.ACENTO)
        self.chave_didatico.pack(side="left")

        self.faixa = Faixa(painel)
        self.faixa.configure(height=112)
        self.faixa.texto.configure(wraplength=320, justify="left", anchor="w")
        self.faixa.bind("<Configure>", lambda e: self.faixa.texto.configure(wraplength=max(120, e.width - 40)))
        self.faixa.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        self._definir_faixa("Câmera desligada", tema.CARTAO, tema.TEXTO_2)

        sim = ctk.CTkFrame(painel, fg_color="transparent")
        sim.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        self.rotulo_similaridade = ctk.CTkLabel(sim, text="", font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w")
        self.rotulo_similaridade.pack(fill="x")
        self.barra_similaridade = ctk.CTkProgressBar(sim, height=12, fg_color=tema.BORDA, progress_color=tema.VERMELHO)
        self.barra_similaridade.set(0.0)
        self.barra_similaridade.pack(fill="x", pady=(4, 0))
        self._definir_similaridade(None)

        cartoes = ctk.CTkFrame(painel, fg_color="transparent")
        cartoes.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        cartoes.grid_columnconfigure((0, 1), weight=1, uniform="cartoes")
        self.cartao_galeria = Cartao(cartoes, "amostras na galeria", "0")
        self.cartao_galeria.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.cartao_fps = Cartao(cartoes, "FPS", "0")
        self.cartao_fps.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.aviso = ctk.CTkLabel(painel, text="", font=tema.CORPO, text_color=tema.AMARELO, anchor="w",
                                  justify="left", wraplength=320)
        self.aviso.grid(row=6, column=0, sticky="ew", pady=(0, 12))
        self.aviso.grid_remove()

        ctk.CTkLabel(painel, text="Últimos acessos", font=tema.PEQUENO, text_color=tema.TEXTO_2,
                     anchor="w").grid(row=7, column=0, sticky="ew")
        self.tabela = Tabela(painel, [("hora", "Hora", 64), ("nome", "Nome", 100), ("resultado", "Resultado", 130),
                                      ("nivel", "Nível", 44), ("sim", "Sim.", 44)], altura=8)
        self.tabela.grid(row=8, column=0, sticky="nsew", pady=(2, 12))

        botoes = ctk.CTkFrame(painel, fg_color="transparent")
        botoes.grid(row=9, column=0, sticky="ew")
        botoes.grid_columnconfigure((0, 1), weight=1, uniform="botoes")
        self.botao_recarregar = botao_secundario(botoes, "Recarregar galeria", self.recarregar_galeria)
        self.botao_recarregar.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.botao_camera = botao_secundario(botoes, "Tentar câmera novamente", self.tentar_camera)
        self.botao_camera.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    # ------------------------------------------------------------------ ciclo de vida
    def ao_mostrar(self) -> None:
        self._quer_camera = True
        self._iniciada = False
        self._seq_visto = -1
        self._estado_anterior = None
        self._erro_mostrado = None
        self.app.camera.erro = None          # parar() não limpa o erro anterior; só iniciar() limpa
        self.botao_tentar.place_forget()
        if self.terminal is not None:
            self.terminal.definir_nivel(self.nivel)      # volta a AGUARDANDO ao reabrir a tela
        self._mensagem(self.video, "Carregando modelos..." if not self.app.pipeline_pronto() else "Abrindo a câmera...")
        self._definir_faixa("Aguardando a câmera...", tema.CARTAO, tema.TEXTO_2)
        self.atualizar_acessos()
        self.verificar_usuarios()
        if self._funcid_tecla is None:
            self._funcid_tecla = self.app.bind("<KeyPress>", self._tecla, add="+")

    def ao_esconder(self) -> None:
        self._quer_camera = False
        self._iniciada = False
        try:
            self.app.camera.parar()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        if self._funcid_tecla is not None:
            try:
                self.app.unbind("<KeyPress>", self._funcid_tecla)
            except tk.TclError:
                pass
            self._funcid_tecla = None
        self._mensagem(self.video, "Câmera desligada")

    def atualizar(self) -> None:
        if not self._quer_camera:
            return
        cam = self.app.camera
        if cam.erro and not cam.ativo:               # a thread da câmera morreu (sem permissão, sem dispositivo...)
            self._mostrar_erro_camera(cam.erro)
            return
        if not self._iniciada:
            if not self.app.pipeline_pronto():
                erro = getattr(self.app, "_erro_pipeline", None)
                if erro:
                    self._mostrar_erro_camera(erro, retentar=False)
                return
            self._iniciar_camera()
            return
        self._checar_banco()
        pacote = cam.ultimo()
        if not isinstance(pacote, tuple) or len(pacote) != 3:
            return
        frame, res, seq = pacote
        if seq == self._seq_visto:
            return
        self._seq_visto = seq
        if self._erro_mostrado is not None:          # a câmera voltou
            self._erro_mostrado = None
            self.botao_tentar.place_forget()
        term = self.terminal
        try:
            term.passo(frame, res.principal, len(res.rostos))
            tela = term.desenhar(frame, res, cam.fps)
            st = term.status()
            ident = term.identificacao_atual(res.principal)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._definir_faixa(f"Erro no processamento: {e}", tema.VERMELHO, tema.TEXTO)
            return
        st["similaridade"] = float(ident.similaridade) if ident is not None else None
        st["fps"] = float(cam.fps)
        st["n_rostos"] = len(res.rostos)
        self.status = st
        self.video.mostrar(tela)
        if self.didatico:
            try:
                self.video_didatico.mostrar(hud.mosaico(res.etapas_didaticas(), lado=160, colunas=5))
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        if cam.erro:                                 # erro de processamento que não derrubou a câmera
            self._definir_faixa(cam.erro, tema.VERMELHO, tema.TEXTO)
        else:
            self._atualizar_painel(st)
        if st["estado"] == Estado.RESULTADO.value and self._estado_anterior != Estado.RESULTADO.value:
            self.atualizar_acessos()                 # a decisão (e um eventual bloqueio) acabou de ser registrada
        self._estado_anterior = st["estado"]

    # ------------------------------------------------------------------ câmera
    @staticmethod
    def _mensagem(video: VideoWidget, texto: str) -> None:
        _mensagem(video, texto)

    def _iniciar_camera(self) -> None:
        if self.terminal is None:
            self.terminal = TerminalAutenticacao(self.app.banco, self.app.pipeline, nivel_exigido=self.nivel,
                                                 liveness=self.liveness, didatico=self.didatico)
            self.verificar_usuarios()
        self.app.camera.definir_processador(self._processar)
        self.app.camera.iniciar()
        self._iniciada = True
        self._mensagem(self.video, "Abrindo a câmera...")

    def _processar(self, frame):
        """Roda NA THREAD DA CÂMERA: só a parte cara (detecção + embedding). Nada de Tk nem de banco aqui."""
        res = self.app.pipeline.processar(frame)
        self._seq += 1
        return (frame, res, self._seq)

    def tentar_camera(self) -> None:
        """Reabre a câmera (botão "Tentar novamente" / "Tentar câmera novamente")."""
        if not self._quer_camera:
            return
        try:
            self.app.camera.parar()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        self.app.camera.erro = None          # senão `atualizar()` continua no ramo de erro e nunca reabre
        self._iniciada = False
        self._seq_visto = -1
        self._erro_mostrado = None
        self.botao_tentar.place_forget()
        self._mensagem(self.video, "Abrindo a câmera...")
        self._definir_faixa("Tentando abrir a câmera...", tema.CARTAO, tema.TEXTO_2)
        self.app.status.definir("Reabrindo a câmera...", None)

    def _mostrar_erro_camera(self, erro: str, retentar: bool = True) -> None:
        if erro == self._erro_mostrado:
            return
        self._erro_mostrado = erro
        texto = f"Câmera indisponível\n\n{erro}"
        if retentar:
            texto += f"\n\n{AJUDA_CAMERA_MAC}"
            self.botao_tentar.place(in_=self.video, relx=0.5, rely=0.8, anchor="center")
        self._mensagem(self.video, texto)
        self._definir_faixa("Câmera indisponível" if retentar else "Modelos não carregados", tema.VERMELHO, tema.TEXTO)
        self._definir_similaridade(None)
        self.cartao_fps.definir("0")

    # ------------------------------------------------------------------ controles
    def definir_nivel(self, nivel: int) -> None:
        """Muda a área/nível exigido (seletor, atalhos 1/2/3)."""
        if nivel not in config.AREAS:
            return
        self.nivel = int(nivel)
        if self.seletor_nivel.get() != ROTULO_NIVEL[self.nivel]:
            self.seletor_nivel.set(ROTULO_NIVEL[self.nivel])
        if self.terminal is not None:
            self.terminal.definir_nivel(self.nivel)
        self.app.status.definir(f"Área exigida: {config.AREAS[self.nivel]} (nível {self.nivel})", None)

    def alternar_liveness(self, ativo: bool | None = None) -> None:
        """Liga/desliga a prova de vida (switch, atalho l). Sem argumento, inverte."""
        self.liveness = (not self.liveness) if ativo is None else bool(ativo)
        self._var_liveness.set(self.liveness)
        if self.terminal is not None:
            self.terminal.liveness_ativo = self.liveness
        self.app.status.definir(f"Prova de vida {'ligada' if self.liveness else 'desligada'}", None)

    def alternar_didatico(self, ativo: bool | None = None) -> None:
        """Mostra/esconde o painel didático com as 5 fases (switch, atalho d). Sem argumento, inverte."""
        self.didatico = (not self.didatico) if ativo is None else bool(ativo)
        self._var_didatico.set(self.didatico)
        if self.terminal is not None:
            self.terminal.didatico = self.didatico
        if self.didatico:
            self.video_didatico.grid()
        else:
            self.video_didatico.grid_remove()
            self._mensagem(self.video_didatico, "Painel didático: as 5 fases do pipeline aparecem aqui")

    def _checar_banco(self) -> None:
        """Recarrega a galeria quando outro processo grava no banco. Sem isso, um cadastro feito
        em outra janela ou pela linha de comando só valeria depois de "Recarregar galeria"."""
        agora = time.monotonic()
        if agora - self._ultima_checagem_banco < INTERVALO_CHECAGEM_BANCO_SEG:
            return
        self._ultima_checagem_banco = agora
        try:
            versao = self.app.banco.versao_dados()
        except Exception:  # noqa: BLE001
            return
        anterior, self._versao_banco = self._versao_banco, versao
        if anterior is not None and versao != anterior:
            self.recarregar_galeria()

    def recarregar_galeria(self) -> None:
        """Relê usuários ativos e amostras do banco (botão, atalho r)."""
        try:
            if self.terminal is not None:
                self.terminal.reconhecedor.recarregar()
                total = self.terminal.reconhecedor.total_amostras
            else:
                total = self.app.banco.estatisticas()["amostras"]
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._definir_faixa(f"Falha ao recarregar a galeria: {e}", tema.VERMELHO, tema.TEXTO)
            return
        self.cartao_galeria.definir(total)
        self.verificar_usuarios()
        self.atualizar_acessos()
        self.app.status.definir(f"Galeria recarregada: {total} amostras", None)

    def verificar_usuarios(self) -> None:
        """Avisa em amarelo quando não há usuário ativo (ou nenhum tem amostra biométrica)."""
        try:
            ativos = self.app.banco.listar_usuarios(apenas_ativos=True)
            if not ativos:
                texto = ("Nenhum usuário ativo cadastrado: todo rosto será negado. "
                         "Cadastre alguém em \"Cadastro biométrico\".")
            elif self.terminal is not None and self.terminal.reconhecedor.total_amostras == 0:
                texto = "Os usuários ativos não têm amostras biométricas: refaça o cadastro."
            else:
                texto = ""
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            texto = f"Não foi possível consultar os usuários: {e}"
        if texto:
            self.aviso.configure(text=texto)
            self.aviso.grid()
        else:
            self.aviso.grid_remove()

    def atualizar_acessos(self) -> None:
        """Recarrega a lista dos últimos 8 acessos registrados."""
        try:
            acessos = self.app.banco.listar_acessos(8)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._definir_faixa(f"Falha ao ler o log de acessos: {e}", tema.VERMELHO, tema.TEXTO)
            return
        self.tabela.limpar()
        for a in acessos:
            hora = a.data_hora[11:19] if len(a.data_hora) >= 19 else a.data_hora
            if a.resultado == "CONCEDIDO":
                tag = "ok"
            elif a.resultado == "NEGADO_NIVEL":
                tag = "aviso"
            else:
                tag = "neg"
            self.tabela.adicionar(str(a.id), (
                hora, a.nome_detectado or "-", tema.ROTULO_RESULTADO.get(a.resultado, a.resultado),
                f"N{a.nivel_exigido}", f"{a.similaridade:.2f}" if a.similaridade is not None else "-"), tag)

    # ------------------------------------------------------------------ eventos
    def _ao_escolher_nivel(self, rotulo: str) -> None:
        self.definir_nivel(NIVEL_DO_ROTULO.get(rotulo, self.nivel))

    def _ao_alternar_liveness(self) -> None:
        self.alternar_liveness(bool(self._var_liveness.get()))

    def _ao_alternar_didatico(self) -> None:
        self.alternar_didatico(bool(self._var_didatico.get()))

    def _tecla(self, evento) -> None:
        """Atalhos: 1/2/3 área, l prova de vida, d painel didático, r recarregar galeria."""
        if not self._quer_camera or isinstance(getattr(evento, "widget", None), (tk.Entry, tk.Text)):
            return
        ch = (getattr(evento, "char", "") or "").lower()
        if ch in ("1", "2", "3"):
            self.definir_nivel(int(ch))
        elif ch == "l":
            self.alternar_liveness()
        elif ch == "d":
            self.alternar_didatico()
        elif ch == "r":
            self.recarregar_galeria()

    # ------------------------------------------------------------------ painel
    def _atualizar_painel(self, st: dict) -> None:
        estado, d = st["estado"], st.get("decisao")
        if estado == Estado.RESULTADO.value and d:
            cor = tema.COR_RESULTADO.get(d["resultado"], tema.VERMELHO)
            linhas = [tema.ROTULO_RESULTADO.get(d["resultado"], d["resultado"])]
            if d.get("nome"):
                sim = d.get("similaridade")
                linhas.append(f"{d['nome']}" + (f"  ·  similaridade {sim:.2f}" if sim is not None else ""))
            if d.get("mensagem"):
                linhas.append(d["mensagem"])
            self._definir_faixa("\n".join(linhas), cor, tema.FUNDO if cor in (tema.VERDE, tema.LARANJA) else tema.TEXTO)
        elif estado == Estado.BLOQUEADO.value:
            self._definir_faixa(f"TERMINAL BLOQUEADO\nAguarde {st['bloqueado_restante']:.0f} s "
                                f"({config.MAX_TENTATIVAS_FALHAS} negações seguidas)", tema.VERMELHO, tema.TEXTO)
        elif estado == Estado.LIVENESS.value:
            self._definir_faixa(f"PROVA DE VIDA\n{st['liveness_instrucao']}\n{st['liveness_restante']:.0f} s restantes",
                                tema.LARANJA, tema.FUNDO)
        elif estado == Estado.CONFIRMANDO.value:
            self._definir_faixa(f"CONFIRMANDO {int(st['progresso_confirmacao'] * 100)}%\n"
                                f"Mantenha o rosto parado diante da câmera", tema.AZUL, tema.TEXTO)
        else:
            extra = "\nMais de uma pessoa diante do terminal" if st.get("n_rostos", 0) > 1 else \
                ("\n" + st["orientacao"]) if st.get("orientacao") else "\nPosicione-se de frente para a câmera"
            self._definir_faixa("AGUARDANDO" + extra, tema.CARTAO, tema.TEXTO_2)
        self._definir_similaridade(st.get("similaridade"))
        self._configurar(self.cartao_galeria.valor, text=str(st.get("galeria", 0)))
        self._configurar(self.cartao_fps.valor, text=f"{st.get('fps', 0.0):.0f}")

    def _definir_faixa(self, texto: str, cor: str, cor_texto: str) -> None:
        chave = id(self.faixa)
        valores = {"texto": texto, "cor": cor, "cor_texto": cor_texto}
        if self._cache_cfg.get(chave) == valores:
            return
        self._cache_cfg[chave] = valores
        self.faixa.definir(texto, cor, cor_texto)

    def _definir_similaridade(self, sim: float | None) -> None:
        limiar = config.LIMIAR_COSSENO
        if sim is None:
            texto, valor, cor = f"Similaridade  -   ·   limiar {limiar:.2f}", 0.0, tema.BORDA
        else:
            texto = f"Similaridade {sim:.2f}   ·   limiar {limiar:.2f}" + ("  (acima)" if sim >= limiar else "  (abaixo)")
            valor, cor = max(0.0, min(1.0, sim)), (tema.VERDE if sim >= limiar else tema.VERMELHO)
        self._configurar(self.rotulo_similaridade, text=texto)
        chave = id(self.barra_similaridade)
        valores = {"valor": round(valor, 3), "cor": cor}
        if self._cache_cfg.get(chave) != valores:
            self._cache_cfg[chave] = valores
            self.barra_similaridade.configure(progress_color=cor)
            self.barra_similaridade.set(valor)

    def _configurar(self, widget, **kw) -> None:
        chave = id(widget)
        if self._cache_cfg.get(chave) == kw:
            return
        self._cache_cfg[chave] = kw
        widget.configure(**kw)
