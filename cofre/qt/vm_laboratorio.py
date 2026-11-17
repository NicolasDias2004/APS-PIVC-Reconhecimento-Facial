"""Página Laboratório PIVC (v2): dona da amostra e da referência que as três abas examinam.

A amostra é uma imagem levada da fase 1 à fase 4 por `amostra_lab.preparar`, sempre fora da thread
da interface. Ela vem de uma foto de teste do repositório, de um arquivo escolhido ou de um quadro
congelado da câmera. A referência é uma segunda imagem, para as comparações das abas; ao escolher
uma foto de teste, a outra foto da mesma pessoa de teste vira a referência automática (até o
operador escolher uma à mão).

A pré-visualização da câmera só converte o quadro em imagem: nenhum pipeline roda nela e nada é
comparado com a galeria. Ela só liga com a página na tela e sem sessão aberta. O quadro congelado
existe só em memória e some quando a página sai da tela; amostras de foto e de arquivo ficam.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PySide6.QtCore import Signal, Slot

from .. import amostra_lab
from .base import objeto, prop
from .base_v2 import PaginaAbasVM
from .formatos import caminho_de_url
from .imagens import bgr_para_qimage
from .trabalhos import Trabalho
from .video import FonteVideo

AMOSTRA, REFERENCIA = "amostra", "referencia"
ALVOS = (AMOSTRA, REFERENCIA)
ORIGEM_FOTO, ORIGEM_ARQUIVO, ORIGEM_CAMERA = "foto_teste", "arquivo", "camera"
MODELOS_CARREGANDO = "Os modelos ainda estão carregando."


def ler_imagem(caminho: Path) -> np.ndarray:
    """Lê uma imagem do disco em BGR (aceita caminho com acento). Roda na thread de trabalho."""
    dados = np.fromfile(str(caminho), dtype=np.uint8)
    frame = cv2.imdecode(dados, cv2.IMREAD_COLOR) if dados.size else None
    if frame is None:
        raise ValueError("o arquivo não é uma imagem reconhecida")
    return frame


def processar_previa(frame: np.ndarray):
    """Processador da câmera na pré-visualização (thread da câmera): só converte o quadro em imagem."""
    return bgr_para_qimage(frame)


class LaboratorioVM(PaginaAbasVM):
    CHAVE = "laboratorio"

    amostraMudou = Signal()             # a amostra (ou a ausência dela) mudou
    referenciaMudou = Signal()
    temAmostraMudou = Signal()
    amostraRotuloMudou = Signal()
    amostraOrigemMudou = Signal()
    temRostoMudou = Signal()
    nRostosMudou = Signal()
    temReferenciaMudou = Signal()
    referenciaRotuloMudou = Signal()
    referenciaTemRostoMudou = Signal()
    processandoMudou = Signal()
    erroMudou = Signal()
    previaMudou = Signal()
    alvoPreviaMudou = Signal()
    revisaoMudou = Signal()
    fotosTesteMudou = Signal()

    temAmostra = prop(bool, "temAmostra", temAmostraMudou)
    amostraRotulo = prop(str, "amostraRotulo", amostraRotuloMudou)
    amostraOrigem = prop(str, "amostraOrigem", amostraOrigemMudou)            # "" | foto_teste | arquivo | camera
    temRosto = prop(bool, "temRosto", temRostoMudou)
    nRostos = prop(int, "nRostos", nRostosMudou)
    temReferencia = prop(bool, "temReferencia", temReferenciaMudou)
    referenciaRotulo = prop(str, "referenciaRotulo", referenciaRotuloMudou)
    referenciaTemRosto = prop(bool, "referenciaTemRosto", referenciaTemRostoMudou)
    processando = prop(bool, "processando", processandoMudou)
    erro = prop(str, "erro", erroMudou)
    previa = prop(bool, "previa", previaMudou)                                # câmera em pré-visualização
    alvoPrevia = prop(str, "alvoPrevia", alvoPreviaMudou)                     # "amostra" | "referencia"
    revisao = prop(int, "revisao", revisaoMudou)                              # sobe a cada troca de amostra ou referência
    fotosTeste = prop("QVariantList", "fotosTeste", fotosTesteMudou)          # [{indice, rotulo}]
    fonteVideo = objeto("video")                                              # pré-visualização ou a imagem da amostra

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._fotos: list[tuple[str, Path]] = [(pessoa, caminho) for pessoa, caminhos in amostra_lab.fotos_de_teste().items()
                                               for caminho in caminhos]
        rotulos, contagem = [], {}
        for pessoa, _ in self._fotos:
            contagem[pessoa] = contagem.get(pessoa, 0) + 1
            rotulos.append({"indice": len(rotulos), "rotulo": f"{pessoa} · foto {contagem[pessoa]}"})
        self._iniciar(temAmostra=False, amostraRotulo="", amostraOrigem="", temRosto=False, nRostos=0,
                      temReferencia=False, referenciaRotulo="", referenciaTemRosto=False, processando=False, erro="",
                      previa=False, alvoPrevia=AMOSTRA, revisao=0, fotosTeste=rotulos)
        self.amostra: amostra_lab.AmostraLab | None = None
        self.referencia: amostra_lab.AmostraLab | None = None
        self.video = FonteVideo("laboratorio", self)
        self._imagem_amostra = None                 # QImage da amostra, para voltar a mostrá-la depois da prévia
        self._referencia_manual = False             # o operador escolheu a referência: a automática não a troca
        self._dono_camera = False
        self._ultimo_frame: np.ndarray | None = None
        self._trabalhos = {alvo: Trabalho(aplicacao.extensoes.trabalhos, self) for alvo in ALVOS}
        self._origem_pedido: dict[str, str] = {}    # origem do pedido em andamento de cada alvo
        self._pendentes: dict[str, tuple[str, str, Callable[[], np.ndarray]]] = {}   # à espera dos modelos
        for trabalho in self._trabalhos.values():
            trabalho.ocupadoMudou.connect(self._atualizar_processando)
        aplicacao.camera.quadroDisponivel.connect(self._quadro)

    # ------------------------------------------------------------------ escolha da imagem
    @Slot(int)
    def usarFotoTeste(self, indice: int) -> None:
        if not 0 <= indice < len(self._fotos):
            return
        pessoa, caminho = self._fotos[indice]
        self._carregar(AMOSTRA, ORIGEM_FOTO, self._v["fotosTeste"][indice]["rotulo"], lambda: ler_imagem(caminho))
        if self._referencia_manual:
            return
        outra = next((i for i, (p, _) in enumerate(self._fotos) if p == pessoa and i != indice), None)
        if outra is None:
            self._cancelar_pedido(REFERENCIA)
            self._remover(REFERENCIA)
        else:
            self._carregar_foto_referencia(outra)

    @Slot(int)
    def usarFotoTesteComoReferencia(self, indice: int) -> None:
        if 0 <= indice < len(self._fotos):
            self._referencia_manual = True
            self._carregar_foto_referencia(indice)

    def _carregar_foto_referencia(self, indice: int) -> None:
        caminho = self._fotos[indice][1]
        self._carregar(REFERENCIA, ORIGEM_FOTO, self._v["fotosTeste"][indice]["rotulo"], lambda: ler_imagem(caminho))

    @Slot(str)
    def abrirArquivo(self, url: str) -> None:
        self._abrir(AMOSTRA, url)

    @Slot(str)
    def abrirReferencia(self, url: str) -> None:
        self._referencia_manual = True
        self._abrir(REFERENCIA, url)

    def _abrir(self, alvo: str, url: str) -> None:
        caminho = caminho_de_url(url)
        if caminho is None:
            return
        rotulo = f"Arquivo aberto às {datetime.now():%H:%M:%S}"      # o nome do arquivo pode ter o nome da pessoa
        self._carregar(alvo, ORIGEM_ARQUIVO, rotulo, lambda: ler_imagem(caminho))

    def carregar_frame(self, frame: np.ndarray, *, origem: str, rotulo: str, alvo: str = AMOSTRA) -> None:
        """Prepara um quadro já em memória (BGR) como amostra ou referência. Usado pelo congelamento da
        câmera, pelos testes e pela ferramenta de capturas."""
        if alvo not in ALVOS:
            raise ValueError(f"alvo desconhecido: {alvo!r}")
        if alvo == REFERENCIA:
            self._referencia_manual = True
        copia = np.array(frame, copy=True)
        self._carregar(alvo, origem, rotulo, lambda: copia)

    @Slot()
    def limpar(self) -> None:
        self._cancelar_pedido(AMOSTRA)
        self._remover(AMOSTRA)

    @Slot()
    def limparReferencia(self) -> None:
        self._cancelar_pedido(REFERENCIA)
        self._referencia_manual = False
        self._remover(REFERENCIA)

    # ------------------------------------------------------------------ preparo fora da interface
    def _carregar(self, alvo: str, origem: str, rotulo: str, ler: Callable[[], np.ndarray]) -> None:
        pipeline = self.app.pipeline
        if pipeline is None:                        # refeito em ao_pipeline_pronto
            self._cancelar_pedido(alvo)
            self._pendentes[alvo] = (origem, rotulo, ler)
            self._definir("erro", MODELOS_CARREGANDO)
            return
        self._pendentes.pop(alvo, None)
        self._definir("erro", "")
        com_imagem = alvo == AMOSTRA

        def preparar(sinal):
            frame = ler()
            sinal.conferir()
            amostra = amostra_lab.preparar(frame, pipeline, origem=origem, rotulo=rotulo)
            return amostra, (bgr_para_qimage(amostra.frame) if com_imagem else None)

        self._origem_pedido[alvo] = origem
        self._trabalhos[alvo].executar(preparar, lambda resultado, erro: self._ao_preparar(alvo, resultado, erro))

    def _ao_preparar(self, alvo: str, resultado, erro: str) -> None:
        self._origem_pedido.pop(alvo, None)
        if erro:
            self._definir("erro", f"Não foi possível abrir a imagem: {erro}")
            return
        amostra, imagem = resultado
        if alvo == AMOSTRA:
            self.amostra, self._imagem_amostra = amostra, imagem
        else:
            self.referencia = amostra
        self._publicar(alvo)

    def _cancelar_pedido(self, alvo: str) -> None:
        self._trabalhos[alvo].cancelar()
        self._origem_pedido.pop(alvo, None)
        self._pendentes.pop(alvo, None)

    def _remover(self, alvo: str) -> None:
        if (self.amostra if alvo == AMOSTRA else self.referencia) is None:
            return
        if alvo == AMOSTRA:
            self.amostra, self._imagem_amostra = None, None
        else:
            self.referencia = None
        self._publicar(alvo)

    def _publicar(self, alvo: str) -> None:
        if alvo == AMOSTRA:
            a = self.amostra
            self._definir("temAmostra", a is not None)
            self._definir("amostraRotulo", a.rotulo if a is not None else "")
            self._definir("amostraOrigem", a.origem if a is not None else "")
            self._definir("temRosto", bool(a is not None and a.tem_rosto))
            self._definir("nRostos", int(a.n_rostos) if a is not None else 0)
            if not self._v["previa"]:
                self._mostrar_amostra()
        else:
            r = self.referencia
            self._definir("temReferencia", r is not None)
            self._definir("referenciaRotulo", r.rotulo if r is not None else "")
            self._definir("referenciaTemRosto", bool(r is not None and r.tem_rosto))
        self._definir("revisao", self._v["revisao"] + 1)
        (self.amostraMudou if alvo == AMOSTRA else self.referenciaMudou).emit()

    def _mostrar_amostra(self) -> None:
        self.video.definir(self._imagem_amostra, [])

    @Slot()
    def _atualizar_processando(self) -> None:
        self._definir("processando", any(t.ocupado for t in self._trabalhos.values()))

    # ------------------------------------------------------------------ câmera (só pré-visualização)
    @Slot(str)
    def iniciarPrevia(self, alvo: str) -> None:
        """Liga a câmera só para ver o quadro; recusada com a página fora da tela ou a sessão aberta."""
        if alvo not in ALVOS or not self._ativo or self.app.sessao_vm.ativa:
            return
        self._definir("alvoPrevia", alvo)
        if self._v["previa"]:
            return
        self._ultimo_frame = None
        self._definir("previa", True)
        self._dono_camera = True
        self.video.limpar()
        self.app.camera.iniciar(processar_previa)

    @Slot()
    def _quadro(self) -> None:
        if not self._v["previa"]:
            return
        pacote = self.app.camera.ultimo()
        if pacote is None or pacote.saida is None:
            return
        self._ultimo_frame = pacote.frame
        self.video.definir(pacote.saida, [])

    @Slot()
    def congelar(self) -> None:
        """Copia o quadro atual, desliga a câmera e prepara o quadro como amostra (ou referência)."""
        if not self._v["previa"]:
            return
        pacote = self.app.camera.ultimo()
        frame = pacote.frame if pacote is not None else self._ultimo_frame
        if frame is None:
            return                                  # a câmera ainda não entregou nenhum quadro
        frame = np.array(frame, copy=True)
        alvo = self._v["alvoPrevia"]
        self._encerrar_previa()
        self.carregar_frame(frame, origem=ORIGEM_CAMERA, rotulo=f"Quadro congelado {datetime.now():%H:%M:%S}", alvo=alvo)

    @Slot()
    def cancelarPrevia(self) -> None:
        if self._v["previa"]:
            self._encerrar_previa()

    def _encerrar_previa(self) -> None:
        if self._dono_camera:
            self.app.camera.parar()
            self._dono_camera = False
        self._ultimo_frame = None
        self._definir("previa", False)
        self._mostrar_amostra()

    # ------------------------------------------------------------------ ganchos da Aplicacao
    def desativar(self) -> None:
        """Primeiro a aba atual sai (fica inativa), depois a prévia para e o quadro da câmera some:
        os avisos de amostra e referência chegam às abas já inativas, que só ficam sujas."""
        super().desativar()
        self.cancelarPrevia()
        for alvo in ALVOS:
            if self._origem_pedido.get(alvo) == ORIGEM_CAMERA or self._pendentes.get(alvo, ("",))[0] == ORIGEM_CAMERA:
                self._cancelar_pedido(alvo)
            atual = self.amostra if alvo == AMOSTRA else self.referencia
            if atual is not None and atual.origem == ORIGEM_CAMERA:
                self._remover(alvo)

    def ao_pipeline_pronto(self) -> None:
        pendentes, self._pendentes = self._pendentes, {}
        if pendentes and self._v["erro"] == MODELOS_CARREGANDO:
            self._definir("erro", "")
        for alvo, (origem, rotulo, ler) in pendentes.items():
            self._carregar(alvo, origem, rotulo, ler)
        super().ao_pipeline_pronto()
