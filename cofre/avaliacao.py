"""
Avaliação quantitativa do reconhecedor em um conjunto rotulado de imagens.

Estrutura esperada:  pasta/<nome_da_pessoa>/*.jpg

Para todos os pares de imagens calcula a similaridade do cosseno e separa em
pares genuínos (mesma pessoa) e impostores (pessoas diferentes). Reporta, para o
limiar configurado e para uma varredura de limiares, as taxas:
  TAR (True Accept Rate)  = genuínos aceitos / genuínos
  FAR (False Accept Rate) = impostores aceitos / impostores
  FRR = 1 - TAR
e o EER (ponto em que FAR ≈ FRR). Esses números vão direto para a dissertação.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import config
from .fase1_aquisicao import carregar_imagem, listar_imagens
from .fase4_representacao import similaridade_cosseno
from .pipeline import Pipeline


@dataclass
class ResultadoAvaliacao:
    genuinos: list[float] = field(default_factory=list)
    impostores: list[float] = field(default_factory=list)
    sem_rosto: list[str] = field(default_factory=list)
    pessoas: dict[str, int] = field(default_factory=dict)

    def taxas(self, limiar: float) -> dict[str, float]:
        g, i = np.asarray(self.genuinos), np.asarray(self.impostores)
        tar = float((g >= limiar).mean()) if g.size else float("nan")
        far = float((i >= limiar).mean()) if i.size else float("nan")
        return {"limiar": limiar, "TAR": tar, "FRR": 1 - tar, "FAR": far}

    def varredura(self, passos: int = 41) -> list[dict[str, float]]:
        return [self.taxas(t) for t in np.linspace(0.0, 1.0, passos)]

    def eer(self) -> tuple[float, float]:
        """(limiar, taxa) onde |FAR - FRR| é mínimo."""
        melhor = min(self.varredura(201), key=lambda r: abs(r["FAR"] - r["FRR"]))
        return melhor["limiar"], (melhor["FAR"] + melhor["FRR"]) / 2

    def resumo(self) -> str:
        g, i = np.asarray(self.genuinos), np.asarray(self.impostores)
        t = self.taxas(config.LIMIAR_COSSENO)
        eer_l, eer_v = self.eer()
        partes = [
            f"Pessoas: {len(self.pessoas)}  Imagens: {sum(self.pessoas.values())}  Sem rosto: {len(self.sem_rosto)}",
            f"Pares genuínos: {g.size}  (média {g.mean():.3f}, mín {g.min():.3f})" if g.size else "Pares genuínos: 0",
            f"Pares impostores: {i.size}  (média {i.mean():.3f}, máx {i.max():.3f})" if i.size else "Pares impostores: 0",
            f"Limiar configurado {t['limiar']:.3f}:  TAR {t['TAR']:.1%}  FRR {t['FRR']:.1%}  FAR {t['FAR']:.1%}",
            f"EER ≈ {eer_v:.1%} no limiar {eer_l:.3f}",
            "",
            "limiar   TAR     FAR",
        ]
        for r in self.varredura(11):
            partes.append(f"{r['limiar']:.2f}   {r['TAR']:6.1%}  {r['FAR']:6.1%}")
        return "\n".join(partes)


def avaliar_pasta(pasta: str | Path, pipeline: Pipeline | None = None) -> ResultadoAvaliacao:
    pipeline = pipeline or Pipeline()
    pasta = Path(pasta)
    res = ResultadoAvaliacao()
    embeddings: list[tuple[str, np.ndarray]] = []
    for sub in sorted(p for p in pasta.iterdir() if p.is_dir()):
        n = 0
        for img_path in listar_imagens(sub):
            r = pipeline.processar(carregar_imagem(img_path))
            if r.principal is None:
                res.sem_rosto.append(str(img_path))
                continue
            embeddings.append((sub.name, r.principal.embedding))
            n += 1
        res.pessoas[sub.name] = n
    for (pa, ea), (pb, eb) in itertools.combinations(embeddings, 2):
        s = similaridade_cosseno(ea, eb)
        (res.genuinos if pa == pb else res.impostores).append(s)
    return res
