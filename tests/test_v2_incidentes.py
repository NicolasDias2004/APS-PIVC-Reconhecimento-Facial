"""Técnica da aba Incidentes (L2): o detector de `cofre/incidentes.py`, por tipo e no fluxo real."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from cofre import config, incidentes
from cofre.autenticacao import TerminalAutenticacao
from cofre.banco import Banco
from cofre.incidentes import Linha

JANELA = 60.0
FORTE = 0.50


def L(i, hms, res, sim=None, uid=None, nu=None, ne=3, dia="2026-11-10"):
    return Linha(i, f"{dia}T{hms}", res, sim, nu, ne, uid)


def detectar(linhas):
    return incidentes.detectar(linhas, janela_seg=JANELA, limiar_forte=FORTE)


def test_registro_vazio():
    assert detectar([]) == []
    assert [r["tipo"] for r in incidentes.regras_em_texto(JANELA, 3, FORTE)] == list(incidentes.TIPOS)


def test_bloqueio():
    linhas = [L(1, "20:40:00", "CONCEDIDO", 0.7, 1, 3), L(2, "20:41:00", "NEGADO_DESCONHECIDO", 0.1),
              L(3, "20:41:10", "NEGADO_DESCONHECIDO", 0.2), L(4, "20:41:22", "NEGADO_DESCONHECIDO", 0.1),
              L(5, "20:41:22", "BLOQUEADO")]
    (inc,) = detectar(linhas)
    assert inc.tipo == "bloqueio" and inc.gravidade == "alta" and inc.ids == (2, 3, 4, 5)
    assert inc.chave == "bloqueio:2-5" and inc.usuario_id is None
    assert inc.resumo == "3 negações em 22 s antes do bloqueio"
    assert "Fulano" not in inc.resumo


def test_acima_do_nivel():
    linhas = [L(1, "08:00:00", "NEGADO_NIVEL", 0.8, 7, 1), L(2, "08:05:00", "NEGADO_NIVEL", 0.8, 7, 1),
              L(3, "08:14:00", "NEGADO_NIVEL", 0.8, 7, 1), L(4, "09:00:00", "NEGADO_NIVEL", 0.8, 7, 1),
              L(5, "08:06:00", "NEGADO_NIVEL", 0.8, 8, 2)]
    achados = sorted(detectar(linhas), key=lambda i: i.ids)
    assert [i.ids for i in achados] == [(1, 2, 3), (4,), (5,)]
    assert achados[0].gravidade == "alta" and achados[1].gravidade == "media"
    assert {i.usuario_id for i in achados} == {7, 8}


def test_prova_de_vida():
    linhas = [L(1, "10:00:00", "NEGADO_LIVENESS", 0.62, 4, 3), L(2, "10:03:00", "NEGADO_LIVENESS", 0.70, 4, 3),
              L(3, "10:04:00", "NEGADO_LIVENESS", 0.40, 4, 3)]          # abaixo do limiar forte: fora
    (inc,) = detectar(linhas)
    assert inc.tipo == "prova_de_vida" and inc.ids == (1, 2) and inc.gravidade == "media"
    assert incidentes.TEXTO_PROVA_DE_VIDA in inc.resumo


def test_multiplos():
    linhas = [L(1, "11:00:00", "NEGADO_MULTIPLOS"), L(2, "11:01:30", "NEGADO_MULTIPLOS"),
              L(3, "11:05:00", "NEGADO_MULTIPLOS")]
    achados = sorted(detectar(linhas), key=lambda i: i.ids)
    assert [i.ids for i in achados] == [(1, 2), (3,)]
    assert all(i.tipo == "multiplos" and i.usuario_id is None for i in achados)


def test_fronteira_da_janela():
    dentro = [L(1, "12:00:00", "NEGADO_DESCONHECIDO"), L(2, "12:00:30", "NEGADO_DESCONHECIDO"),
              L(3, "12:01:00", "NEGADO_DESCONHECIDO"), L(4, "12:01:00", "BLOQUEADO")]
    assert detectar(dentro)[0].ids == (1, 2, 3, 4)                    # exatamente 60 s antes: entra
    fora = [L(1, "11:59:59", "NEGADO_DESCONHECIDO")] + dentro[1:]
    assert detectar(fora)[0].ids == (2, 3, 4)                         # 61 s antes: fica de fora
    corte = [L(1, "12:00:00", "NEGADO_DESCONHECIDO"), L(2, "12:00:10", "CONCEDIDO", 0.7, 1, 3),
             L(3, "12:00:20", "NEGADO_DESCONHECIDO"), L(4, "12:00:30", "BLOQUEADO")]
    assert detectar(corte)[0].ids == (3, 4)                           # para no último concedido
    nivel = [L(1, "08:00:00", "NEGADO_NIVEL", 0.8, 7, 1), L(2, "08:10:00", "NEGADO_NIVEL", 0.8, 7, 1)]
    assert len(detectar(nivel)) == 2                                  # 600 s entre vizinhas: separa


def test_incidentes_nao_juntam_pessoas_removidas():
    linhas = [L(1, "08:00:00", "NEGADO_NIVEL", 0.8, None, 1), L(2, "08:01:00", "NEGADO_NIVEL", 0.8, None, 1)]
    achados = detectar(linhas)
    assert len(achados) == 2 and all(i.usuario_id is None and len(i.ids) == 1 for i in achados)


def test_contexto_inclui_vizinhas():
    linhas = [L(1, "08:00:00", "CONCEDIDO", 0.7, 1, 3), L(2, "08:30:00", "NEGADO_MULTIPLOS"),
              L(3, "08:31:00", "NEGADO_MULTIPLOS"), L(4, "08:32:30", "CONCEDIDO", 0.7, 1, 3)]
    (inc,) = detectar(linhas)
    assert [l.id for l in incidentes.contexto(linhas, inc)] == [2, 3, 4]


def test_bloqueio_do_fluxo_real(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.0)
    banco = Banco(tmp_path / "t.db")
    try:
        conduzir_tres_negacoes(banco)
    finally:
        banco.fechar()
    linhas = incidentes.ler_linhas(tmp_path / "t.db")
    assert [l.resultado for l in linhas] == ["NEGADO_DESCONHECIDO"] * 3 + ["BLOQUEADO"]
    achados = incidentes.detectar(linhas, janela_seg=config.JANELA_FALHAS_SEG, limiar_forte=config.LIMIAR_COSSENO_FORTE)
    (inc,) = achados
    assert inc.tipo == "bloqueio" and len(inc.ids) == 4 and inc.resumo.startswith("3 negações")


def conduzir_tres_negacoes(banco) -> None:
    """Dirige o terminal real com objetos falsos (sem câmera nem rede) até o bloqueio."""
    t = TerminalAutenticacao(banco, None, nivel_exigido=3, liveness=False)
    rng = np.random.default_rng(3)
    frame = np.zeros((480, 640, 3), np.uint8)
    for _ in range(t.tentativas.max_falhas):
        v = rng.normal(size=128).astype(np.float32)
        v /= np.linalg.norm(v)
        rosto = SimpleNamespace(embedding=v, rosto=SimpleNamespace(problema_pose=lambda: "", yaw=lambda: 0.0),
                                qualidade=SimpleNamespace(aprovada=True, motivo=""))
        for _ in range(t.confirmador.n):
            t.passo(frame, rosto, 1)
        t.passo(frame, None, 0)
