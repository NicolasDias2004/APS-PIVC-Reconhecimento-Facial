#!/usr/bin/env python3
"""Gera docs/LISTAGEM-CODIGO.md com todos os arquivos-fonte do projeto
(item "Relatório com as linhas de código" exigido pela APS)."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
QML = RAIZ / "cofre" / "qt" / "qml" / "Cofre" / "Ui"
ARQUIVOS = [RAIZ / "main.py", RAIZ / "app.py", RAIZ / "app_qt.py", RAIZ / "app_demo.py", *sorted((RAIZ / "cofre").glob("*.py")),
            *sorted((RAIZ / "cofre" / "interface").glob("*.py")), *sorted((RAIZ / "cofre" / "qt").glob("*.py")),
            *sorted(QML.glob("*.qml")), *sorted(QML.glob("*.js")), QML / "qmldir",
            *sorted((RAIZ / "tests").glob("*.py")),
            RAIZ / "ferramentas" / "capturar_telas.py", RAIZ / "ferramentas" / "listar_codigo.py", RAIZ / "requirements.txt"]
ARQUIVOS = [a for a in ARQUIVOS if a.exists()]
DESTINO = RAIZ / "docs" / "LISTAGEM-CODIGO.md"
LINGUAGEM = {".py": "python", ".qml": "qml", ".js": "javascript"}

partes = ["# Listagem de código-fonte\n",
          "Sistema de Identificação e Autenticação Biométrica Facial - APS PIVC\n"]
total = 0
for arq in ARQUIVOS:
    texto = arq.read_text(encoding="utf-8")
    linhas = texto.count("\n")
    total += linhas
    rel = arq.relative_to(RAIZ)
    partes.append(f"\n## `{rel}` ({linhas} linhas)\n\n```{LINGUAGEM.get(arq.suffix, 'text')}\n{texto}\n```\n")
partes.insert(2, f"\nTotal: {len(ARQUIVOS)} arquivos, {total} linhas.\n")
DESTINO.write_text("".join(partes), encoding="utf-8")
print(f"Gerado {DESTINO} ({total} linhas de código em {len(ARQUIVOS)} arquivos)")
