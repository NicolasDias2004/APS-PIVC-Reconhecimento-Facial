"""Fases 1 a 4: robustez e ablação.

Robustez: o rosto alinhado da amostra é degradado nas oito famílias de `degradacoes` (doze
intensidades cada) e cada versão é comparada, pelo cosseno, com a referência do laboratório. A
curva mostra até onde o descritor aguenta e o ponto de quebra diz onde ela cruza o limiar em vigor.

Ablação: duas perguntas de "para que serve esta fase", respondidas nas fotos de teste: o alinhamento
(fase 3) com a cabeça inclinada e a equalização da fase 2 com a cena escura.

Tudo é sintético, rotulado como tal, e não muda o pipeline: as imagens degradadas existem só em memória.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np

from . import degradacoes
from . import fase2_preprocessamento as f2
from . import fase3_segmentacao as f3
from .degradacoes import NIVEIS_PADRAO
from .lote_sface import LoteSFace


@dataclass(frozen=True)
class CurvaRobustez:
    familia: str
    nome: str
    niveis: tuple[float, ...]
    rotulos: tuple[str, ...]
    similaridade: tuple[float, ...]
    quebra_nivel: float | None
    quebra_rotulo: str                  # "" quando não cruza o limiar


def _conferir(sinal) -> None:
    if sinal is not None:
        sinal.conferir()


def _normalizar(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def similaridade_degradada(alinhado, referencia: np.ndarray, familia: str, nivel: float, semente: int = 0) -> float:
    """Cosseno entre o rosto degradado e a referência (embedding)."""
    img = degradacoes.aplicar(alinhado, familia, nivel, semente)
    e, _ = LoteSFace.instancia().embeddings([img])
    return float(e[0] @ _normalizar(referencia))


def ponto_de_quebra(niveis, similaridades, limiar: float) -> float | None:
    """Primeiro nível em que a curva fica abaixo do limiar, por interpolação linear; None se não cruzar."""
    n = list(map(float, niveis))
    s = list(map(float, similaridades))
    if not s:
        return None
    if s[0] < limiar:
        return n[0]
    for i in range(1, len(s)):
        if s[i] < limiar <= s[i - 1]:
            frac = (s[i - 1] - limiar) / (s[i - 1] - s[i]) if s[i - 1] != s[i] else 0.0
            return n[i - 1] + frac * (n[i] - n[i - 1])
    return None


def varrer(alinhado, referencia: np.ndarray, limiar: float, familias: Sequence[str] | None = None,
           niveis: Sequence[float] = NIVEIS_PADRAO, sinal=None) -> list[CurvaRobustez]:
    """Uma curva por família: as intensidades num lote só do `LoteSFace`, comparadas com a referência."""
    chaves = list(familias) if familias is not None else list(degradacoes.FAMILIAS)
    ref = _normalizar(referencia)
    lote = LoteSFace.instancia()
    curvas = []
    for i, chave in enumerate(chaves):
        _conferir(sinal)
        fam = degradacoes.FAMILIAS[chave]
        imagens = [degradacoes.aplicar(alinhado, chave, nv) for nv in niveis]
        e, _ = lote.embeddings(imagens, sinal=sinal)
        sims = tuple(float(x) for x in e @ ref)
        quebra = ponto_de_quebra(niveis, sims, limiar)
        curvas.append(CurvaRobustez(familia=chave, nome=fam.nome, niveis=tuple(float(n) for n in niveis),
                                    rotulos=tuple(fam.rotulo(n) for n in niveis), similaridade=sims,
                                    quebra_nivel=quebra, quebra_rotulo="" if quebra is None else fam.rotulo(quebra)))
        if sinal is not None:
            sinal.progresso(i + 1, len(chaves))
    return curvas


def _maior_rosto(frame: np.ndarray, pipeline):
    """Detecta como o pipeline (fase 2 completa e YuNet no quadro reduzido); rosto no quadro original."""
    pre = f2.preprocessar(frame)
    rostos = pipeline.detector.detectar(pre.equalizada)
    if not rostos:
        return None
    r = rostos[0]
    return r.escalar(1.0 / pre.escala) if pre.escala != 1.0 else r


def _embedding_de(frame: np.ndarray, pipeline) -> np.ndarray | None:
    rosto = _maior_rosto(frame, pipeline)
    if rosto is None:
        return None
    return pipeline.extrator.extrair(pipeline.extrator.alinhar(frame, rosto))


def ablacao_alinhamento(pares: Sequence[tuple[np.ndarray, np.ndarray]], pipeline, limiar: float,
                        graus: float = 20.0, sinal=None) -> dict:
    """Cabeça inclinada `graus`: similaridade com e sem o alinhamento da fase 3.

    Cada par é (quadro da sonda, referência), da mesma pessoa; a referência pode ser um quadro ou um
    embedding. Sem alinhamento, o recorte da caixa vai direto para 112×112."""
    nivel = graus / degradacoes.FAMILIAS["rotacao"].fim
    com, sem, perdidos = [], [], 0
    for sonda, referencia in pares:
        _conferir(sinal)
        ref = referencia if np.asarray(referencia).ndim == 1 else _embedding_de(referencia, pipeline)
        girada = degradacoes.aplicar_no_quadro(sonda, "rotacao", nivel)
        rosto = _maior_rosto(girada, pipeline)
        if ref is None or rosto is None:
            perdidos += 1
            continue
        ref = _normalizar(ref)
        alinhado = pipeline.extrator.alinhar(girada, rosto)
        recorte = cv2.resize(f3.recortar(girada, rosto, margem=0.0), (112, 112), interpolation=cv2.INTER_LINEAR)
        com.append(float(pipeline.extrator.extrair(alinhado) @ ref))
        sem.append(float(pipeline.extrator.extrair(recorte) @ ref))
    return {"n": len(com), "perdidos": perdidos, "graus": float(graus), "com": com, "sem": sem,
            "abaixo_com": sum(s < limiar for s in com), "abaixo_sem": sum(s < limiar for s in sem)}


def ablacao_clahe(frames: Sequence[np.ndarray], pipeline, ganhos: Sequence[float] = (0.05, 0.06, 0.10, 0.20),
                  sinal=None) -> dict:
    """Cena escura (ganho de brilho): rostos detectados com a fase 2 completa e só com a redução."""
    completa, reducao = [], []
    for ganho in ganhos:
        k_completa = k_reducao = 0
        for frame in frames:
            _conferir(sinal)
            q = cv2.convertScaleAbs(frame, alpha=float(ganho))
            k_completa += bool(pipeline.detector.detectar(f2.preprocessar(q).equalizada))
            k_reducao += bool(pipeline.detector.detectar(f2.redimensionar(q)[0]))
        completa.append(k_completa)
        reducao.append(k_reducao)
    return {"n": len(frames), "ganhos": [float(g) for g in ganhos], "completa": completa, "reducao": reducao}
