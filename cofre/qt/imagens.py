"""Conversão entre as imagens do OpenCV (NumPy BGR) e QImage."""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage


def bgr_para_qimage(img: np.ndarray) -> QImage:
    """Copia a imagem para um QImage independente (o buffer do NumPy pode ser reutilizado)."""
    if img.ndim == 2:
        img = np.ascontiguousarray(img)
        h, w = img.shape
        return QImage(img.data, w, h, img.strides[0], QImage.Format.Format_Grayscale8).copy()
    if img.shape[2] == 4:
        img = img[:, :, :3]
    img = np.ascontiguousarray(img)
    h, w = img.shape[:2]
    return QImage(img.data, w, h, img.strides[0], QImage.Format.Format_BGR888).copy()


def hex_de_bgr(cor: tuple[int, int, int]) -> str:
    """Cor do HUD do OpenCV (B, G, R) para '#rrggbb'."""
    b, g, r = (int(c) for c in cor[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def criar_provedor():
    """Provedor de imagens em memória servidas ao QML por `image://cofre/<chave>`
    (miniaturas do cadastro, por exemplo)."""
    import threading

    from PySide6.QtQuick import QQuickImageProvider

    class _Provedor(QQuickImageProvider):
        def __init__(self):
            super().__init__(QQuickImageProvider.ImageType.Image)
            self._lock = threading.Lock()
            self._imagens: dict[str, QImage] = {}

        def guardar(self, chave: str, imagem: QImage) -> None:
            with self._lock:
                self._imagens[chave] = imagem

        def remover_prefixo(self, prefixo: str) -> None:
            with self._lock:
                for k in [k for k in self._imagens if k.startswith(prefixo)]:
                    del self._imagens[k]

        def requestImage(self, ident, tamanho, pedido):  # noqa: N802 (API do Qt)
            chave = ident.split("?", 1)[0]
            with self._lock:
                img = self._imagens.get(chave)
            if img is None:
                img = QImage(1, 1, QImage.Format.Format_ARGB32)
                img.fill(0)
            if pedido is not None and pedido.isValid() and pedido.width() > 0 and pedido.height() > 0:
                from PySide6.QtCore import Qt
                img = img.scaled(pedido, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
            if tamanho is not None:
                tamanho.setWidth(img.width())
                tamanho.setHeight(img.height())
            return img

    return _Provedor()
