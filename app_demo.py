#!/usr/bin/env python3
"""Abre o aplicativo desktop na base de demonstração, sem tocar nos dados reais.

Uso:
  python app_demo.py                               cria data/demo/ se não existir e abre o aplicativo nela
  python app_demo.py --so-gerar                    gera e sai (não abre janela)
  python app_demo.py --recriar                     refaz a base antes de abrir; recusa se houver cadastro
                                                   ou evidência feitos nela
  python app_demo.py --recriar --apagar-cadastros  refaz apagando também o que foi cadastrado na base de demonstração

A base tem duas pessoas (os dois retratos de domínio público das fotos de teste) e um histórico
fictício de 30 dias. Banco, fotos, evidências e relatórios ficam todos em data/demo/: abrir só com
`app_qt.py --db` trocaria o banco e deixaria fotos e evidências nas pastas reais.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None, raiz: Path | None = None) -> int:
    """Aponta as cinco pastas de `config` para a base de demonstração, gera a base se preciso e abre o
    aplicativo nela; no fim as pastas voltam ao que eram. Devolve o código de saída."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--so-gerar", action="store_true", help="gera a base e sai, sem abrir a janela")
    p.add_argument("--recriar", action="store_true", help="refaz a base de demonstração antes de abrir")
    p.add_argument("--apagar-cadastros", action="store_true",
                   help="com --recriar: apaga também cadastros e evidências feitos na base de demonstração")
    args = p.parse_args(argv)
    if args.apagar_cadastros and not args.recriar:
        p.error("--apagar-cadastros só vale junto com --recriar")

    from cofre import base_demo, config
    raiz = Path(raiz) if raiz is not None else base_demo.RAIZ_PADRAO
    alvo = base_demo.pastas(raiz)
    antes = {nome: getattr(config, nome) for nome in base_demo.VARIAVEIS}
    # trocadas antes de criar o banco ou o aplicativo: o cadastro e o terminal leem as pastas na hora de gravar
    config.DATA_DIR = alvo["DATA_DIR"]
    config.DB_PATH = alvo["DB_PATH"]
    config.FOTOS_DIR = alvo["FOTOS_DIR"]
    config.EVIDENCIAS_DIR = alvo["EVIDENCIAS_DIR"]
    config.RELATORIOS_DIR = alvo["RELATORIOS_DIR"]
    try:
        base_demo.gerar(raiz, recriar=args.recriar, apagar_cadastros=args.apagar_cadastros, raiz_permitida=raiz)
        if args.so_gerar:
            print(f"Base de demonstração pronta em {raiz}")
            return 0
        from cofre.qt.app import executar
        return executar(str(alvo["DB_PATH"]))
    except base_demo.RecusaBaseDemo as recusa:
        print(f"Base de demonstração: {recusa}", file=sys.stderr)
        return 2
    finally:
        config.DATA_DIR = antes["DATA_DIR"]
        config.DB_PATH = antes["DB_PATH"]
        config.FOTOS_DIR = antes["FOTOS_DIR"]
        config.EVIDENCIAS_DIR = antes["EVIDENCIAS_DIR"]
        config.RELATORIOS_DIR = antes["RELATORIOS_DIR"]


if __name__ == "__main__":
    sys.exit(main())
