"""Tela de cadastro biométrico: formulário do usuário, captura pela câmera (SessaoCadastro)
ou importação de fotos (cadastrar_de_imagens).

Divisão de threads:
- a thread da câmera só roda `pipeline.processar(frame)` e devolve `(frame, resultado)`;
- `SessaoCadastro.passo()` e `desenhar()` rodam em `atualizar()` (thread do Tk), porque a
  sessão grava amostras no banco e a conexão SQLite só aceita a thread que a criou;
- o cadastro por fotos roda em uma `threading.Thread` com uma conexão própria ao banco e
  entrega o resultado por uma flag lida em `atualizar()`.
"""

from __future__ import annotations

import threading
import traceback
from pathlib import Path
from tkinter import StringVar, filedialog

import customtkinter as ctk
import cv2

from .. import config, hud
from ..banco import Banco
from ..cadastro import DadosCadastro, SessaoCadastro, cadastrar_de_imagens
from . import tema
from .base import Tela
from .widgets import Faixa, VideoWidget, botao, botao_secundario, titulo

TAM_MINIATURA = 72
MAX_AVISOS_EXIBIDOS = 6

# Cores BGR do HUD (cofre/hud.py) -> hex do tema
_COR_HUD = {
    hud.VERDE: tema.VERDE,
    hud.VERMELHO: tema.VERMELHO,
    hud.AMARELO: tema.AMARELO,
    hud.LARANJA: tema.LARANJA,
    hud.AZUL: tema.AZUL,
    hud.BRANCO: tema.TEXTO,
    hud.CINZA: tema.TEXTO_2,
}


def cor_hud_para_hex(bgr) -> str:
    """Converte uma cor BGR do HUD em hex; cores conhecidas usam a paleta do tema."""
    try:
        b, g, r = (int(v) for v in bgr[:3])
    except Exception:  # noqa: BLE001
        return tema.TEXTO
    return _COR_HUD.get((b, g, r), f"#{r:02x}{g:02x}{b:02x}")


def miniatura_quadrada(recorte, lado: int = TAM_MINIATURA) -> ctk.CTkImage:
    """Recorta o centro do rosto em um quadrado e gera um CTkImage lado x lado."""
    h, w = recorte.shape[:2]
    m = min(h, w)
    y0, x0 = (h - m) // 2, (w - m) // 2
    quadrado = recorte[y0:y0 + m, x0:x0 + m]
    red = cv2.resize(quadrado, (lado, lado), interpolation=cv2.INTER_AREA)
    return ctk.CTkImage(tema.bgr_para_pil(red), size=(lado, lado))


def _resumir_aviso(aviso: str) -> str:
    """'/pasta/longa/foto.jpg: nenhum rosto' -> 'foto.jpg: nenhum rosto'."""
    caminho, sep, resto = aviso.partition(": ")
    if sep and Path(caminho).suffix:
        return f"{Path(caminho).name}: {resto}"
    return aviso


class TelaCadastro(Tela):
    TITULO = "Cadastro biométrico"

    # ------------------------------------------------------------------ construção
    def construir(self) -> None:
        self.sessao: SessaoCadastro | None = None
        self._dados_pendentes: DadosCadastro | None = None   # Iniciar clicado, esperando o pipeline
        self._quer_camera = False       # a tela quer a câmera ligada
        self._camera_pedida = False     # já chamou camera.iniciar() para esta sessão
        self._id_ultimo_res: int | None = None
        self._miniaturas_widgets: list[ctk.CTkLabel] = []
        self._miniaturas_imgs: list[ctk.CTkImage] = []
        self._thread_fotos: threading.Thread | None = None
        self._resultado_fotos: tuple | None = None            # escrito pela thread, lido em atualizar()
        self._opcoes_nivel = [f"{n} - {desc}" for n, desc in sorted(config.NIVEIS.items())]

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=380)
        self.grid_rowconfigure(1, weight=1)

        titulo(self, self.TITULO, "Cadastre um usuário autorizado: preencha os dados e capture 12 amostras "
               "do rosto pela câmera, ou importe fotos.").grid(row=0, column=0, columnspan=2, sticky="ew",
                                                              padx=24, pady=(24, 12))
        self._construir_esquerda()
        self._construir_formulario()

    def _construir_esquerda(self) -> None:
        esq = ctk.CTkFrame(self, fg_color="transparent")
        esq.grid(row=1, column=0, sticky="nsew", padx=(24, 12), pady=(0, 24))
        esq.grid_columnconfigure(0, weight=1)
        esq.grid_rowconfigure(0, weight=1)

        self.video = VideoWidget(esq)
        self.video.grid(row=0, column=0, sticky="nsew")

        self.botao_tentar = botao_secundario(esq, "Tentar novamente", self.tentar_novamente, width=180)
        self.botao_tentar.grid(row=1, column=0, pady=(12, 0))
        self.botao_tentar.grid_remove()

        linha = ctk.CTkFrame(esq, fg_color="transparent")
        linha.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        linha.grid_columnconfigure(1, weight=1)
        self.rotulo_amostras = ctk.CTkLabel(linha, text="", font=tema.CORPO, text_color=tema.TEXTO_2, width=130,
                                            anchor="w")
        self.rotulo_amostras.grid(row=0, column=0, sticky="w")
        self.barra = ctk.CTkProgressBar(linha, progress_color=tema.ACENTO, fg_color=tema.CARTAO, height=12)
        self.barra.grid(row=0, column=1, sticky="ew", padx=(12, 0))
        self.barra.set(0)

        self.faixa_instrucao = Faixa(esq)
        self.faixa_instrucao.texto.configure(wraplength=560)
        self.faixa_instrucao.grid(row=3, column=0, sticky="ew", pady=(12, 0))

        self.faixa_miniaturas = ctk.CTkScrollableFrame(esq, orientation="horizontal", fg_color=tema.CARTAO,
                                                       corner_radius=10, height=TAM_MINIATURA + 16)
        self.faixa_miniaturas.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.rotulo_miniaturas = ctk.CTkLabel(self.faixa_miniaturas, text="As amostras capturadas aparecem aqui",
                                              font=tema.PEQUENO, text_color=tema.TEXTO_2)
        self.rotulo_miniaturas.pack(side="left", padx=12, pady=4)
        self._definir_amostras(0, config.AMOSTRAS_POR_CADASTRO)

    def _construir_formulario(self) -> None:
        form = ctk.CTkFrame(self, fg_color=tema.CARTAO, corner_radius=10)
        form.grid(row=1, column=1, sticky="nsew", padx=(0, 24), pady=(0, 24))
        self.form = form

        ctk.CTkLabel(form, text="Dados do usuário", font=tema.SUBTITULO, text_color=tema.TEXTO, anchor="w").pack(
            fill="x", padx=16, pady=(16, 8))

        self.entrada_nome = self._campo(form, "Nome completo *", "Ex.: Maria da Silva")
        self.entrada_matricula = self._campo(form, "Matrícula *", "Ex.: 2024001")
        self.entrada_cargo = self._campo(form, "Cargo / divisão", "Ex.: Diretor de Fiscalização")

        ctk.CTkLabel(form, text="Nível de acesso", font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w").pack(
            fill="x", padx=16, pady=(8, 2))
        self.var_nivel = StringVar(value=self._opcoes_nivel[0])
        self.menu_nivel = ctk.CTkOptionMenu(form, values=self._opcoes_nivel, variable=self.var_nivel, font=tema.CORPO,
                                            fg_color=tema.FUNDO_2, button_color=tema.BORDA,
                                            button_hover_color=tema.ACENTO_HOVER, dropdown_fg_color=tema.FUNDO_2,
                                            text_color=tema.TEXTO, command=self._ao_escolher_nivel)
        self.menu_nivel.pack(fill="x", padx=16)
        self.rotulo_area = ctk.CTkLabel(form, text="", font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w",
                                        wraplength=330, justify="left")
        self.rotulo_area.pack(fill="x", padx=16, pady=(4, 0))
        self._ao_escolher_nivel(self.var_nivel.get())

        self.rotulo_erro = ctk.CTkLabel(form, text="", font=tema.CORPO, text_color=tema.VERMELHO, anchor="w",
                                        wraplength=330, justify="left")
        self.rotulo_erro.pack(fill="x", padx=16, pady=(12, 0))

        self.botao_iniciar = botao(form, "Iniciar captura pela câmera", self.iniciar_captura, height=40)
        self.botao_iniciar.pack(fill="x", padx=16, pady=(12, 0))
        self.botao_fotos = botao_secundario(form, "Cadastrar por fotos...", self._escolher_fotos, height=40)
        self.botao_fotos.pack(fill="x", padx=16, pady=(8, 0))

        # Botões da captura (aparecem só durante a sessão)
        self.quadro_captura = ctk.CTkFrame(form, fg_color="transparent")
        self.quadro_captura.grid_columnconfigure((0, 1), weight=1)
        self.botao_cancelar = botao(self.quadro_captura, "Cancelar", self.cancelar, cor=tema.VERMELHO, height=40)
        self.botao_cancelar.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.botao_concluir = botao(self.quadro_captura, "Concluir", self.concluir, cor=tema.VERDE, height=40)
        self.botao_concluir.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # Mensagem de resultado (sucesso/aviso) no rodapé do formulário
        self.rotulo_msg = ctk.CTkLabel(form, text="", font=tema.CORPO, text_color=tema.TEXTO, anchor="w",
                                       justify="left", wraplength=320, corner_radius=8, fg_color="transparent")
        self.rotulo_msg.pack(side="bottom", fill="x", padx=16, pady=(12, 16))

    def _campo(self, master, rotulo: str, dica: str) -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=rotulo, font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w").pack(
            fill="x", padx=16, pady=(8, 2))
        e = ctk.CTkEntry(master, placeholder_text=dica, font=tema.CORPO, fg_color=tema.FUNDO_2,
                         border_color=tema.BORDA, text_color=tema.TEXTO, height=34)
        e.pack(fill="x", padx=16)
        return e

    # ------------------------------------------------------------------ ciclo de vida
    def ao_mostrar(self) -> None:
        if self.capturando:
            # voltou para a tela no meio de uma captura: religa a câmera
            self._quer_camera = True

    def ao_esconder(self) -> None:
        self._quer_camera = False
        self._camera_pedida = False
        self.app.camera.parar()

    def atualizar(self) -> None:
        try:
            self._tratar_resultado_fotos()
            self._iniciar_sessao_se_pronto()
            self._ligar_camera_se_preciso()
            self._atualizar_captura()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            self._mostrar_erro("Erro inesperado na tela de cadastro (veja o terminal).")

    def _video_mensagem(self, texto: str) -> None:
        """Troca o vídeo por uma mensagem. Antes solta a imagem no Label do Tk: `VideoWidget.mensagem`
        descarta o CTkImage, e o Tk ainda apontaria para a foto destruída ("image doesn't exist")."""
        try:
            self.video._label.configure(image="")  # noqa: SLF001 (interno do CTkLabel)
        except Exception:  # noqa: BLE001
            pass
        self.video.mensagem(texto)

    # ------------------------------------------------------------------ propriedades
    @property
    def capturando(self) -> bool:
        """True entre o clique em Iniciar e o Concluir/Cancelar."""
        return self._dados_pendentes is not None or (self.sessao is not None and not self.sessao.encerrada)

    @property
    def importando_fotos(self) -> bool:
        return self._thread_fotos is not None and self._thread_fotos.is_alive()

    # ------------------------------------------------------------------ formulário
    def preencher(self, nome: str = "", matricula: str = "", cargo: str = "", nivel: int = 1) -> None:
        """Preenche o formulário (usado por testes e por outras telas)."""
        for entrada, valor in ((self.entrada_nome, nome), (self.entrada_matricula, matricula),
                               (self.entrada_cargo, cargo)):
            entrada.delete(0, "end")
            if valor:
                entrada.insert(0, valor)
        for opcao in self._opcoes_nivel:
            if opcao.startswith(f"{nivel} -"):
                self.var_nivel.set(opcao)
        self._ao_escolher_nivel(self.var_nivel.get())

    def limpar_formulario(self) -> None:
        self.preencher()
        self.rotulo_erro.configure(text="")

    def nivel_escolhido(self) -> int:
        try:
            return int(self.var_nivel.get().split(" -")[0])
        except (ValueError, AttributeError):
            return 1

    def _ao_escolher_nivel(self, valor: str) -> None:
        n = self.nivel_escolhido()
        self.rotulo_area.configure(text=f"Libera: {config.AREAS.get(n, '?')}", text_color=tema.COR_NIVEL.get(n, tema.TEXTO_2))

    def ler_formulario(self) -> DadosCadastro | None:
        """Valida e devolve os dados; em erro escreve a mensagem vermelha e devolve None."""
        nome = self.entrada_nome.get().strip()
        matricula = self.entrada_matricula.get().strip()
        cargo = self.entrada_cargo.get().strip()
        nivel = self.nivel_escolhido()
        if not nome:
            return self._mostrar_erro("Informe o nome do usuário.")
        if not matricula:
            return self._mostrar_erro("Informe a matrícula.")
        if nivel not in config.NIVEIS:
            return self._mostrar_erro("Escolha um nível de acesso válido.")
        try:
            existente = self.app.banco.obter_por_matricula(matricula)
        except Exception as e:  # noqa: BLE001
            return self._mostrar_erro(f"Não foi possível consultar o banco: {e}")
        if existente is not None:
            return self._mostrar_erro(f"Matrícula {matricula} já cadastrada para {existente.nome}.")
        self.rotulo_erro.configure(text="")
        return DadosCadastro(nome, matricula, cargo, nivel)

    def _definir_formulario(self, habilitado: bool) -> None:
        estado = "normal" if habilitado else "disabled"
        for w in (self.entrada_nome, self.entrada_matricula, self.entrada_cargo, self.menu_nivel,
                  self.botao_iniciar, self.botao_fotos):
            w.configure(state=estado)

    def _mostrar_erro(self, texto: str) -> None:
        self.rotulo_erro.configure(text=texto)
        return None

    def _mostrar_msg(self, texto: str, cor: str = tema.TEXTO, fundo: str = "transparent") -> None:
        self.rotulo_msg.configure(text=texto, text_color=cor, fg_color=fundo)

    # ------------------------------------------------------------------ captura pela câmera
    def iniciar_captura(self) -> bool:
        """Valida o formulário e agenda o início da sessão (a câmera liga quando o pipeline estiver pronto)."""
        if self.capturando or self.importando_fotos:
            return False
        dados = self.ler_formulario()
        if dados is None:
            return False
        self._dados_pendentes = dados
        self._definir_formulario(False)
        self._mostrar_msg("")
        self._limpar_miniaturas()
        self._definir_amostras(0, config.AMOSTRAS_POR_CADASTRO)
        self.faixa_instrucao.definir("Preparando a captura...", tema.CARTAO, tema.TEXTO_2)
        self._video_mensagem("Carregando modelos..." if not self.app.pipeline_pronto() else "Ligando a câmera...")
        self.botao_concluir.configure(state="disabled")
        self.quadro_captura.pack(fill="x", padx=16, pady=(12, 0))
        self.app.status.definir("Cadastro: preparando captura", None)
        return True

    def _iniciar_sessao_se_pronto(self) -> None:
        if self._dados_pendentes is None or not self.app.pipeline_pronto():
            return
        dados, self._dados_pendentes = self._dados_pendentes, None
        try:
            self.sessao = SessaoCadastro(self.app.banco, self.app.pipeline, dados)
        except Exception as e:  # noqa: BLE001
            self.sessao = None
            self._encerrar_captura()
            self._mostrar_erro(f"Não foi possível iniciar o cadastro: {e}")
            return
        self._id_ultimo_res = None
        self._definir_amostras(0, self.sessao.amostras)
        self.app.camera.definir_processador(self._criar_processador(self.app.pipeline))
        self._quer_camera = True

    @staticmethod
    def _criar_processador(pipeline):
        """Roda na thread da câmera: só o pipeline (sem banco, sem widgets)."""
        def processador(frame):
            res = pipeline.processar(frame, extrair_embedding=False)
            return frame, res
        return processador

    def _ligar_camera_se_preciso(self) -> None:
        if not self._quer_camera or self._camera_pedida or self.sessao is None:
            return
        cam = self.app.camera
        cam.definir_processador(self._criar_processador(self.app.pipeline))
        cam.iniciar()
        self._camera_pedida = True
        self._video_mensagem("Ligando a câmera...")

    def tentar_novamente(self) -> None:
        """Religa a câmera depois de uma falha (permissão negada, dispositivo ocupado...)."""
        self.botao_tentar.grid_remove()
        self.app.camera.parar()
        self.app.camera.erro = None
        self._camera_pedida = False
        self._quer_camera = self.sessao is not None and not self.sessao.encerrada
        self.faixa_instrucao.definir("Religando a câmera...", tema.CARTAO, tema.TEXTO_2)
        self._video_mensagem("Ligando a câmera...")

    def _atualizar_captura(self) -> None:
        sessao = self.sessao
        if sessao is None or sessao.encerrada:
            return
        cam = self.app.camera
        if cam.erro:
            self._video_mensagem(f"Câmera indisponível\n{cam.erro}\n\nNo macOS, autorize a câmera em Ajustes do "
                                f"Sistema > Privacidade e Segurança > Câmera.")
            self.botao_tentar.grid()
            self.faixa_instrucao.definir("Câmera indisponível", tema.CARTAO, tema.VERMELHO)
            return
        saida = cam.ultimo()
        if not isinstance(saida, tuple) or len(saida) != 2:
            return
        frame, res = saida
        if id(res) == self._id_ultimo_res:
            return
        self._id_ultimo_res = id(res)
        sessao.passo(frame, res)
        tela = sessao.desenhar(frame, res)
        self.video.mostrar(tela)
        cor = cor_hud_para_hex(sessao.cor)
        self.faixa_instrucao.definir(sessao.status, tema.CARTAO, cor)
        self._definir_amostras(sessao.capturadas, sessao.amostras)
        self._sincronizar_miniaturas(sessao)
        if sessao.concluida:
            self.botao_concluir.configure(state="normal")
            self.app.status.definir("Cadastro: amostras completas, clique em Concluir",
                                    f"câmera {cam.fps:.0f} fps")
        else:
            self.app.status.definir(f"Cadastro: {sessao.dados.nome} ({sessao.capturadas}/{sessao.amostras})",
                                    f"câmera {cam.fps:.0f} fps")

    def cancelar(self) -> None:
        """Desfaz o cadastro em andamento (usuário e amostras) e desliga a câmera."""
        sessao, self.sessao = self.sessao, None
        self._dados_pendentes = None
        if sessao is not None and not sessao.encerrada:
            try:
                sessao.cancelar()
            except Exception as e:  # noqa: BLE001
                self._mostrar_erro(f"Falha ao desfazer o cadastro: {e}")
        self._encerrar_captura()
        self._limpar_miniaturas()
        self._definir_amostras(0, config.AMOSTRAS_POR_CADASTRO)
        self.faixa_instrucao.definir("Cadastro cancelado", tema.CARTAO, tema.TEXTO_2)
        self.app.status.definir("Cadastro cancelado", "")

    def concluir(self):
        """Fecha a sessão, grava o usuário e avisa o terminal para recarregar a galeria."""
        sessao = self.sessao
        if sessao is None:
            return None
        self.sessao = None
        try:
            usuario = sessao.concluir()
        except Exception as e:  # noqa: BLE001
            usuario = None
            self._mostrar_erro(f"Falha ao concluir o cadastro: {e}")
        self._encerrar_captura()
        if usuario is None:
            self.faixa_instrucao.definir("Nenhuma amostra capturada: cadastro desfeito", tema.CARTAO, tema.LARANJA)
            self.app.status.definir("Cadastro desfeito (sem amostras)", "")
            return None
        self._anunciar_sucesso(usuario, sessao.capturadas)
        self.faixa_instrucao.definir(f"{usuario.nome} cadastrado com {sessao.capturadas} amostras",
                                     tema.CARTAO, tema.VERDE)
        return usuario

    def _encerrar_captura(self) -> None:
        self._quer_camera = False
        self._camera_pedida = False
        self.app.camera.parar()
        self.app.camera.definir_processador(None)
        self.botao_tentar.grid_remove()
        self.quadro_captura.pack_forget()
        self._definir_formulario(True)
        self._video_mensagem("Câmera desligada")
        self._id_ultimo_res = None

    def _anunciar_sucesso(self, usuario, n_amostras: int, avisos: list[str] | None = None) -> None:
        texto = (f"Cadastro concluído\n{usuario.nome}  (matrícula {usuario.matricula})\n"
                 f"Nível {usuario.nivel} - {usuario.nivel_descricao}\n{n_amostras} amostra(s) gravada(s)")
        if avisos:
            mostrados = avisos[:MAX_AVISOS_EXIBIDOS]
            if len(avisos) > MAX_AVISOS_EXIBIDOS:
                mostrados.append(f"... e mais {len(avisos) - MAX_AVISOS_EXIBIDOS} aviso(s)")
            texto += "\n\nAvisos:\n" + "\n".join(f"- {_resumir_aviso(a)}" for a in mostrados)
        self._mostrar_msg(texto, tema.FUNDO, tema.VERDE)
        self.limpar_formulario()
        self.app.status.definir(f"Cadastrado: {usuario.nome} (nível {usuario.nivel})", "")
        self._avisar_terminal()

    def _avisar_terminal(self) -> None:
        tela = self.app.tela("tela_terminal")
        recarregar = getattr(tela, "recarregar_galeria", None)
        if callable(recarregar):
            try:
                recarregar()
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    # ------------------------------------------------------------------ amostras / miniaturas
    def _definir_amostras(self, n: int, total: int) -> None:
        self.rotulo_amostras.configure(text=f"Amostras {n}/{total}")
        self.barra.set(0 if total <= 0 else min(1.0, n / total))

    def _limpar_miniaturas(self) -> None:
        for w in self._miniaturas_widgets:
            w.destroy()
        self._miniaturas_widgets.clear()
        self._miniaturas_imgs.clear()
        self.rotulo_miniaturas.pack(side="left", padx=12, pady=4)

    def _sincronizar_miniaturas(self, sessao: SessaoCadastro) -> None:
        novas = sessao.miniaturas[len(self._miniaturas_widgets):]
        if not novas:
            return
        self.rotulo_miniaturas.pack_forget()
        for recorte in novas:
            try:
                img = miniatura_quadrada(recorte)
            except Exception:  # noqa: BLE001
                continue
            self._miniaturas_imgs.append(img)
            rot = ctk.CTkLabel(self.faixa_miniaturas, image=img, text="", width=TAM_MINIATURA, height=TAM_MINIATURA)
            rot.pack(side="left", padx=4, pady=4)
            self._miniaturas_widgets.append(rot)

    # ------------------------------------------------------------------ cadastro por fotos
    def _escolher_fotos(self) -> None:
        if self.capturando or self.importando_fotos:
            return
        if self.ler_formulario() is None:
            return
        caminhos = filedialog.askopenfilenames(
            parent=self, title="Escolha as fotos do rosto",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.bmp *.webp"), ("Todos os arquivos", "*.*")])
        if caminhos:
            self.cadastrar_por_fotos(list(caminhos))

    def cadastrar_por_fotos(self, caminhos: list[str | Path]) -> bool:
        """Cadastra o usuário do formulário a partir dos arquivos dados, em uma thread."""
        if self.capturando or self.importando_fotos:
            return False
        if not caminhos:
            self._mostrar_erro("Nenhuma foto escolhida.")
            return False
        dados = self.ler_formulario()
        if dados is None:
            return False
        if not self.app.pipeline_pronto():
            self._mostrar_erro("Os modelos ainda estão carregando. Tente novamente em instantes.")
            return False
        self._definir_formulario(False)
        self._mostrar_msg(f"Processando {len(caminhos)} foto(s)...", tema.TEXTO_2)
        self.app.status.definir(f"Cadastro por fotos: processando {len(caminhos)} arquivo(s)", None)
        self._resultado_fotos = None
        caminho_db = self.app.banco.caminho
        pipeline = self.app.pipeline
        self._thread_fotos = threading.Thread(
            target=self._trabalho_fotos, args=(caminho_db, pipeline, dados, list(caminhos)),
            name="cadastro-fotos", daemon=True)
        self._thread_fotos.start()
        return True

    def _trabalho_fotos(self, caminho_db, pipeline, dados, caminhos) -> None:
        """Thread de trabalho: conexão própria ao banco (SQLite exige a mesma thread)."""
        banco = None
        try:
            banco = Banco(caminho_db) if str(caminho_db) != ":memory:" else self.app.banco
            usuario, n, avisos = cadastrar_de_imagens(banco, pipeline, dados, caminhos)
            self._resultado_fotos = ("ok", usuario, n, avisos)
        except Exception as e:  # noqa: BLE001
            self._resultado_fotos = ("erro", str(e))
        finally:
            if banco is not None and banco is not self.app.banco:
                try:
                    banco.fechar()
                except Exception:  # noqa: BLE001
                    pass

    def _tratar_resultado_fotos(self) -> None:
        res = self._resultado_fotos
        if res is None:
            return
        self._resultado_fotos = None
        self._thread_fotos = None
        self._definir_formulario(True)
        if res[0] == "ok":
            _, usuario, n, avisos = res
            # reconsulta pela conexão principal (os dados vieram de outra conexão)
            usuario = self.app.banco.obter_usuario(usuario.id) or usuario
            self._anunciar_sucesso(usuario, n, avisos)
        else:
            self._mostrar_msg("")
            self._mostrar_erro(f"Cadastro por fotos falhou: {res[1]}")
            self.app.status.definir("Cadastro por fotos falhou", "")
