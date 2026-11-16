"""Tela "Acessos e relatórios" do aplicativo desktop, com banco temporário e câmera falsa."""
import time

import numpy as np
import pytest

from cofre.interface import tela_acessos
from tests.apoio_interface import FOTO_OBAMA, criar_app, girar


def _popular(banco, tmp_path):
    import cv2
    u = banco.criar_usuario("Obama", "001", "Ministro", 3)
    banco.adicionar_amostra(u.id, np.zeros(128, dtype=np.float32), None)
    ev = tmp_path / "ev" / "neg.jpg"
    ev.parent.mkdir(parents=True)
    cv2.imwrite(str(ev), np.full((1200, 900, 3), 90, dtype=np.uint8))
    banco.registrar_acesso(usuario_id=u.id, nome_detectado="Obama", nivel_usuario=3, nivel_exigido=3,
                           similaridade=0.71, resultado="CONCEDIDO", mensagem="ok")
    banco.registrar_acesso(usuario_id=u.id, nome_detectado="Obama", nivel_usuario=3, nivel_exigido=1,
                           similaridade=0.65, resultado="CONCEDIDO")
    banco.registrar_acesso(usuario_id=None, nome_detectado="DESCONHECIDO", nivel_usuario=None, nivel_exigido=2,
                           similaridade=0.21, resultado="NEGADO_DESCONHECIDO", mensagem="sem match",
                           evidencia=str(ev))
    banco.registrar_acesso(usuario_id=None, nome_detectado="Biden", nivel_usuario=2, nivel_exigido=3,
                           similaridade=0.55, resultado="NEGADO_NIVEL")
    return ev


@pytest.fixture
def app(tmp_path):
    a = criar_app(tmp_path / "t.db", imagens=[FOTO_OBAMA])
    _popular(a.banco, tmp_path)
    yield a
    a.fechar()


def _esperar(app, cond, seg=10.0):
    fim = time.time() + seg
    while time.time() < fim:
        girar(app, 0.05)
        if cond():
            return True
    return False


def test_cartoes_tabela_e_resumos(app):
    app.mostrar("tela_acessos")
    girar(app, 0.5)
    t = app.tela("tela_acessos")
    assert t.cartoes["total"].valor.cget("text") == "4"
    assert t.cartoes["CONCEDIDO"].valor.cget("text") == "2"
    assert t.cartoes["negados"].valor.cget("text") == "2"
    assert t.cartoes["NEGADO_NIVEL"].valor.cget("text") == "1"
    assert t.cartoes["usuarios"].valor.cget("text") == "1"
    assert t.cartoes["amostras"].valor.cget("text") == "1"
    assert len(t.tabela.tree.get_children()) == 4
    # banco.estatisticas() agrupa por u.nome (alias ignorado pelo SQLite): não cadastrados viram um grupo só
    assert len(t.tabela_pessoas.tree.get_children()) >= 2
    assert len(t.tabela_dias.tree.get_children()) == 1
    iid = t.tabela.tree.get_children()[0]
    assert t.tabela.tree.item(iid, "values")[6] in tema_rotulos()


def tema_rotulos():
    from cofre.interface import tema
    return set(tema.ROTULO_RESULTADO.values())


def test_filtros_resultado_e_busca(app):
    app.mostrar("tela_acessos")
    girar(app, 0.3)
    t = app.tela("tela_acessos")
    t.var_resultado.set("Negado: nível insuficiente")
    t.recarregar()
    assert len(t.tabela.tree.get_children()) == 1
    t.var_resultado.set("Todos")
    t.var_busca.set("oba")
    t._agendar_busca()
    assert _esperar(app, lambda: len(t.tabela.tree.get_children()) == 2, 3)
    t.var_busca.set("")
    t.var_limite.set("50")
    t.recarregar()
    assert len(t.tabela.tree.get_children()) == 4


def test_detalhe_com_evidencia(app):
    app.mostrar("tela_acessos")
    girar(app, 0.3)
    t = app.tela("tela_acessos")
    com_ev = next(iid for iid, a in t._acessos.items() if a.evidencia)
    t._abrir_detalhe(com_ev)
    girar(app, 0.3)
    assert t._detalhe is not None and t._detalhe.winfo_exists()
    img = t._detalhe._imagem_evidencia
    w, h = img.cget("size")
    assert w <= 800 and h <= 600
    sem_ev = next(iid for iid, a in t._acessos.items() if not a.evidencia)
    t._abrir_detalhe(sem_ev)  # substitui a janela anterior sem erro
    girar(app, 0.2)
    assert not hasattr(t._detalhe, "_imagem_evidencia")
    app.mostrar("tela_usuarios")  # ao_esconder fecha o detalhe
    assert t._detalhe is None


def test_exportar_csv_e_html_em_thread(app, monkeypatch, tmp_path):
    abertos = []
    monkeypatch.setattr(tela_acessos, "_abrir_no_sistema", lambda c: abertos.append(c))
    monkeypatch.setattr(tela_acessos.webbrowser, "open", lambda u: abertos.append(u))
    app.mostrar("tela_acessos")
    girar(app, 0.3)
    t = app.tela("tela_acessos")
    t.btn_csv.invoke()
    assert _esperar(app, lambda: t._ultimo_exportado is not None and t._ultimo_exportado.suffix == ".csv")
    csv = t._ultimo_exportado
    assert csv.exists() and csv.parent == tmp_path / "relatorios"
    assert "NEGADO_DESCONHECIDO" in csv.read_text(encoding="utf-8")
    t.btn_abrir.invoke()
    assert abertos[-1] == csv.resolve()
    t.btn_html.invoke()
    assert _esperar(app, lambda: t._ultimo_exportado is not None and t._ultimo_exportado.suffix == ".html")
    assert t._ultimo_exportado.exists()
    t.btn_abrir.invoke()
    assert str(abertos[-1]).startswith("file://")
    t.btn_evidencias.invoke()
    assert abertos[-1] == (tmp_path / "evidencias").resolve()
    assert t.btn_csv.cget("state") == "normal"
