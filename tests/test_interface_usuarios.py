"""Tela "Usuários" do aplicativo desktop, exercitada sem webcam e sem interação humana."""
from tkinter import messagebox

import pytest

from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from tests.apoio_interface import FOTO_OBAMA, criar_app, girar


@pytest.fixture
def app(tmp_path, fotos):
    app = criar_app(tmp_path / "t.db", imagens=[FOTO_OBAMA])
    cadastrar_de_imagens(app.banco, app.pipeline, DadosCadastro("Barack Obama", "001", "Ministro", 3), fotos["obama"])
    cadastrar_de_imagens(app.banco, app.pipeline, DadosCadastro("Joe Biden", "002", "Diretor", 2), fotos["biden"][:1])
    app.mostrar("tela_usuarios")
    girar(app, 0.3)
    yield app
    app.fechar()


def _tela(app):
    return app.tela("tela_usuarios")


def _selecionar(app, iid: str):
    t = _tela(app)
    t.tabela.tree.selection_set(iid)
    t.tabela.tree.event_generate("<<TreeviewSelect>>")
    girar(app, 0.1)
    return t


def _linhas(t):
    return [t.tabela.tree.item(i, "values") for i in t.tabela.tree.get_children()]


def test_tabela_e_cartoes(app):
    t = _tela(app)
    linhas = _linhas(t)
    assert len(linhas) == 2
    por_nome = {l[1]: l for l in linhas}
    assert por_nome["Barack Obama"][4] == "3 - Ministro do Meio Ambiente"
    assert int(por_nome["Barack Obama"][5]) == 2 and int(por_nome["Joe Biden"][5]) == 1
    assert t.cartao_total.valor.cget("text") == "2" and t.cartao_ativos.valor.cget("text") == "2"
    assert t.cartoes_nivel[3].valor.cget("text") == "1" and t.cartoes_nivel[1].valor.cget("text") == "0"
    # sem seleção os botões de ação ficam desabilitados
    assert all(b.cget("state") == "disabled" for b in (t.btn_nivel, t.btn_ativo, t.btn_fotos, t.btn_remover))


def test_busca_filtra_por_nome_e_matricula(app):
    t = _tela(app)
    t.busca_var.set("biden")
    girar(app, 0.1)
    assert [l[1] for l in _linhas(t)] == ["Joe Biden"]
    t.busca_var.set("001")
    girar(app, 0.1)
    assert [l[1] for l in _linhas(t)] == ["Barack Obama"]
    t.busca_var.set("")
    girar(app, 0.1)
    assert len(_linhas(t)) == 2


def test_alterar_nivel_ativar_desativar(app):
    t = _selecionar(app, "2")  # Biden
    assert t.btn_nivel.cget("state") == "normal"
    t.alterar_nivel(1)
    girar(app, 0.1)
    assert app.banco.obter_usuario(2).nivel == 1
    assert t.tabela.tree.item("2", "values")[4].startswith("1 -")
    assert t.cartoes_nivel[1].valor.cget("text") == "1"
    assert t.tabela.selecionado() == "2"  # seleção mantida após recarregar
    t.btn_ativo.invoke()
    girar(app, 0.1)
    assert app.banco.obter_usuario(2).ativo is False
    assert "inativo" in t.tabela.tree.item("2", "tags")
    assert t.cartao_ativos.valor.cget("text") == "1"
    t.btn_ativo.invoke()
    girar(app, 0.1)
    assert app.banco.obter_usuario(2).ativo is True


def test_dialogo_de_nivel_abre_e_fecha(app):
    t = _selecionar(app, "1")
    t.btn_nivel.invoke()
    girar(app, 0.2)
    assert t._janela_nivel is not None and t._janela_nivel.winfo_exists()
    t._fechar_janela_nivel()
    girar(app, 0.1)
    assert t._janela_nivel is None


def test_ver_fotos_abre_toplevel_com_miniaturas(app):
    t = _selecionar(app, "1")  # Obama, 2 fotos
    t.btn_fotos.invoke()
    girar(app, 0.3)
    jan = t._janela_fotos
    assert jan is not None and jan.winfo_exists()
    assert len(jan.miniaturas) == 2
    app.mostrar("tela_acessos")  # trocar de tela fecha a janela auxiliar
    girar(app, 0.1)
    assert t._janela_fotos is None


def test_remover_pede_confirmacao(app, monkeypatch):
    t = _selecionar(app, "2")
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
    t.btn_remover.invoke()
    girar(app, 0.1)
    assert app.banco.obter_usuario(2) is not None
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    t.btn_remover.invoke()
    girar(app, 0.1)
    assert app.banco.obter_usuario(2) is None
    assert len(_linhas(t)) == 1 and t.cartao_total.valor.cget("text") == "1"
    assert t.btn_remover.cget("state") == "disabled"


def test_avisa_terminal_e_novo_cadastro(app):
    chamadas = []
    app.mostrar("tela_terminal")
    app.tela("tela_terminal").recarregar_galeria = lambda: chamadas.append(1)
    app.mostrar("tela_usuarios")
    t = _selecionar(app, "1")
    t.alterar_nivel(2)
    assert chamadas == [1]
    t.btn_novo.invoke()
    girar(app, 0.1)
    assert app._atual == "tela_cadastro"
