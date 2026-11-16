"""
Encadeia as fases 2, 3 e 4 para um frame: pré-processamento -> detecção ->
alinhamento -> embedding. Usado pelo cadastro, pela autenticação, pela
avaliação e pela demonstração didática, para que todos sigam exatamente o
mesmo caminho de processamento.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import fase2_preprocessamento as f2
from . import fase3_segmentacao as f3
from . import fase4_representacao as f4


@dataclass
class RostoProcessado:
    rosto: f3.Rosto                 # coordenadas no frame ORIGINAL
    rosto_reduzido: f3.Rosto        # coordenadas no frame reduzido (para o HUD)
    alinhado: np.ndarray            # 112x112 BGR
    embedding: np.ndarray           # (128,) float32 normalizado
    qualidade: f2.Qualidade
    recorte: np.ndarray             # recorte simples com margem (fotos/evidências)


@dataclass
class ResultadoPipeline:
    pre: f2.ResultadoPreprocessamento
    rostos: list[RostoProcessado] = field(default_factory=list)

    @property
    def principal(self) -> RostoProcessado | None:
        return self.rostos[0] if self.rostos else None

    def etapas_didaticas(self) -> dict[str, np.ndarray]:
        """Imagens de todas as fases para o painel didático."""
        etapas = dict(self.pre.etapas)
        p = self.principal
        if p is not None:
            marcado = f3.desenhar_pontos(self.pre.equalizada, p.rosto_reduzido)
            x, y, w, h = p.rosto_reduzido.caixa
            import cv2
            cv2.rectangle(marcado, (x, y), (x + w, y + h), (0, 255, 0), 2)
            etapas["3 deteccao+pontos"] = marcado
            etapas["3 recorte"] = p.recorte
            etapas["3 alinhado 112x112"] = p.alinhado
            cinza = f2.converter_cinza(p.alinhado)
            etapas["4 LBP (textura)"] = f4.lbp_mapa(cinza)
            etapas["4 embedding 128-d"] = _embedding_como_imagem(p.embedding)
        return etapas


def _embedding_como_imagem(emb: np.ndarray, altura: int = 40) -> np.ndarray:
    """Visualiza o vetor de 128 dimensões como uma faixa de intensidades."""
    v = emb.reshape(1, -1)
    v = (v - v.min()) / ((v.max() - v.min()) or 1.0)
    faixa = (v * 255).astype(np.uint8)
    return np.repeat(faixa, altura, axis=0)


class Pipeline:
    def __init__(self):
        self.detector = f3.DetectorFacial()
        self.extrator = f4.ExtratorCaracteristicas()

    def processar(self, frame: np.ndarray, extrair_embedding: bool = True) -> ResultadoPipeline:
        pre = f2.preprocessar(frame)                         # fase 2
        rostos_red = self.detector.detectar(pre.equalizada)  # fase 3 (no frame reduzido)
        resultado = ResultadoPipeline(pre=pre)
        for rr in rostos_red:
            rosto = rr.escalar(1.0 / pre.escala) if pre.escala != 1.0 else rr
            recorte = f3.recortar(frame, rosto)
            alinhado = self.extrator.alinhar(frame, rosto)   # fase 3 (alinhamento)
            qualidade = f2.avaliar_qualidade(alinhado)
            emb = self.extrator.extrair(alinhado) if extrair_embedding else np.zeros(128, np.float32)  # fase 4
            resultado.rostos.append(RostoProcessado(rosto, rr, alinhado, emb, qualidade, recorte))
        return resultado
