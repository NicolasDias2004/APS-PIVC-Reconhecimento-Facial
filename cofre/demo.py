"""Demonstração didática: roda o pipeline completo em uma imagem e monta o painel das 5 fases."""

from __future__ import annotations

from pathlib import Path

import cv2

from . import config, hud
from .banco import Banco
from .fase1_aquisicao import carregar_imagem
from .fase5_reconhecimento import Reconhecedor, decidir_acesso
from .pipeline import Pipeline


def demonstrar_imagem(caminho: str | Path, pipeline: Pipeline, banco: Banco | None = None,
                      nivel_exigido: int = 3, salvar_em: Path | None = None, exibir: bool = True) -> Path | None:
    frame = carregar_imagem(caminho)
    res = pipeline.processar(frame)
    painel = hud.mosaico(res.etapas_didaticas(), lado=240, colunas=4)
    linhas = [f"Fase 1 aquisicao: {Path(caminho).name}  {frame.shape[1]}x{frame.shape[0]}",
              f"Fase 2/3: {len(res.rostos)} rosto(s) detectado(s) no frame reduzido {res.pre.reduzida.shape[1]}px"]
    p = res.principal
    if p is not None:
        linhas.append(f"Fase 3: caixa {p.rosto.caixa}  conf {p.rosto.confianca:.2f}  yaw {p.rosto.yaw():+.2f}  "
                      f"nitidez {p.qualidade.nitidez:.0f} brilho {p.qualidade.brilho:.0f}")
        linhas.append(f"Fase 4: embedding 128-d  norma {float((p.embedding ** 2).sum()) ** 0.5:.2f}")
        if banco is not None:
            ident = Reconhecedor(banco).identificar(p.embedding)
            d = decidir_acesso(ident, nivel_exigido)
            linhas.append(f"Fase 5: {ident.rotulo} sim={ident.similaridade:.3f} (limiar {config.LIMIAR_COSSENO}) "
                          f"-> {d.resultado.value}")
    rodape = 24 * len(linhas) + 16
    import numpy as np
    base = np.full((painel.shape[0] + rodape, painel.shape[1], 3), 20, np.uint8)
    base[:painel.shape[0]] = painel
    y = painel.shape[0] + 24
    for l in linhas:
        hud.texto(base, l, (10, y), 0.55, hud.BRANCO, 1)
        y += 24
    destino = None
    if salvar_em is not None:
        salvar_em.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(salvar_em), base)
        destino = salvar_em
    if exibir:
        cv2.imshow("Pipeline - 5 fases do PDI", base)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return destino
