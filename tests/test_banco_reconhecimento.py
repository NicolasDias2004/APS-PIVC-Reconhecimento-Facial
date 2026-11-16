"""Banco, identificação 1:N, decisão por nível, relatórios e avaliação."""
import numpy as np
import pytest

from cofre import config, relatorios
from cofre.avaliacao import avaliar_pasta
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from cofre.fase1_aquisicao import carregar_imagem
from cofre.fase5_reconhecimento import Identificacao, Reconhecedor, Resultado, decidir_acesso
from tests.conftest import FIX


def test_crud_usuario_e_amostras(banco):
    u = banco.criar_usuario("Ana", "M001", "Diretora", 2)
    assert u.nivel == 2 and u.ativo
    banco.adicionar_amostra(u.id, np.ones(128, np.float32))
    assert banco.contar_amostras(u.id) == 1
    assert banco.embeddings_do_usuario(u.id)[0].shape == (128,)
    banco.alterar_nivel(u.id, 3)
    assert banco.obter_usuario(u.id).nivel == 3
    banco.definir_ativo(u.id, False)
    assert banco.listar_usuarios(apenas_ativos=True) == []
    banco.remover_usuario(u.id)
    assert banco.obter_usuario(u.id) is None
    assert banco.contar_amostras(u.id) == 0  # cascade


def test_matricula_unica_e_nivel_invalido(banco):
    banco.criar_usuario("A", "X1", "", 1)
    with pytest.raises(Exception):
        banco.criar_usuario("B", "X1", "", 1)
    with pytest.raises(ValueError):
        banco.criar_usuario("C", "X2", "", 4)


def _ident(nivel):
    from cofre.banco import Usuario
    u = Usuario(1, "Fulano", "m", "c", nivel, True, "")
    return Identificacao(u, 0.8)


@pytest.mark.parametrize("nivel_usuario,nivel_exigido,esperado", [
    (1, 1, Resultado.CONCEDIDO), (1, 2, Resultado.NEGADO_NIVEL), (1, 3, Resultado.NEGADO_NIVEL),
    (2, 1, Resultado.CONCEDIDO), (2, 2, Resultado.CONCEDIDO), (2, 3, Resultado.NEGADO_NIVEL),
    (3, 1, Resultado.CONCEDIDO), (3, 2, Resultado.CONCEDIDO), (3, 3, Resultado.CONCEDIDO),
])
def test_esquema_de_permissoes(nivel_usuario, nivel_exigido, esperado):
    assert decidir_acesso(_ident(nivel_usuario), nivel_exigido).resultado is esperado


def test_desconhecido_negado():
    assert decidir_acesso(Identificacao(None, 0.1), 1).resultado is Resultado.NEGADO_DESCONHECIDO
    assert decidir_acesso(None, 1).resultado is Resultado.NEGADO_DESCONHECIDO


def test_identificacao_1_para_n_com_fotos_reais(banco, pipeline, fotos):
    # cadastra cada pessoa com UMA foto e consulta com a OUTRA
    ob, _, _ = cadastrar_de_imagens(banco, pipeline, DadosCadastro("Obama", "001", "Ministro", 3), [fotos["obama"][0]])
    bi, _, _ = cadastrar_de_imagens(banco, pipeline, DadosCadastro("Biden", "002", "Diretor", 2), [fotos["biden"][0]])
    rec = Reconhecedor(banco)
    assert rec.total_amostras == 2
    q_ob = pipeline.processar(carregar_imagem(fotos["obama"][1])).principal.embedding
    q_bi = pipeline.processar(carregar_imagem(fotos["biden"][1])).principal.embedding
    i1, i2 = rec.identificar(q_ob), rec.identificar(q_bi)
    assert i1.reconhecido and i1.usuario.id == ob.id
    assert i2.reconhecido and i2.usuario.id == bi.id
    assert decidir_acesso(i1, 3).concedido
    assert decidir_acesso(i2, 3).resultado is Resultado.NEGADO_NIVEL
    assert decidir_acesso(i2, 2).concedido
    # usuário desativado some da galeria
    banco.definir_ativo(bi.id, False)
    rec.recarregar()
    assert not rec.identificar(q_bi).reconhecido


def test_galeria_vazia(banco):
    assert not Reconhecedor(banco).identificar(np.ones(128, np.float32)).reconhecido


def test_autenticar_imagem_registra_log_e_evidencia(banco, pipeline, fotos, tmp_path, monkeypatch):
    from cofre.autenticacao import autenticar_imagem
    monkeypatch.setattr(config, "EVIDENCIAS_DIR", tmp_path / "ev")
    cadastrar_de_imagens(banco, pipeline, DadosCadastro("Obama", "001", "Ministro", 3), [fotos["obama"][0]])
    d1, _ = autenticar_imagem(banco, pipeline, carregar_imagem(fotos["obama"][1]), 3)
    d2, _ = autenticar_imagem(banco, pipeline, carregar_imagem(fotos["biden"][0]), 1)
    assert d1.concedido and d2.resultado is Resultado.NEGADO_DESCONHECIDO
    acessos = banco.listar_acessos()
    assert [a.resultado for a in acessos] == ["NEGADO_DESCONHECIDO", "CONCEDIDO"]
    assert acessos[0].evidencia and (tmp_path / "ev").exists()
    e = banco.estatisticas()
    assert e["total"] == 2 and e["por_resultado"]["CONCEDIDO"] == 1


def test_relatorios_exportam(banco, tmp_path):
    u = banco.criar_usuario("Ana", "M1", "Dir", 2)
    banco.registrar_acesso(usuario_id=u.id, nome_detectado="Ana", nivel_usuario=2, nivel_exigido=3,
                           similaridade=0.7, resultado="NEGADO_NIVEL", mensagem="x")
    assert "Ana" in relatorios.texto_usuarios(banco)
    assert "nível insuficiente" in relatorios.texto_acessos(banco)
    csv_p = relatorios.exportar_csv(banco, tmp_path / "a.csv")
    html_p = relatorios.exportar_html(banco, tmp_path / "a.html")
    assert "NEGADO_NIVEL" in csv_p.read_text(encoding="utf-8")
    assert "<table" in html_p.read_text(encoding="utf-8") and "Ana" in html_p.read_text(encoding="utf-8")


def test_avaliacao_em_pasta_rotulada(pipeline):
    r = avaliar_pasta(FIX, pipeline)
    assert r.pessoas == {"biden": 2, "obama": 2}
    assert len(r.genuinos) == 2 and len(r.impostores) == 4
    t = r.taxas(config.LIMIAR_COSSENO)
    assert t["TAR"] == 1.0 and t["FAR"] == 0.0
    assert "EER" in r.resumo()
