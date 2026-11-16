"""
Autenticação em tempo real (o "terminal" na porta do cofre).

Máquina de estados por frame:
  AGUARDANDO  : nenhum rosto / rosto instável
  CONFIRMANDO : mesma identidade em N frames seguidos (reduz falsos positivos)
  LIVENESS    : desafio de movimento (se ativo)
  RESULTADO   : exibe o veredito por alguns segundos e registra no log
  BLOQUEADO   : após várias negações seguidas
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime
from enum import Enum

import cv2
import numpy as np

from . import config, hud
from .banco import Banco
from .fase1_aquisicao import FonteCamera
from .fase5_reconhecimento import Decisao, Identificacao, Reconhecedor, Resultado, decidir_acesso
from .liveness import ControleTentativas, DesafioMovimento, EtapaLiveness
from .pipeline import Pipeline, RostoProcessado


class Estado(str, Enum):
    AGUARDANDO = "AGUARDANDO"
    CONFIRMANDO = "CONFIRMANDO"
    LIVENESS = "LIVENESS"
    RESULTADO = "RESULTADO"
    BLOQUEADO = "BLOQUEADO"


class Confirmador:
    """Exige a mesma identidade (ou 'desconhecido') em `n` frames consecutivos."""

    def __init__(self, n: int = config.FRAMES_CONFIRMACAO):
        self.n = n
        self._fila: deque[tuple[int | None, float]] = deque(maxlen=n)

    def limpar(self) -> None:
        self._fila.clear()

    def adicionar(self, ident: Identificacao) -> Identificacao | None:
        chave = ident.usuario.id if ident.reconhecido else None
        self._fila.append((chave, ident.similaridade))
        if len(self._fila) < self.n:
            return None
        if len({c for c, _ in self._fila}) != 1:
            return None
        media = float(np.mean([s for _, s in self._fila]))
        return Identificacao(ident.usuario if chave is not None else None, media, ident.segunda_similaridade)

    @property
    def progresso(self) -> float:
        return len(self._fila) / self.n


def salvar_evidencia(frame: np.ndarray, rotulo: str) -> str:
    config.EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
    nome = f"{datetime.now():%Y%m%d_%H%M%S}_{rotulo}.jpg"
    caminho = config.EVIDENCIAS_DIR / nome
    cv2.imwrite(str(caminho), frame)
    return str(caminho)


def registrar(banco: Banco, decisao: Decisao, frame: np.ndarray | None) -> None:
    ident = decisao.identificacao
    u = ident.usuario if ident and ident.reconhecido else None
    evidencia = None
    if frame is not None and not decisao.concedido:
        evidencia = salvar_evidencia(frame, decisao.resultado.value)
    banco.registrar_acesso(
        usuario_id=u.id if u else None,
        nome_detectado=u.nome if u else None,
        nivel_usuario=u.nivel if u else None,
        nivel_exigido=decisao.nivel_exigido,
        similaridade=ident.similaridade if ident else None,
        resultado=decisao.resultado.value,
        mensagem=decisao.mensagem,
        evidencia=evidencia,
    )


class TerminalAutenticacao:
    def __init__(self, banco: Banco, pipeline: Pipeline, nivel_exigido: int = 3,
                 liveness: bool = config.LIVENESS_ATIVO, didatico: bool = False):
        self.banco = banco
        self.pipeline = pipeline
        self.reconhecedor = Reconhecedor(banco)
        self.nivel_exigido = nivel_exigido
        self.liveness_ativo = liveness
        self.didatico = didatico
        self.estado = Estado.AGUARDANDO
        self.confirmador = Confirmador()
        self.desafio = DesafioMovimento()
        self.tentativas = ControleTentativas()
        self._ident_confirmada: Identificacao | None = None
        self._decisao: Decisao | None = None
        self._resultado_desde = 0.0
        self._frame_decisao: np.ndarray | None = None
        self.orientacao = ""      # instrução para a pessoa quando a pose/qualidade não serve ("" = ok)

    # ------------------------------------------------------------------ lógica
    def _finalizar(self, decisao: Decisao, frame: np.ndarray) -> None:
        self._decisao = decisao
        self._resultado_desde = time.time()
        self.estado = Estado.RESULTADO
        registrar(self.banco, decisao, frame)
        if decisao.concedido:
            self.tentativas.registrar_sucesso()
        elif self.tentativas.registrar_falha():
            self.banco.registrar_acesso(
                usuario_id=None, nome_detectado=None, nivel_usuario=None, nivel_exigido=self.nivel_exigido,
                similaridade=None, resultado=Resultado.BLOQUEADO.value,
                mensagem=f"Terminal bloqueado por {config.BLOQUEIO_SEG:.0f}s após {config.MAX_TENTATIVAS_FALHAS} falhas",
            )
        self.confirmador.limpar()

    def passo(self, frame: np.ndarray, principal: RostoProcessado | None, n_rostos: int) -> None:
        """Avança a máquina de estados com o resultado do pipeline para este frame."""
        agora = time.time()
        if self.estado is Estado.RESULTADO:
            if agora - self._resultado_desde >= config.TEMPO_EXIBIR_RESULTADO_SEG:
                self.estado = Estado.BLOQUEADO if self.tentativas.bloqueado else Estado.AGUARDANDO
                self._decisao = None
            return
        if self.tentativas.bloqueado:
            self.estado = Estado.BLOQUEADO
            return
        if self.estado is Estado.BLOQUEADO:
            self.estado = Estado.AGUARDANDO

        if n_rostos > 1 and config.BLOQUEAR_MULTIPLOS_ROSTOS:
            if self.estado in (Estado.CONFIRMANDO, Estado.LIVENESS):
                self._finalizar(Decisao(Resultado.NEGADO_MULTIPLOS, None, self.nivel_exigido,
                                        "Mais de uma pessoa diante do terminal."), frame)
            self.confirmador.limpar()
            return

        if principal is None:
            self.orientacao = ""
            if self.estado is Estado.LIVENESS:
                self.desafio.atualizar(None)
                if self.desafio.etapa is EtapaLiveness.FALHOU:
                    self._finalizar(Decisao(Resultado.NEGADO_LIVENESS, self._ident_confirmada, self.nivel_exigido,
                                            "Prova de vida não concluída."), frame)
            else:
                self.estado = Estado.AGUARDANDO
                self.confirmador.limpar()
            return

        if self.estado in (Estado.AGUARDANDO, Estado.CONFIRMANDO):
            # Entrada que não serve (rosto virado, inclinado, cabeça baixa, borrado) não é
            # avaliada: o frame é ignorado, sem contar como tentativa nem como falha.
            self.orientacao = principal.rosto.problema_pose() or (
                "" if principal.qualidade.aprovada else f"Ajuste: {principal.qualidade.motivo}")
            if self.orientacao:
                return
            self.estado = Estado.CONFIRMANDO
            ident = self.reconhecedor.identificar(principal.embedding)
            confirmada = self.confirmador.adicionar(ident)
            if confirmada is None:
                return
            self._ident_confirmada = confirmada
            if confirmada.reconhecido and self.liveness_ativo:
                self.desafio.iniciar()
                self.estado = Estado.LIVENESS
            else:
                self._finalizar(decidir_acesso(confirmada, self.nivel_exigido), frame)
            return

        if self.estado is Estado.LIVENESS:
            self.orientacao = ""
            atual = self.reconhecedor.identificar(principal.embedding)
            confirmada = self._ident_confirmada
            if (confirmada is None or confirmada.usuario is None or not atual.reconhecido
                    or atual.usuario is None or atual.usuario.id != confirmada.usuario.id):
                self._ident_confirmada = None
                self._finalizar(Decisao(Resultado.NEGADO_LIVENESS, None, self.nivel_exigido,
                                        "Identidade não confirmada durante a prova de vida. Tente novamente."), frame)
                return

            etapa = self.desafio.atualizar(principal.rosto.yaw())
            if etapa is EtapaLiveness.APROVADO:
                self._ident_confirmada = atual
                self._finalizar(decidir_acesso(atual, self.nivel_exigido), frame)
            elif etapa is EtapaLiveness.FALHOU:
                self._finalizar(Decisao(Resultado.NEGADO_LIVENESS, self._ident_confirmada, self.nivel_exigido,
                                        "Prova de vida falhou (rosto estático?)."), frame)

    @property
    def decisao_atual(self) -> Decisao | None:
        return self._decisao

    def identificacao_atual(self, principal: RostoProcessado | None) -> Identificacao | None:
        if self.estado in (Estado.LIVENESS, Estado.RESULTADO):
            return self._ident_confirmada
        if principal is not None:
            return self.reconhecedor.identificar(principal.embedding)
        return None

    def encerrar_resultado(self) -> None:
        """Fecha o RESULTADO antes do tempo (a área liberada foi encerrada): volta a aguardar, ou
        fica bloqueado se o controle de tentativas ainda estiver bloqueado."""
        if self.estado is Estado.RESULTADO:
            self._decisao = None
            self.estado = Estado.BLOQUEADO if self.tentativas.bloqueado else Estado.AGUARDANDO
            self.confirmador.limpar()

    def definir_nivel(self, nivel: int) -> None:
        self.nivel_exigido = nivel
        self.confirmador.limpar()
        if self.estado is not Estado.RESULTADO:
            self.estado = Estado.AGUARDANDO

    def status(self) -> dict:
        """Resumo do estado para interfaces (sem depender do OpenCV)."""
        d = self._decisao
        return {
            "estado": self.estado.value,
            "nivel_exigido": self.nivel_exigido,
            "area": config.AREAS[self.nivel_exigido],
            "progresso_confirmacao": self.confirmador.progresso,
            "orientacao": self.orientacao if self.estado in (Estado.AGUARDANDO, Estado.CONFIRMANDO) else "",
            "liveness_instrucao": self.desafio.instrucao if self.estado is Estado.LIVENESS else "",
            "liveness_restante": self.desafio.tempo_restante if self.estado is Estado.LIVENESS else 0.0,
            "bloqueado_restante": self.tentativas.segundos_restantes,
            "decisao": None if d is None else {
                "resultado": d.resultado.value, "concedido": d.concedido, "mensagem": d.mensagem,
                "nome": d.identificacao.rotulo if d.identificacao else None,
                "similaridade": d.identificacao.similaridade if d.identificacao else None,
            },
            "galeria": self.reconhecedor.total_amostras,
        }

    # ------------------------------------------------------------------ HUD
    def desenhar(self, frame: np.ndarray, res, fps: float) -> np.ndarray:
        tela = frame.copy()
        area = config.AREAS[self.nivel_exigido]
        linhas = [(f"COFRE MMA  |  Area: {area}  (nivel {self.nivel_exigido})", hud.BRANCO)]
        for i, rp in enumerate(res.rostos):
            cor, rotulo = hud.AMARELO, "..."
            if i == 0 and self.estado in (Estado.CONFIRMANDO, Estado.LIVENESS, Estado.RESULTADO):
                ident = self._ident_confirmada if self.estado is not Estado.CONFIRMANDO else \
                    self.reconhecedor.identificar(rp.embedding)
                if ident is not None:
                    cor = hud.VERDE if ident.reconhecido else hud.VERMELHO
                    rotulo = f"{ident.rotulo} {ident.similaridade:.2f}"
                    if ident.reconhecido:
                        rotulo += f"  N{ident.usuario.nivel}"
            elif i > 0:
                cor, rotulo = hud.VERMELHO, "extra"
            hud.caixa_rosto(tela, rp.rosto, cor, rotulo)
            hud.pontos_faciais(tela, rp.rosto)
        if self.estado in (Estado.AGUARDANDO, Estado.CONFIRMANDO) and self.orientacao:
            linhas.append((self.orientacao, hud.LARANJA))
        elif self.estado is Estado.AGUARDANDO:
            linhas.append(("Aguardando: posicione-se de frente para a camera", hud.AMARELO))
        elif self.estado is Estado.CONFIRMANDO:
            linhas.append((f"Confirmando identidade... {int(self.confirmador.progresso * 100)}%", hud.AZUL))
            if res.principal is not None:
                ident = self.reconhecedor.identificar(res.principal.embedding)
                hud.barra_similaridade(tela, (12, 76), 220, ident.similaridade, config.LIMIAR_COSSENO)
        elif self.estado is Estado.LIVENESS:
            linhas.append((f"Prova de vida: {self.desafio.instrucao}  ({self.desafio.tempo_restante:.0f}s)", hud.LARANJA))
            if res.principal is not None:
                yaw = res.principal.rosto.yaw()
                linhas.append((f"yaw = {yaw:+.2f}", hud.CINZA))
        elif self.estado is Estado.BLOQUEADO:
            linhas.append((f"TERMINAL BLOQUEADO por {self.tentativas.segundos_restantes:.0f}s", hud.VERMELHO))
        if self.estado is Estado.RESULTADO and self._decisao is not None:
            d = self._decisao
            hud.faixa_resultado(tela, ("ACESSO CONCEDIDO: " if d.concedido else "ACESSO NEGADO: ") + d.mensagem,
                                hud.VERDE if d.concedido else hud.VERMELHO)
        hud.painel_topo(tela, linhas)
        extras = "ON" if self.liveness_ativo else "OFF"
        hud.rodape(tela, f"[1][2][3] area  [l] liveness:{extras}  [d] didatico  [r] recarregar  [q] sair   fps {fps:.0f}  "
                         f"galeria {self.reconhecedor.total_amostras} amostras")
        return tela

    # ------------------------------------------------------------------ loop
    def executar(self) -> None:
        janela = "Autenticacao - cofre MMA"
        with FonteCamera() as cam:
            for frame in cam.frames():
                res = self.pipeline.processar(frame)
                self.passo(frame, res.principal, len(res.rostos))
                tela = self.desenhar(frame, res, cam.fps_medido)
                cv2.imshow(janela, tela)
                if self.didatico:
                    cv2.imshow("Pipeline (5 fases)", hud.mosaico(res.etapas_didaticas(), lado=180, colunas=5))
                tecla = cv2.waitKey(1) & 0xFF
                if tecla in (ord("q"), 27):
                    break
                if tecla in (ord("1"), ord("2"), ord("3")):
                    self.definir_nivel(int(chr(tecla)))
                elif tecla == ord("l"):
                    self.liveness_ativo = not self.liveness_ativo
                elif tecla == ord("d"):
                    self.didatico = not self.didatico
                    if not self.didatico:
                        cv2.destroyWindow("Pipeline (5 fases)")
                elif tecla == ord("r"):
                    self.reconhecedor.recarregar()
        cv2.destroyAllWindows()


def autenticar_imagem(banco: Banco, pipeline: Pipeline, frame: np.ndarray, nivel_exigido: int,
                      registrar_log: bool = True) -> tuple[Decisao, object]:
    """Autenticação 'offline' em uma imagem (testes, demonstração, scanner)."""
    reconhecedor = Reconhecedor(banco)
    res = pipeline.processar(frame)
    if len(res.rostos) > 1 and config.BLOQUEAR_MULTIPLOS_ROSTOS:
        decisao = Decisao(Resultado.NEGADO_MULTIPLOS, None, nivel_exigido, "Mais de uma pessoa na imagem.")
    elif res.principal is None:
        decisao = Decisao(Resultado.NEGADO_DESCONHECIDO, None, nivel_exigido, "Nenhum rosto detectado.")
    else:
        decisao = decidir_acesso(reconhecedor.identificar(res.principal.embedding), nivel_exigido)
    if registrar_log:
        registrar(banco, decisao, frame)
    return decisao, res
