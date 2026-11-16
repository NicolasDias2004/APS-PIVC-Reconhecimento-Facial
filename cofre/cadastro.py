"""Fluxo de cadastro (enrollment) de usuários autorizados."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import cv2

from . import config, hud
from .banco import Banco, Usuario
from .fase1_aquisicao import FonteCamera, carregar_imagem
from .pipeline import Pipeline

# 9 poses, 2 amostras cada (AMOSTRAS_POR_CADASTRO = 18). Cobrem giro (yaw), inclinação (roll)
# e cabeça baixa/erguida (pitch): o terminal reconhece melhor quem não está perfeitamente de frente.
INSTRUCOES_POSE = [
    "Olhe para a camera",
    "Vire um pouco o rosto para a esquerda",
    "Vire um pouco o rosto para a direita",
    "Incline a cabeca para a esquerda",
    "Incline a cabeca para a direita",
    "Levante um pouco o queixo",
    "Abaixe o queixo, como se olhasse o celular",
    "Olhe para a camera de novo",
    "Sorria",
]


@dataclass
class DadosCadastro:
    nome: str
    matricula: str
    cargo: str
    nivel: int


def _pasta_fotos(usuario: Usuario) -> Path:
    pasta = config.FOTOS_DIR / f"{usuario.id:03d}_{usuario.matricula}"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def cadastrar_de_imagens(banco: Banco, pipeline: Pipeline, dados: DadosCadastro,
                         caminhos: list[str | Path]) -> tuple[Usuario, int, list[str]]:
    """Cadastra a partir de arquivos (scanner/câmera externa). Retorna (usuario, n_amostras, avisos)."""
    usuario = banco.criar_usuario(dados.nome, dados.matricula, dados.cargo, dados.nivel)
    pasta = _pasta_fotos(usuario)
    avisos, n = [], 0
    for caminho in caminhos:
        try:
            img = carregar_imagem(caminho)
        except Exception as e:  # noqa: BLE001
            avisos.append(f"{caminho}: {e}")
            continue
        res = pipeline.processar(img)
        if not res.rostos:
            avisos.append(f"{caminho}: nenhum rosto detectado")
            continue
        if len(res.rostos) > 1:
            avisos.append(f"{caminho}: {len(res.rostos)} rostos, usando o maior")
        p = res.principal
        destino = pasta / f"{n + 1:02d}_{Path(caminho).stem}.jpg"
        cv2.imwrite(str(destino), p.recorte)
        banco.adicionar_amostra(usuario.id, p.embedding, str(destino), p.qualidade.nitidez, p.qualidade.brilho)
        n += 1
    if n == 0:
        banco.remover_usuario(usuario.id)
        raise RuntimeError("Nenhuma amostra válida; cadastro cancelado. " + "; ".join(avisos))
    return usuario, n, avisos


class SessaoCadastro:
    """Lógica de cadastro por frame, independente de interface (usada pela janela OpenCV
    e pelo aplicativo desktop). Cria o usuário no início; `cancelar()` desfaz tudo."""

    def __init__(self, banco: Banco, pipeline: Pipeline, dados: DadosCadastro,
                 amostras: int = config.AMOSTRAS_POR_CADASTRO):
        self.banco = banco
        self.pipeline = pipeline
        self.dados = dados
        self.amostras = amostras
        self.usuario = banco.criar_usuario(dados.nome, dados.matricula, dados.cargo, dados.nivel)
        self.pasta = _pasta_fotos(self.usuario)
        self.capturadas = 0
        self.ultima = 0.0
        self.status = "Posicione o rosto na camera"
        self.cor = hud.AMARELO
        self.pose = INSTRUCOES_POSE[0]
        self.miniaturas: list = []      # recortes capturados (para a interface mostrar)
        self.capturou_agora = False
        self.encerrada = False

    @property
    def concluida(self) -> bool:
        return self.capturadas >= self.amostras

    @property
    def progresso(self) -> float:
        return self.capturadas / self.amostras

    def passo(self, frame, res) -> None:
        """Avalia o resultado do pipeline deste frame e captura uma amostra se for o caso."""
        self.capturou_agora = False
        if self.concluida or self.encerrada:
            return
        self.pose = INSTRUCOES_POSE[min(self.capturadas * len(INSTRUCOES_POSE) // max(1, self.amostras),
                                        len(INSTRUCOES_POSE) - 1)]
        if len(res.rostos) > 1:
            self.status, self.cor = "Apenas UMA pessoa deve aparecer", hud.VERMELHO
            return
        if not res.rostos:
            self.status, self.cor = "Posicione o rosto na camera", hud.AMARELO
            return
        p = res.principal
        q = p.qualidade
        if not q.aprovada:
            self.status, self.cor = f"Ajuste: {q.motivo} (nitidez {q.nitidez:.0f}, brilho {q.brilho:.0f})", hud.LARANJA
            return
        self.status, self.cor = f"Capturando... {self.pose}", hud.VERDE
        if time.time() - self.ultima >= config.INTERVALO_AMOSTRAS_SEG:
            emb = self.pipeline.extrator.extrair(p.alinhado)
            destino = self.pasta / f"{self.capturadas + 1:02d}.jpg"
            cv2.imwrite(str(destino), p.recorte)
            self.banco.adicionar_amostra(self.usuario.id, emb, str(destino), q.nitidez, q.brilho)
            self.capturadas += 1
            self.ultima = time.time()
            self.miniaturas.append(p.recorte)
            self.capturou_agora = True
            if self.concluida:
                self.status, self.cor = "Cadastro concluido!", hud.VERDE

    def desenhar(self, frame, res):
        """Frame com o HUD de cadastro desenhado (OpenCV)."""
        tela = frame.copy()
        if len(res.rostos) > 1:
            for r in res.rostos:
                hud.caixa_rosto(tela, r.rosto, hud.VERMELHO)
        elif res.rostos:
            p = res.principal
            hud.caixa_rosto(tela, p.rosto, self.cor, "OK" if p.qualidade.aprovada else None)
            if p.qualidade.aprovada:
                hud.pontos_faciais(tela, p.rosto)
        if self.capturou_agora:
            cv2.rectangle(tela, (0, 0), (tela.shape[1], tela.shape[0]), hud.BRANCO, 12)
        hud.painel_topo(tela, [
            (f"Cadastro: {self.dados.nome}  |  nivel {self.dados.nivel} - {config.NIVEIS[self.dados.nivel]}", hud.BRANCO),
            (self.status, self.cor),
            (f"Amostras: {self.capturadas}/{self.amostras}", hud.AZUL),
        ])
        return tela

    def cancelar(self) -> None:
        """Remove o usuário e as amostras já gravadas."""
        if not self.encerrada:
            self.encerrada = True
            self.banco.remover_usuario(self.usuario.id)

    def concluir(self) -> Usuario | None:
        """Fecha a sessão; sem nenhuma amostra o cadastro é desfeito."""
        self.encerrada = True
        if self.capturadas == 0:
            self.banco.remover_usuario(self.usuario.id)
            return None
        return self.usuario


def cadastrar_pela_camera(banco: Banco, pipeline: Pipeline, dados: DadosCadastro,
                          amostras: int = config.AMOSTRAS_POR_CADASTRO) -> Usuario | None:
    """Versão com janela OpenCV (linha de comando). ESC cancela e desfaz o cadastro."""
    sessao = SessaoCadastro(banco, pipeline, dados, amostras)
    janela = "Cadastro biometrico - cofre MMA"
    with FonteCamera() as cam:
        for frame in cam.frames():
            res = pipeline.processar(frame, extrair_embedding=False)
            sessao.passo(frame, res)
            tela = sessao.desenhar(frame, res)
            hud.rodape(tela, "ESC cancela o cadastro")
            cv2.imshow(janela, tela)
            tecla = cv2.waitKey(1) & 0xFF
            if tecla == 27:
                sessao.cancelar()
                break
            if sessao.concluida:
                hud.faixa_resultado(tela, "Cadastro concluido!", hud.VERDE)
                cv2.imshow(janela, tela)
                cv2.waitKey(1200)
                break
    cv2.destroyWindow(janela)
    return sessao.concluir()
