"""Fases 1 a 4: tempo por fase e checagem do ambiente.

Mede quanto cada fase do pipeline leva numa foto de teste, calcula a impressão digital (SHA-256)
dos modelos e conta as evidências que o registro cita e que não estão mais no disco. Só lê: nada é
gravado, a câmera não é ligada e a máquina de estados do terminal não é usada.
"""

from __future__ import annotations

import hashlib
import statistics
from pathlib import Path

import numpy as np

from . import amostra_lab, leitura_ro

FASES = ("fase2", "fase3_deteccao", "fase3_alinhamento", "fase4", "total")
AQUECIMENTO = 2


def _p95(valores: list[float]) -> float:
    ordenados = sorted(valores)
    if not ordenados:
        return 0.0
    k = min(len(ordenados) - 1, int(round(0.95 * (len(ordenados) - 1))))
    return float(ordenados[k])


def tempos_por_fase(pipeline, frame: np.ndarray, repeticoes: int = 30, sinal=None) -> dict[str, dict[str, float]]:
    """Mediana e p95, em milissegundos, de cada fase em `repeticoes` passadas (mais duas de aquecimento,
    descartadas)."""
    medidas: dict[str, list[float]] = {f: [] for f in FASES}
    for i in range(AQUECIMENTO + max(1, int(repeticoes))):
        if sinal is not None:
            sinal.conferir()
        amostra = amostra_lab.preparar(frame, pipeline, origem="foto_teste", rotulo="diagnóstico")
        if i < AQUECIMENTO:
            continue
        for f in FASES:
            medidas[f].append(float(amostra.tempos_ms.get(f, 0.0)))
        if sinal is not None:
            sinal.progresso(i + 1, AQUECIMENTO + repeticoes)
    return {f: {"mediana": float(statistics.median(v)), "p95": _p95(v)} for f, v in medidas.items()}


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as arq:
        for bloco in iter(lambda: arq.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def evidencias_ausentes(caminho_db) -> tuple[int, int]:
    """(referenciadas, ausentes): lê só a coluna `evidencia` e confere se cada arquivo existe."""
    linhas = leitura_ro.consultar(caminho_db, "SELECT evidencia FROM acessos WHERE evidencia IS NOT NULL")
    referenciadas = len(linhas)
    ausentes = sum(1 for linha in linhas if not Path(str(linha[0])).exists())
    return referenciadas, ausentes
