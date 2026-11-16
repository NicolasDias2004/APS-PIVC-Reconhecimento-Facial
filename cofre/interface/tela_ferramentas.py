"""Tela "Avaliação e demo": demonstração didática das 5 fases, autenticação por
imagem e avaliação quantitativa do reconhecedor (TAR/FAR/FRR/EER).

Regras de thread: o `Banco` usa uma conexão sqlite presa à thread do Tk, por isso
só o pipeline (fases 2 a 4) e a avaliação de pasta rodam em `threading.Thread`;
a fase 5 (galeria), o log de acesso e todos os widgets ficam na thread do Tk.
Os resultados das threads chegam por uma fila consumida em `atualizar()`.
"""

from __future__ import annotations

import queue
import threading
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk
import cv2
import numpy as np

from .. import config, hud
from ..autenticacao import autenticar_imagem
from ..avaliacao import ResultadoAvaliacao, avaliar_pasta
from ..fase1_aquisicao import carregar_imagem
from ..fase5_reconhecimento import Reconhecedor, decidir_acesso
from . import tema
from .base import Tela
from .widgets import Cartao, Faixa, Tabela, VideoWidget, botao, botao_secundario, titulo

PASTA_FOTOS_TESTE = config.BASE_DIR / "tests" / "fixtures" / "pessoas"
TIPOS_IMAGEM = [("Imagens", "*.jpg *.jpeg *.png *.bmp *.webp"), ("Todos os arquivos", "*.*")]
NIVEIS_ROTULO = {f"Nível {n}": n for n in config.NIVEIS}

ABA_DEMO = "Demo das 5 fases"
ABA_AUTH = "Autenticar por imagem"
ABA_AVAL = "Avaliar reconhecedor"


def _pct(v: float) -> str:
    return "-" if v != v else f"{v:.1%}"  # NaN quando não há pares


class TelaFerramentas(Tela):
    TITULO = "Avaliação e demo"

    # ------------------------------------------------------------------ construção
    def construir(self) -> None:
        self._fila: queue.Queue[Callable[[], None]] = queue.Queue()
        self.ocupado = False                      # thread de trabalho em andamento
        self.ultimo_demo = None                   # ResultadoPipeline da última demo
        self.ultima_decisao = None                # Decisao da última autenticação por imagem
        self.ultima_avaliacao: ResultadoAvaliacao | None = None
        self.pasta_avaliacao: Path | None = None
        self._caminho_demo: Path | None = None
        self._painel: np.ndarray | None = None    # mosaico da demo (para salvar PNG)
        self._linhas_demo: list[str] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        titulo(self, self.TITULO, "Ferramentas de demonstração e validação do pipeline").grid(
            row=0, column=0, padx=24, pady=(24, 12), sticky="ew")
        self.abas = ctk.CTkTabview(self, fg_color=tema.FUNDO_2, corner_radius=10,
                                   segmented_button_fg_color=tema.CARTAO,
                                   segmented_button_selected_color=tema.ACENTO,
                                   segmented_button_selected_hover_color=tema.ACENTO_HOVER,
                                   segmented_button_unselected_color=tema.CARTAO,
                                   segmented_button_unselected_hover_color=tema.BORDA,
                                   text_color=tema.TEXTO)
        self.abas.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="nsew")
        for nome in (ABA_DEMO, ABA_AUTH, ABA_AVAL):
            self.abas.add(nome)
        self._construir_demo(self.abas.tab(ABA_DEMO))
        self._construir_auth(self.abas.tab(ABA_AUTH))
        self._construir_avaliacao(self.abas.tab(ABA_AVAL))

    def _seletor_nivel(self, master, comando=None) -> ctk.CTkSegmentedButton:
        seg = ctk.CTkSegmentedButton(master, values=list(NIVEIS_ROTULO), font=tema.CORPO,
                                     fg_color=tema.CARTAO, selected_color=tema.ACENTO,
                                     selected_hover_color=tema.ACENTO_HOVER, unselected_color=tema.CARTAO,
                                     unselected_hover_color=tema.BORDA, text_color=tema.TEXTO,
                                     command=comando)
        seg.set("Nível 3")
        return seg

    def _caixa_texto(self, master, **kw) -> ctk.CTkTextbox:
        cx = ctk.CTkTextbox(master, font=tema.MONO, fg_color=tema.CARTAO, text_color=tema.TEXTO,
                            corner_radius=10, wrap="none", **kw)
        cx.configure(state="disabled")
        return cx

    @staticmethod
    def _escrever(caixa: ctk.CTkTextbox, texto: str) -> None:
        caixa.configure(state="normal")
        caixa.delete("1.0", "end")
        caixa.insert("1.0", texto)
        caixa.configure(state="disabled")

    # ---- aba (a): demo das 5 fases
    def _construir_demo(self, aba) -> None:
        aba.grid_columnconfigure(0, weight=1)
        aba.grid_rowconfigure(1, weight=1)
        barra = ctk.CTkFrame(aba, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.bt_demo_imagem = botao(barra, "Escolher imagem...", self._escolher_imagem_demo)
        self.bt_demo_imagem.pack(side="left")
        ctk.CTkLabel(barra, text="Área exigida:", font=tema.CORPO, text_color=tema.TEXTO_2).pack(
            side="left", padx=(12, 6))
        self.nivel_demo = self._seletor_nivel(barra, self._nivel_demo_alterado)
        self.nivel_demo.pack(side="left")
        self.bt_salvar_painel = botao_secundario(barra, "Salvar painel PNG", self.salvar_painel)
        self.bt_salvar_painel.pack(side="left", padx=(12, 0))
        self.lbl_demo_arquivo = ctk.CTkLabel(barra, text="Nenhuma imagem escolhida", font=tema.PEQUENO,
                                             text_color=tema.TEXTO_2)
        self.lbl_demo_arquivo.pack(side="left", padx=12)

        corpo = ctk.CTkFrame(aba, fg_color="transparent")
        corpo.grid(row=1, column=0, sticky="nsew")
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_rowconfigure(0, weight=1)
        self.video_demo = VideoWidget(corpo, largura=640, altura=400)
        self.video_demo.grid(row=0, column=0, sticky="nsew")
        self.video_demo.mensagem("Escolha uma imagem para ver as 5 fases do pipeline")
        self.texto_demo = self._caixa_texto(corpo, width=400)
        self.texto_demo.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.faixa_demo = Faixa(aba)
        self.faixa_demo.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.faixa_demo.definir("Fases 1 a 4 no painel; a fase 5 compara com a galeria do banco.")

    # ---- aba (b): autenticar por imagem
    def _construir_auth(self, aba) -> None:
        aba.grid_columnconfigure(0, weight=1)
        aba.grid_rowconfigure(2, weight=1)
        barra = ctk.CTkFrame(aba, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.bt_auth_imagem = botao(barra, "Escolher imagem...", self._escolher_imagem_auth)
        self.bt_auth_imagem.pack(side="left")
        ctk.CTkLabel(barra, text="Área exigida:", font=tema.CORPO, text_color=tema.TEXTO_2).pack(
            side="left", padx=(12, 6))
        self.nivel_auth = self._seletor_nivel(barra)
        self.nivel_auth.pack(side="left")
        self.lbl_auth_arquivo = ctk.CTkLabel(barra, text="Nenhuma imagem escolhida", font=tema.PEQUENO,
                                             text_color=tema.TEXTO_2)
        self.lbl_auth_arquivo.pack(side="left", padx=12)

        self.faixa_auth = Faixa(aba)
        self.faixa_auth.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.faixa_auth.definir("Escolha uma imagem: a tentativa é registrada no log de acessos.")

        corpo = ctk.CTkFrame(aba, fg_color="transparent")
        corpo.grid(row=2, column=0, sticky="nsew")
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_rowconfigure(0, weight=1)
        self.video_auth = VideoWidget(corpo, largura=560, altura=360)
        self.video_auth.grid(row=0, column=0, sticky="nsew")
        self.video_auth.mensagem("A imagem aparece aqui com o rosto marcado")
        cartoes = ctk.CTkFrame(corpo, fg_color="transparent", width=240)
        cartoes.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        self.cartao_auth_usuario = Cartao(cartoes, "Identificado como")
        self.cartao_auth_sim = Cartao(cartoes, f"Similaridade (limiar {config.LIMIAR_COSSENO:.3f})")
        self.cartao_auth_nivel = Cartao(cartoes, "Nível do usuário / exigido")
        self.cartao_auth_rostos = Cartao(cartoes, "Rostos na imagem")
        for c in (self.cartao_auth_usuario, self.cartao_auth_sim, self.cartao_auth_nivel, self.cartao_auth_rostos):
            c.pack(fill="x", pady=(0, 12))

    # ---- aba (c): avaliar reconhecedor
    def _construir_avaliacao(self, aba) -> None:
        aba.grid_columnconfigure(0, weight=1)
        aba.grid_rowconfigure(2, weight=1)
        barra = ctk.CTkFrame(aba, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.bt_aval_pasta = botao_secundario(barra, "Escolher pasta...", self._escolher_pasta)
        self.bt_aval_pasta.pack(side="left")
        self.bt_aval_teste = botao_secundario(barra, "Usar fotos de teste", self.usar_fotos_teste)
        self.bt_aval_teste.pack(side="left", padx=(12, 0))
        self.bt_avaliar = botao(barra, "Avaliar", self._avaliar_clicado)
        self.bt_avaliar.pack(side="left", padx=(12, 0))
        self.lbl_aval_status = ctk.CTkLabel(barra, text="", font=tema.CORPO, text_color=tema.ACENTO)
        self.lbl_aval_status.pack(side="right")
        self.lbl_aval_pasta = ctk.CTkLabel(barra, text="Nenhuma pasta escolhida (estrutura: pasta/pessoa/*.jpg)",
                                           font=tema.PEQUENO, text_color=tema.TEXTO_2)
        self.lbl_aval_pasta.pack(side="left", padx=12)

        linha_cartoes = ctk.CTkFrame(aba, fg_color="transparent")
        linha_cartoes.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        lim = f"limiar {config.LIMIAR_COSSENO:.3f}"
        self.cartao_tar = Cartao(linha_cartoes, f"TAR ({lim})", cor=tema.VERDE)
        self.cartao_far = Cartao(linha_cartoes, f"FAR ({lim})", cor=tema.VERMELHO)
        self.cartao_frr = Cartao(linha_cartoes, f"FRR ({lim})", cor=tema.LARANJA)
        self.cartao_eer = Cartao(linha_cartoes, "EER (limiar -)", cor=tema.AZUL)
        for i, c in enumerate((self.cartao_tar, self.cartao_far, self.cartao_frr, self.cartao_eer)):
            linha_cartoes.grid_columnconfigure(i, weight=1)
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 12, 0))

        corpo = ctk.CTkFrame(aba, fg_color="transparent")
        corpo.grid(row=2, column=0, sticky="nsew")
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_columnconfigure(1, weight=1)
        corpo.grid_rowconfigure(0, weight=1)
        self.texto_aval = self._caixa_texto(corpo)
        self.texto_aval.grid(row=0, column=0, sticky="nsew")
        self._escrever(self.texto_aval, "O resumo da avaliação aparece aqui.")
        self.tabela_varredura = Tabela(corpo, [("limiar", "Limiar", 90), ("tar", "TAR", 90),
                                               ("frr", "FRR", 90), ("far", "FAR", 90)], altura=11)
        self.tabela_varredura.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.faixa_aval = Faixa(aba)
        self.faixa_aval.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.faixa_aval.definir("Compara todos os pares de imagens: mesma pessoa = genuíno, pessoas diferentes = impostor.")

    # ------------------------------------------------------------------ ciclo
    def ao_mostrar(self) -> None:
        self.app.status.definir(self.TITULO, None)

    def atualizar(self) -> None:
        while True:
            try:
                fn = self._fila.get_nowait()
            except queue.Empty:
                return
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self._erro_geral(f"Erro inesperado: {e}")

    def _erro_geral(self, msg: str) -> None:
        faixa = {ABA_DEMO: self.faixa_demo, ABA_AUTH: self.faixa_auth, ABA_AVAL: self.faixa_aval}[self.abas.get()]
        faixa.definir(msg, tema.VERMELHO)

    def _pipeline_ou_aviso(self, faixa: Faixa) -> bool:
        if not self.app.pipeline_pronto():
            faixa.definir("Os modelos ainda estão carregando, tente de novo em instantes.", tema.LARANJA, tema.FUNDO)
            return False
        if self.ocupado:
            faixa.definir("Aguarde: já existe um processamento em andamento.", tema.LARANJA, tema.FUNDO)
            return False
        return True

    def _em_thread(self, alvo: Callable[[], Callable[[], None]], faixa: Faixa) -> None:
        """Roda `alvo` fora do Tk; ele devolve a função que aplica o resultado nos widgets."""
        self.ocupado = True

        def rodar():
            try:
                aplicar = alvo()
            except Exception as e:  # noqa: BLE001
                msg = f"Falha: {e}"
                aplicar = lambda: faixa.definir(msg, tema.VERMELHO)  # noqa: E731
            finally:
                self.ocupado = False
            self._fila.put(aplicar)

        threading.Thread(target=rodar, name="ferramentas", daemon=True).start()

    # ------------------------------------------------------------------ (a) demo
    def _escolher_imagem_demo(self) -> None:
        caminho = filedialog.askopenfilename(title="Imagem para a demonstração", filetypes=TIPOS_IMAGEM)
        if caminho:
            self.demonstrar(caminho)

    def _nivel_demo_alterado(self, _valor=None) -> None:
        if self.ultimo_demo is not None:
            self._mostrar_demo(self.ultimo_demo)

    def demonstrar(self, caminho: str | Path) -> None:
        """Roda o pipeline na imagem e monta o painel das 5 fases (fases 2 a 4 em thread)."""
        if not self._pipeline_ou_aviso(self.faixa_demo):
            return
        caminho = Path(caminho)
        self._caminho_demo = caminho
        self.lbl_demo_arquivo.configure(text=caminho.name)
        self.faixa_demo.definir("Processando...", tema.CARTAO)
        pipeline = self.app.pipeline

        def trabalho():
            frame = carregar_imagem(caminho)
            res = pipeline.processar(frame)
            painel = hud.mosaico(res.etapas_didaticas(), lado=200, colunas=4)
            return lambda: self._demo_pronta(res, painel)

        self._em_thread(trabalho, self.faixa_demo)

    def _demo_pronta(self, res, painel: np.ndarray) -> None:
        self.ultimo_demo, self._painel = res, painel
        self.video_demo.mostrar(painel)
        self._mostrar_demo(res)

    def _mostrar_demo(self, res) -> None:
        """Monta o texto das fases (a fase 5 usa o banco, por isso roda na thread do Tk)."""
        nivel = NIVEIS_ROTULO[self.nivel_demo.get()]
        nome = self._caminho_demo.name if self._caminho_demo else "-"
        frame = res.pre.original
        linhas = [f"FASE 1  Aquisição",
                  f"  arquivo: {nome}",
                  f"  tamanho: {frame.shape[1]}x{frame.shape[0]} px",
                  "",
                  f"FASE 2  Pré-processamento",
                  f"  frame reduzido: {res.pre.reduzida.shape[1]}x{res.pre.reduzida.shape[0]} px (escala {res.pre.escala:.2f})",
                  "",
                  f"FASE 3  Segmentação",
                  f"  rostos detectados: {len(res.rostos)}"]
        p = res.principal
        if p is None:
            linhas += ["  nenhum rosto: as fases 4 e 5 não rodam", "", "FASE 4  Representação: -", "", "FASE 5  Reconhecimento: -"]
            self.faixa_demo.definir("Nenhum rosto detectado na imagem. Tente uma foto frontal e bem iluminada.",
                                    tema.LARANJA, tema.FUNDO)
        else:
            x, y, w, h = p.rosto.caixa
            norma = float(np.linalg.norm(p.embedding))
            qual = "aprovada" if p.qualidade.aprovada else "reprovada"
            ident = Reconhecedor(self.app.banco).identificar(p.embedding)
            d = decidir_acesso(ident, nivel)
            linhas += [f"  caixa (x, y, w, h): ({x}, {y}, {w}, {h})",
                       f"  confiança: {p.rosto.confianca:.3f}",
                       f"  yaw (nariz/olhos): {p.rosto.yaw():+.3f}",
                       f"  nitidez: {p.qualidade.nitidez:.1f} (mín {config.MIN_NITIDEZ:.0f})",
                       f"  brilho: {p.qualidade.brilho:.1f} ({config.MIN_BRILHO:.0f} a {config.MAX_BRILHO:.0f})",
                       f"  qualidade: {qual}",
                       "",
                       f"FASE 4  Representação",
                       f"  embedding: {p.embedding.shape[0]}-d, norma {norma:.3f}",
                       f"  min {float(p.embedding.min()):+.3f}  max {float(p.embedding.max()):+.3f}",
                       "",
                       f"FASE 5  Reconhecimento ({config.AREAS[nivel]})",
                       f"  galeria: {len(Reconhecedor(self.app.banco).usuarios)} usuário(s)",
                       f"  identificado: {ident.rotulo}",
                       f"  similaridade: {ident.similaridade:.3f} (limiar {config.LIMIAR_COSSENO:.3f})",
                       f"  2º colocado: {ident.segunda_similaridade:.3f}",
                       f"  decisão: {d.resultado.value}",
                       f"  {d.mensagem}"]
            self.faixa_demo.definir(f"{tema.ROTULO_RESULTADO[d.resultado.value]}: {d.mensagem}",
                                    tema.COR_RESULTADO[d.resultado.value], tema.FUNDO)
        self._linhas_demo = linhas
        self._escrever(self.texto_demo, "\n".join(linhas))

    def salvar_painel(self) -> Path | None:
        """Grava o mosaico (com as linhas de dados no rodapé) em config.RELATORIOS_DIR."""
        if self._painel is None:
            self.faixa_demo.definir("Nada para salvar: rode a demonstração em uma imagem primeiro.",
                                    tema.LARANJA, tema.FUNDO)
            return None
        try:
            linhas = [l for l in self._linhas_demo if l.strip()]
            rodape = 20 * len(linhas) + 16
            painel = self._painel
            base = np.full((painel.shape[0] + rodape, painel.shape[1], 3), 20, np.uint8)
            base[:painel.shape[0]] = painel
            y = painel.shape[0] + 20
            for l in linhas:
                hud.texto(base, l, (10, y), 0.45, hud.BRANCO, 1)
                y += 20
            pasta = Path(config.RELATORIOS_DIR)
            pasta.mkdir(parents=True, exist_ok=True)
            stem = self._caminho_demo.stem if self._caminho_demo else "imagem"
            destino = pasta / f"demo_{stem}_{datetime.now():%Y%m%d_%H%M%S}.png"
            if not cv2.imwrite(str(destino), base):
                raise OSError("cv2.imwrite não conseguiu gravar o arquivo")
        except Exception as e:  # noqa: BLE001
            self.faixa_demo.definir(f"Não foi possível salvar o painel: {e}", tema.VERMELHO)
            return None
        self.faixa_demo.definir(f"Painel salvo em {destino}", tema.VERDE, tema.FUNDO)
        self.app.status.definir(f"Painel salvo: {destino.name}", None)
        return destino

    # ------------------------------------------------------------------ (b) autenticar por imagem
    def _escolher_imagem_auth(self) -> None:
        caminho = filedialog.askopenfilename(title="Imagem para autenticar", filetypes=TIPOS_IMAGEM)
        if caminho:
            self.autenticar(caminho)

    def autenticar(self, caminho: str | Path):
        """Autentica a imagem no nível escolhido e registra no log (roda na thread do Tk:
        `autenticar_imagem` grava no banco, que não aceita outra thread)."""
        if not self._pipeline_ou_aviso(self.faixa_auth):
            return None
        caminho = Path(caminho)
        self.lbl_auth_arquivo.configure(text=caminho.name)
        nivel = NIVEIS_ROTULO[self.nivel_auth.get()]
        try:
            frame = carregar_imagem(caminho)
            decisao, res = autenticar_imagem(self.app.banco, self.app.pipeline, frame, nivel)
        except Exception as e:  # noqa: BLE001
            self.faixa_auth.definir(f"Falha ao autenticar: {e}", tema.VERMELHO)
            return None
        self.ultima_decisao = decisao
        marcado = frame.copy()
        cor = hud.VERDE if decisao.concedido else hud.VERMELHO
        for r in res.rostos:
            hud.caixa_rosto(marcado, r.rosto, cor, rotulo=None)
        self.video_auth.mostrar(marcado)

        chave = decisao.resultado.value
        self.faixa_auth.definir(f"{tema.ROTULO_RESULTADO[chave]}: {decisao.mensagem}",
                                tema.COR_RESULTADO[chave], tema.FUNDO)
        ident = decisao.identificacao
        u = ident.usuario if ident and ident.reconhecido else None
        self.cartao_auth_usuario.definir(u.nome if u else "Desconhecido", tema.VERDE if u else tema.VERMELHO)
        if ident is not None:
            self.cartao_auth_sim.definir(f"{ident.similaridade:.3f}",
                                         tema.VERDE if ident.reconhecido else tema.VERMELHO)
        else:
            self.cartao_auth_sim.definir("-", tema.TEXTO_2)
        self.cartao_auth_nivel.definir(f"{u.nivel if u else '-'} / {nivel}",
                                       tema.COR_NIVEL.get(nivel, tema.TEXTO))
        self.cartao_auth_rostos.definir(len(res.rostos), tema.TEXTO if len(res.rostos) == 1 else tema.LARANJA)
        self.app.status.definir(f"Autenticação por imagem: {chave}", None)
        return decisao

    # ------------------------------------------------------------------ (c) avaliar reconhecedor
    def _escolher_pasta(self) -> None:
        pasta = filedialog.askdirectory(title="Pasta com subpastas por pessoa")
        if pasta:
            self._definir_pasta(Path(pasta))

    def usar_fotos_teste(self) -> None:
        self._definir_pasta(PASTA_FOTOS_TESTE)

    def _definir_pasta(self, pasta: Path) -> None:
        self.pasta_avaliacao = pasta
        self.lbl_aval_pasta.configure(text=str(pasta))
        self.faixa_aval.definir(f"Pasta escolhida: {pasta.name}. Clique em Avaliar.")

    def _avaliar_clicado(self) -> None:
        if self.pasta_avaliacao is None:
            self.faixa_aval.definir("Escolha uma pasta (ou use as fotos de teste) antes de avaliar.",
                                    tema.LARANJA, tema.FUNDO)
            return
        self.avaliar(self.pasta_avaliacao)

    def avaliar(self, pasta: str | Path) -> None:
        """Roda `avaliacao.avaliar_pasta` em thread e preenche resumo, cartões e varredura."""
        if not self._pipeline_ou_aviso(self.faixa_aval):
            return
        pasta = Path(pasta)
        if not pasta.is_dir():
            self.faixa_aval.definir(f"Pasta não encontrada: {pasta}", tema.VERMELHO)
            return
        if not any(p.is_dir() for p in pasta.iterdir()):
            self.faixa_aval.definir("A pasta precisa ter uma subpasta por pessoa (pasta/pessoa/*.jpg).",
                                    tema.LARANJA, tema.FUNDO)
            return
        self._definir_pasta(pasta)
        self.lbl_aval_status.configure(text="Avaliando...")
        self.bt_avaliar.configure(state="disabled")
        self.faixa_aval.definir("Avaliando todas as imagens, isso pode levar alguns segundos...", tema.CARTAO)
        pipeline = self.app.pipeline

        def trabalho():
            r = avaliar_pasta(pasta, pipeline)
            return lambda: self._avaliacao_pronta(r)

        def ao_terminar():
            self.lbl_aval_status.configure(text="")
            self.bt_avaliar.configure(state="normal")

        def trabalho_com_fecho():
            try:
                aplicar = trabalho()
            except Exception:
                self._fila.put(ao_terminar)
                raise
            return lambda: (ao_terminar(), aplicar())

        self._em_thread(trabalho_com_fecho, self.faixa_aval)

    def _avaliacao_pronta(self, r: ResultadoAvaliacao) -> None:
        self.ultima_avaliacao = r
        self._escrever(self.texto_aval, r.resumo())
        self.tabela_varredura.limpar()
        n_pares = len(r.genuinos) + len(r.impostores)
        if n_pares == 0:
            for c in (self.cartao_tar, self.cartao_far, self.cartao_frr, self.cartao_eer):
                c.definir("-")
            self.faixa_aval.definir(
                f"Nenhum par para comparar ({sum(r.pessoas.values())} imagem(ns) com rosto, "
                f"{len(r.sem_rosto)} sem rosto). São necessárias ao menos 2 imagens com rosto.",
                tema.LARANJA, tema.FUNDO)
            return
        t = r.taxas(config.LIMIAR_COSSENO)
        eer_l, eer_v = r.eer()
        self.cartao_tar.definir(_pct(t["TAR"]))
        self.cartao_far.definir(_pct(t["FAR"]))
        self.cartao_frr.definir(_pct(t["FRR"]))
        self.cartao_eer.definir(_pct(eer_v))
        self.cartao_eer.rotulo.configure(text=f"EER (limiar {eer_l:.3f})")
        mais_proximo = min(r.varredura(11), key=lambda v: abs(v["limiar"] - config.LIMIAR_COSSENO))["limiar"]
        for i, v in enumerate(r.varredura(11)):
            tag = "ok" if v["limiar"] == mais_proximo else None
            self.tabela_varredura.adicionar(f"v{i}", [f"{v['limiar']:.2f}", _pct(v["TAR"]), _pct(v["FRR"]),
                                                     _pct(v["FAR"])], tag)
        partes = [f"{len(r.pessoas)} pessoa(s), {sum(r.pessoas.values())} imagem(ns) com rosto, "
                  f"{len(r.genuinos)} par(es) genuíno(s) e {len(r.impostores)} impostor(es)."]
        cor, cor_texto = tema.VERDE, tema.FUNDO
        if r.sem_rosto:
            nomes = ", ".join(Path(s).name for s in r.sem_rosto[:3])
            extra = f" e mais {len(r.sem_rosto) - 3}" if len(r.sem_rosto) > 3 else ""
            partes.append(f"Ignoradas {len(r.sem_rosto)} sem rosto: {nomes}{extra}.")
            cor, cor_texto = tema.LARANJA, tema.FUNDO
        self.faixa_aval.definir(" ".join(partes), cor, cor_texto)
        self.app.status.definir(f"Avaliação concluída: EER {_pct(eer_v)}", None)
