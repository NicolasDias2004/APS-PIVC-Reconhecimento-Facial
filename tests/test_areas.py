"""Conteúdo das áreas liberadas depois da autenticação: herança por nível e dados fictícios."""
from datetime import date

import pytest

from cofre import areas, config


def test_heranca_de_niveis():
    assert areas.areas_liberadas(1) == [1]
    assert areas.areas_liberadas(2) == [1, 2]
    assert areas.areas_liberadas(3) == [1, 2, 3]
    assert areas.areas_liberadas(0) == []
    resumo = areas.resumo_areas(2)
    assert [r["nivel"] for r in resumo] == [1, 2, 3]
    assert [r["liberada"] for r in resumo] == [True, True, False]
    assert resumo[2]["titulo"] == config.AREAS[3]


def test_conteudo_por_nivel_e_deterministico():
    hoje = date(2026, 11, 4)
    c1, c2, c3 = (areas.conteudo(n, hoje) for n in (1, 2, 3))
    assert c1["titulo"] == config.AREAS[1] and len(c1["comunicados"]) == 4 and len(c1["qualidadeAr"]) == 7
    assert c2["resumo"]["divisoes"] == len(c2["divisoes"]) == 5 and c2["resumo"]["aprovacoesPendentes"] == 6
    assert all(0 < d["fracao"] <= 1 for d in c2["divisoes"])
    assert len(c3["lotes"]) == 8 and c3["totais"]["criticos"] == 3 and len(c3["temperatura"]) == 24
    assert all(-82 <= t["valor"] <= -74 for t in c3["temperatura"])
    assert areas.conteudo(3, hoje)["lotes"] == c3["lotes"]            # mesma semente, mesmo conteúdo
    with pytest.raises(ValueError):
        areas.conteudo(4, hoje)
