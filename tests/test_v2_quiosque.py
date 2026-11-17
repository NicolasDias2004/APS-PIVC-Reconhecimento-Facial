"""Modo porta (v2, lote L8): o quiosque e a cena de abertura só refletem o terminal e a sessão.

Câmera sempre falsa (quadros de `apoio_v2.QUADROS_OK`), banco temporário, nada de webcam.
"""

from __future__ import annotations

import dataclasses
import os

import numpy as np
from PySide6.QtCore import Qt

from cofre import config
from cofre.qt.vm_sessao import SessaoVM
from tests import apoio_v2
from tests.apoio_interface import FOTO_BIDEN, FOTO_BIDEN_2, FOTO_OBAMA, FOTO_OBAMA_2
from tests.apoio_v2 import _config_isolada  # noqa: F401

K = Qt.Key


# ---------------------------------------------------------------------------- apoio local
def _ctx(qapp, tmp_path, pipeline, fotos=None):
    """Contexto com a câmera falsa mostrando os quadros compostos das `fotos` (lista mutável devolvida)."""
    imagens = None if fotos is None else [apoio_v2.quadro_webcam(f) for f in fotos]
    return apoio_v2.contexto(qapp, tmp_path, pipeline, imagens=imagens), imagens


def _q(ctx):
    return ctx.apl.extensoes.quiosque


def _item(ctx, nome):
    achados = apoio_v2.itens(ctx.janela, lambda i: i.objectName() == nome)
    return achados[0] if achados else None


def _textos_de(item) -> list[str]:
    """Textos visíveis só dentro de `item` (o quiosque), ignorando ramos invisíveis."""
    achados, pilha = [], [item]
    while pilha:
        it = pilha.pop()
        if not it.isVisible():
            continue
        texto = it.property("text")
        if isinstance(texto, str) and texto:
            achados.append(texto)
        pilha.extend(it.childItems())
    return achados


def _entrar(ctx):
    ctx.apl.extensoes.entrarQuiosque()
    ctx.girar(0.5)
    assert _q(ctx).ativo and ctx.apl.pagina == "terminal"
    return _item(ctx, "quiosque")


def _cena_visivel(ctx) -> bool:
    cena = _item(ctx, "cenaAbertura")
    return cena is not None and cena.isVisible()


def _encerrar_com_camera_vazia(ctx, imagens):
    imagens[0] = np.zeros_like(imagens[0])          # ninguém na frente da câmera ao encerrar
    ctx.apl.sessao.encerrar()
    ctx.girar(0.3)


# ---------------------------------------------------------------------------- entrada e saída
def test_entrar_so_com_terminal_e_sem_sessao(qapp, tmp_path, pipeline, monkeypatch):
    ctx, _ = _ctx(qapp, tmp_path, pipeline)
    try:
        q = _q(ctx)
        assert not q.ativo and not q.usado and _item(ctx, "quiosque") is None   # carrega só na primeira entrada
        ctx.apl.navegar("usuarios")
        ctx.girar(0.2)
        _entrar(ctx)                                     # leva ao terminal
        assert q.usado and _item(ctx, "quiosque").isVisible()
        q.sair()
        ctx.girar(0.5)
        assert not q.ativo and q.usado
        # com a sessão aberta: nada (e a navegação fica travada)
        monkeypatch.setattr(SessaoVM, "ativa", property(lambda s: True))
        ctx.apl.navegar("usuarios")
        q.entrar()
        ctx.girar(0.2)
        assert not q.ativo
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_quiosque_nao_toca_na_camera(qapp, tmp_path, pipeline):
    ctx, _ = _ctx(qapp, tmp_path, pipeline, [FOTO_BIDEN])
    try:
        camera = ctx.apl.camera
        original = camera.ultimo
        chamadores: list[str] = []

        def contar():
            import sys
            chamadores.append(os.path.basename(sys._getframe(1).f_code.co_filename))
            return original()

        camera.ultimo = contar
        ctx.apl.terminal.definirNivel(3)
        ctx.apl.navegar("terminal")
        ctx.girar(1.5)
        sem = list(chamadores)
        chamadores.clear()
        ctx.apl.navegar("usuarios")
        ctx.girar(0.2)
        _entrar(ctx)
        ctx.girar(1.5)
        com = list(chamadores)
        assert sem and com
        assert set(sem) == set(com) == {"vm_terminal.py"}   # só o terminal lê o pacote, com ou sem o quiosque
        assert _q(ctx).fonteVideo.temImagem                  # e o quiosque mostra o quadro mesmo assim
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- teclado (T9)
def test_quiosque_engole_teclas_do_terminal(qapp, tmp_path, pipeline):
    ctx, _ = _ctx(qapp, tmp_path, pipeline)
    try:
        t = ctx.apl.terminal
        t.definirNivel(3)
        ctx.apl.navegar("terminal")
        ctx.girar(0.3)
        apoio_v2.tecla(ctx, K.Key_2)
        assert t.nivel == 2                              # controle: sem o quiosque a tecla chega
        t.definirNivel(3)
        _entrar(ctx)
        vida = t.liveness
        apoio_v2.tecla(ctx, K.Key_2)
        apoio_v2.tecla(ctx, K.Key_L)
        apoio_v2.tecla(ctx, K.Key_4, Qt.KeyboardModifier.ControlModifier)
        assert t.nivel == 3 and t.liveness == vida and ctx.apl.pagina == "terminal"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_quiosque_nao_vaza_teclas_depois_de_tab(qapp, tmp_path, pipeline):
    ctx, _ = _ctx(qapp, tmp_path, pipeline)
    try:
        t = ctx.apl.terminal
        t.definirNivel(3)
        _entrar(ctx)
        for _ in range(3):
            apoio_v2.tecla(ctx, K.Key_Tab)
        apoio_v2.tecla(ctx, K.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
        assert apoio_v2.foco_atual(ctx) == "quiosque"
        vida = t.liveness
        for k in (K.Key_L, K.Key_2, K.Key_Space):
            apoio_v2.tecla(ctx, k)
        assert t.liveness == vida and t.nivel == 3 and ctx.apl.pagina == "terminal"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_quiosque_nao_vaza_teclas_depois_de_encerrar_sessao(qapp, tmp_path, pipeline):
    ctx, imagens = _ctx(qapp, tmp_path, pipeline, [FOTO_OBAMA_2])
    try:
        apoio_v2.cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        t, s = ctx.apl.terminal, ctx.apl.sessao
        t.definirLiveness(False)
        t.definirNivel(1)
        _entrar(ctx)
        assert ctx.esperar(lambda: s.ativa, 25)
        assert ctx.esperar(lambda: not _cena_visivel(ctx), 4)
        imagens[0] = np.zeros_like(imagens[0])
        botao = [i for i in apoio_v2.itens(ctx.janela, lambda i: i.property("text") == "Encerrar sessão") if i.isVisible()]
        assert botao
        apoio_v2.clicar(ctx, botao[0])
        assert ctx.esperar(lambda: not s.ativa, 3)
        assert _q(ctx).ativo
        assert ctx.esperar(lambda: apoio_v2.foco_atual(ctx) == "quiosque", 3)
        apoio_v2.tecla(ctx, K.Key_L)
        apoio_v2.tecla(ctx, K.Key_2)
        assert t.liveness is False and t.nivel == 1 and ctx.apl.pagina == "terminal"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- verde só com a sessão
def test_desconhecido_nunca_fica_verde_nem_abre_cena(qapp, tmp_path, pipeline):
    ctx, _ = _ctx(qapp, tmp_path, pipeline, [FOTO_BIDEN])
    try:
        apoio_v2.cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        t, s = ctx.apl.terminal, ctx.apl.sessao
        t.definirLiveness(False)
        t.definirNivel(1)
        item = _entrar(ctx)
        verde = []
        item.concedidoChanged.connect(lambda: verde.append(item.property("concedido")))
        assert ctx.esperar(lambda: t.estado == "RESULTADO", 20)
        ctx.girar(0.1)
        assert t.resultadoConcedido is False and s.ativa is False
        assert not _cena_visivel(ctx)
        assert item.property("concedido") is False and item.property("negado") is True
        assert "Acesso negado" in _textos_de(item) and "Acesso autorizado" not in _textos_de(item)
        assert True not in verde
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_concedido_sem_sessao_nao_fica_verde(qapp, tmp_path, pipeline, monkeypatch):
    ctx, _ = _ctx(qapp, tmp_path, pipeline, [FOTO_OBAMA_2])
    try:
        apoio_v2.cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        banco = ctx.apl.banco
        original = banco.obter_usuario

        def desativado(uid):                             # desativado depois da carga da galeria
            u = original(uid)
            return None if u is None else dataclasses.replace(u, ativo=False)

        monkeypatch.setattr(banco, "obter_usuario", desativado)
        t, s = ctx.apl.terminal, ctx.apl.sessao
        t.definirLiveness(False)
        t.definirNivel(1)
        item = _entrar(ctx)
        assert ctx.esperar(lambda: t.estado == "RESULTADO", 20)
        ctx.girar(0.1)
        assert t.resultadoConcedido is True and s.ativa is False
        assert item.property("concedido") is False and item.property("pendente") is True
        textos = _textos_de(item)
        assert "Acesso autorizado" not in textos and "Decisão registrada" in textos
        assert not _cena_visivel(ctx)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_quiosque_negado_nao_mostra_nome(qapp, tmp_path, pipeline):
    ctx, _ = _ctx(qapp, tmp_path, pipeline, [FOTO_BIDEN_2])
    try:
        apoio_v2.cadastrar(ctx, "Joe Biden", "M2", 2, [FOTO_BIDEN])
        t = ctx.apl.terminal
        t.definirLiveness(False)
        t.definirNivel(3)
        item = _entrar(ctx)
        assert ctx.esperar(lambda: t.estado == "RESULTADO", 20)
        ctx.girar(0.1)
        assert t.resultadoTipo == "NEGADO_NIVEL"
        textos = _textos_de(item)
        assert not any("Biden" in x for x in textos)
        assert "Nível insuficiente" in textos
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- cena de abertura
def test_concedido_abre_sessao_e_toca_a_cena(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.5)
    ctx, imagens = _ctx(qapp, tmp_path, pipeline, [FOTO_OBAMA_2])
    try:
        apoio_v2.cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        t, s = ctx.apl.terminal, ctx.apl.sessao
        t.definirLiveness(False)
        t.definirNivel(1)
        _entrar(ctx)
        assert ctx.esperar(lambda: s.ativa, 25)
        cena = _item(ctx, "cenaAbertura")
        assert cena is not None and cena.isVisible() and cena.property("fase") < 1
        assert "Barack Obama" in _textos_de(cena)
        assert ctx.esperar(lambda: not cena.isVisible(), 4)
        assert s.ativa                                   # a cena acabou; a sessão segue aberta por baixo
        _encerrar_com_camera_vazia(ctx, imagens)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def _fluxo(qapp, pasta, pipeline, com_quiosque: bool) -> tuple[list[str], list[str]]:
    """Biden (nível 2) pede o nível 3 (negado) e depois o 2 (concedido). Devolve o estado do terminal no
    instante em que a sessão abre e a lista de resultados gravados, do mais antigo ao mais novo."""
    pasta.mkdir()
    ctx, imagens = _ctx(qapp, pasta, pipeline, [FOTO_BIDEN_2])
    try:
        apoio_v2.cadastrar(ctx, "Joe Biden", "M2", 2, [FOTO_BIDEN])
        t, s = ctx.apl.terminal, ctx.apl.sessao
        no_instante: list[str] = []
        ctx.apl.sessao_vm.ativaMudou.connect(lambda: no_instante.append(t.estado) if s.ativa else None)
        t.definirLiveness(False)
        t.definirNivel(3)
        if com_quiosque:
            _entrar(ctx)
        else:
            ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: t.estado == "RESULTADO", 20) and t.resultadoTipo == "NEGADO_NIVEL"
        t.definirNivel(2)
        assert ctx.esperar(lambda: s.ativa, 25)
        if com_quiosque:
            assert _cena_visivel(ctx)
        _encerrar_com_camera_vazia(ctx, imagens)
        resultados = [a.resultado for a in reversed(ctx.apl.banco.listar_acessos())]
        assert ctx.avisos_qml() == []
        return no_instante, resultados
    finally:
        ctx.fechar()


def test_sessao_abre_no_mesmo_ciclo_com_a_cena(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.5)
    sem, _ = _fluxo(qapp, tmp_path / "sem", pipeline, False)
    com, _ = _fluxo(qapp, tmp_path / "com", pipeline, True)
    assert sem == com == ["RESULTADO"]


def test_mesmo_registro_com_e_sem_quiosque(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.5)
    _, sem = _fluxo(qapp, tmp_path / "sem", pipeline, False)
    _, com = _fluxo(qapp, tmp_path / "com", pipeline, True)
    assert sem == com and sem[-1] == "CONCEDIDO" and "NEGADO_NIVEL" in sem


def test_cena_some_ao_encerrar_a_sessao(qapp, tmp_path, pipeline):
    ctx, imagens = _ctx(qapp, tmp_path, pipeline, [FOTO_OBAMA_2])
    try:
        apoio_v2.cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        t, s = ctx.apl.terminal, ctx.apl.sessao
        t.definirLiveness(False)
        t.definirNivel(1)
        ctx.apl.navegar("terminal")                     # a cena aparece com ou sem o quiosque
        assert ctx.esperar(lambda: s.ativa, 25)
        assert _cena_visivel(ctx)
        imagens[0] = np.zeros_like(imagens[0])
        s.encerrar()
        assert not s.ativa and not _cena_visivel(ctx)   # no mesmo instante
        assert _item(ctx, "cenaAbertura").property("fase") == 1
        ctx.girar(0.3)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- avisos, saída e tela cheia
def test_aviso_de_prova_de_vida_desligada(qapp, tmp_path, pipeline):
    ctx, _ = _ctx(qapp, tmp_path, pipeline)
    try:
        t = ctx.apl.terminal
        t.definirLiveness(False)
        item = _entrar(ctx)
        assert "Prova de vida desligada" in _textos_de(item)
        t.definirLiveness(True)
        ctx.girar(0.2)
        assert "Prova de vida desligada" not in _textos_de(item)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_esc_segurado_sai_e_toque_curto_nao(qapp, tmp_path, pipeline):
    ctx, _ = _ctx(qapp, tmp_path, pipeline)
    try:
        _entrar(ctx)
        apoio_v2.tecla(ctx, K.Key_Escape)
        apoio_v2.tecla(ctx, K.Key_Escape, segurar_ms=250)
        assert _q(ctx).ativo
        apoio_v2.tecla(ctx, K.Key_Escape, segurar_ms=900)
        assert not _q(ctx).ativo and ctx.apl.pagina == "terminal"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_sair_ao_trocar_de_pagina(qapp, tmp_path, pipeline):
    ctx, _ = _ctx(qapp, tmp_path, pipeline)
    try:
        _entrar(ctx)
        ctx.apl.navegar("usuarios")
        ctx.girar(0.5)
        assert not _q(ctx).ativo and not _q(ctx).fonteVideo.temImagem
        assert not _item(ctx, "quiosque").isVisible()
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_tela_cheia_e_so_de_sessao(qapp, tmp_path, pipeline):
    ctx, _ = _ctx(qapp, tmp_path, pipeline)
    try:
        antes = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
        q = _q(ctx)
        assert not q.telaCheia and not q.telaCheiaAtiva
        _entrar(ctx)
        apoio_v2.tecla(ctx, K.Key_F)
        assert q.telaCheia and q.telaCheiaAtiva and ctx.apl.extensoes.quiosqueTelaCheia
        q.sair()
        ctx.girar(0.3)
        assert q.telaCheia and not q.telaCheiaAtiva     # a preferência fica; a janela sai da tela cheia
        depois = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
        assert depois == antes                           # nada gravado em disco
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
    (tmp_path / "outra").mkdir()
    novo, _ = _ctx(qapp, tmp_path / "outra", pipeline)
    try:
        assert not _q(novo).telaCheia                    # nova sessão do aplicativo: começa desligada
    finally:
        novo.fechar()


def test_sem_avisos_no_ciclo_completo(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.5)
    ctx, imagens = _ctx(qapp, tmp_path, pipeline, [FOTO_OBAMA_2])
    try:
        apoio_v2.cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        t, s = ctx.apl.terminal, ctx.apl.sessao
        t.definirLiveness(False)
        t.definirNivel(1)
        _entrar(ctx)
        assert ctx.esperar(lambda: t.estado == "CONFIRMANDO" or s.ativa, 20)
        assert ctx.esperar(lambda: s.ativa, 25)
        assert ctx.esperar(lambda: not _cena_visivel(ctx), 4)
        _encerrar_com_camera_vazia(ctx, imagens)
        assert ctx.esperar(lambda: t.estado == "AGUARDANDO", 8)
        apoio_v2.tecla(ctx, K.Key_Escape, segurar_ms=900)
        assert not _q(ctx).ativo
        ctx.girar(0.5)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
