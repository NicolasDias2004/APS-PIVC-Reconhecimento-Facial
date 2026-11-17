"""Fases 2 a 5: validação de medidas de qualidade.

Pergunta: alguma das medidas de `cofre.qualidade` prevê o erro do reconhecimento? O protocolo é
sintético: cada imagem rotulada (fotos de teste ou uma pasta com uma subpasta por pessoa) é degradada
em algumas famílias e intensidades; os pares genuínos (mesma pessoa, imagens de origem diferentes)
são ordenados pela qualidade do par (a pior das duas) e descartados do pior para o melhor. Se a
medida presta, a taxa de falso não casamento (FNMR) no limiar cai mais rápido que descartando ao
acaso (curva erro × descarte, ERC). O ρ de Spearman resume a mesma relação por amostra.

Leitura informativa: nenhuma destas medidas é usada no cadastro nem na autenticação. Os descritores
ficam dentro de `ConjuntoAumentado` e nunca saem de `avaliar`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from . import amostra_lab, degradacoes, qualidade
from .lote_sface import LoteSFace

FRACOES_PADRAO = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
EMBARALHAMENTOS = 20
NOMES = {"norma": "Norma do vetor", "nitidez": "Nitidez (Laplaciano)", "ruido": "Ruído estimado",
         "exposicao": "Exposição", "simetria": "Simetria", "pose": "Pose", "resolucao": "Resolução",
         "confianca": "Confiança do detector"}
_COM_ARTIGO = {"norma": "a norma do vetor", "nitidez": "a nitidez", "ruido": "o ruído estimado",
               "exposicao": "a exposição", "simetria": "a simetria", "pose": "a pose", "resolucao": "a resolução",
               "confianca": "a confiança do detector"}


@dataclass
class ConjuntoAumentado:
    pessoa: np.ndarray                  # (N,) int: índice da pessoa
    imagem: np.ndarray                  # (N,) int: índice da imagem de origem
    familia: list[str]
    nivel: np.ndarray
    componentes: dict[str, np.ndarray]  # chave de cofre.qualidade -> (N,) float (nota 0..1); NaN se ausente
    _embeddings: np.ndarray = field(repr=False)     # (N, 128), interno: nunca sai do módulo
    pessoas: int = 0
    imagens: int = 0


def _ler(caminho: Path) -> np.ndarray | None:
    dados = np.fromfile(str(caminho), dtype=np.uint8)
    return cv2.imdecode(dados, cv2.IMREAD_COLOR) if dados.size else None


def montar(pastas: dict[str, list[Path]], pipeline, niveis: Sequence[float] = (0.0, 0.3, 0.6, 0.9),
           familias: Sequence[str] = ("desfoque", "ruido", "escuro", "claro", "resolucao"), sinal=None) -> ConjuntoAumentado:
    """O alinhado limpo de cada imagem com rosto mais as degradações (um lote por imagem)."""
    pessoa, imagem, fam, niv = [], [], [], []
    comps: dict[str, list[float]] = {c: [] for c in qualidade.COMPONENTES}
    blocos = []
    lote = LoteSFace.instancia()
    n_img = 0
    pessoas_com_rosto = set()
    for p_idx, caminhos in enumerate(pastas.values()):
        for caminho in caminhos:
            if sinal is not None:
                sinal.conferir()
            frame = _ler(Path(caminho))
            if frame is None:
                continue
            a = amostra_lab.preparar(frame, pipeline)
            if a.alinhado is None:
                continue
            variantes = [(a.alinhado, "limpa", 0.0)]
            variantes += [(degradacoes.aplicar(a.alinhado, f, nv), f, float(nv)) for f in familias for nv in niveis if nv > 0]
            e, normas = lote.embeddings([v[0] for v in variantes], sinal=sinal)
            blocos.append(e)
            for (img, f, nv), norma in zip(variantes, normas):
                pessoa.append(p_idx)
                imagem.append(n_img)
                fam.append(f)
                niv.append(nv)
                for c, v in qualidade.componentes(img, a.rosto, float(norma)).items():
                    comps[c].append(np.nan if v is None else float(v))
            pessoas_com_rosto.add(p_idx)
            n_img += 1
    emb = np.vstack(blocos) if blocos else np.zeros((0, 128), np.float32)
    return ConjuntoAumentado(pessoa=np.array(pessoa, np.int64), imagem=np.array(imagem, np.int64), familia=fam,
                             nivel=np.array(niv, np.float64),
                             componentes={c: np.array(v, np.float64) for c, v in comps.items()},
                             _embeddings=emb, pessoas=len(pessoas_com_rosto), imagens=n_img)


def pares_genuinos(conj: ConjuntoAumentado) -> tuple[np.ndarray, np.ndarray]:
    """(escores (P,), índices (P, 2)): mesma pessoa, imagens de origem diferentes."""
    i, j = np.triu_indices(len(conj.pessoa), k=1)
    sel = (conj.pessoa[i] == conj.pessoa[j]) & (conj.imagem[i] != conj.imagem[j])
    i, j = i[sel], j[sel]
    escores = np.einsum("ij,ij->i", conj._embeddings[i], conj._embeddings[j]) if len(i) else np.zeros(0)
    return escores.astype(np.float64), np.stack([i, j], axis=1) if len(i) else np.zeros((0, 2), np.int64)


def curva_erro_descarte(escores, qualidade_par, limiar: float,
                        fracoes: Sequence[float] = FRACOES_PADRAO) -> list[tuple[float, float, int, int]]:
    """(fração descartada, FNMR, k, n): descarta os pares de pior qualidade primeiro e recalcula."""
    s = np.asarray(escores, np.float64)
    q = np.asarray(qualidade_par, np.float64)
    q = np.where(np.isnan(q), -np.inf, q)               # sem medida conta como a pior
    ordem = np.argsort(q, kind="stable")
    s = s[ordem]
    saida = []
    for f in fracoes:
        resto = s[int(np.floor(f * len(s))):]
        k, n = int((resto < limiar).sum()), int(len(resto))
        saida.append((float(f), k / n if n else float("nan"), k, n))
    return saida


def _postos(x: np.ndarray) -> np.ndarray:
    ordem = np.argsort(x, kind="stable")
    postos = np.empty(len(x), np.float64)
    postos[ordem] = np.arange(1, len(x) + 1)
    _, inverso, contagem = np.unique(x, return_inverse=True, return_counts=True)
    soma = np.bincount(inverso, weights=postos)
    return (soma / contagem)[inverso]


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Correlação de postos (empates pela média); NaN com menos de 3 pontos ou sem variação."""
    x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    if len(x) < 3:
        return float("nan")
    rx, ry = _postos(x), _postos(y)
    rx, ry = rx - rx.mean(), ry - ry.mean()
    den = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / den) if den > 0 else float("nan")


def _escore_por_amostra(conj: ConjuntoAumentado) -> np.ndarray:
    """Cosseno de cada amostra com o descritor limpo de outra imagem da mesma pessoa (NaN se não houver)."""
    limpas = {int(conj.imagem[k]): k for k in range(len(conj.imagem)) if conj.familia[k] == "limpa"}
    saida = np.full(len(conj.imagem), np.nan)
    for k in range(len(conj.imagem)):
        outra = next((idx for img, idx in limpas.items()
                      if img != conj.imagem[k] and conj.pessoa[idx] == conj.pessoa[k]), None)
        if outra is not None:
            saida[k] = float(conj._embeddings[k] @ conj._embeddings[outra])
    return saida


def _num(v: float) -> str:
    return "–" if v != v else f"{v:.2f}".replace(".", ",").replace("-", "−")


def avaliar(conj: ConjuntoAumentado, limiar: float, semente: int = 0) -> dict:
    """Curvas erro × descarte por componente, o controle aleatório e o ρ de Spearman. Só escalares."""
    escores, idx = pares_genuinos(conj)
    curvas, rho = {}, {}
    por_amostra = _escore_por_amostra(conj)
    for c in qualidade.COMPONENTES:
        v = conj.componentes[c]
        q_par = np.fmin(v[idx[:, 0]], v[idx[:, 1]]) if len(idx) else np.zeros(0)
        curvas[c] = curva_erro_descarte(escores, q_par, limiar)
        rho[c] = spearman(v, por_amostra)
    rng = np.random.default_rng(semente)
    sorteios = [curva_erro_descarte(escores, rng.random(len(escores)), limiar) for _ in range(EMBARALHAMENTOS)]
    aleatorio = [(f, float(np.nanmean([s[i][1] for s in sorteios])) if len(escores) else float("nan"), 0, n)
                 for i, (f, _, _, n) in enumerate(sorteios[0])]
    validos = {c: r for c, r in rho.items() if r == r}
    if validos:
        melhor = max(validos, key=lambda c: validos[c])
        pior = min(validos, key=lambda c: abs(validos[c]))
        if validos[melhor] >= 0.3 and melhor != pior:
            leitura = (f"Neste protocolo, {_COM_ARTIGO[melhor]} prevê o erro (ρ = {_num(validos[melhor])}); "
                       f"{_COM_ARTIGO[pior]} não (ρ = {_num(validos[pior])}).")
        else:
            leitura = (f"Neste protocolo, nenhuma medida prevê bem o erro (maior ρ = {_num(validos[melhor])}, "
                       f"{_COM_ARTIGO[melhor]}).")
    else:
        leitura = "Neste protocolo não houve amostras suficientes para medir a relação."
    ficha = {"pessoas": int(conj.pessoas), "imagens": int(conj.imagens), "amostras": int(len(conj.pessoa)),
             "pares": int(len(escores)), "semente": int(semente)}
    return {"ficha": ficha, "curvas": curvas, "aleatorio": aleatorio, "spearman": rho, "leitura": leitura}
