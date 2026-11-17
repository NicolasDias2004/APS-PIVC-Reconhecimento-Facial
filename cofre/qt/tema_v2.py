"""Cores da v2 no lado Python, com os valores exatos de `Ui/Theme.qml` (um teste compara os dois).

O `tema.py` antigo fica como está. Daqui saem as duas paletas dos gráficos: `PALETA_TELA`
(grafite, a mesma do aplicativo) e `PALETA_PAPEL` (fundo branco, para figura exportada e PDF).
"""

from __future__ import annotations

from typing import Any, Sequence

# superfícies e texto (Theme.qml)
SUPERFICIE = "#151a1f"
BORDA = "#252b33"
TEXTO = "#e7ebef"
TEXTO2 = "#9aa3ae"
TEXTO3 = "#68717d"

# acento e estados (Theme.qml)
ACENTO = "#35d0c0"
SUCESSO = "#3dd68c"
PERIGO = "#f06a6a"
AVISO = "#f2b544"

# dados (Theme.qml, bloco da v2)
NEUTRO_DADO = "#8b97a6"
CORES_SERIE = ("#29a89b", "#4d8fe6", "#d75fa8", "#8a7cf0")
CALOR = ("#2a5a5e", "#266f6c", "#24877e", "#27a093", "#2fbfb0", "#9be9df")

# o mesmo vermelho do negado, cada vez mais fraco: "negado", "negado2", "negado3", "negado4"
ALFAS_NEGADO = (1.0, 0.78, 0.58, 0.40)

PALETA_TELA: dict[str, Any] = {
    "fundo": SUPERFICIE,
    "tinta": TEXTO,
    "tinta2": TEXTO2,
    "tinta3": TEXTO3,
    "grade": BORDA,
    "series": CORES_SERIE,
    "neutro": NEUTRO_DADO,
    "concedido": SUCESSO,
    "negado": PERIGO,
    "bloqueio": TEXTO3,
    "aviso": AVISO,
    "calor": CALOR,
}

PALETA_PAPEL: dict[str, Any] = {
    "fundo": "#ffffff",
    "tinta": "#1b2026",
    "tinta2": "#4a5360",
    "tinta3": "#6b7682",
    "grade": "#d9dee4",
    "series": ("#0f9a8c", "#2f6fc4", "#b8408a", "#6a5acd"),
    "neutro": "#6b7682",
    "concedido": "#1f9d61",
    "negado": "#d14a4a",
    "bloqueio": "#8a939e",
    "aviso": "#9a6200",
    "calor": ("#d9f3ef", "#a9e3db", "#6fcdc1", "#3bb0a2", "#1f8f84", "#136b63"),
}


def cor_serie(indice: int, series: Sequence[str] = CORES_SERIE) -> str:
    """Cor da série `indice`, em ciclo (igual a `Theme.corSerie`)."""
    return series[indice % len(series)]


def cor_calor(fracao: float, rampa: Sequence[str] = CALOR) -> str:
    """Degrau da rampa para uma fração de 0 a 1 (igual a `Theme.corCalor`)."""
    return rampa[max(0, min(len(rampa) - 1, int(fracao * len(rampa))))]


def luminancia(cor: str) -> float:
    """Luminância relativa (WCAG) de uma cor "#rrggbb", de 0 (preto) a 1 (branco)."""
    def linear(canal: float) -> float:
        return canal / 12.92 if canal <= 0.03928 else ((canal + 0.055) / 1.055) ** 2.4

    r, g, b = (int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)


def bgr(cor: str) -> tuple[int, int, int]:
    """Cor "#rrggbb" na ordem do OpenCV (B, G, R), para quem desenha com `cv2`."""
    return int(cor[5:7], 16), int(cor[3:5], 16), int(cor[1:3], 16)
