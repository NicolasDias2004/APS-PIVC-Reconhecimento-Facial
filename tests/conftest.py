import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

FIX = Path(__file__).resolve().parent / "fixtures" / "pessoas"


@pytest.fixture(autouse=True)
def _pastas_temporarias(tmp_path, monkeypatch):
    """Nenhum teste escreve em data/ do projeto: fotos, evidências e relatórios vão para tmp."""
    from cofre import config
    monkeypatch.setattr(config, "FOTOS_DIR", tmp_path / "fotos")
    monkeypatch.setattr(config, "EVIDENCIAS_DIR", tmp_path / "evidencias")
    monkeypatch.setattr(config, "RELATORIOS_DIR", tmp_path / "relatorios")


@pytest.fixture(scope="session")
def pipeline():
    from cofre.pipeline import Pipeline
    return Pipeline()


@pytest.fixture
def banco(tmp_path):
    from cofre.banco import Banco
    b = Banco(tmp_path / "teste.db")
    yield b
    b.fechar()


@pytest.fixture
def fotos():
    return {
        "obama": sorted((FIX / "obama").glob("*.jpg")),
        "biden": sorted((FIX / "biden").glob("*.jpg")),
    }


@pytest.fixture(scope="session")
def qapp():
    """QGuiApplication única para os testes do aplicativo Qt (plataforma offscreen)."""
    import tests.apoio_qt  # noqa: F401  (define QT_QPA_PLATFORM antes de criar a aplicação)
    from cofre.qt.app import preparar_qt
    return preparar_qt([])
