"""Fases 1 a 5: protocolos de avaliação.

Cada protocolo monta o conjunto de escores genuínos e impostores com uma ficha (pessoas, imagens,
pares) e os selos que viajam com as figuras. Nada é treinado e nenhum vetor sai daqui: só escores,
contagens e a ficha.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import amostra_lab, leitura_ro
from . import fase2_preprocessamento as f2
from . import fase4_representacao as f4
from .fase1_aquisicao import carregar_imagem

SELO_MESMA_SESSAO = "Mesma sessão · otimista"
SELO_DEMONSTRACAO = "Base de demonstração"
DESCRITORES_LBP = ("LBP · cosseno", "LBP · qui-quadrado")


@dataclass
class Protocolo:
    chave: str                                            # "fotos_teste" | "pasta" | "galeria"
    genuinos: np.ndarray                                  # escores (cosseno do SFace)
    impostores: np.ndarray
    ficha: dict                                           # pessoas, imagens, sem_rosto, pares_genuinos, pares_impostores, amostras_por_pessoa
    selos: list[str] = field(default_factory=list)
    descritores: dict[str, tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)


def _separar(escores: np.ndarray, donos: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Triângulo superior da matriz de escores, separado em mesmo dono (genuíno) e donos diferentes."""
    a, b = np.triu_indices(donos.size, k=1)
    mesmo = donos[a] == donos[b]
    valores = escores[a, b].astype(np.float64)
    return valores[mesmo], valores[~mesmo]


def _ficha(donos: np.ndarray, imagens: int, sem_rosto: int, g: np.ndarray, i: np.ndarray) -> dict:
    _, contagens = np.unique(donos, return_counts=True) if donos.size else (None, np.array([], dtype=int))
    return {"pessoas": int(contagens.size), "imagens": int(imagens), "sem_rosto": int(sem_rosto),
            "pares_genuinos": int(g.size), "pares_impostores": int(i.size),
            "amostras_por_pessoa": [int(c) for c in contagens]}


def _qui_quadrado(h: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Similaridade 1 / (1 + χ²) entre os histogramas dos pares (a, b), em blocos para limitar a memória."""
    saida = np.empty(a.size, dtype=np.float64)
    passo = max(1, 2_000_000 // max(1, h.shape[1]))
    for ini in range(0, a.size, passo):
        x, y = h[a[ini:ini + passo]], h[b[ini:ini + passo]]
        soma = x + y
        chi = 0.5 * np.divide((x - y) ** 2, soma, out=np.zeros_like(soma), where=soma > 0).sum(axis=1)
        saida[ini:ini + passo] = 1 / (1 + chi)
    return saida


def de_pasta(pasta: Path, pipeline, chave: str = "pasta", sinal=None) -> Protocolo:
    conjunto = amostra_lab.pasta_rotulada(pasta)
    caminhos = [(p, c) for p, (_, lista) in enumerate(conjunto.items()) for c in lista]
    embeddings, histogramas, donos = [], [], []
    sem_rosto = 0
    for n, (pessoa, caminho) in enumerate(caminhos):
        if sinal is not None:
            sinal.conferir()
            sinal.progresso(n, len(caminhos))
        r = pipeline.processar(carregar_imagem(caminho))
        if r.principal is None:
            sem_rosto += 1
            continue
        embeddings.append(np.asarray(r.principal.embedding, dtype=np.float64))
        histogramas.append(np.asarray(f4.lbp_histograma(f2.converter_cinza(r.principal.alinhado)), dtype=np.float64))
        donos.append(pessoa)
    if sinal is not None:
        sinal.progresso(len(caminhos), len(caminhos))
    donos_a = np.asarray(donos, dtype=np.int64)
    descritores: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if donos_a.size:
        e = np.vstack(embeddings)
        g, i = _separar(e @ e.T, donos_a)
        h = np.vstack(histogramas)
        normas = np.linalg.norm(h, axis=1, keepdims=True)
        hn = np.divide(h, normas, out=np.zeros_like(h), where=normas > 0)
        descritores[DESCRITORES_LBP[0]] = _separar(hn @ hn.T, donos_a)
        a, b = np.triu_indices(donos_a.size, k=1)
        chi = _qui_quadrado(h, a, b)
        mesmo = donos_a[a] == donos_a[b]
        descritores[DESCRITORES_LBP[1]] = (chi[mesmo], chi[~mesmo])
    else:
        g = i = np.zeros(0, dtype=np.float64)
    selos = [f"Fotos de teste · {len(caminhos)} imagens"] if chave == "fotos_teste" else []
    return Protocolo(chave, g, i, _ficha(donos_a, len(caminhos), sem_rosto, g, i), selos, descritores)


def de_galeria(caminho_db, demonstracao: bool = False, sinal=None) -> Protocolo:
    gal = leitura_ro.galeria(caminho_db, apenas_ativos=True)
    if sinal is not None:
        sinal.conferir()
    m = np.asarray(gal.matriz, dtype=np.float64)
    if m.shape[0]:
        g, i = _separar(m @ m.T, np.asarray(gal.donos, dtype=np.int64))
    else:
        g = i = np.zeros(0, dtype=np.float64)
    selos = [SELO_DEMONSTRACAO] if demonstracao else [SELO_MESMA_SESSAO]
    return Protocolo("galeria", g, i, _ficha(np.asarray(gal.donos), int(m.shape[0]), 0, g, i), selos, {})
