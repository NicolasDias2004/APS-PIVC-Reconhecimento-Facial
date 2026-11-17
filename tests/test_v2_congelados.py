"""Conjunto congelado da versão 2: os arquivos da versão 1 continuam iguais byte a byte ao commit de
partida. O manifesto `tests/v2_congelados.json` foi gerado uma vez a partir desse commit; nenhum teste
chama o git, então a suíte roda também em uma cópia sem `.git`."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

RAIZ = Path(__file__).resolve().parent.parent
MANIFESTO = json.loads((RAIZ / "tests" / "v2_congelados.json").read_text(encoding="utf-8"))
UI = "cofre/qt/qml/Cofre/Ui"
EDITAVEIS = {"cofre/qt/aplicacao.py", "cofre/qt/app.py", f"{UI}/Main.qml", f"{UI}/Theme.qml", f"{UI}/Icones.js"}


def test_congelados_intactos():
    alterados = []
    for caminho, sha256 in MANIFESTO["arquivos"].items():
        arquivo = RAIZ / caminho
        if not arquivo.is_file():
            alterados.append(f"{caminho} (ausente)")
        elif hashlib.sha256(arquivo.read_bytes()).hexdigest() != sha256:
            alterados.append(caminho)
    assert not alterados, "Arquivos congelados alterados em relação ao commit " + MANIFESTO["commit"] + ": " + ", ".join(alterados)


def test_manifesto_cobre_o_conjunto():
    assert MANIFESTO["commit"] == "049a8ac"
    arquivos = set(MANIFESTO["arquivos"])
    assert all(len(sha256) == 64 for sha256 in MANIFESTO["arquivos"].values())

    def diretos(pasta: str, sufixo: str = "") -> set[str]:
        return {c for c in arquivos if str(PurePosixPath(c).parent) == pasta and c.endswith(sufixo)}

    assert len(diretos("cofre", ".py")) >= 18 and "cofre/__init__.py" in arquivos
    assert len({c for c in arquivos if c.startswith("cofre/interface/")}) >= 12
    assert len(diretos("cofre/qt", ".py")) >= 15
    assert len(diretos(UI)) >= 30 and f"{UI}/qmldir" in arquivos
    assert len({c for c in arquivos if c.startswith("tests/")}) >= 22
    assert {"tests/apoio_qt.py", "tests/apoio_interface.py", "tests/conftest.py"} <= arquivos
    assert len({c for c in arquivos if c.startswith("models/")}) >= 2
    assert {"main.py", "app.py", "app_qt.py", "requirements.txt"} <= arquivos

    # os cinco arquivos de código que a versão 2 pode editar ficam fora dos congelados, com as linhas originais guardadas
    assert set(MANIFESTO["editaveis"]) == EDITAVEIS
    assert not EDITAVEIS & arquivos
    for caminho, linhas in MANIFESTO["editaveis"].items():
        assert linhas and all(isinstance(linha, str) and "\n" not in linha for linha in linhas), caminho
