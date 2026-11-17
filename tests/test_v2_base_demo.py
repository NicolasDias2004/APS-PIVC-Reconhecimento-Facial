"""Base de demonstração: recusas do gerador, marcador, identidades, histórico fictício dentro das
regras do terminal e o lançador `app_demo.py`. Tudo em pasta temporária: `data/` do projeto nunca é
tocado (a fixture `_data_real_intacta` confere isso em cada caso)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from cofre import amostra_lab, base_demo, config, leitura_ro
from cofre.banco import Banco
from cofre.fase1_aquisicao import carregar_imagem
from cofre.fase5_reconhecimento import Resultado
from cofre.liveness import ControleTentativas
from tests import apoio_v2

AGORA = datetime(2026, 11, 16, 10, 30)          # uma segunda-feira; o histórico termina no domingo, dia 15
COLUNAS = ("id, data_hora, usuario_id, nome_detectado, nivel_usuario, nivel_exigido, area, similaridade, "
           "resultado, mensagem, evidencia")


DATA_REAL = config.BASE_DIR / "data"            # só para conferir que nada nasce aqui; nenhum teste abre o que há dentro


def _retrato_de_data_real() -> tuple:
    """O que o gerador poderia criar por engano dentro de `data/` do projeto: a pasta `demo` e o banco solto."""
    demo, solto = DATA_REAL / "demo", DATA_REAL / "cofre_demo.db"
    return (demo.exists(), demo.stat().st_mtime_ns if demo.exists() else None, solto.exists())


@pytest.fixture(autouse=True)
def _data_real_intacta():
    antes = _retrato_de_data_real()
    yield
    assert _retrato_de_data_real() == antes, "o teste mexeu em data/ do projeto"


def _gerar(raiz, pipeline, **opcoes):
    opcoes.setdefault("agora", AGORA)
    return base_demo.gerar(raiz, raiz_permitida=raiz, pipeline=pipeline, **opcoes)


def _acessos(caminho) -> list:
    return leitura_ro.consultar(caminho, f"SELECT {COLUNAS} FROM acessos ORDER BY id")


def _arvore(pasta) -> list[str]:
    return sorted(str(p.relative_to(pasta)) for p in pasta.rglob("*"))


# ---------------------------------------------------------------------------- recusas
def test_recusa_o_banco_real(tmp_path, monkeypatch, pipeline):
    pasta_real = base_demo.BANCO_REAL.parent
    assert base_demo.BANCO_REAL == (DATA_REAL / "cofre.db").resolve() and base_demo.RAIZ_PADRAO == DATA_REAL / "demo"
    with pytest.raises(base_demo.RecusaBaseDemo, match="banco real"):
        base_demo.gerar(pasta_real, pipeline=pipeline)
    with pytest.raises(base_demo.RecusaBaseDemo, match="banco real"):
        base_demo.gerar(pasta_real, recriar=True, apagar_cadastros=True, raiz_permitida=pasta_real, pipeline=pipeline)

    # a mesma recusa, isolada das outras: pastas redirecionadas e um "banco real" de mentira
    for nome_do_banco in ("cofre.db", "cofre_demo.db"):          # a raiz é a pasta do banco real, ou o próprio arquivo é ele
        raiz = tmp_path / nome_do_banco.replace(".", "_")
        monkeypatch.setattr(base_demo, "BANCO_REAL", (raiz / nome_do_banco).resolve())
        apoio_v2.usar_pastas(monkeypatch, raiz)
        with pytest.raises(base_demo.RecusaBaseDemo, match="banco real"):
            base_demo.gerar(raiz, raiz_permitida=raiz, pipeline=pipeline)
    assert _arvore(tmp_path) == []


def test_recusa_fora_da_raiz_permitida(tmp_path, monkeypatch, pipeline):
    raiz = tmp_path / "demo"
    apoio_v2.usar_pastas(monkeypatch, raiz)
    with pytest.raises(base_demo.RecusaBaseDemo, match="fora da pasta permitida"):
        base_demo.gerar(raiz, raiz_permitida=tmp_path / "outra", pipeline=pipeline)
    with pytest.raises(base_demo.RecusaBaseDemo, match="fora da pasta permitida"):
        base_demo.gerar(raiz, raiz_permitida=raiz / "dentro", pipeline=pipeline)
    assert _arvore(tmp_path) == []


def test_recusa_sem_pastas_redirecionadas(tmp_path, monkeypatch, pipeline):
    raiz = tmp_path / "demo"
    with pytest.raises(base_demo.RecusaBaseDemo, match="FOTOS_DIR"):     # só com o preparo comum dos testes (conftest)
        base_demo.gerar(raiz, raiz_permitida=raiz, pipeline=pipeline)
    for nome in ("FOTOS_DIR", "EVIDENCIAS_DIR", "RELATORIOS_DIR"):
        with monkeypatch.context() as m:
            apoio_v2.usar_pastas(m, raiz)
            m.setattr(config, nome, tmp_path / "outra" / nome.lower())
            with pytest.raises(base_demo.RecusaBaseDemo, match=nome):
                base_demo.gerar(raiz, raiz_permitida=raiz, pipeline=pipeline)
    assert _arvore(tmp_path) == []                                       # nada escrito em lugar nenhum


def test_recusa_arquivo_sem_marcador(tmp_path, monkeypatch, pipeline):
    raiz = tmp_path / "demo"
    alvo = apoio_v2.usar_pastas(monkeypatch, raiz)
    with Banco(alvo["DB_PATH"]) as banco:                                # um banco comum com o nome da base
        banco.criar_usuario("Ana", "M001", "", 1)
    antes = alvo["DB_PATH"].read_bytes()
    assert base_demo.marcador(alvo["DB_PATH"]) is None
    for opcoes in ({}, {"recriar": True}, {"recriar": True, "apagar_cadastros": True}):
        with pytest.raises(base_demo.RecusaBaseDemo, match="marcador"):
            _gerar(raiz, pipeline, **opcoes)
    assert alvo["DB_PATH"].read_bytes() == antes and _arvore(raiz) == ["cofre_demo.db"]

    alvo["DB_PATH"].write_text("isto não é um banco")
    with pytest.raises(base_demo.RecusaBaseDemo, match="marcador"):
        _gerar(raiz, pipeline, recriar=True, apagar_cadastros=True)
    assert alvo["DB_PATH"].read_text() == "isto não é um banco"


# ---------------------------------------------------------------------------- geração
def test_gera_com_marcador_e_so_dois_usuarios_ativos(tmp_path, monkeypatch, pipeline):
    raiz = tmp_path / "demo"
    alvo = apoio_v2.usar_pastas(monkeypatch, raiz)
    assert alvo == base_demo.pastas(raiz) and tuple(alvo) == base_demo.VARIAVEIS
    raiz.mkdir()
    (raiz / "cofre_demo.db.gerando").write_text("resto de uma geração interrompida")
    caminho = _gerar(raiz, pipeline)
    assert caminho == base_demo.caminho_banco(raiz) == raiz / "cofre_demo.db" and caminho.is_file()

    assert base_demo.APPLICATION_ID == 0x434D4D44
    assert leitura_ro.consultar(caminho, "PRAGMA application_id")[0][0] == base_demo.APPLICATION_ID
    assert leitura_ro.eh_base_demonstracao(caminho) is True
    assert base_demo.marcador(caminho) == {"gerado_em": "2026-11-16T10:30:00", "semente": "7", "dias": "30", "versao": "1"}

    usuarios = leitura_ro.consultar(caminho, "SELECT id, nome, matricula, cargo, nivel, ativo FROM usuarios ORDER BY id")
    assert [tuple(u) for u in usuarios] == [
        (1, "Retrato público 1 (demonstração)", "DEMO-001", "Ministro (demonstração)", 3, 1),
        (2, "Retrato público 2 (demonstração)", "DEMO-002", "Diretor (demonstração)", 2, 1)]

    # 4 amostras, e todo vetor é o que o cadastro normal grava para a foto de teste correspondente
    galeria = leitura_ro.galeria(caminho, apenas_ativos=False)
    assert galeria.donos.tolist() == [1, 1, 2, 2] and galeria.amostras.tolist() == [1, 2, 1, 2] and galeria.inativos == 0
    fotos = [c for grupo in amostra_lab.fotos_de_teste().values() for c in grupo]
    esperados = np.vstack([pipeline.processar(carregar_imagem(c)).principal.embedding for c in fotos])
    assert np.array_equal(galeria.matriz, esperados)
    recortes = [linha[0] for linha in leitura_ro.consultar(caminho, "SELECT caminho_foto FROM amostras ORDER BY id")]
    assert all(alvo["FOTOS_DIR"] in Path(recorte).parents and Path(recorte).is_file() for recorte in recortes)

    # tudo dentro da raiz: banco e recortes; nada provisório, nada fora
    assert sorted(p.name for p in tmp_path.iterdir()) == ["demo"]
    assert sorted(p.name for p in raiz.iterdir()) == ["cofre_demo.db", "fotos"]
    assert len(list(alvo["FOTOS_DIR"].rglob("*.jpg"))) == 4

    antes = caminho.read_bytes()                                         # base pronta: chamar de novo não mexe
    assert _gerar(raiz, pipeline, semente=99) == caminho and caminho.read_bytes() == antes


def test_falha_no_meio_nao_deixa_base_pela_metade(tmp_path, monkeypatch, pipeline):
    class PipelineQuebrado:
        def processar(self, frame):
            raise RuntimeError("modelo indisponível")

    raiz = tmp_path / "demo"
    alvo = apoio_v2.usar_pastas(monkeypatch, raiz)
    with pytest.raises(RuntimeError, match="modelo indisponível"):
        base_demo.gerar(raiz, raiz_permitida=raiz, pipeline=PipelineQuebrado(), agora=AGORA)
    assert _arvore(raiz) == [] and base_demo.marcador(alvo["DB_PATH"]) is None
    caminho = _gerar(raiz, pipeline)                         # a tentativa seguinte começa do zero e funciona
    assert base_demo.marcador(caminho) is not None and _arvore(raiz)[0] == "cofre_demo.db"


def test_linhas_ficticias_marcadas_e_sem_evidencia(tmp_path, monkeypatch, pipeline):
    raiz = tmp_path / "demo"
    alvo = apoio_v2.usar_pastas(monkeypatch, raiz)
    linhas = _acessos(_gerar(raiz, pipeline))
    assert len(linhas) > 300
    assert base_demo.MARCA_MENSAGEM == "[demonstração] "
    assert all(linha["mensagem"].startswith(base_demo.MARCA_MENSAGEM) for linha in linhas)
    assert all(linha["evidencia"] is None for linha in linhas)
    assert not alvo["EVIDENCIAS_DIR"].exists() and not alvo["RELATORIOS_DIR"].exists()
    assert all(linha["area"] == config.AREAS[linha["nivel_exigido"]] and len(linha["data_hora"]) == 19 for linha in linhas)
    assert [linha["id"] for linha in linhas] == list(range(1, len(linhas) + 1))

    # 30 dias terminando na véspera de `agora`
    dias = sorted({linha["data_hora"][:10] for linha in linhas})
    vespera = (AGORA - timedelta(days=1)).date()
    assert dias[0] >= (AGORA - timedelta(days=30)).date().isoformat() and dias[-1] <= vespera.isoformat()
    uteis = [(AGORA - timedelta(days=d)).date() for d in range(1, 31) if (AGORA - timedelta(days=d)).weekday() < 5]
    assert all(dia.isoformat() in dias for dia in uteis)

    # uma tentativa de verdade nesta base não leva a marca (é assim que a aba de integridade separa as duas)
    with Banco(alvo["DB_PATH"]) as banco:
        banco.registrar_acesso(usuario_id=None, nome_detectado=None, nivel_usuario=None, nivel_exigido=3,
                               similaridade=0.1, resultado=Resultado.NEGADO_DESCONHECIDO.value,
                               mensagem="Rosto não cadastrado. Acesso negado.")
    assert leitura_ro.consultar(alvo["DB_PATH"], "SELECT COUNT(*) FROM acessos WHERE mensagem NOT LIKE ?",
                                (base_demo.MARCA_MENSAGEM + "%",))[0][0] == 1
    assert leitura_ro.eh_base_demonstracao(alvo["DB_PATH"])


def test_regras_do_terminal_no_historico(tmp_path, monkeypatch, pipeline):
    raiz = tmp_path / "demo"
    apoio_v2.usar_pastas(monkeypatch, raiz)
    caminho = _gerar(raiz, pipeline)

    def contar(condicao: str, params=()) -> int:
        return leitura_ro.consultar(caminho, f"SELECT COUNT(*) FROM acessos WHERE {condicao}", params)[0][0]

    assert contar("resultado NOT IN ('CONCEDIDO','NEGADO_NIVEL','NEGADO_DESCONHECIDO','NEGADO_LIVENESS',"
                  "'NEGADO_MULTIPLOS','BLOQUEADO')") == 0
    # concedido: sempre com pessoa, no nível dela ou abaixo, com similaridade de reconhecimento forte
    assert contar("resultado = 'CONCEDIDO'") > 100
    assert contar("resultado = 'CONCEDIDO' AND (usuario_id IS NULL OR nome_detectado IS NULL OR nivel_usuario IS NULL "
                  "OR nivel_usuario < nivel_exigido OR similaridade IS NULL OR similaridade < 0.50 OR similaridade > 0.93)") == 0
    assert contar("usuario_id IS NOT NULL AND nivel_usuario <> (SELECT nivel FROM usuarios WHERE id = usuario_id)") == 0
    assert contar("usuario_id IS NOT NULL AND nome_detectado <> (SELECT nome FROM usuarios WHERE id = usuario_id)") == 0
    # desconhecido: sem pessoa e sempre abaixo do limiar
    assert contar("resultado = 'NEGADO_DESCONHECIDO'") > 30
    assert contar("resultado = 'NEGADO_DESCONHECIDO' AND (usuario_id IS NOT NULL OR nome_detectado IS NOT NULL "
                  "OR similaridade IS NULL OR similaridade >= ? OR similaridade > 0.33)", (config.LIMIAR_COSSENO,)) == 0
    # nível insuficiente: a pessoa de nível 2 pedindo o nível 3
    assert contar("resultado = 'NEGADO_NIVEL'") > 10
    assert contar("resultado = 'NEGADO_NIVEL' AND (nivel_usuario <> 2 OR nivel_exigido <> 3 OR usuario_id IS NULL "
                  "OR similaridade < 0.55 OR similaridade > 0.90)") == 0
    assert contar("resultado = 'NEGADO_LIVENESS'") > 10
    assert contar("resultado = 'NEGADO_LIVENESS' AND (usuario_id IS NULL OR similaridade < 0.50 OR similaridade > 0.88)") == 0
    assert contar("resultado = 'NEGADO_MULTIPLOS'") > 0
    assert contar("resultado IN ('NEGADO_MULTIPLOS', 'BLOQUEADO') AND (usuario_id IS NOT NULL OR nome_detectado IS NOT NULL "
                  "OR nivel_usuario IS NOT NULL OR similaridade IS NOT NULL)") == 0
    # a data nunca regride com o id
    assert leitura_ro.consultar(caminho, "SELECT COUNT(*) FROM (SELECT data_hora, LAG(data_hora) OVER (ORDER BY id) AS anterior "
                                         "FROM acessos) WHERE data_hora < anterior")[0][0] == 0
    # todo BLOQUEADO vem logo depois de uma negação, no mesmo segundo
    assert leitura_ro.consultar(caminho, """SELECT COUNT(*) FROM (
        SELECT resultado, data_hora, LAG(resultado) OVER (ORDER BY id) AS res_anterior,
               LAG(data_hora) OVER (ORDER BY id) AS hora_anterior FROM acessos)
        WHERE resultado = 'BLOQUEADO' AND (res_anterior NOT LIKE 'NEGADO_%' OR hora_anterior <> data_hora)""")[0][0] == 0
    assert contar("resultado = 'BLOQUEADO'") >= 3

    # o bloqueio pela regra do próprio terminal: o controle de tentativas do núcleo, com o relógio do histórico
    relogio = [0.0]
    controle = ControleTentativas(relogio=lambda: relogio[0])
    assert (controle.max_falhas, controle.janela) == (3, 60.0)
    disparou = False
    for linha in _acessos(caminho):
        relogio[0] = datetime.fromisoformat(linha["data_hora"]).timestamp()
        if linha["resultado"] == Resultado.BLOQUEADO.value:
            assert disparou, f"BLOQUEADO sem a terceira negação antes (id {linha['id']})"
            assert linha["mensagem"] == base_demo.MARCA_MENSAGEM + "Terminal bloqueado por 30s após 3 falhas"
            disparou = False
            continue
        assert not disparou, f"terceira negação em 60 s sem BLOQUEADO logo depois (antes do id {linha['id']})"
        assert not controle.bloqueado, f"tentativa durante o bloqueio (id {linha['id']})"
        if linha["resultado"] == Resultado.CONCEDIDO.value:
            controle.registrar_sucesso()
        else:
            disparou = controle.registrar_falha()
    assert not disparou

    # mistura e horários aproximados do roteiro: maioria concedida, pico de manhã e no começo da tarde
    linhas = _acessos(caminho)
    por_resultado = Counter(linha["resultado"] for linha in linhas)
    assert 0.45 <= por_resultado["CONCEDIDO"] / len(linhas) <= 0.65
    assert 0.12 <= por_resultado["NEGADO_DESCONHECIDO"] / len(linhas) <= 0.30
    no_pico = sum(1 for linha in linhas if int(linha["data_hora"][11:13]) in (8, 9, 10, 13, 14))
    assert no_pico / len(linhas) > 0.6
    por_dia = Counter(linha["data_hora"][:10] for linha in linhas if linha["resultado"] != "BLOQUEADO")
    for dia, total in por_dia.items():
        if datetime.fromisoformat(dia).weekday() < 5:
            assert 10 <= total <= 46, (dia, total)          # 15 a 40 sorteadas, menos as vizinhas de um episódio, mais as 3 dele
        else:
            assert total <= 4, (dia, total)


def test_deterministica_com_a_mesma_semente(tmp_path, monkeypatch, pipeline):
    def historico(nome: str, **opcoes) -> list[tuple]:
        raiz = tmp_path / nome
        apoio_v2.usar_pastas(monkeypatch, raiz)
        return [tuple(linha) for linha in _acessos(_gerar(raiz, pipeline, **opcoes))]

    primeira = historico("a", semente=7)
    assert historico("b", semente=7) == primeira
    assert historico("c", semente=7, agora=AGORA.replace(hour=23, minute=59)) == primeira      # só o dia conta
    assert historico("d", semente=8) != primeira
    curta = historico("e", semente=7, dias=3)
    assert len(curta) < len(primeira) and sum(1 for linha in curta if linha[8] == "BLOQUEADO") >= 3
    assert {linha[1][:10] for linha in curta} <= {"2026-11-13", "2026-11-14", "2026-11-15"}


def test_recriar_recusa_com_cadastro_do_usuario(tmp_path, monkeypatch, pipeline):
    raiz = tmp_path / "demo"
    alvo = apoio_v2.usar_pastas(monkeypatch, raiz)
    caminho = _gerar(raiz, pipeline)
    alvo["RELATORIOS_DIR"].mkdir()
    (alvo["RELATORIOS_DIR"] / "acessos.csv").write_text("x")
    _gerar(raiz, pipeline, recriar=True, semente=8)          # base só com o que o gerador fez: refaz sem pedir mais nada
    assert base_demo.marcador(caminho)["semente"] == "8" and not alvo["RELATORIOS_DIR"].exists()

    with Banco(caminho) as banco:                            # alguém se cadastrou e tentou entrar pelo aplicativo
        banco.criar_usuario("Visitante", "V-001", "", 1)
    alvo["EVIDENCIAS_DIR"].mkdir()
    (alvo["EVIDENCIAS_DIR"] / "20261116_103000_NEGADO_NIVEL.jpg").write_bytes(b"jpg")
    antes = caminho.read_bytes()
    with pytest.raises(base_demo.RecusaBaseDemo, match=r"1 cadastro\(s\) e 1 evidência\(s\)"):
        _gerar(raiz, pipeline, recriar=True)
    assert caminho.read_bytes() == antes and len(list(alvo["EVIDENCIAS_DIR"].iterdir())) == 1
    assert _gerar(raiz, pipeline) == caminho and caminho.read_bytes() == antes       # sem recriar, segue devolvendo a base

    _gerar(raiz, pipeline, recriar=True, apagar_cadastros=True)
    assert leitura_ro.consultar(caminho, "SELECT matricula FROM usuarios ORDER BY id")[0][0] == "DEMO-001"
    assert len(leitura_ro.ids_usuarios(caminho)) == 2 and not alvo["EVIDENCIAS_DIR"].exists()
    assert sorted(p.name for p in raiz.iterdir()) == ["cofre_demo.db", "fotos"]

    alvo["EVIDENCIAS_DIR"].mkdir()                           # só a evidência já basta para recusar
    (alvo["EVIDENCIAS_DIR"] / "x.jpg").write_bytes(b"jpg")
    with pytest.raises(base_demo.RecusaBaseDemo, match=r"0 cadastro\(s\) e 1 evidência\(s\)"):
        _gerar(raiz, pipeline, recriar=True)


# ---------------------------------------------------------------------------- lançador
def test_lancador_troca_as_cinco_pastas_e_restaura(tmp_path, monkeypatch, capsys):
    import app_demo

    for nome in base_demo.VARIAVEIS:                         # se algo falhar no meio, o pytest devolve os cinco valores
        monkeypatch.setattr(config, nome, getattr(config, nome))
    antes = {nome: getattr(config, nome) for nome in base_demo.VARIAVEIS}
    raiz = tmp_path / "demo"
    vistos = {}
    gerar_de_verdade = base_demo.gerar

    def gerar_observado(*args, **opcoes):
        vistos.update({nome: getattr(config, nome) for nome in base_demo.VARIAVEIS})
        return gerar_de_verdade(*args, **opcoes)

    monkeypatch.setattr(base_demo, "gerar", gerar_observado)
    assert app_demo.main(["--so-gerar"], raiz=raiz) == 0
    assert vistos == base_demo.pastas(raiz)                  # durante a geração, as cinco apontavam para a base
    assert {nome: getattr(config, nome) for nome in base_demo.VARIAVEIS} == antes
    caminho = raiz / "cofre_demo.db"
    assert caminho.is_file() and base_demo.marcador(caminho) is not None
    assert len(leitura_ro.ids_usuarios(caminho)) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["demo"]
    assert "Base de demonstração pronta" in capsys.readouterr().out

    with Banco(caminho) as banco:                            # recusa do gerador: mensagem no stderr, código 2, pastas de volta
        banco.criar_usuario("Visitante", "V-001", "", 1)
    assert app_demo.main(["--so-gerar", "--recriar"], raiz=raiz) == 2
    assert "1 cadastro(s)" in capsys.readouterr().err
    assert {nome: getattr(config, nome) for nome in base_demo.VARIAVEIS} == antes
    assert app_demo.main(["--so-gerar", "--recriar", "--apagar-cadastros"], raiz=raiz) == 0
    assert len(leitura_ro.ids_usuarios(caminho)) == 2
    assert {nome: getattr(config, nome) for nome in base_demo.VARIAVEIS} == antes
