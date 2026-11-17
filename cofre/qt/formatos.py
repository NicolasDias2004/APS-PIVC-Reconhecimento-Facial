"""Texto de número, porcentagem, data e caminho, igual em todas as telas novas, e a conversão de
imagem com transparência para o QML.

Os ViewModels novos formatam por aqui: vírgula decimal, travessão quando não há valor e as mesmas
casas em toda aba. Nada neste módulo guarda estado.
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage

SEM_VALOR = "–"                 # travessão: o dado não existe (diferente de zero)
SEPARADOR_MILHAR = " "     # espaço fino inseparável


def _ausente(v: float | None) -> bool:
    return v is None or v != v      # None ou NaN


def num(v: float | None, casas: int = 3) -> str:
    """Número com vírgula decimal: 0.3634 -> "0,363". None ou NaN -> "–"; infinito -> "∞"."""
    if _ausente(v):
        return SEM_VALOR
    v = float(v)
    if math.isinf(v):
        return "∞" if v > 0 else "-∞"
    texto = f"{v:.{casas}f}"
    if float(texto) == 0:
        texto = texto.lstrip("-")           # um valor que arredonda para zero não sai como "-0,000"
    return texto.replace(".", ",")


def inteiro(n: int | None) -> str:
    """Inteiro com os milhares separados por espaço fino: 2236 -> "2 236". None -> "–"."""
    if n is None:
        return SEM_VALOR
    return f"{int(n):,}".replace(",", SEPARADOR_MILHAR)


def pct_valor(f: float | None, casas: int = 2) -> str:
    """Fração como porcentagem: 0.0488 -> "4,88 %". None ou NaN -> "–"."""
    if _ausente(f):
        return SEM_VALOR
    return f"{num(float(f) * 100, casas)} %"


def pct(k: int, n: int, casas: int = 2) -> str:
    """`k` em `n` como porcentagem: 43, 882 -> "4,88 %". Sem total (n == 0) -> "–"."""
    if not n:
        return SEM_VALOR
    return pct_valor(k / n, casas)


def _momento(iso: str | None) -> datetime | None:
    if not isinstance(iso, str):
        return None
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


def hora(iso: str | None) -> str:
    """Hora de uma data ISO do registro: "2026-11-10T20:41:07" -> "20:41:07". Inválida -> "–"."""
    momento = _momento(iso)
    return SEM_VALOR if momento is None else f"{momento:%H:%M:%S}"


def dia_hora(iso: str | None) -> str:
    """Dia e hora curtos: "2026-11-10T20:41:07" -> "10/11 · 20:41". Inválida -> "–"."""
    momento = _momento(iso)
    return SEM_VALOR if momento is None else f"{momento:%d/%m} · {momento:%H:%M}"


def carimbo_arquivo(agora: datetime | None = None) -> str:
    """Data e hora para nome de arquivo, no formato AAAAMMDD_HHMMSS."""
    return f"{agora or datetime.now():%Y%m%d_%H%M%S}"


def caminho_de_url(url: str) -> Path | None:
    """Caminho local de uma URL devolvida pelo FileDialog ou FolderDialog ("file:///...").
    Texto que já é um caminho passa direto; vazio -> None."""
    if not url:
        return None
    u = QUrl(url)
    return Path(u.toLocalFile() if u.isLocalFile() else url)


def bgra_para_qimage(img: np.ndarray) -> QImage:
    """Imagem BGRA (h, w, 4) uint8 -> QImage ARGB32 independente, com o canal alfa preservado.
    (`imagens.bgr_para_qimage` descarta o quarto canal: um mapa com transparência sairia opaco.)"""
    if img.ndim != 3 or img.shape[2] != 4 or img.dtype != np.uint8:
        raise ValueError("bgra_para_qimage espera uma imagem (altura, largura, 4) uint8")
    img = np.ascontiguousarray(img)
    h, w = img.shape[:2]
    return QImage(img.data, w, h, img.strides[0], QImage.Format.Format_ARGB32).copy()
