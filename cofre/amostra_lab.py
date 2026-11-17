"""Fases 1 a 4: composição instrumentada do pipeline.

`preparar` percorre uma imagem pelas mesmas etapas e na mesma ordem de `pipeline.Pipeline.processar`
(redução, cinza, suavização, CLAHE, detecção, alinhamento, descritor), guardando cada resultado
intermediário e o tempo de cada fase em uma `AmostraLab`, que é o que o laboratório examina.

Os parâmetros da fase 2 entram como argumento (`ParametrosEstudo`): o estudo "e se o filtro fosse
outro?" vale só para a amostra preparada e nunca altera `cofre.config`. Com os parâmetros padrão, o
rosto alinhado e o descritor são idênticos aos do núcleo.

Também é daqui que saem os conjuntos de imagens rotuladas sem nome de pessoa: as fotos de teste do
repositório (`fotos_de_teste`) e uma pasta com uma subpasta por pessoa (`pasta_rotulada`).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import config
from . import fase1_aquisicao as f1
from . import fase2_preprocessamento as f2
from . import fase3_segmentacao as f3
from .leitura_ro import letras
from .lote_sface import LoteSFace

PASTA_FOTOS_TESTE = config.BASE_DIR / "tests" / "fixtures" / "pessoas"


@dataclass(frozen=True)
class ParametrosEstudo:
    """Parâmetros da fase 2 que o laboratório deixa variar, só na amostra em estudo."""

    largura: int = config.LARGURA_PROCESSAMENTO     # largura do quadro reduzido para a detecção
    kernel: int = config.GAUSS_KERNEL[0]            # lado do filtro gaussiano (ímpar; 1 = sem suavização)
    clip: float = config.CLAHE_CLIP                 # limite de contraste do CLAHE
    grade: int = config.CLAHE_GRADE[0]              # blocos por lado do CLAHE

    def __post_init__(self) -> None:
        if self.largura < 1:
            raise ValueError("largura precisa ser positiva")
        if self.kernel < 1 or self.kernel % 2 == 0:
            raise ValueError("kernel precisa ser ímpar e positivo (1 = sem suavização)")
        if self.clip <= 0:
            raise ValueError("clip precisa ser positivo")
        if self.grade < 1:
            raise ValueError("grade precisa ser positiva")

    @property
    def padrao(self) -> bool:
        """True se todos são iguais aos de `config` no momento da chamada (os que o sistema usa)."""
        return (self.largura == config.LARGURA_PROCESSAMENTO
                and (self.kernel, self.kernel) == tuple(config.GAUSS_KERNEL)
                and self.clip == config.CLAHE_CLIP
                and (self.grade, self.grade) == tuple(config.CLAHE_GRADE))


@dataclass
class AmostraLab:
    """Uma imagem levada da fase 1 à fase 4, com tudo o que cada fase produziu."""

    origem: str                         # "foto_teste" | "arquivo" | "camera"
    rotulo: str                         # texto curto de tela, sem nome de pessoa
    frame: np.ndarray                   # BGR uint8, cópia própria
    parametros: ParametrosEstudo
    reduzida: np.ndarray
    cinza: np.ndarray
    suavizada: np.ndarray
    equalizada: np.ndarray
    escala: float                       # fator do quadro original para o reduzido
    n_rostos: int
    rosto: f3.Rosto | None              # principal, em coordenadas do quadro original
    rosto_reduzido: f3.Rosto | None     # o mesmo rosto, em coordenadas do quadro reduzido
    alinhado: np.ndarray | None         # 112x112 BGR
    recorte: np.ndarray | None
    embedding: np.ndarray | None        # (128,) float32 normalizado; NUNCA vai para QML nem arquivo
    norma_crua: float | None            # norma da saída da rede antes da normalização
    qualidade: f2.Qualidade | None
    tempos_ms: dict[str, float]         # "fase2", "fase3_deteccao", "fase3_alinhamento", "fase4", "total"

    @property
    def tem_rosto(self) -> bool:
        return self.rosto is not None


def preparar(frame: np.ndarray, pipeline, parametros: ParametrosEstudo | None = None, *,
             origem: str = "arquivo", rotulo: str = "") -> AmostraLab:
    """Leva um quadro pelas fases 2 a 4 com o detector e o extrator de `pipeline`, medindo o tempo de
    cada fase. De vários rostos, segue só o maior (o principal do núcleo); sem rosto, as fases 3 e 4
    ficam vazias. Custa dezenas de milissegundos: chame fora da thread da interface.

    Os tempos cobrem o que o sistema executa; a leitura da norma crua é um instrumento do laboratório
    e fica fora deles."""
    p = parametros if parametros is not None else ParametrosEstudo()
    frame = frame.copy()
    t0 = time.perf_counter()
    reduzida, escala = f2.redimensionar(frame, largura=p.largura)                           # fase 2
    cinza = f2.converter_cinza(reduzida)
    suavizada = reduzida.copy() if p.kernel == 1 else f2.suavizar(reduzida, kernel=(p.kernel, p.kernel))
    equalizada = f2.equalizar_clahe(suavizada, clip=p.clip, grade=(p.grade, p.grade))
    t1 = time.perf_counter()
    rostos = pipeline.detector.detectar(equalizada)                                         # fase 3 (no quadro reduzido)
    t2 = time.perf_counter()
    tempos = {"fase2": (t1 - t0) * 1e3, "fase3_deteccao": (t2 - t1) * 1e3, "fase3_alinhamento": 0.0, "fase4": 0.0}
    rosto = rosto_reduzido = alinhado = recorte = embedding = norma_crua = qualidade = None
    if rostos:
        rosto_reduzido = rostos[0]
        rosto = rosto_reduzido.escalar(1.0 / escala) if escala != 1.0 else rosto_reduzido
        recorte = f3.recortar(frame, rosto)
        alinhado = pipeline.extrator.alinhar(frame, rosto)                                  # fase 3 (alinhamento)
        qualidade = f2.avaliar_qualidade(alinhado)
        t3 = time.perf_counter()
        embedding = pipeline.extrator.extrair(alinhado)                                     # fase 4
        t4 = time.perf_counter()
        tempos["fase3_alinhamento"], tempos["fase4"] = (t3 - t2) * 1e3, (t4 - t3) * 1e3
        norma_crua = float(LoteSFace.instancia().embeddings([alinhado])[1][0])
    tempos["total"] = sum(tempos.values())
    return AmostraLab(origem=origem, rotulo=rotulo, frame=frame, parametros=p, reduzida=reduzida, cinza=cinza,
                      suavizada=suavizada, equalizada=equalizada, escala=escala, n_rostos=len(rostos), rosto=rosto,
                      rosto_reduzido=rosto_reduzido, alinhado=alinhado, recorte=recorte, embedding=embedding,
                      norma_crua=norma_crua, qualidade=qualidade, tempos_ms=tempos)


def _imagens_por_subpasta(pasta: Path) -> list[list[Path]]:
    """Imagens de cada subpasta, com as subpastas em ordem alfabética; subpasta sem imagem fica de fora."""
    if not pasta.is_dir():
        return []
    grupos = (f1.listar_imagens(sub) for sub in sorted(p for p in pasta.iterdir() if p.is_dir()))
    return [imagens for imagens in grupos if imagens]


def fotos_de_teste() -> dict[str, list[Path]]:
    """Fotos de teste do repositório (retratos de domínio público), por pessoa: "Pessoa de teste A",
    "Pessoa de teste B"... na ordem alfabética das subpastas, com as fotos em ordem alfabética.
    O nome da subpasta nunca é devolvido. {} se a pasta não existir."""
    grupos = _imagens_por_subpasta(PASTA_FOTOS_TESTE)
    return {f"Pessoa de teste {letras(i)}": imagens for i, imagens in enumerate(grupos)}


def pasta_rotulada(pasta: str | Path) -> dict[str, list[Path]]:
    """Conjunto rotulado em disco, com uma subpasta por pessoa: "Pessoa 1", "Pessoa 2"... na ordem
    alfabética das subpastas. Pasta inexistente ou sem subpastas com imagem -> {}."""
    grupos = _imagens_por_subpasta(Path(pasta))
    return {f"Pessoa {i}": imagens for i, imagens in enumerate(grupos, start=1)}
