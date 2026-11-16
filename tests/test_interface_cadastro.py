"""Tela de cadastro biométrico com câmera falsa (sem webcam, sem interação humana)."""
import time

import pytest

from cofre import config
from cofre.fase1_aquisicao import ErroAquisicao
from tests.apoio_interface import FOTO_BIDEN, FOTO_OBAMA, FOTO_OBAMA_2, criar_app, girar


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INTERVALO_AMOSTRAS_SEG", 0.05)  # 12 amostras em ~1 s
    a = criar_app(tmp_path / "t.db", imagens=[FOTO_OBAMA, FOTO_OBAMA_2])
    a.mostrar("tela_cadastro")
    yield a
    a.fechar()


def _esperar(app, condicao, seg=10.0):
    fim = time.time() + seg
    while time.time() < fim:
        girar(app, 0.1)
        if condicao():
            return True
    return False


def test_validacao_do_formulario(app):
    tela = app.tela("tela_cadastro")
    assert tela.iniciar_captura() is False
    assert "nome" in tela.rotulo_erro.cget("text").lower()
    tela.preencher(nome="Fulano")
    assert tela.iniciar_captura() is False
    assert "matrícula" in tela.rotulo_erro.cget("text").lower()
    app.banco.criar_usuario("Outro", "123", "Cargo", 1)
    tela.preencher(nome="Fulano", matricula="123")
    assert tela.iniciar_captura() is False
    assert "já cadastrada" in tela.rotulo_erro.cget("text")
    assert not tela.capturando and not app.camera.ativo


def test_captura_pela_camera_ate_concluir(app):
    tela = app.tela("tela_cadastro")
    tela.preencher(nome="Barack Obama", matricula="001", cargo="Ministro", nivel=3)
    assert tela.iniciar_captura() is True
    assert tela.capturando
    assert tela.entrada_nome.cget("state") == "disabled"
    assert _esperar(app, lambda: tela.sessao is not None and tela.sessao.concluida, 15)
    assert app.camera.ativo
    assert tela.rotulo_amostras.cget("text") == f"Amostras {config.AMOSTRAS_POR_CADASTRO}/{config.AMOSTRAS_POR_CADASTRO}"
    assert len(tela._miniaturas_widgets) == config.AMOSTRAS_POR_CADASTRO
    assert tela.botao_concluir.cget("state") == "normal"
    tela.botao_concluir.invoke()
    girar(app, 0.3)
    u = app.banco.obter_por_matricula("001")
    assert u is not None and u.nivel == 3
    assert app.banco.contar_amostras(u.id) == config.AMOSTRAS_POR_CADASTRO
    assert not tela.capturando and not app.camera.ativo
    assert tela.entrada_nome.get() == "" and tela.entrada_nome.cget("state") == "normal"
    assert "Barack Obama" in tela.rotulo_msg.cget("text")


def test_cancelar_desfaz_o_cadastro(app):
    tela = app.tela("tela_cadastro")
    tela.preencher(nome="Joe Biden", matricula="002", nivel=2)
    tela.botao_iniciar.invoke()
    assert _esperar(app, lambda: tela.sessao is not None and tela.sessao.capturadas >= 2, 10)
    tela.botao_cancelar.invoke()
    girar(app, 0.3)
    assert app.banco.obter_por_matricula("002") is None
    assert not tela.capturando and not app.camera.ativo
    assert tela.entrada_nome.cget("state") == "normal"


def test_trocar_de_tela_desliga_e_religa_a_camera(app):
    tela = app.tela("tela_cadastro")
    tela.preencher(nome="Joe Biden", matricula="002", nivel=2)
    tela.iniciar_captura()
    assert _esperar(app, lambda: app.camera.ativo, 10)
    app.mostrar("tela_usuarios")
    girar(app, 0.3)
    assert not app.camera.ativo and tela.capturando
    app.mostrar("tela_cadastro")
    assert _esperar(app, lambda: app.camera.ativo, 10)
    tela.cancelar()


def test_cadastrar_por_fotos(app):
    tela = app.tela("tela_cadastro")
    tela.preencher(nome="Joe Biden", matricula="002", cargo="Diretor", nivel=2)
    assert tela.cadastrar_por_fotos([str(FOTO_BIDEN), str(FOTO_OBAMA)]) is True
    assert tela.entrada_nome.cget("state") == "disabled"
    assert _esperar(app, lambda: not tela.importando_fotos and tela.entrada_nome.cget("state") == "normal", 20)
    u = app.banco.obter_por_matricula("002")
    assert u is not None and app.banco.contar_amostras(u.id) == 2
    assert "Joe Biden" in tela.rotulo_msg.cget("text")

    # mesma matrícula de novo: validação barra antes de abrir a thread
    tela.preencher(nome="Joe Biden", matricula="002")
    assert tela.cadastrar_por_fotos([str(FOTO_BIDEN)]) is False
    assert "já cadastrada" in tela.rotulo_erro.cget("text")


def test_cadastrar_por_fotos_sem_rosto_mostra_erro(app, tmp_path):
    import cv2
    import numpy as np
    vazia = tmp_path / "vazia.jpg"
    cv2.imwrite(str(vazia), np.full((300, 300, 3), 120, np.uint8))
    tela = app.tela("tela_cadastro")
    tela.preencher(nome="Ninguém", matricula="999")
    assert tela.cadastrar_por_fotos([str(vazia)]) is True
    assert _esperar(app, lambda: tela.rotulo_erro.cget("text") != "", 20)
    assert "falhou" in tela.rotulo_erro.cget("text")
    assert app.banco.obter_por_matricula("999") is None


class _FonteQueFalha:
    fps_medido = 0.0

    def __enter__(self):
        raise ErroAquisicao("Câmera não encontrada (teste)")

    def __exit__(self, *exc):
        return False

    def frames(self):
        yield from ()


def test_camera_indisponivel_mostra_tentar_novamente(app):
    tela = app.tela("tela_cadastro")
    app.camera.fonte_fabrica = _FonteQueFalha
    tela.preencher(nome="Fulano", matricula="010")
    tela.iniciar_captura()
    assert _esperar(app, lambda: tela.botao_tentar.winfo_ismapped(), 10)
    assert "Câmera indisponível" in tela.video.cget("text")
    # a câmera volta a funcionar: Tentar novamente retoma a mesma sessão
    from tests.apoio_interface import FonteFalsa
    app.camera.fonte_fabrica = lambda: FonteFalsa([FOTO_OBAMA])
    tela.botao_tentar.invoke()
    assert _esperar(app, lambda: tela.sessao is not None and tela.sessao.capturadas >= 1, 10)
    assert not tela.botao_tentar.winfo_ismapped()
    tela.cancelar()
    assert app.banco.obter_por_matricula("010") is None
