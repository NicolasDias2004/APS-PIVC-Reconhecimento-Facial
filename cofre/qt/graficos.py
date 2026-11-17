"""Gráficos da v2: um desenho só para a tela e para o arquivo.

`desenhar` pinta com QPainter um dos seis tipos (`TIPOS`) a partir de um dicionário simples. O item
`Grafico` do QML, `renderizar` (QImage) e `exportar` (PNG 2x, SVG e CSV em paleta papel) chamam essa
mesma função: a figura que vai para o arquivo é a que estava na tela. Nada aqui lê banco, decide
acesso ou guarda dado. É só desenho, leitura sob o cursor e a trava `conferir_sem_vetor`, que
impede um vetor biométrico de 128 dimensões de chegar a um arquivo.

Formato de `dados` (toda chave é opcional; cores por nome: "serie0".."serie3", "neutro", "texto",
"concedido", "negado", "negado2".."negado4", "bloqueio", "aviso"):

  comuns      titulo, subtitulo, n, selos, resumo, vazio, eixoX, eixoY
              (eixo: rotulo, min, max, escala "linear"|"log", formato "0.00"|"0.000"|"%"|"int"|"hora",
              marcas, marcasTexto)
  xy          series [{nome, cor, pontos [[x, y|None]], rotulos, estilo "linha"|"degrau"|"pontos",
              tracejada, faixa [[x, ymin, ymax]], rotuloPonta}], marcadoresV [{x, rotulo, estilo}],
              marcadoresH [{y, rotulo, estilo}], anotacoes [{x, y, texto}]
  histograma  bordas, series [{nome, cor, contagens, sentido 1|-1}], marcadoresV, truncarEm
  barras      categorias, series [{nome, cor, valores}], orientacao "h"|"v", empilhado, rotulosValor,
              marcadoresV, marcadoresH
  calor       linhas, colunas, valores, min, max, mostrarValores, formato, destaques, marcaEscala
  dispersao   grupos [{nome, cor 0..3, forma 0..3, pontos, rotulos, centro}], rotularCentros, outros
  fita        faixas [{rotulo, eventos [{t, tipo, id, texto}], intervalos [{t0, t1}]}]

Estilo dos marcadores de limiar: "vigor" (traço cheio de tinta, tracejado), "estudo" (pontilhado,
mais fraco) e "nota" (fio contínuo e discreto). O formato "%" recebe fração (0,0488 vira "4,88 %").

A leitura sob o cursor (`valor_em`, `valor_indice`) devolve {"texto", "px", "py", "indice"} e o realce
que o dado pede: "forma" ("fio", "anel" ou "caixa") e o retângulo "rx", "ry", "rl", "ra". A legenda
que o dado pede sai de `itens_legenda`, e o tamanho da figura exportada, de `tamanho_figura`.
"""

from __future__ import annotations

import csv
import io
import math
from bisect import bisect_right
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any, Sequence

from PySide6.QtCore import Property, QPointF, QRect, QRectF, QSize, Qt, Signal, Slot
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QGuiApplication, QImage, QPainter, QPainterPath, QPen,
                           QPolygonF)
from PySide6.QtQuick import QQuickPaintedItem
from PySide6.QtSvg import QSvgGenerator

from . import tema_v2

TIPOS = ("xy", "histograma", "barras", "calor", "dispersao", "fita")

MENOS = "−"                 # sinal de menos dos rótulos (no CSV vai o hífen, que a planilha entende)
ESPACO_MILHAR = " "         # espaço fino inseparável entre milhares
ESPACO_UNIDADE = " "        # espaço inseparável antes de "%"
SEM_VALOR = "–"
FRASE_VAZIO = "Sem dados para mostrar"
NOMES_FITA = {"concedido": "Concedido", "negado": "Negado", "bloqueio": "Bloqueio"}
NOME_INTERVALO = "Terminal bloqueado"
NOME_OUTROS = "Outras"
ALTURA_TRACO_FITA = {"concedido": 1.0, "negado": 0.64, "bloqueio": 0.34}     # fração da faixa

MARGEM_FIGURA = 20.0             # respiro da figura exportada (título, legenda e gráfico)
LARGURA_FIGURA = 760             # largura lógica da figura exportada; a altura depende do conteúdo
LARGURA_ESCALA = 10.0            # barra de escala do calor
FAMILIA_SVG = "Helvetica"        # o nome da fonte do sistema só existe no macOS; no SVG vai uma família comum


# ---------------------------------------------------------------------------- leitura defensiva de `dados`
def _numero(v: Any) -> float | None:
    """Número de gráfico, ou None: booleano, texto, NaN, infinito e módulo acima de 1e12 não contam, e o
    que é menor que 1e-12 vale zero (assim nenhuma conta de eixo estoura nem divide por zero)."""
    if isinstance(v, bool) or not isinstance(v, Real):
        return None
    try:
        f = float(v)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(f) or abs(f) > 1e12:
        return None
    return f if abs(f) >= 1e-12 else 0.0


def _lista(v: Any) -> list:
    return list(v) if isinstance(v, (list, tuple)) else []


def _mapa(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _texto(v: Any) -> str:
    return v if isinstance(v, str) else ("" if v is None or isinstance(v, (dict, list, tuple)) else str(v))


def _ponto(v: Any) -> tuple[float, float] | None:
    """Par [x, y] com os dois números válidos."""
    par = _lista(v)
    if len(par) < 2:
        return None
    x, y = _numero(par[0]), _numero(par[1])
    return (x, y) if x is not None and y is not None else None


# ---------------------------------------------------------------------------- números por extenso
def _decimal(v: float, casas: int) -> str:
    texto = f"{abs(v):.{casas}f}"
    return (MENOS if v < 0 and float(texto) != 0 else "") + texto.replace(".", ",")


def _inteiro(v: float) -> str:
    n = round(v)
    return (MENOS if n < 0 else "") + f"{abs(n):,}".replace(",", ESPACO_MILHAR)


def _hora(v: float) -> str:
    minutos = max(0, round(v * 60))
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def _porcento(v: float, casas: int) -> str:
    return _decimal(v * 100, casas) + ESPACO_UNIDADE + "%"


def _casas_de(v: float, teto: int = 4) -> int:
    """Menor número de casas decimais que escreve `v` sem arredondar (até `teto`)."""
    for casas in range(teto):
        if abs(round(v, casas) - v) <= 1e-9 * max(1.0, abs(v)):
            return casas
    return teto


def _formatar(v: float | None, formato: str, casas: int = 2) -> str:
    """Número no formato de um eixo; `casas` vale para "%" e para o formato automático ("")."""
    if v is None:
        return SEM_VALOR
    if formato == "int":
        return _inteiro(v)
    if formato == "hora":
        return _hora(v)
    if formato == "%":
        return _porcento(v, casas)
    if formato.startswith("0"):
        return _decimal(v, len(formato.partition(".")[2]))
    return _inteiro(v) if casas == 0 else _decimal(v, casas)


def _csv_numero(v: float | None) -> str:
    """Número para a planilha: vírgula decimal, hífen como sinal e nenhum separador de milhar."""
    if v is None:
        return ""
    return str(int(v)) if float(v).is_integer() else f"{v:.6f}".rstrip("0").replace(".", ",")


# ---------------------------------------------------------------------------- eixos
@dataclass(frozen=True)
class _Eixo:
    """Um eixo já resolvido: limites, marcas com o texto de cada uma e o formato dos valores."""
    rotulo: str
    minimo: float
    maximo: float
    log: bool
    formato: str
    marcas: tuple[float, ...]
    textos: tuple[str, ...]
    casas: int                      # casas decimais das marcas quando o formato é automático

    def fracao(self, v: float) -> float:
        """Posição ao longo do eixo: 0 no mínimo, 1 no máximo (no log, o que não é positivo fica no piso)."""
        if self.log:
            v = max(v, self.minimo)
            return (math.log10(v) - math.log10(self.minimo)) / (math.log10(self.maximo) - math.log10(self.minimo))
        return (v - self.minimo) / (self.maximo - self.minimo)

    def ler(self, v: float | None) -> str:
        """Valor por extenso para a leitura sob o cursor (no automático, uma casa a mais que as marcas)."""
        if v is None:
            return SEM_VALOR
        if self.formato == "%":
            pct = abs(v) * 100
            return _porcento(v, 2 if pct == 0 or pct >= 0.1 else min(4, 1 - math.floor(math.log10(pct))))
        if self.formato:
            return _formatar(v, self.formato)
        return _inteiro(v) if self.casas == 0 and float(v).is_integer() else _decimal(v, self.casas + 1)


def _passo(amplitude: float, alvo: int, formato: str = "") -> float:
    """Distância redonda entre marcas para caber cerca de `alvo` intervalos em `amplitude`."""
    bruto = amplitude / max(1, alvo)
    if formato == "hora":
        return next((h for h in (0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 12.0) if h >= bruto * (1 - 1e-9)), 24.0)
    base = 10.0 ** math.floor(math.log10(bruto))
    multiplos = (1.0, 2.0, 5.0, 10.0) if formato == "int" else (1.0, 2.0, 2.5, 5.0, 10.0)
    passo = next(m * base for m in multiplos if m * base >= bruto * (1 - 1e-9))
    return max(1.0, passo) if formato == "int" else passo


def _marcas_lineares(minimo: float, maximo: float, passo: float) -> list[float]:
    primeira, ultima = math.ceil(minimo / passo - 1e-9), math.floor(maximo / passo + 1e-9)
    return [k * passo for k in range(primeira, ultima + 1)]


def _marcas_log(minimo: float, maximo: float) -> list[float]:
    primeira, ultima = math.ceil(math.log10(minimo) - 1e-9), math.floor(math.log10(maximo) + 1e-9)
    salto = 1 if ultima - primeira < 6 else 2
    return [10.0 ** k for k in range(primeira, ultima + 1, salto)]


def _limites(spec: dict, valores: Sequence[float], log: bool, do_zero: bool, justo: bool, alvo: int,
             formato: str) -> tuple[float, float]:
    minimo, maximo = _numero(spec.get("min")), _numero(spec.get("max"))
    if log:
        positivos = [v for v in valores if v > 0]
        if minimo is None or minimo <= 0:
            minimo = 10.0 ** math.floor(math.log10(min(positivos))) if positivos else 0.001
        if maximo is None or maximo <= minimo:
            maximo = max(10.0 ** math.ceil(math.log10(max(positivos, default=minimo))), minimo * 10)
        return minimo, maximo
    baixo, alto = min(valores, default=0.0), max(valores, default=1.0)
    if do_zero:
        baixo, alto = min(baixo, 0.0), max(alto, 0.0)
    baixo = baixo if minimo is None else minimo
    alto = alto if maximo is None else maximo
    if alto <= baixo:                              # um valor só: abre espaço dos dois lados
        folga = abs(baixo) * 0.5 or 0.5
        baixo, alto = (baixo, baixo + 2 * folga) if do_zero or minimo is not None else (baixo - folga, baixo + folga)
    if not justo:
        passo = _passo(alto - baixo, alvo, formato)
        if minimo is None:
            baixo = math.floor(baixo / passo + 1e-9) * passo
        if maximo is None:
            alto = math.ceil(alto / passo - 1e-9) * passo
    return baixo, alto


def _eixo(spec: Any, valores: Sequence[float], *, alvo: int = 4, do_zero: bool = False, justo: bool = False) -> _Eixo:
    """Resolve um eixo com o que veio em `dados` (tudo opcional) e com os valores que ele precisa mostrar."""
    spec = _mapa(spec)
    formato = _texto(spec.get("formato"))
    log = spec.get("escala") == "log"
    minimo, maximo = _limites(spec, valores, log, do_zero, justo, alvo, formato)
    dadas = [_numero(m) for m in _lista(spec.get("marcas"))]
    textos_dados = [_texto(t) for t in _lista(spec.get("marcasTexto"))]
    if not dadas and textos_dados:                 # um texto por valor de X, sem a lista de marcas
        distintos = sorted(set(valores))
        dadas = distintos if len(distintos) == len(textos_dados) else []
    if dadas:
        pares = [(m, textos_dados[i] if i < len(textos_dados) else None) for i, m in enumerate(dadas)]
        pares = [(m, t) for m, t in pares if m is not None and minimo <= m <= maximo]
        marcas = [m for m, _ in pares]
    elif log:
        marcas, pares = _marcas_log(minimo, maximo), []
    else:
        marcas, pares = _marcas_lineares(minimo, maximo, _passo(maximo - minimo, alvo, formato)), []
    escala = 100.0 if formato == "%" else 1.0
    casas = min(3, max((_casas_de(m * escala) for m in marcas), default=0))

    def escrever(m: float) -> str:                 # no log cada década pede as suas casas (0,1 % · 1 % · 10 %)
        if formato.startswith("0"):                # "0.0" com marcas de 0,25 em 0,25 escreve 0,25, não 0,2
            return _decimal(m, max(len(formato.partition(".")[2]), casas))
        return _formatar(m, formato, _casas_de(m * escala) if log else casas)

    textos = [t if t is not None else escrever(m) for m, t in pares] if pares else [escrever(m) for m in marcas]
    return _Eixo(_texto(spec.get("rotulo")), minimo, maximo, log, formato, tuple(marcas), tuple(textos), casas)


# ---------------------------------------------------------------------------- estilo: paleta e letras
@dataclass(frozen=True)
class _Letra:
    fonte: QFont
    m: QFontMetricsF


def _letra(familia: str, tamanho: int, peso: QFont.Weight = QFont.Weight.Normal) -> _Letra:
    fonte = QFont(QGuiApplication.font())
    if familia:
        fonte.setFamily(familia)
    fonte.setPixelSize(tamanho)
    fonte.setWeight(peso)
    fonte.setFeature(QFont.Tag("tnum"), 1)          # algarismos de largura fixa, como no resto do aplicativo
    return _Letra(fonte, QFontMetricsF(fonte))


class _Estilo:
    """Cores e letras de uma pintura. A paleta decide se é tela (grafite) ou papel (fundo branco)."""

    def __init__(self, paleta: dict | None) -> None:
        self.paleta = {**tema_v2.PALETA_TELA, **(paleta or {})}
        familia = _texto(self.paleta.get("familia"))
        self.rotulo = _letra(familia, 11)
        self.forte = _letra(familia, 11, QFont.Weight.DemiBold)
        self.corpo = _letra(familia, 12)
        self.titulo = _letra(familia, 15, QFont.Weight.DemiBold)
        self.fundo = QColor(self.paleta["fundo"])
        self.tinta = QColor(self.paleta["tinta"])
        self.tinta2 = QColor(self.paleta["tinta2"])
        self.tinta3 = QColor(self.paleta["tinta3"])
        self.grade = QColor(self.paleta["grade"])
        self.placa = QColor(self.fundo)             # fundo de rótulo escrito por cima do dado
        self.placa.setAlphaF(0.84)

    def cor(self, nome: Any) -> QColor:
        """Cor pelo nome usado em `dados` (ou pelo índice da série); nome desconhecido cai no neutro."""
        series = self.paleta["series"]
        if isinstance(nome, int) and not isinstance(nome, bool):
            return QColor(tema_v2.cor_serie(nome, series))
        if isinstance(nome, str):
            if nome.startswith("serie") and nome[5:].isdigit():
                return QColor(tema_v2.cor_serie(int(nome[5:]), series))
            if nome in ("negado", "negado2", "negado3", "negado4"):
                cor = QColor(self.paleta["negado"])
                cor.setAlphaF(tema_v2.ALFAS_NEGADO[int(nome[6:] or 1) - 1])
                return cor
            if nome == "texto":
                return QColor(self.tinta)
            if nome in ("concedido", "bloqueio", "aviso"):
                return QColor(self.paleta[nome])
        return QColor(self.paleta["neutro"])

    def calor(self, fracao: float) -> QColor:
        return QColor(tema_v2.cor_calor(fracao, self.paleta["calor"]))

    def sobre(self, cor: QColor) -> QColor:
        """Tinta legível por cima de uma cor de dado (já misturada com o fundo quando ela tem alfa)."""
        alfa = cor.alphaF()
        mistura = QColor.fromRgbF(*(alfa * c + (1 - alfa) * f
                                    for c, f in zip(cor.getRgbF()[:3], self.fundo.getRgbF()[:3])))
        base = tema_v2.luminancia(mistura.name())

        def contraste(tinta: QColor) -> float:
            outra = tema_v2.luminancia(tinta.name())
            return (max(base, outra) + 0.05) / (min(base, outra) + 0.05)

        return max((self.tinta, self.fundo), key=contraste)


# ---------------------------------------------------------------------------- texto e traços comuns
def _fio(v: float) -> float:
    """Centro de pixel: um fio de 1 px desenhado aqui não se espalha por dois."""
    return math.floor(v) + 0.5


def _caixa(letra: _Letra, texto: str, x: float, y: float, ah: int = -1, av: int = 0) -> QRectF:
    """Retângulo do texto ancorado em (x, y). `ah`: -1 começa em x, 0 centra, 1 termina em x.
    `av`: -1 fica abaixo de y, 0 centra, 1 fica acima."""
    largura, altura = letra.m.horizontalAdvance(texto), letra.m.height()
    esquerda = x if ah < 0 else (x - largura / 2 if ah == 0 else x - largura)
    topo = y if av < 0 else (y - altura / 2 if av == 0 else y - altura)
    return QRectF(round(esquerda), round(topo), largura, altura)


def _encaixar(ret: QRectF, limite: QRectF) -> QRectF:
    """Desloca o retângulo na horizontal até caber em `limite`."""
    return ret.translated(max(limite.left() - ret.left(), 0.0) or min(limite.right() - ret.right(), 0.0), 0.0)


def _escrever(p: QPainter, letra: _Letra, cor: QColor, ret: QRectF, texto: str, placa: QColor | None = None) -> None:
    if placa is not None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(placa)
        p.drawRoundedRect(ret.adjusted(-3, -1, 3, 1), 3, 3)
    p.setFont(letra.fonte)
    p.setPen(cor)
    p.drawText(QPointF(ret.left(), ret.top() + letra.m.ascent()), texto)


def _cortar(letra: _Letra, texto: str, largura: float) -> str:
    return letra.m.elidedText(texto, Qt.TextElideMode.ElideRight, max(0.0, largura))


def _arredondada(ret: QRectF, raio: float, lado: str) -> QPainterPath:
    """Barra com as duas pontas de um lado arredondadas ("cima", "baixo", "esquerda", "direita" ou "todos"):
    a ponta redonda fica só do lado do dado."""
    r = max(0.0, min(raio, ret.width() / 2, ret.height() / 2))
    cantos = {"cima": (r, r, 0, 0), "baixo": (0, 0, r, r), "esquerda": (r, 0, 0, r), "direita": (0, r, r, 0),
              "todos": (r, r, r, r)}.get(lado, (0, 0, 0, 0))
    se, sd, id_, ie = cantos                        # superior esquerdo, superior direito, inferior direito, inferior esquerdo
    caminho = QPainterPath()
    caminho.moveTo(ret.left() + se, ret.top())
    caminho.lineTo(ret.right() - sd, ret.top())
    if sd:
        caminho.arcTo(QRectF(ret.right() - 2 * sd, ret.top(), 2 * sd, 2 * sd), 90, -90)
    caminho.lineTo(ret.right(), ret.bottom() - id_)
    if id_:
        caminho.arcTo(QRectF(ret.right() - 2 * id_, ret.bottom() - 2 * id_, 2 * id_, 2 * id_), 0, -90)
    caminho.lineTo(ret.left() + ie, ret.bottom())
    if ie:
        caminho.arcTo(QRectF(ret.left(), ret.bottom() - 2 * ie, 2 * ie, 2 * ie), 270, -90)
    caminho.lineTo(ret.left(), ret.top() + se)
    if se:
        caminho.arcTo(QRectF(ret.left(), ret.top(), 2 * se, 2 * se), 180, -90)
    caminho.closeSubpath()
    return caminho


def _marca(p: QPainter, centro: QPointF, forma: int, tamanho: float) -> None:
    """Marcador de dispersão e de legenda: 0 círculo, 1 quadrado, 2 triângulo, 3 losango."""
    r = tamanho / 2
    x, y = centro.x(), centro.y()
    if forma % 4 == 0:
        p.drawEllipse(centro, r, r)
    elif forma % 4 == 1:
        p.drawRect(QRectF(x - r * 0.88, y - r * 0.88, r * 1.76, r * 1.76))
    elif forma % 4 == 2:
        p.drawPolygon(QPolygonF([QPointF(x, y - r * 1.1), QPointF(x + r * 1.1, y + r * 0.85), QPointF(x - r * 1.1, y + r * 0.85)]))
    else:
        p.drawPolygon(QPolygonF([QPointF(x, y - r * 1.2), QPointF(x + r * 1.2, y), QPointF(x, y + r * 1.2), QPointF(x - r * 1.2, y)]))


def _hachura(p: QPainter, ret: QRectF, cor: QColor) -> None:
    """Retângulo hachurado em diagonal (terminal bloqueado na fita, célula sem valor no calor)."""
    fundo = QColor(cor)
    fundo.setAlphaF(cor.alphaF() * 0.16)
    p.fillRect(ret, fundo)
    traco = QColor(cor)
    traco.setAlphaF(cor.alphaF() * 0.70)
    p.save()
    p.setClipRect(ret)
    p.setPen(QPen(traco, 1))
    passo, altura = 5.0, ret.height()
    k = ret.left() - altura
    while k < ret.right():
        p.drawLine(QPointF(k, ret.bottom()), QPointF(k + altura, ret.top()))
        k += passo
    p.restore()


class _Reserva:
    """Retângulos já tomados por rótulos soltos: um rótulo novo só entra onde não cobre outro."""

    def __init__(self) -> None:
        self._tomados: list[QRectF] = []

    def livre(self, ret: QRectF) -> bool:
        return not any(ret.intersects(t) for t in self._tomados)

    def tomar(self, ret: QRectF, folga: float = 4.0) -> None:
        """Reserva o retângulo com `folga` pixels de respiro dos lados (zero para reservar uma barra exata)."""
        self._tomados.append(ret.adjusted(-folga, -min(folga, 1.0), folga, min(folga, 1.0)))

    def primeiro_livre(self, candidatos: Sequence[QRectF]) -> QRectF:
        """O primeiro candidato que não cobre ninguém; se nenhum servir, vale o primeiro."""
        escolhido = next((c for c in candidatos if self.livre(c)), candidatos[0])
        self.tomar(escolhido)
        return escolhido


# ---------------------------------------------------------------------------- plano cartesiano
class _Plano:
    """Área dos dados com os dois eixos: converte valor em pixel."""

    def __init__(self, ret: QRectF, ex: _Eixo, ey: _Eixo) -> None:
        self.ret, self.ex, self.ey = ret, ex, ey

    def x(self, v: float) -> float:
        return self.ret.left() + self.ex.fracao(v) * self.ret.width()

    def y(self, v: float) -> float:
        return self.ret.bottom() - self.ey.fracao(v) * self.ret.height()

    def contem(self, x: float, y: float, folga: float = 6.0) -> bool:
        return self.ret.adjusted(-folga, -folga, folga, folga).contains(x, y)


def _largura_rotulos(e: _Estilo, textos: Sequence[str]) -> float:
    return max((e.rotulo.m.horizontalAdvance(t) for t in textos), default=0.0)


def _montar_plano(area: QRectF, e: _Estilo, ex: _Eixo, ey: _Eixo, *, topo: float, direita: float, baixo: float,
                  esquerda: float | None = None) -> _Plano:
    """Tira de `area` as margens dos rótulos; o que sobra é a área dos dados (nunca menor que 1 px)."""
    if esquerda is None:
        esquerda = _largura_rotulos(e, ey.textos) + 10
    ret = QRectF(area.left() + esquerda, area.top() + topo,
                 max(1.0, area.width() - esquerda - direita), max(1.0, area.height() - topo - baixo))
    return _Plano(ret, ex, ey)


def _pintar_grade(p: QPainter, e: _Estilo, plano: _Plano, horizontais: Sequence[float], verticais: Sequence[float]) -> None:
    ret = plano.ret
    p.setPen(QPen(e.grade, 1))
    for v in horizontais:
        y = _fio(plano.y(v))
        p.drawLine(QPointF(ret.left(), y), QPointF(ret.right(), y))
    for v in verticais:
        x = _fio(plano.x(v))
        p.drawLine(QPointF(x, ret.top()), QPointF(x, ret.bottom()))


def _pintar_rotulos_y(p: QPainter, e: _Estilo, plano: _Plano) -> None:
    anterior: QRectF | None = None
    for v, texto in zip(plano.ey.marcas, plano.ey.textos):
        ret = _caixa(e.rotulo, texto, plano.ret.left() - 8, plano.y(v), ah=1)
        if anterior is None or not ret.intersects(anterior):
            _escrever(p, e.rotulo, e.tinta3, ret, texto)
            anterior = ret


def _pintar_rotulos_x(p: QPainter, e: _Estilo, plano: _Plano, limite: QRectF) -> list[float]:
    """Escreve os rótulos do eixo X de tantos em tantos, para um não encostar no outro, e devolve as
    marcas que ganharam rótulo (a grade vertical acompanha)."""
    eixo, topo = plano.ex, plano.ret.bottom() + 6
    caixas = [_encaixar(_caixa(e.rotulo, t, plano.x(v), topo, ah=0, av=-1), limite)
              for v, t in zip(eixo.marcas, eixo.textos)]
    n = len(caixas)
    salto = next((k for k in range(1, n) if all(not caixas[i].adjusted(-5, 0, 5, 0).intersects(caixas[i + k])
                                                for i in range(0, n - k, k))), max(1, n))
    for i in range(0, n, salto):
        _escrever(p, e.rotulo, e.tinta3, caixas[i], eixo.textos[i])
    return [eixo.marcas[i] for i in range(0, n, salto)]


def _pintar_titulos(p: QPainter, e: _Estilo, plano: _Plano, area: QRectF, reserva: _Reserva) -> None:
    """Título do eixo Y no alto, à esquerda (deitado, para ler sem virar a cabeça), e do X embaixo, à direita."""
    ret = plano.ret
    if plano.ey.rotulo:
        caixa = _caixa(e.rotulo, plano.ey.rotulo, area.left(), ret.top() - 8, av=1)
        if reserva.livre(caixa):
            reserva.tomar(caixa)
            _escrever(p, e.rotulo, e.tinta2, caixa, plano.ey.rotulo)
    if plano.ex.rotulo:
        texto = _cortar(e.rotulo, plano.ex.rotulo, ret.width())
        _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, texto, ret.right(), area.bottom(), ah=1, av=1), texto)


# ---------------------------------------------------------------------------- marcadores de limiar
@dataclass(frozen=True)
class _Marcador:
    valor: float
    rotulo: str
    estilo: str


def _marcadores(bruto: Any, campo: str) -> list[_Marcador]:
    saida = []
    for item in _lista(bruto):
        m = _mapa(item)
        valor = _numero(m.get(campo))
        if valor is not None:
            estilo = m.get("estilo")
            saida.append(_Marcador(valor, _texto(m.get("rotulo")), estilo if estilo in ("vigor", "estudo") else "nota"))
    return saida


def _caneta_limiar(e: _Estilo, estilo: str) -> QPen:
    """Os três traços nunca repetem cor nem padrão: vigor tracejado [4, 3], estudo pontilhado [1, 3], nota em fio."""
    if estilo == "nota":
        return QPen(e.tinta3, 1)
    caneta = QPen(e.tinta if estilo == "vigor" else e.tinta2, 1.5)
    traco, vao = (4.0, 3.0) if estilo == "vigor" else (1.0, 3.0)
    caneta.setDashPattern([traco / 1.5, vao / 1.5])          # o padrão do Qt é em múltiplos da largura
    caneta.setCapStyle(Qt.PenCapStyle.FlatCap)
    return caneta


def _pintar_limiares(p: QPainter, e: _Estilo, plano: _Plano, verticais: Sequence[_Marcador],
                     horizontais: Sequence[_Marcador], reserva: _Reserva, limite: QRectF) -> None:
    """A linha do limiar atravessa a área dos dados; o rótulo do vertical fica no topo, fora dela."""
    ret = plano.ret
    visiveis = sorted((m for m in verticais if plano.ex.minimo <= m.valor <= plano.ex.maximo), key=lambda m: m.valor)
    for i, m in enumerate(visiveis):
        x = plano.x(m.valor)
        caneta = _caneta_limiar(e, m.estilo)
        p.setPen(caneta)
        p.drawLine(QPointF(x, ret.top()), QPointF(x, ret.bottom()))
        if m.rotulo:
            # sozinho, o rótulo centra na linha; em dupla, o da esquerda termina nela e o da direita começa nela
            ordem = (0, -1, 1) if len(visiveis) == 1 else ((1, 0, -1) if i == 0 else (-1, 0, 1))
            candidatos = [_encaixar(_caixa(e.rotulo, m.rotulo, x - 4 * ah, ret.top() - 8, ah=ah, av=1), limite)
                          for ah in ordem]
            _escrever(p, e.rotulo, caneta.color(), reserva.primeiro_livre(candidatos), m.rotulo)
    for m in horizontais:
        if not plano.ey.minimo <= m.valor <= plano.ey.maximo:
            continue
        y = plano.y(m.valor)
        caneta = _caneta_limiar(e, m.estilo)
        p.setPen(caneta)
        p.drawLine(QPointF(ret.left(), y), QPointF(ret.right(), y))
        if m.rotulo:
            texto = _cortar(e.rotulo, m.rotulo, ret.width() - 8)
            candidatos = [_caixa(e.rotulo, texto, ret.right() - 4, y - 3, ah=1, av=1),
                          _caixa(e.rotulo, texto, ret.right() - 4, y + 3, ah=1, av=-1),
                          _caixa(e.rotulo, texto, ret.left() + 4, y - 3, av=1),
                          _caixa(e.rotulo, texto, ret.left() + 4, y + 3, av=-1)]
            cabem = [c for c in candidatos if c.top() >= ret.top() - 2 and c.bottom() <= ret.bottom() + 2]
            _escrever(p, e.rotulo, caneta.color(), reserva.primeiro_livre(cabem or candidatos), texto, placa=e.placa)


def _pintar_vazio(p: QPainter, e: _Estilo, area: QRectF, frase: str) -> None:
    """Vazio honesto: só a moldura e a frase."""
    p.setPen(QPen(e.grade, 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(_fio(area.left()), _fio(area.top()), max(1.0, area.width() - 1), max(1.0, area.height() - 1)), 8, 8)
    texto = _cortar(e.corpo, frase, area.width() - 24)
    _escrever(p, e.corpo, e.tinta3, _caixa(e.corpo, texto, area.center().x(), area.center().y(), ah=0), texto)


# ---------------------------------------------------------------------------- base dos seis desenhos
@dataclass(frozen=True)
class _Alvo:
    """Um dado que a leitura sob o cursor alcança: onde está, que realce pede e de onde vem o texto."""
    px: float
    py: float
    ret: QRectF
    forma: str                      # "fio", "anel" ou "caixa": o realce que o cartão desenha por cima
    ref: tuple


class _Desenho:
    """Base dos seis desenhos: a geometria fica pronta no construtor; pintar e ler vêm depois."""

    def __init__(self, dados: dict, area: QRectF, e: _Estilo) -> None:
        self.dados, self.area, self.e = dados, area, e
        self.alvos: list[_Alvo] = []
        self.tem_dado = False

    def pintar(self, p: QPainter) -> None:
        if self.tem_dado:
            self._pintar(p)
        else:
            _pintar_vazio(p, self.e, self.area, _texto(self.dados.get("vazio")) or FRASE_VAZIO)

    def leitura(self, indice: int) -> dict:
        """Dicionário da leitura do alvo `indice`, ou {} se ele não existir."""
        if not 0 <= indice < len(self.alvos):
            return {}
        alvo = self.alvos[indice]
        return {"texto": self._ler(alvo), "px": alvo.px, "py": alvo.py, "indice": indice, "forma": alvo.forma,
                "rx": alvo.ret.x(), "ry": alvo.ret.y(), "rl": alvo.ret.width(), "ra": alvo.ret.height(),
                **self._extra(alvo)}

    def escolher(self, x: float, y: float) -> int:
        """Índice do alvo sob o cursor, ou -1."""
        raise NotImplementedError

    def _pintar(self, p: QPainter) -> None:
        raise NotImplementedError

    def _ler(self, alvo: _Alvo) -> str:
        raise NotImplementedError

    def _extra(self, alvo: _Alvo) -> dict:
        """Chaves a mais na leitura (a fita devolve o `id` do evento)."""
        return {}

    def _mais_perto(self, x: float, y: float, alcance: float) -> int:
        """Alvo mais próximo do cursor em linha reta, até `alcance` pixels."""
        melhor, distancia = -1, alcance * alcance
        for i, alvo in enumerate(self.alvos):
            d = (alvo.px - x) ** 2 + (alvo.py - y) ** 2
            if d <= distancia:
                melhor, distancia = i, d
        return melhor


# ---------------------------------------------------------------------------- xy
@dataclass(frozen=True)
class _SerieXY:
    nome: str
    cor: Any
    pontos: tuple[tuple[int, float, float | None], ...]      # (posição em `pontos`, x, y)
    rotulos: tuple[str, ...]
    estilo: str
    tracejada: bool
    faixa: tuple[tuple[float, float, float], ...]
    ponta: bool | None


def _series_xy(dados: dict) -> list[_SerieXY]:
    series = []
    for i, bruto in enumerate(_lista(dados.get("series"))):
        s = _mapa(bruto)
        pontos = []
        for k, item in enumerate(_lista(s.get("pontos"))):
            par = _lista(item)
            x = _numero(par[0]) if par else None
            if x is not None:
                pontos.append((k, x, _numero(par[1]) if len(par) > 1 else None))
        faixa = []
        for item in _lista(s.get("faixa")):
            trio = [_numero(v) for v in _lista(item)[:3]]
            if len(trio) == 3 and None not in trio:
                faixa.append((trio[0], trio[1], trio[2]))
        estilo, ponta = s.get("estilo"), s.get("rotuloPonta")
        series.append(_SerieXY(_texto(s.get("nome")), s.get("cor", f"serie{i}"), tuple(pontos),
                               tuple(_texto(r) for r in _lista(s.get("rotulos"))),
                               estilo if estilo in ("degrau", "pontos") else "linha", bool(s.get("tracejada")),
                               tuple(faixa), ponta if isinstance(ponta, bool) else None))
    return series


class _XY(_Desenho):
    """Relação entre duas medidas: linhas, degraus ou pontos, com limiares, faixas e anotações."""

    def __init__(self, dados: dict, area: QRectF, e: _Estilo) -> None:
        super().__init__(dados, area, e)
        self.series = _series_xy(dados)
        self.verticais = _marcadores(dados.get("marcadoresV"), "x")
        self.horizontais = _marcadores(dados.get("marcadoresH"), "y")
        self.anotacoes = [(ponto[0], ponto[1], _texto(a.get("texto")))
                          for a in map(_mapa, _lista(dados.get("anotacoes")))
                          if (ponto := _ponto([a.get("x"), a.get("y")])) is not None]
        xs = [x for s in self.series for _, x, y in s.pontos if y is not None] + [x for s in self.series for x, _, _ in s.faixa]
        ys = [y for s in self.series for _, _, y in s.pontos if y is not None]
        ys += [v for s in self.series for _, a, b in s.faixa for v in (a, b)]
        self.tem_dado = bool(ys)
        self.compacto = area.height() < 170             # pequenos múltiplos: sem título de eixo
        ex = _eixo(dados.get("eixoX"), xs + [m.valor for m in self.verticais] + [a[0] for a in self.anotacoes],
                   alvo=5 if area.width() >= 420 else 3, justo=True)
        ey = _eixo(dados.get("eixoY"), ys + [m.valor for m in self.horizontais] + [a[1] for a in self.anotacoes],
                   alvo=4 if area.height() >= 150 else 2, do_zero=all(v >= 0 for v in ys))
        diretas = 2 <= len(self.series) <= 4            # até 4 séries: rótulo direto na ponta, além da legenda
        self.pontas = [s for s in self.series if s.nome and (diretas if s.ponta is None else s.ponta)
                       and any(y is not None for _, _, y in s.pontos)]
        direita = min(120.0, _largura_rotulos(e, [s.nome for s in self.pontas])) + 24 if self.pontas else 10.0
        tem_topo = any(m.rotulo for m in self.verticais) or (bool(ey.rotulo) and not self.compacto)
        self.plano = _montar_plano(area, e, ex, ey, topo=22 if tem_topo else 8, direita=direita,
                                   baixo=22 + (16 if ex.rotulo and not self.compacto else 0))
        ret = self.plano.ret
        for si, s in enumerate(self.series):
            for k, x, y in s.pontos:
                if y is not None:
                    px = min(max(self.plano.x(x), ret.left()), ret.right())
                    py = min(max(self.plano.y(y), ret.top()), ret.bottom())
                    self.alvos.append(_Alvo(px, py, QRectF(px - 0.5, ret.top(), 1.0, ret.height()), "fio", (si, k, x, y)))

    def _pintar(self, p: QPainter) -> None:
        e, plano = self.e, self.plano
        _pintar_grade(p, e, plano, plano.ey.marcas, _pintar_rotulos_x(p, e, plano, self.area))
        _pintar_rotulos_y(p, e, plano)
        p.save()
        p.setClipRect(plano.ret.adjusted(-5, -5, 5, 5))
        for s in self.series:
            self._pintar_faixa(p, s)
        for s in self.series:
            self._pintar_serie(p, s)
        p.restore()
        reserva = _Reserva()
        _pintar_limiares(p, e, plano, self.verticais, self.horizontais, reserva, self.area)
        self._pintar_anotacoes(p, reserva)
        self._pintar_pontas(p)
        if not self.compacto:
            _pintar_titulos(p, e, plano, self.area, reserva)

    def _pintar_faixa(self, p: QPainter, s: _SerieXY) -> None:
        if len(s.faixa) < 2:
            return
        cor = self.e.cor(s.cor)
        cor.setAlphaF(0.16)
        contorno = [QPointF(self.plano.x(x), self.plano.y(alto)) for x, _, alto in s.faixa]
        contorno += [QPointF(self.plano.x(x), self.plano.y(baixo)) for x, baixo, _ in reversed(s.faixa)]
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(cor)
        p.drawPolygon(QPolygonF(contorno))

    def _pintar_serie(self, p: QPainter, s: _SerieXY) -> None:
        cor = self.e.cor(s.cor)
        pontos = [QPointF(self.plano.x(x), self.plano.y(y)) for _, x, y in s.pontos if y is not None]
        if s.estilo != "pontos":
            caneta = QPen(cor, 2)
            caneta.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            caneta.setCapStyle(Qt.PenCapStyle.FlatCap if s.tracejada else Qt.PenCapStyle.RoundCap)
            if s.tracejada:
                caneta.setDashPattern([2.5, 2.0])
            p.setPen(caneta)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(self._caminho(s))
        if s.estilo == "pontos" or (s.estilo == "linha" and len(pontos) <= 16):
            raio = 4.0 if s.estilo == "pontos" and len(pontos) <= 60 else 2.5
            p.setPen(QPen(self.e.fundo, 1.5) if s.estilo == "linha" else Qt.PenStyle.NoPen)
            p.setBrush(cor)
            for ponto in pontos:
                p.drawEllipse(ponto, raio, raio)

    def _caminho(self, s: _SerieXY) -> QPainterPath:
        """Linha da série; um y ausente interrompe o traço em vez de ligar os vizinhos."""
        caminho = QPainterPath()
        aberto = False
        for _, x, y in s.pontos:
            if y is None:
                aberto = False
                continue
            ponto = QPointF(self.plano.x(x), self.plano.y(y))
            if not aberto:
                caminho.moveTo(ponto)
                aberto = True
                continue
            if s.estilo == "degrau":
                caminho.lineTo(QPointF(ponto.x(), caminho.currentPosition().y()))
            caminho.lineTo(ponto)
        return caminho

    def _pintar_anotacoes(self, p: QPainter, reserva: _Reserva) -> None:
        e, ret = self.e, self.plano.ret
        for x, y, texto in self.anotacoes:
            centro = QPointF(self.plano.x(x), self.plano.y(y))
            if not self.plano.contem(centro.x(), centro.y(), 1.0):
                continue
            p.setPen(QPen(e.tinta, 1.5))
            p.setBrush(e.fundo)
            p.drawEllipse(centro, 4.0, 4.0)
            if texto:
                candidatos = [_caixa(e.rotulo, texto, centro.x() + 9, centro.y()),
                              _caixa(e.rotulo, texto, centro.x() - 9, centro.y(), ah=1),
                              _caixa(e.rotulo, texto, centro.x(), centro.y() - 8, ah=0, av=1),
                              _caixa(e.rotulo, texto, centro.x(), centro.y() + 8, ah=0, av=-1)]
                cabem = [c for c in candidatos if ret.adjusted(-2, -2, 2, 2).contains(c)]
                _escrever(p, e.rotulo, e.tinta, reserva.primeiro_livre(cabem or candidatos), texto, placa=e.placa)

    def _pintar_pontas(self, p: QPainter) -> None:
        """Nome da série ao lado do último ponto; quando dois ficariam um sobre o outro, o de baixo desce."""
        if not self.pontas:
            return
        e, ret = self.e, self.plano.ret
        itens = []
        for s in self.pontas:
            _, x, y = next(ponto for ponto in reversed(s.pontos) if ponto[2] is not None)
            itens.append([min(max(self.plano.y(y), ret.top()), ret.bottom()), s])
        itens.sort(key=lambda item: item[0])
        altura = e.rotulo.m.height()
        for k in range(1, len(itens)):
            itens[k][0] = max(itens[k][0], itens[k - 1][0] + altura)
        sobra = max(0.0, itens[-1][0] - ret.bottom())
        for y, s in itens:
            y -= sobra
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(e.cor(s.cor))
            p.drawRoundedRect(QRectF(ret.right() + 8, y - 3, 6, 6), 1.5, 1.5)
            texto = _cortar(e.rotulo, s.nome, self.area.right() - ret.right() - 18)
            _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, texto, ret.right() + 18, y), texto)

    def _ler(self, alvo: _Alvo) -> str:
        si, k, x, y = alvo.ref
        s, ex, ey = self.series[si], self.plano.ex, self.plano.ey
        proprio = s.rotulos[k] if k < len(s.rotulos) else ""
        partes = [proprio or s.nome]
        if ex.rotulo or not proprio:                # o rótulo do ponto já diz o X quando o eixo não tem nome
            partes.append(f"{ex.rotulo} {ex.ler(x)}".strip())
        partes.append(f"{ey.rotulo} {ey.ler(y)}".strip())
        return " · ".join(parte for parte in partes if parte)

    def escolher(self, x: float, y: float) -> int:
        if not self.plano.contem(x, y):
            return -1
        melhor, chave = -1, (math.inf, math.inf)
        for i, alvo in enumerate(self.alvos):       # primeiro o X mais próximo (o fio é vertical); no empate, o Y
            atual = (round(abs(alvo.px - x)), abs(alvo.py - y))
            if atual < chave:
                melhor, chave = i, atual
        return melhor


# ---------------------------------------------------------------------------- histograma
@dataclass(frozen=True)
class _SerieHist:
    nome: str
    cor: Any
    contagens: tuple[float, ...]
    sentido: int


def _series_hist(dados: dict) -> tuple[list[float], list[_SerieHist]]:
    """Bordas (crescentes) e séries com uma contagem por faixa; bordas inválidas esvaziam tudo."""
    bordas = [b for b in map(_numero, _lista(dados.get("bordas"))) if b is not None]
    if len(bordas) < 2 or any(a >= b for a, b in zip(bordas, bordas[1:])):
        return [], []
    n = len(bordas) - 1
    series = []
    for i, bruto in enumerate(_lista(dados.get("series"))):
        s = _mapa(bruto)
        contagens = [max(0.0, _numero(c) or 0.0) for c in _lista(s.get("contagens"))[:n]]
        contagens += [0.0] * (n - len(contagens))
        series.append(_SerieHist(_texto(s.get("nome")), s.get("cor", f"serie{i}"), tuple(contagens),
                                 -1 if s.get("sentido") == -1 else 1))
    return bordas, series


class _Histograma(_Desenho):
    """Distribuição em faixas. Série com sentido -1 cresce para baixo do eixo (o "espectro")."""

    def __init__(self, dados: dict, area: QRectF, e: _Estilo) -> None:
        super().__init__(dados, area, e)
        self.bordas, self.series = _series_hist(dados)
        self.verticais = _marcadores(dados.get("marcadoresV"), "x")
        corte = _numero(dados.get("truncarEm"))
        self.corte = corte if corte is not None and corte > 0 else math.inf
        cima = max((c for s in self.series if s.sentido > 0 for c in s.contagens), default=0.0)
        baixo = max((c for s in self.series if s.sentido < 0 for c in s.contagens), default=0.0)
        self.tem_dado = cima > 0 or baixo > 0
        self.espelhado = cima > 0 and baixo > 0
        self.compacto = area.height() < 170
        spec_y = _mapa(dados.get("eixoY"))
        inteiras = all(c.is_integer() for s in self.series for c in s.contagens)
        formato = _texto(spec_y.get("formato")) or ("int" if inteiras else "")
        # a pilha cortada ganha folga acima do corte para o rótulo "+k"; sem corte, o eixo fecha numa marca redonda
        tetos = [min(v, self.corte) * (1.18 if v > self.corte else 1.0) for v in (cima, baixo)]
        # no espectro o passo divide a altura toda (cima + baixo): um lado baixo não herda o teto do outro
        passo = _passo((sum(tetos) if self.espelhado else max(tetos)) or 1.0, 4 if area.height() >= 150 else 2, formato)
        topo_v, fundo_v = (t if v > self.corte else math.ceil(t / passo - 1e-9) * passo
                           for t, v in zip(tetos, (cima, baixo)))
        if not self.tem_dado:
            topo_v = passo
        marcas = _marcas_lineares(-fundo_v, topo_v, passo)
        casas = min(3, max((_casas_de(m) for m in marcas), default=0))
        ey = _Eixo(_texto(spec_y.get("rotulo")), -fundo_v, topo_v, False, formato, tuple(marcas),
                   tuple(_formatar(abs(m), formato, casas) for m in marcas), casas)
        ex = _eixo(dados.get("eixoX"), self.bordas[:1] + self.bordas[-1:], alvo=5 if area.width() >= 420 else 3, justo=True)
        tem_topo = any(m.rotulo for m in self.verticais) or (bool(ey.rotulo) and not self.compacto)
        self.plano = _montar_plano(area, e, ex, ey, topo=22 if tem_topo else 8, direita=10,
                                   baixo=22 + (16 if ex.rotulo and not self.compacto else 0))
        ret = self.plano.ret
        self.zero = self.plano.y(0.0)
        self.cantos = [self.plano.x(b) for b in self.bordas]
        faixas = len(self.bordas) - 1
        largura = (self.cantos[-1] - self.cantos[0]) / faixas if faixas > 0 else 0.0
        self.vao = 2.0 if largura >= 6 else (1.0 if largura >= 3 else 0.0)
        self.casas_bordas = min(3, max((_casas_de(b) for b in self.bordas), default=0))
        for si, s in enumerate(self.series):
            for i, c in enumerate(s.contagens):
                meio = (self.cantos[i] + self.cantos[i + 1]) / 2
                ponta = self.plano.y(s.sentido * min(c, self.corte))
                self.alvos.append(_Alvo(meio, ponta, QRectF(meio - 0.5, ret.top(), 1.0, ret.height()), "fio", (si, i)))

    def _pintar(self, p: QPainter) -> None:
        e, plano, ret = self.e, self.plano, self.plano.ret
        _pintar_rotulos_x(p, e, plano, self.area)
        _pintar_grade(p, e, plano, [m for m in plano.ey.marcas if m != 0], [])
        _pintar_rotulos_y(p, e, plano)
        p.save()
        p.setClipRect(ret.adjusted(0, -1, 0, 1))
        for sentido in (1, -1):
            juntas = [s for s in self.series if s.sentido == sentido]
            for s in juntas:                        # séries do mesmo lado se sobrepõem: a transparência mostra as duas
                self._pintar_barras(p, s, 1.0 if len(juntas) == 1 else 0.72)
        p.restore()
        p.setPen(QPen(e.tinta3, 1))
        p.drawLine(QPointF(ret.left(), _fio(self.zero)), QPointF(ret.right(), _fio(self.zero)))
        reserva = _Reserva()
        self._pintar_cortes(p, reserva)
        _pintar_limiares(p, e, plano, self.verticais, [], reserva, self.area)
        if self.espelhado:
            self._pintar_lados(p)
        if not self.compacto:
            _pintar_titulos(p, e, plano, self.area, reserva)

    def _pintar_barras(self, p: QPainter, s: _SerieHist, alfa: float) -> None:
        cor = self.e.cor(s.cor)
        cor.setAlphaF(cor.alphaF() * alfa)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(cor)
        for i, c in enumerate(s.contagens):
            if c <= 0:
                continue
            esquerda = self.cantos[i] + self.vao / 2
            direita = max(self.cantos[i + 1] - self.vao / 2, esquerda + 1.0)
            altura = max(2.0, abs(self.plano.y(s.sentido * min(c, self.corte)) - self.zero))   # um evento sempre aparece
            barra = QRectF(esquerda, self.zero - altura if s.sentido > 0 else self.zero, direita - esquerda, altura)
            p.drawPath(_arredondada(barra, 0.0 if c > self.corte else 3.0, "cima" if s.sentido > 0 else "baixo"))

    def _pintar_cortes(self, p: QPainter, reserva: _Reserva) -> None:
        """Pilha acima de `truncarEm`: risco de quebra na ponta e o rótulo "+k" com o que ficou de fora."""
        e, faixas = self.e, len(self.bordas) - 1
        cortadas = sorted(((c - self.corte, si, i) for si, s in enumerate(self.series)
                           for i, c in enumerate(s.contagens) if c > self.corte), reverse=True)
        for excesso, si, i in cortadas:
            sentido, alvo = self.series[si].sentido, self.alvos[si * faixas + i]
            y = alvo.py + 5 * sentido
            p.setPen(QPen(e.fundo, 2))
            p.drawLine(QPointF(self.cantos[i], y + 2), QPointF(self.cantos[i + 1], y - 2))
            texto = "+" + self.plano.ey.ler(excesso)
            caixa = _caixa(e.rotulo, texto, alvo.px, alvo.py - 2 * sentido, ah=0, av=sentido)
            if reserva.livre(caixa):                # as maiores primeiro; rótulo que cobriria outro fica de fora
                reserva.tomar(caixa)
                _escrever(p, e.rotulo, e.tinta2, caixa, texto)

    def _pintar_lados(self, p: QPainter) -> None:
        """No espectro, o nome de cada lado vai escrito no canto mais vazio daquele lado."""
        e, ret = self.e, self.plano.ret
        terco = max(1, (len(self.bordas) - 1) // 3)
        for sentido in (1, -1):
            juntas = [s for s in self.series if s.sentido == sentido and s.nome]
            if not juntas:
                continue
            texto = " · ".join(s.nome for s in juntas)
            a_esquerda = sum(sum(s.contagens[:terco]) for s in juntas) <= sum(sum(s.contagens[-terco:]) for s in juntas)
            caixa = _caixa(e.rotulo, texto, ret.left() + 6 if a_esquerda else ret.right() - 6,
                           ret.top() + 4 if sentido > 0 else ret.bottom() - 4, ah=-1 if a_esquerda else 1, av=-sentido)
            _escrever(p, e.rotulo, e.tinta2, caixa, texto, placa=e.placa)

    def _borda(self, ex: _Eixo, v: float) -> str:
        """Borda de faixa por extenso, com casas bastantes para duas vizinhas não saírem iguais."""
        if ex.formato in ("%", "int", "hora"):
            return ex.ler(v)
        casas = len(ex.formato.partition(".")[2]) if ex.formato else ex.casas
        return _decimal(v, max(casas, self.casas_bordas))

    def _ler(self, alvo: _Alvo) -> str:
        si, i = alvo.ref
        s, ex = self.series[si], self.plano.ex
        faixa = f"de {self._borda(ex, self.bordas[i])} a {self._borda(ex, self.bordas[i + 1])}"
        return " · ".join(parte for parte in (s.nome, faixa, self.plano.ey.ler(s.contagens[i])) if parte)

    def escolher(self, x: float, y: float) -> int:
        if not self.plano.contem(x, y) or not self.alvos:
            return -1
        faixas = len(self.bordas) - 1
        i = min(faixas - 1, max(0, bisect_right(self.cantos, x) - 1))
        lado = 1 if y <= self.zero else -1
        candidatas = [si for si, s in enumerate(self.series) if s.sentido == lado] or list(range(len(self.series)))
        return min(candidatas, key=lambda si: abs(self.alvos[si * faixas + i].py - y)) * faixas + i


# ---------------------------------------------------------------------------- barras
@dataclass(frozen=True)
class _SerieBarras:
    nome: str
    cor: Any
    valores: tuple[float | None, ...]


def _series_barras(dados: dict) -> tuple[list[str], list[_SerieBarras]]:
    """Categorias e séries com um valor por categoria (o que faltar fica sem valor)."""
    brutas = [_mapa(s) for s in _lista(dados.get("series"))]
    categorias = [_texto(c) for c in _lista(dados.get("categorias"))]
    n = max([len(categorias)] + [len(_lista(s.get("valores"))) for s in brutas])
    categorias += [""] * (n - len(categorias))
    series = []
    for i, s in enumerate(brutas):
        valores = [_numero(v) for v in _lista(s.get("valores"))]
        valores += [None] * (n - len(valores))
        series.append(_SerieBarras(_texto(s.get("nome")), s.get("cor", f"serie{i}"), tuple(valores)))
    return categorias, series


def _distancia(ret: QRectF, x: float, y: float) -> float:
    """Distância de um ponto a um retângulo (zero dentro dele)."""
    return math.hypot(max(ret.left() - x, 0.0, x - ret.right()), max(ret.top() - y, 0.0, y - ret.bottom()))


class _Barras(_Desenho):
    """Comparação entre categorias. Empilhada e deitada numa linha só, é a barra de composição."""

    def __init__(self, dados: dict, area: QRectF, e: _Estilo) -> None:
        super().__init__(dados, area, e)
        self.categorias, self.series = _series_barras(dados)
        n = len(self.categorias)
        self.deitado = dados.get("orientacao") == "h"
        self.inclinado = False
        self.empilhado = bool(dados.get("empilhado"))
        self.rotulos_valor = bool(dados.get("rotulosValor"))
        self.tem_dado = any(v is not None for s in self.series for v in s.valores)
        if self.empilhado:
            extremos = [sum(max(0.0, s.valores[c] or 0.0) for s in self.series) for c in range(n)]
        else:
            extremos = [v for s in self.series for v in s.valores if v is not None]
        self.verticais = _marcadores(dados.get("marcadoresV"), "x") if self.deitado else []
        self.horizontais = [] if self.deitado else _marcadores(dados.get("marcadoresH"), "y")
        comprido = area.width() if self.deitado else area.height()
        valor = _eixo(dados.get("eixoX" if self.deitado else "eixoY"),
                      extremos + [m.valor for m in self.verticais + self.horizontais],
                      alvo=(5 if comprido >= 420 else 3) if self.deitado else (4 if comprido >= 150 else 2), do_zero=True)
        nome_cat = _texto(_mapa(dados.get("eixoY" if self.deitado else "eixoX")).get("rotulo"))
        cat = _Eixo(nome_cat, 0.0, float(max(1, n)), False, "", (), (), 0)
        self.valor = valor
        self.base = valor.minimo if valor.log else min(max(0.0, valor.minimo), valor.maximo)
        if self.deitado:
            self.largura_cat = min(_largura_rotulos(e, self.categorias), area.width() * 0.34)
            folga = 0.0
            if self.rotulos_valor and not self.empilhado:
                folga = _largura_rotulos(e, [valor.ler(v) for v in extremos]) + 8
            self.plano = _montar_plano(area, e, valor, cat, esquerda=self.largura_cat + 10 if self.largura_cat else 4.0,
                                       topo=22 if nome_cat or any(m.rotulo for m in self.verticais) else 6,
                                       direita=10 + folga, baixo=22 + (16 if valor.rotulo else 0))
        else:
            # categorias embaixo: deitadas quando cabem na banda; senão inclinadas, e a área dos dados encolhe
            topo, baixo = 22 if valor.rotulo or self.rotulos_valor else 8, 22 + (16 if nome_cat else 0)
            self.plano = _montar_plano(area, e, cat, valor, topo=topo, direita=10, baixo=baixo)
            banda = self.plano.ret.width() / max(1, n)
            self.largura_cat = min(_largura_rotulos(e, self.categorias), 84.0)
            self.inclinado = self.largura_cat > banda - 6 and banda >= 14 and area.height() >= 170
            if self.inclinado:
                baixo += (self.largura_cat + e.rotulo.m.height()) * 0.7071 - 10
                self.plano = _montar_plano(area, e, cat, valor, topo=topo, direita=10, baixo=baixo)
        ret = self.plano.ret
        self.banda = (ret.height() if self.deitado else ret.width()) / max(1, n)
        lado_a_lado = 1 if self.empilhado else max(1, len(self.series))
        self.espessura = max(1.5, min(22.0 if self.deitado else 36.0, (self.banda * 0.76 - 2 * (lado_a_lado - 1)) / lado_a_lado))
        for c in range(n):
            if self.empilhado:
                self._empilhar(c)
            else:
                self._agrupar(c, lado_a_lado)

    def _centro(self, c: int) -> float:
        ret = self.plano.ret
        return (ret.top() if self.deitado else ret.left()) + (c + 0.5) * self.banda

    def _px(self, v: float) -> float:
        return self.plano.x(v) if self.deitado else self.plano.y(v)

    def _barra(self, centro: float, a: float, b: float) -> QRectF:
        """Retângulo da barra: `centro` no eixo das categorias, de `a` a `b` (pixels) no eixo do valor."""
        menor, tamanho = min(a, b), abs(a - b)
        if self.deitado:
            return QRectF(menor, centro - self.espessura / 2, tamanho, self.espessura)
        return QRectF(centro - self.espessura / 2, menor, self.espessura, tamanho)

    def _alvo(self, ret: QRectF, sobe: bool, ref: tuple) -> None:
        if self.deitado:
            ponta = QPointF(ret.right() if sobe else ret.left(), ret.center().y())
        else:
            ponta = QPointF(ret.center().x(), ret.top() if sobe else ret.bottom())
        self.alvos.append(_Alvo(ponta.x(), ponta.y(), ret, "caixa", ref))

    def _agrupar(self, c: int, lado_a_lado: int) -> None:
        zero = self._px(self.base)
        for si, s in enumerate(self.series):
            v = s.valores[c]
            if v is None:
                continue
            centro = self._centro(c) + (si - (lado_a_lado - 1) / 2) * (self.espessura + 2)
            sobe = v >= self.base
            ponta = self._px(v)
            if v != self.base and abs(ponta - zero) < 2:               # valor pequeno ainda aparece
                ponta = zero + (2 if sobe == self.deitado else -2)
            lado = ("direita" if sobe else "esquerda") if self.deitado else ("cima" if sobe else "baixo")
            self._alvo(self._barra(centro, zero, ponta), sobe, (si, c, v, lado))

    def _empilhar(self, c: int) -> None:
        """Segmentos um depois do outro, com 2 px de fenda; só o último tem a ponta redonda."""
        presentes = [(si, max(0.0, s.valores[c])) for si, s in enumerate(self.series) if s.valores[c] is not None]
        ultimo = max((si for si, v in presentes if v > 0), default=-1)
        acumulado, primeiro = self.base, True
        for si, v in presentes:
            a, b = self._px(acumulado), self._px(acumulado + v)
            acumulado += v
            ret = self._barra(self._centro(c), a, b)
            if v > 0 and not primeiro:
                if self.deitado and ret.width() > 3:
                    ret.setLeft(ret.left() + 2)
                elif not self.deitado and ret.height() > 3:
                    ret.setBottom(ret.bottom() - 2)
            primeiro = primeiro and v <= 0
            lado = ("direita" if self.deitado else "cima") if si == ultimo else ""
            self._alvo(ret, True, (si, c, self.series[si].valores[c], lado))

    def _pintar(self, p: QPainter) -> None:
        e, plano, ret = self.e, self.plano, self.plano.ret
        if self.deitado:
            rotuladas = _pintar_rotulos_x(p, e, plano, self.area)
            _pintar_grade(p, e, plano, [], [m for m in rotuladas if m != self.base])
        else:
            _pintar_grade(p, e, plano, [m for m in self.valor.marcas if m != self.base], [])
            _pintar_rotulos_y(p, e, plano)
        self._pintar_categorias(p)
        p.save()
        p.setClipRect(ret.adjusted(-1, -1, 1, 1))
        p.setPen(Qt.PenStyle.NoPen)
        for alvo in self.alvos:
            si, _, _, lado = alvo.ref
            if alvo.ret.width() > 0 and alvo.ret.height() > 0:
                p.setBrush(e.cor(self.series[si].cor))
                p.drawPath(_arredondada(alvo.ret, 3.0, lado))
        p.restore()
        zero = _fio(self._px(self.base))
        p.setPen(QPen(e.tinta3, 1))
        if self.deitado:
            p.drawLine(QPointF(zero, ret.top()), QPointF(zero, ret.bottom()))
        else:
            p.drawLine(QPointF(ret.left(), zero), QPointF(ret.right(), zero))
        reserva = _Reserva()
        _pintar_limiares(p, e, plano, self.verticais, self.horizontais, reserva, self.area)
        _pintar_titulos(p, e, plano, self.area, reserva)
        if self.rotulos_valor:
            self._pintar_valores(p, reserva)

    def _pintar_categorias(self, p: QPainter) -> None:
        e, ret = self.e, self.plano.ret
        if self.deitado:
            salto = max(1, math.ceil(e.rotulo.m.height() / max(1.0, self.banda)))
            for c in range(0, len(self.categorias), salto):
                texto = _cortar(e.rotulo, self.categorias[c], self.largura_cat)
                _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, texto, ret.left() - 8, self._centro(c), ah=1), texto)
            return
        if self.inclinado:
            for c, categoria in enumerate(self.categorias):
                texto = _cortar(e.rotulo, categoria, self.largura_cat)
                p.save()                           # a 45°, terminando embaixo da barra
                p.translate(self._centro(c) + 3, ret.bottom() + 6)
                p.rotate(-45)
                _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, texto, 0, 0, ah=1, av=-1), texto)
                p.restore()
            return
        salto = max(1, math.ceil(26 / max(1.0, self.banda)))
        for c in range(0, len(self.categorias), salto):
            texto = _cortar(e.rotulo, self.categorias[c], self.banda * salto - 6)
            caixa = _caixa(e.rotulo, texto, self._centro(c), ret.bottom() + 6, ah=0, av=-1)
            _escrever(p, e.rotulo, e.tinta2, _encaixar(caixa, self.area), texto)

    def _pintar_valores(self, p: QPainter, reserva: _Reserva) -> None:
        """Valor escrito na ponta da barra (ou dentro do segmento, na empilhada), só onde cabe: um rótulo
        nunca cobre uma barra (nem a vizinha, lado a lado) nem outro rótulo."""
        e = self.e
        barras = _Reserva()
        for alvo in self.alvos:
            barras.tomar(alvo.ret, folga=0.0)
        for alvo in self.alvos:
            si, _, v, _ = alvo.ref
            texto = self.valor.ler(v)
            largura, altura = e.rotulo.m.horizontalAdvance(texto), e.rotulo.m.height()
            if self.empilhado:
                if alvo.ret.width() >= largura + 8 and alvo.ret.height() >= altura:
                    centro = alvo.ret.center()
                    _escrever(p, e.rotulo, e.sobre(e.cor(self.series[si].cor)),
                              _caixa(e.rotulo, texto, centro.x(), centro.y(), ah=0), texto)
                continue
            sobe = v >= self.base
            if self.deitado:
                caixa = _caixa(e.rotulo, texto, alvo.px + (5 if sobe else -5), alvo.py, ah=-1 if sobe else 1)
            else:
                caixa = _caixa(e.rotulo, texto, alvo.px, alvo.py + (-3 if sobe else 3), ah=0, av=1 if sobe else -1)
            if reserva.livre(caixa) and barras.livre(caixa):
                reserva.tomar(caixa, folga=1.5)
                # a placa cobre grade e limiar por trás, mas nunca a barra vizinha
                placa = e.placa if barras.livre(caixa.adjusted(-3, -1, 3, 1)) else None
                _escrever(p, e.rotulo, e.tinta2, caixa, texto, placa=placa)

    def _ler(self, alvo: _Alvo) -> str:
        si, c, v, _ = alvo.ref
        return " · ".join(parte for parte in (self.categorias[c], self.series[si].nome, self.valor.ler(v)) if parte)

    def escolher(self, x: float, y: float) -> int:
        if not self.plano.contem(x, y):
            return -1
        ret = self.plano.ret
        c = int(((y - ret.top()) if self.deitado else (x - ret.left())) // max(1e-9, self.banda))
        candidatos = [i for i, alvo in enumerate(self.alvos) if alvo.ref[1] == c]
        return min(candidatos, key=lambda i: _distancia(self.alvos[i].ret, x, y), default=-1)


# ---------------------------------------------------------------------------- calor
class _Calor(_Desenho):
    """Matriz linha × coluna em que a cor é a magnitude; a barra de escala ao lado diz quanto vale cada tom."""

    def __init__(self, dados: dict, area: QRectF, e: _Estilo) -> None:
        super().__init__(dados, area, e)
        valores = [[_numero(v) for v in _lista(linha)] for linha in _lista(dados.get("valores"))]
        self.linhas = [_texto(t) for t in _lista(dados.get("linhas"))]
        self.colunas = [_texto(t) for t in _lista(dados.get("colunas"))]
        nl = max(len(self.linhas), len(valores))
        nc = max([len(self.colunas)] + [len(linha) for linha in valores])
        self.linhas += [""] * (nl - len(self.linhas))
        self.colunas += [""] * (nc - len(self.colunas))
        valores += [[] for _ in range(nl - len(valores))]
        self.valores = [linha + [None] * (nc - len(linha)) for linha in valores]
        todos = [v for linha in self.valores for v in linha if v is not None]
        self.tem_dado = bool(todos)
        minimo, maximo = _numero(dados.get("min")), _numero(dados.get("max"))
        self.minimo = minimo if minimo is not None else min(todos, default=0.0)
        self.maximo = maximo if maximo is not None else max(todos, default=1.0)
        if self.maximo <= self.minimo:
            self.maximo = self.minimo + 1.0
        self.formato = _texto(dados.get("formato")) or "0.00"
        self.mostrar = bool(dados.get("mostrarValores"))
        self.destaques = [(int(par[0]), int(par[1])) for par in map(_ponto, _lista(dados.get("destaques"))) if par is not None]
        marca = _numero(dados.get("marcaEscala"))
        self.marca = marca if marca is not None and self.minimo <= marca <= self.maximo else None
        # medidas: rótulos das linhas à esquerda, das colunas embaixo (inclinados quando não cabem) e escala à direita
        nl, nc = max(1, nl), max(1, nc)
        largura_linhas = min(_largura_rotulos(e, self.linhas), area.width() * 0.26)
        esquerda = largura_linhas + 8 if largura_linhas else 0.0
        textos_escala = [self._escrever_valor(v) for v in (self.minimo, self.maximo, self.marca) if v is not None]
        direita = 14 + LARGURA_ESCALA + 6 + _largura_rotulos(e, textos_escala)
        largura_colunas = _largura_rotulos(e, self.colunas)
        baixo = e.rotulo.m.height() + 6 if largura_colunas else 0.0

        def lado(reserva_baixo: float) -> float:
            return max(1.0, min((area.width() - esquerda - direita) / nc, (area.height() - reserva_baixo) / nl, 64.0))

        self.celula = lado(baixo)
        self.inclinado = largura_colunas > self.celula - 4
        if self.inclinado:
            self.largura_coluna = min(largura_colunas, 84.0)
            baixo = self.largura_coluna * 0.7071 + e.rotulo.m.height() * 0.7071 + 8
            self.celula = lado(baixo)
        else:
            self.largura_coluna = self.celula - 4
        self.largura_linhas = largura_linhas
        largura, altura = nc * self.celula, nl * self.celula
        x0 = area.left() + esquerda + max(0.0, (area.width() - esquerda - direita - largura) / 2)
        y0 = area.top() + max(0.0, (area.height() - baixo - altura) / 2)
        self.grade = QRectF(x0, y0, largura, altura)
        self.vao = 2.0 if self.celula >= 12 else (1.0 if self.celula >= 5 else 0.0)
        self.indice: dict[tuple[int, int], int] = {}
        for i, linha in enumerate(self.valores):
            for j, v in enumerate(linha):
                if v is not None:
                    ret = self._ret(i, j)
                    self.indice[(i, j)] = len(self.alvos)
                    self.alvos.append(_Alvo(ret.center().x(), ret.center().y(), ret, "caixa", (i, j, v)))

    def _ret(self, i: int, j: int) -> QRectF:
        meio = self.vao / 2
        return QRectF(self.grade.left() + j * self.celula + meio, self.grade.top() + i * self.celula + meio,
                      max(1.0, self.celula - self.vao), max(1.0, self.celula - self.vao))

    def _escrever_valor(self, v: float) -> str:
        return _formatar(v, self.formato)

    def _fracao(self, v: float) -> float:
        return min(1.0, max(0.0, (v - self.minimo) / (self.maximo - self.minimo)))

    def _pintar(self, p: QPainter) -> None:
        e = self.e
        raio = min(3.0, self.celula * 0.18)
        apagada = QColor(e.grade)
        apagada.setAlphaF(0.55)
        p.setPen(Qt.PenStyle.NoPen)
        for i, linha in enumerate(self.valores):
            for j, v in enumerate(linha):
                ret = self._ret(i, j)
                cor = apagada if v is None else e.calor(self._fracao(v))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(cor)
                p.drawRoundedRect(ret, raio, raio)
                if v is not None and self.mostrar:
                    texto = self._escrever_valor(v)
                    if ret.width() >= e.rotulo.m.horizontalAdvance(texto) + 4 and ret.height() >= e.rotulo.m.height():
                        _escrever(p, e.rotulo, e.sobre(cor), _caixa(e.rotulo, texto, ret.center().x(), ret.center().y(), ah=0), texto)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(e.cor("aviso"), 2))
        for i, j in self.destaques:
            if 0 <= i < len(self.linhas) and 0 <= j < len(self.colunas):
                p.drawRoundedRect(self._ret(i, j).adjusted(-1, -1, 1, 1), raio + 1, raio + 1)
        self._pintar_rotulos(p)
        self._pintar_escala(p)

    def _pintar_rotulos(self, p: QPainter) -> None:
        e, grade = self.e, self.grade
        salto = max(1, math.ceil(e.rotulo.m.height() / self.celula))
        for i in range(0, len(self.linhas), salto):
            texto = _cortar(e.rotulo, self.linhas[i], self.largura_linhas)
            _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, texto, grade.left() - 8, grade.top() + (i + 0.5) * self.celula, ah=1), texto)
        for j in range(0, len(self.colunas), salto):
            texto = _cortar(e.rotulo, self.colunas[j], self.largura_coluna)
            x = grade.left() + (j + 0.5) * self.celula
            if not self.inclinado:
                _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, texto, x, grade.bottom() + 6, ah=0, av=-1), texto)
                continue
            p.save()                               # inclinado a 45°, terminando embaixo da coluna
            p.translate(x + 3, grade.bottom() + 6)
            p.rotate(-45)
            _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, texto, 0, 0, ah=1, av=-1), texto)
            p.restore()

    def _pintar_escala(self, p: QPainter) -> None:
        """Barra de escala: os degraus da rampa empilhados, o maior em cima, com os extremos e a marca escritos."""
        e, grade = self.e, self.grade
        rampa = e.paleta["calor"]
        altura = min(grade.height(), 132.0)
        barra = QRectF(grade.right() + 14, grade.top(), LARGURA_ESCALA, altura)
        degrau = altura / len(rampa)
        p.setPen(Qt.PenStyle.NoPen)
        for k, cor in enumerate(reversed(rampa)):
            p.setBrush(QColor(cor))
            p.drawRect(QRectF(barra.left(), barra.top() + k * degrau, barra.width(), degrau + (0.5 if k < len(rampa) - 1 else 0)))
        x = barra.right() + 6
        reserva = _Reserva()
        if self.marca is not None:
            y = barra.bottom() - self._fracao(self.marca) * altura
            p.setPen(QPen(e.tinta, 1.5))
            p.drawLine(QPointF(barra.left() - 3, y), QPointF(barra.right() + 3, y))
            texto = self._escrever_valor(self.marca)
            caixa = _caixa(e.rotulo, texto, x, min(max(y, barra.top() + 6), barra.bottom() - 6))
            reserva.tomar(caixa)
            _escrever(p, e.rotulo, e.tinta, caixa, texto)
        for valor, y, av in ((self.maximo, barra.top() - 2, -1), (self.minimo, barra.bottom() + 2, 1)):
            texto = self._escrever_valor(valor)
            caixa = _caixa(e.rotulo, texto, x, y, av=av)
            if reserva.livre(caixa):
                _escrever(p, e.rotulo, e.tinta3, caixa, texto)

    def _ler(self, alvo: _Alvo) -> str:
        i, j, v = alvo.ref
        par = " × ".join(parte for parte in (self.linhas[i], self.colunas[j]) if parte)
        return " · ".join(parte for parte in (par, self._escrever_valor(v)) if parte)

    def escolher(self, x: float, y: float) -> int:
        if not self.grade.contains(x, y):
            return -1
        return self.indice.get((int((y - self.grade.top()) // self.celula), int((x - self.grade.left()) // self.celula)), -1)


# ---------------------------------------------------------------------------- dispersão
@dataclass(frozen=True)
class _Grupo:
    nome: str
    cor: Any
    forma: int
    pontos: tuple[tuple[int, float, float], ...]      # (posição em `pontos`, x, y)
    rotulos: tuple[str, ...]
    centro: tuple[float, float] | None


def _indice_0a3(v: Any, padrao: int) -> int:
    return v % 4 if isinstance(v, int) and not isinstance(v, bool) else padrao


def _grupos(dados: dict) -> tuple[list[_Grupo], list[tuple[float, float]]]:
    """Grupos e pontos soltos. Sem cor e forma declaradas, a identidade segue a ordem cor0-forma0,
    cor1-forma0, ..., cor3-forma3."""
    grupos = []
    for gi, bruto in enumerate(_lista(dados.get("grupos"))):
        g = _mapa(bruto)
        pontos = tuple((k, ponto[0], ponto[1]) for k, item in enumerate(_lista(g.get("pontos")))
                       if (ponto := _ponto(item)) is not None)
        cor = g.get("cor")
        grupos.append(_Grupo(_texto(g.get("nome")), cor if isinstance(cor, str) else _indice_0a3(cor, gi % 4),
                             _indice_0a3(g.get("forma"), (gi // 4) % 4), pontos,
                             tuple(_texto(r) for r in _lista(g.get("rotulos"))), _ponto(g.get("centro"))))
    outros = [ponto for item in _lista(dados.get("outros")) if (ponto := _ponto(item)) is not None]
    return grupos, outros


def _com_folga(valores: Sequence[float], fracao: float = 0.07) -> list[float]:
    """Os extremos dos valores afastados um pouco, para nenhum marcador ficar colado na borda."""
    if not valores:
        return []
    baixo, alto = min(valores), max(valores)
    folga = (alto - baixo) * fracao
    return [baixo - folga, alto + folga]


class _Dispersao(_Desenho):
    """Amostras em duas dimensões: a identidade de cada grupo é cor mais forma do marcador."""

    def __init__(self, dados: dict, area: QRectF, e: _Estilo) -> None:
        super().__init__(dados, area, e)
        self.grupos, self.outros = _grupos(dados)
        self.rotular_centros = bool(dados.get("rotularCentros"))
        soltos = [(x, y) for g in self.grupos for _, x, y in g.pontos] + self.outros
        self.tem_dado = bool(soltos)
        todos = soltos + [g.centro for g in self.grupos if g.centro is not None]
        ex = _eixo(dados.get("eixoX"), _com_folga([x for x, _ in todos]), alvo=5 if area.width() >= 420 else 3, justo=True)
        ey = _eixo(dados.get("eixoY"), _com_folga([y for _, y in todos]), alvo=4 if area.height() >= 150 else 2, justo=True)
        self.plano = _montar_plano(area, e, ex, ey, topo=22 if ey.rotulo else 10, direita=12,
                                   baixo=22 + (16 if ex.rotulo else 0))
        for gi, g in enumerate(self.grupos):
            for k, x, y in g.pontos:
                self._alvo(x, y, (gi, k))
        for x, y in self.outros:
            self._alvo(x, y, (-1, 0))

    def _alvo(self, x: float, y: float, ref: tuple) -> None:
        px, py = self.plano.x(x), self.plano.y(y)
        self.alvos.append(_Alvo(px, py, QRectF(px - 5, py - 5, 10, 10), "anel", ref))

    def _pintar(self, p: QPainter) -> None:
        e, plano = self.e, self.plano
        _pintar_grade(p, e, plano, plano.ey.marcas, [])
        _pintar_rotulos_y(p, e, plano)
        _pintar_rotulos_x(p, e, plano, self.area)
        p.save()
        p.setClipRect(plano.ret.adjusted(-7, -7, 7, 7))
        neutro = e.cor("neutro")
        neutro.setAlphaF(0.55)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(neutro)
        for x, y in self.outros:
            p.drawEllipse(QPointF(plano.x(x), plano.y(y)), 2.5, 2.5)
        for g in self.grupos:
            p.setPen(QPen(e.fundo, 1))
            p.setBrush(e.cor(g.cor))
            for _, x, y in g.pontos:
                _marca(p, QPointF(plano.x(x), plano.y(y)), g.forma, 8.0)
        reserva = _Reserva()
        for g in self.grupos:
            if g.centro is not None:
                self._pintar_centro(p, g, reserva)
        p.restore()
        _pintar_titulos(p, e, plano, self.area, reserva)

    def _pintar_centro(self, p: QPainter, g: _Grupo, reserva: _Reserva) -> None:
        """Centro do grupo: o mesmo marcador, maior e vazado; com `rotularCentros`, o nome ao lado."""
        e, ret = self.e, self.plano.ret
        centro = QPointF(self.plano.x(g.centro[0]), self.plano.y(g.centro[1]))
        p.setPen(QPen(e.cor(g.cor), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        _marca(p, centro, g.forma, 13.0)
        if self.rotular_centros and g.nome:
            candidatos = [_caixa(e.forte, g.nome, centro.x() + 12, centro.y()),
                          _caixa(e.forte, g.nome, centro.x() - 12, centro.y(), ah=1),
                          _caixa(e.forte, g.nome, centro.x(), centro.y() - 11, ah=0, av=1),
                          _caixa(e.forte, g.nome, centro.x(), centro.y() + 11, ah=0, av=-1)]
            cabem = [c for c in candidatos if ret.contains(c)]
            _escrever(p, e.forte, e.tinta, reserva.primeiro_livre(cabem or candidatos), g.nome, placa=e.placa)

    def _ler(self, alvo: _Alvo) -> str:
        gi, k = alvo.ref
        if gi < 0:
            return NOME_OUTROS
        g = self.grupos[gi]
        return (g.rotulos[k] if k < len(g.rotulos) else "") or g.nome

    def escolher(self, x: float, y: float) -> int:
        return self._mais_perto(x, y, 14.0) if self.plano.contem(x, y) else -1


# ---------------------------------------------------------------------------- fita
@dataclass(frozen=True)
class _Faixa:
    rotulo: str
    eventos: tuple[tuple[float, str, str, Any], ...]      # (hora decimal, tipo, texto, id), em ordem de hora
    intervalos: tuple[tuple[float, float], ...]


def _faixas(dados: dict) -> list[_Faixa]:
    faixas = []
    for bruto in _lista(dados.get("faixas")):
        f = _mapa(bruto)
        eventos = []
        for item in _lista(f.get("eventos")):
            ev = _mapa(item)
            t = _numero(ev.get("t"))
            if t is not None:
                eventos.append((t, _texto(ev.get("tipo")), _texto(ev.get("texto")), ev.get("id")))
        intervalos = []
        for item in _lista(f.get("intervalos")):
            iv = _mapa(item)
            t0, t1 = _numero(iv.get("t0")), _numero(iv.get("t1"))
            if t0 is not None and t1 is not None and t1 > t0:
                intervalos.append((t0, t1))
        faixas.append(_Faixa(_texto(f.get("rotulo")), tuple(sorted(eventos, key=lambda ev: ev[0])), tuple(intervalos)))
    return faixas


class _Fita(_Desenho):
    """Eventos no tempo, um traço por evento: alto para concedido, médio para negado, curto para bloqueio."""

    def __init__(self, dados: dict, area: QRectF, e: _Estilo) -> None:
        super().__init__(dados, area, e)
        self.faixas = _faixas(dados)
        self.tem_dado = any(f.eventos or f.intervalos for f in self.faixas)
        ex = _eixo({"min": 0.0, "max": 24.0, "formato": "hora", **_mapa(dados.get("eixoX"))}, [],
                   alvo=6 if area.width() >= 420 else 4, justo=True)
        n = max(1, len(self.faixas))
        largura_rotulos = min(_largura_rotulos(e, [f.rotulo for f in self.faixas]), area.width() * 0.26)
        baixo = 22 + (16 if ex.rotulo else 0)
        self.altura = min(56.0, max(8.0, (area.height() - 6 - baixo) / n))
        self.largura_rotulos = largura_rotulos
        self.plano = _montar_plano(area, e, ex, _Eixo("", 0.0, 1.0, False, "", (), (), 0), topo=6, direita=12,
                                   esquerda=largura_rotulos + 12 if largura_rotulos else 8.0,
                                   baixo=max(baixo, area.height() - 6 - n * self.altura))
        self.util = max(4.0, self.altura - 12.0)        # altura do traço mais alto
        for fi, f in enumerate(self.faixas):
            chao = self._chao(fi)
            for k, (t, tipo, _, _) in enumerate(f.eventos):
                x = self.plano.x(min(max(t, ex.minimo), ex.maximo))
                topo = chao - self.util * ALTURA_TRACO_FITA.get(tipo, ALTURA_TRACO_FITA["bloqueio"])
                self.alvos.append(_Alvo(x, topo, QRectF(x - 0.5, chao - self.util, 1.0, self.util), "fio", (fi, k)))

    def _chao(self, fi: int) -> float:
        """Linha de base da faixa `fi` (os traços sobem a partir dela)."""
        return self.plano.ret.top() + (fi + 1) * self.altura - 6

    def _pintar(self, p: QPainter) -> None:
        e, plano, ret = self.e, self.plano, self.plano.ret
        ex = plano.ex
        for fi, f in enumerate(self.faixas):
            chao = self._chao(fi)
            p.setPen(QPen(e.grade, 1))
            p.drawLine(QPointF(ret.left(), _fio(chao)), QPointF(ret.right(), _fio(chao)))
            if f.rotulo:
                texto = _cortar(e.rotulo, f.rotulo, self.largura_rotulos)
                _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, texto, ret.left() - 12, chao - self.util / 2, ah=1), texto)
            for t0, t1 in f.intervalos:
                a, b = (plano.x(min(max(t, ex.minimo), ex.maximo)) for t in (t0, t1))
                if b > a:
                    _hachura(p, QRectF(a, chao - self.util, b - a, self.util), e.cor("bloqueio"))
            p.setPen(Qt.PenStyle.NoPen)
            for tipo in sorted({ev[1] for ev in f.eventos}, key=lambda nome: -ALTURA_TRACO_FITA.get(nome, 0.0)):
                p.setBrush(e.cor(tipo if tipo in ALTURA_TRACO_FITA else "neutro"))      # os mais altos primeiro, por baixo
                for alvo in (a for a in self.alvos if a.ref[0] == fi and f.eventos[a.ref[1]][1] == tipo):
                    p.drawRoundedRect(QRectF(round(alvo.px) - 1.0, alvo.py, 2.0, chao - alvo.py), 1, 1)
        fim = self._chao(len(self.faixas) - 1) if self.faixas else ret.top()
        caixas = [_encaixar(_caixa(e.rotulo, t, plano.x(v), fim + 9, ah=0, av=-1), self.area) for v, t in zip(ex.marcas, ex.textos)]
        anterior: QRectF | None = None
        for v, texto, caixa in zip(ex.marcas, ex.textos, caixas):
            x = _fio(plano.x(v))
            p.setPen(QPen(e.grade, 1))
            p.drawLine(QPointF(x, fim), QPointF(x, fim + 4))
            if anterior is None or not caixa.adjusted(-5, 0, 5, 0).intersects(anterior):
                _escrever(p, e.rotulo, e.tinta3, caixa, texto)
                anterior = caixa
        if ex.rotulo:
            texto = _cortar(e.rotulo, ex.rotulo, ret.width())
            _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, texto, ret.right(), fim + 9 + e.rotulo.m.height() + 3, ah=1, av=-1), texto)

    def _ler(self, alvo: _Alvo) -> str:
        t, tipo, texto, _ = self.faixas[alvo.ref[0]].eventos[alvo.ref[1]]
        return texto or " · ".join(parte for parte in (_hora(t), NOMES_FITA.get(tipo, "")) if parte)

    def _extra(self, alvo: _Alvo) -> dict:
        identificador = self.faixas[alvo.ref[0]].eventos[alvo.ref[1]][3]
        return {"id": identificador} if isinstance(identificador, int) and not isinstance(identificador, bool) else {}

    def escolher(self, x: float, y: float) -> int:
        ret = self.plano.ret
        fi = int((y - ret.top()) // self.altura)
        if not (ret.left() - 6 <= x <= ret.right() + 6 and 0 <= fi < len(self.faixas)):
            return -1
        candidatos = [i for i, alvo in enumerate(self.alvos) if alvo.ref[0] == fi and abs(alvo.px - x) <= 10]
        return min(candidatos, key=lambda i: abs(self.alvos[i].px - x), default=-1)


# ---------------------------------------------------------------------------- legenda e cabeçalho da figura
def _nome_cor(v: Any, padrao: str) -> str:
    if isinstance(v, str) and v:
        return v
    return f"serie{v % 4}" if isinstance(v, int) and not isinstance(v, bool) else padrao


def itens_legenda(tipo: str, dados: dict) -> list[dict]:
    """Legenda que o próprio dado pede: [{"nome", "cor" (pelo nome), "forma"?, "tracejada"?, "hachura"?}].
    Com "tracejada" a amostra é um traço; com "forma", o marcador; sem as duas, um quadrado. Uma série
    só dispensa legenda (o título nomeia) e o calor tem a barra de escala."""
    dados = _mapa(dados)
    itens: list[dict] = []
    if tipo in ("xy", "histograma", "barras"):
        for i, s in enumerate(map(_mapa, _lista(dados.get("series")))):
            item = {"nome": _texto(s.get("nome")), "cor": _nome_cor(s.get("cor"), f"serie{i % 4}")}
            if tipo == "xy" and s.get("estilo") == "pontos":
                item["forma"] = 0
            elif tipo == "xy":
                item["tracejada"] = bool(s.get("tracejada"))
            itens.append(item)
    elif tipo == "dispersao":
        grupos, outros = _grupos(dados)
        itens = [{"nome": g.nome, "cor": _nome_cor(g.cor, "neutro"), "forma": g.forma} for g in grupos]
        if outros:
            itens.append({"nome": NOME_OUTROS, "cor": "neutro", "forma": 0})
    elif tipo == "fita":
        faixas = _faixas(dados)
        presentes = {ev[1] for f in faixas for ev in f.eventos}
        itens = [{"nome": NOMES_FITA[nome], "cor": nome} for nome in NOMES_FITA if nome in presentes]
        if any(f.intervalos for f in faixas):
            itens.append({"nome": NOME_INTERVALO, "cor": "bloqueio", "hachura": True})
        return itens
    itens = [item for item in itens if item["nome"]]
    return itens if len(itens) >= 2 else []


def _pintar_amostra(p: QPainter, e: _Estilo, item: dict, x: float, meio: float) -> None:
    """Amostra de 14 px da legenda: traço, marcador, hachura ou quadrado."""
    cor = e.cor(item.get("cor"))
    if "tracejada" in item:
        caneta = QPen(cor, 2)
        caneta.setCapStyle(Qt.PenCapStyle.FlatCap)
        if item["tracejada"]:
            caneta.setDashPattern([2.5, 2.0])
        p.setPen(caneta)
        p.drawLine(QPointF(x, meio), QPointF(x + 14, meio))
    elif item.get("hachura"):
        _hachura(p, QRectF(x + 2, meio - 5, 10, 10), cor)
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(cor)
        if "forma" in item:
            _marca(p, QPointF(x + 7, meio), item["forma"], 8.0)
        else:
            p.drawRoundedRect(QRectF(x + 3, meio - 4, 8, 8), 2, 2)


def _pintar_linha_de_itens(p: QPainter | None, limite: QRectF, y: float, altura: float, larguras: Sequence[float],
                           pintar_item) -> float:
    """Dispõe itens em linha, quebrando quando acaba a largura; devolve o y do fim. Sem pintor, só mede."""
    x = limite.left()
    for i, largura in enumerate(larguras):
        if x > limite.left() and x + largura > limite.right():
            x, y = limite.left(), y + altura + 6
        if p is not None:
            pintar_item(i, x, y)
        x += largura + 8
    return y + altura


def _cabecalho(p: QPainter | None, e: _Estilo, area: QRectF, tipo: str, dados: dict) -> QRectF:
    """Cabeçalho da figura exportada: título, N, subtítulo, selos e legenda. Devolve a área que sobra
    para o gráfico. Sem pintor (`p` None) só mede, para a figura ter a altura certa."""
    dentro = area.adjusted(MARGEM_FIGURA, MARGEM_FIGURA, -MARGEM_FIGURA, -MARGEM_FIGURA)
    titulo, subtitulo, n = (_texto(dados.get(chave)) for chave in ("titulo", "subtitulo", "n"))
    selos = [s for s in map(_texto, _lista(dados.get("selos"))) if s]
    legenda = itens_legenda(tipo, dados)
    y = dentro.top()
    if titulo or n:
        n = _cortar(e.rotulo, n, dentro.width() * 0.55)
        largura_n = e.rotulo.m.horizontalAdvance(n) + 16 if n else 0.0
        if p is not None:
            texto = _cortar(e.titulo, titulo, dentro.width() - largura_n)
            _escrever(p, e.titulo, e.tinta, _caixa(e.titulo, texto, dentro.left(), y, av=-1), texto)
            if n:
                base = y + e.titulo.m.ascent() - e.rotulo.m.ascent()          # na mesma linha de base do título
                _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, n, dentro.right(), base, ah=1, av=-1), n)
        y += e.titulo.m.height() + 2
    if subtitulo:
        if p is not None:
            texto = _cortar(e.corpo, subtitulo, dentro.width())
            _escrever(p, e.corpo, e.tinta3, _caixa(e.corpo, texto, dentro.left(), y, av=-1), texto)
        y += e.corpo.m.height()
    if selos:
        cor = e.cor("aviso")
        fundo, borda = QColor(cor), QColor(cor)
        fundo.setAlphaF(0.13)
        borda.setAlphaF(0.45)

        def pintar_selo(i: int, x: float, topo: float) -> None:
            ret = QRectF(x, topo, e.forte.m.horizontalAdvance(selos[i]) + 16, 20)
            p.setPen(QPen(borda, 1))
            p.setBrush(fundo)
            p.drawRoundedRect(ret.adjusted(0.5, 0.5, -0.5, -0.5), 9.5, 9.5)
            _escrever(p, e.forte, cor, _caixa(e.forte, selos[i], ret.left() + 8, ret.center().y()), selos[i])

        y = _pintar_linha_de_itens(p, dentro, y + 8, 20, [e.forte.m.horizontalAdvance(s) + 16 for s in selos], pintar_selo)
    if legenda:
        nomes = [_cortar(e.rotulo, item["nome"], dentro.width() - 30) for item in legenda]

        def pintar_item(i: int, x: float, topo: float) -> None:
            _pintar_amostra(p, e, legenda[i], x, topo + 7)
            _escrever(p, e.rotulo, e.tinta2, _caixa(e.rotulo, nomes[i], x + 19, topo + 7), nomes[i])

        y = _pintar_linha_de_itens(p, dentro, y + 10, 14, [19 + e.rotulo.m.horizontalAdvance(nome) + 6 for nome in nomes], pintar_item)
    if y > dentro.top():
        y += 14
    return QRectF(dentro.left(), y, dentro.width(), max(1.0, dentro.bottom() - y))


# ---------------------------------------------------------------------------- funções públicas
_DESENHOS: dict[str, type[_Desenho]] = {"xy": _XY, "histograma": _Histograma, "barras": _Barras, "calor": _Calor,
                                        "dispersao": _Dispersao, "fita": _Fita}
_AREA_NOMINAL = QRectF(0, 0, 640, 360)


def _conhecido(tipo: Any) -> bool:
    return isinstance(tipo, str) and tipo in _DESENHOS


def _montar(tipo: str, dados: Any, area: QRectF, e: _Estilo) -> _Desenho | None:
    """O desenho pronto para pintar e para ler, ou None quando não há o que desenhar (dados vazios,
    tipo desconhecido ou área pequena demais)."""
    if not _conhecido(tipo) or not isinstance(dados, dict) or not dados or area.width() < 24 or area.height() < 24:
        return None
    return _DESENHOS[tipo](dados, area, e)


def desenhar(p: QPainter, area: QRectF, tipo: str, dados: dict, paleta: dict | None = None,
             cabecalho: bool = False) -> None:
    """Pinta o gráfico `tipo` em `area`. Sem paleta, usa a da tela (`tema_v2.PALETA_TELA`). Com
    `cabecalho`, desenha antes o título, o subtítulo, o N, os selos e a legenda (figura exportada).
    Dados vazios ou tipo desconhecido: só o fundo."""
    e = _Estilo(paleta)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    p.fillRect(area, e.fundo)
    corpo = area
    if cabecalho and isinstance(dados, dict) and _conhecido(tipo):
        corpo = _cabecalho(p, e, area, tipo, dados)
    desenho = _montar(tipo, dados, corpo, e)
    if desenho is not None:
        desenho.pintar(p)
    p.restore()


def valor_em(tipo: str, dados: dict, area: QRectF, x: float, y: float) -> dict:
    """Leitura do dado sob o ponto (x, y): {"texto", "px", "py", "indice"} mais o realce que ele pede
    ("forma": "fio", "anel" ou "caixa", e o retângulo "rx", "ry", "rl", "ra"). Fora da área de dados: {}."""
    desenho = _montar(tipo, dados, area, _Estilo(None))
    if desenho is None or not desenho.tem_dado:
        return {}
    return desenho.leitura(desenho.escolher(float(x), float(y)))


def valor_indice(tipo: str, dados: dict, area: QRectF, indice: int) -> dict:
    """Leitura do dado de número `indice` (para percorrer com o teclado), no formato de `valor_em`."""
    desenho = _montar(tipo, dados, area, _Estilo(None))
    if desenho is None or not desenho.tem_dado:
        return {}
    return desenho.leitura(int(indice))


def total_indices(tipo: str, dados: dict) -> int:
    """Quantos dados a leitura alcança (os índices válidos de `valor_indice` vão de 0 a esse total menos 1)."""
    desenho = _montar(tipo, dados, _AREA_NOMINAL, _Estilo(None))
    return len(desenho.alvos) if desenho is not None and desenho.tem_dado else 0


def tamanho_figura(tipo: str, dados: dict) -> tuple[int, int]:
    """Largura e altura lógicas da figura exportada (o PNG sai com o dobro). A altura segue o conteúdo:
    o cabeçalho ocupa o que precisa e matriz, fita e barras deitadas crescem com as linhas."""
    dados = _mapa(dados)
    e = _Estilo(tema_v2.PALETA_PAPEL)
    topo = _cabecalho(None, e, QRectF(0, 0, LARGURA_FIGURA, 4000), tipo, dados).top() if _conhecido(tipo) else MARGEM_FIGURA
    corpo = 300.0
    if tipo == "calor":
        linhas = max(len(_lista(dados.get("linhas"))), len(_lista(dados.get("valores"))))
        corpo = min(460.0, max(200.0, linhas * 40.0 + 70.0))
    elif tipo == "fita":
        corpo = min(420.0, max(96.0, len(_lista(dados.get("faixas"))) * 48.0 + 34.0))
    elif tipo == "barras" and dados.get("orientacao") == "h":
        categorias, series = _series_barras(dados)
        lado_a_lado = 1 if dados.get("empilhado") else max(1, len(series))
        corpo = min(460.0, max(96.0, len(categorias) * (14.0 + 16.0 * lado_a_lado) + 44.0))
    return LARGURA_FIGURA, math.ceil(topo + corpo + MARGEM_FIGURA)


def renderizar(tipo: str, dados: dict, largura: int = 1200, altura: int = 600, escala: float = 2.0,
               papel: bool = False, *, cabecalho: bool = True) -> QImage:
    """A figura numa imagem de `largura * escala` por `altura * escala` pixels, com o cabeçalho.
    `papel` troca a paleta da tela pela de fundo branco."""
    escala = escala if isinstance(escala, (int, float)) and escala > 0 else 1.0
    largura, altura = max(1, int(largura)), max(1, int(altura))
    imagem = QImage(max(1, round(largura * escala)), max(1, round(altura * escala)), QImage.Format.Format_ARGB32_Premultiplied)
    paleta = tema_v2.PALETA_PAPEL if papel else tema_v2.PALETA_TELA
    imagem.fill(QColor(paleta["fundo"]))
    p = QPainter(imagem)
    p.scale(escala, escala)
    desenhar(p, QRectF(0, 0, largura, altura), tipo, dados, paleta, cabecalho=cabecalho)
    p.end()
    return imagem


# ---------------------------------------------------------------------------- planilha
def _csv_xy(dados: dict) -> list[list[str]]:
    series = _series_xy(dados)
    com_faixa, com_rotulo = any(s.faixa for s in series), any(s.rotulos for s in series)
    nome_x = _texto(_mapa(dados.get("eixoX")).get("rotulo")) or "x"
    nome_y = _texto(_mapa(dados.get("eixoY")).get("rotulo")) or "y"
    linhas = [["serie", nome_x, nome_y] + (["minimo", "maximo"] if com_faixa else []) + (["rotulo"] if com_rotulo else [])]
    for s in series:
        faixa = {x: (baixo, alto) for x, baixo, alto in s.faixa}
        for k, x, y in s.pontos:
            linha = [s.nome, _csv_numero(x), _csv_numero(y)]
            if com_faixa:
                linha += [_csv_numero(v) for v in faixa.pop(x, (None, None))]
            if com_rotulo:
                linha.append(s.rotulos[k] if k < len(s.rotulos) else "")
            linhas.append(linha)
        for x, (baixo, alto) in faixa.items():          # faixa em um X sem ponto
            linhas.append([s.nome, _csv_numero(x), "", _csv_numero(baixo), _csv_numero(alto)] + ([""] if com_rotulo else []))
    return linhas


def _csv_histograma(dados: dict) -> list[list[str]]:
    bordas, series = _series_hist(dados)
    linhas = [["de", "ate"] + [s.nome or f"serie{i + 1}" for i, s in enumerate(series)]]
    for i in range(len(bordas) - 1):
        linhas.append([_csv_numero(bordas[i]), _csv_numero(bordas[i + 1])] + [_csv_numero(s.contagens[i]) for s in series])
    return linhas


def _csv_barras(dados: dict) -> list[list[str]]:
    categorias, series = _series_barras(dados)
    linhas = [["categoria"] + [s.nome or f"serie{i + 1}" for i, s in enumerate(series)]]
    for c, categoria in enumerate(categorias):
        linhas.append([categoria] + [_csv_numero(s.valores[c]) for s in series])
    return linhas


def _csv_calor(dados: dict) -> list[list[str]]:
    colunas = [_texto(t) for t in _lista(dados.get("colunas"))]
    rotulos = [_texto(t) for t in _lista(dados.get("linhas"))]
    linhas = [[""] + colunas]
    for i, valores in enumerate(_lista(dados.get("valores"))):
        linhas.append([rotulos[i] if i < len(rotulos) else ""] + [_csv_numero(_numero(v)) for v in _lista(valores)])
    return linhas


def _csv_dispersao(dados: dict) -> list[list[str]]:
    grupos, outros = _grupos(dados)
    com_rotulo = any(g.rotulos for g in grupos)
    linhas = [["grupo", "x", "y"] + (["rotulo"] if com_rotulo else [])]
    for g in grupos:
        for k, x, y in g.pontos:
            linhas.append([g.nome, _csv_numero(x), _csv_numero(y)] + ([g.rotulos[k] if k < len(g.rotulos) else ""] if com_rotulo else []))
    for x, y in outros:
        linhas.append([NOME_OUTROS, _csv_numero(x), _csv_numero(y)] + ([""] if com_rotulo else []))
    return linhas


def _hora_csv(t: float) -> str:
    segundos = max(0, round(t * 3600))
    return f"{segundos // 3600:02d}:{segundos // 60 % 60:02d}:{segundos % 60:02d}"


def _csv_fita(dados: dict) -> list[list[str]]:
    linhas = [["faixa", "inicio", "fim", "tipo", "texto"]]
    for f in _faixas(dados):
        for t, tipo, texto, _ in f.eventos:
            linhas.append([f.rotulo, _hora_csv(t), "", NOMES_FITA.get(tipo, tipo), texto])
        for t0, t1 in f.intervalos:
            linhas.append([f.rotulo, _hora_csv(t0), _hora_csv(t1), NOME_INTERVALO, ""])
    return linhas


_LINHAS_CSV = {"xy": _csv_xy, "histograma": _csv_histograma, "barras": _csv_barras, "calor": _csv_calor,
               "dispersao": _csv_dispersao, "fita": _csv_fita}


def dados_para_csv(tipo: str, dados: dict) -> str:
    """Os dados da figura como planilha em texto: ";" entre colunas e vírgula decimal. No topo, uma
    linha "# ..." para o título, o subtítulo, o N e cada selo."""
    dados = _mapa(dados)
    saida = io.StringIO()
    notas = [_texto(dados.get(chave)) for chave in ("titulo", "subtitulo", "n")] + [_texto(s) for s in _lista(dados.get("selos"))]
    for nota in notas:
        if nota:
            saida.write("# " + " ".join(nota.split()) + "\n")
    if _conhecido(tipo):
        csv.writer(saida, delimiter=";", lineterminator="\n").writerows(_LINHAS_CSV[tipo](dados))
    return saida.getvalue()


# ---------------------------------------------------------------------------- trava de privacidade (regra T6)
TAMANHO_VETOR = 128


def _sequencia(v: Any) -> list | None:
    """Lista, tupla ou matriz do NumPy como lista; qualquer outra coisa não é sequência."""
    if isinstance(v, (list, tuple)):
        return list(v)
    if hasattr(v, "tolist") and hasattr(v, "shape") and getattr(v, "ndim", 0) >= 1:
        return v.tolist()
    return None


def _e_numero(v: Any) -> bool:
    return isinstance(v, Real) and not isinstance(v, bool)


def _coluna_de_vetor(coluna: Sequence[float]) -> bool:
    """Uma coluna tem cara de descritor facial quando mistura sinais e está normalizada: norma L2
    perto de 1 (vetor unitário) ou maior módulo perto de 1 (vetor dividido pelo maior valor)."""
    if not (any(v > 0 for v in coluna) and any(v < 0 for v in coluna)):
        return False
    norma = math.sqrt(sum(float(v) * float(v) for v in coluna))
    maior = max(abs(float(v)) for v in coluna)
    return 0.9 <= norma <= 1.1 or 0.99 <= maior <= 1.01


def conferir_sem_vetor(dados: Any) -> None:
    """Levanta `ValueError` se houver um vetor biométrico de 128 dimensões em qualquer profundidade de
    dicionário, lista ou tupla: (a) uma sequência plana de exatamente 128 números; ou (b) exatamente 128
    linhas de mesmo tamanho (pares [i, v], pontos [x, y]) com alguma coluna de sinais misturados e
    normalizada. Por isso nenhum gráfico da v2 usa 128 faixas nem 128 pontos."""
    pilha = [dados]
    while pilha:
        atual = pilha.pop()
        if isinstance(atual, dict):
            pilha.extend(atual.values())
            continue
        itens = _sequencia(atual)
        if itens is None:
            continue
        if len(itens) == TAMANHO_VETOR:
            if all(_e_numero(v) for v in itens):
                raise ValueError("Sequência de 128 números: parece um vetor biométrico e não pode sair daqui.")
            linhas = [_sequencia(v) for v in itens]
            if all(linha is not None for linha in linhas) and len({len(linha) for linha in linhas}) == 1:
                for coluna in zip(*linhas):
                    if all(_e_numero(v) for v in coluna) and _coluna_de_vetor(coluna):
                        raise ValueError("128 linhas com uma coluna normalizada: parece um vetor biométrico e não pode sair daqui.")
        pilha.extend(itens)


# ---------------------------------------------------------------------------- exportação
def exportar(tipo: str, dados: dict, destino_sem_extensao: Path, carimbo: str = "") -> list[Path]:
    """Grava a figura em PNG (2x) e SVG, na paleta papel e com o cabeçalho, e os dados em CSV. O
    `carimbo` (ex.: "Base de demonstração") entra como mais um selo nos três arquivos. Confere antes
    que nenhum vetor biométrico está nos dados (`ValueError`, e nada é gravado). Devolve os caminhos."""
    conferir_sem_vetor(dados)
    dados = dict(_mapa(dados))
    selos = [s for s in map(_texto, _lista(dados.get("selos"))) if s]
    if carimbo and carimbo not in selos:
        selos.append(carimbo)
    dados["selos"] = selos
    destino = Path(destino_sem_extensao)
    destino.parent.mkdir(parents=True, exist_ok=True)
    png, svg, planilha = (destino.with_name(destino.name + extensao) for extensao in (".png", ".svg", ".csv"))
    largura, altura = tamanho_figura(tipo, dados)
    if not renderizar(tipo, dados, largura, altura, 2.0, papel=True).save(str(png), "PNG"):
        raise OSError(f"Não foi possível gravar {png.name}")
    gerador = QSvgGenerator(QSvgGenerator.SvgVersion.Svg11)
    gerador.setFileName(str(svg))
    gerador.setResolution(96)                      # 1 px lógico = 1/96 de polegada: 760 px dão 20 cm, cabe numa página A4
    gerador.setSize(QSize(largura, altura))
    gerador.setViewBox(QRect(0, 0, largura, altura))
    gerador.setTitle(_texto(dados.get("titulo")))
    gerador.setDescription(" · ".join(parte for parte in [_texto(dados.get("resumo"))] + selos if parte))
    p = QPainter()
    if not p.begin(gerador):
        raise OSError(f"Não foi possível gravar {svg.name}")
    desenhar(p, QRectF(0, 0, largura, altura), tipo, dados, {**tema_v2.PALETA_PAPEL, "familia": FAMILIA_SVG}, cabecalho=True)
    p.end()
    planilha.write_text(dados_para_csv(tipo, dados), encoding="utf-8-sig")
    return [png, svg, planilha]


# ---------------------------------------------------------------------------- item do QML
class Grafico(QQuickPaintedItem):
    """Gráfico nativo do QML (`import Cofre.Nativo`): pinta `dados` com `desenhar`, na paleta da tela
    ou, com `papel`, na de fundo branco. A leitura sob o cursor sai de `valorEm` e, pelo teclado, de
    `valorIndice`; o gráfico não é repintado quando o mouse se move."""

    tipoMudou = Signal()
    dadosMudou = Signal()
    papelMudou = Signal()
    legendaMudou = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tipo = ""
        self._dados: dict = {}
        self._papel = False
        self._leitor: tuple[tuple[float, float], _Desenho | None] | None = None     # geometria da última leitura
        self.setAntialiasing(True)
        self.setOpaquePainting(False)

    # ------------------------------------------------------------------ propriedades
    def _mudou(self) -> None:
        self._leitor = None
        self.legendaMudou.emit()
        self.update()

    def _get_tipo(self) -> str:
        return self._tipo

    def _set_tipo(self, v: str) -> None:
        if v != self._tipo:
            self._tipo = str(v)
            self.tipoMudou.emit()
            self._mudou()

    def _get_dados(self) -> dict:
        return self._dados

    def _set_dados(self, v) -> None:
        v = v if isinstance(v, dict) else {}
        if v != self._dados:
            self._dados = v
            self.dadosMudou.emit()
            self._mudou()

    def _get_papel(self) -> bool:
        return self._papel

    def _set_papel(self, v: bool) -> None:
        if bool(v) != self._papel:
            self._papel = bool(v)
            self.papelMudou.emit()
            self._mudou()

    def _paleta(self) -> dict:
        return tema_v2.PALETA_PAPEL if self._papel else tema_v2.PALETA_TELA

    def _get_legenda(self) -> list:
        e = _Estilo(self._paleta())
        return [{**item, "cor": e.cor(item["cor"]).name(QColor.NameFormat.HexArgb)}
                for item in itens_legenda(self._tipo, self._dados)]

    tipo = Property(str, _get_tipo, _set_tipo, notify=tipoMudou)
    dados = Property("QVariantMap", _get_dados, _set_dados, notify=dadosMudou)
    papel = Property(bool, _get_papel, _set_papel, notify=papelMudou)
    legenda = Property("QVariantList", _get_legenda, notify=legendaMudou)

    # ------------------------------------------------------------------ desenho e leitura
    def paint(self, p: QPainter) -> None:
        if self.width() <= 1 or self.height() <= 1:
            return
        desenhar(p, QRectF(0, 0, self.width(), self.height()), self._tipo, self._dados, self._paleta())

    def _desenho(self) -> _Desenho | None:
        """Geometria do gráfico no tamanho atual do item, refeita só quando algo muda."""
        tamanho = (self.width(), self.height())
        if self._leitor is None or self._leitor[0] != tamanho:
            desenho = _montar(self._tipo, self._dados, QRectF(0, 0, *tamanho), _Estilo(None))
            self._leitor = (tamanho, desenho if desenho is not None and desenho.tem_dado else None)
        return self._leitor[1]

    @Slot(float, float, result="QVariantMap")
    def valorEm(self, x: float, y: float) -> dict:
        desenho = self._desenho()
        return desenho.leitura(desenho.escolher(x, y)) if desenho is not None else {}

    @Slot(int, result="QVariantMap")
    def valorIndice(self, indice: int) -> dict:
        desenho = self._desenho()
        return desenho.leitura(indice) if desenho is not None else {}

    @Slot(result=int)
    def totalIndices(self) -> int:
        desenho = self._desenho()
        return len(desenho.alvos) if desenho is not None else 0
