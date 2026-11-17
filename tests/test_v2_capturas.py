"""Ferramenta de capturas (`ferramentas/capturar_telas.py`): listar sem abrir nada, uma captura de ponta a
ponta com as pastas de `config` restauradas, a recusa do banco real e os quadros da câmera falsa.

A ferramenta é carregada sem importar (nem gravar bytecode): `ferramentas/` não é pacote e não ganha
`__pycache__`. Nenhum caso abre a webcam, o banco real nem uma janela visível.
"""

from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication, QImage

from cofre import amostra_lab, base_demo, config, parametros
from cofre.qt import aplicacao, extensoes
from cofre.qt import app as app_qt
from tests import apoio_v2
from tests.apoio_v2 import _config_isolada  # noqa: F401

FERRAMENTA = config.BASE_DIR / "ferramentas" / "capturar_telas.py"
DATA_REAL = config.BASE_DIR / "data"            # só para conferir que nada nasce aqui; nenhum teste abre o que há dentro


def _pastas_de_config() -> dict:
    return {nome: getattr(config, nome) for nome in base_demo.VARIAVEIS}


def _retrato_de_data_real() -> tuple:
    demo = DATA_REAL / "demo"
    return demo.exists(), demo.stat().st_mtime_ns if demo.exists() else None, (DATA_REAL / "cofre_demo.db").exists()


@pytest.fixture(autouse=True)
def _data_real_intacta():
    antes = _retrato_de_data_real()
    yield
    assert _retrato_de_data_real() == antes, "a ferramenta mexeu em data/ do projeto"


@pytest.fixture
def ferramenta(monkeypatch):
    modulo = types.ModuleType("capturar_telas_em_teste")
    modulo.__file__ = str(FERRAMENTA)
    monkeypatch.setitem(sys.modules, modulo.__name__, modulo)     # as dataclasses do módulo procuram por ele aqui
    exec(compile(FERRAMENTA.read_text(encoding="utf-8"), str(FERRAMENTA), "exec"), modulo.__dict__)
    return modulo


@pytest.fixture
def contadores(monkeypatch) -> dict[str, list]:
    """Conta o que a ferramenta constrói: Aplicacao, QGuiApplication (por `preparar_qt`) e base de demonstração."""
    chamadas: dict[str, list] = {"aplicacao": [], "preparar_qt": [], "gerar": []}
    aplicacao_real, preparar_real, gerar_real = aplicacao.Aplicacao, app_qt.preparar_qt, base_demo.gerar

    def contar(nome, funcao):
        def contada(*args, **kwargs):
            chamadas[nome].append(args)
            return funcao(*args, **kwargs)
        return contada

    monkeypatch.setattr(aplicacao, "Aplicacao", contar("aplicacao", aplicacao_real))
    monkeypatch.setattr(app_qt, "preparar_qt", contar("preparar_qt", preparar_real))
    monkeypatch.setattr(base_demo, "gerar", contar("gerar", gerar_real))
    return chamadas


def _pastas_temporarias_da_ferramenta(monkeypatch) -> list[Path]:
    """Anota as pastas que a ferramenta cria com `tempfile.mkdtemp` (para conferir que foram apagadas)."""
    criadas: list[Path] = []
    original = tempfile.mkdtemp

    def mkdtemp(*args, **kwargs):
        caminho = original(*args, **kwargs)
        criadas.append(Path(caminho))
        return caminho

    monkeypatch.setattr(tempfile, "mkdtemp", mkdtemp)
    return criadas


# ---------------------------------------------------------------------------- listar e ids
def test_listar_nao_abre_nada(ferramenta, contadores, capsys):
    havia_qt = QGuiApplication.instance() is not None
    assert ferramenta.main(["--listar"]) == 0
    assert contadores == {"aplicacao": [], "preparar_qt": [], "gerar": []}
    assert (QGuiApplication.instance() is not None) == havia_qt
    linhas = capsys.readouterr().out.split()
    fixos = [linha for linha in linhas if ":" not in linha]       # as variantes das abas entram entre os ids fixos
    assert fixos[:len(ferramenta.CAPTURAS)] == list(ferramenta.CAPTURAS)
    assert {"terminal", "terminal-negado", "area-nivel3", "painel.geral", "resultados.galeria", "quiosque-negado",
            "cena-abertura", "kit"} <= set(linhas)


def test_variantes_vem_das_classes_e_os_ids_das_abas(ferramenta, monkeypatch, capsys):
    abas = {f"{pagina}.{valor}" for pagina, lista in extensoes.ABAS.items() for valor, *_ in lista}
    assert set(ferramenta.ABAS_FIXAS) == abas and len(abas) == 9
    from cofre.qt.vm_painel_geral import PainelGeralVM
    monkeypatch.setattr(PainelGeralVM, "VARIANTES_CAPTURA", ("teste",), raising=False)
    assert ferramenta.main(["--listar"]) == 0
    linhas = capsys.readouterr().out.split()
    assert linhas[linhas.index("painel.geral") + 1] == "painel.geral:teste"
    assert ferramenta.nome_arquivo("painel.geral:teste") == "painel.geral--teste.png"
    assert ferramenta.nome_arquivo("kit") == "kit.png"


def test_so_recusa_id_desconhecido(ferramenta, contadores, tmp_path, capsys):
    assert ferramenta.main(["--so", "painel.inexistente", "--saida", str(tmp_path)]) == 2
    assert "painel.inexistente" in capsys.readouterr().err
    assert contadores["aplicacao"] == [] and contadores["gerar"] == []
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------- uma captura de ponta a ponta
def test_captura_uma_tela(ferramenta, contadores, tmp_path, monkeypatch, capsys):
    temporarias = _pastas_temporarias_da_ferramenta(monkeypatch)
    pastas, parametros_antes = _pastas_de_config(), parametros.valores_atuais()
    saida = tmp_path / "telas"
    assert ferramenta.main(["--so", "painel.geral", "--saida", str(saida)]) == 0
    texto = capsys.readouterr().out
    assert "Avisos do QML: nenhum" in texto and "Falhas: nenhuma" in texto
    assert [p.name for p in saida.iterdir()] == ["painel.geral.png"]
    imagem = QImage(str(saida / "painel.geral.png"))
    assert (imagem.width(), imagem.height()) == (1360, 860)
    assert apoio_v2.cores_distintas(imagem) >= 12
    assert _pastas_de_config() == pastas                       # as cinco pastas voltaram
    assert parametros.valores_atuais() == parametros_antes
    # o banco foi uma base de demonstração gerada na pasta temporária, que já foi apagada
    assert len(contadores["aplicacao"]) == 1 and len(contadores["gerar"]) == 1
    banco = Path(contadores["aplicacao"][0][0])
    assert banco.name == "cofre_demo.db" and banco.resolve() != base_demo.BANCO_REAL
    assert temporarias and banco.parent in temporarias
    assert not any(p.exists() for p in temporarias)


# ---------------------------------------------------------------------------- recusas
@pytest.mark.parametrize("falso, trecho", [
    (lambda *args, **kwargs: base_demo.BANCO_REAL, "banco real"),
    (lambda *args, **kwargs: (_ for _ in ()).throw(base_demo.RecusaBaseDemo("recusa de teste")), "recusa de teste"),
], ids=["banco-resolvido-real", "gerador-recusou"])
def test_recusa_banco_real(ferramenta, contadores, tmp_path, monkeypatch, capsys, falso, trecho):
    temporarias = _pastas_temporarias_da_ferramenta(monkeypatch)
    monkeypatch.setattr(base_demo, "gerar", falso)
    pastas = _pastas_de_config()
    assert ferramenta.main(["--so", "painel.geral", "--saida", str(tmp_path / "telas")]) == 2
    assert trecho in capsys.readouterr().err
    assert contadores["aplicacao"] == []                       # nenhum aplicativo sobre o banco recusado
    assert not (tmp_path / "telas").exists()
    assert _pastas_de_config() == pastas
    assert not any(p.exists() for p in temporarias)


def test_recusa_saida_dentro_de_data(ferramenta, contadores, capsys):
    assert ferramenta.main(["--so", "kit", "--saida", str(DATA_REAL / "telas")]) == 2
    assert "data/" in capsys.readouterr().err
    assert contadores == {"aplicacao": [], "preparar_qt": [], "gerar": []}


# ---------------------------------------------------------------------------- câmera falsa
def test_quadros_da_camera_falsa_tem_um_rosto(ferramenta, pipeline):
    assert len(apoio_v2.QUADROS_OK) == 3
    for foto in apoio_v2.QUADROS_OK:
        quadro = apoio_v2.quadro_webcam(foto)
        assert quadro.shape == (720, 1280, 3)
        assert len(pipeline.processar(quadro).rostos) == 1, foto.name
    # as duas pessoas da base de demonstração têm um quadro que serve, achado pelo nível
    quadros = ferramenta._Sessao._quadros_por_nivel(amostra_lab, base_demo)
    assert sorted(quadros) == [2, 3]
