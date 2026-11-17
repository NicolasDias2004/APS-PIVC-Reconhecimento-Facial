#!/usr/bin/env python3
"""Capturas das telas do aplicativo Qt Quick sem janela visível, para a documentação e a conferência.

Uso:
  python ferramentas/capturar_telas.py                         todas as telas, em <pasta temporária>/cofre-telas-<pid>/
  python ferramentas/capturar_telas.py --saida docs/telas      escolhe a pasta de saída
  python ferramentas/capturar_telas.py --so painel.geral,kit   só estas capturas (ids de --listar)
  python ferramentas/capturar_telas.py --tamanho 1080x680      janela no tamanho mínimo
  python ferramentas/capturar_telas.py --escala 2              PNG com o dobro de pixels (tela Retina)
  python ferramentas/capturar_telas.py --listar                lista os ids e as variantes e sai

Garantias:
  * nunca abre a webcam nem o banco real: o banco é uma base de demonstração gerada numa pasta
    temporária própria (apagada no fim) e a câmera é sempre a câmera falsa dos testes, com quadros
    compostos a partir das fotos de teste;
  * as cinco pastas de `config` apontam para essa pasta temporária enquanto a ferramenta roda e voltam
    ao que eram no fim, mesmo com erro (a ferramenta também roda dentro do pytest);
  * as telas de acesso concedido e negado saem de decisões reais do backend sobre os quadros da câmera
    falsa: a ferramenta nunca abre a sessão à mão, só liga e desliga a prova de vida e escolhe o nível
    pelos mesmos slots dos botões do terminal, no banco temporário;
  * nada é aberto no sistema (pasta, PDF, navegador) e nada é escrito fora da pasta temporária e da
    pasta de saída.

Código de saída: 0 tudo certo; 1 aviso de QML, captura lisa (menos de 12 cores), espera estourada ou
captura que falhou; 2 recusa (argumento inválido, banco real, Qt fora da plataforma offscreen).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parent.parent

PAGINAS_ANTIGAS: tuple[str, ...] = ("terminal", "cadastro", "usuarios", "acessos", "avaliacao", "config")
ABAS_FIXAS: tuple[str, ...] = (
    "painel.geral", "painel.incidentes", "painel.integridade",
    "laboratorio.fases", "laboratorio.robustez", "laboratorio.explicabilidade",
    "resultados.separacao", "resultados.qualidade", "resultados.galeria",
)
QUIOSQUE: tuple[str, ...] = ("quiosque-confirmando", "quiosque-prova-de-vida", "quiosque-negado", "cena-abertura")

# Ids fixos, na ordem em que são capturados. As variantes de cada aba (`VARIANTES_CAPTURA` do ViewModel
# dela) são descobertas nas classes e entram logo depois da captura base da aba.
CAPTURAS: tuple[str, ...] = (PAGINAS_ANTIGAS + ("terminal-negado", "area-nivel3") + ABAS_FIXAS + QUIOSQUE
                             + ("kit",))

TAMANHO_PADRAO = (1360, 860)                # o do Main.qml
TAMANHO_MINIMO = (1080, 680)                # minimumWidth e minimumHeight do Main.qml
MIN_CORES = 12                              # abaixo disso a captura é considerada lisa
ESPERA_ABA_SEG = 30.0                       # limite da espera genérica de uma aba
AVISOS_IGNORADOS = ("Sans Serif", "propagateSizeHints")   # os mesmos de tests/apoio_qt.py (fonte do offscreen)
FOTO_TESTE_LABORATORIO = 2                  # índice de `laboratorio.fotosTeste` usado nas abas do Laboratório


class Recusa(RuntimeError):
    """A ferramenta se recusou a rodar (nada foi capturado)."""


def _exigir(condicao: bool, mensagem: str) -> None:
    """As garantias da ferramenta: conferidas sempre (um `assert` sumiria com `python -O`)."""
    if not condicao:
        raise Recusa(mensagem)


def nome_arquivo(ident: str) -> str:
    """Nome do PNG de uma captura: o id com ':' trocado por '--'."""
    return ident.replace(":", "--") + ".png"


# ---------------------------------------------------------------------------- ids e variantes
def variantes_das_abas() -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    """Variantes declaradas por aba ("pagina.aba" -> variantes), lidas do atributo de classe
    `VARIANTES_CAPTURA` de cada ViewModel de `extensoes.REGISTRO`, sem criar aplicação, banco nem câmera.
    Um módulo que não importa fica sem variantes e o erro vai para o segundo dicionário."""
    from cofre.qt import extensoes
    classes = {chave: (modulo, classe) for chave, modulo, classe in extensoes.REGISTRO}
    variantes: dict[str, tuple[str, ...]] = {}
    erros: dict[str, str] = {}
    for pagina, abas in extensoes.ABAS.items():
        for valor, _texto, chave, _fonte in abas:
            ident = f"{pagina}.{valor}"
            try:
                modulo, classe = classes[chave]
                declaradas = getattr(getattr(importlib.import_module(modulo), classe), "VARIANTES_CAPTURA", ())
                variantes[ident] = tuple(str(v) for v in declaradas)
            except Exception as e:  # noqa: BLE001  (módulo de lote quebrado: a aba fica só com a captura base)
                variantes[ident] = ()
                erros[ident] = f"{type(e).__name__}: {e}"
    return variantes, erros


def todos_os_ids(variantes: dict[str, tuple[str, ...]]) -> list[str]:
    """Os ids fixos com as variantes de cada aba logo depois da captura base dela."""
    ids = []
    for ident in CAPTURAS:
        ids.append(ident)
        ids.extend(f"{ident}:{v}" for v in variantes.get(ident, ()))
    return ids


def listar(saida=None) -> int:
    """`--listar`: imprime os ids fixos e, em cada aba, as variantes declaradas."""
    saida = sys.stdout if saida is None else saida
    variantes, erros = variantes_das_abas()
    for ident in CAPTURAS:
        print(ident, file=saida)
        for v in variantes.get(ident, ()):
            print(f"{ident}:{v}", file=saida)
        if ident in erros:
            print(f"    (variantes indisponíveis: {erros[ident]})", file=saida)
    return 0


# ---------------------------------------------------------------------------- relatório
@dataclass
class Captura:
    """Uma captura gravada (ou que falhou)."""

    ident: str
    arquivo: Path | None = None
    tamanho: str = ""
    cores: int = 0
    estavel: bool = True
    segundos: float = 0.0
    nota: str = ""


@dataclass
class Relatorio:
    capturas: list[Captura] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    saida: Path | None = None

    @property
    def codigo(self) -> int:
        return 1 if self.falhas or self.avisos else 0

    def imprimir(self, destino=None) -> None:
        destino = sys.stdout if destino is None else destino
        print(f"\nCapturas em {self.saida}", file=destino)
        for c in self.capturas:
            arquivo = c.arquivo.name if c.arquivo is not None else "(sem arquivo)"
            print(f"  {arquivo:<44} {c.tamanho:>10} cores={c.cores:>4} estavel={'sim' if c.estavel else 'nao'} "
                  f"{c.segundos:5.2f}s{('  ' + c.nota) if c.nota else ''}", file=destino)
        print(f"Avisos do QML: {len(self.avisos) or 'nenhum'}", file=destino)
        for aviso in self.avisos:
            print(f"  {aviso}", file=destino)
        print(f"Falhas: {len(self.falhas) or 'nenhuma'}", file=destino)
        for falha in self.falhas:
            print(f"  {falha}", file=destino)


# ---------------------------------------------------------------------------- dados de exemplo do kit
def _dados_kit() -> dict[str, dict]:
    """Um dado de exemplo fixo para cada um dos seis tipos de gráfico (nada vem do banco; nenhum vetor)."""
    bordas = [round(-0.2 + i * 0.05, 2) for i in range(25)]
    genuinos = [0] * 24
    impostores = [0] * 24
    for i, n in zip(range(16, 23), (3, 9, 18, 26, 19, 8, 2)):
        genuinos[i] = n
    for i, n in zip(range(2, 9), (6, 22, 41, 37, 19, 7, 1)):
        impostores[i] = n
    niveis = list(range(9))
    desfoque = [0.78, 0.77, 0.75, 0.70, 0.61, 0.47, 0.33, 0.22, 0.15]
    ruido = [0.78, 0.76, 0.73, 0.69, 0.64, 0.57, 0.50, 0.42, 0.35]
    luz = [0.78, 0.74, 0.62, 0.43, 0.27, 0.18, 0.13, 0.11, 0.10]
    pessoas = ["Pessoa A", "Pessoa B", "Pessoa C", "Pessoa D"]
    proximidade = [[None, 0.12, 0.08, 0.21], [0.12, None, 0.39, 0.05], [0.08, 0.39, None, 0.17],
                   [0.21, 0.05, 0.17, None]]
    centros = ((-1.5, 0.9), (1.4, 1.1), (0.3, -1.4), (-1.1, -0.9))
    deslocamentos = ((0.0, 0.0), (0.22, 0.14), (-0.18, 0.2), (0.15, -0.21), (-0.2, -0.12))
    grupos = [{"nome": nome, "cor": i, "forma": 0, "centro": [cx, cy],
               "pontos": [[round(cx + dx, 2), round(cy + dy, 2)] for dx, dy in deslocamentos],
               "rotulos": [f"{nome} · amostra {k + 1}" for k in range(len(deslocamentos))]}
              for i, (nome, (cx, cy)) in enumerate(zip(pessoas, centros))]
    dias = ("seg 09/11", "ter 10/11", "qua 11/11")
    horas = ((8.4, 9.1, 13.6, 17.2), (9.8, 20.6, 20.65, 20.7), (10.2, 14.9, 16.3))
    faixas = []
    for rotulo, momentos in zip(dias, horas):
        eventos = [{"t": t, "tipo": "negado", "id": k, "texto": f"{int(t):02d}:{int(round(t % 1 * 60)) % 60:02d} · Negado"}
                   for k, t in enumerate(momentos)]
        faixas.append({"rotulo": rotulo, "eventos": eventos, "intervalos": []})
    faixas[1]["eventos"].append({"t": 20.72, "tipo": "bloqueio", "id": 9, "texto": "20:43 · Bloqueio"})
    faixas[1]["intervalos"] = [{"t0": 20.72, "t1": 21.22}]
    return {
        "histograma": {
            "titulo": "Genuíno × impostor", "subtitulo": "Similaridade de cosseno entre pares de fotos",
            "n": "N = 85 genuínos · 133 impostores", "selos": ["Exemplo"],
            "eixoX": {"rotulo": "similaridade", "min": -0.2, "max": 1.0, "formato": "0.0"},
            "eixoY": {"rotulo": "pares"}, "bordas": bordas,
            "series": [{"nome": "Genuíno", "cor": "serie0", "contagens": genuinos, "sentido": 1},
                       {"nome": "Impostor", "cor": "neutro", "contagens": impostores, "sentido": -1}],
            "marcadoresV": [{"x": 0.363, "rotulo": "limiar em vigor 0,363", "estilo": "vigor"}]},
        "xy": {
            "titulo": "Robustez por condição de captura", "subtitulo": "Similaridade com a referência a cada nível",
            "n": "N = 4 fotos de teste", "selos": ["Sintético"],
            "eixoX": {"rotulo": "nível", "formato": "int", "min": 0, "max": 8},
            "eixoY": {"rotulo": "similaridade", "min": 0, "max": 1, "formato": "0.00"},
            "series": [{"nome": "Desfoque", "cor": "serie0", "pontos": [[n, v] for n, v in zip(niveis, desfoque)]},
                       {"nome": "Ruído", "cor": "serie1", "pontos": [[n, v] for n, v in zip(niveis, ruido)]},
                       {"nome": "Pouca luz", "cor": "serie2", "pontos": [[n, v] for n, v in zip(niveis, luz)],
                        "tracejada": True}],
            "marcadoresH": [{"y": 0.363, "rotulo": "limiar em vigor 0,363", "estilo": "vigor"}]},
        "barras": {
            "titulo": "Tempo por fase do pipeline", "subtitulo": "Mediana e p95 em 40 quadros", "n": "N = 40 quadros",
            "eixoY": {"rotulo": "ms", "formato": "0.0"}, "rotulosValor": True,
            "categorias": ["Aquisição", "Pré-processo", "Detecção", "Alinhamento", "Descritor"],
            "series": [{"nome": "Mediana", "cor": "serie0", "valores": [0.8, 2.6, 11.4, 1.2, 19.7]},
                       {"nome": "p95", "cor": "neutro", "valores": [1.1, 3.4, 14.9, 1.6, 24.8]}]},
        "calor": {
            "titulo": "Proximidade entre pessoas", "subtitulo": "Maior similaridade entre pessoas diferentes",
            "n": "N = 4 pessoas", "linhas": pessoas, "colunas": pessoas, "valores": proximidade,
            "min": 0.0, "max": 0.6, "mostrarValores": True, "formato": "0.00", "marcaEscala": 0.363},
        "dispersao": {
            "titulo": "Galeria em duas dimensões", "subtitulo": "Projeção PCA dos descritores",
            "n": "N = 20 amostras · 4 pessoas", "grupos": grupos, "rotularCentros": True,
            "eixoX": {"rotulo": "componente 1"}, "eixoY": {"rotulo": "componente 2"}},
        "fita": {
            "titulo": "Negações no tempo", "subtitulo": "Um traço por decisão registrada", "n": "N = 12 decisões",
            "faixas": faixas, "eixoX": {"formato": "hora", "min": 6, "max": 23}},
    }


def _qml_kit(largura: int, altura_minima: int) -> str:
    """Janela do kit: um CartaoGrafico de cada tipo, a Tabela e os outros componentes, com dados fixos."""
    dados = _dados_kit()
    cartoes = "".join(
        f"""
                CartaoGrafico {{ Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop
                    titulo: {json.dumps(d["titulo"])}; subtitulo: {json.dumps(d["subtitulo"])}; tipo: "{tipo}"
                    altura: 200; nomeArquivo: "{tipo}"; dados: ({json.dumps(d, ensure_ascii=False)}) }}"""
        for tipo, d in dados.items())
    return f"""
import QtQuick
import QtQuick.Window
import QtQuick.Layouts

Window {{
    id: kit
    width: {largura}
    height: Math.max({altura_minima}, corpo.implicitHeight + 56)
    visible: true
    color: Theme.janela
    title: "Kit visual da v2"

    ColumnLayout {{
        id: corpo
        x: 28; y: 28; width: kit.width - 56; spacing: 22
        GridLayout {{
            Layout.fillWidth: true; columns: 3; rowSpacing: 18; columnSpacing: 18{cartoes}
        }}
        RowLayout {{
            Layout.fillWidth: true; spacing: 18
            Rectangle {{
                color: Theme.superficie; radius: Theme.raioGrande; border.color: Theme.borda
                Layout.preferredWidth: 440; Layout.preferredHeight: 250
                Text {{ x: 18; y: 16; text: "Anel, prova de vida e teclas"; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }}
                Row {{
                    x: 18; y: 54; spacing: 22
                    Item {{ width: 120; height: 120
                        Anel {{ anchors.fill: parent; valor: 0.71; marca: 0.363; descricao: "Similaridade 0,71" }}
                        Column {{ anchors.centerIn: parent
                            Text {{ anchors.horizontalCenter: parent.horizontalCenter; text: "0,71"; color: Theme.texto; font.pixelSize: 24; font.weight: Font.DemiBold }}
                            Text {{ anchors.horizontalCenter: parent.horizontalCenter; text: "acima do limiar"; color: Theme.acento; font.pixelSize: Theme.tLegenda }} }} }}
                    Item {{ width: 120; height: 120
                        Anel {{ anchors.fill: parent; valor: 0.21; marca: 0.363; cor: Theme.texto2; descricao: "Similaridade 0,21" }}
                        Column {{ anchors.centerIn: parent
                            Text {{ anchors.horizontalCenter: parent.horizontalCenter; text: "0,21"; color: Theme.texto; font.pixelSize: 24; font.weight: Font.DemiBold }}
                            Text {{ anchors.horizontalCenter: parent.horizontalCenter; text: "abaixo do limiar"; color: Theme.texto2; font.pixelSize: Theme.tLegenda }} }} }}
                    AnelPassos {{ width: 96; height: 96; anchors.verticalCenter: parent.verticalCenter; feitos: 1; atual: 1 }}
                }}
                Row {{ x: 18; y: 210; spacing: 6; Tecla {{ texto: "Esc" }} Tecla {{ texto: "⌘⇧F" }} Tecla {{ texto: "L" }} }}
            }}
            Rectangle {{
                color: Theme.superficie; radius: Theme.raioGrande; border.color: Theme.borda
                Layout.fillWidth: true; Layout.preferredHeight: 250
                ColumnLayout {{
                    anchors.fill: parent; anchors.margins: 18; spacing: 14
                    Abas {{ opcoes: [{{ valor: "s", texto: "Separação" }}, {{ valor: "q", texto: "Qualidade", contador: 3 }}, {{ valor: "g", texto: "Galeria" }}]; atual: "q" }}
                    RowLayout {{
                        Layout.fillWidth: true; spacing: 26
                        ColumnLayout {{
                            Layout.fillWidth: true; Layout.preferredWidth: 1; spacing: 12
                            Deslizante {{ Layout.fillWidth: true; rotulo: "Limiar de estudo"; valor: 0.42; padrao: 0.363; casas: 3 }}
                            Deslizante {{ Layout.fillWidth: true; rotulo: "Desfoque (σ)"; valor: 1.5; minimo: 0; maximo: 4; passo: 0.5; padrao: 1.5; casas: 1; sufixo: " px" }}
                        }}
                        ColumnLayout {{
                            Layout.fillWidth: true; Layout.preferredWidth: 1; spacing: 12
                            Text {{ text: "Barra de similaridade"; color: Theme.texto2; font.pixelSize: Theme.tPequeno }}
                            BarraSimilaridade {{ Layout.fillWidth: true; valor: 0.71; marca: 0.363; marcaEstudo: 0.42 }}
                            BarraSimilaridade {{ Layout.fillWidth: true; valor: 0.28; marca: 0.363; cor: Theme.texto2 }}
                            ParRotuloValor {{ Layout.fillWidth: true; rotulo: "Limiar em vigor"; valor: "0,363" }}
                            ParRotuloValor {{ Layout.fillWidth: true; rotulo: "Selo SHA-256"; valor: "9f2c41d07ab35e6618c0d94f7a21be5503c7f1a4"; mono: true }}
                        }}
                    }}
                }}
            }}
        }}
        RowLayout {{
            Layout.fillWidth: true; spacing: 14
            Metrica {{ Layout.fillWidth: true; rotulo: "EER"; valor: "0,49 %"; detalhe: "IC 95 %: 0,12 a 1,31" }}
            Metrica {{ Layout.fillWidth: true; rotulo: "AUC"; valor: "0,998"; detalhe: "N = 85 · 133" }}
            Metrica {{ Layout.fillWidth: true; rotulo: "Falso aceite no limiar"; valor: "0 de 133"; detalhe: "teto 2,2 %" }}
            ColumnLayout {{
                spacing: 8
                SeloConsultivo {{}}
                RowLayout {{ spacing: 8; SeloDemo {{}} Selo {{ texto: "Sintético"; cor: Theme.aviso }} }}
            }}
        }}
        GridLayout {{
            Layout.fillWidth: true; columns: 2; rowSpacing: 10; columnSpacing: 14
            Aviso {{ Layout.fillWidth: true; tipo: "info"; texto: "As fotos de teste vêm da pasta tests/fixtures e não entram no banco." }}
            Aviso {{ Layout.fillWidth: true; tipo: "aviso"; texto: "2 pares genuínos e 4 impostores: leia como exemplo, não como taxa." }}
            Aviso {{ Layout.fillWidth: true; tipo: "erro"; texto: "O banco estava ocupado e a leitura falhou."; acao: "Tentar novamente" }}
            Aviso {{ Layout.fillWidth: true; tipo: "consultivo"; texto: "Leitura consultiva: nada aqui muda o acesso." }}
        }}
        RowLayout {{
            Layout.fillWidth: true; spacing: 14
            Rectangle {{ color: Theme.superficie; radius: Theme.raioGrande; border.color: Theme.borda; Layout.fillWidth: true; Layout.preferredHeight: 190
                EstadoBloco {{ anchors.fill: parent; estado: "vazio"; vazioIcone: "imagem"; vazioTitulo: "Nenhuma amostra"; vazioTexto: "Escolha uma imagem para ver cada fase." }} }}
            Rectangle {{ color: Theme.superficie; radius: Theme.raioGrande; border.color: Theme.borda; Layout.fillWidth: true; Layout.preferredHeight: 190
                EstadoBloco {{ anchors.fill: parent; estado: "carregando"; progresso: 0.4; cancelavel: true }} }}
            Rectangle {{ color: Theme.superficie; radius: Theme.raioGrande; border.color: Theme.borda; Layout.fillWidth: true; Layout.preferredHeight: 190
                EstadoBloco {{ anchors.fill: parent; estado: "erro"; erro: "O banco estava ocupado." }} }}
            Rectangle {{ color: Theme.superficie; radius: Theme.raioGrande; border.color: Theme.borda; Layout.fillWidth: true; Layout.preferredHeight: 190
                EstadoBloco {{ anchors.fill: parent; estado: "indisponivel"; erro: "Análise disponível só com banco em arquivo" }} }}
        }}
        Rectangle {{
            color: Theme.superficie; radius: Theme.raioGrande; border.color: Theme.borda
            Layout.fillWidth: true; Layout.preferredHeight: tabela.implicitHeight + 70
            Text {{ x: 18; y: 16; text: "Regras de integridade"; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }}
            LegendaGrafico {{ x: 300; y: 20; itens: [{{ nome: "Genuíno", cor: "serie0" }}, {{ nome: "Impostor", cor: "neutro" }},
                                                    {{ nome: "Pessoa C", cor: 2, forma: 2 }}, {{ nome: "Estudo", cor: "texto", tracejada: true }},
                                                    {{ nome: "Bloqueado", cor: "bloqueio", hachura: true }}] }}
            Tabela {{ id: tabela; x: 18; y: 50; width: parent.width - 36; destaque: 1
                colunas: [{{ chave: "regra", titulo: "Regra", largura: 0 }}, {{ chave: "linhas", titulo: "Linhas", largura: 80, alinhamento: "dir" }},
                          {{ chave: "estado", titulo: "Estado", largura: 120, alinhamento: "centro" }}, {{ chave: "selo", titulo: "Selo", largura: 200, mono: true }}]
                linhas: [{{ regra: "Nível suficiente em toda liberação", linhas: "121", estado: "confere", selo: "9f2c41d07ab35e66" }},
                         {{ regra: "Desconhecido sempre abaixo do limiar", linhas: "19", estado: "confere", selo: "07ab35e6618c0d94" }},
                         {{ regra: "Terceira negação em 60 s bloqueia o terminal", linhas: "5", estado: "confere", selo: "618c0d94f7a21be5" }},
                         {{ regra: "Data e hora sempre crescentes", linhas: "182", estado: "confere" }}] }}
        }}
    }}
}}
"""


# ---------------------------------------------------------------------------- a sessão de capturas
def estabilizar(janela, girar: Callable[[float], None], maximo: float = 2.5, passo: float = 0.15):
    """Captura até dois quadros seguidos saírem iguais. Devolve (imagem, estavel). Tela com animação
    contínua nunca estabiliza: aí vale a última captura."""
    anterior = janela.grabWindow()
    fim = time.time() + maximo
    while time.time() < fim:
        girar(passo)
        atual = janela.grabWindow()
        if atual == anterior:
            return atual, True
        anterior = atual
    return anterior, False


class _Sessao:
    """Aplicativo completo sobre a base de demonstração temporária, com a câmera falsa."""

    def __init__(self, qapp, caminho_db: Path, pipeline, pasta_tmp: Path, saida: Path, tamanho: tuple[int, int],
                 pedidos: set[str], variantes: dict[str, tuple[str, ...]], relatorio: Relatorio):
        import numpy as np

        from cofre import amostra_lab, base_demo
        from cofre.qt.aplicacao import Aplicacao
        from cofre.qt.app import criar_motor
        from tests import apoio_v2
        from tests.apoio_interface import FonteFalsa
        from tests.apoio_qt import Contexto

        self.tmp = pasta_tmp
        self.saida = saida
        self.tamanho = tamanho
        self.pedidos = pedidos
        self.variantes = variantes
        self.rel = relatorio
        self.apoio = apoio_v2
        # quem está diante da câmera falsa: relido a cada abertura da câmera (Anexo A.5, item 5)
        self.na_camera: list = []
        self.preto = np.zeros((720, 1280, 3), np.uint8)
        self.quadros = self._quadros_por_nivel(amostra_lab, base_demo)
        self.fotos = [caminho for grupo in amostra_lab.fotos_de_teste().values() for caminho in grupo]
        apl = Aplicacao(str(caminho_db), fonte_camera=lambda: FonteFalsa(list(self.na_camera)), carregar_modelos=False)
        avisos: list[str] = []
        motor = criar_motor(apl, avisos)
        self.ctx = Contexto(qapp, apl, motor, avisos)
        _exigir(self.ctx.janela is not None, "Main.qml não carregou: " + "; ".join(avisos))
        apl.usar_pipeline(pipeline)
        self.ctx.janela.setWidth(tamanho[0])
        self.ctx.janela.setHeight(tamanho[1])
        self.ctx.girar(0.1)
        self._avisos_vistos = 0

    @staticmethod
    def _quadros_por_nivel(amostra_lab, base_demo) -> dict[int, object]:
        """Um quadro de câmera falsa para cada pessoa da base, pelo nível dela: o de `QUADROS_OK` que é
        foto dessa pessoa (a base cadastra as pessoas de teste na ordem de `fotos_de_teste`)."""
        from tests import apoio_v2
        quadros = {}
        grupos = list(amostra_lab.fotos_de_teste().values())
        for (_nome, _matricula, _cargo, nivel), fotos in zip(base_demo.IDENTIDADES, grupos):
            resolvidas = {f.resolve() for f in fotos}
            caminho = next((f for f in apoio_v2.QUADROS_OK if f.resolve() in resolvidas), None)
            _exigir(caminho is not None, f"nenhum quadro de câmera falsa serve para a pessoa de nível {nivel}")
            quadros[nivel] = apoio_v2.quadro_webcam(caminho)
        _exigir({2, 3} <= set(quadros), "a base de demonstração precisa de uma pessoa de nível 2 e uma de nível 3")
        return quadros

    # ------------------------------------------------------------------ utilidades
    @property
    def apl(self):
        return self.ctx.apl

    def girar(self, segundos: float) -> None:
        self.ctx.girar(segundos)

    def esperar(self, condicao, segundos: float, passo: float = 0.02) -> bool:
        """Gira o loop em passos curtos até a condição valer (um estado curto, como CONFIRMANDO, não escapa)."""
        fim = time.time() + segundos
        while time.time() < fim:
            if condicao():
                return True
            self.girar(passo)
        return bool(condicao())

    def quer(self, *ids: str) -> bool:
        return any(i in self.pedidos for i in ids)

    def falhar(self, ident: str, texto: str) -> None:
        self.rel.falhas.append(f"{ident}: {texto}")

    def gravar(self, ident: str, imagem, estavel: bool, inicio: float, nota: str = "") -> None:
        """Grava o PNG de um id pedido e confere se a imagem não saiu lisa."""
        if ident not in self.pedidos:
            return
        destino = self.saida / nome_arquivo(ident)
        cap = Captura(ident, destino, f"{imagem.width()}x{imagem.height()}", self.apoio.cores_distintas(imagem),
                      estavel, time.perf_counter() - inicio, nota)
        if not imagem.save(str(destino)):
            cap.arquivo = None
            self.falhar(ident, f"não foi possível gravar {destino}")
        elif cap.cores < MIN_CORES:
            self.falhar(ident, f"captura lisa ({cap.cores} cores)")
        self.rel.capturas.append(cap)

    def capturar(self, ident: str, inicio: float, maximo: float = 2.5, nota: str = "") -> None:
        imagem, estavel = estabilizar(self.ctx.janela, self.girar, maximo)
        self.gravar(ident, imagem, estavel, inicio, nota)

    def coletar_avisos(self, ident: str) -> None:
        """Avisos do QML que apareceram desde a última coleta, com o id em que surgiram."""
        novos = [a for a in self.ctx.avisos[self._avisos_vistos:] if not any(i in a for i in AVISOS_IGNORADOS)]
        self._avisos_vistos = len(self.ctx.avisos)
        self.rel.avisos.extend(f"[{ident}] {a}" for a in novos)

    # ------------------------------------------------------------------ terminal e câmera
    def sair_do_terminal(self) -> None:
        """Deixa o terminal (e o quiosque, que sai junto): a câmera só relê quem está diante dela quando abre de novo."""
        self.encerrar_sessao()
        if self.apl.pagina == "terminal":
            self.apl.navegar("usuarios")
            self.girar(0.2)

    def diante_da_camera(self, quadro) -> None:
        self.sair_do_terminal()
        self.na_camera[:] = [quadro]

    def preparar_terminal(self, liveness: bool, nivel_pessoa: int) -> None:
        """Prova de vida e nível pelos slots dos botões do terminal (banco temporário) e a pessoa na câmera."""
        self.diante_da_camera(self.quadros[nivel_pessoa])
        terminal = self.apl.terminal_vm
        terminal.definirLiveness(liveness)
        terminal.definirNivel(3)
        _exigir(terminal.liveness == liveness and terminal.nivel == 3, "o terminal recusou a configuração da captura")

    def encerrar_sessao(self) -> None:
        """Ninguém diante da câmera e a sessão encerrada (senão o terminal reabriria a sessão; Anexo A.5, item 6)."""
        if self.apl.sessao_vm.ativa:
            self.na_camera[:] = [self.preto]
            self.apl.sessao_vm.encerrar()
            self.girar(0.5)

    # ------------------------------------------------------------------ etapas
    def pagina_antiga(self, pagina: str) -> None:
        inicio = time.perf_counter()
        if pagina == "terminal":
            self.preparar_terminal(True, 3)
        self.apl.navegar(pagina)
        _exigir(self.apl.pagina == pagina, f"a navegação para {pagina!r} foi recusada")
        self.girar(0.3)
        if pagina == "terminal":
            # prova de vida ligada: a foto parada fica pedindo o giro, sem decidir nada
            if not self.esperar(lambda: self.apl.terminal_vm.estado == "LIVENESS", 20):
                self.falhar(pagina, f"espera estourada: o terminal ficou em {self.apl.terminal_vm.estado}")
        elif pagina == "cadastro":
            self.esperar(lambda: self.apl.camera.estado in ("ativa", "erro", "desligada"), 5)
        elif pagina == "avaliacao":
            # as 5 fases numa foto de teste copiada com nome neutro (o nome do arquivo aparece na tela)
            foto = self.tmp / "foto_de_teste.jpg"
            shutil.copyfile(self.fotos[-1], foto)
            avaliacao = self.apl.avaliacao_vm
            avaliacao.demonstrar(str(foto))
            if not self.esperar(lambda: not avaliacao.demoProcessando and len(avaliacao.demoFases) == 5, 20):
                self.falhar(pagina, "espera estourada: a demonstração das 5 fases não terminou")
        self.capturar(pagina, inicio)

    def terminal_negado(self) -> None:
        """Pessoa de nível 2 pedindo o nível 3, sem prova de vida: NEGADO_NIVEL pelo backend."""
        inicio = time.perf_counter()
        self.preparar_terminal(False, 2)
        self.apl.navegar("terminal")
        terminal = self.apl.terminal_vm
        if not self.esperar(lambda: terminal.estado == "RESULTADO", 20):
            self.falhar("terminal-negado", f"espera estourada: o terminal ficou em {terminal.estado}")
        elif terminal.resultadoTipo != "NEGADO_NIVEL":
            self.falhar("terminal-negado", f"o backend decidiu {terminal.resultadoTipo}, não NEGADO_NIVEL")
        self.girar(0.25)
        self.capturar("terminal-negado", inicio, maximo=1.5)    # o veredito fica só alguns segundos na tela
        self.sair_do_terminal()

    def area_nivel3(self) -> None:
        """Pessoa de nível 3 na área 3, sem prova de vida: a sessão abre pela decisão do backend."""
        inicio = time.perf_counter()
        self.preparar_terminal(False, 3)
        self.apl.navegar("terminal")
        if not self.esperar(lambda: self.apl.sessao_vm.ativa, 25):
            self.falhar("area-nivel3", f"espera estourada: a sessão não abriu ({self.apl.terminal_vm.resultadoTipo})")
        self.girar(0.6)                                          # transição da área liberada
        self.capturar("area-nivel3", inicio)
        self.sair_do_terminal()

    def aba(self, ident: str) -> None:
        """Genérico: aba escolhida antes de navegar, foto de teste no Laboratório, `preparar_captura` e a
        espera até a aba sair de "carregando" com os trabalhos parados."""
        inicio = time.perf_counter()
        base, _, variante = ident.partition(":")
        pagina, _, valor = base.partition(".")
        vm_pagina = self.apl.extensoes.obter(pagina)
        vm_pagina.definirAba(valor)
        _exigir(vm_pagina.aba == valor, f"a página {pagina!r} não tem a aba {valor!r}")
        self.apl.navegar(pagina)
        _exigir(self.apl.pagina == pagina, f"a navegação para {pagina!r} foi recusada")
        self.girar(0.3)
        trabalhos = self.apl.extensoes.trabalhos
        if pagina == "laboratorio":
            laboratorio = self.apl.extensoes.obter("laboratorio")
            laboratorio.usarFotoTeste(FOTO_TESTE_LABORATORIO)
            if not self.esperar(lambda: not laboratorio.processando, ESPERA_ABA_SEG):
                self.falhar(ident, "espera estourada: a foto de teste do Laboratório não ficou pronta")
        vm_aba = vm_pagina.vm_aba(valor)
        erro_carga = getattr(vm_aba, "erroCarga", "")
        if erro_carga:
            self.falhar(ident, f"ViewModel indisponível: {erro_carga}")
        else:
            vm_aba.preparar_captura(variante)
            self.girar(0.05)
            if not self.esperar(lambda: vm_aba.estado != "carregando" and trabalhos.ocioso(), ESPERA_ABA_SEG, 0.05):
                self.falhar(ident, f"espera estourada ({ESPERA_ABA_SEG:.0f} s): a aba ficou em {vm_aba.estado}")
        self.capturar(ident, inicio)

    def quiosque_prova_de_vida(self) -> None:
        """Pessoa de nível 3 com prova de vida: CONFIRMANDO (sem estabilizar) e depois LIVENESS."""
        inicio = time.perf_counter()
        self.preparar_terminal(True, 3)
        self.apl.extensoes.entrarQuiosque()
        terminal = self.apl.terminal_vm
        if self.esperar(lambda: terminal.estado == "CONFIRMANDO", 20, 0.005):
            estado = terminal.estado
            nota = "" if estado == "CONFIRMANDO" else f"saiu {estado}"
            self.gravar("quiosque-confirmando", self.ctx.janela.grabWindow(), True, inicio, nota)
        elif self.quer("quiosque-confirmando"):
            self.falhar("quiosque-confirmando", f"espera estourada: o terminal ficou em {terminal.estado}")
        inicio = time.perf_counter()
        if not self.esperar(lambda: terminal.estado == "LIVENESS", 20):
            self.falhar("quiosque-prova-de-vida", f"espera estourada: o terminal ficou em {terminal.estado}")
        self.capturar("quiosque-prova-de-vida", inicio)
        self.apl.extensoes.sairQuiosque()
        self.sair_do_terminal()

    def quiosque_negado(self) -> None:
        """Pessoa de nível 2 pedindo o nível 3 no modo porta, sem prova de vida: NEGADO_NIVEL pelo backend."""
        inicio = time.perf_counter()
        self.preparar_terminal(False, 2)
        self.apl.extensoes.entrarQuiosque()
        terminal = self.apl.terminal_vm
        if not self.esperar(lambda: terminal.estado == "RESULTADO", 20):
            self.falhar("quiosque-negado", f"espera estourada: o terminal ficou em {terminal.estado}")
        elif terminal.resultadoTipo != "NEGADO_NIVEL":
            self.falhar("quiosque-negado", f"o backend decidiu {terminal.resultadoTipo}, não NEGADO_NIVEL")
        self.girar(0.25)
        self.capturar("quiosque-negado", inicio, maximo=1.5)
        self.apl.extensoes.sairQuiosque()
        self.sair_do_terminal()

    def cena_abertura(self) -> None:
        """Pessoa de nível 3 no modo porta, sem prova de vida: a sessão abre e a cena começa por cima."""
        inicio = time.perf_counter()
        self.preparar_terminal(False, 3)
        self.apl.extensoes.entrarQuiosque()
        if not self.esperar(lambda: self.apl.sessao_vm.ativa, 25):
            self.falhar("cena-abertura", f"espera estourada: a sessão não abriu ({self.apl.terminal_vm.resultadoTipo})")
        self.girar(0.35)
        self.gravar("cena-abertura", self.ctx.janela.grabWindow(), True, inicio, "sem estabilizar (cena em movimento)")
        self.encerrar_sessao()
        self.apl.extensoes.sairQuiosque()
        self.sair_do_terminal()

    def kit(self) -> None:
        """O kit visual fora da navegação: um QQmlComponent no mesmo motor (com `app`, para o selo)."""
        from PySide6.QtCore import QCoreApplication, QEvent, QUrl
        from PySide6.QtQml import QQmlComponent

        from cofre.qt.app import DIR_QML

        inicio = time.perf_counter()
        componente = QQmlComponent(self.ctx.motor)
        # a URL de base fica na pasta Ui, para os componentes do kit serem achados pelo nome
        componente.setData(_qml_kit(*self.tamanho).encode("utf-8"),
                           QUrl.fromLocalFile(str(DIR_QML / "Cofre" / "Ui" / "KitCaptura.qml")))
        janela = componente.create()
        if janela is None:
            self.falhar("kit", "; ".join(e.toString() for e in componente.errors()))
            return
        try:
            self.girar(0.6)
            imagem, estavel = estabilizar(janela, self.girar)
            self.gravar("kit", imagem, estavel, inicio)
        finally:
            janela.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.girar(0.05)

    # ------------------------------------------------------------------ roteiro
    def etapas(self) -> list[tuple[tuple[str, ...], Callable[[], None]]]:
        """(ids que a etapa produz, função), na ordem de captura."""
        lista: list[tuple[tuple[str, ...], Callable[[], None]]] = []
        for pagina in PAGINAS_ANTIGAS:
            lista.append(((pagina,), lambda p=pagina: self.pagina_antiga(p)))
        lista.append((("terminal-negado",), self.terminal_negado))
        lista.append((("area-nivel3",), self.area_nivel3))
        for base in ABAS_FIXAS:
            for ident in (base, *(f"{base}:{v}" for v in self.variantes.get(base, ()))):
                lista.append(((ident,), lambda i=ident: self.aba(i)))
        lista.append((("quiosque-confirmando", "quiosque-prova-de-vida"), self.quiosque_prova_de_vida))
        lista.append((("quiosque-negado",), self.quiosque_negado))
        lista.append((("cena-abertura",), self.cena_abertura))
        lista.append((("kit",), self.kit))
        return lista

    def executar(self) -> None:
        for ids, etapa in self.etapas():
            if not self.quer(*ids):
                continue
            rotulo = ",".join(i for i in ids if i in self.pedidos)
            try:
                etapa()
            except Exception as e:  # noqa: BLE001  (uma tela quebrada não impede as outras)
                traceback.print_exc()
                self.falhar(rotulo, f"{type(e).__name__}: {e}")
                try:
                    self.apl.extensoes.sairQuiosque()
                    self.sair_do_terminal()
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
            self.coletar_avisos(rotulo)

    def fechar(self) -> None:
        self.encerrar_sessao()
        self.ctx.fechar()                       # fecha o app, solta a janela e só então destrói o motor
        self.coletar_avisos("encerramento")


# ---------------------------------------------------------------------------- ambiente e entrada
def _forcar_ambiente(escala: int) -> None:
    """Plataforma offscreen e renderizador por software antes do primeiro `import PySide6` (Anexo A.5,
    item 1). Dentro do pytest o PySide6 já foi carregado nessa plataforma: aí só confere."""
    qt_iniciado = False
    if "PySide6.QtGui" in sys.modules:
        from PySide6.QtGui import QGuiApplication
        qt_iniciado = QGuiApplication.instance() is not None
    if qt_iniciado:
        _exigir(escala == 1, "--escala só vale num processo em que o Qt ainda não foi iniciado")
    else:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ["QT_QUICK_BACKEND"] = "software"
        if escala != 1:
            os.environ["QT_SCALE_FACTOR"] = str(escala)
    _exigir(os.environ.get("QT_QPA_PLATFORM") == "offscreen", "QT_QPA_PLATFORM precisa ser offscreen")
    _exigir(os.environ.get("QT_QUICK_BACKEND") == "software", "QT_QUICK_BACKEND precisa ser software")


def _preparar_qt():
    """A QGuiApplication (a existente é reaproveitada), conferida na plataforma offscreen."""
    from PySide6.QtGui import QGuiApplication

    from cofre.qt.app import preparar_qt
    qapp = preparar_qt([])
    _exigir(QGuiApplication.platformName() == "offscreen",
            f"a aplicação Qt usa a plataforma {QGuiApplication.platformName()!r}, não offscreen")
    return qapp


def _tamanho(texto: str) -> tuple[int, int]:
    try:
        largura, altura = (int(x) for x in texto.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"tamanho inválido: {texto!r} (use LARGURAxALTURA, como 1360x860)") from None
    if largura < TAMANHO_MINIMO[0] or altura < TAMANHO_MINIMO[1]:
        raise argparse.ArgumentTypeError(f"o mínimo da janela é {TAMANHO_MINIMO[0]}x{TAMANHO_MINIMO[1]}")
    return largura, altura


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--saida", type=Path, help="pasta dos PNG (padrão: <pasta temporária>/cofre-telas-<pid>/)")
    p.add_argument("--so", default="", help="ids separados por vírgula (veja --listar)")
    p.add_argument("--escala", type=int, choices=(1, 2), default=1, help="2 gera PNG com o dobro de pixels")
    p.add_argument("--tamanho", type=_tamanho, default=TAMANHO_PADRAO, help="LARGURAxALTURA da janela (mínimo 1080x680)")
    p.add_argument("--listar", action="store_true", help="lista os ids e as variantes e sai, sem abrir nada")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Gera as capturas pedidas e devolve o código de saída (0, 1 ou 2)."""
    args = _argumentos(argv)
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))           # rodando como script, sys.path[0] é ferramentas/
    try:
        _forcar_ambiente(args.escala)
        if args.listar:
            return listar()
        return _capturar(args)
    except Recusa as recusa:
        print(f"Capturas: {recusa}", file=sys.stderr)
        return 2


def _capturar(args: argparse.Namespace) -> int:
    variantes, _erros = variantes_das_abas()      # módulo quebrado: a captura da aba registra a falha
    validos = todos_os_ids(variantes)
    pedidos = [i.strip() for i in args.so.split(",") if i.strip()] if args.so else list(validos)
    desconhecidos = [i for i in pedidos if i not in validos]
    _exigir(not desconhecidos, f"ids desconhecidos: {', '.join(desconhecidos)} (veja --listar)")
    saida = (args.saida if args.saida is not None else Path(tempfile.gettempdir()) / f"cofre-telas-{os.getpid()}").resolve()
    _exigir(not saida.is_relative_to(RAIZ / "data"), "a pasta de saída não pode ficar dentro de data/")

    qapp = _preparar_qt()
    from cofre import base_demo, config
    from cofre.pipeline import Pipeline

    relatorio = Relatorio(saida=saida)
    tmp = Path(tempfile.mkdtemp(prefix="cofre-capturas-"))
    alvo = base_demo.pastas(tmp)
    antes = {nome: getattr(config, nome) for nome in base_demo.VARIAVEIS}
    # trocadas antes de criar o banco ou a Aplicacao: ela lê config_usuario.json no construtor e o cadastro
    # grava os recortes em config.FOTOS_DIR (Anexo A.5, item 2)
    config.DATA_DIR = alvo["DATA_DIR"]
    config.DB_PATH = alvo["DB_PATH"]
    config.FOTOS_DIR = alvo["FOTOS_DIR"]
    config.EVIDENCIAS_DIR = alvo["EVIDENCIAS_DIR"]
    config.RELATORIOS_DIR = alvo["RELATORIOS_DIR"]
    sessao = None
    try:
        pipeline = Pipeline()
        caminho_db = Path(base_demo.gerar(tmp, raiz_permitida=tmp, pipeline=pipeline))
        _exigir(caminho_db.resolve() != base_demo.BANCO_REAL, "o banco resolvido é o banco real (data/cofre.db)")
        _exigir(caminho_db.resolve().is_relative_to(tmp.resolve()), f"o banco {caminho_db} fica fora da pasta temporária")
        saida.mkdir(parents=True, exist_ok=True)
        sessao = _Sessao(qapp, caminho_db, pipeline, tmp, saida, args.tamanho, set(pedidos), variantes, relatorio)
        sessao.executar()
    except base_demo.RecusaBaseDemo as recusa:
        raise Recusa(f"base de demonstração: {recusa}") from None
    finally:
        if sessao is not None:
            sessao.fechar()
        config.DATA_DIR = antes["DATA_DIR"]
        config.DB_PATH = antes["DB_PATH"]
        config.FOTOS_DIR = antes["FOTOS_DIR"]
        config.EVIDENCIAS_DIR = antes["EVIDENCIAS_DIR"]
        config.RELATORIOS_DIR = antes["RELATORIOS_DIR"]
        shutil.rmtree(tmp, ignore_errors=True)
    relatorio.imprimir()
    return relatorio.codigo


if __name__ == "__main__":
    sys.exit(main())
