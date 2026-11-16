"""
Exibição de vídeo no QML: `FonteVideo` guarda o quadro (QImage) e as marcações dos rostos;
`VisorVideo` (item do QML) desenha tudo com QPainter.

As marcações são desenhadas pelo Qt (e não pelo OpenCV) para ficarem nítidas em qualquer
tamanho de janela e com a mesma tipografia do restante da interface.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen
from PySide6.QtQuick import QQuickPaintedItem


class FonteVideo(QObject):
    """Último quadro + marcações. `caixas` é uma lista de dicionários:
    {"x", "y", "w", "h", "cor": "#rrggbb", "rotulo": str, "pontos": [(x, y), ...]} em pixels do quadro."""

    mudou = Signal()
    temImagemMudou = Signal()

    def __init__(self, nome: str = "", parent=None):
        super().__init__(parent)
        self._nome = nome
        self._imagem = QImage()
        self._caixas: list[dict[str, Any]] = []

    def definir(self, imagem: QImage | None, caixas: list[dict[str, Any]] | None = None) -> None:
        tinha = not self._imagem.isNull()
        self._imagem = imagem if imagem is not None else QImage()
        self._caixas = list(caixas or [])
        if tinha != (not self._imagem.isNull()):
            self.temImagemMudou.emit()
        self.mudou.emit()

    def limpar(self) -> None:
        self.definir(None, [])

    @property
    def imagem(self) -> QImage:
        return self._imagem

    @property
    def caixas(self) -> list[dict[str, Any]]:
        return self._caixas

    def _tem_imagem(self) -> bool:
        return not self._imagem.isNull()

    def _get_nome(self) -> str:
        return self._nome

    temImagem = Property(bool, _tem_imagem, notify=temImagemMudou)
    nome = Property(str, _get_nome, constant=True)


class VisorVideo(QQuickPaintedItem):
    fonteMudou = Signal()
    preencherMudou = Signal()
    raioMudou = Signal()
    corFundoMudou = Signal()
    mostrarPontosMudou = Signal()
    varreduraMudou = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fonte: FonteVideo | None = None
        self._preencher = False
        self._raio = 0.0
        self._cor_fundo = QColor("#0b0d10")
        self._mostrar_pontos = True
        self._varredura = -1.0        # 0..1 = linha de varredura na caixa principal; < 0 = desligada
        self.setAntialiasing(True)
        self.setOpaquePainting(False)

    # ------------------------------------------------------------------ propriedades
    def _get_fonte(self):
        return self._fonte

    def _set_fonte(self, fonte) -> None:
        if fonte is self._fonte:
            return
        if self._fonte is not None:
            try:
                self._fonte.mudou.disconnect(self.update)
            except (RuntimeError, TypeError):
                pass
        self._fonte = fonte
        if fonte is not None:
            fonte.mudou.connect(self.update)
        self.fonteMudou.emit()
        self.update()

    def _get_preencher(self) -> bool:
        return self._preencher

    def _set_preencher(self, v: bool) -> None:
        if v != self._preencher:
            self._preencher = bool(v)
            self.preencherMudou.emit()
            self.update()

    def _get_raio(self) -> float:
        return self._raio

    def _set_raio(self, v: float) -> None:
        if v != self._raio:
            self._raio = float(v)
            self.raioMudou.emit()
            self.update()

    def _get_cor_fundo(self) -> QColor:
        return self._cor_fundo

    def _set_cor_fundo(self, v) -> None:
        cor = QColor(v)
        if cor != self._cor_fundo:
            self._cor_fundo = cor
            self.corFundoMudou.emit()
            self.update()

    def _get_mostrar_pontos(self) -> bool:
        return self._mostrar_pontos

    def _set_mostrar_pontos(self, v: bool) -> None:
        if v != self._mostrar_pontos:
            self._mostrar_pontos = bool(v)
            self.mostrarPontosMudou.emit()
            self.update()

    fonte = Property(QObject, _get_fonte, _set_fonte, notify=fonteMudou)
    preencher = Property(bool, _get_preencher, _set_preencher, notify=preencherMudou)
    raio = Property(float, _get_raio, _set_raio, notify=raioMudou)
    corFundo = Property(QColor, _get_cor_fundo, _set_cor_fundo, notify=corFundoMudou)
    mostrarPontos = Property(bool, _get_mostrar_pontos, _set_mostrar_pontos, notify=mostrarPontosMudou)

    def _get_varredura(self) -> float:
        return self._varredura

    def _set_varredura(self, v: float) -> None:
        if v != self._varredura:
            self._varredura = float(v)
            self.varreduraMudou.emit()
            self.update()

    varredura = Property(float, _get_varredura, _set_varredura, notify=varreduraMudou)

    # ------------------------------------------------------------------ desenho
    def paint(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        if w <= 1 or h <= 1:
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        area = QRectF(0, 0, w, h)
        recorte = QPainterPath()
        recorte.addRoundedRect(area, self._raio, self._raio)
        p.setClipPath(recorte)
        p.fillRect(area, self._cor_fundo)
        fonte = self._fonte
        if fonte is None or fonte.imagem.isNull():
            return
        img = fonte.imagem
        iw, ih = img.width(), img.height()
        esc = (max if self._preencher else min)(w / iw, h / ih)
        dw, dh = iw * esc, ih * esc
        ox, oy = (w - dw) / 2, (h - dh) / 2
        p.drawImage(QRectF(ox, oy, dw, dh), img)
        for caixa in fonte.caixas:
            self._desenhar_caixa(p, caixa, esc, ox, oy)

    @staticmethod
    def _desenhar_malha(p: QPainter, pts: list[QPointF], cor: QColor, caixa: QRectF) -> None:
        """Geometria usada pelo alinhamento: linha dos olhos (eixo de inclinação), eixo vertical do
        nariz (eixo de giro) e a malha olhos-nariz-boca. Os pontos vêm do detector (YuNet)."""
        od, oe, nz, bd, be = pts
        fraca = QColor(cor)
        fraca.setAlphaF(0.45)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(fraca, 1.0))
        for a, b in ((od, oe), (od, nz), (oe, nz), (nz, bd), (nz, be), (bd, be)):
            p.drawLine(a, b)
        # eixos: prolongam a linha dos olhos e ligam o meio dos olhos ao meio da boca pelo nariz
        meio_olhos = QPointF((od.x() + oe.x()) / 2, (od.y() + oe.y()) / 2)
        meio_boca = QPointF((bd.x() + be.x()) / 2, (bd.y() + be.y()) / 2)
        eixo = QPen(fraca, 1.0, Qt.PenStyle.DashLine)
        p.setPen(eixo)
        dx, dy = oe.x() - od.x(), oe.y() - od.y()
        p.drawLine(QPointF(od.x() - dx * 0.35, od.y() - dy * 0.35), QPointF(oe.x() + dx * 0.35, oe.y() + dy * 0.35))
        vx, vy = meio_boca.x() - meio_olhos.x(), meio_boca.y() - meio_olhos.y()
        p.drawLine(QPointF(meio_olhos.x() - vx * 0.45, meio_olhos.y() - vy * 0.45),
                   QPointF(meio_boca.x() + vx * 0.35, meio_boca.y() + vy * 0.35))

    def _desenhar_varredura(self, p: QPainter, caixa: QRectF, cor: QColor) -> None:
        y = caixa.top() + caixa.height() * self._varredura
        faixa = QColor(cor)
        faixa.setAlphaF(0.10)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(faixa)
        p.drawRect(QRectF(caixa.left() + 2, max(caixa.top(), y - 18), caixa.width() - 4, min(18.0, y - caixa.top())))
        linha = QColor(cor)
        linha.setAlphaF(0.85)
        p.setPen(QPen(linha, 1.5))
        p.drawLine(QPointF(caixa.left() + 2, y), QPointF(caixa.right() - 2, y))

    def _desenhar_caixa(self, p: QPainter, c: dict[str, Any], esc: float, ox: float, oy: float) -> None:
        cor = QColor(c.get("cor", "#2dd4bf"))
        x, y = ox + c["x"] * esc, oy + c["y"] * esc
        bw, bh = c["w"] * esc, c["h"] * esc
        caixa = QRectF(x, y, bw, bh)
        fraca = QColor(cor)
        fraca.setAlphaF(0.35)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(fraca, 1.2))
        p.drawRoundedRect(caixa, 6, 6)
        # cantos destacados
        canto = max(10.0, min(bw, bh) * 0.18)
        caneta = QPen(cor, 3.0)
        caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(caneta)
        for px, py, dx, dy in ((x, y, 1, 1), (x + bw, y, -1, 1), (x, y + bh, 1, -1), (x + bw, y + bh, -1, -1)):
            p.drawLine(QPointF(px, py), QPointF(px + dx * canto, py))
            p.drawLine(QPointF(px, py), QPointF(px, py + dy * canto))
        pontos = [QPointF(ox + px * esc, oy + py * esc) for px, py in c.get("pontos", ())]
        if c.get("malha") and len(pontos) == 5:
            self._desenhar_malha(p, pontos, cor, caixa)
        if c.get("principal") and 0.0 <= self._varredura <= 1.0:
            self._desenhar_varredura(p, caixa, cor)
        if self._mostrar_pontos:
            p.setPen(Qt.PenStyle.NoPen)
            ponto = QColor(cor)
            ponto.setAlphaF(0.9)
            p.setBrush(ponto)
            for pt in pontos:
                p.drawEllipse(pt, 2.6, 2.6)
            if c.get("malha") and len(pontos) == 5:
                anel = QPen(ponto, 1.0)
                p.setPen(anel)
                p.setBrush(Qt.BrushStyle.NoBrush)
                for pt in pontos:
                    p.drawEllipse(pt, 6.0, 6.0)
        rotulo = c.get("rotulo") or ""
        if rotulo:
            f = QFont(p.font())
            f.setPixelSize(12)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            m = QFontMetricsF(f)
            tw = m.horizontalAdvance(rotulo) + 16
            th = m.height() + 8
            ty = y - th - 6 if y - th - 6 >= 4 else y + bh + 6
            pilula = QRectF(x, ty, tw, th)
            fundo = QColor(cor)
            fundo.setAlphaF(0.92)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fundo)
            p.drawRoundedRect(pilula, th / 2, th / 2)
            p.setPen(QColor("#0b0d10"))
            p.drawText(pilula, Qt.AlignmentFlag.AlignCenter, rotulo)
