"""Testes da tela de Configurações (sem câmera real, sem interação humana)."""

import json

import pytest

from cofre import config
from cofre.interface.tela_config import ARQUIVO_CONFIG_NOME, CAMPOS, MENSAGEM_APLICADO
from tests.apoio_interface import FOTO_OBAMA, criar_app, girar


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """Arquivo de usuário em tmp e valores de config restaurados ao final do teste."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    for c in CAMPOS:
        monkeypatch.setattr(config, c.chave, getattr(config, c.chave))
    return tmp_path


@pytest.fixture
def app(ambiente):
    app = criar_app(ambiente / "t.db", imagens=[FOTO_OBAMA], esperar_pipeline=False)
    yield app
    app.fechar()


def _abrir(app):
    app.mostrar("tela_config")
    girar(app, 0.3)
    return app.tela("tela_config")


def test_formulario_reflete_config_e_aplica(app):
    tela = _abrir(app)
    assert tela.valores()["LIMIAR_COSSENO"] == pytest.approx(config.LIMIAR_COSSENO)
    assert tela.valores()["LIVENESS_ATIVO"] == config.LIVENESS_ATIVO

    tela.definir("LIMIAR_COSSENO", 0.5)
    tela.definir("FRAMES_CONFIRMACAO", 9)
    tela.definir("LIVENESS_ATIVO", False)
    assert config.LIMIAR_COSSENO != 0.5          # ainda não aplicado
    assert tela.btn_aplicar.invoke() is True
    assert config.LIMIAR_COSSENO == 0.5
    assert config.FRAMES_CONFIRMACAO == 9
    assert config.LIVENESS_ATIVO is False
    assert tela.mensagem.texto.cget("text") == MENSAGEM_APLICADO
    girar(app, 0.2)


def test_definir_limita_ao_intervalo_e_tipo(app):
    tela = _abrir(app)
    tela.definir("BLOQUEIO_SEG", 9999)
    tela.definir("CAMERA_INDEX", -3)
    tela.definir("LIMIAR_COSSENO", 0.01)
    assert tela.valores()["BLOQUEIO_SEG"] == 300
    assert tela.valores()["CAMERA_INDEX"] == 0
    assert tela.valores()["LIMIAR_COSSENO"] == 0.20
    with pytest.raises(ValueError):
        tela.definir("MIN_NITIDEZ", "alto")


def test_restaurar_padroes(app):
    tela = _abrir(app)
    original = tela.padroes["MAX_TENTATIVAS_FALHAS"]
    tela.definir("MAX_TENTATIVAS_FALHAS", 7)
    tela.aplicar()
    assert config.MAX_TENTATIVAS_FALHAS == 7
    tela.btn_restaurar.invoke()
    assert tela.valores()["MAX_TENTATIVAS_FALHAS"] == original
    assert config.MAX_TENTATIVAS_FALHAS == 7    # restaurar só muda o formulário
    tela.aplicar()
    assert config.MAX_TENTATIVAS_FALHAS == original


def test_salvar_e_carregar_arquivo(app, ambiente):
    tela = _abrir(app)
    caminho = ambiente / "data" / ARQUIVO_CONFIG_NOME
    assert tela.caminho_arquivo == caminho
    tela.definir("AMOSTRAS_POR_CADASTRO", 20)
    tela.definir("ESPELHAR_CAMERA", False)
    assert tela.btn_salvar.invoke() is True
    dados = json.loads(caminho.read_text())
    assert dados["AMOSTRAS_POR_CADASTRO"] == 20 and dados["ESPELHAR_CAMERA"] is False
    assert set(dados) == {c.chave for c in CAMPOS}

    tela.restaurar_padroes()
    assert tela.valores()["AMOSTRAS_POR_CADASTRO"] != 20
    assert tela.btn_carregar.invoke() is True
    assert tela.valores()["AMOSTRAS_POR_CADASTRO"] == 20
    assert config.AMOSTRAS_POR_CADASTRO == 20 and config.ESPELHAR_CAMERA is False


def test_carregar_arquivo_inexistente_ou_invalido(app, ambiente):
    tela = _abrir(app)
    assert tela.carregar_arquivo() is False
    assert "não encontrado" in tela.mensagem.texto.cget("text")
    caminho = ambiente / "data" / ARQUIVO_CONFIG_NOME
    caminho.parent.mkdir(parents=True)
    caminho.write_text("{isso nao é json")
    assert tela.carregar_arquivo() is False
    assert "inválido" in tela.mensagem.texto.cget("text")
    caminho.write_text(json.dumps({"LIMIAR_COSSENO": "texto"}))
    assert tela.carregar_arquivo() is False
    girar(app, 0.1)


def test_arquivo_existente_e_aplicado_ao_abrir(ambiente):
    caminho = ambiente / "data" / ARQUIVO_CONFIG_NOME
    caminho.parent.mkdir(parents=True)
    caminho.write_text(json.dumps({"LIMIAR_COSSENO": 0.45, "BLOQUEIO_SEG": 77, "CHAVE_DESCONHECIDA": 1}))
    app = criar_app(ambiente / "t.db", imagens=[FOTO_OBAMA], esperar_pipeline=False)
    try:
        tela = _abrir(app)
        assert config.LIMIAR_COSSENO == 0.45
        assert config.BLOQUEIO_SEG == 77
        assert tela.padroes["BLOQUEIO_SEG"] == 30     # padrão lido antes do arquivo
        assert tela.valores()["LIMIAR_COSSENO"] == 0.45
        assert "carregada" in tela.mensagem.texto.cget("text")
    finally:
        app.fechar()


def test_informacoes_e_tabela(app):
    tela = _abrir(app)
    nomes = dict(tela.informacoes())
    assert str(app.banco.caminho) == nomes["Banco de dados"]
    assert "128" in nomes["Dimensões dos modelos"]
    assert len(tela.tabela_niveis.tree.get_children()) == len(config.NIVEIS)
