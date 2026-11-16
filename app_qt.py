#!/usr/bin/env python3
"""Aplicativo desktop (PySide6 + Qt Quick) do sistema de autenticação biométrica facial (APS PIVC).

Uso:  python app_qt.py [--db caminho.db]

A interface anterior (customtkinter) continua disponível em `python app.py`.
No macOS, rode pelo Terminal: é o aplicativo que abre o programa que recebe a permissão da câmera.
"""

import argparse
import sys

from cofre import config

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=str(config.DB_PATH), help="arquivo SQLite (padrão: data/cofre.db)")
    args = p.parse_args()
    from cofre.qt.app import executar
    sys.exit(executar(args.db))
