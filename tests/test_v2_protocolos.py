"""Protocolos de avaliação (lote L6): fotos de teste, pasta rotulada e galeria cadastrada."""

from __future__ import annotations

import sqlite3

import numpy as np

from cofre import amostra_lab, protocolos
from cofre.avaliacao import avaliar_pasta
from cofre.banco import Banco
from tests import apoio_v2


def _amostra(rng) -> bytes:
    v = rng.normal(size=128).astype(np.float32)
    return (v / np.linalg.norm(v)).astype(np.float32).tobytes()


def _banco_com_amostras(caminho, contagens: list[int]):
    Banco(caminho).fechar()                              # cria o arquivo com o esquema do núcleo
    con = sqlite3.connect(str(caminho))
    try:
        rng = np.random.default_rng(11)
        for k, n in enumerate(contagens):
            cur = con.execute("INSERT INTO usuarios (nome, matricula, nivel, ativo, criado_em) VALUES (?,?,?,?,?)",
                              (f"Teste {k}", f"M{k}", 1, 1, "2026-11-01T10:00:00"))
            for _ in range(n):
                con.execute("INSERT INTO amostras (usuario_id, embedding, criado_em) VALUES (?,?,?)",
                            (cur.lastrowid, _amostra(rng), "2026-11-01T10:00:00"))
        con.commit()
    finally:
        con.close()


def test_fotos_de_teste_dao_2_genuinos_e_4_impostores(pipeline):
    prot = protocolos.de_pasta(amostra_lab.PASTA_FOTOS_TESTE, pipeline, chave="fotos_teste")
    assert prot.genuinos.size == 2 and prot.impostores.size == 4
    assert prot.ficha["pessoas"] == 2 and prot.ficha["imagens"] == 4 and prot.ficha["sem_rosto"] == 0
    assert prot.ficha["amostras_por_pessoa"] == [2, 2]
    assert prot.selos == ["Fotos de teste · 4 imagens"]
    ref = avaliar_pasta(amostra_lab.PASTA_FOTOS_TESTE, pipeline)
    assert np.allclose(np.sort(prot.genuinos), np.sort(ref.genuinos), atol=1e-6)
    assert np.allclose(np.sort(prot.impostores), np.sort(ref.impostores), atol=1e-6)


def test_galeria_conta_pares(tmp_path):
    caminho = tmp_path / "t.db"
    _banco_com_amostras(caminho, [3, 2])
    prot = protocolos.de_galeria(caminho)
    assert prot.genuinos.size == 4 and prot.impostores.size == 6
    assert prot.ficha["pessoas"] == 2 and prot.ficha["imagens"] == 5
    assert prot.selos == ["Mesma sessão · otimista"] and prot.descritores == {}
    assert protocolos.de_galeria(caminho, demonstracao=True).selos == ["Base de demonstração"]


def test_galeria_so_escores(tmp_path):
    caminho = tmp_path / "t.db"
    _banco_com_amostras(caminho, [70, 64])          # 134 amostras: nenhuma saída pode ter 128 vetores
    prot = protocolos.de_galeria(caminho)
    assert apoio_v2.sem_vetor_128(prot.ficha)
    assert apoio_v2.sem_vetor_128({"selos": prot.selos, "ficha": prot.ficha})
    assert set(vars(prot)) == {"chave", "genuinos", "impostores", "ficha", "selos", "descritores"}
    assert prot.genuinos.ndim == 1 and prot.impostores.ndim == 1


def test_descritores_presentes_na_pasta(pipeline):
    prot = protocolos.de_pasta(amostra_lab.PASTA_FOTOS_TESTE, pipeline)
    assert set(prot.descritores) == set(protocolos.DESCRITORES_LBP)
    for g, i in prot.descritores.values():
        assert g.size == 2 and i.size == 4
        assert np.all((g >= -1) & (g <= 1)) and np.all((i >= -1) & (i <= 1))
    assert prot.selos == []
