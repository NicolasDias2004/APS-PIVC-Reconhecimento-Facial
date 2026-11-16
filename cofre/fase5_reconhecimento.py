"""
FASE 5 - RECONHECIMENTO E INTERPRETAÇÃO

Compara o descritor do rosto com a galeria de usuários cadastrados e decide:

  1. Identificação (1:N): para cada usuário, a maior similaridade do cosseno
     entre o embedding da consulta e as amostras cadastradas. O usuário com a
     maior similaridade vence, se superar o limiar (`LIMIAR_COSSENO`).
  2. Autorização: o nível do usuário é comparado com o nível exigido pela área.
     Nível do usuário >= nível exigido => acesso concedido.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from . import config
from .banco import Banco, Usuario


class Resultado(str, Enum):
    CONCEDIDO = "CONCEDIDO"
    NEGADO_NIVEL = "NEGADO_NIVEL"              # pessoa conhecida, nível insuficiente
    NEGADO_DESCONHECIDO = "NEGADO_DESCONHECIDO"  # rosto não cadastrado
    NEGADO_LIVENESS = "NEGADO_LIVENESS"        # falhou no desafio anti-fraude
    NEGADO_MULTIPLOS = "NEGADO_MULTIPLOS"      # mais de um rosto na cena
    BLOQUEADO = "BLOQUEADO"                    # terminal em bloqueio temporário


@dataclass
class Identificacao:
    usuario: Usuario | None
    similaridade: float
    segunda_similaridade: float = 0.0   # do 2º colocado (mede ambiguidade)

    @property
    def reconhecido(self) -> bool:
        return self.usuario is not None and self.similaridade >= config.LIMIAR_COSSENO

    @property
    def forte(self) -> bool:
        return self.reconhecido and self.similaridade >= config.LIMIAR_COSSENO_FORTE

    @property
    def rotulo(self) -> str:
        return self.usuario.nome if self.reconhecido else "DESCONHECIDO"


@dataclass
class Decisao:
    resultado: Resultado
    identificacao: Identificacao | None
    nivel_exigido: int
    mensagem: str

    @property
    def concedido(self) -> bool:
        return self.resultado is Resultado.CONCEDIDO


class Reconhecedor:
    """Mantém a galeria em memória (matriz N x 128) para comparação rápida."""

    def __init__(self, banco: Banco):
        self.banco = banco
        self._usuarios: list[Usuario] = []
        self._donos: np.ndarray = np.zeros(0, dtype=np.int64)   # id do usuário de cada linha
        self._matriz: np.ndarray = np.zeros((0, 128), dtype=np.float32)
        self.recarregar()

    def recarregar(self) -> None:
        self._usuarios = self.banco.listar_usuarios(apenas_ativos=True)
        linhas, donos = [], []
        for u in self._usuarios:
            for emb in self.banco.embeddings_do_usuario(u.id):
                linhas.append(emb)
                donos.append(u.id)
        if linhas:
            self._matriz = np.vstack(linhas).astype(np.float32)
            self._donos = np.asarray(donos, dtype=np.int64)
        else:
            self._matriz = np.zeros((0, 128), dtype=np.float32)
            self._donos = np.zeros(0, dtype=np.int64)

    @property
    def total_amostras(self) -> int:
        return int(self._matriz.shape[0])

    @property
    def usuarios(self) -> list[Usuario]:
        return list(self._usuarios)

    def amostra_mais_parecida(self, embedding: np.ndarray) -> np.ndarray | None:
        """Embedding da galeria mais próximo do dado (só para visualização; não decide nada)."""
        if self.total_amostras == 0:
            return None
        q = np.asarray(embedding, dtype=np.float32).reshape(-1)
        q = q / (np.linalg.norm(q) or 1.0)
        return self._matriz[int(np.argmax(self._matriz @ q))].copy()

    def identificar(self, embedding: np.ndarray) -> Identificacao:
        if self.total_amostras == 0:
            return Identificacao(None, 0.0)
        q = np.asarray(embedding, dtype=np.float32).reshape(-1)
        q = q / (np.linalg.norm(q) or 1.0)
        sims = self._matriz @ q                       # cosseno de todas as amostras
        por_usuario: dict[int, float] = {}
        for uid, s in zip(self._donos.tolist(), sims.tolist()):
            if s > por_usuario.get(uid, -1.0):
                por_usuario[uid] = s
        ordem = sorted(por_usuario.items(), key=lambda kv: kv[1], reverse=True)
        melhor_id, melhor_sim = ordem[0]
        segunda = ordem[1][1] if len(ordem) > 1 else 0.0
        usuario = next(u for u in self._usuarios if u.id == melhor_id)
        if melhor_sim < config.LIMIAR_COSSENO:
            return Identificacao(None, float(melhor_sim), float(segunda))
        return Identificacao(usuario, float(melhor_sim), float(segunda))


def decidir_acesso(ident: Identificacao | None, nivel_exigido: int) -> Decisao:
    """Aplica o esquema de permissões do enunciado."""
    area = config.AREAS.get(nivel_exigido, f"nível {nivel_exigido}")
    if ident is None or not ident.reconhecido:
        return Decisao(
            Resultado.NEGADO_DESCONHECIDO, ident, nivel_exigido,
            "Rosto não cadastrado. Acesso negado.",
        )
    u = ident.usuario
    if u.nivel >= nivel_exigido:
        return Decisao(
            Resultado.CONCEDIDO, ident, nivel_exigido,
            f"Bem-vindo(a), {u.nome}. Acesso liberado: {area}.",
        )
    return Decisao(
        Resultado.NEGADO_NIVEL, ident, nivel_exigido,
        f"{u.nome} possui nível {u.nivel} ({config.NIVEIS[u.nivel]}); "
        f"a área exige nível {nivel_exigido}.",
    )
