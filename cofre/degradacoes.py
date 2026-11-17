"""Fase 1 (aquisição): condições de captura simuladas.

Oito famílias de degradação que imitam o que piora uma captura real: foco, ruído do sensor, pouca
luz, luz demais, cabeça inclinada, olhos ou parte de baixo do rosto cobertos e rosto pequeno no
quadro. Cada família vai de uma intensidade 0 (imagem intacta) a 1 (o pior caso previsto), com um
parâmetro físico que pode ser mostrado na tela ("σ = 3,2", "18°", "28 px").

Tudo é sintético e determinístico (o ruído usa uma semente): serve para estudar a robustez do
descritor no laboratório. Nenhuma imagem gerada aqui é gravada nem entra em cadastro ou decisão.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

LADO = 112                      # lado do rosto alinhado, onde as oclusões e a resolução são definidas
LINHA_DOS_OLHOS = 52            # altura (y) dos olhos no rosto alinhado
FAMILIAS_DE_QUADRO = ("escuro", "claro", "desfoque", "ruido", "rotacao")    # valem para um quadro inteiro


@dataclass(frozen=True)
class Familia:
    """Uma condição de captura e a escala do seu parâmetro físico."""

    chave: str
    nome: str
    unidade: str
    inicio: float = 0.0         # valor físico na intensidade 0 (imagem intacta)
    fim: float = 1.0            # valor físico na intensidade 1
    formato: str = "{}"         # como o valor aparece na tela; {} é o número
    casas: int = 0              # casas decimais do rótulo
    inteiro: bool = False       # parâmetro em pixels inteiros: o valor aplicado é o arredondado

    def parametro(self, nivel: float) -> float:
        """Valor físico aplicado na intensidade `nivel` (0 a 1; fora disso é limitado ao intervalo)."""
        nivel = min(1.0, max(0.0, float(nivel)))
        valor = self.inicio + (self.fim - self.inicio) * nivel
        return float(round(valor)) if self.inteiro else valor

    def rotulo(self, nivel: float) -> str:
        """Texto de tela do parâmetro: "σ = 3,2", "ganho × 0,35", "18°", "28 px"."""
        numero = f"{self.parametro(nivel):.{self.casas}f}".replace(".", ",")
        return self.formato.format(numero)


FAMILIAS: dict[str, Familia] = {f.chave: f for f in (
    Familia("desfoque", "Desfoque", "σ", 0.0, 8.0, "σ = {}", 1),
    Familia("ruido", "Ruído", "σ", 0.0, 60.0, "σ = {}", 1),
    Familia("escuro", "Pouca luz", "ganho", 1.0, 0.05, "ganho × {}", 2),
    Familia("claro", "Luz em excesso", "ganho", 1.0, 3.0, "ganho × {}", 2),
    Familia("rotacao", "Rotação no plano", "°", 0.0, 40.0, "{}°", 0),
    Familia("oclusao_olhos", "Olhos cobertos", "px", 0.0, 48.0, "{} px", 0, True),
    Familia("oclusao_baixo", "Parte de baixo coberta", "px", 0.0, 64.0, "{} px", 0, True),
    Familia("resolucao", "Baixa resolução", "px", float(LADO), 12.0, "{} px", 0, True),
)}

NIVEIS_PADRAO: tuple[float, ...] = tuple(i / 11 for i in range(12))    # 12 intensidades de 0 a 1


def _familia(chave: str) -> Familia:
    try:
        return FAMILIAS[chave]
    except KeyError:
        raise ValueError(f"Família de degradação desconhecida: {chave!r}") from None


def _degradar_quadro(img: np.ndarray, familia: Familia, nivel: float, semente: int) -> np.ndarray:
    """As cinco famílias que não dependem da geometria do rosto alinhado."""
    valor = familia.parametro(nivel)
    if familia.chave == "desfoque":
        return cv2.GaussianBlur(img, (0, 0), valor)
    if familia.chave == "ruido":
        ruido = np.random.default_rng(semente).standard_normal(img.shape, dtype=np.float32) * np.float32(valor)
        return np.clip(np.rint(img.astype(np.float32) + ruido), 0, 255).astype(np.uint8)
    if familia.chave in ("escuro", "claro"):
        return cv2.convertScaleAbs(img, alpha=valor)
    h, w = img.shape[:2]            # rotação no plano, em torno do centro, com a borda replicada
    matriz = cv2.getRotationMatrix2D(((w - 1) / 2, (h - 1) / 2), valor, 1.0)
    return cv2.warpAffine(img, matriz, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def _cobrir(img: np.ndarray, y0: int, y1: int) -> np.ndarray:
    """Cobre as linhas de y0 a y1 com a cor média da imagem (uma tarja sem textura nem borda forte)."""
    saida = img.copy()
    saida[y0:y1] = np.rint(img.reshape(-1, img.shape[2]).mean(axis=0)).astype(np.uint8)
    return saida


def aplicar(alinhado: np.ndarray, familia: str, nivel: float, semente: int = 0) -> np.ndarray:
    """Degrada um rosto alinhado (BGR uint8 112x112) e devolve uma cópia do mesmo formato.

    Intensidade 0 devolve a imagem idêntica; a mesma entrada dá sempre a mesma saída."""
    fam = _familia(familia)
    if alinhado.shape != (LADO, LADO, 3) or alinhado.dtype != np.uint8:
        raise ValueError(f"aplicar espera o rosto alinhado BGR uint8 {LADO}x{LADO}")
    if nivel <= 0:
        return alinhado.copy()
    if fam.chave in FAMILIAS_DE_QUADRO:
        return _degradar_quadro(alinhado, fam, nivel, semente)
    valor = int(fam.parametro(nivel))
    if fam.chave == "oclusao_olhos":        # tarja centrada na linha dos olhos
        y0 = max(0, LINHA_DOS_OLHOS - valor // 2)
        return _cobrir(alinhado, y0, min(LADO, y0 + valor))
    if fam.chave == "oclusao_baixo":        # cobre a partir da base
        return _cobrir(alinhado, LADO - valor, LADO)
    if valor >= LADO:                       # resolução: reduz e amplia de volta
        return alinhado.copy()
    pequena = cv2.resize(alinhado, (valor, valor), interpolation=cv2.INTER_AREA)
    return cv2.resize(pequena, (LADO, LADO), interpolation=cv2.INTER_LINEAR)


def aplicar_no_quadro(frame: np.ndarray, familia: str, nivel: float, semente: int = 0) -> np.ndarray:
    """Degrada o quadro inteiro, antes do pipeline (usado na ablação). Só para as famílias de
    `FAMILIAS_DE_QUADRO`; as oclusões e a resolução são definidas no rosto alinhado."""
    fam = _familia(familia)
    if fam.chave not in FAMILIAS_DE_QUADRO:
        raise ValueError(f"A família {familia!r} só vale para o rosto alinhado (use aplicar).")
    if nivel <= 0:
        return frame.copy()
    return _degradar_quadro(frame, fam, nivel, semente)
