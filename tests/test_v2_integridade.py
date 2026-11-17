"""Técnica da aba Integridade (L2): as 13 regras e o selo encadeado de `cofre/integridade.py`."""

from __future__ import annotations

import json
import sqlite3

import pytest

from cofre import base_demo, config, integridade, leitura_ro
from cofre.banco import Banco
from tests import apoio_v2
from tests.test_v2_incidentes import conduzir_tres_negacoes

LIMIAR = 0.363


def _conferir(db, demonstracao=False):
    return {r.regra.id: r for r in integridade.conferir(db, limiar=LIMIAR, janela_seg=60.0, max_falhas=3,
                                                        demonstracao=demonstracao)}


def _ok(db):
    """Linha válida de cada tipo (o que o terminal gravaria)."""
    ev = str(db.parent / "ev" / "20261110_080100_NEGADO_DESCONHECIDO.jpg")
    apoio_v2.semear_acessos(db, [
        {"data_hora": "2026-11-10T08:00:00", "resultado": "CONCEDIDO", "usuario_id": 1, "nome_detectado": "Ana",
         "nivel_usuario": 3, "nivel_exigido": 2, "similaridade": 0.7},
        {"data_hora": "2026-11-10T08:01:00", "resultado": "NEGADO_DESCONHECIDO", "similaridade": 0.2, "evidencia": ev}])


def test_invariantes_no_fluxo_real(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.0)
    banco = Banco(tmp_path / "t.db")
    try:
        conduzir_tres_negacoes(banco)
    finally:
        banco.fechar()
    res = integridade.conferir(tmp_path / "t.db", limiar=config.LIMIAR_COSSENO, janela_seg=config.JANELA_FALHAS_SEG,
                               max_falhas=config.MAX_TENTATIVAS_FALHAS)
    assert len(res) == 13 and [r.regra.id for r in res] == [f"I{i}" for i in range(1, 14)]
    assert {r.regra.id: r.violacoes for r in res} == {f"I{i}": 0 for i in range(1, 14)}


INVALIDAS = {
    "I1": {"data_hora": "2026-11-10T09:00:00", "resultado": "CONCEDIDO", "nome_detectado": "Ana", "nivel_usuario": 1,
           "nivel_exigido": 3, "similaridade": 0.7},
    "I2": {"data_hora": "2026-11-10T09:00:00", "resultado": "CONCEDIDO", "nome_detectado": "Ana", "nivel_usuario": 3,
           "nivel_exigido": 3, "similaridade": 0.2},
    "I3": {"data_hora": "2026-11-10T09:00:00", "resultado": "CONCEDIDO", "nivel_usuario": 3, "nivel_exigido": 3,
           "similaridade": 0.7},
    "I4": {"data_hora": "2026-11-10T09:00:00", "resultado": "CONCEDIDO", "nome_detectado": "Ana", "nivel_usuario": 3,
           "nivel_exigido": 3, "similaridade": 0.7, "evidencia": "/x/20261110_090000_CONCEDIDO.jpg"},
    "I5": {"data_hora": "2026-11-10T09:00:00", "resultado": "NEGADO_MULTIPLOS"},
    "I6": {"data_hora": "2026-11-10T09:00:00", "resultado": "NEGADO_DESCONHECIDO", "similaridade": 0.5,
           "evidencia": "/x/20261110_090000_NEGADO_DESCONHECIDO.jpg"},
    "I7": {"data_hora": "2026-11-10T09:00:00", "resultado": "NEGADO_NIVEL", "nivel_usuario": 3, "nivel_exigido": 2,
           "similaridade": 0.7, "evidencia": "/x/20261110_090000_NEGADO_NIVEL.jpg"},
    "I8": {"data_hora": "2026-11-09T09:00:00", "resultado": "CONCEDIDO", "nome_detectado": "Ana", "nivel_usuario": 3,
           "nivel_exigido": 3, "similaridade": 0.7},
    "I9": {"data_hora": "2026-11-10T09:00:00", "resultado": "BLOQUEADO"},
    "I10": {"data_hora": "2026-11-10T09:00:00", "resultado": "TALVEZ"},
    "I13": {"data_hora": "2026-11-10T09:00:00", "resultado": "NEGADO_DESCONHECIDO", "similaridade": 0.1,
            "evidencia": "/x/20261110_090000_NEGADO_NIVEL.jpg"},
}


@pytest.mark.parametrize("regra", sorted(INVALIDAS) + ["I11", "I12"])
def test_cada_regra_acusa(tmp_path, regra):
    db = tmp_path / "t.db"
    _ok(db)
    assert all(r.violacoes == 0 for r in _conferir(db).values())
    if regra == "I11":
        apoio_v2.semear_acessos(db, [INVALIDAS["I5"] | {"evidencia": "/x/20261110_090000_NEGADO_MULTIPLOS.jpg"}])
        con = sqlite3.connect(str(db))
        con.execute("DELETE FROM acessos WHERE id = 2")
        con.commit()
        con.close()
    elif regra == "I9":
        apoio_v2.semear_acessos(db, [INVALIDAS["I8"] | {"data_hora": "2026-11-10T08:59:00"}, INVALIDAS["I9"]])
    elif regra == "I12":
        apoio_v2.semear_acessos(db, [
            {"data_hora": f"2026-11-10T09:00:{s:02d}", "resultado": "NEGADO_DESCONHECIDO", "similaridade": 0.1,
             "evidencia": f"/x/20261110_0900{s:02d}_NEGADO_DESCONHECIDO.jpg"} for s in (0, 10, 20)])
    else:
        apoio_v2.semear_acessos(db, [INVALIDAS[regra]])
    res = _conferir(db)
    acusadas = {i for i, r in res.items() if r.violacoes}
    assert acusadas == {regra}
    assert res[regra].ids
    consultiva = {r.id: r.consultiva for r in integridade.REGRAS}[regra]
    assert consultiva == (regra in ("I2", "I6", "I8", "I12"))


def test_selo_detecta_update_e_delete(tmp_path):
    db = tmp_path / "t.db"
    _ok(db)
    apoio_v2.semear_acessos(db, [INVALIDAS["I6"] | {"similaridade": 0.1}])
    antes = integridade.selar(db)
    assert antes.registros == 3 and antes.ultimo_id == 3 and len(antes.sha256) == 64
    assert integridade.selar(db).sha256 == antes.sha256                # determinístico
    con = sqlite3.connect(str(db))
    con.execute("UPDATE acessos SET similaridade = 0.71 WHERE id = 1")
    con.commit()
    assert integridade.selar(db).sha256 != antes.sha256
    con.execute("UPDATE acessos SET similaridade = 0.7 WHERE id = 1")
    con.commit()
    assert integridade.selar(db).sha256 == antes.sha256
    con.execute("DELETE FROM acessos WHERE id = 3")
    con.commit()
    con.close()
    assert _conferir(db)["I11"].violacoes == 1
    assert integridade.estrutura(db)["seq_menos_max"] == 1


def test_selo_nao_muda_ao_remover_usuario(tmp_path):
    db = tmp_path / "t.db"
    banco = Banco(db)
    try:
        u = banco.criar_usuario("Pessoa Temporária", "M-1", "", 2)
        banco.registrar_acesso(usuario_id=u.id, nome_detectado=u.nome, nivel_usuario=2, nivel_exigido=1,
                               similaridade=0.8, resultado="CONCEDIDO", mensagem="ok")
        antes = integridade.selar(db)
        integridade.gravar_selo(antes, tmp_path / "rel", base="t.db", demonstracao=False)
        banco.remover_usuario(u.id)
        assert leitura_ro.consultar(db, "SELECT usuario_id FROM acessos")[0][0] is None    # vínculo esvaziado
    finally:
        banco.fechar()
    depois = integridade.selar(db)
    assert depois.sha256 == antes.sha256
    conf = integridade.conferir_selos(db, tmp_path / "rel")
    assert conf["total"] == 1 and conf["conferem"] == 1 and conf["ultimo"]["confere"] is True


def test_selo_gravado_confere_e_diverge(tmp_path):
    db = tmp_path / "t.db"
    _ok(db)
    pasta = tmp_path / "rel"
    destino = integridade.gravar_selo(integridade.selar(db), pasta, base="t.db", demonstracao=False)
    dados = json.loads(destino.read_text(encoding="utf-8"))
    assert destino.name.startswith("selo_") and destino.suffix == ".json"
    assert set(dados) == {"sha256", "registros", "ultimo_id", "gerado_em", "base", "demonstracao", "colunas", "observacao"}
    assert dados["colunas"] == list(integridade.COLUNAS_SELO) and "usuario_id" not in dados["colunas"]
    apoio_v2.semear_acessos(db, [INVALIDAS["I6"] | {"similaridade": 0.1}])     # linha nova depois do selo
    assert integridade.conferir_selos(db, pasta)["conferem"] == 1
    con = sqlite3.connect(str(db))
    con.execute("UPDATE acessos SET resultado = 'CONCEDIDO' WHERE id = 2")
    con.commit()
    con.close()
    conf = integridade.conferir_selos(db, pasta)
    assert conf["conferem"] == 0 and conf["divergentes"] == [{"arquivo": destino.name, "ultimo_id": 2}]
    assert conf["ultimo"]["confere"] is False


def test_base_demo_passa_nas_13_regras(tmp_path, monkeypatch, pipeline):
    apoio_v2.usar_pastas(monkeypatch, tmp_path / "demo")
    db = base_demo.gerar(tmp_path / "demo", dias=10, pipeline=pipeline)
    res = integridade.conferir(db, limiar=config.LIMIAR_COSSENO, janela_seg=config.JANELA_FALHAS_SEG,
                               max_falhas=config.MAX_TENTATIVAS_FALHAS, demonstracao=True)
    assert {r.regra.id: r.violacoes for r in res} == {f"I{i}": 0 for i in range(1, 14)}
    sem_marca = {r.regra.id: r.violacoes for r in integridade.conferir(
        db, limiar=config.LIMIAR_COSSENO, janela_seg=config.JANELA_FALHAS_SEG, max_falhas=config.MAX_TENTATIVAS_FALHAS)}
    assert sem_marca["I5"] > 0                                       # sem o marcador, as fictícias acusariam


def test_conferir_nao_escreve(tmp_path):
    db = tmp_path / "t.db"
    _ok(db)
    antes = apoio_v2.retrato_banco(db)
    _conferir(db)
    integridade.selar(db)
    integridade.estrutura(db)
    integridade.conferir_selos(db, tmp_path / "nada")
    assert apoio_v2.retrato_banco(db) == antes
    assert not (tmp_path / "nada").exists()
