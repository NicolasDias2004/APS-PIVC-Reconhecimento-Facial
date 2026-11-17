"""Técnica da aba Visão geral (L1): agregações do registro em `cofre/analitica.py`."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from cofre import analitica
from cofre.analitica import Evento
from tests import apoio_v2


def ev(i, dh, res, sim=None, nivel=3):
    return Evento(i, dh, res, nivel, sim)


def test_resumo_conta_os_seis_resultados():
    eventos = [ev(1, "2026-11-10T08:00:00", "CONCEDIDO", 0.6), ev(2, "2026-11-10T08:01:00", "NEGADO_NIVEL", 0.7),
               ev(3, "2026-11-11T08:02:00", "NEGADO_DESCONHECIDO", 0.2),
               ev(4, "2026-11-11T08:03:00", "NEGADO_DESCONHECIDO", 0.1),
               ev(5, "2026-11-11T08:04:00", "BLOQUEADO")]
    r = analitica.resumo(eventos)
    assert set(r["por_resultado"]) == set(analitica.RESULTADOS)
    assert r["por_resultado"]["NEGADO_LIVENESS"] == 0 and r["por_resultado"]["NEGADO_MULTIPLOS"] == 0
    assert r["por_resultado"]["NEGADO_DESCONHECIDO"] == 2
    assert (r["total"], r["dias_distintos"], r["bloqueios"], r["negadas"]) == (5, 2, 1, 3)
    assert r["primeiro"] == "2026-11-10T08:00:00" and r["ultimo"] == "2026-11-11T08:04:00"
    vazio = analitica.resumo([])
    assert vazio["total"] == 0 and sum(vazio["por_resultado"].values()) == 0 and vazio["primeiro"] is None


def test_folga_com_e_sem_concedidos():
    eventos = [ev(1, "2026-11-10T08:00:00", "CONCEDIDO", 0.546), ev(2, "2026-11-10T08:01:00", "CONCEDIDO", 0.30),
               ev(3, "2026-11-10T08:02:00", "NEGADO_DESCONHECIDO", 0.329)]
    f = analitica.folga(eventos, 0.363)
    assert f["menor_concedida"] == 0.30 and f["maior_desconhecida"] == 0.329 and f["concedidas_abaixo"] == 1
    assert abs(f["folga_acima"] - (0.30 - 0.363)) < 1e-9 and abs(f["folga_abaixo"] - (0.363 - 0.329)) < 1e-9
    sem = analitica.folga([ev(1, "2026-11-10T08:00:00", "NEGADO_MULTIPLOS")], 0.363)
    assert sem == {"menor_concedida": None, "maior_desconhecida": None, "concedidas_abaixo": 0,
                   "folga_acima": None, "folga_abaixo": None}


def test_manchete_vazia():
    res = analitica.resumo([])
    assert analitica.manchete(res, analitica.folga([], 0.363), 0.363) == ("Ainda não há tentativas registradas.", [])
    eventos = [ev(1, "2026-11-10T08:00:00", "CONCEDIDO", 0.546), ev(2, "2026-11-10T08:01:00", "NEGADO_DESCONHECIDO", 0.329)]
    frase, leituras = analitica.manchete(analitica.resumo(eventos), analitica.folga(eventos, 0.363), 0.363)
    assert frase == "2 tentativas, 1 autorizada."
    assert leituras[1] == "Nenhuma autorização abaixo do limiar de 0,363"
    assert leituras[2] == "Menor similaridade autorizada: 0,546 · maior não reconhecida: 0,329"


def test_fita_uma_faixa_por_dia_e_intervalo_de_bloqueio():
    eventos = [ev(i, f"2026-11-{d:02d}T10:00:00", "CONCEDIDO", 0.6) for i, d in enumerate(range(1, 10), start=1)]
    eventos.append(ev(20, "2026-11-09T12:30:00", "BLOQUEADO"))
    d = analitica.dados_fita(eventos, 90.0)
    assert len(d["faixas"]) == 7                                # os 7 dias mais recentes
    assert d["faixas"][-1]["rotulo"].endswith("09/11") and d["faixas"][0]["rotulo"].endswith("03/11")
    ultimo = d["faixas"][-1]
    assert [e["tipo"] for e in ultimo["eventos"]] == ["concedido", "bloqueio"]
    (iv,) = ultimo["intervalos"]
    assert abs(iv["t0"] - 12.5) < 1e-4 and abs((iv["t1"] - iv["t0"]) * 3600 - 90.0) < 0.1
    d2 = analitica.dados_fita(eventos, 600.0)
    (iv2,) = d2["faixas"][-1]["intervalos"]
    assert abs((iv2["t1"] - iv2["t0"]) * 3600 - 600.0) < 0.1
    assert apoio_v2.sem_vetor_128(d)


def test_espectro_soma_bate_com_n_com_similaridade():
    eventos = [ev(i, "2026-11-10T08:00:00", "CONCEDIDO", 0.4 + i / 100) for i in range(20)]
    eventos += [ev(100 + i, "2026-11-10T08:00:00", "NEGADO_DESCONHECIDO", i / 100) for i in range(15)]
    eventos += [ev(200, "2026-11-10T08:00:00", "BLOQUEADO"), ev(201, "2026-11-10T08:00:00", "NEGADO_MULTIPLOS")]
    d = analitica.dados_espectro(eventos, 0.363, 0.5)
    aut, neg = d["series"]
    assert len(d["bordas"]) == 51 and len(aut["contagens"]) == 50
    assert sum(aut["contagens"]) == 20 and sum(neg["contagens"]) == 15
    assert aut["sentido"] == 1 and neg["sentido"] == -1
    assert [m["estilo"] for m in d["marcadoresV"]] == ["vigor", "nota"]
    assert d["truncarEm"] >= 12
    assert apoio_v2.sem_vetor_128(d)


def test_ler_eventos_nao_seleciona_nomes(tmp_path):
    fonte = Path(analitica.__file__).read_text(encoding="utf-8")
    cadeias = [n.value for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    sql = [c for c in cadeias if "SELECT" in c.upper()]
    assert sql, "o módulo deveria ter uma consulta"
    for c in sql:
        for proibido in ("nome_detectado", "mensagem", "usuario_id", "evidencia"):
            assert proibido not in c
    campos = {f.name for f in dataclasses.fields(Evento)}
    assert campos.isdisjoint({"nome_detectado", "mensagem", "usuario_id", "evidencia", "nome"})
    db = tmp_path / "t.db"
    apoio_v2.semear_acessos(db, [
        {"data_hora": "2026-11-10T08:00:00", "resultado": "CONCEDIDO", "nome_detectado": "Fulana", "similaridade": 0.7,
         "nivel_usuario": 3, "mensagem": "Bem-vinda, Fulana"},
        {"data_hora": "2026-11-11T08:00:00", "resultado": "NEGADO_DESCONHECIDO", "similaridade": 0.2}])
    todos = analitica.ler_eventos(db)
    assert [e.id for e in todos] == [1, 2]
    assert [e.id for e in analitica.ler_eventos(db, desde="2026-11-11T00:00:00")] == [2]
    assert [e.id for e in analitica.ler_eventos(db, limite=1)] == [2]
    assert "Fulana" not in repr(todos)
