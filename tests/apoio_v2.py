"""Apoio para os testes da versão 2 (análise, modo porta e ferramentas); `tests/apoio_qt.py` não é editado.

Reúne a fixture de isolamento, o preparo de pastas e de banco temporários, as esperas pelos trabalhos
em segundo plano e a leitura da árvore visual do QML. Nada aqui abre a webcam, o banco real nem um
programa do sistema: a câmera é sempre falsa, o banco é temporário e o que o código novo tentaria
abrir no sistema fica só anotado em `ABERTOS`.

Cada arquivo de teste novo que cria a `Aplicacao` importa a fixture:

    from tests.apoio_v2 import _config_isolada  # noqa: F401
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import cv2
import numpy as np
import pytest

from tests.apoio_qt import Contexto, criar_contexto  # noqa: F401  (reexporta; define a plataforma offscreen)

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from cofre import config, parametros  # noqa: E402
from cofre.banco import Banco, Usuario  # noqa: E402
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens  # noqa: E402
from tests.apoio_interface import FOTO_BIDEN, FOTO_BIDEN_2, FOTO_OBAMA_2  # noqa: E402

# O que o código novo tentou abrir no sistema durante o teste (pasta de figuras, selos, relatório).
ABERTOS: list[Path] = []

# Fotos de teste cujo quadro composto por `quadro_webcam` tem exatamente um rosto para o detector.
QUADROS_OK: tuple[Path, ...] = (FOTO_OBAMA_2, FOTO_BIDEN_2, FOTO_BIDEN)

_CHAVES_ACESSO = frozenset({"data_hora", "resultado", "usuario_id", "nome_detectado", "nivel_usuario",
                            "nivel_exigido", "similaridade", "mensagem", "evidencia"})


def _registrar_abertura(caminho) -> bool:
    """Fica no lugar de `vm_figuras.abrir_no_sistema` durante o teste: anota o caminho e não abre nada."""
    ABERTOS.append(Path(caminho))
    return True


@pytest.fixture(autouse=True)
def _config_isolada(tmp_path, monkeypatch):
    """Pasta de dados temporária (config_usuario.json), parâmetros restaurados ao fim do teste e nada
    aberto no sistema: `ABERTOS` começa vazia e recebe o que o código novo pedir para abrir."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    ABERTOS.clear()
    try:
        from cofre.qt import vm_figuras
    except Exception:  # noqa: BLE001  (módulo ainda ausente ou quebrado: ninguém consegue chamá-lo)
        vm_figuras = None
    if vm_figuras is not None:
        monkeypatch.setattr(vm_figuras, "abrir_no_sistema", _registrar_abertura, raising=False)
    antes = parametros.valores_atuais()
    yield
    parametros.aplicar(antes)


# ---------------------------------------------------------------------------- pastas e banco
def usar_pastas(monkeypatch, raiz) -> dict:
    """Aponta as cinco variáveis de pasta de `config` para `raiz` (as de `base_demo.pastas`); o pytest
    restaura tudo ao fim do teste. Devolve o dicionário de pastas."""
    from cofre import base_demo
    pastas = base_demo.pastas(Path(raiz))
    for nome, valor in pastas.items():
        monkeypatch.setattr(config, nome, valor)
    return pastas


def _banco_temporario(caminho_db) -> Path:
    """Caminho do banco de teste; recusa o banco real do projeto."""
    from cofre import base_demo
    caminho = Path(caminho_db)
    if caminho.resolve() == base_demo.BANCO_REAL:
        raise ValueError("Os testes nunca tocam no banco real (data/cofre.db).")
    return caminho


def contexto(qapp, tmp_path, pipeline, imagens=None) -> Contexto:
    """Aplicativo completo com o banco em `tmp_path / "t.db"`; sem `imagens` a câmera se comporta como ausente."""
    return criar_contexto(qapp, tmp_path / "t.db", pipeline=pipeline, imagens=imagens)


def cadastrar(ctx, nome: str, matricula: str, nivel: int, fotos: list) -> Usuario:
    """Cadastra pelo caminho normal do núcleo e avisa o aplicativo de que o banco mudou."""
    dados = DadosCadastro(nome, matricula, "", nivel)
    usuario, n, _ = cadastrar_de_imagens(ctx.apl.banco, ctx.apl.pipeline, dados, fotos)
    assert n == len(fotos)
    ctx.apl.banco_alterado()
    return usuario


def semear_acessos(caminho_db, linhas: list[dict]) -> None:
    """Grava linhas no registro de um banco TEMPORÁRIO, na ordem dada, com a hora que o teste quiser.

    Cada dicionário traz `data_hora` e `resultado` e, se precisar, `usuario_id`, `nome_detectado`,
    `nivel_usuario`, `nivel_exigido` (3 quando ausente), `similaridade`, `mensagem` e `evidencia`.
    Os valores não são conferidos: o teste pode semear de propósito uma linha que o terminal nunca gravaria."""
    caminho = _banco_temporario(caminho_db)
    registros = []
    for linha in linhas:
        estranhas = set(linha) - _CHAVES_ACESSO
        if estranhas:
            raise ValueError(f"Chaves desconhecidas em semear_acessos: {sorted(estranhas)}")
        nivel = linha.get("nivel_exigido", 3)
        registros.append((linha["data_hora"], linha.get("usuario_id"), linha.get("nome_detectado"),
                          linha.get("nivel_usuario"), nivel, config.AREAS.get(nivel, str(nivel)),
                          linha.get("similaridade"), linha["resultado"], linha.get("mensagem"), linha.get("evidencia")))
    if not caminho.exists():
        Banco(caminho).fechar()                          # cria o arquivo com o esquema do núcleo
    con = sqlite3.connect(str(caminho))
    try:
        con.executemany(
            """INSERT INTO acessos (data_hora, usuario_id, nome_detectado, nivel_usuario, nivel_exigido, area,
                                    similaridade, resultado, mensagem, evidencia)
               VALUES (?,?,?,?,?,?,?,?,?,?)""", registros)
        con.commit()
    finally:
        con.close()


def retrato_banco(caminho_db) -> dict:
    """SHA-256 do arquivo e contagem das três tabelas: igual antes e depois prova que nada foi gravado."""
    from cofre import leitura_ro
    caminho = _banco_temporario(caminho_db)
    retrato: dict = {"sha256": hashlib.sha256(caminho.read_bytes()).hexdigest()}
    for tabela in ("usuarios", "amostras", "acessos"):
        retrato[tabela] = int(leitura_ro.consultar(caminho, f"SELECT COUNT(*) FROM {tabela}")[0][0])
    return retrato


def retrato_parametros() -> dict:
    """Parâmetros de segurança em vigor (os mesmos da tela de Configurações)."""
    return parametros.valores_atuais()


def nomes_do_banco(caminho_db) -> list[str]:
    """Todo nome de pessoa guardado no banco de teste: os cadastrados e os que ficaram no registro."""
    from cofre import leitura_ro
    caminho = _banco_temporario(caminho_db)
    nomes = set(leitura_ro.nomes(caminho).values())
    nomes.update(linha[0] for linha in leitura_ro.consultar(
        caminho, "SELECT DISTINCT nome_detectado FROM acessos WHERE nome_detectado IS NOT NULL"))
    return sorted(nomes)


# ---------------------------------------------------------------------------- páginas, abas e trabalhos
def abrir_aba(ctx, pagina: str, aba: str, espera: float = 0.4):
    """Seleciona a aba ANTES de navegar (assim só o QML dela é carregado), gira o loop e devolve o VM da aba."""
    vm_pagina = ctx.apl.extensoes.obter(pagina)
    vm_pagina.definirAba(aba)
    assert vm_pagina.aba == aba, f"a página {pagina!r} não tem a aba {aba!r}"
    ctx.apl.navegar(pagina)
    assert ctx.apl.pagina == pagina, f"a navegação para {pagina!r} foi recusada"
    ctx.girar(espera)
    return vm_pagina.vm_aba(aba)


def esperar_ocioso(ctx, segundos: float = 15.0) -> bool:
    """Gira o loop até não haver nenhum trabalho da v2 em andamento."""
    return ctx.esperar(ctx.apl.extensoes.trabalhos.ocioso, segundos)


def esperar_estado(ctx, vm, segundos: float = 15.0) -> str:
    """Espera a aba sair de "carregando" e os trabalhos pararem; devolve o estado em que ela ficou."""
    trabalhos = ctx.apl.extensoes.trabalhos
    ctx.esperar(lambda: vm.estado != "carregando" and trabalhos.ocioso(), segundos)
    return vm.estado


def bloquear_terminal(ctx) -> None:
    """Deixa o terminal bloqueado sem gastar três negações reais (só em teste, com banco temporário).

    O terminal só existe depois da primeira visita à página dele: chame `ctx.apl.navegar("terminal")` antes."""
    terminal = ctx.apl.terminal_vm.terminal
    assert terminal is not None, 'o terminal ainda não existe: chame ctx.apl.navegar("terminal") antes'
    tentativas = terminal.tentativas
    for _ in range(tentativas.max_falhas):
        if tentativas.bloqueado:
            break
        tentativas.registrar_falha()
    assert tentativas.bloqueado


def imagem_do_provedor(ctx, chave: str) -> QImage:
    """O que `image://cofre/<chave>` entregaria ao QML (uma imagem 1x1 transparente se a chave não existe)."""
    return ctx.apl.imagens.requestImage(chave, None, None)


# ---------------------------------------------------------------------------- árvore visual do QML
def itens(janela, pred) -> list:
    """Itens da árvore VISUAL (`childItems`) que satisfazem `pred`; alcança delegates de listas,
    que `findChildren` não devolve."""
    achados, pilha = [], [janela.contentItem()]
    while pilha:
        item = pilha.pop()
        if pred(item):
            achados.append(item)
        pilha.extend(item.childItems())
    return achados


def textos_visiveis(janela) -> list[str]:
    """Textos (`text`) de todos os itens visíveis da janela; um ramo invisível é ignorado inteiro."""
    achados, pilha = [], [janela.contentItem()]
    while pilha:
        item = pilha.pop()
        if not item.isVisible():
            continue
        texto = item.property("text")
        if isinstance(texto, str) and texto:
            achados.append(texto)
        pilha.extend(item.childItems())
    return achados


def objeto_por_nome(janela, nome: str):
    """Objeto do QML com esse `objectName`, ou None."""
    return janela.findChild(QObject, nome)


def centro(item) -> QPoint:
    """Centro do item em coordenadas da janela."""
    return item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()


def tecla(ctx, key, modificadores=None, segurar_ms: int = 0) -> None:
    """Pressiona e solta uma tecla na janela, como o teclado faria; `segurar_ms` mantém a tecla apertada."""
    mods = Qt.KeyboardModifier.NoModifier if modificadores is None else modificadores
    if not ctx.janela.isActive():
        ctx.janela.requestActivate()
        ctx.girar(0.1)
    QTest.keyPress(ctx.janela, key, mods)
    if segurar_ms > 0:
        ctx.girar(segurar_ms / 1000)
    QTest.keyRelease(ctx.janela, key, mods)
    ctx.girar(0.15)


def clicar(ctx, item) -> None:
    """Clique real do mouse no centro do item."""
    QTest.mouseClick(ctx.janela, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centro(item))
    ctx.girar(0.2)


def foco_atual(ctx) -> str:
    """`objectName` do item com o foco do teclado ou, se ele não tiver nome, a classe; "" sem foco."""
    item = ctx.janela.activeFocusItem()
    if item is None:
        return ""
    return item.objectName() or item.metaObject().className()


# ---------------------------------------------------------------------------- imagens e propriedades
def cores_distintas(img: QImage, passo: int = 8) -> int:
    """Quantas cores diferentes a imagem tem, olhando um pixel a cada `passo` nas duas direções
    (uma captura lisa tem pouquíssimas)."""
    copia = img.convertToFormat(QImage.Format.Format_ARGB32)
    largura, altura = copia.width(), copia.height()
    if largura == 0 or altura == 0:
        return 0
    pixels = np.frombuffer(copia.constBits(), dtype=np.uint32).reshape(altura, copia.bytesPerLine() // 4)
    return int(np.unique(pixels[::passo, :largura:passo]).size)


def sem_vetor_128(obj) -> bool:
    """False se o objeto carrega algo com cara de vetor biométrico (a mesma regra da exportação de figuras)."""
    from cofre.qt import graficos
    try:
        graficos.conferir_sem_vetor(obj)
    except ValueError:
        return False
    return True


def props_do_vm(vm) -> dict:
    """Todas as propriedades legíveis do QObject (as que o QML enxerga), lidas pelo metaobjeto."""
    meta = vm.metaObject()
    props = {}
    for i in range(meta.propertyCount()):
        prop = meta.property(i)
        if prop.isReadable():
            props[prop.name()] = prop.read(vm)
    return props


def quadro_webcam(caminho_foto) -> np.ndarray:
    """Compõe um quadro 1280x720 (como webcam) a partir do retrato de fixture: pessoa ao centro, fundo borrado."""
    foto = cv2.imread(str(caminho_foto))
    h, w = foto.shape[:2]
    topo = foto[0:min(h, int(w * 1.25))]
    esc = 720 / topo.shape[0]
    pessoa = cv2.resize(topo, (int(topo.shape[1] * esc), 720), interpolation=cv2.INTER_AREA)
    fundo = cv2.GaussianBlur(cv2.resize(topo, (1280, 720)), (0, 0), 28)
    x0 = (1280 - pessoa.shape[1]) // 2
    fundo[:, x0:x0 + pessoa.shape[1]] = pessoa
    return fundo
