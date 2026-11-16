"""
Anti-fraude (prova de vida) simples, baseado em geometria dos pontos faciais.

Uma foto impressa ou exibida no celular reproduz um rosto estático. O desafio
pede que a pessoa vire a cabeça para os dois lados; a razão nariz/olhos (yaw)
muda de sinal apenas em um rosto tridimensional real que gira na frente da
câmera. Não é um método infalível (um vídeo pode enganar), mas eleva a barreira
contra o ataque mais comum e é explicável na dissertação.
"""

from __future__ import annotations

import time
from enum import Enum

from . import config


class EtapaLiveness(str, Enum):
    INATIVO = "INATIVO"
    VIRAR_ESQUERDA = "VIRAR_ESQUERDA"
    VIRAR_DIREITA = "VIRAR_DIREITA"
    VOLTAR_CENTRO = "VOLTAR_CENTRO"
    APROVADO = "APROVADO"
    FALHOU = "FALHOU"


class DesafioMovimento:
    """Máquina de estados: esquerda -> direita -> centro, dentro do tempo limite."""

    def __init__(self, limiar: float = config.LIVENESS_LIMIAR_YAW, timeout: float = config.LIVENESS_TIMEOUT_SEG,
                 relogio=time.time):
        self.limiar = limiar
        self.timeout = timeout
        self._relogio = relogio
        self.etapa = EtapaLiveness.INATIVO
        self._inicio = 0.0
        self.historico: list[float] = []

    def iniciar(self) -> None:
        self.etapa = EtapaLiveness.VIRAR_ESQUERDA
        self._inicio = self._relogio()
        self.historico = []

    @property
    def ativo(self) -> bool:
        return self.etapa in (EtapaLiveness.VIRAR_ESQUERDA, EtapaLiveness.VIRAR_DIREITA, EtapaLiveness.VOLTAR_CENTRO)

    @property
    def tempo_restante(self) -> float:
        return max(0.0, self.timeout - (self._relogio() - self._inicio))

    @property
    def instrucao(self) -> str:
        return {
            EtapaLiveness.VIRAR_ESQUERDA: "Vire o rosto para a ESQUERDA",
            EtapaLiveness.VIRAR_DIREITA: "Agora vire para a DIREITA",
            EtapaLiveness.VOLTAR_CENTRO: "Olhe para a camera",
            EtapaLiveness.APROVADO: "Prova de vida OK",
            EtapaLiveness.FALHOU: "Prova de vida falhou",
            EtapaLiveness.INATIVO: "",
        }[self.etapa]

    def atualizar(self, yaw: float | None) -> EtapaLiveness:
        """Recebe o yaw do frame atual (None se nenhum rosto) e avança a máquina."""
        if not self.ativo:
            return self.etapa
        if self.tempo_restante <= 0:
            self.etapa = EtapaLiveness.FALHOU
            return self.etapa
        if yaw is None:
            return self.etapa
        self.historico.append(yaw)
        if self.etapa is EtapaLiveness.VIRAR_ESQUERDA and yaw <= -self.limiar:
            self.etapa = EtapaLiveness.VIRAR_DIREITA
        elif self.etapa is EtapaLiveness.VIRAR_DIREITA and yaw >= self.limiar:
            self.etapa = EtapaLiveness.VOLTAR_CENTRO
        elif self.etapa is EtapaLiveness.VOLTAR_CENTRO and abs(yaw) < self.limiar / 2:
            self.etapa = EtapaLiveness.APROVADO
        return self.etapa


class ControleTentativas:
    """Bloqueio temporário do terminal após várias negações seguidas (força bruta)."""

    def __init__(self, max_falhas: int = config.MAX_TENTATIVAS_FALHAS, janela: float = config.JANELA_FALHAS_SEG,
                 bloqueio: float = config.BLOQUEIO_SEG, relogio=time.time):
        self.max_falhas = max_falhas
        self.janela = janela
        self.bloqueio = bloqueio
        self._relogio = relogio
        self._falhas: list[float] = []
        self._bloqueado_ate = 0.0

    def registrar_falha(self) -> bool:
        """Retorna True se esta falha acionou o bloqueio."""
        agora = self._relogio()
        self._falhas = [t for t in self._falhas if agora - t <= self.janela]
        self._falhas.append(agora)
        if len(self._falhas) >= self.max_falhas:
            self._bloqueado_ate = agora + self.bloqueio
            self._falhas = []
            return True
        return False

    def registrar_sucesso(self) -> None:
        self._falhas = []

    @property
    def bloqueado(self) -> bool:
        return self._relogio() < self._bloqueado_ate

    @property
    def segundos_restantes(self) -> float:
        return max(0.0, self._bloqueado_ate - self._relogio())
