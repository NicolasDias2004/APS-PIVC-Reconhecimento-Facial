#!/usr/bin/env python3
"""Aplicativo desktop do sistema de autenticação biométrica facial (APS PIVC).

Uso:  python app.py [--db caminho.db]
"""

import argparse

from cofre import config
from cofre.interface.app import executar

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(config.DB_PATH))
    executar(p.parse_args().db)
