"""Tela "Terminal de acesso" com câmera falsa: concessão, negação por nível, controles e erro de câmera."""
import time
import types

import pytest

from cofre import config
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from cofre.fase1_aquisicao import ErroAquisicao
from tests.apoio_interface import FOTO_BIDEN, FOTO_BIDEN_2, FOTO_OBAMA, FOTO_OBAMA_2, FonteFalsa, criar_app, girar


class FonteQuebrada:
    """Simula câmera sem permissão / sem dispositivo."""

    def __enter__(self):
        raise ErroAquisicao("Não foi possível abrir a câmera (teste)")

    def __exit__(self, *exc):
        return False


def _esperar(app, cond, seg=15.0):
    fim = time.time() + seg
    while time.time() < fim and not cond():
        girar(app, 0.1)
    return cond()


def _esperar_decisao(app, tela, seg=15.0):
    _esperar(app, lambda: not tela.status.get("decisao"), seg)   # deixa expirar um RESULTADO anterior
    assert _esperar(app, lambda: bool(tela.status.get("decisao")), seg), tela.status
    return tela.status["decisao"]


@pytest.fixture
def app(tmp_path):
    a = criar_app(tmp_path / "t.db", imagens=[FOTO_OBAMA])
    yield a
    a.fechar()


def test_terminal_concede_e_nega_por_nivel(app, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 1.0)
    tela = app.tela("tela_terminal")
    assert type(tela).__name__ == "TelaTerminal"
    girar(app, 0.5)
    assert tela.aviso.winfo_manager() == "grid"            # sem usuários ativos: aviso em amarelo
    assert app.camera.ativo and tela.terminal is not None
    cadastrar_de_imagens(app.banco, app.pipeline, DadosCadastro("Obama", "001", "Presidente", 2), [FOTO_OBAMA_2])
    tela.botao_recarregar.invoke()
    assert tela.aviso.winfo_manager() == ""
    assert tela.cartao_galeria.valor.cget("text") == "1"
    tela.alternar_liveness(False)
    tela.definir_nivel(2)
    d = _esperar_decisao(app, tela)
    assert d["concedido"] and d["nome"] == "Obama" and d["similaridade"] >= config.LIMIAR_COSSENO
    assert tela.faixa.cget("fg_color") == "#2ecc71"
    assert "Obama" in tela.faixa.texto.cget("text")
    assert "acima" in tela.rotulo_similaridade.cget("text")
    assert app.banco.listar_acessos(1)[0].resultado == "CONCEDIDO"
    assert len(tela.tabela.tree.get_children()) >= 1
    # nível 3 exigido: Obama (nível 2) é negado por nível -> faixa laranja
    tela.definir_nivel(3)
    assert tela.seletor_nivel.get() == "3 Cofre do Ministro" and tela.terminal.nivel_exigido == 3
    d = _esperar_decisao(app, tela)
    assert d["resultado"] == "NEGADO_NIVEL"
    assert tela.faixa.cget("fg_color") == "#f39c12"
    assert app.banco.listar_acessos(1)[0].resultado == "NEGADO_NIVEL"


def test_cadastro_feito_em_outra_janela_entra_sem_recarregar(app, tmp_path):
    """Outra janela (outro processo) grava no mesmo banco: o terminal percebe e recarrega."""
    from cofre.banco import Banco
    tela = app.tela("tela_terminal")
    girar(app, 1.5)
    assert tela.terminal is not None and tela.terminal.reconhecedor.total_amostras == 0
    outra = Banco(app.banco.caminho)                     # conexão separada, como a de outra janela
    try:
        cadastrar_de_imagens(outra, app.pipeline, DadosCadastro("Obama", "001", "Presidente", 2), [FOTO_OBAMA_2])
    finally:
        outra.fechar()
    assert _esperar(app, lambda: tela.terminal.reconhecedor.total_amostras == 1, 5.0)
    assert tela.cartao_galeria.valor.cget("text") == "1"
    assert tela.aviso.winfo_manager() == ""


def test_controles_atalhos_e_painel_didatico(app):
    tela = app.tela("tela_terminal")
    girar(app, 0.5)
    tela._tecla(types.SimpleNamespace(char="1", widget=None))
    assert tela.nivel == 1 and tela.terminal.nivel_exigido == 1 and tela.seletor_nivel.get() == "1 Área comum"
    tela.seletor_nivel.set("2 Diretores"); tela._ao_escolher_nivel("2 Diretores")
    assert tela.terminal.nivel_exigido == 2
    antes = tela.liveness
    tela._tecla(types.SimpleNamespace(char="l", widget=None))
    assert tela.liveness is (not antes) and tela.terminal.liveness_ativo is tela.liveness
    tela.chave_liveness.toggle()
    assert tela.terminal.liveness_ativo is antes
    tela.chave_didatico.toggle()
    # Espera pela condição em vez de um tempo fixo: com a máquina carregada o frame atrasa.
    assert _esperar(app, lambda: tela.didatico and tela.video_didatico.winfo_manager() == "grid"
                    and tela.video_didatico._img is not None, 5.0)
    tela._tecla(types.SimpleNamespace(char="d", widget=None))
    assert _esperar(app, lambda: not tela.didatico and tela.video_didatico.winfo_manager() == "", 3.0)
    tela._tecla(types.SimpleNamespace(char="r", widget=None))     # recarregar não pode quebrar
    assert _esperar(app, lambda: tela.video._img is not None and tela.cartao_fps.valor.cget("text") != "0", 3.0)


def test_erro_de_camera_e_tentar_novamente(app):
    tela = app.tela("tela_terminal")
    girar(app, 0.5)
    app.camera.fonte_fabrica = FonteQuebrada
    tela.botao_camera.invoke()
    assert _esperar(app, lambda: tela.botao_tentar.winfo_manager() == "place", 5.0)
    assert "Câmera indisponível" in tela.video.cget("text")
    assert tela.faixa.cget("fg_color") == "#e74c3c"
    app.camera.fonte_fabrica = lambda: FonteFalsa([FOTO_BIDEN])
    tela.botao_tentar.invoke()
    assert _esperar(app, lambda: app.camera.ativo and tela.botao_tentar.winfo_manager() == "", 5.0)
    assert tela.status.get("estado") in {"AGUARDANDO", "CONFIRMANDO", "RESULTADO", "LIVENESS"}


def test_troca_de_tela_desliga_e_religa_camera(app):
    tela = app.tela("tela_terminal")
    girar(app, 0.5)
    assert app.camera.ativo
    app.mostrar("tela_usuarios")
    girar(app, 0.3)
    assert not app.camera.ativo
    app.mostrar("tela_terminal")
    assert _esperar(app, lambda: app.camera.ativo and tela.video._img is not None, 5.0)
