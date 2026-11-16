"""Tela "Avaliação e demo" com câmera falsa e banco temporário (sem interação humana)."""

import time

import cv2
import numpy as np
import pytest

from cofre import config
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from tests.apoio_interface import FIX, FOTO_BIDEN, FOTO_OBAMA, FOTO_OBAMA_2, criar_app, girar


def _esperar(app, tela, seg=15):
    fim = time.time() + seg
    girar(app, 0.1)
    while tela.ocupado and time.time() < fim:
        girar(app, 0.1)
    girar(app, 0.2)  # consome a fila
    assert not tela.ocupado


@pytest.fixture
def app(tmp_path):
    a = criar_app(tmp_path / "t.db", imagens=[FOTO_OBAMA])
    cadastrar_de_imagens(a.banco, a.pipeline, DadosCadastro("Barack", "001", "Presidente", 2), [FOTO_OBAMA_2])
    a.mostrar("tela_ferramentas")
    girar(a, 0.3)
    yield a
    a.fechar()


def test_demo_identifica_e_salva_painel(app, tmp_path):
    tela = app.tela("tela_ferramentas")
    tela.nivel_demo.set("Nível 2")
    tela.demonstrar(FOTO_OBAMA)
    _esperar(app, tela)
    assert tela.ultimo_demo is not None and tela.ultimo_demo.principal is not None
    texto = tela.texto_demo.get("1.0", "end")
    assert "identificado: Barack" in texto and "CONCEDIDO" in texto
    # trocar o nível refaz só a fase 5
    tela.nivel_demo.set("Nível 3")
    tela._nivel_demo_alterado()
    assert "NEGADO_NIVEL" in tela.texto_demo.get("1.0", "end")
    destino = tela.salvar_painel()
    assert destino is not None and destino.exists() and destino.parent == config.RELATORIOS_DIR
    assert cv2.imread(str(destino)) is not None


def test_demo_sem_rosto(app, tmp_path):
    tela = app.tela("tela_ferramentas")
    sem_rosto = tmp_path / "cinza.jpg"
    cv2.imwrite(str(sem_rosto), np.full((300, 400, 3), 120, np.uint8))
    tela.demonstrar(sem_rosto)
    _esperar(app, tela)
    assert tela.ultimo_demo.principal is None
    assert "nenhum rosto" in tela.texto_demo.get("1.0", "end")
    assert "Nenhum rosto" in tela.faixa_demo.texto.cget("text")


def test_demo_arquivo_invalido(app, tmp_path):
    tela = app.tela("tela_ferramentas")
    tela.demonstrar(tmp_path / "nao_existe.jpg")
    _esperar(app, tela)
    assert "Falha" in tela.faixa_demo.texto.cget("text")
    assert tela.salvar_painel() is None


def test_autenticar_por_imagem_registra_log(app):
    tela = app.tela("tela_ferramentas")
    tela.nivel_auth.set("Nível 2")
    d = tela.autenticar(FOTO_OBAMA)
    assert d.concedido and tela.ultima_decisao is d
    tela.nivel_auth.set("Nível 3")
    d2 = tela.autenticar(FOTO_OBAMA)
    assert d2.resultado.value == "NEGADO_NIVEL"
    d3 = tela.autenticar(FOTO_BIDEN)
    assert d3.resultado.value == "NEGADO_DESCONHECIDO"
    acessos = app.banco.listar_acessos()
    assert sorted(a.resultado for a in acessos) == ["CONCEDIDO", "NEGADO_DESCONHECIDO", "NEGADO_NIVEL"]
    assert tela.cartao_auth_usuario.valor.cget("text") == "Desconhecido"
    assert tela.cartao_auth_rostos.valor.cget("text") == "1"


def test_avaliar_fotos_de_teste(app):
    tela = app.tela("tela_ferramentas")
    tela.bt_aval_teste.invoke()
    assert tela.pasta_avaliacao == FIX
    tela.bt_avaliar.invoke()
    assert tela.lbl_aval_status.cget("text") == "Avaliando..."
    _esperar(app, tela, 60)
    r = tela.ultima_avaliacao
    assert r is not None and len(r.genuinos) == 2 and len(r.impostores) == 4
    assert "Pessoas: 2" in tela.texto_aval.get("1.0", "end")
    assert len(tela.tabela_varredura.tree.get_children()) == 11
    assert tela.cartao_tar.valor.cget("text").endswith("%")
    assert tela.lbl_aval_status.cget("text") == "" and tela.bt_avaliar.cget("state") == "normal"


def test_avaliar_pasta_vazia_e_sem_rosto(app, tmp_path):
    tela = app.tela("tela_ferramentas")
    tela.avaliar(tmp_path / "vazia")
    assert "não encontrada" in tela.faixa_aval.texto.cget("text")
    (tmp_path / "plana").mkdir()
    tela.avaliar(tmp_path / "plana")
    assert "subpasta" in tela.faixa_aval.texto.cget("text")
    pessoa = tmp_path / "conj" / "ninguem"
    pessoa.mkdir(parents=True)
    cv2.imwrite(str(pessoa / "a.jpg"), np.full((200, 200, 3), 90, np.uint8))
    tela.avaliar(tmp_path / "conj")
    _esperar(app, tela, 30)
    assert tela.ultima_avaliacao is not None and tela.ultima_avaliacao.sem_rosto
    assert "Nenhum par" in tela.faixa_aval.texto.cget("text")
    assert tela.cartao_tar.valor.cget("text") == "-"
