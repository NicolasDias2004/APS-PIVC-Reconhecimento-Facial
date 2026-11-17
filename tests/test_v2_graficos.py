"""Gráficos, tokens e kit visual da versão 2: os seis tipos de `cofre.qt.graficos` (desenho, leitura sob
o cursor, exportação e a trava que impede um vetor biométrico de sair), o espelho de cores `tema_v2`
e os componentes novos de `Ui/` carregados sem tela.

Todo caso pede a fixture `qapp`: desenhar texto com QPainter precisa de uma QGuiApplication viva."""

from __future__ import annotations

import copy
import random
import re
import time

import numpy as np
import pytest

from tests import apoio_v2  # define a plataforma offscreen antes de qualquer janela

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QPoint, QRectF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtQml import QJSValue, QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from cofre.qt import graficos, tema_v2  # noqa: E402
from cofre.qt.app import DIR_QML  # noqa: E402

DIR_UI = DIR_QML / "Cofre" / "Ui"
AREA = QRectF(0, 0, 480, 300)
KIT = ("Anel", "AnelPassos", "BarraSimilaridade", "Tecla", "Abas", "Aviso", "Deslizante", "Metrica", "SeloConsultivo",
       "SeloDemo", "EstadoBloco", "LegendaGrafico", "CartaoGrafico", "Tabela", "ParRotuloValor")
ICONES_NOVOS = ("painel", "laboratorio", "resultados", "porta", "telaCheia", "congelar", "selo", "incidente", "privado",
                "alvo", "matriz", "comando", "roteiro", "esquerda", "cima", "copiar")
_AVISOS_IGNORADOS = ("Sans Serif", "propagateSizeHints")     # os mesmos de tests/apoio_qt.py: não vêm do nosso QML
# O tipo de evento (e nome de cor) do acesso liberado só é escrito por extenso em graficos.py e tema_v2.py (regra T5).
LIBERADO = next(iter(graficos.NOMES_FITA))


# ---------------------------------------------------------------------------- dados de exemplo
def _vetor_unitario(semente: int = 5) -> np.ndarray:
    """128 números com sinais misturados e norma 1: a forma de um descritor facial (não é de ninguém)."""
    v = np.random.default_rng(semente).normal(size=128)
    return v / np.linalg.norm(v)


def _um_ponto(tipo: str) -> dict:
    return {
        "xy": {"series": [{"nome": "A", "cor": "serie0", "pontos": [[1.0, 0.5]]}]},
        "histograma": {"bordas": [0.0, 1.0], "series": [{"nome": "A", "cor": "serie0", "contagens": [3]}]},
        "barras": {"categorias": ["Detecção"], "series": [{"nome": "A", "cor": "serie0", "valores": [11.4]}]},
        "calor": {"linhas": ["Pessoa A"], "colunas": ["Pessoa B"], "valores": [[0.12]]},
        "dispersao": {"grupos": [{"nome": "Pessoa A", "cor": 0, "forma": 0, "pontos": [[0.3, -0.2]]}]},
        "fita": {"faixas": [{"rotulo": "hoje", "eventos": [{"t": 20.68, "tipo": "negado", "id": 7, "texto": "20:41 · Não cadastrado"}]}]},
    }[tipo]


def _massa(tipo: str) -> dict:
    rng = random.Random(3)
    comuns = {"titulo": "Figura de teste", "subtitulo": "Dados sintéticos", "n": "N = 60", "selos": ["Sintético"],
              "resumo": "Uma frase de resumo."}
    if tipo == "xy":
        niveis = list(range(12))
        return {**comuns, "eixoX": {"rotulo": "nível", "formato": "int"}, "eixoY": {"rotulo": "similaridade", "min": 0, "max": 1, "formato": "0.00"},
                "series": [{"nome": "Desfoque", "cor": "serie0", "pontos": [[n, 0.8 - 0.06 * n] for n in niveis],
                            "faixa": [[n, 0.75 - 0.06 * n, 0.85 - 0.06 * n] for n in niveis]},
                           {"nome": "Ruído", "cor": "serie1", "pontos": [[n, 0.8 - 0.03 * n] for n in niveis], "tracejada": True},
                           {"nome": "Pouca luz", "cor": "serie2", "estilo": "degrau", "pontos": [[n, 0.7 - 0.05 * n if n != 4 else None] for n in niveis]}],
                "marcadoresH": [{"y": 0.363, "rotulo": "limiar em vigor 0,363", "estilo": "vigor"}],
                "marcadoresV": [{"x": 5, "rotulo": "estudo", "estilo": "estudo"}],
                "anotacoes": [{"x": 7, "y": 0.38, "texto": "quebra em 7"}]}
    if tipo == "histograma":
        bordas = [round(-0.2 + i * 1.2 / 64, 5) for i in range(65)]
        return {**comuns, "eixoX": {"rotulo": "similaridade", "min": -0.2, "max": 1.0, "formato": "0.00"}, "bordas": bordas,
                "series": [{"nome": "Genuíno", "cor": "serie0", "contagens": [max(0, 30 - abs(i - 48) * 3) for i in range(64)], "sentido": 1},
                           {"nome": "Impostor", "cor": "neutro", "contagens": [max(0, 90 - abs(i - 14) * 9) for i in range(64)], "sentido": -1}],
                "marcadoresV": [{"x": 0.363, "rotulo": "limiar em vigor 0,363", "estilo": "vigor"},
                                {"x": 0.42, "rotulo": "estudo 0,420", "estilo": "estudo"}], "truncarEm": 60}
    if tipo == "barras":
        return {**comuns, "eixoY": {"rotulo": "ms", "formato": "0.0"}, "rotulosValor": True,
                "categorias": ["Aquisição", "Pré-processo", "Detecção", "Alinhamento", "Representação", "Decisão"],
                "series": [{"nome": "Mediana", "cor": "serie0", "valores": [0.8, 2.6, 11.4, 1.2, 19.7, 0.3]},
                           {"nome": "p95", "cor": "neutro", "valores": [1.1, 3.4, 14.9, None, 24.8, 0.5]}],
                "marcadoresH": [{"y": 16.0, "rotulo": "meta", "estilo": "nota"}]}
    if tipo == "calor":
        nomes = [f"Pessoa {letra}" for letra in "ABCDEF"]
        valores = [[None if i == j else round(rng.uniform(0.0, 0.5), 2) for j in range(6)] for i in range(6)]
        return {**comuns, "linhas": nomes, "colunas": nomes, "valores": valores, "min": 0.0, "max": 0.6, "mostrarValores": True,
                "formato": "0.00", "destaques": [[1, 4]], "marcaEscala": 0.363}
    if tipo == "dispersao":
        grupos = []
        for gi in range(5):
            cx, cy = rng.uniform(-2, 2), rng.uniform(-2, 2)
            pontos = [[round(rng.gauss(cx, 0.3), 3), round(rng.gauss(cy, 0.3), 3)] for _ in range(8)]
            grupos.append({"nome": f"Pessoa {'ABCDE'[gi]}", "cor": gi % 4, "forma": gi // 4, "pontos": pontos, "centro": [cx, cy],
                           "rotulos": [f"Pessoa {'ABCDE'[gi]} · amostra {k + 1}" for k in range(8)]})
        return {**comuns, "grupos": grupos, "rotularCentros": True, "outros": [[rng.uniform(-3, 3), rng.uniform(-3, 3)] for _ in range(6)]}
    eventos = [{"t": round(rng.uniform(7, 22), 3), "tipo": rng.choice([LIBERADO, LIBERADO, "negado"]), "id": k, "texto": f"evento {k}"}
               for k in range(30)]
    eventos.append({"t": 20.7, "tipo": "bloqueio", "id": 99, "texto": "20:42 · Bloqueio"})
    return {**comuns, "faixas": [{"rotulo": "seg 09/11", "eventos": eventos[:15], "intervalos": []},
                                 {"rotulo": "ter 10/11", "eventos": eventos[15:], "intervalos": [{"t0": 20.7, "t1": 21.3}]}]}


def _conferir_desenho(tipo: str) -> None:
    """Dados vazios, com um ponto e com massa: nada levanta exceção e, com massa, a figura tem muitas cores."""
    for dados in ({}, {"vazio": "Sem decisões no período"}, _um_ponto(tipo), _massa(tipo)):
        imagem = QImage(480, 300, QImage.Format.Format_ARGB32_Premultiplied)
        imagem.fill(QColor("#000000"))
        p = QPainter(imagem)
        graficos.desenhar(p, AREA, tipo, dados)
        p.end()
        assert imagem.pixelColor(0, 0) == QColor(tema_v2.PALETA_TELA["fundo"])      # o fundo é pintado sempre
    assert apoio_v2.cores_distintas(imagem) > 12
    for papel in (False, True):
        figura = graficos.renderizar(tipo, _massa(tipo), 600, 400, 1.0, papel=papel)
        assert (figura.width(), figura.height()) == (600, 400)
        assert apoio_v2.cores_distintas(figura) > 12
    assert graficos.renderizar(tipo, _massa(tipo), 600, 400, 1.0, papel=True).pixelColor(2, 2) == QColor("#ffffff")
    vazia = graficos.renderizar(tipo, {}, 300, 200, 1.0, cabecalho=False)
    assert apoio_v2.cores_distintas(vazia, passo=4) == 1                           # dados vazios: só o fundo
    assert graficos.total_indices(tipo, _um_ponto(tipo)) == 1
    assert graficos.valor_indice(tipo, _um_ponto(tipo), AREA, 0)["indice"] == 0
    assert graficos.valor_indice(tipo, _um_ponto(tipo), AREA, 1) == {}
    assert graficos.valor_em(tipo, {}, AREA, 100, 100) == {}


# ---------------------------------------------------------------------------- desenho dos seis tipos
def test_xy_desenha(qapp):
    _conferir_desenho("xy")


def test_histograma_desenha(qapp):
    _conferir_desenho("histograma")


def test_barras_desenha(qapp):
    _conferir_desenho("barras")
    deitada = {"orientacao": "h", "empilhado": True, "rotulosValor": True, "categorias": [""],
               "series": [{"nome": "Concedido", "cor": LIBERADO, "valores": [121]}, {"nome": "Negado", "cor": "negado", "valores": [56]},
                          {"nome": "Bloqueio", "cor": "bloqueio", "valores": [5]}]}
    assert apoio_v2.cores_distintas(graficos.renderizar("barras", deitada, 600, 120, 1.0, cabecalho=False)) > 6
    leitura = graficos.valor_indice("barras", deitada, QRectF(0, 0, 600, 120), 1)
    assert leitura["texto"] == "Negado · 56" and leitura["forma"] == "caixa"
    primeira = graficos.valor_indice("barras", deitada, QRectF(0, 0, 600, 120), 0)
    assert leitura["rx"] >= primeira["rx"] + primeira["rl"] + 1.5                   # 2 px de fenda entre os segmentos


def test_calor_desenha(qapp):
    _conferir_desenho("calor")


def test_dispersao_desenha(qapp):
    _conferir_desenho("dispersao")


def test_fita_desenha(qapp):
    _conferir_desenho("fita")


def test_tipo_desconhecido_e_dados_tortos_nao_levantam(qapp):
    """Oito agentes montam estes dicionários à mão: nenhuma combinação torta pode derrubar a pintura."""
    lixo = [None, True, 0, -1, 3.5, float("nan"), float("inf"), "", "x", [], {}, [[]], [None], [1, 2], [[1, 2], [3]],
            {"a": 1}, 1e308, -1e308, 1e-320, 10 ** 30, [["a", "b"]]]
    rng = random.Random(1)

    def estragar(v, prob):
        if isinstance(v, dict):
            return {k: (rng.choice(lixo) if rng.random() < prob else estragar(x, prob)) for k, x in v.items() if rng.random() > prob / 3}
        if isinstance(v, list):
            return [(rng.choice(lixo) if rng.random() < prob else estragar(x, prob)) for x in v if rng.random() > prob / 4]
        return rng.choice(lixo) if rng.random() < prob else v

    imagem = QImage(400, 300, QImage.Format.Format_ARGB32_Premultiplied)
    areas = [QRectF(0, 0, 400, 300), QRectF(0, 0, 40, 30), QRectF(0, 0, 160, 90), QRectF(5, 5, 390, 120), QRectF(0, 0, 3, 3)]
    for tipo in graficos.TIPOS:
        base = _massa(tipo)
        for _ in range(60):
            dados = estragar(copy.deepcopy(base), rng.choice([0.03, 0.1, 0.3]))
            area = rng.choice(areas)
            p = QPainter(imagem)
            try:
                graficos.desenhar(p, area, tipo, dados, None, cabecalho=rng.random() < 0.3)
            finally:
                p.end()
            graficos.valor_em(tipo, dados, area, rng.uniform(-10, 410), rng.uniform(-10, 310))
            total = graficos.total_indices(tipo, dados)
            for indice in (0, total - 1, total, -1):
                graficos.valor_indice(tipo, dados, area, indice)
            graficos.dados_para_csv(tipo, dados)
            graficos.itens_legenda(tipo, dados)
            graficos.tamanho_figura(tipo, dados)
    for tipo in ("", "pizza", None, ["xy"]):
        p = QPainter(imagem)
        graficos.desenhar(p, AREA, tipo, _massa("xy"), cabecalho=True)
        p.end()
        assert graficos.valor_em(tipo, _massa("xy"), AREA, 50, 50) == {}
        assert graficos.total_indices(tipo, _massa("xy")) == 0
        assert graficos.dados_para_csv(tipo, {"titulo": "T"}) == "# T\n"


# ---------------------------------------------------------------------------- leitura sob o cursor
def test_valor_em_devolve_o_ponto_certo(qapp):
    xy = {"eixoX": {"rotulo": "nível", "min": 0, "max": 10, "formato": "int"}, "eixoY": {"rotulo": "similaridade", "min": 0, "max": 1, "formato": "0.00"},
          "series": [{"nome": "Desfoque", "cor": "serie0", "pontos": [[0, 0.8], [5, 0.4], [10, 0.2]]}]}
    pontos = [graficos.valor_indice("xy", xy, AREA, i) for i in range(3)]
    assert [p["indice"] for p in pontos] == [0, 1, 2]
    assert abs(pontos[1]["px"] - (pontos[0]["px"] + pontos[2]["px"]) / 2) < 0.6          # x = 5 fica no meio do eixo
    assert pontos[0]["py"] < pontos[1]["py"] < pontos[2]["py"]                           # y maior fica mais alto na tela
    assert abs((pontos[1]["py"] - pontos[0]["py"]) - 2 * (pontos[2]["py"] - pontos[1]["py"])) < 0.6
    perto = graficos.valor_em("xy", xy, AREA, pontos[1]["px"] + 3, pontos[1]["py"] - 4)
    assert perto["indice"] == 1 and perto["texto"] == "Desfoque · nível 5 · similaridade 0,40" and perto["forma"] == "fio"
    assert graficos.valor_em("xy", xy, AREA, pontos[2]["px"] - 2, 150)["indice"] == 2
    assert graficos.valor_em("xy", xy, AREA, 2, 2) == {}                                 # fora da área de dados
    assert graficos.valor_em("xy", xy, AREA, 479, 299) == {}

    hist = {"eixoX": {"formato": "0.00"}, "bordas": [0.0, 0.25, 0.5, 0.75, 1.0],
            "series": [{"nome": "Genuíno", "cor": "serie0", "contagens": [1, 5, 2, 0]}]}
    faixas = [graficos.valor_indice("histograma", hist, AREA, i) for i in range(4)]
    largura = faixas[1]["px"] - faixas[0]["px"]
    assert largura > 0 and all(abs((faixas[i + 1]["px"] - faixas[i]["px"]) - largura) < 0.01 for i in range(3))
    assert faixas[1]["py"] < faixas[2]["py"] < faixas[0]["py"] < faixas[3]["py"]         # a barra mais alta é a de 5
    dentro = graficos.valor_em("histograma", hist, AREA, faixas[1]["px"] + largura * 0.3, faixas[1]["py"] + 20)
    assert dentro["indice"] == 1 and dentro["texto"] == "Genuíno · de 0,25 a 0,50 · 5"
    assert graficos.valor_em("histograma", hist, AREA, faixas[3]["px"], faixas[1]["py"])["texto"] == "Genuíno · de 0,75 a 1,00 · 0"
    assert graficos.valor_em("histograma", hist, AREA, 1, 1) == {}

    espelho = {"bordas": [0.0, 0.5, 1.0], "series": [{"nome": "Genuíno", "contagens": [2, 9], "sentido": 1},
                                                    {"nome": "Impostor", "contagens": [7, 1], "sentido": -1}]}
    em_cima, em_baixo = graficos.valor_indice("histograma", espelho, AREA, 1), graficos.valor_indice("histograma", espelho, AREA, 2)
    assert em_cima["py"] < em_baixo["py"]                                                # sentido -1 desce do eixo
    assert graficos.valor_em("histograma", espelho, AREA, em_baixo["px"], em_baixo["py"] - 3)["texto"] == "Impostor · de 0,0 a 0,5 · 7"


def test_texto_da_leitura_usa_o_rotulo_do_ponto(qapp):
    xy = {"eixoY": {"rotulo": "similaridade", "formato": "0.000"},
          "series": [{"nome": "Desfoque", "cor": "serie0", "pontos": [[0, 0.78], [4, 0.412]], "rotulos": ["σ = 0,0", "σ = 3,2"]},
                     {"nome": "Ruído", "cor": "serie1", "pontos": [[0, 0.7], [4, 0.6]]}]}
    assert graficos.valor_indice("xy", xy, AREA, 1)["texto"] == "σ = 3,2 · similaridade 0,412"
    assert graficos.valor_indice("xy", xy, AREA, 3)["texto"].startswith("Ruído · ")      # sem rótulo próprio: nome da série
    xy["eixoX"] = {"rotulo": "nível", "formato": "int"}
    assert graficos.valor_indice("xy", xy, AREA, 1)["texto"] == "σ = 3,2 · nível 4 · similaridade 0,412"

    dispersao = {"grupos": [{"nome": "Pessoa A", "cor": 0, "forma": 0, "pontos": [[0, 0], [1, 1]]},
                            {"nome": "Pessoa B", "cor": 1, "forma": 0, "pontos": [[2, 0.5], [3, 2]], "rotulos": ["Pessoa B · amostra 6", "Pessoa B · amostra 7"]}],
                 "outros": [[1.5, 1.5]]}
    textos = [graficos.valor_indice("dispersao", dispersao, AREA, i)["texto"] for i in range(5)]
    assert textos == ["Pessoa A", "Pessoa A", "Pessoa B · amostra 6", "Pessoa B · amostra 7", "Outras"]
    alvo = graficos.valor_indice("dispersao", dispersao, AREA, 3)
    assert alvo["forma"] == "anel"
    assert graficos.valor_em("dispersao", dispersao, AREA, alvo["px"] + 4, alvo["py"] + 4)["texto"] == "Pessoa B · amostra 7"


def test_leitura_de_barras_calor_e_fita(qapp):
    barras = _massa("barras")
    assert graficos.total_indices("barras", barras) == 11                               # 12 barras menos a sem valor
    assert graficos.valor_indice("barras", barras, AREA, 4)["texto"] == "Detecção · Mediana · 11,4"
    calor = {"linhas": ["Pessoa A", "Pessoa B"], "colunas": ["Pessoa A", "Pessoa B"], "valores": [[None, 0.41], [0.41, None]], "formato": "0.00"}
    assert graficos.total_indices("calor", calor) == 2                                  # célula sem valor não tem leitura
    celula = graficos.valor_indice("calor", calor, AREA, 0)
    assert celula["texto"] == "Pessoa A × Pessoa B · 0,41" and celula["forma"] == "caixa"
    assert graficos.valor_em("calor", calor, AREA, celula["px"], celula["py"])["indice"] == 0
    assert graficos.valor_em("calor", calor, AREA, celula["px"] - celula["rl"] - 2, celula["py"]) == {}    # a diagonal vazia
    fita = _um_ponto("fita")
    evento = graficos.valor_indice("fita", fita, AREA, 0)
    assert evento["texto"] == "20:41 · Não cadastrado" and evento["id"] == 7 and evento["forma"] == "fio"
    assert graficos.valor_em("fita", fita, AREA, evento["px"] + 3, evento["py"] + 5)["indice"] == 0
    assert graficos.valor_em("fita", fita, AREA, evento["px"] - 60, evento["py"] + 5) == {}
    sem_texto = {"faixas": [{"rotulo": "hoje", "eventos": [{"t": 9.5, "tipo": LIBERADO}]}]}
    assert graficos.valor_indice("fita", sem_texto, AREA, 0)["texto"] == "09:30 · Concedido"


def test_legenda_do_dado(qapp):
    assert graficos.itens_legenda("xy", _um_ponto("xy")) == []                           # uma série só dispensa legenda
    assert graficos.itens_legenda("xy", _massa("xy")) == [
        {"nome": "Desfoque", "cor": "serie0", "tracejada": False}, {"nome": "Ruído", "cor": "serie1", "tracejada": True},
        {"nome": "Pouca luz", "cor": "serie2", "tracejada": False}]
    assert [item["nome"] for item in graficos.itens_legenda("histograma", _massa("histograma"))] == ["Genuíno", "Impostor"]
    dispersao = graficos.itens_legenda("dispersao", _massa("dispersao"))
    assert [(item["cor"], item["forma"]) for item in dispersao] == [("serie0", 0), ("serie1", 0), ("serie2", 0), ("serie3", 0),
                                                                     ("serie0", 1), ("neutro", 0)]
    assert dispersao[-1]["nome"] == "Outras"
    fita = graficos.itens_legenda("fita", _massa("fita"))
    assert [item["nome"] for item in fita] == ["Concedido", "Negado", "Bloqueio", "Terminal bloqueado"]
    assert graficos.itens_legenda("calor", _massa("calor")) == []                        # o calor tem a barra de escala


# ---------------------------------------------------------------------------- exportação
def test_exporta_png_svg_csv(qapp, tmp_path):
    dados = _massa("xy")
    antes = copy.deepcopy(dados)
    caminhos = graficos.exportar("xy", dados, tmp_path / "figuras" / "robustez.v2_20261116_101500")
    assert [c.name for c in caminhos] == ["robustez.v2_20261116_101500.png", "robustez.v2_20261116_101500.svg",
                                          "robustez.v2_20261116_101500.csv"]
    assert all(c.is_file() and c.stat().st_size > 0 for c in caminhos)
    assert dados == antes                                                               # exportar não mexe nos dados de quem chamou
    largura, altura = graficos.tamanho_figura("xy", dados)
    imagem = QImage(str(caminhos[0]))
    assert (imagem.width(), imagem.height()) == (2 * largura, 2 * altura)               # PNG com o dobro do tamanho
    assert imagem.pixelColor(3, 3) == QColor("#ffffff")                                 # paleta papel
    assert apoio_v2.cores_distintas(imagem) > 12
    svg = caminhos[1].read_text(encoding="utf-8")
    assert "<svg" in svg and "Figura de teste" in svg and "limiar em vigor 0,363" in svg
    planilha = caminhos[2].read_text(encoding="utf-8-sig")
    assert ";" in planilha and "serie;nível;similaridade;minimo;maximo" in planilha
    assert "Desfoque;0;0,8;0,75;0,85" in planilha and "Pouca luz;4;;;" in planilha       # vírgula decimal; y ausente fica vazio
    for tipo in graficos.TIPOS:
        saidas = graficos.exportar(tipo, _massa(tipo), tmp_path / "todas" / tipo)
        figura = QImage(str(saidas[0]))
        assert (figura.width(), figura.height()) == tuple(2 * v for v in graficos.tamanho_figura(tipo, _massa(tipo)))
        assert "<svg" in saidas[1].read_text(encoding="utf-8") and ";" in saidas[2].read_text(encoding="utf-8-sig")


def test_csv_de_cada_tipo(qapp):
    def corpo(tipo: str, dados: dict) -> list[str]:
        return [linha for linha in graficos.dados_para_csv(tipo, dados).splitlines() if not linha.startswith("#")]

    assert corpo("histograma", {"bordas": [0, 0.5, 1], "series": [{"nome": "Genuíno", "contagens": [2, 9]}]}) == ["de;ate;Genuíno", "0;0,5;2", "0,5;1;9"]
    assert corpo("barras", {"categorias": ["A", "B"], "series": [{"nome": "Mediana", "valores": [1.5, None]}]}) == ["categoria;Mediana", "A;1,5", "B;"]
    assert corpo("calor", {"linhas": ["L1"], "colunas": ["C1", "C2"], "valores": [[0.25, None]]}) == [";C1;C2", "L1;0,25;"]
    assert corpo("dispersao", {"grupos": [{"nome": "Pessoa A", "pontos": [[1, -2.5]]}], "outros": [[0, 0]]}) == ["grupo;x;y", "Pessoa A;1;-2,5", "Outras;0;0"]
    fita = {"faixas": [{"rotulo": "hoje", "eventos": [{"t": 20.5, "tipo": "negado", "texto": "a; b"}], "intervalos": [{"t0": 20.5, "t1": 21}]}]}
    assert corpo("fita", fita) == ["faixa;inicio;fim;tipo;texto", 'hoje;20:30:00;;Negado;"a; b"', "hoje;20:30:00;21:00:00;Terminal bloqueado;"]
    cabecalho = graficos.dados_para_csv("xy", {"titulo": "T", "subtitulo": "S", "n": "N = 3", "selos": ["Sintético", "Mesma sessão · otimista"]})
    assert cabecalho.splitlines()[:5] == ["# T", "# S", "# N = 3", "# Sintético", "# Mesma sessão · otimista"]


def test_exportacao_carimba_selos(qapp, tmp_path):
    dados = _massa("histograma")
    com = graficos.exportar("histograma", dados, tmp_path / "com", carimbo="Base de demonstração")
    sem = graficos.exportar("histograma", {**dados, "selos": []}, tmp_path / "sem")
    planilha = com[2].read_text(encoding="utf-8-sig").splitlines()
    assert "# Sintético" in planilha and "# Base de demonstração" in planilha            # selo dos dados e carimbo
    assert not any(linha.startswith("# Base de demonstração") for linha in sem[2].read_text(encoding="utf-8-sig").splitlines())
    svg = com[1].read_text(encoding="utf-8")
    assert "Sintético" in svg and "Base de demonstração" in svg
    assert "Base de demonstração" not in sem[1].read_text(encoding="utf-8")
    figura_com, figura_sem = QImage(str(com[0])), QImage(str(sem[0]))
    assert figura_com.height() > figura_sem.height()                                    # a linha dos selos entra no cabeçalho do PNG
    ambar = QColor(tema_v2.PALETA_PAPEL["aviso"]).rgb()
    assert any(figura_com.pixel(x, y) == ambar for y in range(0, 260, 1) for x in range(40, 700, 1))
    assert not any(figura_sem.pixel(x, y) == ambar for y in range(0, 260, 1) for x in range(40, 700, 1))
    repetido = graficos.exportar("histograma", {**dados, "selos": ["Base de demonstração"]}, tmp_path / "rep", carimbo="Base de demonstração")
    assert repetido[2].read_text(encoding="utf-8-sig").count("# Base de demonstração") == 1


def test_exportacao_recusa_vetor(qapp, tmp_path):
    """Regra T6: um vetor de 128 dimensões não sai em PNG, SVG nem CSV, venha na forma que vier."""
    vetor = _vetor_unitario()
    como_pares = {"titulo": "Assinatura", "series": [{"nome": "v", "cor": "serie0", "pontos": [[i, float(v)] for i, v in enumerate(vetor)]}]}
    como_barras = {"categorias": [str(i) for i in range(128)], "series": [{"nome": "v", "valores": [float(v) for v in vetor]}]}
    for tipo, dados in (("xy", como_pares), ("barras", como_barras)):
        with pytest.raises(ValueError):
            graficos.exportar(tipo, dados, tmp_path / "vetor" / tipo)
    assert not (tmp_path / "vetor").exists()                                            # nada foi gravado
    assert not apoio_v2.sem_vetor_128(como_pares)
    assert graficos.exportar("xy", _massa("xy"), tmp_path / "limpo" / "xy")              # o caminho normal segue funcionando


def test_conferir_sem_vetor_pega_pares_e_poupa_histograma(qapp):
    vetor = _vetor_unitario()
    plano = [float(v) for v in vetor]
    pares = [[i, float(v)] for i, v in enumerate(vetor)]
    pelo_maior = [[float(v / np.abs(vetor).max()), i] for i, v in enumerate(vetor)]      # dividido pelo maior valor, em outra coluna
    recusados = [plano, tuple(plano), vetor, pares, pelo_maior, {"a": {"b": [1, {"c": plano}]}}, {"pontos": tuple(map(tuple, pares))},
                 [0] * 128, np.stack([np.arange(128.0), vetor], axis=1)]
    for dados in recusados:
        with pytest.raises(ValueError):
            graficos.conferir_sem_vetor(dados)
        assert not apoio_v2.sem_vetor_128(dados)
    histograma_64 = _massa("histograma")
    xy_12 = _massa("xy")
    assert len(histograma_64["series"][0]["contagens"]) == 64 and len(xy_12["series"][0]["pontos"]) == 12
    so_positivos = [[i, abs(float(v))] for i, v in enumerate(vetor)]                     # 128 pares sem sinal misturado
    fora_de_escala = [[i, float(v) * 40] for i, v in enumerate(vetor)]                   # 128 pares longe da norma 1
    aceitos = [histograma_64, xy_12, plano[:127], plano + [0.5], pares[:127], so_positivos, fora_de_escala, ["a"] * 128,
               [[i, "x"] for i in range(128)], {"n": 128, "texto": "x" * 128}, None, 3, "texto", {}, []]
    aceitos += [_massa(tipo) for tipo in graficos.TIPOS]
    for dados in aceitos:
        graficos.conferir_sem_vetor(dados)
        assert apoio_v2.sem_vetor_128(dados)


# ---------------------------------------------------------------------------- tokens e ícones
def _tokens_do_theme() -> dict:
    """Cores e listas de cores de `Theme.qml`, lidas do texto do arquivo."""
    texto = (DIR_UI / "Theme.qml").read_text(encoding="utf-8")
    tokens: dict = dict(re.findall(r'readonly property color (\w+): "(#[0-9a-fA-F]{6})"', texto))
    for nome, lista in re.findall(r"readonly property var (\w+): \[([^\]]*)\]", texto):
        tokens[nome] = tuple(re.findall(r'"(#[0-9a-fA-F]{6})"', lista))
    return tokens


def test_tema_v2_bate_com_theme_qml(qapp):
    tokens = _tokens_do_theme()
    pares = {"superficie": tema_v2.SUPERFICIE, "borda": tema_v2.BORDA, "texto": tema_v2.TEXTO, "texto2": tema_v2.TEXTO2,
             "texto3": tema_v2.TEXTO3, "acento": tema_v2.ACENTO, "sucesso": tema_v2.SUCESSO, "perigo": tema_v2.PERIGO,
             "aviso": tema_v2.AVISO, "neutroDado": tema_v2.NEUTRO_DADO, "coresSerie": tema_v2.CORES_SERIE, "calor": tema_v2.CALOR}
    for nome, valor in pares.items():
        assert tokens[nome] == valor, nome
    tela = tema_v2.PALETA_TELA
    assert (tela["fundo"], tela["tinta"], tela["tinta2"], tela["tinta3"], tela["grade"]) == (
        tokens["superficie"], tokens["texto"], tokens["texto2"], tokens["texto3"], tokens["borda"])
    assert (tela["series"], tela["neutro"], tela["calor"]) == (tokens["coresSerie"], tokens["neutroDado"], tokens["calor"])
    assert (tela[LIBERADO], tela["negado"], tela["bloqueio"], tela["aviso"]) == (
        tokens["sucesso"], tokens["perigo"], tokens["texto3"], tokens["aviso"])
    papel = tema_v2.PALETA_PAPEL                                                         # os valores da seção 5.1
    assert (papel["fundo"], papel["tinta"], papel["grade"], papel["neutro"]) == ("#ffffff", "#1b2026", "#d9dee4", "#6b7682")
    assert papel["series"] == ("#0f9a8c", "#2f6fc4", "#b8408a", "#6a5acd")
    assert (papel[LIBERADO], papel["negado"], papel["bloqueio"]) == ("#1f9d61", "#d14a4a", "#8a939e")
    assert set(papel) == set(tela)
    texto = (DIR_UI / "Theme.qml").read_text(encoding="utf-8")
    for token in ("familiaMono", "tCena", "vidro", "hover", "luzTopo", "trilho", "cena", "cenaLonga", "colunaLateral",
                  "linhaTabela", "espacoBloco"):
        assert re.search(rf"readonly property \w+ {token}:", texto), token
    assert tema_v2.cor_serie(5) == tema_v2.CORES_SERIE[1] and tema_v2.cor_calor(0.999) == tema_v2.CALOR[-1]
    assert tema_v2.cor_calor(0.0) == tema_v2.CALOR[0] and tema_v2.cor_calor(7.0) == tema_v2.CALOR[-1]
    assert tema_v2.bgr("#102030") == (0x30, 0x20, 0x10)


def test_rampa_de_calor_monotona(qapp):
    tela = [tema_v2.luminancia(cor) for cor in tema_v2.PALETA_TELA["calor"]]
    papel = [tema_v2.luminancia(cor) for cor in tema_v2.PALETA_PAPEL["calor"]]
    assert all(a < b for a, b in zip(tela, tela[1:]))            # na tela escura, mais valor = mais claro
    assert all(a > b for a, b in zip(papel, papel[1:]))          # no papel branco, mais valor = mais escuro
    assert len(tela) == len(papel) == 6


def test_icones_novos_existem(qapp):
    texto = (DIR_UI / "Icones.js").read_text(encoding="utf-8")
    chaves = re.findall(r'^\s+"(\w+)": "([^"]+)",?$', texto, flags=re.MULTILINE)
    nomes = [nome for nome, _ in chaves]
    assert len(nomes) == len(set(nomes)) == 63                                          # as 47 antigas e as 16 novas
    assert tuple(nomes[-16:]) == ICONES_NOVOS and nomes[46] == "teclado"
    for nome, caminho in chaves[-16:]:
        assert re.fullmatch(r"[MLHVCSQTAZmlhvcsqtaz0-9 .,\-]+", caminho), nome            # só comandos de caminho SVG
        numeros = [float(n) for n in re.findall(r"(?<![\d.])\d+(?:\.\d+)?", caminho.split(" ", 1)[0][1:] + " ")]
        assert all(0 <= n <= 24 for n in numeros), nome                                 # começa dentro da grade 24×24


# ---------------------------------------------------------------------------- QML sem tela
class _Cena:
    """Um componente QML criado como se estivesse na pasta `Ui/`, numa janela fora da tela."""

    def __init__(self, qapp, corpo: str, importar: str = "", largura: int = 640, altura: int = 420):
        self.qapp = qapp
        self.avisos: list[str] = []
        self.motor = QQmlEngine()
        self.motor.warnings.connect(lambda lista: self.avisos.extend(aviso.toString() for aviso in lista))
        self.motor.addImportPath(str(DIR_QML))
        fonte = ("import QtQuick\nimport QtQuick.Window\nimport QtQuick.Layouts\n" + importar
                 + f"Window {{\n    id: janela\n    width: {largura}; height: {altura}; visible: true; color: Theme.janela\n" + corpo + "\n}\n")
        self.componente = QQmlComponent(self.motor)          # fica vivo junto com a janela que ele criou
        self.componente.setData(fonte.encode("utf-8"), QUrl.fromLocalFile(str(DIR_UI / "CenaDeTeste.qml")))
        self.janela = self.componente.create()
        assert self.janela is not None, [erro.toString() for erro in self.componente.errors()]
        self.girar(0.25)

    def girar(self, segundos: float) -> None:
        fim = time.time() + segundos
        while time.time() < fim:
            self.qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            time.sleep(0.005)

    def avisos_qml(self) -> list[str]:
        return [a for a in self.avisos if not any(ignorado in a for ignorado in _AVISOS_IGNORADOS)]

    def item(self, nome: str):
        achado = apoio_v2.objeto_por_nome(self.janela, nome)
        assert achado is not None, nome
        return achado

    def focar(self, item) -> None:
        if not self.janela.isActive():
            self.janela.requestActivate()
            self.girar(0.1)
        item.forceActiveFocus()
        self.girar(0.05)

    def fechar(self) -> None:
        self.janela.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.janela = None
        self.componente = None
        self.motor.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.girar(0.02)


def _valor_js(valor):
    """Uma propriedade `var` do QML chega como QJSValue quando guarda um objeto vazio: devolve o valor Python."""
    return valor.toVariant() if isinstance(valor, QJSValue) else valor


def test_item_grafico_no_qml(qapp, monkeypatch):
    pinturas = []
    desenhar = graficos.desenhar

    def contar(p, area, tipo, dados, paleta=None, cabecalho=False):
        pinturas.append((tipo, area.width(), area.height()))
        desenhar(p, area, tipo, dados, paleta, cabecalho)

    monkeypatch.setattr(graficos, "desenhar", contar)
    cena = _Cena(qapp, """
    property var leitura: grafico.valorIndice(1)
    Grafico {
        id: grafico
        objectName: "grafico"
        x: 20; y: 20; width: 480; height: 300
        tipo: "xy"
        dados: ({ eixoX: { rotulo: "nível", formato: "int" }, eixoY: { rotulo: "similaridade", min: 0, max: 1, formato: "0.00" },
                  series: [{ nome: "Desfoque", cor: "serie0", pontos: [[0, 0.8], [4, 0.4], [8, null]] },
                           { nome: "Ruído", cor: "serie1", pontos: [[0, 0.7], [4, 0.6], [8, 0.5]], tracejada: true }],
                  marcadoresH: [{ y: 0.363, rotulo: "limiar em vigor 0,363", estilo: "vigor" }] })
    }""", "import Cofre.Nativo\n")
    try:
        grafico = cena.item("grafico")
        imagem = cena.janela.grabWindow()
        assert pinturas and pinturas[-1] == ("xy", 480.0, 300.0)                         # paint chamou o desenho único
        assert apoio_v2.cores_distintas(imagem.copy(20, 20, 480, 300), passo=2) > 12
        assert grafico.totalIndices() == 5                                              # o ponto sem y não tem leitura
        assert cena.janela.property("leitura")["texto"] == "Desfoque · nível 4 · similaridade 0,40"
        alvo = grafico.valorIndice(1)
        assert grafico.valorEm(alvo["px"] + 2, alvo["py"])["indice"] == 1
        assert grafico.valorEm(-5, -5) == {} and grafico.valorIndice(99) == {}
        legenda = grafico.property("legenda")
        assert [(item["nome"], item["tracejada"]) for item in legenda] == [("Desfoque", False), ("Ruído", True)]
        assert QColor(legenda[0]["cor"]) == QColor(tema_v2.CORES_SERIE[0])
        antes = len(pinturas)
        grafico.setProperty("dados", dict(grafico.property("dados")))                   # o mesmo valor não repinta
        cena.janela.grabWindow()
        assert len(pinturas) == antes
        grafico.setProperty("papel", True)
        assert cena.janela.grabWindow().pixelColor(24, 24) == QColor("#ffffff") and len(pinturas) == antes + 1
        grafico.setProperty("tipo", "pizza")                                            # tipo desconhecido: só o fundo
        grafico.setProperty("dados", {})
        vazio = cena.janela.grabWindow().copy(20, 20, 480, 300)
        assert apoio_v2.cores_distintas(vazio, passo=4) == 1
        assert grafico.totalIndices() == 0 and grafico.property("legenda") == []
        assert cena.avisos_qml() == []
    finally:
        cena.fechar()


def test_tabela_no_qml(qapp):
    cena = _Cena(qapp, """
    property int acionada: -1
    Tabela {
        id: tabela
        objectName: "tabela"
        x: 20; y: 20; width: 560
        destaque: 3
        colunas: [{ chave: "regra", titulo: "Regra", largura: 0 }, { chave: "linhas", titulo: "Linhas", largura: 70, alinhamento: "dir" },
                  { chave: "selo", titulo: "Selo", largura: 120, alinhamento: "centro", mono: true }]
        linhas: [{ regra: "Concedido só com nível suficiente", linhas: "121", selo: "9f2c41d0" },
                 { regra: "Desconhecido abaixo do limiar", linhas: "19", selo: "07ab35e6" },
                 { regra: "Terceira negação em 60 s bloqueia", linhas: "5", selo: "618c0d94" },
                 { regra: "Data e hora sempre crescentes", linhas: "182" }]
        onLinhaAcionada: function(indice) { janela.acionada = indice }
    }
    Tabela { objectName: "vazia"; x: 20; y: 260; width: 560; colunas: [{ chave: "a", titulo: "Coluna" }]; linhas: []; vazio: "Nenhuma regra conferida ainda" }
    """)
    try:
        tabela = cena.item("tabela")
        assert tabela.property("implicitHeight") == 30 + 4 * 40                         # cabeçalho e 4 linhas de Theme.linhaTabela
        textos = apoio_v2.textos_visiveis(cena.janela)
        for esperado in ("Regra", "Linhas", "Selo", "Concedido só com nível suficiente", "182", "618c0d94", "–",
                         "Nenhuma regra conferida ainda"):
            assert esperado in textos, esperado
        assert tabela.property("realce") == 3                                           # o destaque de quem usa
        cena.focar(tabela)
        apoio_v2.tecla(cena, Qt.Key.Key_Up)
        assert tabela.property("realce") == 2 and tabela.property("destaque") == 3      # o teclado não mexe em `destaque`
        apoio_v2.tecla(cena, Qt.Key.Key_Down)
        apoio_v2.tecla(cena, Qt.Key.Key_Down)                                           # para na última linha
        assert tabela.property("realce") == 3
        apoio_v2.tecla(cena, Qt.Key.Key_Up)
        apoio_v2.tecla(cena, Qt.Key.Key_Return)
        assert cena.janela.property("acionada") == 2
        QTest.mouseClick(cena.janela, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(120, 20 + 30 + 20))
        cena.girar(0.1)
        assert cena.janela.property("acionada") == 0
        assert cena.avisos_qml() == []
    finally:
        cena.fechar()


def test_kit_carrega_sem_avisos(qapp):
    """Os 15 componentes do kit com valores de uso, sem `app` no contexto: nenhum aviso, e o selo de
    demonstração fica invisível em vez de reclamar que `app` não existe."""
    assert sorted(KIT) == sorted(p.stem for p in DIR_UI.glob("*.qml") if p.stem in KIT)
    cena = _Cena(qapp, """
    Flow {
        anchors.fill: parent; anchors.margins: 16; spacing: 14
        Anel { objectName: "anel"; valor: 0.71; marca: 0.363; descricao: "Similaridade 0,71" }
        AnelPassos { objectName: "passos"; feitos: 1; atual: 1 }
        BarraSimilaridade { objectName: "barra"; valor: 0.71; marca: 0.363; marcaEstudo: 0.42 }
        BarraSimilaridade { objectName: "barraVazia"; valor: -1 }
        Tecla { texto: "Esc" }
        Abas { objectName: "abas"; opcoes: [{ valor: "a", texto: "Separação" }, { valor: "b", texto: "Qualidade", contador: 3, erro: true }]; atual: "a" }
        Aviso { objectName: "avisoInfo"; tipo: "info"; texto: "Informação." }
        Aviso { objectName: "avisoAviso"; tipo: "aviso"; texto: "Amostra pequena."; acao: "Usar fotos de teste"; iconeAcao: "imagem" }
        Aviso { tipo: "erro"; texto: "Falha de leitura." }
        Aviso { tipo: "consultivo"; texto: "Leitura consultiva." }
        Deslizante { objectName: "deslizante"; rotulo: "Limiar de estudo"; valor: 0.42; padrao: 0.363; casas: 3 }
        Deslizante { rotulo: "Sem padrão"; valor: 2; minimo: 0; maximo: 4; passo: 0.5; casas: 1; sufixo: " px"; habilitado: false }
        Metrica { objectName: "metrica"; rotulo: "EER"; valor: "0,49 %"; detalhe: "IC 95 %: 0,12 a 1,31"; dica: "Taxa de erro igual" }
        SeloConsultivo { objectName: "consultivo" }
        SeloDemo { objectName: "demo" }
        SeloDemo { compacto: true }
        Item { width: 300; height: 150; EstadoBloco { objectName: "estado"; anchors.fill: parent; estado: "carregando"; progresso: 0.4; cancelavel: true } }
        Item { width: 300; height: 200; EstadoBloco { anchors.fill: parent; estado: "vazio"; vazioTitulo: "Nada aqui"; vazioTexto: "Escolha uma imagem."; vazioAcao: "Escolher imagem" } }
        Item { width: 300; height: 200; EstadoBloco { anchors.fill: parent; estado: "erro"; erro: "O banco estava ocupado." } }
        Item { width: 300; height: 60; EstadoBloco { anchors.fill: parent; estado: "indisponivel"; erro: "Análise disponível só com banco em arquivo" } }
        Item { width: 300; height: 60; EstadoBloco { objectName: "pronto"; anchors.fill: parent; estado: "pronto" } }
        LegendaGrafico { width: 300; itens: [{ nome: "Genuíno", cor: "serie0" }, { nome: "Impostor", cor: "neutro" }, { nome: "A", cor: 1, forma: 2 },
                                             { nome: "Estudo", cor: "texto", tracejada: true }, { nome: "Negado", cor: "negado3" }, { nome: "Pronta", cor: "#ff8800", hachura: true }] }
        ParRotuloValor { objectName: "par"; width: 260; rotulo: "Limiar em vigor"; valor: "0,363"; dica: "Lido na hora" }
        ParRotuloValor { width: 260; rotulo: "Selo"; valor: "9f2c41d07ab35e6618c0d94f7a21be5503c7f1a4"; mono: true }
        CartaoGrafico { objectName: "cartao"; width: 420; titulo: "Sem dado"; tipo: "xy"; dados: ({ vazio: "Sem decisões no período" }); estado: "vazio" }
        CartaoGrafico { width: 420; titulo: "Com erro"; tipo: "calor"; estado: "erro"; erro: "Falha."; exportavel: false }
        Tabela { width: 300; colunas: [{ chave: "a", titulo: "A" }]; linhas: [{ a: "1" }] }
    }""", largura=980, altura=1100)
    try:
        cena.janela.grabWindow()
        assert cena.avisos_qml() == []
        assert cena.item("demo").property("visible") is False                           # sem `app`: invisível e calado
        assert cena.item("pronto").property("visible") is False
        assert cena.item("estado").property("visible") is True
        assert cena.item("anel").property("implicitWidth") == 120 and cena.item("metrica").property("implicitHeight") == 76
        textos = apoio_v2.textos_visiveis(cena.janela)
        for esperado in ("Análise consultiva · não altera o acesso", "Calculando…", "Cancelar", "Não foi possível calcular",
                         "Tentar novamente", "Análise disponível só com banco em arquivo", "Sem decisões no período", "0,420"):
            assert esperado in textos, esperado
        assert "Base de demonstração" not in textos
    finally:
        cena.fechar()


def test_abas_e_deslizante_pelo_teclado(qapp):
    cena = _Cena(qapp, """
    property string aba: "separacao"
    property real limiar: 0.42
    property int movimentos: 0
    Abas {
        objectName: "abas"; x: 20; y: 20
        atual: janela.aba
        opcoes: [{ valor: "separacao", texto: "Separação" }, { valor: "qualidade", texto: "Qualidade" }, { valor: "galeria", texto: "Galeria" }]
        onEscolhida: function(valor) { janela.aba = valor }
    }
    Deslizante {
        objectName: "deslizante"; x: 20; y: 100; width: 300
        rotulo: "Limiar de estudo"; valor: janela.limiar; minimo: 0; maximo: 1; passo: 0.005; padrao: 0.363; casas: 3
        onMovido: function(valor) { janela.movimentos += 1; if (valor <= 0.5) janela.limiar = valor }
    }""")
    try:
        abas = cena.item("abas")
        cena.focar(abas)
        apoio_v2.tecla(cena, Qt.Key.Key_Right)
        assert cena.janela.property("aba") == "qualidade"
        apoio_v2.tecla(cena, Qt.Key.Key_Left)
        apoio_v2.tecla(cena, Qt.Key.Key_Left)                                           # dá a volta
        assert cena.janela.property("aba") == "galeria"
        segunda = [item for item in apoio_v2.itens(cena.janela, lambda i: i.property("text") == "Qualidade")][0]
        apoio_v2.clicar(cena, segunda)
        assert cena.janela.property("aba") == "qualidade"

        deslizante = cena.item("deslizante")
        assert deslizante.property("foraDoPadrao") is True
        controle = apoio_v2.itens(cena.janela, lambda i: i.inherits("QQuickSlider"))[0]
        cena.focar(controle)
        apoio_v2.tecla(cena, Qt.Key.Key_Right)
        assert cena.janela.property("limiar") == pytest.approx(0.425) and cena.janela.property("movimentos") == 1
        apoio_v2.tecla(cena, Qt.Key.Key_Backspace)                                      # volta ao valor do sistema
        assert cena.janela.property("limiar") == pytest.approx(0.363) and deslizante.property("foraDoPadrao") is False
        assert "0,363" in apoio_v2.textos_visiveis(cena.janela)
        cena.janela.setProperty("limiar", 0.5)
        cena.girar(0.05)
        apoio_v2.tecla(cena, Qt.Key.Key_Right)                                          # quem usa recusou 0,505
        assert cena.janela.property("limiar") == pytest.approx(0.5)
        assert controle.property("value") == pytest.approx(0.5)                         # o controle mostra o que foi devolvido
        assert cena.avisos_qml() == []
    finally:
        cena.fechar()


def test_cartao_grafico_le_e_so_emite_exportar(qapp):
    cena = _Cena(qapp, """
    property int pedidos: 0
    CartaoGrafico {
        objectName: "cartao"; x: 20; y: 20; width: 560
        titulo: "Robustez por condição de captura"; subtitulo: "Similaridade a cada nível"; tipo: "xy"; nomeArquivo: "robustez"
        dados: ({ n: "N = 4 fotos de teste", selos: ["Sintético"], resumo: "A similaridade cai com o desfoque.",
                  eixoX: { rotulo: "nível", formato: "int" }, eixoY: { rotulo: "similaridade", min: 0, max: 1, formato: "0.00" },
                  series: [{ nome: "Desfoque", cor: "serie0", pontos: [[0, 0.8], [4, 0.4], [8, 0.2]] },
                           { nome: "Ruído", cor: "serie1", pontos: [[0, 0.7], [4, 0.6], [8, 0.5]] }] })
        onExportar: janela.pedidos += 1
    }""")
    try:
        cartao = cena.item("cartao")
        textos = apoio_v2.textos_visiveis(cena.janela)
        for esperado in ("Robustez por condição de captura", "Similaridade a cada nível", "N = 4 fotos de teste", "Sintético",
                         "Desfoque", "Ruído"):                                           # título, N, selo e a legenda que o dado pede
            assert esperado in textos, esperado
        grafico = apoio_v2.itens(cena.janela, lambda i: isinstance(i, graficos.Grafico))[0]
        alvo = grafico.valorIndice(4)
        ponto = grafico.mapToScene(QPoint(int(alvo["px"]) + 1, int(alvo["py"]) + 1)).toPoint()
        QTest.mouseMove(cena.janela, ponto + QPoint(6, 6))
        cena.girar(0.05)
        QTest.mouseMove(cena.janela, ponto)
        cena.girar(0.15)
        assert cartao.property("leitura")["texto"] == "Ruído · nível 4 · similaridade 0,60"
        assert "Ruído · nível 4 · similaridade 0,60" in apoio_v2.textos_visiveis(cena.janela)      # a linha de leitura do rodapé
        QTest.mouseMove(cena.janela, QPoint(630, 410))
        cena.girar(0.15)
        assert _valor_js(cartao.property("leitura")) == {}
        cena.focar(cartao)
        apoio_v2.tecla(cena, Qt.Key.Key_Right)
        assert cartao.property("indice") == 0 and cartao.property("leitura")["texto"] == "Desfoque · nível 0 · similaridade 0,80"
        apoio_v2.tecla(cena, Qt.Key.Key_Left)                                           # dá a volta para o último ponto
        assert cartao.property("indice") == 5
        assert cena.janela.property("pedidos") == 0
        apoio_v2.tecla(cena, Qt.Key.Key_Return)
        assert cena.janela.property("pedidos") == 1                                     # o cartão só emite; quem grava é a página
        botao = apoio_v2.itens(cena.janela, lambda i: i.property("icone") == "baixar")[0]
        apoio_v2.clicar(cena, botao)
        assert cena.janela.property("pedidos") == 2
        cartao.setProperty("estado", "carregando")
        cena.girar(0.1)
        assert grafico.isVisible() is False and "Calculando…" in apoio_v2.textos_visiveis(cena.janela)
        apoio_v2.tecla(cena, Qt.Key.Key_Return)
        assert cena.janela.property("pedidos") == 2                                     # sem dado na tela não há o que exportar
        assert cena.avisos_qml() == []
    finally:
        cena.fechar()
