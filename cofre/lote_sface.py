"""Fase 4 (representação e descrição): descritores SFace em lote.

As análises do laboratório (robustez, sensibilidade por oclusão, validação das medidas de
qualidade) pedem dezenas de descritores de uma vez. Este módulo carrega a sua própria cópia da
rede SFace, com lock próprio, e calcula o lote inteiro em uma inferência. O extrator do núcleo
(`fase4_representacao.ExtratorCaracteristicas`), usado pelo terminal e pelo cadastro, não é tocado.

Além do descritor normalizado (o mesmo valor que o núcleo calcula para a mesma imagem alinhada),
devolve a norma da saída crua da rede, que o núcleo descarta ao normalizar: ela serve de indício
informativo da qualidade do rosto.
"""

from __future__ import annotations

import threading
from typing import Sequence

import cv2
import numpy as np

from . import config

DIMENSAO = 128
LADO = 112                      # lado da imagem alinhada que a rede recebe


class LoteSFace:
    """Rede SFace própria deste módulo (cv2.dnn.readNetFromONNX), com lock próprio. Não toca no extrator do núcleo."""

    _instancia: "LoteSFace | None" = None
    _lock_instancia = threading.Lock()

    def __init__(self, modelo=config.MODELO_RECONHECIMENTO):
        if not modelo.exists():
            raise FileNotFoundError(f"Modelo de reconhecimento não encontrado: {modelo}")
        self._rede = cv2.dnn.readNetFromONNX(str(modelo))
        self._lock = threading.Lock()   # a rede não aceita duas inferências ao mesmo tempo

    @classmethod
    def instancia(cls) -> "LoteSFace":
        """Instância única, criada no primeiro uso (nunca na importação do módulo)."""
        with cls._lock_instancia:
            if cls._instancia is None:
                cls._instancia = cls()
            return cls._instancia

    def embeddings(self, alinhados: Sequence[np.ndarray], tamanho_lote: int = 32,
                   sinal=None) -> tuple[np.ndarray, np.ndarray]:
        """Descritores de rostos já alinhados (112x112 BGR), na ordem recebida.

        Devolve `(E, normas)`: `E` float32 (N, 128) com cada linha L2-normalizada e `normas` float32 (N,)
        com a norma da saída crua da rede. Com `sinal` (o de um trabalho em segundo plano), confere o
        cancelamento antes de cada lote."""
        n = len(alinhados)
        cruas = np.zeros((n, DIMENSAO), dtype=np.float32)
        for inicio in range(0, n, tamanho_lote):
            if sinal is not None:
                sinal.conferir()
            lote = list(alinhados[inicio:inicio + tamanho_lote])
            blob = cv2.dnn.blobFromImages(lote, 1.0, (LADO, LADO), (0, 0, 0), swapRB=True, crop=False)
            with self._lock:
                self._rede.setInput(blob)
                saida = self._rede.forward()
            cruas[inicio:inicio + len(lote)] = saida.reshape(len(lote), -1)
        # a mesma conta do núcleo, linha a linha (norma do vetor e divisão em float32): mesmo resultado
        normas = np.array([np.linalg.norm(linha) for linha in cruas], dtype=np.float32)
        divisor = np.where(normas > 0, normas, np.float32(1.0))[:, None]
        return cruas / divisor, normas
