#!/usr/bin/env python3
"""
Sistema de Identificação e Autenticação Biométrica Facial
Cofre do Ministério do Meio Ambiente - APS PIVC (UNIP, CC 5º/6º)

Uso:
  python main.py                      -> menu interativo
  python main.py cadastrar            -> cadastro pela webcam
  python main.py cadastrar --imagens foto1.jpg foto2.jpg
  python main.py autenticar [--nivel 1|2|3] [--sem-liveness] [--didatico]
  python main.py autenticar --imagem foto.jpg --nivel 2
  python main.py usuarios | remover ID | nivel ID N | ativar ID | desativar ID
  python main.py relatorio [--html] [--csv]
  python main.py avaliar PASTA        -> métricas TAR/FAR em pasta rotulada
  python main.py demo IMAGEM          -> painel didático das 5 fases
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cofre import __version__, config, relatorios
from cofre.banco import Banco


def _pipeline():
    from cofre.pipeline import Pipeline
    return Pipeline()


def _perguntar_dados(nivel_padrao: int | None = None):
    from cofre.cadastro import DadosCadastro
    nome = input("Nome completo: ").strip()
    matricula = input("Matrícula: ").strip()
    cargo = input("Cargo/divisão: ").strip()
    while True:
        txt = input(f"Nível de acesso {dict(config.NIVEIS)} [{nivel_padrao or ''}]: ").strip() or str(nivel_padrao or "")
        if txt in ("1", "2", "3"):
            return DadosCadastro(nome, matricula, cargo, int(txt))
        print("Digite 1, 2 ou 3.")


def cmd_cadastrar(args, banco: Banco):
    from cofre import cadastro
    dados = _perguntar_dados(args.nivel)
    if banco.obter_por_matricula(dados.matricula):
        print("Já existe usuário com essa matrícula.")
        return 1
    pipe = _pipeline()
    if args.imagens:
        u, n, avisos = cadastro.cadastrar_de_imagens(banco, pipe, dados, args.imagens)
        for a in avisos:
            print("  aviso:", a)
        print(f"Cadastrado {u.nome} (id {u.id}) com {n} amostra(s).")
    else:
        u = cadastro.cadastrar_pela_camera(banco, pipe, dados, args.amostras)
        if u is None:
            print("Cadastro cancelado.")
            return 1
        print(f"Cadastrado {u.nome} (id {u.id}) com {banco.contar_amostras(u.id)} amostras.")
    return 0


def cmd_autenticar(args, banco: Banco):
    from cofre.autenticacao import TerminalAutenticacao, autenticar_imagem
    pipe = _pipeline()
    if args.imagem:
        from cofre.fase1_aquisicao import carregar_imagem
        d, _ = autenticar_imagem(banco, pipe, carregar_imagem(args.imagem), args.nivel)
        print(f"{d.resultado.value}: {d.mensagem}")
        if d.identificacao:
            print(f"similaridade = {d.identificacao.similaridade:.3f} (limiar {config.LIMIAR_COSSENO})")
        return 0 if d.concedido else 2
    if not banco.listar_usuarios(apenas_ativos=True):
        print("Nenhum usuário ativo cadastrado. Cadastre alguém primeiro.")
    TerminalAutenticacao(banco, pipe, args.nivel, liveness=not args.sem_liveness, didatico=args.didatico).executar()
    return 0


def cmd_usuarios(args, banco: Banco):
    print(relatorios.texto_usuarios(banco))
    return 0


def cmd_remover(args, banco: Banco):
    u = banco.obter_usuario(args.id)
    if not u:
        print("Usuário não encontrado.")
        return 1
    if not args.sim and input(f"Remover {u.nome} e todas as amostras? [s/N] ").lower() != "s":
        return 1
    banco.remover_usuario(u.id)
    print("Removido.")
    return 0


def cmd_nivel(args, banco: Banco):
    banco.alterar_nivel(args.id, args.nivel)
    print("Nível alterado.")
    return 0


def cmd_ativo(args, banco: Banco, ativo: bool):
    banco.definir_ativo(args.id, ativo)
    print("Usuário", "ativado." if ativo else "desativado.")
    return 0


def cmd_relatorio(args, banco: Banco):
    print(relatorios.texto_estatisticas(banco))
    print()
    print(relatorios.texto_acessos(banco, args.limite))
    if args.csv:
        print("CSV:", relatorios.exportar_csv(banco))
    if args.html:
        print("HTML:", relatorios.exportar_html(banco))
    return 0


def cmd_avaliar(args, banco: Banco):
    from cofre.avaliacao import avaliar_pasta
    print(avaliar_pasta(args.pasta, _pipeline()).resumo())
    return 0


def cmd_demo(args, banco: Banco):
    from cofre.demo import demonstrar_imagem
    destino = config.RELATORIOS_DIR / f"demo_{Path(args.imagem).stem}.png"
    demonstrar_imagem(args.imagem, _pipeline(), banco, args.nivel, salvar_em=destino, exibir=not args.sem_janela)
    print("Painel salvo em", destino)
    return 0


def menu(banco: Banco):
    opcoes = """
=== Cofre MMA - Autenticação Biométrica (v{v}) ===
 1) Autenticar (webcam)         5) Relatório de acessos
 2) Cadastrar usuário (webcam)  6) Exportar relatório HTML+CSV
 3) Listar usuários             7) Avaliar reconhecedor em pasta
 4) Remover usuário             8) Demo didática em imagem
 0) Sair
""".format(v=__version__)
    while True:
        print(opcoes)
        op = input("Opção: ").strip()
        try:
            if op == "1":
                n = input("Nível exigido da área [1/2/3] (3): ").strip() or "3"
                cmd_autenticar(argparse.Namespace(nivel=int(n), sem_liveness=False, didatico=False, imagem=None), banco)
            elif op == "2":
                cmd_cadastrar(argparse.Namespace(nivel=None, imagens=None, amostras=config.AMOSTRAS_POR_CADASTRO), banco)
            elif op == "3":
                cmd_usuarios(None, banco)
            elif op == "4":
                cmd_remover(argparse.Namespace(id=int(input("id: ")), sim=False), banco)
            elif op == "5":
                cmd_relatorio(argparse.Namespace(limite=30, csv=False, html=False), banco)
            elif op == "6":
                cmd_relatorio(argparse.Namespace(limite=10, csv=True, html=True), banco)
            elif op == "7":
                cmd_avaliar(argparse.Namespace(pasta=input("pasta: ").strip()), banco)
            elif op == "8":
                cmd_demo(argparse.Namespace(imagem=input("imagem: ").strip(), nivel=3, sem_janela=False), banco)
            elif op == "0":
                return 0
        except KeyboardInterrupt:
            print()
        except Exception as e:  # noqa: BLE001
            print("ERRO:", e)


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=str(config.DB_PATH), help="caminho do banco SQLite")
    sub = p.add_subparsers(dest="comando")

    s = sub.add_parser("cadastrar", help="cadastrar usuário autorizado")
    s.add_argument("--nivel", type=int, choices=(1, 2, 3))
    s.add_argument("--imagens", nargs="+", help="cadastrar a partir de arquivos em vez da webcam")
    s.add_argument("--amostras", type=int, default=config.AMOSTRAS_POR_CADASTRO)

    s = sub.add_parser("autenticar", help="terminal de autenticação")
    s.add_argument("--nivel", type=int, choices=(1, 2, 3), default=3, help="nível exigido pela área")
    s.add_argument("--sem-liveness", action="store_true")
    s.add_argument("--didatico", action="store_true", help="mostra o painel das 5 fases")
    s.add_argument("--imagem", help="autentica uma imagem em vez da webcam")

    sub.add_parser("usuarios", help="listar usuários")
    s = sub.add_parser("remover"); s.add_argument("id", type=int); s.add_argument("--sim", action="store_true")
    s = sub.add_parser("nivel"); s.add_argument("id", type=int); s.add_argument("nivel", type=int, choices=(1, 2, 3))
    s = sub.add_parser("ativar"); s.add_argument("id", type=int)
    s = sub.add_parser("desativar"); s.add_argument("id", type=int)

    s = sub.add_parser("relatorio", help="estatísticas e log de acessos")
    s.add_argument("--limite", type=int, default=30)
    s.add_argument("--csv", action="store_true")
    s.add_argument("--html", action="store_true")

    s = sub.add_parser("avaliar", help="métricas em pasta rotulada (pasta/pessoa/*.jpg)")
    s.add_argument("pasta")

    s = sub.add_parser("demo", help="painel didático das 5 fases em uma imagem")
    s.add_argument("imagem")
    s.add_argument("--nivel", type=int, choices=(1, 2, 3), default=3)
    s.add_argument("--sem-janela", action="store_true")
    return p


def main(argv=None) -> int:
    args = construir_parser().parse_args(argv)
    with Banco(args.db) as banco:
        if args.comando is None:
            return menu(banco)
        return {
            "cadastrar": cmd_cadastrar, "autenticar": cmd_autenticar, "usuarios": cmd_usuarios,
            "remover": cmd_remover, "nivel": cmd_nivel, "relatorio": cmd_relatorio,
            "avaliar": cmd_avaliar, "demo": cmd_demo,
            "ativar": lambda a, b: cmd_ativo(a, b, True), "desativar": lambda a, b: cmd_ativo(a, b, False),
        }[args.comando](args, banco)


if __name__ == "__main__":
    sys.exit(main())
