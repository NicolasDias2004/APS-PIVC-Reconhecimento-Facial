# Listagem de código-fonte
Sistema de Identificação e Autenticação Biométrica Facial - APS PIVC

Total: 102 arquivos, 15982 linhas.

## `main.py` (225 linhas)

```python
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

```

## `app.py` (15 linhas)

```python
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

```

## `app_qt.py` (20 linhas)

```python
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

```

## `cofre/__init__.py` (24 linhas)

```python
"""
Pacote `cofre`: sistema de identificação e autenticação biométrica facial
para controle de acesso ao cofre do Ministério do Meio Ambiente (APS PIVC).

O código é organizado seguindo as cinco fases do processamento de imagens digitais:

    fase1_aquisicao        -> captura da imagem (webcam ou arquivo)
    fase2_preprocessamento -> correção de iluminação, ruído e tamanho
    fase3_segmentacao      -> detecção e recorte/alinhamento do rosto
    fase4_representacao    -> extração do vetor de características (embedding)
    fase5_reconhecimento   -> comparação com a base e decisão de acesso

Módulos de apoio: banco (SQLite), liveness (anti-fraude), hud (interface),
cadastro, autenticacao, relatorios e avaliacao.
"""

__version__ = "1.0.0"

# Silencia avisos internos do OpenCV 5 ("Targets are not supported by the new graph engine")
try:  # pragma: no cover
    import cv2 as _cv2
    _cv2.utils.logging.setLogLevel(_cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:  # noqa: BLE001
    pass

```

## `cofre/areas.py` (169 linhas)

```python
"""
Conteúdo das áreas protegidas, liberado depois de uma autenticação CONCEDIDA no terminal.

Os dados são fictícios e determinísticos (mesma semente → mesmo conteúdo), só para a
demonstração: nada aqui consulta sistemas reais. A regra de herança é a dos níveis do
sistema: quem tem nível N enxerga as áreas de nível 1 até N (`areas_liberadas`).

Este módulo não decide acesso. Quem decide é `fase5_reconhecimento.decidir_acesso`, no
terminal; aqui só se monta o que mostrar DEPOIS que o backend concedeu.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from . import config

DESCRICAO_AREA = {
    1: "Comunicados, agenda e indicadores públicos do Ministério.",
    2: "Orçamento, metas e aprovações das divisões.",
    3: "Inventário, sensores e registro de retiradas do cofre de toxinas.",
}


def areas_liberadas(nivel_usuario: int) -> list[int]:
    """Níveis de área que um usuário com `nivel_usuario` pode abrir (herança: N libera 1..N)."""
    return [n for n in sorted(config.NIVEIS) if n <= int(nivel_usuario)]


def resumo_areas(nivel_usuario: int) -> list[dict]:
    liberadas = set(areas_liberadas(nivel_usuario))
    return [{"nivel": n, "titulo": config.AREAS[n], "descricao": DESCRICAO_AREA.get(n, ""),
             "liberada": n in liberadas} for n in sorted(config.NIVEIS)]


def conteudo(nivel: int, hoje: date | None = None) -> dict:
    """Conteúdo fictício da área de nível `nivel`. Levanta ValueError para nível inexistente."""
    nivel = int(nivel)
    if nivel not in config.NIVEIS:
        raise ValueError(f"Área inexistente: {nivel}")
    hoje = hoje or date.today()
    return {1: _area_comum, 2: _area_diretores, 3: _area_cofre}[nivel](hoje)


# --------------------------------------------------------------------------- nível 1
def _area_comum(hoje: date) -> dict:
    r = random.Random(101)
    dias = [hoje - timedelta(days=6 - i) for i in range(7)]
    base = 38
    qualidade = []
    for d in dias:
        base = max(18, min(95, base + r.randint(-9, 9)))
        qualidade.append({"dia": d.strftime("%d/%m"), "valor": base})
    return {
        "titulo": config.AREAS[1],
        "comunicados": [
            {"tipo": "aviso", "data": (hoje - timedelta(days=0)).strftime("%d/%m"),
             "titulo": "Manutenção do sistema de climatização no bloco B",
             "texto": "Entre 13h e 15h o 3º andar ficará sem climatização. Reuniões podem usar as salas do bloco A."},
            {"tipo": "info", "data": (hoje - timedelta(days=1)).strftime("%d/%m"),
             "titulo": "Semana do Meio Ambiente: inscrições abertas",
             "texto": "Oficinas de compostagem e de coleta seletiva no auditório. Vagas limitadas por setor."},
            {"tipo": "info", "data": (hoje - timedelta(days=2)).strftime("%d/%m"),
             "titulo": "Novo cardápio do restaurante",
             "texto": "Opção vegetariana diária a partir de segunda. Sugestões pelo ramal 4120."},
            {"tipo": "ok", "data": (hoje - timedelta(days=4)).strftime("%d/%m"),
             "titulo": "Credenciais do estacionamento renovadas",
             "texto": "As credenciais de 2026 já valem nas cancelas. As antigas expiram no fim do mês."},
        ],
        "agenda": [
            {"hora": "09:00", "titulo": "Café com a Secretaria de Biodiversidade", "local": "Sala 204"},
            {"hora": "10:30", "titulo": "Treinamento: SEI para iniciantes", "local": "Laboratório 1"},
            {"hora": "14:00", "titulo": "Reunião geral do Departamento de Florestas", "local": "Auditório"},
            {"hora": "16:30", "titulo": "Plantão de dúvidas de RH", "local": "Sala 110"},
        ],
        "indicadores": [
            {"nome": "Focos de queimada (24 h)", "valor": "1.284", "variacao": -12, "unidade": "focos"},
            {"nome": "Unidades de conservação", "valor": "335", "variacao": 2, "unidade": "federais"},
            {"nome": "Alertas de desmatamento", "valor": "412", "variacao": -8, "unidade": "km² no mês"},
            {"nome": "Qualidade do ar (DF)", "valor": str(qualidade[-1]["valor"]), "variacao": qualidade[-1]["valor"] - qualidade[-2]["valor"], "unidade": "IQAr"},
        ],
        "qualidadeAr": qualidade,
        "ramais": [
            {"setor": "Recepção", "ramal": "4000"}, {"setor": "Protocolo", "ramal": "4015"},
            {"setor": "Recursos Humanos", "ramal": "4100"}, {"setor": "Suporte de TI", "ramal": "4200"},
            {"setor": "Segurança", "ramal": "4300"}, {"setor": "Restaurante", "ramal": "4120"},
        ],
    }


# --------------------------------------------------------------------------- nível 2
def _area_diretores(hoje: date) -> dict:
    r = random.Random(202)
    divisoes = []
    for nome, orcamento in (("Florestas", 48.2), ("Biodiversidade", 36.9), ("Recursos Hídricos", 29.4),
                            ("Qualidade Ambiental", 22.7), ("Educação Ambiental", 11.3)):
        exec_ = round(orcamento * r.uniform(0.42, 0.88), 1)
        divisoes.append({"nome": nome, "orcamento": orcamento, "executado": exec_,
                         "fracao": round(exec_ / orcamento, 3), "meta": r.randint(68, 94),
                         "servidores": r.randint(38, 160)})
    prioridades = ["alta", "média", "baixa"]
    aprovacoes = []
    assuntos = [("Licença de operação: hidrelétrica do Rio Claro", "Divisão de Recursos Hídricos"),
                ("Plano de manejo da Floresta Nacional de Ipanema", "Divisão de Florestas"),
                ("Convênio com universidades para monitoramento de fauna", "Divisão de Biodiversidade"),
                ("Compra de sensores de qualidade do ar", "Divisão de Qualidade Ambiental"),
                ("Edital de educação ambiental nas escolas", "Divisão de Educação Ambiental"),
                ("Contratação de brigadistas para a estação seca", "Divisão de Florestas")]
    for i, (assunto, origem) in enumerate(assuntos):
        aprovacoes.append({"id": f"SEI-{2026}-{10400 + i * 37}", "assunto": assunto, "origem": origem,
                           "prazo": (hoje + timedelta(days=r.randint(1, 20))).strftime("%d/%m"),
                           "prioridade": prioridades[i % 3], "valor": f"R$ {r.uniform(0.3, 9.8):.1f} mi"})
    total_orc = sum(d["orcamento"] for d in divisoes)
    total_exec = sum(d["executado"] for d in divisoes)
    return {
        "titulo": config.AREAS[2],
        "resumo": {"orcamento": f"R$ {total_orc:.1f} mi", "executado": f"R$ {total_exec:.1f} mi",
                   "fracao": round(total_exec / total_orc, 3), "aprovacoesPendentes": len(aprovacoes),
                   "divisoes": len(divisoes)},
        "divisoes": divisoes,
        "aprovacoes": aprovacoes,
        "metas": [{"nome": "Área reflorestada", "atual": 1.84, "alvo": 2.5, "unidade": "mil ha"},
                  {"nome": "Licenças analisadas no prazo", "atual": 81, "alvo": 90, "unidade": "%"},
                  {"nome": "Municípios com coleta seletiva", "atual": 1372, "alvo": 1600, "unidade": ""},
                  {"nome": "Unidades com plano de manejo", "atual": 212, "alvo": 335, "unidade": ""}],
    }


# --------------------------------------------------------------------------- nível 3
def _area_cofre(hoje: date) -> dict:
    r = random.Random(303)
    agentes = [("Tetrodotoxina", "Marinha", "crítico"), ("Batracotoxina", "Anfíbios", "crítico"),
               ("Ricina", "Vegetal", "alto"), ("Crotoxina", "Serpentes", "alto"),
               ("Microcistina-LR", "Cianobactérias", "moderado"), ("Palitoxina", "Corais", "crítico"),
               ("Abrina", "Vegetal", "alto"), ("Saxitoxina", "Dinoflagelados", "alto")]
    lotes = []
    for i, (agente, origem, risco) in enumerate(agentes):
        lotes.append({"codigo": f"TX-{2600 + i * 13:04d}", "agente": agente, "origem": origem, "risco": risco,
                      "quantidade": f"{r.uniform(0.2, 12.0):.1f}", "unidade": "mg",
                      "validade": (hoje + timedelta(days=r.randint(40, 700))).strftime("%d/%m/%Y"),
                      "prateleira": f"{'ABCD'[i % 4]}{i // 4 + 1}"})
    temperatura, t = [], -78.0
    for h in range(24):
        t = max(-82.0, min(-74.0, t + r.uniform(-0.6, 0.6)))
        temperatura.append({"hora": f"{(datetime.now().hour - 23 + h) % 24:02d}h", "valor": round(t, 1)})
    retiradas = [
        {"data": (hoje - timedelta(days=d)).strftime("%d/%m"), "lote": lotes[i]["codigo"], "agente": lotes[i]["agente"],
         "responsavel": nome, "finalidade": fim, "quantidade": f"{q:.1f} mg"}
        for d, i, nome, fim, q in ((2, 0, "Lab. de Toxinologia", "Antiveneno experimental", 0.4),
                                   (9, 3, "Instituto Butantan", "Padrão de referência", 1.0),
                                   (17, 4, "Lab. de Qualidade da Água", "Calibração de ensaio", 0.2),
                                   (31, 2, "Perícia Federal", "Contraprova", 0.5))]
    return {
        "titulo": config.AREAS[3],
        "sensores": [
            {"nome": "Temperatura", "valor": f"{temperatura[-1]['valor']:.1f}", "unidade": "°C", "faixa": "-82 a -74", "ok": True},
            {"nome": "Umidade", "valor": "31", "unidade": "%", "faixa": "20 a 40", "ok": True},
            {"nome": "Pressão interna", "valor": "-12", "unidade": "Pa", "faixa": "-20 a -5", "ok": True},
            {"nome": "Filtro HEPA", "valor": "94", "unidade": "%", "faixa": "≥ 85", "ok": True},
        ],
        "temperatura": temperatura,
        "lotes": lotes,
        "retiradas": retiradas,
        "portas": [{"nome": "Antecâmara", "estado": "fechada"}, {"nome": "Câmara fria", "estado": "fechada"},
                   {"nome": "Armário de contenção", "estado": "lacrado"}, {"nome": "Exaustão", "estado": "ativa"}],
        "totais": {"lotes": len(lotes), "criticos": sum(1 for l in lotes if l["risco"] == "crítico"),
                   "retiradas30d": sum(1 for x in retiradas if True), "vencendo": sum(1 for l in lotes if int(l["validade"][6:]) == hoje.year)},
    }

```

## `cofre/autenticacao.py` (326 linhas)

```python
"""
Autenticação em tempo real (o "terminal" na porta do cofre).

Máquina de estados por frame:
  AGUARDANDO  : nenhum rosto / rosto instável
  CONFIRMANDO : mesma identidade em N frames seguidos (reduz falsos positivos)
  LIVENESS    : desafio de movimento (se ativo)
  RESULTADO   : exibe o veredito por alguns segundos e registra no log
  BLOQUEADO   : após várias negações seguidas
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime
from enum import Enum

import cv2
import numpy as np

from . import config, hud
from .banco import Banco
from .fase1_aquisicao import FonteCamera
from .fase5_reconhecimento import Decisao, Identificacao, Reconhecedor, Resultado, decidir_acesso
from .liveness import ControleTentativas, DesafioMovimento, EtapaLiveness
from .pipeline import Pipeline, RostoProcessado


class Estado(str, Enum):
    AGUARDANDO = "AGUARDANDO"
    CONFIRMANDO = "CONFIRMANDO"
    LIVENESS = "LIVENESS"
    RESULTADO = "RESULTADO"
    BLOQUEADO = "BLOQUEADO"


class Confirmador:
    """Exige a mesma identidade (ou 'desconhecido') em `n` frames consecutivos."""

    def __init__(self, n: int = config.FRAMES_CONFIRMACAO):
        self.n = n
        self._fila: deque[tuple[int | None, float]] = deque(maxlen=n)

    def limpar(self) -> None:
        self._fila.clear()

    def adicionar(self, ident: Identificacao) -> Identificacao | None:
        chave = ident.usuario.id if ident.reconhecido else None
        self._fila.append((chave, ident.similaridade))
        if len(self._fila) < self.n:
            return None
        if len({c for c, _ in self._fila}) != 1:
            return None
        media = float(np.mean([s for _, s in self._fila]))
        return Identificacao(ident.usuario if chave is not None else None, media, ident.segunda_similaridade)

    @property
    def progresso(self) -> float:
        return len(self._fila) / self.n


def salvar_evidencia(frame: np.ndarray, rotulo: str) -> str:
    config.EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
    nome = f"{datetime.now():%Y%m%d_%H%M%S}_{rotulo}.jpg"
    caminho = config.EVIDENCIAS_DIR / nome
    cv2.imwrite(str(caminho), frame)
    return str(caminho)


def registrar(banco: Banco, decisao: Decisao, frame: np.ndarray | None) -> None:
    ident = decisao.identificacao
    u = ident.usuario if ident and ident.reconhecido else None
    evidencia = None
    if frame is not None and not decisao.concedido:
        evidencia = salvar_evidencia(frame, decisao.resultado.value)
    banco.registrar_acesso(
        usuario_id=u.id if u else None,
        nome_detectado=u.nome if u else None,
        nivel_usuario=u.nivel if u else None,
        nivel_exigido=decisao.nivel_exigido,
        similaridade=ident.similaridade if ident else None,
        resultado=decisao.resultado.value,
        mensagem=decisao.mensagem,
        evidencia=evidencia,
    )


class TerminalAutenticacao:
    def __init__(self, banco: Banco, pipeline: Pipeline, nivel_exigido: int = 3,
                 liveness: bool = config.LIVENESS_ATIVO, didatico: bool = False):
        self.banco = banco
        self.pipeline = pipeline
        self.reconhecedor = Reconhecedor(banco)
        self.nivel_exigido = nivel_exigido
        self.liveness_ativo = liveness
        self.didatico = didatico
        self.estado = Estado.AGUARDANDO
        self.confirmador = Confirmador()
        self.desafio = DesafioMovimento()
        self.tentativas = ControleTentativas()
        self._ident_confirmada: Identificacao | None = None
        self._decisao: Decisao | None = None
        self._resultado_desde = 0.0
        self._frame_decisao: np.ndarray | None = None
        self.orientacao = ""      # instrução para a pessoa quando a pose/qualidade não serve ("" = ok)

    # ------------------------------------------------------------------ lógica
    def _finalizar(self, decisao: Decisao, frame: np.ndarray) -> None:
        self._decisao = decisao
        self._resultado_desde = time.time()
        self.estado = Estado.RESULTADO
        registrar(self.banco, decisao, frame)
        if decisao.concedido:
            self.tentativas.registrar_sucesso()
        elif self.tentativas.registrar_falha():
            self.banco.registrar_acesso(
                usuario_id=None, nome_detectado=None, nivel_usuario=None, nivel_exigido=self.nivel_exigido,
                similaridade=None, resultado=Resultado.BLOQUEADO.value,
                mensagem=f"Terminal bloqueado por {config.BLOQUEIO_SEG:.0f}s após {config.MAX_TENTATIVAS_FALHAS} falhas",
            )
        self.confirmador.limpar()

    def passo(self, frame: np.ndarray, principal: RostoProcessado | None, n_rostos: int) -> None:
        """Avança a máquina de estados com o resultado do pipeline para este frame."""
        agora = time.time()
        if self.estado is Estado.RESULTADO:
            if agora - self._resultado_desde >= config.TEMPO_EXIBIR_RESULTADO_SEG:
                self.estado = Estado.BLOQUEADO if self.tentativas.bloqueado else Estado.AGUARDANDO
                self._decisao = None
            return
        if self.tentativas.bloqueado:
            self.estado = Estado.BLOQUEADO
            return
        if self.estado is Estado.BLOQUEADO:
            self.estado = Estado.AGUARDANDO

        if n_rostos > 1 and config.BLOQUEAR_MULTIPLOS_ROSTOS:
            if self.estado in (Estado.CONFIRMANDO, Estado.LIVENESS):
                self._finalizar(Decisao(Resultado.NEGADO_MULTIPLOS, None, self.nivel_exigido,
                                        "Mais de uma pessoa diante do terminal."), frame)
            self.confirmador.limpar()
            return

        if principal is None:
            self.orientacao = ""
            if self.estado is Estado.LIVENESS:
                self.desafio.atualizar(None)
                if self.desafio.etapa is EtapaLiveness.FALHOU:
                    self._finalizar(Decisao(Resultado.NEGADO_LIVENESS, self._ident_confirmada, self.nivel_exigido,
                                            "Prova de vida não concluída."), frame)
            else:
                self.estado = Estado.AGUARDANDO
                self.confirmador.limpar()
            return

        if self.estado in (Estado.AGUARDANDO, Estado.CONFIRMANDO):
            # Entrada que não serve (rosto virado, inclinado, cabeça baixa, borrado) não é
            # avaliada: o frame é ignorado, sem contar como tentativa nem como falha.
            self.orientacao = principal.rosto.problema_pose() or (
                "" if principal.qualidade.aprovada else f"Ajuste: {principal.qualidade.motivo}")
            if self.orientacao:
                return
            self.estado = Estado.CONFIRMANDO
            ident = self.reconhecedor.identificar(principal.embedding)
            confirmada = self.confirmador.adicionar(ident)
            if confirmada is None:
                return
            self._ident_confirmada = confirmada
            if confirmada.reconhecido and self.liveness_ativo:
                self.desafio.iniciar()
                self.estado = Estado.LIVENESS
            else:
                self._finalizar(decidir_acesso(confirmada, self.nivel_exigido), frame)
            return

        if self.estado is Estado.LIVENESS:
            self.orientacao = ""
            atual = self.reconhecedor.identificar(principal.embedding)
            confirmada = self._ident_confirmada
            if (confirmada is None or confirmada.usuario is None or not atual.reconhecido
                    or atual.usuario is None or atual.usuario.id != confirmada.usuario.id):
                self._ident_confirmada = None
                self._finalizar(Decisao(Resultado.NEGADO_LIVENESS, None, self.nivel_exigido,
                                        "Identidade não confirmada durante a prova de vida. Tente novamente."), frame)
                return

            etapa = self.desafio.atualizar(principal.rosto.yaw())
            if etapa is EtapaLiveness.APROVADO:
                self._ident_confirmada = atual
                self._finalizar(decidir_acesso(atual, self.nivel_exigido), frame)
            elif etapa is EtapaLiveness.FALHOU:
                self._finalizar(Decisao(Resultado.NEGADO_LIVENESS, self._ident_confirmada, self.nivel_exigido,
                                        "Prova de vida falhou (rosto estático?)."), frame)

    @property
    def decisao_atual(self) -> Decisao | None:
        return self._decisao

    def identificacao_atual(self, principal: RostoProcessado | None) -> Identificacao | None:
        if self.estado in (Estado.LIVENESS, Estado.RESULTADO):
            return self._ident_confirmada
        if principal is not None:
            return self.reconhecedor.identificar(principal.embedding)
        return None

    def encerrar_resultado(self) -> None:
        """Fecha o RESULTADO antes do tempo (a área liberada foi encerrada): volta a aguardar, ou
        fica bloqueado se o controle de tentativas ainda estiver bloqueado."""
        if self.estado is Estado.RESULTADO:
            self._decisao = None
            self.estado = Estado.BLOQUEADO if self.tentativas.bloqueado else Estado.AGUARDANDO
            self.confirmador.limpar()

    def definir_nivel(self, nivel: int) -> None:
        self.nivel_exigido = nivel
        self.confirmador.limpar()
        if self.estado is not Estado.RESULTADO:
            self.estado = Estado.AGUARDANDO

    def status(self) -> dict:
        """Resumo do estado para interfaces (sem depender do OpenCV)."""
        d = self._decisao
        return {
            "estado": self.estado.value,
            "nivel_exigido": self.nivel_exigido,
            "area": config.AREAS[self.nivel_exigido],
            "progresso_confirmacao": self.confirmador.progresso,
            "orientacao": self.orientacao if self.estado in (Estado.AGUARDANDO, Estado.CONFIRMANDO) else "",
            "liveness_instrucao": self.desafio.instrucao if self.estado is Estado.LIVENESS else "",
            "liveness_restante": self.desafio.tempo_restante if self.estado is Estado.LIVENESS else 0.0,
            "bloqueado_restante": self.tentativas.segundos_restantes,
            "decisao": None if d is None else {
                "resultado": d.resultado.value, "concedido": d.concedido, "mensagem": d.mensagem,
                "nome": d.identificacao.rotulo if d.identificacao else None,
                "similaridade": d.identificacao.similaridade if d.identificacao else None,
            },
            "galeria": self.reconhecedor.total_amostras,
        }

    # ------------------------------------------------------------------ HUD
    def desenhar(self, frame: np.ndarray, res, fps: float) -> np.ndarray:
        tela = frame.copy()
        area = config.AREAS[self.nivel_exigido]
        linhas = [(f"COFRE MMA  |  Area: {area}  (nivel {self.nivel_exigido})", hud.BRANCO)]
        for i, rp in enumerate(res.rostos):
            cor, rotulo = hud.AMARELO, "..."
            if i == 0 and self.estado in (Estado.CONFIRMANDO, Estado.LIVENESS, Estado.RESULTADO):
                ident = self._ident_confirmada if self.estado is not Estado.CONFIRMANDO else \
                    self.reconhecedor.identificar(rp.embedding)
                if ident is not None:
                    cor = hud.VERDE if ident.reconhecido else hud.VERMELHO
                    rotulo = f"{ident.rotulo} {ident.similaridade:.2f}"
                    if ident.reconhecido:
                        rotulo += f"  N{ident.usuario.nivel}"
            elif i > 0:
                cor, rotulo = hud.VERMELHO, "extra"
            hud.caixa_rosto(tela, rp.rosto, cor, rotulo)
            hud.pontos_faciais(tela, rp.rosto)
        if self.estado in (Estado.AGUARDANDO, Estado.CONFIRMANDO) and self.orientacao:
            linhas.append((self.orientacao, hud.LARANJA))
        elif self.estado is Estado.AGUARDANDO:
            linhas.append(("Aguardando: posicione-se de frente para a camera", hud.AMARELO))
        elif self.estado is Estado.CONFIRMANDO:
            linhas.append((f"Confirmando identidade... {int(self.confirmador.progresso * 100)}%", hud.AZUL))
            if res.principal is not None:
                ident = self.reconhecedor.identificar(res.principal.embedding)
                hud.barra_similaridade(tela, (12, 76), 220, ident.similaridade, config.LIMIAR_COSSENO)
        elif self.estado is Estado.LIVENESS:
            linhas.append((f"Prova de vida: {self.desafio.instrucao}  ({self.desafio.tempo_restante:.0f}s)", hud.LARANJA))
            if res.principal is not None:
                yaw = res.principal.rosto.yaw()
                linhas.append((f"yaw = {yaw:+.2f}", hud.CINZA))
        elif self.estado is Estado.BLOQUEADO:
            linhas.append((f"TERMINAL BLOQUEADO por {self.tentativas.segundos_restantes:.0f}s", hud.VERMELHO))
        if self.estado is Estado.RESULTADO and self._decisao is not None:
            d = self._decisao
            hud.faixa_resultado(tela, ("ACESSO CONCEDIDO: " if d.concedido else "ACESSO NEGADO: ") + d.mensagem,
                                hud.VERDE if d.concedido else hud.VERMELHO)
        hud.painel_topo(tela, linhas)
        extras = "ON" if self.liveness_ativo else "OFF"
        hud.rodape(tela, f"[1][2][3] area  [l] liveness:{extras}  [d] didatico  [r] recarregar  [q] sair   fps {fps:.0f}  "
                         f"galeria {self.reconhecedor.total_amostras} amostras")
        return tela

    # ------------------------------------------------------------------ loop
    def executar(self) -> None:
        janela = "Autenticacao - cofre MMA"
        with FonteCamera() as cam:
            for frame in cam.frames():
                res = self.pipeline.processar(frame)
                self.passo(frame, res.principal, len(res.rostos))
                tela = self.desenhar(frame, res, cam.fps_medido)
                cv2.imshow(janela, tela)
                if self.didatico:
                    cv2.imshow("Pipeline (5 fases)", hud.mosaico(res.etapas_didaticas(), lado=180, colunas=5))
                tecla = cv2.waitKey(1) & 0xFF
                if tecla in (ord("q"), 27):
                    break
                if tecla in (ord("1"), ord("2"), ord("3")):
                    self.definir_nivel(int(chr(tecla)))
                elif tecla == ord("l"):
                    self.liveness_ativo = not self.liveness_ativo
                elif tecla == ord("d"):
                    self.didatico = not self.didatico
                    if not self.didatico:
                        cv2.destroyWindow("Pipeline (5 fases)")
                elif tecla == ord("r"):
                    self.reconhecedor.recarregar()
        cv2.destroyAllWindows()


def autenticar_imagem(banco: Banco, pipeline: Pipeline, frame: np.ndarray, nivel_exigido: int,
                      registrar_log: bool = True) -> tuple[Decisao, object]:
    """Autenticação 'offline' em uma imagem (testes, demonstração, scanner)."""
    reconhecedor = Reconhecedor(banco)
    res = pipeline.processar(frame)
    if len(res.rostos) > 1 and config.BLOQUEAR_MULTIPLOS_ROSTOS:
        decisao = Decisao(Resultado.NEGADO_MULTIPLOS, None, nivel_exigido, "Mais de uma pessoa na imagem.")
    elif res.principal is None:
        decisao = Decisao(Resultado.NEGADO_DESCONHECIDO, None, nivel_exigido, "Nenhum rosto detectado.")
    else:
        decisao = decidir_acesso(reconhecedor.identificar(res.principal.embedding), nivel_exigido)
    if registrar_log:
        registrar(banco, decisao, frame)
    return decisao, res

```

## `cofre/avaliacao.py` (86 linhas)

```python
"""
Avaliação quantitativa do reconhecedor em um conjunto rotulado de imagens.

Estrutura esperada:  pasta/<nome_da_pessoa>/*.jpg

Para todos os pares de imagens calcula a similaridade do cosseno e separa em
pares genuínos (mesma pessoa) e impostores (pessoas diferentes). Reporta, para o
limiar configurado e para uma varredura de limiares, as taxas:
  TAR (True Accept Rate)  = genuínos aceitos / genuínos
  FAR (False Accept Rate) = impostores aceitos / impostores
  FRR = 1 - TAR
e o EER (ponto em que FAR ≈ FRR). Esses números vão direto para a dissertação.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import config
from .fase1_aquisicao import carregar_imagem, listar_imagens
from .fase4_representacao import similaridade_cosseno
from .pipeline import Pipeline


@dataclass
class ResultadoAvaliacao:
    genuinos: list[float] = field(default_factory=list)
    impostores: list[float] = field(default_factory=list)
    sem_rosto: list[str] = field(default_factory=list)
    pessoas: dict[str, int] = field(default_factory=dict)

    def taxas(self, limiar: float) -> dict[str, float]:
        g, i = np.asarray(self.genuinos), np.asarray(self.impostores)
        tar = float((g >= limiar).mean()) if g.size else float("nan")
        far = float((i >= limiar).mean()) if i.size else float("nan")
        return {"limiar": limiar, "TAR": tar, "FRR": 1 - tar, "FAR": far}

    def varredura(self, passos: int = 41) -> list[dict[str, float]]:
        return [self.taxas(t) for t in np.linspace(0.0, 1.0, passos)]

    def eer(self) -> tuple[float, float]:
        """(limiar, taxa) onde |FAR - FRR| é mínimo."""
        melhor = min(self.varredura(201), key=lambda r: abs(r["FAR"] - r["FRR"]))
        return melhor["limiar"], (melhor["FAR"] + melhor["FRR"]) / 2

    def resumo(self) -> str:
        g, i = np.asarray(self.genuinos), np.asarray(self.impostores)
        t = self.taxas(config.LIMIAR_COSSENO)
        eer_l, eer_v = self.eer()
        partes = [
            f"Pessoas: {len(self.pessoas)}  Imagens: {sum(self.pessoas.values())}  Sem rosto: {len(self.sem_rosto)}",
            f"Pares genuínos: {g.size}  (média {g.mean():.3f}, mín {g.min():.3f})" if g.size else "Pares genuínos: 0",
            f"Pares impostores: {i.size}  (média {i.mean():.3f}, máx {i.max():.3f})" if i.size else "Pares impostores: 0",
            f"Limiar configurado {t['limiar']:.3f}:  TAR {t['TAR']:.1%}  FRR {t['FRR']:.1%}  FAR {t['FAR']:.1%}",
            f"EER ≈ {eer_v:.1%} no limiar {eer_l:.3f}",
            "",
            "limiar   TAR     FAR",
        ]
        for r in self.varredura(11):
            partes.append(f"{r['limiar']:.2f}   {r['TAR']:6.1%}  {r['FAR']:6.1%}")
        return "\n".join(partes)


def avaliar_pasta(pasta: str | Path, pipeline: Pipeline | None = None) -> ResultadoAvaliacao:
    pipeline = pipeline or Pipeline()
    pasta = Path(pasta)
    res = ResultadoAvaliacao()
    embeddings: list[tuple[str, np.ndarray]] = []
    for sub in sorted(p for p in pasta.iterdir() if p.is_dir()):
        n = 0
        for img_path in listar_imagens(sub):
            r = pipeline.processar(carregar_imagem(img_path))
            if r.principal is None:
                res.sem_rosto.append(str(img_path))
                continue
            embeddings.append((sub.name, r.principal.embedding))
            n += 1
        res.pessoas[sub.name] = n
    for (pa, ea), (pb, eb) in itertools.combinations(embeddings, 2):
        s = similaridade_cosseno(ea, eb)
        (res.genuinos if pa == pb else res.impostores).append(s)
    return res

```

## `cofre/banco.py` (265 linhas)

```python
"""
Camada de persistência (SQLite, biblioteca padrão do Python).

Tabelas:
  usuarios  : pessoas autorizadas (nome, matrícula, cargo, nível 1-3, ativo)
  amostras  : embeddings (BLOB float32[128]) + foto de referência de cada usuário
  acessos   : log de auditoria de toda tentativa de autenticação

Para usar MySQL (também permitido no enunciado) bastaria trocar o driver e os
placeholders `?` por `%s`; o restante do sistema não conhece o banco.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT    NOT NULL,
    matricula  TEXT    NOT NULL UNIQUE,
    cargo      TEXT    NOT NULL DEFAULT '',
    nivel      INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 3),
    ativo      INTEGER NOT NULL DEFAULT 1,
    criado_em  TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS amostras (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    embedding   BLOB    NOT NULL,
    caminho_foto TEXT,
    nitidez     REAL,
    brilho      REAL,
    criado_em   TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS acessos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora      TEXT    NOT NULL,
    usuario_id     INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    nome_detectado TEXT,
    nivel_usuario  INTEGER,
    nivel_exigido  INTEGER NOT NULL,
    area           TEXT    NOT NULL,
    similaridade   REAL,
    resultado      TEXT    NOT NULL,
    mensagem       TEXT,
    evidencia      TEXT
);
CREATE INDEX IF NOT EXISTS idx_amostras_usuario ON amostras(usuario_id);
CREATE INDEX IF NOT EXISTS idx_acessos_data ON acessos(data_hora);
"""


@dataclass
class Usuario:
    id: int
    nome: str
    matricula: str
    cargo: str
    nivel: int
    ativo: bool
    criado_em: str

    @property
    def nivel_descricao(self) -> str:
        return config.NIVEIS.get(self.nivel, "?")


@dataclass
class Acesso:
    id: int
    data_hora: str
    usuario_id: int | None
    nome_detectado: str | None
    nivel_usuario: int | None
    nivel_exigido: int
    area: str
    similaridade: float | None
    resultado: str
    mensagem: str | None
    evidencia: str | None


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Banco:
    def __init__(self, caminho: str | Path = config.DB_PATH):
        self.caminho = Path(caminho)
        if str(self.caminho) != ":memory:":
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(self.caminho))
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.executescript(SCHEMA)

    # ------------------------------------------------------------------ usuários
    def criar_usuario(self, nome: str, matricula: str, cargo: str, nivel: int) -> Usuario:
        if nivel not in config.NIVEIS:
            raise ValueError(f"Nível inválido: {nivel}")
        nome, matricula, cargo = nome.strip(), matricula.strip(), cargo.strip()
        if not nome or not matricula:
            raise ValueError("Nome e matrícula são obrigatórios.")
        cur = self._con.execute(
            "INSERT INTO usuarios (nome, matricula, cargo, nivel, ativo, criado_em) VALUES (?,?,?,?,1,?)",
            (nome, matricula, cargo, nivel, _agora()),
        )
        self._con.commit()
        return self.obter_usuario(cur.lastrowid)

    def obter_usuario(self, usuario_id: int) -> Usuario | None:
        row = self._con.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        return self._usuario(row) if row else None

    def obter_por_matricula(self, matricula: str) -> Usuario | None:
        row = self._con.execute("SELECT * FROM usuarios WHERE matricula = ?", (matricula.strip(),)).fetchone()
        return self._usuario(row) if row else None

    def listar_usuarios(self, apenas_ativos: bool = False) -> list[Usuario]:
        sql = "SELECT * FROM usuarios" + (" WHERE ativo = 1" if apenas_ativos else "") + " ORDER BY nivel DESC, nome"
        return [self._usuario(r) for r in self._con.execute(sql)]

    def alterar_nivel(self, usuario_id: int, nivel: int) -> None:
        if nivel not in config.NIVEIS:
            raise ValueError(f"Nível inválido: {nivel}")
        self._con.execute("UPDATE usuarios SET nivel = ? WHERE id = ?", (nivel, usuario_id))
        self._con.commit()

    def definir_ativo(self, usuario_id: int, ativo: bool) -> None:
        self._con.execute("UPDATE usuarios SET ativo = ? WHERE id = ?", (1 if ativo else 0, usuario_id))
        self._con.commit()

    def remover_usuario(self, usuario_id: int) -> None:
        self._con.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
        self._con.commit()

    # ------------------------------------------------------------------ amostras
    def adicionar_amostra(self, usuario_id: int, embedding: np.ndarray, caminho_foto: str | None = None,
                          nitidez: float | None = None, brilho: float | None = None) -> int:
        emb = np.asarray(embedding, dtype=np.float32).reshape(-1)
        cur = self._con.execute(
            "INSERT INTO amostras (usuario_id, embedding, caminho_foto, nitidez, brilho, criado_em) VALUES (?,?,?,?,?,?)",
            (usuario_id, emb.tobytes(), caminho_foto, nitidez, brilho, _agora()),
        )
        self._con.commit()
        return cur.lastrowid

    def versao_dados(self) -> int:
        """Muda sempre que OUTRA conexão grava no banco (outra janela do aplicativo, a linha de
        comando). Gravações desta mesma conexão não alteram o valor (`PRAGMA data_version`)."""
        return int(self._con.execute("PRAGMA data_version").fetchone()[0])

    def embeddings_do_usuario(self, usuario_id: int) -> list[np.ndarray]:
        rows = self._con.execute("SELECT embedding FROM amostras WHERE usuario_id = ?", (usuario_id,))
        return [np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]

    def contar_amostras(self, usuario_id: int) -> int:
        return self._con.execute("SELECT COUNT(*) FROM amostras WHERE usuario_id = ?", (usuario_id,)).fetchone()[0]

    def fotos_do_usuario(self, usuario_id: int) -> list[str]:
        rows = self._con.execute(
            "SELECT caminho_foto FROM amostras WHERE usuario_id = ? AND caminho_foto IS NOT NULL", (usuario_id,))
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ acessos
    def registrar_acesso(self, *, usuario_id: int | None, nome_detectado: str | None, nivel_usuario: int | None,
                         nivel_exigido: int, similaridade: float | None, resultado: str,
                         mensagem: str | None = None, evidencia: str | None = None) -> int:
        cur = self._con.execute(
            """INSERT INTO acessos (data_hora, usuario_id, nome_detectado, nivel_usuario, nivel_exigido, area,
                                    similaridade, resultado, mensagem, evidencia)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (_agora(), usuario_id, nome_detectado, nivel_usuario, nivel_exigido,
             config.AREAS.get(nivel_exigido, str(nivel_exigido)), similaridade, resultado, mensagem, evidencia),
        )
        self._con.commit()
        return cur.lastrowid

    def listar_acessos(self, limite: int | None = None, resultado: str | None = None) -> list[Acesso]:
        sql, params = "SELECT * FROM acessos", []
        if resultado:
            sql += " WHERE resultado = ?"
            params.append(resultado)
        sql += " ORDER BY data_hora DESC, id DESC"
        if limite:
            sql += " LIMIT ?"
            params.append(limite)
        return [Acesso(**dict(r)) for r in self._con.execute(sql, params)]

    def filtrar_acessos(self, *, limite: int | None = None, resultado: str | None = None,
                        nivel_exigido: int | None = None, desde: str | None = None,
                        termo: str | None = None) -> list[Acesso]:
        """Consulta só de leitura com filtros combinados (usada pela interface Qt).

        `desde`: data/hora ISO mínima (inclusive); `termo`: parte do nome detectado,
        sem diferenciar maiúsculas. O limite vale depois de aplicar os filtros."""
        sql, filtros, params = "SELECT * FROM acessos", [], []
        if resultado:
            filtros.append("resultado = ?")
            params.append(resultado)
        if nivel_exigido:
            filtros.append("nivel_exigido = ?")
            params.append(int(nivel_exigido))
        if desde:
            filtros.append("data_hora >= ?")
            params.append(desde)
        if termo:
            filtros.append("LOWER(COALESCE(nome_detectado, '')) LIKE ?")
            params.append(f"%{termo.lower()}%")
        if filtros:
            sql += " WHERE " + " AND ".join(filtros)
        sql += " ORDER BY data_hora DESC, id DESC"
        if limite:
            sql += " LIMIT ?"
            params.append(int(limite))
        return [Acesso(**dict(r)) for r in self._con.execute(sql, params)]

    def estatisticas(self) -> dict:
        por_resultado = {r[0]: r[1] for r in self._con.execute(
            "SELECT resultado, COUNT(*) FROM acessos GROUP BY resultado")}
        por_usuario = [dict(r) for r in self._con.execute(
            """SELECT COALESCE(u.nome, a.nome_detectado, 'DESCONHECIDO') AS nome,
                      SUM(a.resultado = 'CONCEDIDO') AS concedidos,
                      SUM(a.resultado != 'CONCEDIDO') AS negados
               FROM acessos a LEFT JOIN usuarios u ON u.id = a.usuario_id
               GROUP BY nome ORDER BY concedidos + negados DESC""")]
        por_dia = [dict(r) for r in self._con.execute(
            """SELECT substr(data_hora, 1, 10) AS dia, COUNT(*) AS total,
                      SUM(resultado = 'CONCEDIDO') AS concedidos
               FROM acessos GROUP BY dia ORDER BY dia DESC LIMIT 30""")]
        por_area = {r[0]: r[1] for r in self._con.execute(
            "SELECT area, COUNT(*) FROM acessos GROUP BY area")}
        return {
            "total": sum(por_resultado.values()),
            "por_resultado": por_resultado,
            "por_usuario": por_usuario,
            "por_dia": por_dia,
            "por_area": por_area,
            "usuarios": len(self.listar_usuarios()),
            "amostras": self._con.execute("SELECT COUNT(*) FROM amostras").fetchone()[0],
        }

    # ------------------------------------------------------------------ util
    @staticmethod
    def _usuario(row: sqlite3.Row) -> Usuario:
        d = dict(row)
        d["ativo"] = bool(d["ativo"])
        return Usuario(**d)

    def fechar(self) -> None:
        self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.fechar()

```

## `cofre/cadastro.py` (191 linhas)

```python
"""Fluxo de cadastro (enrollment) de usuários autorizados."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import cv2

from . import config, hud
from .banco import Banco, Usuario
from .fase1_aquisicao import FonteCamera, carregar_imagem
from .pipeline import Pipeline

# 9 poses, 2 amostras cada (AMOSTRAS_POR_CADASTRO = 18). Cobrem giro (yaw), inclinação (roll)
# e cabeça baixa/erguida (pitch): o terminal reconhece melhor quem não está perfeitamente de frente.
INSTRUCOES_POSE = [
    "Olhe para a camera",
    "Vire um pouco o rosto para a esquerda",
    "Vire um pouco o rosto para a direita",
    "Incline a cabeca para a esquerda",
    "Incline a cabeca para a direita",
    "Levante um pouco o queixo",
    "Abaixe o queixo, como se olhasse o celular",
    "Olhe para a camera de novo",
    "Sorria",
]


@dataclass
class DadosCadastro:
    nome: str
    matricula: str
    cargo: str
    nivel: int


def _pasta_fotos(usuario: Usuario) -> Path:
    pasta = config.FOTOS_DIR / f"{usuario.id:03d}_{usuario.matricula}"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def cadastrar_de_imagens(banco: Banco, pipeline: Pipeline, dados: DadosCadastro,
                         caminhos: list[str | Path]) -> tuple[Usuario, int, list[str]]:
    """Cadastra a partir de arquivos (scanner/câmera externa). Retorna (usuario, n_amostras, avisos)."""
    usuario = banco.criar_usuario(dados.nome, dados.matricula, dados.cargo, dados.nivel)
    pasta = _pasta_fotos(usuario)
    avisos, n = [], 0
    for caminho in caminhos:
        try:
            img = carregar_imagem(caminho)
        except Exception as e:  # noqa: BLE001
            avisos.append(f"{caminho}: {e}")
            continue
        res = pipeline.processar(img)
        if not res.rostos:
            avisos.append(f"{caminho}: nenhum rosto detectado")
            continue
        if len(res.rostos) > 1:
            avisos.append(f"{caminho}: {len(res.rostos)} rostos, usando o maior")
        p = res.principal
        destino = pasta / f"{n + 1:02d}_{Path(caminho).stem}.jpg"
        cv2.imwrite(str(destino), p.recorte)
        banco.adicionar_amostra(usuario.id, p.embedding, str(destino), p.qualidade.nitidez, p.qualidade.brilho)
        n += 1
    if n == 0:
        banco.remover_usuario(usuario.id)
        raise RuntimeError("Nenhuma amostra válida; cadastro cancelado. " + "; ".join(avisos))
    return usuario, n, avisos


class SessaoCadastro:
    """Lógica de cadastro por frame, independente de interface (usada pela janela OpenCV
    e pelo aplicativo desktop). Cria o usuário no início; `cancelar()` desfaz tudo."""

    def __init__(self, banco: Banco, pipeline: Pipeline, dados: DadosCadastro,
                 amostras: int = config.AMOSTRAS_POR_CADASTRO):
        self.banco = banco
        self.pipeline = pipeline
        self.dados = dados
        self.amostras = amostras
        self.usuario = banco.criar_usuario(dados.nome, dados.matricula, dados.cargo, dados.nivel)
        self.pasta = _pasta_fotos(self.usuario)
        self.capturadas = 0
        self.ultima = 0.0
        self.status = "Posicione o rosto na camera"
        self.cor = hud.AMARELO
        self.pose = INSTRUCOES_POSE[0]
        self.miniaturas: list = []      # recortes capturados (para a interface mostrar)
        self.capturou_agora = False
        self.encerrada = False

    @property
    def concluida(self) -> bool:
        return self.capturadas >= self.amostras

    @property
    def progresso(self) -> float:
        return self.capturadas / self.amostras

    def passo(self, frame, res) -> None:
        """Avalia o resultado do pipeline deste frame e captura uma amostra se for o caso."""
        self.capturou_agora = False
        if self.concluida or self.encerrada:
            return
        self.pose = INSTRUCOES_POSE[min(self.capturadas * len(INSTRUCOES_POSE) // max(1, self.amostras),
                                        len(INSTRUCOES_POSE) - 1)]
        if len(res.rostos) > 1:
            self.status, self.cor = "Apenas UMA pessoa deve aparecer", hud.VERMELHO
            return
        if not res.rostos:
            self.status, self.cor = "Posicione o rosto na camera", hud.AMARELO
            return
        p = res.principal
        q = p.qualidade
        if not q.aprovada:
            self.status, self.cor = f"Ajuste: {q.motivo} (nitidez {q.nitidez:.0f}, brilho {q.brilho:.0f})", hud.LARANJA
            return
        self.status, self.cor = f"Capturando... {self.pose}", hud.VERDE
        if time.time() - self.ultima >= config.INTERVALO_AMOSTRAS_SEG:
            emb = self.pipeline.extrator.extrair(p.alinhado)
            destino = self.pasta / f"{self.capturadas + 1:02d}.jpg"
            cv2.imwrite(str(destino), p.recorte)
            self.banco.adicionar_amostra(self.usuario.id, emb, str(destino), q.nitidez, q.brilho)
            self.capturadas += 1
            self.ultima = time.time()
            self.miniaturas.append(p.recorte)
            self.capturou_agora = True
            if self.concluida:
                self.status, self.cor = "Cadastro concluido!", hud.VERDE

    def desenhar(self, frame, res):
        """Frame com o HUD de cadastro desenhado (OpenCV)."""
        tela = frame.copy()
        if len(res.rostos) > 1:
            for r in res.rostos:
                hud.caixa_rosto(tela, r.rosto, hud.VERMELHO)
        elif res.rostos:
            p = res.principal
            hud.caixa_rosto(tela, p.rosto, self.cor, "OK" if p.qualidade.aprovada else None)
            if p.qualidade.aprovada:
                hud.pontos_faciais(tela, p.rosto)
        if self.capturou_agora:
            cv2.rectangle(tela, (0, 0), (tela.shape[1], tela.shape[0]), hud.BRANCO, 12)
        hud.painel_topo(tela, [
            (f"Cadastro: {self.dados.nome}  |  nivel {self.dados.nivel} - {config.NIVEIS[self.dados.nivel]}", hud.BRANCO),
            (self.status, self.cor),
            (f"Amostras: {self.capturadas}/{self.amostras}", hud.AZUL),
        ])
        return tela

    def cancelar(self) -> None:
        """Remove o usuário e as amostras já gravadas."""
        if not self.encerrada:
            self.encerrada = True
            self.banco.remover_usuario(self.usuario.id)

    def concluir(self) -> Usuario | None:
        """Fecha a sessão; sem nenhuma amostra o cadastro é desfeito."""
        self.encerrada = True
        if self.capturadas == 0:
            self.banco.remover_usuario(self.usuario.id)
            return None
        return self.usuario


def cadastrar_pela_camera(banco: Banco, pipeline: Pipeline, dados: DadosCadastro,
                          amostras: int = config.AMOSTRAS_POR_CADASTRO) -> Usuario | None:
    """Versão com janela OpenCV (linha de comando). ESC cancela e desfaz o cadastro."""
    sessao = SessaoCadastro(banco, pipeline, dados, amostras)
    janela = "Cadastro biometrico - cofre MMA"
    with FonteCamera() as cam:
        for frame in cam.frames():
            res = pipeline.processar(frame, extrair_embedding=False)
            sessao.passo(frame, res)
            tela = sessao.desenhar(frame, res)
            hud.rodape(tela, "ESC cancela o cadastro")
            cv2.imshow(janela, tela)
            tecla = cv2.waitKey(1) & 0xFF
            if tecla == 27:
                sessao.cancelar()
                break
            if sessao.concluida:
                hud.faixa_resultado(tela, "Cadastro concluido!", hud.VERDE)
                cv2.imshow(janela, tela)
                cv2.waitKey(1200)
                break
    cv2.destroyWindow(janela)
    return sessao.concluir()

```

## `cofre/config.py` (104 linhas)

```python
"""Configurações centrais do sistema (caminhos, limiares e níveis de acesso)."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cofre.db"
FOTOS_DIR = DATA_DIR / "fotos"            # fotos de referência dos cadastrados
EVIDENCIAS_DIR = DATA_DIR / "evidencias"  # capturas de tentativas negadas
RELATORIOS_DIR = DATA_DIR / "relatorios"  # CSV/HTML gerados

MODELO_DETECCAO = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
MODELO_RECONHECIMENTO = MODELS_DIR / "face_recognition_sface_2021dec.onnx"

# ---------------------------------------------------------------------------
# Níveis de segurança (enunciado da APS)
# ---------------------------------------------------------------------------
NIVEIS = {
    1: "Permissão geral",
    2: "Diretor de divisão",
    3: "Ministro do Meio Ambiente",
}

# Áreas protegidas e o nível mínimo exigido para cada uma
AREAS = {
    1: "Área comum do Ministério",
    2: "Sala dos diretores de divisão",
    3: "Cofre de toxinas (exclusivo do Ministro)",
}

# ---------------------------------------------------------------------------
# Fase 1 - Aquisição
# ---------------------------------------------------------------------------
CAMERA_INDEX = 0
CAMERA_LARGURA = 1280
CAMERA_ALTURA = 720
ESPELHAR_CAMERA = True  # exibe como um espelho, mais natural para o usuário

# ---------------------------------------------------------------------------
# Fase 2 - Pré-processamento
# ---------------------------------------------------------------------------
CLAHE_CLIP = 2.0
CLAHE_GRADE = (8, 8)
GAUSS_KERNEL = (3, 3)
LARGURA_PROCESSAMENTO = 640   # frame reduzido para acelerar a detecção
MIN_NITIDEZ = 60.0            # variância do Laplaciano abaixo disso = borrado
MIN_BRILHO = 40.0             # média de intensidade abaixo disso = muito escuro
MAX_BRILHO = 220.0            # acima disso = estourado

# ---------------------------------------------------------------------------
# Fase 3 - Segmentação (detecção)
# ---------------------------------------------------------------------------
DETECCAO_SCORE_MIN = 0.85
DETECCAO_NMS = 0.3
DETECCAO_TOP_K = 50
TAMANHO_MIN_ROSTO = 80        # lado mínimo (px) do rosto no frame reduzido
# Pose aceitável para AUTENTICAR, medida pelos 5 pontos do YuNet. Fora disso o terminal pede
# "olhe para a câmera" e não tenta reconhecer: a tentativa não entra no log nem conta como
# falha para o bloqueio. Calibrado com 69 quadros reais: rostos de frente ficam com |yaw| < 0,45,
# |roll| < 20° e razão do nariz entre 0,45 e 0,70. Não se aplica à prova de vida (que pede o giro)
# nem ao cadastro (que pede as poses).
POSE_MAX_YAW = 0.60           # |nariz - meio dos olhos| / distância entre os olhos
POSE_MAX_ROLL_GRAUS = 25.0    # inclinação da linha dos olhos
POSE_RAZAO_NARIZ_MIN = 0.35   # (nariz - olhos) / (boca - olhos): abaixo = cabeça muito erguida
POSE_RAZAO_NARIZ_MAX = 0.80   # acima = cabeça muito baixa

# ---------------------------------------------------------------------------
# Fase 5 - Reconhecimento
# ---------------------------------------------------------------------------
# Limiar oficial recomendado pelo OpenCV para o modelo SFace (similaridade do cosseno).
# Acima do limiar = mesma pessoa.
LIMIAR_COSSENO = 0.363
# Margem extra para considerar "reconhecimento forte" (usada no HUD).
LIMIAR_COSSENO_FORTE = 0.50
# Quantidade de frames consecutivos com a MESMA identidade antes de decidir.
FRAMES_CONFIRMACAO = 6

# ---------------------------------------------------------------------------
# Cadastro
# ---------------------------------------------------------------------------
AMOSTRAS_POR_CADASTRO = 18
# Intervalo entre amostras. As 9 instruções de pose ocupam 2 amostras cada, então cada
# instrução fica 3 s na tela (1,5 s para reagir antes de cada captura); o cadastro leva ~27 s.
# Com 0,4 s a pose mudava a cada 0,8 s, rápido demais para acompanhar, e o cadastro saía
# quase todo de frente, reconhecendo pior com a cabeça virada.
INTERVALO_AMOSTRAS_SEG = 1.5

# ---------------------------------------------------------------------------
# Segurança / anti-fraude
# ---------------------------------------------------------------------------
LIVENESS_ATIVO = True
LIVENESS_LIMIAR_YAW = 0.22      # razão nariz/olhos para considerar a cabeça virada
LIVENESS_TIMEOUT_SEG = 12.0
MAX_TENTATIVAS_FALHAS = 3       # negações seguidas antes de bloquear
JANELA_FALHAS_SEG = 60.0
BLOQUEIO_SEG = 30.0
TEMPO_EXIBIR_RESULTADO_SEG = 3.0
# Área liberada (aplicativo Qt): tempo de inatividade até a sessão aberta pelo terminal fechar sozinha.
SESSAO_LIBERADA_SEG = 120
BLOQUEAR_MULTIPLOS_ROSTOS = True  # "carona" (tailgating): mais de um rosto = não autentica

```

## `cofre/demo.py` (50 linhas)

```python
"""Demonstração didática: roda o pipeline completo em uma imagem e monta o painel das 5 fases."""

from __future__ import annotations

from pathlib import Path

import cv2

from . import config, hud
from .banco import Banco
from .fase1_aquisicao import carregar_imagem
from .fase5_reconhecimento import Reconhecedor, decidir_acesso
from .pipeline import Pipeline


def demonstrar_imagem(caminho: str | Path, pipeline: Pipeline, banco: Banco | None = None,
                      nivel_exigido: int = 3, salvar_em: Path | None = None, exibir: bool = True) -> Path | None:
    frame = carregar_imagem(caminho)
    res = pipeline.processar(frame)
    painel = hud.mosaico(res.etapas_didaticas(), lado=240, colunas=4)
    linhas = [f"Fase 1 aquisicao: {Path(caminho).name}  {frame.shape[1]}x{frame.shape[0]}",
              f"Fase 2/3: {len(res.rostos)} rosto(s) detectado(s) no frame reduzido {res.pre.reduzida.shape[1]}px"]
    p = res.principal
    if p is not None:
        linhas.append(f"Fase 3: caixa {p.rosto.caixa}  conf {p.rosto.confianca:.2f}  yaw {p.rosto.yaw():+.2f}  "
                      f"nitidez {p.qualidade.nitidez:.0f} brilho {p.qualidade.brilho:.0f}")
        linhas.append(f"Fase 4: embedding 128-d  norma {float((p.embedding ** 2).sum()) ** 0.5:.2f}")
        if banco is not None:
            ident = Reconhecedor(banco).identificar(p.embedding)
            d = decidir_acesso(ident, nivel_exigido)
            linhas.append(f"Fase 5: {ident.rotulo} sim={ident.similaridade:.3f} (limiar {config.LIMIAR_COSSENO}) "
                          f"-> {d.resultado.value}")
    rodape = 24 * len(linhas) + 16
    import numpy as np
    base = np.full((painel.shape[0] + rodape, painel.shape[1], 3), 20, np.uint8)
    base[:painel.shape[0]] = painel
    y = painel.shape[0] + 24
    for l in linhas:
        hud.texto(base, l, (10, y), 0.55, hud.BRANCO, 1)
        y += 24
    destino = None
    if salvar_em is not None:
        salvar_em.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(salvar_em), base)
        destino = salvar_em
    if exibir:
        cv2.imshow("Pipeline - 5 fases do PDI", base)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return destino

```

## `cofre/fase1_aquisicao.py` (133 linhas)

```python
"""
FASE 1 - AQUISIÇÃO DA IMAGEM

Responsável por obter a imagem digital que entra no pipeline. Duas fontes:
  * `FonteCamera`  : captura em tempo real pela webcam (requisito do enunciado);
  * `FonteImagens` : leitura de arquivos (scanner/câmera externa/testes).

A saída de ambas é sempre um frame BGR (padrão do OpenCV) em `numpy.ndarray`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Iterator

import cv2
import numpy as np

from . import config

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class ErroAquisicao(RuntimeError):
    """Falha ao abrir a câmera ou ler o arquivo."""


class FonteCamera:
    """Captura frames da webcam. Uso como *context manager*:

        with FonteCamera() as cam:
            for frame in cam.frames():
                ...
    """

    def __init__(self, indice: int = config.CAMERA_INDEX, espelhar: bool = config.ESPELHAR_CAMERA):
        self.indice = indice
        self.espelhar = espelhar
        self._cap: cv2.VideoCapture | None = None
        self.fps_medido = 0.0

    def preparar(self) -> "FonteCamera":
        """Cria o dispositivo de captura sem ler frames.

        No macOS, a primeira abertura da câmera pede permissão ao sistema, e o OpenCV só
        consegue mostrar esse pedido se estiver na thread principal. Quem lê os frames em
        outra thread (o aplicativo desktop) chama `preparar()` antes, na thread principal."""
        if self._cap is None:
            self._cap = cv2.VideoCapture(self.indice)
        return self

    def abrir(self) -> "FonteCamera":
        cap = self._cap if self._cap is not None else cv2.VideoCapture(self.indice)
        self._cap = None
        if not cap.isOpened():
            cap.release()
            raise ErroAquisicao(
                f"Não foi possível abrir a câmera {self.indice}. No macOS, autorize o aplicativo que "
                "abriu o programa (Terminal, VS Code, Claude...) em Ajustes > Privacidade e Segurança > Câmera "
                "e abra o programa de novo."
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_LARGURA)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_ALTURA)
        # Primeiras leituras costumam vir pretas enquanto o sensor ajusta a exposição.
        inicio = time.time()
        while time.time() - inicio < 5.0:
            ok, frame = cap.read()
            if ok and frame is not None and frame.mean() > 2:
                break
            time.sleep(0.05)
        self._cap = cap
        return self

    def ler(self) -> np.ndarray:
        if self._cap is None:
            raise ErroAquisicao("Câmera não aberta. Chame abrir() ou use `with`.")
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise ErroAquisicao("Falha ao ler frame da câmera.")
        if self.espelhar:
            frame = cv2.flip(frame, 1)
        return frame

    def frames(self) -> Iterator[np.ndarray]:
        """Gerador infinito de frames (mede FPS no caminho)."""
        anterior = time.time()
        alpha = 0.1
        while True:
            frame = self.ler()
            agora = time.time()
            dt = agora - anterior
            anterior = agora
            if dt > 0:
                fps = 1.0 / dt
                self.fps_medido = fps if self.fps_medido == 0 else (1 - alpha) * self.fps_medido + alpha * fps
            yield frame

    def fechar(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "FonteCamera":
        return self.abrir()

    def __exit__(self, *exc) -> None:
        self.fechar()


def carregar_imagem(caminho: str | Path) -> np.ndarray:
    """Lê uma imagem do disco em BGR. Lança ErroAquisicao se não conseguir."""
    caminho = Path(caminho)
    img = cv2.imread(str(caminho), cv2.IMREAD_COLOR)
    if img is None:
        raise ErroAquisicao(f"Não foi possível ler a imagem: {caminho}")
    return img


def listar_imagens(pasta: str | Path) -> list[Path]:
    pasta = Path(pasta)
    return sorted(p for p in pasta.iterdir() if p.suffix.lower() in EXTENSOES_IMAGEM)


class FonteImagens:
    """Itera sobre arquivos de imagem como se fossem frames (útil em testes e demos)."""

    def __init__(self, caminhos: Iterable[str | Path]):
        self.caminhos = [Path(c) for c in caminhos]

    def frames(self) -> Iterator[tuple[Path, np.ndarray]]:
        for caminho in self.caminhos:
            yield caminho, carregar_imagem(caminho)

```

## `cofre/fase2_preprocessamento.py` (129 linhas)

```python
"""
FASE 2 - PRÉ-PROCESSAMENTO

Melhora a imagem adquirida antes da análise, reduzindo a influência de
iluminação, ruído e resolução no resultado do reconhecimento:

  1. redimensionamento  -> frame menor acelera a detecção;
  2. conversão para escala de cinza -> usada nas métricas de qualidade e no LBP;
  3. suavização gaussiana -> reduz ruído de sensor;
  4. equalização adaptativa de histograma (CLAHE) no canal de luminância (LAB)
     -> corrige contraste/iluminação sem distorcer as cores que o detector usa;
  5. métricas de qualidade (nitidez, brilho) -> rejeitam frames ruins no cadastro.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from . import config


@dataclass
class ResultadoPreprocessamento:
    """Guarda todas as imagens intermediárias (usadas no modo didático)."""

    original: np.ndarray
    reduzida: np.ndarray
    cinza: np.ndarray
    suavizada: np.ndarray
    equalizada: np.ndarray        # BGR, com CLAHE aplicado no canal L
    escala: float                 # fator original -> reduzida
    etapas: dict[str, np.ndarray] = field(default_factory=dict)


def redimensionar(img: np.ndarray, largura: int = config.LARGURA_PROCESSAMENTO) -> tuple[np.ndarray, float]:
    """Reduz a imagem para `largura` px mantendo a proporção. Retorna (imagem, escala)."""
    h, w = img.shape[:2]
    if w <= largura:
        return img.copy(), 1.0
    escala = largura / w
    nova = cv2.resize(img, (largura, int(round(h * escala))), interpolation=cv2.INTER_AREA)
    return nova, escala


def converter_cinza(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def suavizar(img: np.ndarray, kernel: tuple[int, int] = config.GAUSS_KERNEL) -> np.ndarray:
    return cv2.GaussianBlur(img, kernel, 0)


def equalizar_clahe(img_bgr: np.ndarray, clip: float = config.CLAHE_CLIP, grade=config.CLAHE_GRADE) -> np.ndarray:
    """CLAHE aplicado apenas na luminância (espaço LAB). Mantém a imagem colorida."""
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=grade)
    l_eq = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l_eq, a, b)), cv2.COLOR_LAB2BGR)


def equalizar_cinza(img_cinza: np.ndarray) -> np.ndarray:
    """Equalização global clássica (para comparação didática com o CLAHE)."""
    return cv2.equalizeHist(img_cinza)


def medir_nitidez(img: np.ndarray) -> float:
    """Variância do Laplaciano: quanto maior, mais bordas = imagem mais nítida."""
    return float(cv2.Laplacian(converter_cinza(img), cv2.CV_64F).var())


def medir_brilho(img: np.ndarray) -> float:
    return float(converter_cinza(img).mean())


@dataclass
class Qualidade:
    nitidez: float
    brilho: float

    @property
    def aprovada(self) -> bool:
        return (
            self.nitidez >= config.MIN_NITIDEZ
            and config.MIN_BRILHO <= self.brilho <= config.MAX_BRILHO
        )

    @property
    def motivo(self) -> str:
        if self.nitidez < config.MIN_NITIDEZ:
            return "imagem borrada"
        if self.brilho < config.MIN_BRILHO:
            return "muito escura"
        if self.brilho > config.MAX_BRILHO:
            return "muito clara"
        return "ok"


def avaliar_qualidade(recorte: np.ndarray) -> Qualidade:
    return Qualidade(nitidez=medir_nitidez(recorte), brilho=medir_brilho(recorte))


def preprocessar(frame: np.ndarray) -> ResultadoPreprocessamento:
    """Executa a fase 2 completa e devolve as imagens intermediárias."""
    reduzida, escala = redimensionar(frame)
    cinza = converter_cinza(reduzida)
    suavizada = suavizar(reduzida)
    equalizada = equalizar_clahe(suavizada)
    res = ResultadoPreprocessamento(
        original=frame,
        reduzida=reduzida,
        cinza=cinza,
        suavizada=suavizada,
        equalizada=equalizada,
        escala=escala,
    )
    res.etapas = {
        "1 original": frame,
        "2 reduzida": reduzida,
        "2 cinza": cinza,
        "2 suavizada": suavizada,
        "2 CLAHE": equalizada,
    }
    return res

```

## `cofre/fase3_segmentacao.py` (154 linhas)

```python
"""
FASE 3 - SEGMENTAÇÃO

Separa a região de interesse (o rosto) do restante da cena:

  * Detecção com a rede YuNet (OpenCV FaceDetectorYN): devolve caixa delimitadora,
    5 pontos de referência (olhos, nariz, cantos da boca) e confiança.
  * Recorte + alinhamento geométrico: uma transformação afim leva os pontos de
    referência a posições canônicas em uma imagem 112x112, para que todos os
    rostos entrem na fase 4 com a mesma pose/escala.
  * Estimativa simples de pose (yaw) a partir dos pontos, usada no anti-fraude.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass

import cv2
import numpy as np

from . import config


@dataclass
class Rosto:
    """Um rosto detectado no frame (coordenadas no frame onde foi detectado)."""

    x: int
    y: int
    w: int
    h: int
    olho_dir: tuple[float, float]
    olho_esq: tuple[float, float]
    nariz: tuple[float, float]
    boca_dir: tuple[float, float]
    boca_esq: tuple[float, float]
    confianca: float
    bruto: np.ndarray  # linha original do YuNet (necessária para alignCrop)

    @property
    def caixa(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.w, self.h

    @property
    def area(self) -> int:
        return self.w * self.h

    @property
    def centro(self) -> tuple[float, float]:
        return self.x + self.w / 2, self.y + self.h / 2

    def escalar(self, fator: float) -> "Rosto":
        """Converte as coordenadas para outra escala (ex.: frame reduzido -> original)."""
        bruto = self.bruto.copy()
        bruto[:14] *= fator
        return rosto_de_linha(bruto)

    def yaw(self) -> float:
        """Razão horizontal nariz/olhos. ~0 = frontal, negativo = virado para a
        esquerda da imagem, positivo = para a direita. Independe da escala."""
        meio_x = (self.olho_dir[0] + self.olho_esq[0]) / 2
        dist_olhos = abs(self.olho_esq[0] - self.olho_dir[0]) or 1.0
        return (self.nariz[0] - meio_x) / dist_olhos

    def roll(self) -> float:
        """Inclinação da linha dos olhos, em graus. ~0 = cabeça reta."""
        return math.degrees(math.atan2(self.olho_esq[1] - self.olho_dir[1], self.olho_esq[0] - self.olho_dir[0]))

    def razao_nariz(self) -> float:
        """Posição vertical do nariz entre os olhos (0) e a boca (1). De frente fica em ~0,5-0,6;
        cabeça baixa empurra o nariz para a boca (sobe), cabeça erguida afasta (desce)."""
        olhos_y = (self.olho_dir[1] + self.olho_esq[1]) / 2
        boca_y = (self.boca_dir[1] + self.boca_esq[1]) / 2
        return (self.nariz[1] - olhos_y) / ((boca_y - olhos_y) or 1.0)

    def problema_pose(self) -> str:
        """'' se a pose serve para autenticar; senão, a instrução para a pessoa (lê `config` na hora)."""
        if abs(self.yaw()) > config.POSE_MAX_YAW:
            return "Vire o rosto para a câmera"
        if abs(self.roll()) > config.POSE_MAX_ROLL_GRAUS:
            return "Endireite a cabeça"
        razao = self.razao_nariz()
        if razao > config.POSE_RAZAO_NARIZ_MAX:
            return "Levante a cabeça e olhe para a câmera"
        if razao < config.POSE_RAZAO_NARIZ_MIN:
            return "Abaixe o queixo e olhe para a câmera"
        return ""


def rosto_de_linha(linha: np.ndarray) -> Rosto:
    l = linha.astype(np.float32)
    return Rosto(
        x=int(l[0]), y=int(l[1]), w=int(l[2]), h=int(l[3]),
        olho_dir=(float(l[4]), float(l[5])),
        olho_esq=(float(l[6]), float(l[7])),
        nariz=(float(l[8]), float(l[9])),
        boca_dir=(float(l[10]), float(l[11])),
        boca_esq=(float(l[12]), float(l[13])),
        confianca=float(l[14]),
        bruto=l,
    )


class DetectorFacial:
    """Encapsula o YuNet. A rede do OpenCV não aceita duas inferências ao mesmo tempo, então
    `detectar` usa um lock: o aplicativo desktop processa a câmera em uma thread e, ao mesmo
    tempo, pode processar fotos (cadastro por arquivo, demonstração) em outra."""

    def __init__(self, modelo=config.MODELO_DETECCAO, score_min=config.DETECCAO_SCORE_MIN):
        if not modelo.exists():
            raise FileNotFoundError(f"Modelo de detecção não encontrado: {modelo}")
        self._det = cv2.FaceDetectorYN.create(
            str(modelo), "", (320, 320), score_min, config.DETECCAO_NMS, config.DETECCAO_TOP_K
        )
        self._tamanho = (320, 320)
        self._lock = threading.Lock()

    def detectar(self, img_bgr: np.ndarray, tamanho_min: int = config.TAMANHO_MIN_ROSTO) -> list[Rosto]:
        h, w = img_bgr.shape[:2]
        with self._lock:  # o tamanho de entrada e a inferência precisam ficar juntos
            if (w, h) != self._tamanho:
                self._det.setInputSize((w, h))
                self._tamanho = (w, h)
            _, faces = self._det.detect(img_bgr)
        if faces is None:
            return []
        rostos = [rosto_de_linha(f) for f in faces]
        rostos = [r for r in rostos if min(r.w, r.h) >= tamanho_min]
        # maior rosto primeiro (mais próximo da câmera)
        rostos.sort(key=lambda r: r.area, reverse=True)
        return rostos


def recortar(img: np.ndarray, rosto: Rosto, margem: float = 0.15) -> np.ndarray:
    """Recorte simples (sem alinhamento) com margem, para salvar fotos e evidências."""
    h, w = img.shape[:2]
    mx, my = int(rosto.w * margem), int(rosto.h * margem)
    x0, y0 = max(0, rosto.x - mx), max(0, rosto.y - my)
    x1, y1 = min(w, rosto.x + rosto.w + mx), min(h, rosto.y + rosto.h + my)
    return img[y0:y1, x0:x1].copy()


def alinhar(img: np.ndarray, rosto: Rosto, reconhecedor_sf) -> np.ndarray:
    """Recorte alinhado 112x112 via transformação afim pelos 5 pontos (SFace.alignCrop)."""
    return reconhecedor_sf.alignCrop(img, rosto.bruto)


def desenhar_pontos(img: np.ndarray, rosto: Rosto) -> np.ndarray:
    saida = img.copy()
    for p in (rosto.olho_dir, rosto.olho_esq, rosto.nariz, rosto.boca_dir, rosto.boca_esq):
        cv2.circle(saida, (int(p[0]), int(p[1])), 3, (0, 255, 255), -1)
    return saida

```

## `cofre/fase4_representacao.py` (93 linhas)

```python
"""
FASE 4 - REPRESENTAÇÃO E DESCRIÇÃO

Transforma o rosto segmentado em um descritor numérico compacto:

  * Principal: *embedding* de 128 dimensões gerado pela rede SFace
    (OpenCV FaceRecognizerSF). Rostos da mesma pessoa geram vetores próximos
    (alta similaridade do cosseno); de pessoas diferentes, vetores distantes.
  * Didático: descritor LBP (Local Binary Pattern) + histograma, técnica
    clássica de textura usada em reconhecimento facial antes das redes neurais.
    Serve para o painel didático e para comparação na dissertação.
"""

from __future__ import annotations

import threading

import cv2
import numpy as np

from . import config


class ExtratorCaracteristicas:
    """Encapsula o SFace: alinhamento (fase 3) e extração do embedding (fase 4)."""

    DIMENSAO = 128

    def __init__(self, modelo=config.MODELO_RECONHECIMENTO):
        if not modelo.exists():
            raise FileNotFoundError(f"Modelo de reconhecimento não encontrado: {modelo}")
        self._sf = cv2.FaceRecognizerSF.create(str(modelo), "")
        self._lock = threading.Lock()  # a rede não aceita duas inferências ao mesmo tempo

    @property
    def sface(self):
        return self._sf

    def alinhar(self, img: np.ndarray, rosto) -> np.ndarray:
        return self._sf.alignCrop(img, rosto.bruto)

    def extrair(self, rosto_alinhado: np.ndarray) -> np.ndarray:
        """Embedding L2-normalizado (float32, shape (128,))."""
        with self._lock:
            feat = self._sf.feature(rosto_alinhado)
        feat = feat.astype(np.float32).reshape(-1)
        norma = np.linalg.norm(feat)
        return feat / norma if norma > 0 else feat

    def extrair_de_frame(self, img: np.ndarray, rosto) -> np.ndarray:
        return self.extrair(self.alinhar(img, rosto))


def similaridade_cosseno(a: np.ndarray, b: np.ndarray) -> float:
    """Para vetores normalizados, o cosseno é apenas o produto interno."""
    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def lbp_mapa(cinza: np.ndarray) -> np.ndarray:
    """LBP 3x3 básico, vetorizado em NumPy. Cada pixel vira um código de 8 bits
    comparando-o com os 8 vizinhos (1 se vizinho >= centro)."""
    img = cinza.astype(np.int16)
    centro = img[1:-1, 1:-1]
    vizinhos = [
        img[:-2, :-2], img[:-2, 1:-1], img[:-2, 2:],
        img[1:-1, 2:], img[2:, 2:], img[2:, 1:-1],
        img[2:, :-2], img[1:-1, :-2],
    ]
    codigo = np.zeros_like(centro, dtype=np.uint8)
    for bit, viz in enumerate(vizinhos):
        codigo |= ((viz >= centro).astype(np.uint8) << bit)
    return codigo


def lbp_histograma(cinza: np.ndarray, grade: tuple[int, int] = (4, 4)) -> np.ndarray:
    """Histograma LBP concatenado por blocos (grade x grade), normalizado."""
    mapa = lbp_mapa(cinza)
    h, w = mapa.shape
    gh, gw = grade
    hist = []
    for i in range(gh):
        for j in range(gw):
            bloco = mapa[i * h // gh:(i + 1) * h // gh, j * w // gw:(j + 1) * w // gw]
            hb, _ = np.histogram(bloco, bins=256, range=(0, 256))
            hist.append(hb)
    vetor = np.concatenate(hist).astype(np.float32)
    s = vetor.sum()
    return vetor / s if s > 0 else vetor

```

## `cofre/fase5_reconhecimento.py` (141 linhas)

```python
"""
FASE 5 - RECONHECIMENTO E INTERPRETAÇÃO

Compara o descritor do rosto com a galeria de usuários cadastrados e decide:

  1. Identificação (1:N): para cada usuário, a maior similaridade do cosseno
     entre o embedding da consulta e as amostras cadastradas. O usuário com a
     maior similaridade vence, se superar o limiar (`LIMIAR_COSSENO`).
  2. Autorização: o nível do usuário é comparado com o nível exigido pela área.
     Nível do usuário >= nível exigido => acesso concedido.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from . import config
from .banco import Banco, Usuario


class Resultado(str, Enum):
    CONCEDIDO = "CONCEDIDO"
    NEGADO_NIVEL = "NEGADO_NIVEL"              # pessoa conhecida, nível insuficiente
    NEGADO_DESCONHECIDO = "NEGADO_DESCONHECIDO"  # rosto não cadastrado
    NEGADO_LIVENESS = "NEGADO_LIVENESS"        # falhou no desafio anti-fraude
    NEGADO_MULTIPLOS = "NEGADO_MULTIPLOS"      # mais de um rosto na cena
    BLOQUEADO = "BLOQUEADO"                    # terminal em bloqueio temporário


@dataclass
class Identificacao:
    usuario: Usuario | None
    similaridade: float
    segunda_similaridade: float = 0.0   # do 2º colocado (mede ambiguidade)

    @property
    def reconhecido(self) -> bool:
        return self.usuario is not None and self.similaridade >= config.LIMIAR_COSSENO

    @property
    def forte(self) -> bool:
        return self.reconhecido and self.similaridade >= config.LIMIAR_COSSENO_FORTE

    @property
    def rotulo(self) -> str:
        return self.usuario.nome if self.reconhecido else "DESCONHECIDO"


@dataclass
class Decisao:
    resultado: Resultado
    identificacao: Identificacao | None
    nivel_exigido: int
    mensagem: str

    @property
    def concedido(self) -> bool:
        return self.resultado is Resultado.CONCEDIDO


class Reconhecedor:
    """Mantém a galeria em memória (matriz N x 128) para comparação rápida."""

    def __init__(self, banco: Banco):
        self.banco = banco
        self._usuarios: list[Usuario] = []
        self._donos: np.ndarray = np.zeros(0, dtype=np.int64)   # id do usuário de cada linha
        self._matriz: np.ndarray = np.zeros((0, 128), dtype=np.float32)
        self.recarregar()

    def recarregar(self) -> None:
        self._usuarios = self.banco.listar_usuarios(apenas_ativos=True)
        linhas, donos = [], []
        for u in self._usuarios:
            for emb in self.banco.embeddings_do_usuario(u.id):
                linhas.append(emb)
                donos.append(u.id)
        if linhas:
            self._matriz = np.vstack(linhas).astype(np.float32)
            self._donos = np.asarray(donos, dtype=np.int64)
        else:
            self._matriz = np.zeros((0, 128), dtype=np.float32)
            self._donos = np.zeros(0, dtype=np.int64)

    @property
    def total_amostras(self) -> int:
        return int(self._matriz.shape[0])

    @property
    def usuarios(self) -> list[Usuario]:
        return list(self._usuarios)

    def amostra_mais_parecida(self, embedding: np.ndarray) -> np.ndarray | None:
        """Embedding da galeria mais próximo do dado (só para visualização; não decide nada)."""
        if self.total_amostras == 0:
            return None
        q = np.asarray(embedding, dtype=np.float32).reshape(-1)
        q = q / (np.linalg.norm(q) or 1.0)
        return self._matriz[int(np.argmax(self._matriz @ q))].copy()

    def identificar(self, embedding: np.ndarray) -> Identificacao:
        if self.total_amostras == 0:
            return Identificacao(None, 0.0)
        q = np.asarray(embedding, dtype=np.float32).reshape(-1)
        q = q / (np.linalg.norm(q) or 1.0)
        sims = self._matriz @ q                       # cosseno de todas as amostras
        por_usuario: dict[int, float] = {}
        for uid, s in zip(self._donos.tolist(), sims.tolist()):
            if s > por_usuario.get(uid, -1.0):
                por_usuario[uid] = s
        ordem = sorted(por_usuario.items(), key=lambda kv: kv[1], reverse=True)
        melhor_id, melhor_sim = ordem[0]
        segunda = ordem[1][1] if len(ordem) > 1 else 0.0
        usuario = next(u for u in self._usuarios if u.id == melhor_id)
        if melhor_sim < config.LIMIAR_COSSENO:
            return Identificacao(None, float(melhor_sim), float(segunda))
        return Identificacao(usuario, float(melhor_sim), float(segunda))


def decidir_acesso(ident: Identificacao | None, nivel_exigido: int) -> Decisao:
    """Aplica o esquema de permissões do enunciado."""
    area = config.AREAS.get(nivel_exigido, f"nível {nivel_exigido}")
    if ident is None or not ident.reconhecido:
        return Decisao(
            Resultado.NEGADO_DESCONHECIDO, ident, nivel_exigido,
            "Rosto não cadastrado. Acesso negado.",
        )
    u = ident.usuario
    if u.nivel >= nivel_exigido:
        return Decisao(
            Resultado.CONCEDIDO, ident, nivel_exigido,
            f"Bem-vindo(a), {u.nome}. Acesso liberado: {area}.",
        )
    return Decisao(
        Resultado.NEGADO_NIVEL, ident, nivel_exigido,
        f"{u.nome} possui nível {u.nivel} ({config.NIVEIS[u.nivel]}); "
        f"a área exige nível {nivel_exigido}.",
    )

```

## `cofre/hud.py` (115 linhas)

```python
"""Desenho da interface sobre o vídeo (HUD) e painel didático das fases."""

from __future__ import annotations

import unicodedata

import cv2
import numpy as np

# Cores BGR
VERDE = (60, 200, 60)
VERMELHO = (40, 40, 230)
AMARELO = (30, 200, 240)
AZUL = (230, 150, 40)
BRANCO = (255, 255, 255)
PRETO = (0, 0, 0)
CINZA = (90, 90, 90)
LARANJA = (0, 140, 255)

FONTE = cv2.FONT_HERSHEY_SIMPLEX


def sem_acentos(texto: str) -> str:
    """As fontes Hershey do OpenCV não desenham acentos; removemos antes de exibir."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def texto(img, msg: str, pos, escala=0.6, cor=BRANCO, espessura=2, fundo=None, margem=4):
    msg = sem_acentos(msg)
    (tw, th), base = cv2.getTextSize(msg, FONTE, escala, espessura)
    x, y = int(pos[0]), int(pos[1])
    if fundo is not None:
        cv2.rectangle(img, (x - margem, y - th - margem), (x + tw + margem, y + base + margem), fundo, -1)
    cv2.putText(img, msg, (x, y), FONTE, escala, cor, espessura, cv2.LINE_AA)
    return th + base + 2 * margem


def caixa_rosto(img, rosto, cor, rotulo: str | None = None, espessura=2):
    x, y, w, h = rosto.caixa
    cv2.rectangle(img, (x, y), (x + w, y + h), cor, espessura)
    # cantos destacados
    c = max(8, w // 8)
    for (px, py, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        cv2.line(img, (px, py), (px + dx * c, py), cor, espessura + 2)
        cv2.line(img, (px, py), (px, py + dy * c), cor, espessura + 2)
    if rotulo:
        texto(img, rotulo, (x, max(20, y - 8)), 0.6, BRANCO, 2, fundo=cor)


def pontos_faciais(img, rosto, cor=AMARELO):
    for p in (rosto.olho_dir, rosto.olho_esq, rosto.nariz, rosto.boca_dir, rosto.boca_esq):
        cv2.circle(img, (int(p[0]), int(p[1])), 3, cor, -1, cv2.LINE_AA)


def barra_similaridade(img, pos, largura, valor: float, limiar: float):
    """Barra horizontal 0..1 com marcação do limiar."""
    x, y = pos
    h = 14
    cv2.rectangle(img, (x, y), (x + largura, y + h), CINZA, -1)
    v = int(max(0.0, min(1.0, valor)) * largura)
    cv2.rectangle(img, (x, y), (x + v, y + h), VERDE if valor >= limiar else VERMELHO, -1)
    lx = x + int(limiar * largura)
    cv2.line(img, (lx, y - 3), (lx, y + h + 3), BRANCO, 2)
    texto(img, f"{valor:.2f}", (x + largura + 8, y + h - 1), 0.5, BRANCO, 1)


def painel_topo(img, linhas: list[tuple[str, tuple]], altura=None):
    """Faixa escura semitransparente no topo com linhas de texto (msg, cor)."""
    h = altura or (22 * len(linhas) + 16)
    sobre = img.copy()
    cv2.rectangle(sobre, (0, 0), (img.shape[1], h), PRETO, -1)
    cv2.addWeighted(sobre, 0.55, img, 0.45, 0, img)
    y = 24
    for msg, cor in linhas:
        texto(img, msg, (12, y), 0.6, cor, 2)
        y += 22


def faixa_resultado(img, msg: str, cor):
    """Faixa grande no rodapé para o veredito (concedido/negado)."""
    h, w = img.shape[:2]
    sobre = img.copy()
    cv2.rectangle(sobre, (0, h - 70), (w, h), cor, -1)
    cv2.addWeighted(sobre, 0.8, img, 0.2, 0, img)
    texto(img, msg, (16, h - 26), 0.9, BRANCO, 2)


def rodape(img, msg: str):
    h, w = img.shape[:2]
    texto(img, msg, (12, h - 10), 0.5, BRANCO, 1, fundo=PRETO)


def _para_bgr(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img


def mosaico(etapas: dict[str, np.ndarray], lado: int = 220, colunas: int = 4) -> np.ndarray:
    """Monta um painel com miniaturas rotuladas de cada etapa do pipeline."""
    blocos = []
    for nome, img in etapas.items():
        img = _para_bgr(img)
        h, w = img.shape[:2]
        esc = lado / max(h, w)
        mini = cv2.resize(img, (max(1, int(w * esc)), max(1, int(h * esc))))
        tela = np.full((lado + 28, lado, 3), 30, np.uint8)
        oy, ox = (lado - mini.shape[0]) // 2, (lado - mini.shape[1]) // 2
        tela[oy:oy + mini.shape[0], ox:ox + mini.shape[1]] = mini
        texto(tela, nome, (6, lado + 20), 0.5, BRANCO, 1)
        blocos.append(tela)
    if not blocos:
        return np.zeros((lado, lado, 3), np.uint8)
    while len(blocos) % colunas:
        blocos.append(np.full_like(blocos[0], 30))
    linhas = [np.hstack(blocos[i:i + colunas]) for i in range(0, len(blocos), colunas)]
    return np.vstack(linhas)

```

## `cofre/liveness.py` (115 linhas)

```python
"""
Anti-fraude (prova de vida) simples, baseado em geometria dos pontos faciais.

Uma foto impressa ou exibida no celular reproduz um rosto estático. O desafio
pede que a pessoa vire a cabeça para os dois lados; a razão nariz/olhos (yaw)
muda de sinal apenas em um rosto tridimensional real que gira na frente da
câmera. Não é um método infalível (um vídeo pode enganar), mas eleva a barreira
contra o ataque mais comum e é explicável na dissertação.
"""

from __future__ import annotations

import time
from enum import Enum

from . import config


class EtapaLiveness(str, Enum):
    INATIVO = "INATIVO"
    VIRAR_ESQUERDA = "VIRAR_ESQUERDA"
    VIRAR_DIREITA = "VIRAR_DIREITA"
    VOLTAR_CENTRO = "VOLTAR_CENTRO"
    APROVADO = "APROVADO"
    FALHOU = "FALHOU"


class DesafioMovimento:
    """Máquina de estados: esquerda -> direita -> centro, dentro do tempo limite."""

    def __init__(self, limiar: float = config.LIVENESS_LIMIAR_YAW, timeout: float = config.LIVENESS_TIMEOUT_SEG,
                 relogio=time.time):
        self.limiar = limiar
        self.timeout = timeout
        self._relogio = relogio
        self.etapa = EtapaLiveness.INATIVO
        self._inicio = 0.0
        self.historico: list[float] = []

    def iniciar(self) -> None:
        self.etapa = EtapaLiveness.VIRAR_ESQUERDA
        self._inicio = self._relogio()
        self.historico = []

    @property
    def ativo(self) -> bool:
        return self.etapa in (EtapaLiveness.VIRAR_ESQUERDA, EtapaLiveness.VIRAR_DIREITA, EtapaLiveness.VOLTAR_CENTRO)

    @property
    def tempo_restante(self) -> float:
        return max(0.0, self.timeout - (self._relogio() - self._inicio))

    @property
    def instrucao(self) -> str:
        return {
            EtapaLiveness.VIRAR_ESQUERDA: "Vire o rosto para a ESQUERDA",
            EtapaLiveness.VIRAR_DIREITA: "Agora vire para a DIREITA",
            EtapaLiveness.VOLTAR_CENTRO: "Olhe para a camera",
            EtapaLiveness.APROVADO: "Prova de vida OK",
            EtapaLiveness.FALHOU: "Prova de vida falhou",
            EtapaLiveness.INATIVO: "",
        }[self.etapa]

    def atualizar(self, yaw: float | None) -> EtapaLiveness:
        """Recebe o yaw do frame atual (None se nenhum rosto) e avança a máquina."""
        if not self.ativo:
            return self.etapa
        if self.tempo_restante <= 0:
            self.etapa = EtapaLiveness.FALHOU
            return self.etapa
        if yaw is None:
            return self.etapa
        self.historico.append(yaw)
        if self.etapa is EtapaLiveness.VIRAR_ESQUERDA and yaw <= -self.limiar:
            self.etapa = EtapaLiveness.VIRAR_DIREITA
        elif self.etapa is EtapaLiveness.VIRAR_DIREITA and yaw >= self.limiar:
            self.etapa = EtapaLiveness.VOLTAR_CENTRO
        elif self.etapa is EtapaLiveness.VOLTAR_CENTRO and abs(yaw) < self.limiar / 2:
            self.etapa = EtapaLiveness.APROVADO
        return self.etapa


class ControleTentativas:
    """Bloqueio temporário do terminal após várias negações seguidas (força bruta)."""

    def __init__(self, max_falhas: int = config.MAX_TENTATIVAS_FALHAS, janela: float = config.JANELA_FALHAS_SEG,
                 bloqueio: float = config.BLOQUEIO_SEG, relogio=time.time):
        self.max_falhas = max_falhas
        self.janela = janela
        self.bloqueio = bloqueio
        self._relogio = relogio
        self._falhas: list[float] = []
        self._bloqueado_ate = 0.0

    def registrar_falha(self) -> bool:
        """Retorna True se esta falha acionou o bloqueio."""
        agora = self._relogio()
        self._falhas = [t for t in self._falhas if agora - t <= self.janela]
        self._falhas.append(agora)
        if len(self._falhas) >= self.max_falhas:
            self._bloqueado_ate = agora + self.bloqueio
            self._falhas = []
            return True
        return False

    def registrar_sucesso(self) -> None:
        self._falhas = []

    @property
    def bloqueado(self) -> bool:
        return self._relogio() < self._bloqueado_ate

    @property
    def segundos_restantes(self) -> float:
        return max(0.0, self._bloqueado_ate - self._relogio())

```

## `cofre/parametros.py` (186 linhas)

```python
"""
Parâmetros ajustáveis do sistema, sem depender de nenhuma interface gráfica.

Cada `Campo` descreve um atributo de `cofre.config` (tipo, intervalo, seção e explicação).
As duas interfaces (customtkinter e Qt/QML) usam estas definições, e as funções do fim
do arquivo leem, aplicam e gravam o arquivo `config_usuario.json`.

Alguns objetos leem `config` no momento do uso (ex.: o limiar de similaridade, a cada frame)
e outros ao serem criados (`Confirmador`, `DesafioMovimento`, `ControleTentativas`,
`SessaoCadastro`). Estes só enxergam o valor novo na próxima sessão de câmera.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config

ARQUIVO_CONFIG_NOME = "config_usuario.json"

MENSAGEM_APLICADO = (
    "Aplicado: vale para a próxima sessão de câmera. Limiar de similaridade, nitidez mínima, "
    "múltiplos rostos e tempo do resultado valem imediatamente; frames de confirmação, prova de vida, "
    "tentativas/bloqueio, amostras e câmera são lidos quando o terminal ou o cadastro é criado."
)


@dataclass(frozen=True)
class Campo:
    """Descreve um campo do formulário ligado a um atributo de `cofre.config`."""

    chave: str
    rotulo: str
    explicacao: str
    tipo: str                      # "float" | "int" | "bool"
    minimo: float = 0.0
    maximo: float = 1.0
    passo: float = 1.0
    casas: int = 0                 # casas decimais exibidas (float)
    secao: str = ""

    def normalizar(self, valor: Any) -> Any:
        """Converte e limita o valor ao tipo e ao intervalo do campo. Levanta ValueError se inválido."""
        if self.tipo == "bool":
            if isinstance(valor, bool):
                return valor
            if isinstance(valor, (int, float)) and valor in (0, 1):
                return bool(valor)
            raise ValueError(f"{self.chave}: esperado verdadeiro/falso, recebido {valor!r}")
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError(f"{self.chave}: esperado número, recebido {valor!r}")
        v = float(valor)
        if v != v:  # NaN
            raise ValueError(f"{self.chave}: valor inválido")
        v = min(self.maximo, max(self.minimo, v))
        if self.tipo == "int":
            return int(round(v))
        return round(v, max(self.casas, 3))

    def formatar(self, valor: Any) -> str:
        if self.tipo == "bool":
            return "ligado" if valor else "desligado"
        if self.tipo == "int":
            return str(int(valor))
        return f"{float(valor):.{self.casas}f}"


CAMPOS: tuple[Campo, ...] = (
    Campo("LIMIAR_COSSENO", "Limiar de similaridade (cosseno)",
          "Acima deste valor o rosto é considerado a mesma pessoa. Maior = mais rígido, mais rejeições de "
          "cadastrados; menor = mais aceitações indevidas. O OpenCV recomenda 0,363 para o SFace.",
          "float", 0.20, 0.80, 0.005, 3, "Reconhecimento"),
    Campo("FRAMES_CONFIRMACAO", "Frames de confirmação",
          "Quantos frames seguidos precisam apontar a mesma identidade antes de decidir. Evita decisão em "
          "um frame ruim; valores altos deixam a resposta mais lenta.",
          "int", 2, 15, 1, 0, "Reconhecimento"),
    Campo("LIVENESS_ATIVO", "Prova de vida (liveness)",
          "Exige que a pessoa vire a cabeça (esquerda, direita, centro) antes de liberar. Dificulta fraude "
          "com foto ou vídeo na frente da câmera.",
          "bool", secao="Prova de vida"),
    Campo("LIVENESS_LIMIAR_YAW", "Limiar de giro da cabeça (yaw)",
          "Razão nariz/olhos a partir da qual a cabeça conta como virada. Menor = basta um giro leve; maior "
          "= precisa virar mais, o que reduz falsos positivos do desafio.",
          "float", 0.10, 0.40, 0.01, 2, "Prova de vida"),
    Campo("LIVENESS_TIMEOUT_SEG", "Tempo limite do desafio (s)",
          "Segundos para completar o movimento. Se estourar, a tentativa é negada por prova de vida.",
          "int", 5, 30, 1, 0, "Prova de vida"),
    Campo("MAX_TENTATIVAS_FALHAS", "Máximo de falhas seguidas",
          "Negações consecutivas (na janela de tempo) antes de bloquear o terminal. Protege contra "
          "tentativa e erro.",
          "int", 1, 10, 1, 0, "Anti-fraude"),
    Campo("BLOQUEIO_SEG", "Duração do bloqueio (s)",
          "Por quanto tempo o terminal fica bloqueado depois de atingir o máximo de falhas.",
          "int", 5, 300, 1, 0, "Anti-fraude"),
    Campo("BLOQUEAR_MULTIPLOS_ROSTOS", "Bloquear mais de um rosto",
          "Com mais de uma pessoa no quadro a autenticação é negada (evita 'carona' / tailgating).",
          "bool", secao="Anti-fraude"),
    Campo("AMOSTRAS_POR_CADASTRO", "Amostras por cadastro",
          "Quantidade de embeddings capturados ao cadastrar alguém. Mais amostras = cadastro mais robusto "
          "a pose e iluminação, porém mais demorado.",
          "int", 5, 30, 1, 0, "Cadastro e qualidade"),
    Campo("INTERVALO_AMOSTRAS_SEG", "Intervalo entre amostras (s)",
          "Tempo entre duas capturas do cadastro. Precisa dar tempo de seguir a instrução de pose; "
          "intervalos curtos geram amostras quase iguais, todas de frente.",
          "float", 0.2, 3.0, 0.1, 1, "Cadastro e qualidade"),
    Campo("POSE_MAX_YAW", "Giro máximo do rosto (yaw)",
          "Razão nariz/olhos acima da qual o terminal pede para olhar para a câmera em vez de tentar "
          "reconhecer. Rostos de frente ficam abaixo de 0,45. Menor = mais exigente com a pose.",
          "float", 0.30, 1.20, 0.05, 2, "Pose para autenticar"),
    Campo("POSE_MAX_ROLL_GRAUS", "Inclinação máxima da cabeça (graus)",
          "Ângulo da linha dos olhos acima do qual o terminal pede para endireitar a cabeça. "
          "Rostos retos ficam abaixo de 20°.",
          "float", 10, 45, 1, 0, "Pose para autenticar"),
    Campo("POSE_RAZAO_NARIZ_MAX", "Cabeça baixa: razão máxima do nariz",
          "Posição do nariz entre os olhos (0) e a boca (1). Acima disso a cabeça está baixa demais e o "
          "terminal pede para levantar. De frente fica em 0,5 a 0,7.",
          "float", 0.65, 0.95, 0.01, 2, "Pose para autenticar"),
    Campo("POSE_RAZAO_NARIZ_MIN", "Cabeça erguida: razão mínima do nariz",
          "Abaixo disso a cabeça está erguida demais e o terminal pede para abaixar o queixo.",
          "float", 0.20, 0.50, 0.01, 2, "Pose para autenticar"),
    Campo("MIN_NITIDEZ", "Nitidez mínima",
          "Variância do Laplaciano abaixo da qual o rosto é tratado como borrado e descartado. Suba se "
          "estiver aceitando imagens ruins; desça se a câmera for de baixa qualidade.",
          "float", 10, 200, 1, 0, "Cadastro e qualidade"),
    Campo("CAMERA_INDEX", "Índice da câmera",
          "Qual dispositivo de vídeo abrir (0 = padrão do sistema). Mude se houver mais de uma câmera.",
          "int", 0, 5, 1, 0, "Câmera"),
    Campo("ESPELHAR_CAMERA", "Espelhar a imagem",
          "Exibe o vídeo como um espelho, mais natural para quem está na frente da câmera.",
          "bool", secao="Câmera"),
    Campo("SESSAO_LIBERADA_SEG", "Tempo da área liberada (s)",
          "Depois de um acesso concedido, a área fica aberta por este tempo sem interação antes de fechar "
          "sozinha e o terminal voltar a aguardar.",
          "int", 15, 600, 5, 0, "Câmera"),
    Campo("TEMPO_EXIBIR_RESULTADO_SEG", "Tempo do resultado na tela (s)",
          "Quanto tempo a decisão (concedido/negado) fica visível antes de o terminal voltar a aguardar.",
          "int", 1, 10, 1, 0, "Câmera"),
)

CAMPOS_POR_CHAVE: dict[str, Campo] = {c.chave: c for c in CAMPOS}


def caminho_arquivo() -> Path:
    """Arquivo de configuração do usuário (fica na pasta de dados, ignorado pelo Git)."""
    return Path(config.DATA_DIR) / ARQUIVO_CONFIG_NOME


def valores_atuais() -> dict[str, Any]:
    """Valores em vigor no módulo `cofre.config` para todos os campos."""
    return {c.chave: getattr(config, c.chave) for c in CAMPOS}


def normalizar_todos(valores: dict[str, Any]) -> dict[str, Any]:
    """Valida e limita todos os campos. Levanta ValueError/KeyError se faltar ou for inválido."""
    return {c.chave: c.normalizar(valores[c.chave]) for c in CAMPOS}


def aplicar(valores: dict[str, Any]) -> dict[str, Any]:
    """Valida tudo antes e só então grava em `cofre.config` (nada é aplicado pela metade)."""
    novos = normalizar_todos(valores)
    for chave, valor in novos.items():
        setattr(config, chave, valor)
    return novos


def ler_arquivo(caminho: Path | None = None) -> dict[str, Any]:
    """Lê o JSON e devolve só os parâmetros conhecidos, já normalizados."""
    caminho = caminho or caminho_arquivo()
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ValueError("o conteúdo precisa ser um objeto JSON com os nomes dos parâmetros")
    reconhecidos = {k: v for k, v in dados.items() if k in CAMPOS_POR_CHAVE}
    if not reconhecidos:
        raise ValueError("nenhum parâmetro conhecido no arquivo")
    return {k: CAMPOS_POR_CHAVE[k].normalizar(v) for k, v in reconhecidos.items()}


def salvar_arquivo(valores: dict[str, Any], caminho: Path | None = None) -> Path:
    caminho = Path(caminho or caminho_arquivo())
    novos = normalizar_todos(valores)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(novos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return caminho

```

## `cofre/pipeline.py` (80 linhas)

```python
"""
Encadeia as fases 2, 3 e 4 para um frame: pré-processamento -> detecção ->
alinhamento -> embedding. Usado pelo cadastro, pela autenticação, pela
avaliação e pela demonstração didática, para que todos sigam exatamente o
mesmo caminho de processamento.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import fase2_preprocessamento as f2
from . import fase3_segmentacao as f3
from . import fase4_representacao as f4


@dataclass
class RostoProcessado:
    rosto: f3.Rosto                 # coordenadas no frame ORIGINAL
    rosto_reduzido: f3.Rosto        # coordenadas no frame reduzido (para o HUD)
    alinhado: np.ndarray            # 112x112 BGR
    embedding: np.ndarray           # (128,) float32 normalizado
    qualidade: f2.Qualidade
    recorte: np.ndarray             # recorte simples com margem (fotos/evidências)


@dataclass
class ResultadoPipeline:
    pre: f2.ResultadoPreprocessamento
    rostos: list[RostoProcessado] = field(default_factory=list)

    @property
    def principal(self) -> RostoProcessado | None:
        return self.rostos[0] if self.rostos else None

    def etapas_didaticas(self) -> dict[str, np.ndarray]:
        """Imagens de todas as fases para o painel didático."""
        etapas = dict(self.pre.etapas)
        p = self.principal
        if p is not None:
            marcado = f3.desenhar_pontos(self.pre.equalizada, p.rosto_reduzido)
            x, y, w, h = p.rosto_reduzido.caixa
            import cv2
            cv2.rectangle(marcado, (x, y), (x + w, y + h), (0, 255, 0), 2)
            etapas["3 deteccao+pontos"] = marcado
            etapas["3 recorte"] = p.recorte
            etapas["3 alinhado 112x112"] = p.alinhado
            cinza = f2.converter_cinza(p.alinhado)
            etapas["4 LBP (textura)"] = f4.lbp_mapa(cinza)
            etapas["4 embedding 128-d"] = _embedding_como_imagem(p.embedding)
        return etapas


def _embedding_como_imagem(emb: np.ndarray, altura: int = 40) -> np.ndarray:
    """Visualiza o vetor de 128 dimensões como uma faixa de intensidades."""
    v = emb.reshape(1, -1)
    v = (v - v.min()) / ((v.max() - v.min()) or 1.0)
    faixa = (v * 255).astype(np.uint8)
    return np.repeat(faixa, altura, axis=0)


class Pipeline:
    def __init__(self):
        self.detector = f3.DetectorFacial()
        self.extrator = f4.ExtratorCaracteristicas()

    def processar(self, frame: np.ndarray, extrair_embedding: bool = True) -> ResultadoPipeline:
        pre = f2.preprocessar(frame)                         # fase 2
        rostos_red = self.detector.detectar(pre.equalizada)  # fase 3 (no frame reduzido)
        resultado = ResultadoPipeline(pre=pre)
        for rr in rostos_red:
            rosto = rr.escalar(1.0 / pre.escala) if pre.escala != 1.0 else rr
            recorte = f3.recortar(frame, rosto)
            alinhado = self.extrator.alinhar(frame, rosto)   # fase 3 (alinhamento)
            qualidade = f2.avaliar_qualidade(alinhado)
            emb = self.extrator.extrair(alinhado) if extrair_embedding else np.zeros(128, np.float32)  # fase 4
            resultado.rostos.append(RostoProcessado(rosto, rr, alinhado, emb, qualidade, recorte))
        return resultado

```

## `cofre/relatorios.py` (132 linhas)

```python
"""Relatórios: listagens no terminal e exportação CSV/HTML do log de acessos."""

from __future__ import annotations

import csv
import html
from datetime import datetime
from pathlib import Path

from . import config
from .banco import Banco

ROTULOS = {
    "CONCEDIDO": "Acesso concedido",
    "NEGADO_NIVEL": "Negado: nível insuficiente",
    "NEGADO_DESCONHECIDO": "Negado: não cadastrado",
    "NEGADO_LIVENESS": "Negado: prova de vida",
    "NEGADO_MULTIPLOS": "Negado: múltiplas pessoas",
    "BLOQUEADO": "Terminal bloqueado",
}


def tabela(linhas: list[list[str]], cabecalho: list[str]) -> str:
    cols = [cabecalho] + [[str(c) for c in l] for l in linhas]
    larg = [max(len(r[i]) for r in cols) for i in range(len(cabecalho))]
    sep = "-+-".join("-" * w for w in larg)
    fmt = lambda r: " | ".join(c.ljust(w) for c, w in zip(r, larg))  # noqa: E731
    return "\n".join([fmt(cabecalho), sep] + [fmt(r) for r in cols[1:]])


def texto_usuarios(banco: Banco) -> str:
    us = banco.listar_usuarios()
    if not us:
        return "Nenhum usuário cadastrado."
    linhas = [[u.id, u.nome, u.matricula, u.cargo, f"{u.nivel} - {u.nivel_descricao}",
               banco.contar_amostras(u.id), "sim" if u.ativo else "NÃO", u.criado_em] for u in us]
    return tabela(linhas, ["id", "nome", "matrícula", "cargo", "nível", "amostras", "ativo", "cadastro"])


def texto_acessos(banco: Banco, limite: int = 30) -> str:
    ac = banco.listar_acessos(limite)
    if not ac:
        return "Nenhuma tentativa de acesso registrada."
    linhas = [[a.data_hora.replace("T", " "), a.nome_detectado or "-", a.nivel_usuario or "-", a.nivel_exigido,
               f"{a.similaridade:.2f}" if a.similaridade is not None else "-", ROTULOS.get(a.resultado, a.resultado)]
              for a in ac]
    return tabela(linhas, ["data/hora", "pessoa", "nível", "exigido", "simil.", "resultado"])


def texto_estatisticas(banco: Banco) -> str:
    e = banco.estatisticas()
    partes = [
        f"Usuários cadastrados: {e['usuarios']}   Amostras biométricas: {e['amostras']}",
        f"Tentativas de acesso: {e['total']}",
    ]
    for k, v in sorted(e["por_resultado"].items()):
        partes.append(f"  {ROTULOS.get(k, k):32s} {v:5d}")
    if e["por_usuario"]:
        partes.append("\nPor pessoa:")
        partes.append(tabela([[p["nome"], p["concedidos"], p["negados"]] for p in e["por_usuario"]],
                             ["pessoa", "concedidos", "negados"]))
    if e["por_dia"]:
        partes.append("\nPor dia:")
        partes.append(tabela([[d["dia"], d["total"], d["concedidos"]] for d in e["por_dia"]],
                             ["dia", "tentativas", "concedidos"]))
    return "\n".join(partes)


def exportar_csv(banco: Banco, destino: Path | None = None) -> Path:
    config.RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)
    destino = destino or config.RELATORIOS_DIR / f"acessos_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "data_hora", "usuario_id", "nome", "nivel_usuario", "nivel_exigido", "area",
                    "similaridade", "resultado", "mensagem", "evidencia"])
        for a in banco.listar_acessos():
            w.writerow([a.id, a.data_hora, a.usuario_id, a.nome_detectado, a.nivel_usuario, a.nivel_exigido,
                        a.area, a.similaridade, a.resultado, a.mensagem, a.evidencia])
    return destino


def exportar_html(banco: Banco, destino: Path | None = None) -> Path:
    config.RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)
    destino = destino or config.RELATORIOS_DIR / f"relatorio_{datetime.now():%Y%m%d_%H%M%S}.html"
    e = banco.estatisticas()
    h = html.escape

    def linha_tr(cels, tag="td"):
        return "<tr>" + "".join(f"<{tag}>{h(str(c))}</{tag}>" for c in cels) + "</tr>"

    cards = "".join(
        f'<div class="card"><div class="n">{v}</div><div class="l">{h(ROTULOS.get(k, k))}</div></div>'
        for k, v in sorted(e["por_resultado"].items()))
    usuarios = "".join(linha_tr([u.id, u.nome, u.matricula, u.cargo, f"{u.nivel} - {u.nivel_descricao}",
                                 banco.contar_amostras(u.id), "sim" if u.ativo else "não"])
                       for u in banco.listar_usuarios())
    acessos = "".join(
        f'<tr class="{ "ok" if a.resultado == "CONCEDIDO" else "neg"}">'
        + "".join(f"<td>{h(str(c))}</td>" for c in [
            a.data_hora.replace("T", " "), a.nome_detectado or "-", a.nivel_usuario or "-", a.nivel_exigido,
            a.area, f"{a.similaridade:.3f}" if a.similaridade is not None else "-",
            ROTULOS.get(a.resultado, a.resultado), a.mensagem or ""])
        + (f'<td><a href="file://{h(a.evidencia)}">foto</a></td>' if a.evidencia else "<td></td>") + "</tr>"
        for a in banco.listar_acessos())
    por_pessoa = "".join(linha_tr([p["nome"], p["concedidos"], p["negados"]]) for p in e["por_usuario"])
    por_dia = "".join(linha_tr([d["dia"], d["total"], d["concedidos"]]) for d in e["por_dia"])
    doc = f"""<!DOCTYPE html><html lang="pt-br"><head><meta charset="utf-8">
<title>Relatório de acessos - Cofre MMA</title>
<style>
body{{font-family:Arial,Helvetica,sans-serif;margin:32px;color:#222}}
h1{{margin-bottom:0}} .sub{{color:#666;margin-top:4px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}}
.card{{border:1px solid #ddd;border-radius:8px;padding:12px 18px;min-width:140px}}
.card .n{{font-size:28px;font-weight:bold}} .card .l{{font-size:12px;color:#666}}
table{{border-collapse:collapse;width:100%;margin-bottom:28px;font-size:13px}}
th,td{{border:1px solid #ddd;padding:6px 8px;text-align:left}} th{{background:#f3f3f3}}
tr.ok td{{background:#eefbee}} tr.neg td{{background:#fdeeee}}
</style></head><body>
<h1>Sistema de Autenticação Biométrica - Cofre do Ministério do Meio Ambiente</h1>
<p class="sub">Relatório gerado em {datetime.now():%d/%m/%Y %H:%M:%S} · {e['usuarios']} usuários · {e['amostras']} amostras · {e['total']} tentativas</p>
<div class="cards">{cards}</div>
<h2>Usuários autorizados</h2>
<table><tr><th>id</th><th>nome</th><th>matrícula</th><th>cargo</th><th>nível</th><th>amostras</th><th>ativo</th></tr>{usuarios}</table>
<h2>Tentativas por pessoa</h2>
<table><tr><th>pessoa</th><th>concedidos</th><th>negados</th></tr>{por_pessoa}</table>
<h2>Tentativas por dia</h2>
<table><tr><th>dia</th><th>tentativas</th><th>concedidos</th></tr>{por_dia}</table>
<h2>Log completo de acessos</h2>
<table><tr><th>data/hora</th><th>pessoa</th><th>nível</th><th>exigido</th><th>área</th><th>similaridade</th><th>resultado</th><th>mensagem</th><th>evidência</th></tr>{acessos}</table>
</body></html>"""
    destino.write_text(doc, encoding="utf-8")
    return destino

```

## `cofre/interface/__init__.py` (10 linhas)

```python
"""Aplicativo desktop (customtkinter) do sistema de autenticação biométrica.

Estrutura:
  app.py            janela principal, barra lateral e troca de telas
  camera.py         serviço de câmera em thread (captura + pipeline)
  widgets.py        VideoWidget, cartões, tabela escura, barra de status
  tema.py           cores, fontes e conversão de imagens
  base.py           classe base das telas
  tela_*.py         uma tela por funcionalidade
"""

```

## `cofre/interface/app.py` (160 linhas)

```python
"""Janela principal do aplicativo: barra lateral, área de conteúdo e ciclo de atualização."""

from __future__ import annotations

import importlib
import threading
import traceback

import customtkinter as ctk

from .. import __version__, config
from ..banco import Banco
from . import tema
from .base import Tela
from .camera import ServicoCamera
from .widgets import BarraStatus

# (módulo, classe, rótulo do menu)
TELAS = [
    ("tela_terminal", "TelaTerminal", "Terminal de acesso"),
    ("tela_cadastro", "TelaCadastro", "Cadastro biométrico"),
    ("tela_usuarios", "TelaUsuarios", "Usuários"),
    ("tela_acessos", "TelaAcessos", "Acessos e relatórios"),
    ("tela_ferramentas", "TelaFerramentas", "Avaliação e demo"),
    ("tela_config", "TelaConfig", "Configurações"),
]

INTERVALO_MS = 33  # ~30 atualizações por segundo


class TelaIndisponivel(Tela):
    def __init__(self, master, app, nome: str, erro: str):
        self._nome, self._erro = nome, erro
        super().__init__(master, app)

    def construir(self) -> None:
        ctk.CTkLabel(self, text=f"Tela '{self._nome}' indisponível", font=tema.TITULO,
                     text_color=tema.VERMELHO).pack(padx=24, pady=(24, 8), anchor="w")
        ctk.CTkLabel(self, text=self._erro, font=tema.MONO, text_color=tema.TEXTO_2, justify="left",
                     wraplength=900).pack(padx=24, anchor="w")


class App(ctk.CTk):
    def __init__(self, caminho_db=config.DB_PATH, fonte_camera=None):
        """`fonte_camera`: fábrica da fonte de vídeo (padrão: a webcam). Os testes passam uma
        câmera falsa aqui, porque a primeira tela já liga a câmera durante o construtor."""
        super().__init__(fg_color=tema.FUNDO)
        ctk.set_appearance_mode("dark")
        self.title("Cofre MMA - Autenticação Biométrica")
        self.geometry("1280x800")
        self.minsize(1024, 680)
        self.banco = Banco(caminho_db)
        self.camera = ServicoCamera()
        if fonte_camera is not None:
            self.camera.fonte_fabrica = fonte_camera
        self.pipeline = None            # carregado em thread (modelos ONNX levam ~0,5 s)
        self._erro_pipeline: str | None = None
        self._telas: dict[str, Tela] = {}
        self._botoes: dict[str, ctk.CTkButton] = {}
        self._atual: str | None = None
        self._construir()
        threading.Thread(target=self._carregar_pipeline, daemon=True).start()
        self.after(INTERVALO_MS, self._tick)
        self.protocol("WM_DELETE_WINDOW", self.fechar)

    # ------------------------------------------------------------------ layout
    def _construir(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        lateral = ctk.CTkFrame(self, width=230, fg_color=tema.FUNDO_2, corner_radius=0)
        lateral.grid(row=0, column=0, sticky="nsw")
        lateral.grid_propagate(False)
        ctk.CTkLabel(lateral, text="COFRE MMA", font=(tema.FONTE, 20, "bold"), text_color=tema.ACENTO).pack(
            padx=20, pady=(26, 0), anchor="w")
        ctk.CTkLabel(lateral, text="Autenticação biométrica facial", font=tema.PEQUENO,
                     text_color=tema.TEXTO_2).pack(padx=20, pady=(0, 24), anchor="w")
        for mod, cls, rotulo in TELAS:
            b = ctk.CTkButton(lateral, text=rotulo, anchor="w", height=40, corner_radius=8, font=tema.CORPO,
                              fg_color="transparent", hover_color=tema.CARTAO, text_color=tema.TEXTO,
                              command=lambda m=mod: self.mostrar(m))
            b.pack(fill="x", padx=12, pady=3)
            self._botoes[mod] = b
        ctk.CTkLabel(lateral, text=f"v{__version__}", font=tema.PEQUENO, text_color=tema.TEXTO_2).pack(
            side="bottom", pady=12)
        self.area = ctk.CTkFrame(self, fg_color=tema.FUNDO, corner_radius=0)
        self.area.grid(row=0, column=1, sticky="nsew")
        self.area.grid_rowconfigure(0, weight=1)
        self.area.grid_columnconfigure(0, weight=1)
        self.status = BarraStatus(self)
        self.status.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.status.definir("Carregando modelos...", f"banco: {self.banco.caminho.name}")
        self.mostrar(TELAS[0][0])

    def _carregar_pipeline(self) -> None:
        try:
            from ..pipeline import Pipeline
            self.pipeline = Pipeline()
        except Exception as e:  # noqa: BLE001
            self._erro_pipeline = f"Falha ao carregar os modelos: {e}"

    # ------------------------------------------------------------------ telas
    def _instanciar(self, mod: str) -> Tela:
        _, cls, rotulo = next(t for t in TELAS if t[0] == mod)
        try:
            modulo = importlib.import_module(f"{__package__}.{mod}")
            return getattr(modulo, cls)(self.area, self)
        except Exception:  # noqa: BLE001
            return TelaIndisponivel(self.area, self, rotulo, traceback.format_exc())

    def mostrar(self, mod: str) -> None:
        if mod == self._atual:
            return
        if self._atual is not None:
            atual = self._telas[self._atual]
            atual.ao_esconder()
            atual.grid_forget()
            self._botoes[self._atual].configure(fg_color="transparent", text_color=tema.TEXTO)
        if mod not in self._telas:
            self._telas[mod] = self._instanciar(mod)
        tela = self._telas[mod]
        tela.grid(row=0, column=0, sticky="nsew")
        self._botoes[mod].configure(fg_color=tema.CARTAO, text_color=tema.ACENTO)
        self._atual = mod
        if self.pipeline is not None:   # enquanto carrega, mantém o aviso de "Carregando modelos..."
            self.status.definir(next(t[2] for t in TELAS if t[0] == mod), None)
        tela.ao_mostrar()

    def tela(self, mod: str) -> Tela | None:
        return self._telas.get(mod)

    # ------------------------------------------------------------------ ciclo
    def _tick(self) -> None:
        try:
            if self.pipeline is not None and self.status.esq.cget("text") == "Carregando modelos...":
                self.status.definir("Modelos carregados", None)
            if self._erro_pipeline:
                self.status.definir(self._erro_pipeline, None)
            if self.camera.erro:
                self.status.definir(f"Câmera: {self.camera.erro}", None)
            if self._atual is not None:
                self._telas[self._atual].atualizar()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        self.after(INTERVALO_MS, self._tick)

    def pipeline_pronto(self) -> bool:
        return self.pipeline is not None

    def fechar(self) -> None:
        try:
            if self._atual is not None:
                self._telas[self._atual].ao_esconder()
            self.camera.parar()
            self.banco.fechar()
        finally:
            self.destroy()


def executar(caminho_db=config.DB_PATH) -> None:
    App(caminho_db).mainloop()

```

## `cofre/interface/base.py` (33 linhas)

```python
"""Classe base das telas do aplicativo."""

from __future__ import annotations

import customtkinter as ctk

from . import tema


class Tela(ctk.CTkFrame):
    """Cada tela recebe a referência do `App` (banco, pipeline, câmera, status) e
    implementa `ao_mostrar()` / `ao_esconder()` (ligar/desligar câmera etc.) e
    `atualizar()` (chamado ~30x por segundo enquanto visível, na thread do Tk)."""

    TITULO = ""
    ICONE = ""

    def __init__(self, master, app):
        super().__init__(master, fg_color=tema.FUNDO, corner_radius=0)
        self.app = app
        self.construir()

    def construir(self) -> None:
        """Monta os widgets. Chamado uma vez no construtor."""

    def ao_mostrar(self) -> None:
        """Chamado toda vez que a tela passa a ser exibida."""

    def ao_esconder(self) -> None:
        """Chamado quando o usuário troca para outra tela."""

    def atualizar(self) -> None:
        """Chamado periodicamente (~30 Hz) enquanto a tela está visível."""

```

## `cofre/interface/camera.py` (89 linhas)

```python
"""
Serviço de câmera em thread separada.

A thread captura frames, roda um `processador(frame) -> resultado` (normalmente o
pipeline + a lógica da tela) e guarda só o último resultado. A interface, na thread
principal do Tk, chama `ultimo()` periodicamente. Tk não é thread-safe, por isso a
thread nunca toca em widgets.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from ..fase1_aquisicao import ErroAquisicao, FonteCamera


class ServicoCamera:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._lock = threading.Lock()
        self._ultimo: Any = None
        self._processador: Callable[[Any], Any] | None = None
        self.erro: str | None = None
        self.fps = 0.0
        self.ativo = False
        # Fábrica da fonte de vídeo: trocável por uma fonte falsa nos testes
        # (qualquer context manager com `.frames()` e `.fps_medido`).
        self.fonte_fabrica: Callable[[], Any] = FonteCamera

    def definir_processador(self, fn: Callable[[Any], Any] | None) -> None:
        with self._lock:
            self._processador = fn
            self._ultimo = None

    def iniciar(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._parar.clear()
        self.erro = None
        try:
            fonte = self.fonte_fabrica()
            if isinstance(fonte, FonteCamera):
                fonte.preparar()  # thread principal: no macOS é o que permite o pedido de permissão
        except Exception as e:  # noqa: BLE001
            self.erro = f"Falha na câmera: {e}"
            return
        self._thread = threading.Thread(target=self._loop, args=(fonte,), name="camera", daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self._thread = None
        self.ativo = False
        with self._lock:
            self._ultimo = None

    def ultimo(self) -> Any:
        with self._lock:
            return self._ultimo

    def _loop(self, fonte) -> None:
        try:
            with fonte as cam:
                self.ativo = True
                for frame in cam.frames():
                    if self._parar.is_set():
                        break
                    with self._lock:
                        fn = self._processador
                    try:
                        saida = fn(frame) if fn is not None else frame
                    except Exception as e:  # noqa: BLE001
                        self.erro = f"Erro no processamento: {e}"
                        saida = frame
                    self.fps = cam.fps_medido
                    with self._lock:
                        self._ultimo = saida
                    time.sleep(0.001)
        except ErroAquisicao as e:
            self.erro = str(e)
        except Exception as e:  # noqa: BLE001
            self.erro = f"Falha na câmera: {e}"
        finally:
            self.ativo = False

```

## `cofre/interface/tela_acessos.py` (433 linhas)

```python
"""Tela "Acessos e relatórios": estatísticas, log de auditoria com filtros, evidências e exportação."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from .. import config, relatorios
from ..banco import Acesso, Banco
from . import tema
from .base import Tela
from .widgets import Cartao, Tabela, botao, botao_secundario, titulo

TODOS = "Todos"
LIMITES = ("50", "200", "1000")
# Rótulos curtos para os cartões de negação (os completos estão em tema.ROTULO_RESULTADO)
ROTULO_CARTAO = {
    "NEGADO_NIVEL": "Nível insuficiente",
    "NEGADO_DESCONHECIDO": "Não cadastrados",
    "NEGADO_LIVENESS": "Prova de vida",
    "NEGADO_MULTIPLOS": "Mais de uma pessoa",
    "BLOQUEADO": "Bloqueios",
}


def _abrir_no_sistema(caminho: Path) -> None:
    """Abre um arquivo ou pasta com o aplicativo padrão do sistema operacional."""
    sistema = platform.system()
    if sistema == "Windows":
        os.startfile(str(caminho))  # type: ignore[attr-defined]  # noqa: S606
    elif sistema == "Darwin":
        subprocess.Popen(["open", str(caminho)])  # noqa: S603, S607
    else:
        subprocess.Popen(["xdg-open", str(caminho)])  # noqa: S603, S607


def _tag_resultado(resultado: str) -> str:
    if resultado == "CONCEDIDO":
        return "ok"
    if resultado == "NEGADO_NIVEL":
        return "aviso"
    return "neg"


class TelaAcessos(Tela):
    """Mostra o log de acessos com filtros, cartões de estatísticas, resumo por pessoa e por dia,
    e exporta relatórios CSV/HTML (em thread) com atalho para abrir o arquivo gerado."""

    TITULO = "Acessos e relatórios"

    # ------------------------------------------------------------------ construção
    def construir(self) -> None:
        self._acessos: dict[str, Acesso] = {}
        self._exportando = False
        self._resultado_exportacao: tuple[Path | None, str | None] | None = None  # (caminho, erro)
        self._ultimo_exportado: Path | None = None
        self._busca_agendada: str | None = None
        self._detalhe: ctk.CTkToplevel | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Cabeçalho: título + botões
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 12))
        cab.grid_columnconfigure(0, weight=1)
        titulo(cab, self.TITULO, "Log de auditoria das tentativas de autenticação").grid(row=0, column=0, sticky="w")
        botoes = ctk.CTkFrame(cab, fg_color="transparent")
        botoes.grid(row=0, column=1, sticky="e")
        self.btn_atualizar = botao_secundario(botoes, "Atualizar", self.recarregar, width=110)
        self.btn_atualizar.pack(side="left", padx=(0, 8))
        self.btn_evidencias = botao_secundario(botoes, "Abrir pasta de evidências", self.abrir_pasta_evidencias,
                                               width=190)
        self.btn_evidencias.pack(side="left", padx=(0, 8))
        self.btn_csv = botao(botoes, "Exportar CSV", lambda: self.exportar("csv"), width=120)
        self.btn_csv.pack(side="left", padx=(0, 8))
        self.btn_html = botao(botoes, "Exportar HTML", lambda: self.exportar("html"), width=130)
        self.btn_html.pack(side="left")

        # Cartões de estatísticas (duas fileiras de cinco)
        cartoes = ctk.CTkFrame(self, fg_color="transparent")
        cartoes.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        for c in range(5):
            cartoes.grid_columnconfigure(c, weight=1, uniform="cartao")
        self.cartoes: dict[str, Cartao] = {}
        linha1 = [("total", "Tentativas", tema.TEXTO), ("CONCEDIDO", "Concedidos", tema.VERDE),
                  ("negados", "Negados", tema.VERMELHO), ("usuarios", "Usuários", tema.ACENTO),
                  ("amostras", "Amostras", tema.ACENTO)]
        linha2 = [(k, r, tema.COR_RESULTADO[k]) for k, r in ROTULO_CARTAO.items()]
        for r, linha in enumerate((linha1, linha2)):
            for c, (chave, rotulo, cor) in enumerate(linha):
                cartao = Cartao(cartoes, rotulo, "0", cor)
                cartao.grid(row=r, column=c, sticky="ew", padx=(0 if c == 0 else 6, 0 if c == 4 else 6),
                            pady=(0, 8 if r == 0 else 0))
                self.cartoes[chave] = cartao

        # Filtros
        filtros = ctk.CTkFrame(self, fg_color="transparent")
        filtros.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        ctk.CTkLabel(filtros, text="Resultado", font=tema.PEQUENO, text_color=tema.TEXTO_2).pack(side="left")
        self._rotulo_para_chave = {v: k for k, v in tema.ROTULO_RESULTADO.items()}
        self.var_resultado = ctk.StringVar(value=TODOS)
        self.menu_resultado = ctk.CTkOptionMenu(
            filtros, values=[TODOS, *tema.ROTULO_RESULTADO.values()], variable=self.var_resultado,
            command=lambda _v: self.recarregar(), font=tema.CORPO, width=230, fg_color=tema.CARTAO,
            button_color=tema.BORDA, button_hover_color=tema.ACENTO_HOVER, dropdown_fg_color=tema.CARTAO)
        self.menu_resultado.pack(side="left", padx=(8, 16))
        ctk.CTkLabel(filtros, text="Pessoa", font=tema.PEQUENO, text_color=tema.TEXTO_2).pack(side="left")
        self.var_busca = ctk.StringVar()
        self.entrada_busca = ctk.CTkEntry(filtros, textvariable=self.var_busca, placeholder_text="buscar por nome",
                                          font=tema.CORPO, width=220, fg_color=tema.CARTAO, border_color=tema.BORDA)
        self.entrada_busca.pack(side="left", padx=(8, 16))
        self.entrada_busca.bind("<KeyRelease>", self._agendar_busca)
        ctk.CTkLabel(filtros, text="Limite", font=tema.PEQUENO, text_color=tema.TEXTO_2).pack(side="left")
        self.var_limite = ctk.StringVar(value=LIMITES[1])
        self.menu_limite = ctk.CTkOptionMenu(
            filtros, values=list(LIMITES), variable=self.var_limite, command=lambda _v: self.recarregar(),
            font=tema.CORPO, width=90, fg_color=tema.CARTAO, button_color=tema.BORDA,
            button_hover_color=tema.ACENTO_HOVER, dropdown_fg_color=tema.CARTAO)
        self.menu_limite.pack(side="left", padx=(8, 16))
        self.rotulo_contagem = ctk.CTkLabel(filtros, text="", font=tema.PEQUENO, text_color=tema.TEXTO_2)
        self.rotulo_contagem.pack(side="left")

        # Aviso / resultado da exportação (escondido até ser necessário)
        self.aviso = ctk.CTkFrame(self, fg_color=tema.CARTAO, corner_radius=10)
        self.aviso.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 12))
        self.aviso.grid_columnconfigure(0, weight=1)
        self.rotulo_aviso = ctk.CTkLabel(self.aviso, text="", font=tema.CORPO, text_color=tema.TEXTO, anchor="w",
                                         justify="left", wraplength=800)
        self.rotulo_aviso.grid(row=0, column=0, sticky="ew", padx=16, pady=10)
        self.btn_abrir = botao_secundario(self.aviso, "Abrir", self.abrir_exportado, width=90)
        self.btn_abrir.grid(row=0, column=1, padx=(0, 8), pady=6)
        self.btn_fechar_aviso = botao_secundario(self.aviso, "Fechar", self._esconder_aviso, width=80)
        self.btn_fechar_aviso.grid(row=0, column=2, padx=(0, 8), pady=6)
        self.aviso.grid_remove()

        # Corpo: tabela de acessos à esquerda, resumos à direita
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.grid(row=4, column=0, sticky="nsew", padx=24, pady=(0, 24))
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_columnconfigure(1, weight=0, minsize=330)
        corpo.grid_rowconfigure(0, weight=1)
        self.tabela = Tabela(corpo, [
            ("data", "Data/hora", 140), ("pessoa", "Pessoa", 140), ("nivel", "Nível", 50),
            ("exigido", "Exigido", 60), ("area", "Área", 170), ("simil", "Simil.", 60),
            ("resultado", "Resultado", 180), ("mensagem", "Mensagem", 220),
        ], altura=14, ao_duplo_clique=self._abrir_detalhe, rolagem_horizontal=True)
        # Só a ordem de exibição muda (os valores continuam na ordem acima): o que mais importa
        # aparece sem rolar; área e mensagem ficam à direita (e completas no duplo clique).
        self.tabela.tree.configure(displaycolumns=("data", "pessoa", "resultado", "nivel", "exigido", "simil",
                                                   "area", "mensagem"))
        self.tabela.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.tabela.tree.column("nivel", anchor="center")
        self.tabela.tree.column("exigido", anchor="center")
        self.tabela.tree.column("simil", anchor="e")

        lateral = ctk.CTkFrame(corpo, fg_color="transparent")
        lateral.grid(row=0, column=1, sticky="nsew")
        lateral.grid_columnconfigure(0, weight=1)
        lateral.grid_rowconfigure(1, weight=1)
        lateral.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(lateral, text="Por pessoa", font=tema.SUBTITULO, text_color=tema.TEXTO, anchor="w").grid(
            row=0, column=0, sticky="ew", pady=(0, 6))
        self.tabela_pessoas = Tabela(lateral, [("pessoa", "Pessoa", 150), ("conc", "Concedidos", 80),
                                               ("neg", "Negados", 70)], altura=6)
        self.tabela_pessoas.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        ctk.CTkLabel(lateral, text="Por dia", font=tema.SUBTITULO, text_color=tema.TEXTO, anchor="w").grid(
            row=2, column=0, sticky="ew", pady=(0, 6))
        self.tabela_dias = Tabela(lateral, [("dia", "Dia", 110), ("total", "Tentativas", 90),
                                            ("conc", "Concedidos", 90)], altura=6)
        self.tabela_dias.grid(row=3, column=0, sticky="nsew")
        for t in (self.tabela_pessoas, self.tabela_dias):
            for col in t.tree["columns"][1:]:
                t.tree.column(col, anchor="center")

    # ------------------------------------------------------------------ ciclo
    def ao_mostrar(self) -> None:
        self.recarregar()

    def ao_esconder(self) -> None:
        self._fechar_detalhe()

    def atualizar(self) -> None:
        if self._resultado_exportacao is not None:
            caminho, erro = self._resultado_exportacao
            self._resultado_exportacao = None
            self._exportando = False
            self.btn_csv.configure(state="normal")
            self.btn_html.configure(state="normal")
            if erro:
                self._mostrar_aviso(f"Falha ao exportar: {erro}", erro=True)
                self.app.status.definir("Falha na exportação", None)
            else:
                self._ultimo_exportado = caminho
                self._mostrar_aviso(f"Relatório salvo em {caminho}", abrir=True)
                self.app.status.definir(f"Relatório exportado: {caminho.name}", None)

    # ------------------------------------------------------------------ dados
    def recarregar(self) -> None:
        """Relê o banco e redesenha cartões, tabela e resumos conforme os filtros atuais."""
        self._busca_agendada = None
        try:
            est = self.app.banco.estatisticas()
            chave = self._rotulo_para_chave.get(self.var_resultado.get())
            limite = int(self.var_limite.get())
            acessos = self.app.banco.listar_acessos(limite=limite, resultado=chave)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._mostrar_aviso(f"Não foi possível ler o banco: {e}", erro=True)
            return
        self._preencher_cartoes(est)
        self._preencher_tabela(acessos)
        self._preencher_resumos(est)
        self.app.status.definir(None, f"banco: {self.app.banco.caminho.name} · {est['total']} tentativas")

    def _preencher_cartoes(self, est: dict) -> None:
        por = est["por_resultado"]
        concedidos = por.get("CONCEDIDO", 0)
        self.cartoes["total"].definir(est["total"])
        self.cartoes["CONCEDIDO"].definir(concedidos)
        self.cartoes["negados"].definir(est["total"] - concedidos)
        self.cartoes["usuarios"].definir(est["usuarios"])
        self.cartoes["amostras"].definir(est["amostras"])
        for chave in ROTULO_CARTAO:
            self.cartoes[chave].definir(por.get(chave, 0))

    def _preencher_tabela(self, acessos: list[Acesso]) -> None:
        termo = self.var_busca.get().strip().lower()
        self.tabela.limpar()
        self._acessos = {}
        for a in acessos:
            pessoa = a.nome_detectado or "-"
            if termo and termo not in pessoa.lower():
                continue
            iid = str(a.id)
            self._acessos[iid] = a
            self.tabela.adicionar(iid, [
                a.data_hora.replace("T", " "), pessoa, a.nivel_usuario or "-", a.nivel_exigido, a.area,
                f"{a.similaridade:.2f}" if a.similaridade is not None else "-",
                tema.ROTULO_RESULTADO.get(a.resultado, a.resultado), a.mensagem or "",
            ], tag=_tag_resultado(a.resultado))
        n = len(self._acessos)
        if n == 0:
            self.rotulo_contagem.configure(text="nenhuma tentativa com esses filtros")
        else:
            self.rotulo_contagem.configure(text=f"{n} {'tentativa' if n == 1 else 'tentativas'} listadas")

    def _preencher_resumos(self, est: dict) -> None:
        self.tabela_pessoas.limpar()
        for i, p in enumerate(est["por_usuario"]):
            self.tabela_pessoas.adicionar(f"p{i}", [p["nome"], p["concedidos"] or 0, p["negados"] or 0],
                                          tag="ok" if (p["negados"] or 0) == 0 else None)
        self.tabela_dias.limpar()
        for i, d in enumerate(est["por_dia"]):
            self.tabela_dias.adicionar(f"d{i}", [d["dia"], d["total"], d["concedidos"] or 0])

    def _agendar_busca(self, _evento=None) -> None:
        """Debounce da busca por nome: recarrega 250 ms após a última tecla."""
        if self._busca_agendada is not None:
            try:
                self.after_cancel(self._busca_agendada)
            except Exception:  # noqa: BLE001
                pass
        self._busca_agendada = self.after(250, self.recarregar)

    # ------------------------------------------------------------------ aviso
    def _mostrar_aviso(self, texto: str, erro: bool = False, abrir: bool = False) -> None:
        self.aviso.configure(fg_color=tema.VERMELHO if erro else tema.CARTAO)
        self.rotulo_aviso.configure(text=texto, text_color=tema.TEXTO)
        if abrir:
            self.btn_abrir.grid()
        else:
            self.btn_abrir.grid_remove()
        self.aviso.grid()

    def _esconder_aviso(self) -> None:
        self.aviso.grid_remove()

    # ------------------------------------------------------------------ exportação
    def exportar(self, formato: str) -> None:
        """Gera o relatório CSV ou HTML em uma thread; o resultado é lido em `atualizar()`."""
        if self._exportando:
            return
        formato = formato.lower()
        if formato not in ("csv", "html"):
            self._mostrar_aviso(f"Formato desconhecido: {formato}", erro=True)
            return
        self._exportando = True
        self.btn_csv.configure(state="disabled")
        self.btn_html.configure(state="disabled")
        self._mostrar_aviso(f"Exportando {formato.upper()}...")
        caminho_db = self.app.banco.caminho
        threading.Thread(target=self._exportar_em_thread, args=(formato, caminho_db), daemon=True).start()

    def _exportar_em_thread(self, formato: str, caminho_db: Path) -> None:
        # A conexão SQLite do App pertence à thread do Tk; aqui abrimos outra, só para leitura.
        banco = None
        try:
            banco = Banco(caminho_db)
            fn = relatorios.exportar_csv if formato == "csv" else relatorios.exportar_html
            caminho = fn(banco)
            self._resultado_exportacao = (Path(caminho), None)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._resultado_exportacao = (None, str(e))
        finally:
            if banco is not None:
                banco.fechar()

    def abrir_exportado(self) -> None:
        """Abre o último relatório gerado: HTML no navegador, CSV no aplicativo padrão."""
        caminho = self._ultimo_exportado
        if caminho is None or not caminho.exists():
            self._mostrar_aviso("O arquivo exportado não foi encontrado.", erro=True)
            return
        try:
            if caminho.suffix.lower() in (".html", ".htm"):
                webbrowser.open(caminho.resolve().as_uri())
            else:
                _abrir_no_sistema(caminho.resolve())
        except Exception as e:  # noqa: BLE001
            self._mostrar_aviso(f"Não foi possível abrir {caminho.name}: {e}", erro=True)

    def abrir_pasta_evidencias(self) -> None:
        pasta = Path(config.EVIDENCIAS_DIR)
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            _abrir_no_sistema(pasta.resolve())
        except Exception as e:  # noqa: BLE001
            self._mostrar_aviso(f"Não foi possível abrir a pasta de evidências: {e}", erro=True)

    # ------------------------------------------------------------------ detalhe
    def _abrir_detalhe(self, iid: str) -> None:
        acesso = self._acessos.get(iid)
        if acesso is None:
            return
        try:
            self.abrir_detalhe(acesso)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._mostrar_aviso(f"Não foi possível abrir o detalhe: {e}", erro=True)

    def abrir_detalhe(self, acesso: Acesso) -> ctk.CTkToplevel:
        """Janela com a foto de evidência (se houver) e os dados da tentativa."""
        self._fechar_detalhe()
        jan = ctk.CTkToplevel(self, fg_color=tema.FUNDO)
        jan.title(f"Tentativa #{acesso.id} - {tema.ROTULO_RESULTADO.get(acesso.resultado, acesso.resultado)}")
        jan.grid_columnconfigure(0, weight=1)
        jan.grid_rowconfigure(0, weight=1)
        self._detalhe = jan

        foto = ctk.CTkLabel(jan, text="", fg_color=tema.FUNDO_2, corner_radius=8)
        foto.grid(row=0, column=0, sticky="nsew", padx=24, pady=(24, 12))
        # Foto limitada a 800x600 e também ao que cabe na tela junto com o painel de dados (~420 px)
        maximo = (800, max(240, min(600, self.winfo_screenheight() - 420)))
        imagem = self._carregar_evidencia(acesso.evidencia, maximo)
        if imagem is not None:
            jan._imagem_evidencia = ctk.CTkImage(imagem, size=imagem.size)  # mantém referência
            foto.configure(image=jan._imagem_evidencia)
        else:
            foto.configure(text="Sem foto de evidência" if not acesso.evidencia
                           else f"Evidência não encontrada:\n{acesso.evidencia}",
                           font=tema.SUBTITULO, text_color=tema.TEXTO_2, height=120)

        dados = ctk.CTkFrame(jan, fg_color=tema.CARTAO, corner_radius=10)
        dados.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 24))
        dados.grid_columnconfigure(1, weight=1)
        cor = tema.COR_RESULTADO.get(acesso.resultado, tema.TEXTO)
        linhas = [
            ("Resultado", tema.ROTULO_RESULTADO.get(acesso.resultado, acesso.resultado), cor),
            ("Data/hora", acesso.data_hora.replace("T", " "), tema.TEXTO),
            ("Pessoa", acesso.nome_detectado or "-", tema.TEXTO),
            ("Nível", f"{acesso.nivel_usuario} - {config.NIVEIS.get(acesso.nivel_usuario, '')}"
             if acesso.nivel_usuario else "-", tema.COR_NIVEL.get(acesso.nivel_usuario, tema.TEXTO)),
            ("Nível exigido", f"{acesso.nivel_exigido} - {acesso.area}", tema.COR_NIVEL.get(acesso.nivel_exigido,
                                                                                            tema.TEXTO)),
            ("Similaridade", f"{acesso.similaridade:.2f}" if acesso.similaridade is not None else "-", tema.TEXTO),
            ("Mensagem", acesso.mensagem or "-", tema.TEXTO),
            ("Evidência", acesso.evidencia or "-", tema.TEXTO_2),
        ]
        for i, (rotulo, valor, cor_valor) in enumerate(linhas):
            ctk.CTkLabel(dados, text=rotulo, font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w").grid(
                row=i, column=0, sticky="w", padx=(16, 12), pady=(8 if i == 0 else 2, 8 if i == len(linhas) - 1 else 2))
            ctk.CTkLabel(dados, text=str(valor), font=tema.CORPO, text_color=cor_valor, anchor="w", justify="left",
                         wraplength=720).grid(row=i, column=1, sticky="ew", padx=(0, 16),
                                              pady=(8 if i == 0 else 2, 8 if i == len(linhas) - 1 else 2))
        botao_secundario(jan, "Fechar", self._fechar_detalhe, width=100).grid(row=2, column=0, sticky="e",
                                                                              padx=24, pady=(0, 24))
        jan.protocol("WM_DELETE_WINDOW", self._fechar_detalhe)
        jan.bind("<Escape>", lambda _e: self._fechar_detalhe())
        jan.transient(self.winfo_toplevel())
        jan.update_idletasks()
        raiz = self.winfo_toplevel()
        x = raiz.winfo_rootx() + max(0, (raiz.winfo_width() - jan.winfo_reqwidth()) // 2)
        y = raiz.winfo_rooty() + max(0, (raiz.winfo_height() - jan.winfo_reqheight()) // 2)
        jan.geometry(f"+{max(0, x)}+{max(0, y)}")
        jan.after(50, jan.lift)
        return jan

    def _fechar_detalhe(self) -> None:
        if self._detalhe is not None:
            try:
                self._detalhe.destroy()
            except Exception:  # noqa: BLE001
                pass
            self._detalhe = None

    @staticmethod
    def _carregar_evidencia(caminho: str | None, maximo: tuple[int, int] = (800, 600)) -> Image.Image | None:
        if not caminho:
            return None
        p = Path(caminho)
        if not p.is_absolute():
            p = config.BASE_DIR / p
        if not p.exists():
            return None
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                im.thumbnail(maximo)
                return im.copy()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return None

```

## `cofre/interface/tela_cadastro.py` (548 linhas)

```python
"""Tela de cadastro biométrico: formulário do usuário, captura pela câmera (SessaoCadastro)
ou importação de fotos (cadastrar_de_imagens).

Divisão de threads:
- a thread da câmera só roda `pipeline.processar(frame)` e devolve `(frame, resultado)`;
- `SessaoCadastro.passo()` e `desenhar()` rodam em `atualizar()` (thread do Tk), porque a
  sessão grava amostras no banco e a conexão SQLite só aceita a thread que a criou;
- o cadastro por fotos roda em uma `threading.Thread` com uma conexão própria ao banco e
  entrega o resultado por uma flag lida em `atualizar()`.
"""

from __future__ import annotations

import threading
import traceback
from pathlib import Path
from tkinter import StringVar, filedialog

import customtkinter as ctk
import cv2

from .. import config, hud
from ..banco import Banco
from ..cadastro import DadosCadastro, SessaoCadastro, cadastrar_de_imagens
from . import tema
from .base import Tela
from .widgets import Faixa, VideoWidget, botao, botao_secundario, titulo

TAM_MINIATURA = 72
MAX_AVISOS_EXIBIDOS = 6

# Cores BGR do HUD (cofre/hud.py) -> hex do tema
_COR_HUD = {
    hud.VERDE: tema.VERDE,
    hud.VERMELHO: tema.VERMELHO,
    hud.AMARELO: tema.AMARELO,
    hud.LARANJA: tema.LARANJA,
    hud.AZUL: tema.AZUL,
    hud.BRANCO: tema.TEXTO,
    hud.CINZA: tema.TEXTO_2,
}


def cor_hud_para_hex(bgr) -> str:
    """Converte uma cor BGR do HUD em hex; cores conhecidas usam a paleta do tema."""
    try:
        b, g, r = (int(v) for v in bgr[:3])
    except Exception:  # noqa: BLE001
        return tema.TEXTO
    return _COR_HUD.get((b, g, r), f"#{r:02x}{g:02x}{b:02x}")


def miniatura_quadrada(recorte, lado: int = TAM_MINIATURA) -> ctk.CTkImage:
    """Recorta o centro do rosto em um quadrado e gera um CTkImage lado x lado."""
    h, w = recorte.shape[:2]
    m = min(h, w)
    y0, x0 = (h - m) // 2, (w - m) // 2
    quadrado = recorte[y0:y0 + m, x0:x0 + m]
    red = cv2.resize(quadrado, (lado, lado), interpolation=cv2.INTER_AREA)
    return ctk.CTkImage(tema.bgr_para_pil(red), size=(lado, lado))


def _resumir_aviso(aviso: str) -> str:
    """'/pasta/longa/foto.jpg: nenhum rosto' -> 'foto.jpg: nenhum rosto'."""
    caminho, sep, resto = aviso.partition(": ")
    if sep and Path(caminho).suffix:
        return f"{Path(caminho).name}: {resto}"
    return aviso


class TelaCadastro(Tela):
    TITULO = "Cadastro biométrico"

    # ------------------------------------------------------------------ construção
    def construir(self) -> None:
        self.sessao: SessaoCadastro | None = None
        self._dados_pendentes: DadosCadastro | None = None   # Iniciar clicado, esperando o pipeline
        self._quer_camera = False       # a tela quer a câmera ligada
        self._camera_pedida = False     # já chamou camera.iniciar() para esta sessão
        self._id_ultimo_res: int | None = None
        self._miniaturas_widgets: list[ctk.CTkLabel] = []
        self._miniaturas_imgs: list[ctk.CTkImage] = []
        self._thread_fotos: threading.Thread | None = None
        self._resultado_fotos: tuple | None = None            # escrito pela thread, lido em atualizar()
        self._opcoes_nivel = [f"{n} - {desc}" for n, desc in sorted(config.NIVEIS.items())]

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=380)
        self.grid_rowconfigure(1, weight=1)

        titulo(self, self.TITULO, "Cadastre um usuário autorizado: preencha os dados e capture 12 amostras "
               "do rosto pela câmera, ou importe fotos.").grid(row=0, column=0, columnspan=2, sticky="ew",
                                                              padx=24, pady=(24, 12))
        self._construir_esquerda()
        self._construir_formulario()

    def _construir_esquerda(self) -> None:
        esq = ctk.CTkFrame(self, fg_color="transparent")
        esq.grid(row=1, column=0, sticky="nsew", padx=(24, 12), pady=(0, 24))
        esq.grid_columnconfigure(0, weight=1)
        esq.grid_rowconfigure(0, weight=1)

        self.video = VideoWidget(esq)
        self.video.grid(row=0, column=0, sticky="nsew")

        self.botao_tentar = botao_secundario(esq, "Tentar novamente", self.tentar_novamente, width=180)
        self.botao_tentar.grid(row=1, column=0, pady=(12, 0))
        self.botao_tentar.grid_remove()

        linha = ctk.CTkFrame(esq, fg_color="transparent")
        linha.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        linha.grid_columnconfigure(1, weight=1)
        self.rotulo_amostras = ctk.CTkLabel(linha, text="", font=tema.CORPO, text_color=tema.TEXTO_2, width=130,
                                            anchor="w")
        self.rotulo_amostras.grid(row=0, column=0, sticky="w")
        self.barra = ctk.CTkProgressBar(linha, progress_color=tema.ACENTO, fg_color=tema.CARTAO, height=12)
        self.barra.grid(row=0, column=1, sticky="ew", padx=(12, 0))
        self.barra.set(0)

        self.faixa_instrucao = Faixa(esq)
        self.faixa_instrucao.texto.configure(wraplength=560)
        self.faixa_instrucao.grid(row=3, column=0, sticky="ew", pady=(12, 0))

        self.faixa_miniaturas = ctk.CTkScrollableFrame(esq, orientation="horizontal", fg_color=tema.CARTAO,
                                                       corner_radius=10, height=TAM_MINIATURA + 16)
        self.faixa_miniaturas.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.rotulo_miniaturas = ctk.CTkLabel(self.faixa_miniaturas, text="As amostras capturadas aparecem aqui",
                                              font=tema.PEQUENO, text_color=tema.TEXTO_2)
        self.rotulo_miniaturas.pack(side="left", padx=12, pady=4)
        self._definir_amostras(0, config.AMOSTRAS_POR_CADASTRO)

    def _construir_formulario(self) -> None:
        form = ctk.CTkFrame(self, fg_color=tema.CARTAO, corner_radius=10)
        form.grid(row=1, column=1, sticky="nsew", padx=(0, 24), pady=(0, 24))
        self.form = form

        ctk.CTkLabel(form, text="Dados do usuário", font=tema.SUBTITULO, text_color=tema.TEXTO, anchor="w").pack(
            fill="x", padx=16, pady=(16, 8))

        self.entrada_nome = self._campo(form, "Nome completo *", "Ex.: Maria da Silva")
        self.entrada_matricula = self._campo(form, "Matrícula *", "Ex.: 2024001")
        self.entrada_cargo = self._campo(form, "Cargo / divisão", "Ex.: Diretor de Fiscalização")

        ctk.CTkLabel(form, text="Nível de acesso", font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w").pack(
            fill="x", padx=16, pady=(8, 2))
        self.var_nivel = StringVar(value=self._opcoes_nivel[0])
        self.menu_nivel = ctk.CTkOptionMenu(form, values=self._opcoes_nivel, variable=self.var_nivel, font=tema.CORPO,
                                            fg_color=tema.FUNDO_2, button_color=tema.BORDA,
                                            button_hover_color=tema.ACENTO_HOVER, dropdown_fg_color=tema.FUNDO_2,
                                            text_color=tema.TEXTO, command=self._ao_escolher_nivel)
        self.menu_nivel.pack(fill="x", padx=16)
        self.rotulo_area = ctk.CTkLabel(form, text="", font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w",
                                        wraplength=330, justify="left")
        self.rotulo_area.pack(fill="x", padx=16, pady=(4, 0))
        self._ao_escolher_nivel(self.var_nivel.get())

        self.rotulo_erro = ctk.CTkLabel(form, text="", font=tema.CORPO, text_color=tema.VERMELHO, anchor="w",
                                        wraplength=330, justify="left")
        self.rotulo_erro.pack(fill="x", padx=16, pady=(12, 0))

        self.botao_iniciar = botao(form, "Iniciar captura pela câmera", self.iniciar_captura, height=40)
        self.botao_iniciar.pack(fill="x", padx=16, pady=(12, 0))
        self.botao_fotos = botao_secundario(form, "Cadastrar por fotos...", self._escolher_fotos, height=40)
        self.botao_fotos.pack(fill="x", padx=16, pady=(8, 0))

        # Botões da captura (aparecem só durante a sessão)
        self.quadro_captura = ctk.CTkFrame(form, fg_color="transparent")
        self.quadro_captura.grid_columnconfigure((0, 1), weight=1)
        self.botao_cancelar = botao(self.quadro_captura, "Cancelar", self.cancelar, cor=tema.VERMELHO, height=40)
        self.botao_cancelar.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.botao_concluir = botao(self.quadro_captura, "Concluir", self.concluir, cor=tema.VERDE, height=40)
        self.botao_concluir.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # Mensagem de resultado (sucesso/aviso) no rodapé do formulário
        self.rotulo_msg = ctk.CTkLabel(form, text="", font=tema.CORPO, text_color=tema.TEXTO, anchor="w",
                                       justify="left", wraplength=320, corner_radius=8, fg_color="transparent")
        self.rotulo_msg.pack(side="bottom", fill="x", padx=16, pady=(12, 16))

    def _campo(self, master, rotulo: str, dica: str) -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=rotulo, font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w").pack(
            fill="x", padx=16, pady=(8, 2))
        e = ctk.CTkEntry(master, placeholder_text=dica, font=tema.CORPO, fg_color=tema.FUNDO_2,
                         border_color=tema.BORDA, text_color=tema.TEXTO, height=34)
        e.pack(fill="x", padx=16)
        return e

    # ------------------------------------------------------------------ ciclo de vida
    def ao_mostrar(self) -> None:
        if self.capturando:
            # voltou para a tela no meio de uma captura: religa a câmera
            self._quer_camera = True

    def ao_esconder(self) -> None:
        self._quer_camera = False
        self._camera_pedida = False
        self.app.camera.parar()

    def atualizar(self) -> None:
        try:
            self._tratar_resultado_fotos()
            self._iniciar_sessao_se_pronto()
            self._ligar_camera_se_preciso()
            self._atualizar_captura()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            self._mostrar_erro("Erro inesperado na tela de cadastro (veja o terminal).")

    def _video_mensagem(self, texto: str) -> None:
        """Troca o vídeo por uma mensagem. Antes solta a imagem no Label do Tk: `VideoWidget.mensagem`
        descarta o CTkImage, e o Tk ainda apontaria para a foto destruída ("image doesn't exist")."""
        try:
            self.video._label.configure(image="")  # noqa: SLF001 (interno do CTkLabel)
        except Exception:  # noqa: BLE001
            pass
        self.video.mensagem(texto)

    # ------------------------------------------------------------------ propriedades
    @property
    def capturando(self) -> bool:
        """True entre o clique em Iniciar e o Concluir/Cancelar."""
        return self._dados_pendentes is not None or (self.sessao is not None and not self.sessao.encerrada)

    @property
    def importando_fotos(self) -> bool:
        return self._thread_fotos is not None and self._thread_fotos.is_alive()

    # ------------------------------------------------------------------ formulário
    def preencher(self, nome: str = "", matricula: str = "", cargo: str = "", nivel: int = 1) -> None:
        """Preenche o formulário (usado por testes e por outras telas)."""
        for entrada, valor in ((self.entrada_nome, nome), (self.entrada_matricula, matricula),
                               (self.entrada_cargo, cargo)):
            entrada.delete(0, "end")
            if valor:
                entrada.insert(0, valor)
        for opcao in self._opcoes_nivel:
            if opcao.startswith(f"{nivel} -"):
                self.var_nivel.set(opcao)
        self._ao_escolher_nivel(self.var_nivel.get())

    def limpar_formulario(self) -> None:
        self.preencher()
        self.rotulo_erro.configure(text="")

    def nivel_escolhido(self) -> int:
        try:
            return int(self.var_nivel.get().split(" -")[0])
        except (ValueError, AttributeError):
            return 1

    def _ao_escolher_nivel(self, valor: str) -> None:
        n = self.nivel_escolhido()
        self.rotulo_area.configure(text=f"Libera: {config.AREAS.get(n, '?')}", text_color=tema.COR_NIVEL.get(n, tema.TEXTO_2))

    def ler_formulario(self) -> DadosCadastro | None:
        """Valida e devolve os dados; em erro escreve a mensagem vermelha e devolve None."""
        nome = self.entrada_nome.get().strip()
        matricula = self.entrada_matricula.get().strip()
        cargo = self.entrada_cargo.get().strip()
        nivel = self.nivel_escolhido()
        if not nome:
            return self._mostrar_erro("Informe o nome do usuário.")
        if not matricula:
            return self._mostrar_erro("Informe a matrícula.")
        if nivel not in config.NIVEIS:
            return self._mostrar_erro("Escolha um nível de acesso válido.")
        try:
            existente = self.app.banco.obter_por_matricula(matricula)
        except Exception as e:  # noqa: BLE001
            return self._mostrar_erro(f"Não foi possível consultar o banco: {e}")
        if existente is not None:
            return self._mostrar_erro(f"Matrícula {matricula} já cadastrada para {existente.nome}.")
        self.rotulo_erro.configure(text="")
        return DadosCadastro(nome, matricula, cargo, nivel)

    def _definir_formulario(self, habilitado: bool) -> None:
        estado = "normal" if habilitado else "disabled"
        for w in (self.entrada_nome, self.entrada_matricula, self.entrada_cargo, self.menu_nivel,
                  self.botao_iniciar, self.botao_fotos):
            w.configure(state=estado)

    def _mostrar_erro(self, texto: str) -> None:
        self.rotulo_erro.configure(text=texto)
        return None

    def _mostrar_msg(self, texto: str, cor: str = tema.TEXTO, fundo: str = "transparent") -> None:
        self.rotulo_msg.configure(text=texto, text_color=cor, fg_color=fundo)

    # ------------------------------------------------------------------ captura pela câmera
    def iniciar_captura(self) -> bool:
        """Valida o formulário e agenda o início da sessão (a câmera liga quando o pipeline estiver pronto)."""
        if self.capturando or self.importando_fotos:
            return False
        dados = self.ler_formulario()
        if dados is None:
            return False
        self._dados_pendentes = dados
        self._definir_formulario(False)
        self._mostrar_msg("")
        self._limpar_miniaturas()
        self._definir_amostras(0, config.AMOSTRAS_POR_CADASTRO)
        self.faixa_instrucao.definir("Preparando a captura...", tema.CARTAO, tema.TEXTO_2)
        self._video_mensagem("Carregando modelos..." if not self.app.pipeline_pronto() else "Ligando a câmera...")
        self.botao_concluir.configure(state="disabled")
        self.quadro_captura.pack(fill="x", padx=16, pady=(12, 0))
        self.app.status.definir("Cadastro: preparando captura", None)
        return True

    def _iniciar_sessao_se_pronto(self) -> None:
        if self._dados_pendentes is None or not self.app.pipeline_pronto():
            return
        dados, self._dados_pendentes = self._dados_pendentes, None
        try:
            self.sessao = SessaoCadastro(self.app.banco, self.app.pipeline, dados)
        except Exception as e:  # noqa: BLE001
            self.sessao = None
            self._encerrar_captura()
            self._mostrar_erro(f"Não foi possível iniciar o cadastro: {e}")
            return
        self._id_ultimo_res = None
        self._definir_amostras(0, self.sessao.amostras)
        self.app.camera.definir_processador(self._criar_processador(self.app.pipeline))
        self._quer_camera = True

    @staticmethod
    def _criar_processador(pipeline):
        """Roda na thread da câmera: só o pipeline (sem banco, sem widgets)."""
        def processador(frame):
            res = pipeline.processar(frame, extrair_embedding=False)
            return frame, res
        return processador

    def _ligar_camera_se_preciso(self) -> None:
        if not self._quer_camera or self._camera_pedida or self.sessao is None:
            return
        cam = self.app.camera
        cam.definir_processador(self._criar_processador(self.app.pipeline))
        cam.iniciar()
        self._camera_pedida = True
        self._video_mensagem("Ligando a câmera...")

    def tentar_novamente(self) -> None:
        """Religa a câmera depois de uma falha (permissão negada, dispositivo ocupado...)."""
        self.botao_tentar.grid_remove()
        self.app.camera.parar()
        self.app.camera.erro = None
        self._camera_pedida = False
        self._quer_camera = self.sessao is not None and not self.sessao.encerrada
        self.faixa_instrucao.definir("Religando a câmera...", tema.CARTAO, tema.TEXTO_2)
        self._video_mensagem("Ligando a câmera...")

    def _atualizar_captura(self) -> None:
        sessao = self.sessao
        if sessao is None or sessao.encerrada:
            return
        cam = self.app.camera
        if cam.erro:
            self._video_mensagem(f"Câmera indisponível\n{cam.erro}\n\nNo macOS, autorize a câmera em Ajustes do "
                                f"Sistema > Privacidade e Segurança > Câmera.")
            self.botao_tentar.grid()
            self.faixa_instrucao.definir("Câmera indisponível", tema.CARTAO, tema.VERMELHO)
            return
        saida = cam.ultimo()
        if not isinstance(saida, tuple) or len(saida) != 2:
            return
        frame, res = saida
        if id(res) == self._id_ultimo_res:
            return
        self._id_ultimo_res = id(res)
        sessao.passo(frame, res)
        tela = sessao.desenhar(frame, res)
        self.video.mostrar(tela)
        cor = cor_hud_para_hex(sessao.cor)
        self.faixa_instrucao.definir(sessao.status, tema.CARTAO, cor)
        self._definir_amostras(sessao.capturadas, sessao.amostras)
        self._sincronizar_miniaturas(sessao)
        if sessao.concluida:
            self.botao_concluir.configure(state="normal")
            self.app.status.definir("Cadastro: amostras completas, clique em Concluir",
                                    f"câmera {cam.fps:.0f} fps")
        else:
            self.app.status.definir(f"Cadastro: {sessao.dados.nome} ({sessao.capturadas}/{sessao.amostras})",
                                    f"câmera {cam.fps:.0f} fps")

    def cancelar(self) -> None:
        """Desfaz o cadastro em andamento (usuário e amostras) e desliga a câmera."""
        sessao, self.sessao = self.sessao, None
        self._dados_pendentes = None
        if sessao is not None and not sessao.encerrada:
            try:
                sessao.cancelar()
            except Exception as e:  # noqa: BLE001
                self._mostrar_erro(f"Falha ao desfazer o cadastro: {e}")
        self._encerrar_captura()
        self._limpar_miniaturas()
        self._definir_amostras(0, config.AMOSTRAS_POR_CADASTRO)
        self.faixa_instrucao.definir("Cadastro cancelado", tema.CARTAO, tema.TEXTO_2)
        self.app.status.definir("Cadastro cancelado", "")

    def concluir(self):
        """Fecha a sessão, grava o usuário e avisa o terminal para recarregar a galeria."""
        sessao = self.sessao
        if sessao is None:
            return None
        self.sessao = None
        try:
            usuario = sessao.concluir()
        except Exception as e:  # noqa: BLE001
            usuario = None
            self._mostrar_erro(f"Falha ao concluir o cadastro: {e}")
        self._encerrar_captura()
        if usuario is None:
            self.faixa_instrucao.definir("Nenhuma amostra capturada: cadastro desfeito", tema.CARTAO, tema.LARANJA)
            self.app.status.definir("Cadastro desfeito (sem amostras)", "")
            return None
        self._anunciar_sucesso(usuario, sessao.capturadas)
        self.faixa_instrucao.definir(f"{usuario.nome} cadastrado com {sessao.capturadas} amostras",
                                     tema.CARTAO, tema.VERDE)
        return usuario

    def _encerrar_captura(self) -> None:
        self._quer_camera = False
        self._camera_pedida = False
        self.app.camera.parar()
        self.app.camera.definir_processador(None)
        self.botao_tentar.grid_remove()
        self.quadro_captura.pack_forget()
        self._definir_formulario(True)
        self._video_mensagem("Câmera desligada")
        self._id_ultimo_res = None

    def _anunciar_sucesso(self, usuario, n_amostras: int, avisos: list[str] | None = None) -> None:
        texto = (f"Cadastro concluído\n{usuario.nome}  (matrícula {usuario.matricula})\n"
                 f"Nível {usuario.nivel} - {usuario.nivel_descricao}\n{n_amostras} amostra(s) gravada(s)")
        if avisos:
            mostrados = avisos[:MAX_AVISOS_EXIBIDOS]
            if len(avisos) > MAX_AVISOS_EXIBIDOS:
                mostrados.append(f"... e mais {len(avisos) - MAX_AVISOS_EXIBIDOS} aviso(s)")
            texto += "\n\nAvisos:\n" + "\n".join(f"- {_resumir_aviso(a)}" for a in mostrados)
        self._mostrar_msg(texto, tema.FUNDO, tema.VERDE)
        self.limpar_formulario()
        self.app.status.definir(f"Cadastrado: {usuario.nome} (nível {usuario.nivel})", "")
        self._avisar_terminal()

    def _avisar_terminal(self) -> None:
        tela = self.app.tela("tela_terminal")
        recarregar = getattr(tela, "recarregar_galeria", None)
        if callable(recarregar):
            try:
                recarregar()
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    # ------------------------------------------------------------------ amostras / miniaturas
    def _definir_amostras(self, n: int, total: int) -> None:
        self.rotulo_amostras.configure(text=f"Amostras {n}/{total}")
        self.barra.set(0 if total <= 0 else min(1.0, n / total))

    def _limpar_miniaturas(self) -> None:
        for w in self._miniaturas_widgets:
            w.destroy()
        self._miniaturas_widgets.clear()
        self._miniaturas_imgs.clear()
        self.rotulo_miniaturas.pack(side="left", padx=12, pady=4)

    def _sincronizar_miniaturas(self, sessao: SessaoCadastro) -> None:
        novas = sessao.miniaturas[len(self._miniaturas_widgets):]
        if not novas:
            return
        self.rotulo_miniaturas.pack_forget()
        for recorte in novas:
            try:
                img = miniatura_quadrada(recorte)
            except Exception:  # noqa: BLE001
                continue
            self._miniaturas_imgs.append(img)
            rot = ctk.CTkLabel(self.faixa_miniaturas, image=img, text="", width=TAM_MINIATURA, height=TAM_MINIATURA)
            rot.pack(side="left", padx=4, pady=4)
            self._miniaturas_widgets.append(rot)

    # ------------------------------------------------------------------ cadastro por fotos
    def _escolher_fotos(self) -> None:
        if self.capturando or self.importando_fotos:
            return
        if self.ler_formulario() is None:
            return
        caminhos = filedialog.askopenfilenames(
            parent=self, title="Escolha as fotos do rosto",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.bmp *.webp"), ("Todos os arquivos", "*.*")])
        if caminhos:
            self.cadastrar_por_fotos(list(caminhos))

    def cadastrar_por_fotos(self, caminhos: list[str | Path]) -> bool:
        """Cadastra o usuário do formulário a partir dos arquivos dados, em uma thread."""
        if self.capturando or self.importando_fotos:
            return False
        if not caminhos:
            self._mostrar_erro("Nenhuma foto escolhida.")
            return False
        dados = self.ler_formulario()
        if dados is None:
            return False
        if not self.app.pipeline_pronto():
            self._mostrar_erro("Os modelos ainda estão carregando. Tente novamente em instantes.")
            return False
        self._definir_formulario(False)
        self._mostrar_msg(f"Processando {len(caminhos)} foto(s)...", tema.TEXTO_2)
        self.app.status.definir(f"Cadastro por fotos: processando {len(caminhos)} arquivo(s)", None)
        self._resultado_fotos = None
        caminho_db = self.app.banco.caminho
        pipeline = self.app.pipeline
        self._thread_fotos = threading.Thread(
            target=self._trabalho_fotos, args=(caminho_db, pipeline, dados, list(caminhos)),
            name="cadastro-fotos", daemon=True)
        self._thread_fotos.start()
        return True

    def _trabalho_fotos(self, caminho_db, pipeline, dados, caminhos) -> None:
        """Thread de trabalho: conexão própria ao banco (SQLite exige a mesma thread)."""
        banco = None
        try:
            banco = Banco(caminho_db) if str(caminho_db) != ":memory:" else self.app.banco
            usuario, n, avisos = cadastrar_de_imagens(banco, pipeline, dados, caminhos)
            self._resultado_fotos = ("ok", usuario, n, avisos)
        except Exception as e:  # noqa: BLE001
            self._resultado_fotos = ("erro", str(e))
        finally:
            if banco is not None and banco is not self.app.banco:
                try:
                    banco.fechar()
                except Exception:  # noqa: BLE001
                    pass

    def _tratar_resultado_fotos(self) -> None:
        res = self._resultado_fotos
        if res is None:
            return
        self._resultado_fotos = None
        self._thread_fotos = None
        self._definir_formulario(True)
        if res[0] == "ok":
            _, usuario, n, avisos = res
            # reconsulta pela conexão principal (os dados vieram de outra conexão)
            usuario = self.app.banco.obter_usuario(usuario.id) or usuario
            self._anunciar_sucesso(usuario, n, avisos)
        else:
            self._mostrar_msg("")
            self._mostrar_erro(f"Cadastro por fotos falhou: {res[1]}")
            self.app.status.definir("Cadastro por fotos falhou", "")

```

## `cofre/interface/tela_config.py` (325 linhas)

```python
"""
Tela "Configurações": formulário que lê e grava, em tempo de execução, os valores
do módulo `cofre.config` (via `setattr`), com persistência opcional em JSON
(`config.DATA_DIR / "config_usuario.json"`) e uma seção informativa (caminhos,
versões, modelos, níveis e áreas).

Observação importante sobre o efeito das alterações: os objetos do sistema leem
`config` de duas formas. Alguns leem no momento do uso (ex.: `Identificacao.reconhecido`
lê `config.LIMIAR_COSSENO` a cada frame) e por isso mudam na hora. Outros leem ao serem
construídos (`Confirmador`, `DesafioMovimento`, `ControleTentativas`, `FonteCamera`,
`SessaoCadastro`) e só enxergam o valor novo quando a tela de câmera cria um objeto
novo, ou seja, na próxima sessão de câmera.
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk
import cv2

from .. import __version__, config
from ..fase1_aquisicao import FonteCamera
from . import tema
from .base import Tela
from .widgets import Faixa, Tabela, botao, botao_secundario, titulo

from ..parametros import ARQUIVO_CONFIG_NOME, CAMPOS, CAMPOS_POR_CHAVE, MENSAGEM_APLICADO, Campo  # noqa: F401



class _LinhaCampo(ctk.CTkFrame):
    """Uma linha do formulário: rótulo + explicação à esquerda, controle + valor à direita."""

    def __init__(self, master, campo: Campo, ao_mudar: Callable[[str, Any], None]):
        super().__init__(master, fg_color=tema.CARTAO, corner_radius=10)
        self.campo = campo
        self._ao_mudar = ao_mudar
        self._silencio = False
        self.grid_columnconfigure(0, weight=1)
        textos = ctk.CTkFrame(self, fg_color="transparent")
        textos.grid(row=0, column=0, sticky="nsew", padx=(16, 12), pady=12)
        ctk.CTkLabel(textos, text=campo.rotulo, font=tema.SUBTITULO, text_color=tema.TEXTO, anchor="w").pack(fill="x")
        ctk.CTkLabel(textos, text=campo.explicacao, font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w",
                     justify="left", wraplength=520).pack(fill="x", pady=(2, 0))
        controle = ctk.CTkFrame(self, fg_color="transparent", width=300)
        controle.grid(row=0, column=1, sticky="e", padx=(0, 16), pady=12)
        self.valor_lbl = ctk.CTkLabel(controle, text="", font=tema.MONO, text_color=tema.ACENTO, width=70,
                                      anchor="e")
        if campo.tipo == "bool":
            self.switch = ctk.CTkSwitch(controle, text="", width=60, command=self._mudou,
                                        progress_color=tema.ACENTO, button_color=tema.TEXTO)
            self.switch.pack(side="right")
            self.valor_lbl.pack(side="right", padx=(0, 8))
            self.slider = None
        else:
            self.switch = None
            passos = int(round((campo.maximo - campo.minimo) / campo.passo))
            self.slider = ctk.CTkSlider(controle, from_=campo.minimo, to=campo.maximo, number_of_steps=max(1, passos),
                                        width=220, command=self._mudou, progress_color=tema.ACENTO,
                                        button_color=tema.ACENTO, button_hover_color=tema.ACENTO_HOVER)
            self.valor_lbl.pack(side="right", padx=(8, 0))
            self.slider.pack(side="right")
            ctk.CTkLabel(controle, text=f"{campo.formatar(campo.minimo)} a {campo.formatar(campo.maximo)}",
                         font=tema.PEQUENO, text_color=tema.TEXTO_2).pack(side="right", padx=(0, 8))

    def definir(self, valor: Any) -> None:
        """Atualiza o controle sem disparar o callback."""
        self._silencio = True
        try:
            if self.switch is not None:
                (self.switch.select if valor else self.switch.deselect)()
            else:
                self.slider.set(float(valor))
            self.valor_lbl.configure(text=self.campo.formatar(valor))
        finally:
            self._silencio = False

    def _mudou(self, *_: Any) -> None:
        if self._silencio:
            return
        if self.switch is not None:
            valor = bool(self.switch.get())
        else:
            valor = self.campo.normalizar(self.slider.get())
        self.valor_lbl.configure(text=self.campo.formatar(valor))
        self._ao_mudar(self.campo.chave, valor)


class TelaConfig(Tela):
    """Formulário de configurações em tempo de execução + informações do sistema."""

    TITULO = "Configurações"

    # ------------------------------------------------------------------ construção
    def construir(self) -> None:
        # Valores originais do módulo, capturados ANTES de qualquer carregamento de arquivo.
        self.padroes: dict[str, Any] = {c.chave: getattr(config, c.chave) for c in CAMPOS}
        self._valores: dict[str, Any] = dict(self.padroes)
        self._linhas: dict[str, _LinhaCampo] = {}
        self._pendente_msg: tuple[str, str] | None = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        titulo(self, self.TITULO, "Ajuste os parâmetros do sistema sem reiniciar. Aplicar grava no módulo "
               "cofre.config; Salvar guarda em arquivo para as próximas execuções.").grid(
            row=0, column=0, sticky="ew", padx=24, pady=(24, 12))

        self.corpo = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.corpo.grid(row=1, column=0, sticky="nsew", padx=(24, 12))
        self.corpo.grid_columnconfigure(0, weight=1)
        self._construir_formulario(self.corpo)
        self._construir_informacoes(self.corpo)

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.grid(row=2, column=0, sticky="ew", padx=24, pady=(12, 24))
        rodape.grid_columnconfigure(0, weight=1)
        self.mensagem = Faixa(rodape)
        self.mensagem.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        botoes = ctk.CTkFrame(rodape, fg_color="transparent")
        botoes.grid(row=1, column=0, sticky="ew")
        self.btn_aplicar = botao(botoes, "Aplicar", self.aplicar, width=140)
        self.btn_aplicar.pack(side="left")
        self.btn_restaurar = botao_secundario(botoes, "Restaurar padrões", self.restaurar_padroes, width=160)
        self.btn_restaurar.pack(side="left", padx=(12, 0))
        self.btn_carregar = botao_secundario(botoes, "Carregar de arquivo", self.carregar_arquivo, width=170)
        self.btn_carregar.pack(side="right")
        self.btn_salvar = botao_secundario(botoes, "Salvar em arquivo", self.salvar_arquivo, width=160)
        self.btn_salvar.pack(side="right", padx=(0, 12))

        self._ligar_camera_na_config()
        self._carregar_inicial()
        self._atualizar_controles()

    def _construir_formulario(self, pai) -> None:
        secao_atual = None
        linha = 0
        for campo in CAMPOS:
            if campo.secao != secao_atual:
                secao_atual = campo.secao
                ctk.CTkLabel(pai, text=campo.secao, font=tema.SUBTITULO, text_color=tema.ACENTO, anchor="w").grid(
                    row=linha, column=0, sticky="ew", pady=(12 if linha else 0, 6))
                linha += 1
            w = _LinhaCampo(pai, campo, self._campo_mudou)
            w.grid(row=linha, column=0, sticky="ew", pady=(0, 8))
            self._linhas[campo.chave] = w
            linha += 1
        self._proxima_linha = linha

    def _construir_informacoes(self, pai) -> None:
        linha = self._proxima_linha
        ctk.CTkLabel(pai, text="Informações do sistema", font=tema.SUBTITULO, text_color=tema.ACENTO, anchor="w").grid(
            row=linha, column=0, sticky="ew", pady=(24, 6))
        linha += 1
        cartao = ctk.CTkFrame(pai, fg_color=tema.CARTAO, corner_radius=10)
        cartao.grid(row=linha, column=0, sticky="ew", pady=(0, 8))
        cartao.grid_columnconfigure(1, weight=1)
        infos = self.informacoes()
        for i, (nome, valor) in enumerate(infos):
            pady = (12 if i == 0 else 2, 12 if i == len(infos) - 1 else 2)
            ctk.CTkLabel(cartao, text=nome, font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w", width=190).grid(
                row=i, column=0, sticky="nw", padx=(16, 8), pady=pady)
            ctk.CTkLabel(cartao, text=valor, font=tema.MONO, text_color=tema.TEXTO, anchor="w", justify="left",
                         wraplength=760).grid(row=i, column=1, sticky="w", padx=(0, 16), pady=pady)
        linha += 1
        ctk.CTkLabel(pai, text="Níveis de acesso e áreas protegidas", font=tema.SUBTITULO, text_color=tema.ACENTO,
                     anchor="w").grid(row=linha, column=0, sticky="ew", pady=(16, 6))
        linha += 1
        self.tabela_niveis = Tabela(pai, [("nivel", "Nível", 70), ("nome", "Permissão", 260),
                                          ("area", "Área liberada (nível mínimo)", 420)], altura=max(1, len(config.NIVEIS)))
        self.tabela_niveis.grid(row=linha, column=0, sticky="ew", pady=(0, 8))
        for n in sorted(config.NIVEIS):
            self.tabela_niveis.adicionar(str(n), (n, config.NIVEIS[n], config.AREAS.get(n, "-")))

    # ------------------------------------------------------------------ informações
    def informacoes(self) -> list[tuple[str, str]]:
        """Pares (nome, valor) exibidos na seção informativa."""
        def arquivo(p: Path) -> str:
            try:
                return f"{p}  ({p.stat().st_size / 1024:.0f} KB)" if p.exists() else f"{p}  (NÃO ENCONTRADO)"
            except OSError:
                return str(p)
        banco = getattr(self.app, "banco", None)
        caminho_db = getattr(banco, "caminho", config.DB_PATH)
        return [
            ("Banco de dados", str(caminho_db)),
            ("Pasta de dados", str(config.DATA_DIR)),
            ("Fotos / evidências / relatórios", f"{config.FOTOS_DIR}\n{config.EVIDENCIAS_DIR}\n{config.RELATORIOS_DIR}"),
            ("Arquivo de configuração", str(self.caminho_arquivo)),
            ("Modelo de detecção (YuNet)", arquivo(config.MODELO_DETECCAO)),
            ("Modelo de reconhecimento (SFace)", arquivo(config.MODELO_RECONHECIMENTO)),
            ("Dimensões dos modelos", f"YuNet: entrada ajustada ao frame reduzido ({config.LARGURA_PROCESSAMENTO} px de largura), "
                                     f"padrão 320x320\nSFace: rosto alinhado 112x112 -> embedding de 128 dimensões"),
            ("Captura", f"{config.CAMERA_LARGURA}x{config.CAMERA_ALTURA}, processamento em {config.LARGURA_PROCESSAMENTO} px"),
            ("OpenCV", cv2.__version__),
            ("customtkinter / Python", f"{ctk.__version__} / {platform.python_version()} ({sys.platform})"),
            ("Versão do aplicativo", __version__),
        ]

    # ------------------------------------------------------------------ valores
    @property
    def caminho_arquivo(self) -> Path:
        return Path(config.DATA_DIR) / ARQUIVO_CONFIG_NOME

    def valores(self) -> dict[str, Any]:
        """Valores atualmente no formulário (ainda não necessariamente aplicados)."""
        return dict(self._valores)

    def definir(self, chave: str, valor: Any) -> None:
        """Define um campo do formulário (valida e limita ao intervalo). Não aplica no módulo."""
        campo = CAMPOS_POR_CHAVE[chave]
        self._valores[chave] = campo.normalizar(valor)
        if chave in self._linhas:
            self._linhas[chave].definir(self._valores[chave])

    def _campo_mudou(self, chave: str, valor: Any) -> None:
        self._valores[chave] = valor
        self.mensagem.definir("Alterações pendentes: clique em Aplicar", tema.CARTAO, tema.LARANJA)

    def _atualizar_controles(self) -> None:
        for chave, w in self._linhas.items():
            w.definir(self._valores[chave])

    # ------------------------------------------------------------------ ações
    def aplicar(self) -> bool:
        """Valida e grava os valores do formulário no módulo `cofre.config`."""
        try:
            novos = {c.chave: c.normalizar(self._valores[c.chave]) for c in CAMPOS}
        except (ValueError, KeyError) as e:
            self._erro(f"Valor inválido: {e}")
            return False
        for chave, valor in novos.items():
            setattr(config, chave, valor)
        self._valores = novos
        self._atualizar_controles()
        self._ligar_camera_na_config()
        self.mensagem.definir(MENSAGEM_APLICADO, tema.CARTAO, tema.VERDE)
        self.app.status.definir("Configurações aplicadas", None)
        return True

    def restaurar_padroes(self) -> None:
        """Volta o formulário aos valores originais do módulo (não aplica; clique em Aplicar)."""
        self._valores = dict(self.padroes)
        self._atualizar_controles()
        self.mensagem.definir("Padrões restaurados no formulário. Clique em Aplicar para valer.", tema.CARTAO,
                              tema.LARANJA)

    def salvar_arquivo(self) -> bool:
        """Grava os valores do formulário em `config.DATA_DIR/config_usuario.json`."""
        try:
            novos = {c.chave: c.normalizar(self._valores[c.chave]) for c in CAMPOS}
            caminho = self.caminho_arquivo
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(json.dumps(novos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except (OSError, ValueError, KeyError) as e:
            self._erro(f"Não foi possível salvar o arquivo: {e}")
            return False
        self.mensagem.definir(f"Salvo em {caminho}. Será carregado automaticamente ao abrir esta tela.",
                              tema.CARTAO, tema.VERDE)
        return True

    def carregar_arquivo(self) -> bool:
        """Lê o JSON de `config.DATA_DIR/config_usuario.json`, preenche o formulário e aplica."""
        caminho = self.caminho_arquivo
        if not caminho.exists():
            self._erro(f"Arquivo não encontrado: {caminho}")
            return False
        try:
            self._ler_arquivo(caminho)
        except (OSError, ValueError, TypeError) as e:
            self._erro(f"Arquivo inválido ({caminho.name}): {e}")
            return False
        if self.aplicar():
            self.mensagem.definir(f"Carregado de {caminho.name} e aplicado. {MENSAGEM_APLICADO}", tema.CARTAO, tema.VERDE)
            return True
        return False

    # ------------------------------------------------------------------ internos
    def _ler_arquivo(self, caminho: Path) -> None:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(dados, dict):
            raise ValueError("o conteúdo precisa ser um objeto JSON com os nomes dos parâmetros")
        reconhecidos = {k: v for k, v in dados.items() if k in CAMPOS_POR_CHAVE}
        if not reconhecidos:
            raise ValueError("nenhum parâmetro conhecido no arquivo")
        normalizados = {k: CAMPOS_POR_CHAVE[k].normalizar(v) for k, v in reconhecidos.items()}
        self._valores.update(normalizados)
        self._atualizar_controles()

    def _carregar_inicial(self) -> None:
        """Ao abrir a tela: se o arquivo do usuário existir, carrega e aplica (sem estourar exceção)."""
        caminho = self.caminho_arquivo
        try:
            if not caminho.exists():
                self.mensagem.definir("Valores atuais do módulo cofre.config (nenhum arquivo de usuário salvo).",
                                      tema.CARTAO, tema.TEXTO_2)
                return
            self._ler_arquivo(caminho)
            novos = {c.chave: c.normalizar(self._valores[c.chave]) for c in CAMPOS}
            for chave, valor in novos.items():
                setattr(config, chave, valor)
            self._valores = novos
            self.mensagem.definir(f"Configuração carregada de {caminho.name} e aplicada.", tema.CARTAO, tema.VERDE)
        except (OSError, ValueError, TypeError, KeyError) as e:
            self._erro(f"Arquivo {caminho.name} ignorado: {e}")

    def _ligar_camera_na_config(self) -> None:
        """`FonteCamera()` fixa índice/espelho nos defaults de importação; a fábrica passa a ler `config`
        a cada abertura. Só mexe quando a fábrica é a padrão (os testes usam uma câmera falsa)."""
        cam = getattr(self.app, "camera", None)
        if cam is not None and getattr(cam, "fonte_fabrica", None) is FonteCamera:
            cam.fonte_fabrica = lambda: FonteCamera(config.CAMERA_INDEX, config.ESPELHAR_CAMERA)

    def _erro(self, texto: str) -> None:
        self.mensagem.definir(texto, tema.CARTAO, tema.VERMELHO)

    # ------------------------------------------------------------------ ciclo
    def ao_mostrar(self) -> None:
        self.app.status.definir(None, f"arquivo: {self.caminho_arquivo.name}"
                                      f"{'' if self.caminho_arquivo.exists() else ' (não existe)'}")

```

## `cofre/interface/tela_ferramentas.py` (502 linhas)

```python
"""Tela "Avaliação e demo": demonstração didática das 5 fases, autenticação por
imagem e avaliação quantitativa do reconhecedor (TAR/FAR/FRR/EER).

Regras de thread: o `Banco` usa uma conexão sqlite presa à thread do Tk, por isso
só o pipeline (fases 2 a 4) e a avaliação de pasta rodam em `threading.Thread`;
a fase 5 (galeria), o log de acesso e todos os widgets ficam na thread do Tk.
Os resultados das threads chegam por uma fila consumida em `atualizar()`.
"""

from __future__ import annotations

import queue
import threading
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk
import cv2
import numpy as np

from .. import config, hud
from ..autenticacao import autenticar_imagem
from ..avaliacao import ResultadoAvaliacao, avaliar_pasta
from ..fase1_aquisicao import carregar_imagem
from ..fase5_reconhecimento import Reconhecedor, decidir_acesso
from . import tema
from .base import Tela
from .widgets import Cartao, Faixa, Tabela, VideoWidget, botao, botao_secundario, titulo

PASTA_FOTOS_TESTE = config.BASE_DIR / "tests" / "fixtures" / "pessoas"
TIPOS_IMAGEM = [("Imagens", "*.jpg *.jpeg *.png *.bmp *.webp"), ("Todos os arquivos", "*.*")]
NIVEIS_ROTULO = {f"Nível {n}": n for n in config.NIVEIS}

ABA_DEMO = "Demo das 5 fases"
ABA_AUTH = "Autenticar por imagem"
ABA_AVAL = "Avaliar reconhecedor"


def _pct(v: float) -> str:
    return "-" if v != v else f"{v:.1%}"  # NaN quando não há pares


class TelaFerramentas(Tela):
    TITULO = "Avaliação e demo"

    # ------------------------------------------------------------------ construção
    def construir(self) -> None:
        self._fila: queue.Queue[Callable[[], None]] = queue.Queue()
        self.ocupado = False                      # thread de trabalho em andamento
        self.ultimo_demo = None                   # ResultadoPipeline da última demo
        self.ultima_decisao = None                # Decisao da última autenticação por imagem
        self.ultima_avaliacao: ResultadoAvaliacao | None = None
        self.pasta_avaliacao: Path | None = None
        self._caminho_demo: Path | None = None
        self._painel: np.ndarray | None = None    # mosaico da demo (para salvar PNG)
        self._linhas_demo: list[str] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        titulo(self, self.TITULO, "Ferramentas de demonstração e validação do pipeline").grid(
            row=0, column=0, padx=24, pady=(24, 12), sticky="ew")
        self.abas = ctk.CTkTabview(self, fg_color=tema.FUNDO_2, corner_radius=10,
                                   segmented_button_fg_color=tema.CARTAO,
                                   segmented_button_selected_color=tema.ACENTO,
                                   segmented_button_selected_hover_color=tema.ACENTO_HOVER,
                                   segmented_button_unselected_color=tema.CARTAO,
                                   segmented_button_unselected_hover_color=tema.BORDA,
                                   text_color=tema.TEXTO)
        self.abas.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="nsew")
        for nome in (ABA_DEMO, ABA_AUTH, ABA_AVAL):
            self.abas.add(nome)
        self._construir_demo(self.abas.tab(ABA_DEMO))
        self._construir_auth(self.abas.tab(ABA_AUTH))
        self._construir_avaliacao(self.abas.tab(ABA_AVAL))

    def _seletor_nivel(self, master, comando=None) -> ctk.CTkSegmentedButton:
        seg = ctk.CTkSegmentedButton(master, values=list(NIVEIS_ROTULO), font=tema.CORPO,
                                     fg_color=tema.CARTAO, selected_color=tema.ACENTO,
                                     selected_hover_color=tema.ACENTO_HOVER, unselected_color=tema.CARTAO,
                                     unselected_hover_color=tema.BORDA, text_color=tema.TEXTO,
                                     command=comando)
        seg.set("Nível 3")
        return seg

    def _caixa_texto(self, master, **kw) -> ctk.CTkTextbox:
        cx = ctk.CTkTextbox(master, font=tema.MONO, fg_color=tema.CARTAO, text_color=tema.TEXTO,
                            corner_radius=10, wrap="none", **kw)
        cx.configure(state="disabled")
        return cx

    @staticmethod
    def _escrever(caixa: ctk.CTkTextbox, texto: str) -> None:
        caixa.configure(state="normal")
        caixa.delete("1.0", "end")
        caixa.insert("1.0", texto)
        caixa.configure(state="disabled")

    # ---- aba (a): demo das 5 fases
    def _construir_demo(self, aba) -> None:
        aba.grid_columnconfigure(0, weight=1)
        aba.grid_rowconfigure(1, weight=1)
        barra = ctk.CTkFrame(aba, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.bt_demo_imagem = botao(barra, "Escolher imagem...", self._escolher_imagem_demo)
        self.bt_demo_imagem.pack(side="left")
        ctk.CTkLabel(barra, text="Área exigida:", font=tema.CORPO, text_color=tema.TEXTO_2).pack(
            side="left", padx=(12, 6))
        self.nivel_demo = self._seletor_nivel(barra, self._nivel_demo_alterado)
        self.nivel_demo.pack(side="left")
        self.bt_salvar_painel = botao_secundario(barra, "Salvar painel PNG", self.salvar_painel)
        self.bt_salvar_painel.pack(side="left", padx=(12, 0))
        self.lbl_demo_arquivo = ctk.CTkLabel(barra, text="Nenhuma imagem escolhida", font=tema.PEQUENO,
                                             text_color=tema.TEXTO_2)
        self.lbl_demo_arquivo.pack(side="left", padx=12)

        corpo = ctk.CTkFrame(aba, fg_color="transparent")
        corpo.grid(row=1, column=0, sticky="nsew")
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_rowconfigure(0, weight=1)
        self.video_demo = VideoWidget(corpo, largura=640, altura=400)
        self.video_demo.grid(row=0, column=0, sticky="nsew")
        self.video_demo.mensagem("Escolha uma imagem para ver as 5 fases do pipeline")
        self.texto_demo = self._caixa_texto(corpo, width=400)
        self.texto_demo.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.faixa_demo = Faixa(aba)
        self.faixa_demo.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.faixa_demo.definir("Fases 1 a 4 no painel; a fase 5 compara com a galeria do banco.")

    # ---- aba (b): autenticar por imagem
    def _construir_auth(self, aba) -> None:
        aba.grid_columnconfigure(0, weight=1)
        aba.grid_rowconfigure(2, weight=1)
        barra = ctk.CTkFrame(aba, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.bt_auth_imagem = botao(barra, "Escolher imagem...", self._escolher_imagem_auth)
        self.bt_auth_imagem.pack(side="left")
        ctk.CTkLabel(barra, text="Área exigida:", font=tema.CORPO, text_color=tema.TEXTO_2).pack(
            side="left", padx=(12, 6))
        self.nivel_auth = self._seletor_nivel(barra)
        self.nivel_auth.pack(side="left")
        self.lbl_auth_arquivo = ctk.CTkLabel(barra, text="Nenhuma imagem escolhida", font=tema.PEQUENO,
                                             text_color=tema.TEXTO_2)
        self.lbl_auth_arquivo.pack(side="left", padx=12)

        self.faixa_auth = Faixa(aba)
        self.faixa_auth.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.faixa_auth.definir("Escolha uma imagem: a tentativa é registrada no log de acessos.")

        corpo = ctk.CTkFrame(aba, fg_color="transparent")
        corpo.grid(row=2, column=0, sticky="nsew")
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_rowconfigure(0, weight=1)
        self.video_auth = VideoWidget(corpo, largura=560, altura=360)
        self.video_auth.grid(row=0, column=0, sticky="nsew")
        self.video_auth.mensagem("A imagem aparece aqui com o rosto marcado")
        cartoes = ctk.CTkFrame(corpo, fg_color="transparent", width=240)
        cartoes.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        self.cartao_auth_usuario = Cartao(cartoes, "Identificado como")
        self.cartao_auth_sim = Cartao(cartoes, f"Similaridade (limiar {config.LIMIAR_COSSENO:.3f})")
        self.cartao_auth_nivel = Cartao(cartoes, "Nível do usuário / exigido")
        self.cartao_auth_rostos = Cartao(cartoes, "Rostos na imagem")
        for c in (self.cartao_auth_usuario, self.cartao_auth_sim, self.cartao_auth_nivel, self.cartao_auth_rostos):
            c.pack(fill="x", pady=(0, 12))

    # ---- aba (c): avaliar reconhecedor
    def _construir_avaliacao(self, aba) -> None:
        aba.grid_columnconfigure(0, weight=1)
        aba.grid_rowconfigure(2, weight=1)
        barra = ctk.CTkFrame(aba, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.bt_aval_pasta = botao_secundario(barra, "Escolher pasta...", self._escolher_pasta)
        self.bt_aval_pasta.pack(side="left")
        self.bt_aval_teste = botao_secundario(barra, "Usar fotos de teste", self.usar_fotos_teste)
        self.bt_aval_teste.pack(side="left", padx=(12, 0))
        self.bt_avaliar = botao(barra, "Avaliar", self._avaliar_clicado)
        self.bt_avaliar.pack(side="left", padx=(12, 0))
        self.lbl_aval_status = ctk.CTkLabel(barra, text="", font=tema.CORPO, text_color=tema.ACENTO)
        self.lbl_aval_status.pack(side="right")
        self.lbl_aval_pasta = ctk.CTkLabel(barra, text="Nenhuma pasta escolhida (estrutura: pasta/pessoa/*.jpg)",
                                           font=tema.PEQUENO, text_color=tema.TEXTO_2)
        self.lbl_aval_pasta.pack(side="left", padx=12)

        linha_cartoes = ctk.CTkFrame(aba, fg_color="transparent")
        linha_cartoes.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        lim = f"limiar {config.LIMIAR_COSSENO:.3f}"
        self.cartao_tar = Cartao(linha_cartoes, f"TAR ({lim})", cor=tema.VERDE)
        self.cartao_far = Cartao(linha_cartoes, f"FAR ({lim})", cor=tema.VERMELHO)
        self.cartao_frr = Cartao(linha_cartoes, f"FRR ({lim})", cor=tema.LARANJA)
        self.cartao_eer = Cartao(linha_cartoes, "EER (limiar -)", cor=tema.AZUL)
        for i, c in enumerate((self.cartao_tar, self.cartao_far, self.cartao_frr, self.cartao_eer)):
            linha_cartoes.grid_columnconfigure(i, weight=1)
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 12, 0))

        corpo = ctk.CTkFrame(aba, fg_color="transparent")
        corpo.grid(row=2, column=0, sticky="nsew")
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_columnconfigure(1, weight=1)
        corpo.grid_rowconfigure(0, weight=1)
        self.texto_aval = self._caixa_texto(corpo)
        self.texto_aval.grid(row=0, column=0, sticky="nsew")
        self._escrever(self.texto_aval, "O resumo da avaliação aparece aqui.")
        self.tabela_varredura = Tabela(corpo, [("limiar", "Limiar", 90), ("tar", "TAR", 90),
                                               ("frr", "FRR", 90), ("far", "FAR", 90)], altura=11)
        self.tabela_varredura.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.faixa_aval = Faixa(aba)
        self.faixa_aval.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.faixa_aval.definir("Compara todos os pares de imagens: mesma pessoa = genuíno, pessoas diferentes = impostor.")

    # ------------------------------------------------------------------ ciclo
    def ao_mostrar(self) -> None:
        self.app.status.definir(self.TITULO, None)

    def atualizar(self) -> None:
        while True:
            try:
                fn = self._fila.get_nowait()
            except queue.Empty:
                return
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self._erro_geral(f"Erro inesperado: {e}")

    def _erro_geral(self, msg: str) -> None:
        faixa = {ABA_DEMO: self.faixa_demo, ABA_AUTH: self.faixa_auth, ABA_AVAL: self.faixa_aval}[self.abas.get()]
        faixa.definir(msg, tema.VERMELHO)

    def _pipeline_ou_aviso(self, faixa: Faixa) -> bool:
        if not self.app.pipeline_pronto():
            faixa.definir("Os modelos ainda estão carregando, tente de novo em instantes.", tema.LARANJA, tema.FUNDO)
            return False
        if self.ocupado:
            faixa.definir("Aguarde: já existe um processamento em andamento.", tema.LARANJA, tema.FUNDO)
            return False
        return True

    def _em_thread(self, alvo: Callable[[], Callable[[], None]], faixa: Faixa) -> None:
        """Roda `alvo` fora do Tk; ele devolve a função que aplica o resultado nos widgets."""
        self.ocupado = True

        def rodar():
            try:
                aplicar = alvo()
            except Exception as e:  # noqa: BLE001
                msg = f"Falha: {e}"
                aplicar = lambda: faixa.definir(msg, tema.VERMELHO)  # noqa: E731
            finally:
                self.ocupado = False
            self._fila.put(aplicar)

        threading.Thread(target=rodar, name="ferramentas", daemon=True).start()

    # ------------------------------------------------------------------ (a) demo
    def _escolher_imagem_demo(self) -> None:
        caminho = filedialog.askopenfilename(title="Imagem para a demonstração", filetypes=TIPOS_IMAGEM)
        if caminho:
            self.demonstrar(caminho)

    def _nivel_demo_alterado(self, _valor=None) -> None:
        if self.ultimo_demo is not None:
            self._mostrar_demo(self.ultimo_demo)

    def demonstrar(self, caminho: str | Path) -> None:
        """Roda o pipeline na imagem e monta o painel das 5 fases (fases 2 a 4 em thread)."""
        if not self._pipeline_ou_aviso(self.faixa_demo):
            return
        caminho = Path(caminho)
        self._caminho_demo = caminho
        self.lbl_demo_arquivo.configure(text=caminho.name)
        self.faixa_demo.definir("Processando...", tema.CARTAO)
        pipeline = self.app.pipeline

        def trabalho():
            frame = carregar_imagem(caminho)
            res = pipeline.processar(frame)
            painel = hud.mosaico(res.etapas_didaticas(), lado=200, colunas=4)
            return lambda: self._demo_pronta(res, painel)

        self._em_thread(trabalho, self.faixa_demo)

    def _demo_pronta(self, res, painel: np.ndarray) -> None:
        self.ultimo_demo, self._painel = res, painel
        self.video_demo.mostrar(painel)
        self._mostrar_demo(res)

    def _mostrar_demo(self, res) -> None:
        """Monta o texto das fases (a fase 5 usa o banco, por isso roda na thread do Tk)."""
        nivel = NIVEIS_ROTULO[self.nivel_demo.get()]
        nome = self._caminho_demo.name if self._caminho_demo else "-"
        frame = res.pre.original
        linhas = [f"FASE 1  Aquisição",
                  f"  arquivo: {nome}",
                  f"  tamanho: {frame.shape[1]}x{frame.shape[0]} px",
                  "",
                  f"FASE 2  Pré-processamento",
                  f"  frame reduzido: {res.pre.reduzida.shape[1]}x{res.pre.reduzida.shape[0]} px (escala {res.pre.escala:.2f})",
                  "",
                  f"FASE 3  Segmentação",
                  f"  rostos detectados: {len(res.rostos)}"]
        p = res.principal
        if p is None:
            linhas += ["  nenhum rosto: as fases 4 e 5 não rodam", "", "FASE 4  Representação: -", "", "FASE 5  Reconhecimento: -"]
            self.faixa_demo.definir("Nenhum rosto detectado na imagem. Tente uma foto frontal e bem iluminada.",
                                    tema.LARANJA, tema.FUNDO)
        else:
            x, y, w, h = p.rosto.caixa
            norma = float(np.linalg.norm(p.embedding))
            qual = "aprovada" if p.qualidade.aprovada else "reprovada"
            ident = Reconhecedor(self.app.banco).identificar(p.embedding)
            d = decidir_acesso(ident, nivel)
            linhas += [f"  caixa (x, y, w, h): ({x}, {y}, {w}, {h})",
                       f"  confiança: {p.rosto.confianca:.3f}",
                       f"  yaw (nariz/olhos): {p.rosto.yaw():+.3f}",
                       f"  nitidez: {p.qualidade.nitidez:.1f} (mín {config.MIN_NITIDEZ:.0f})",
                       f"  brilho: {p.qualidade.brilho:.1f} ({config.MIN_BRILHO:.0f} a {config.MAX_BRILHO:.0f})",
                       f"  qualidade: {qual}",
                       "",
                       f"FASE 4  Representação",
                       f"  embedding: {p.embedding.shape[0]}-d, norma {norma:.3f}",
                       f"  min {float(p.embedding.min()):+.3f}  max {float(p.embedding.max()):+.3f}",
                       "",
                       f"FASE 5  Reconhecimento ({config.AREAS[nivel]})",
                       f"  galeria: {len(Reconhecedor(self.app.banco).usuarios)} usuário(s)",
                       f"  identificado: {ident.rotulo}",
                       f"  similaridade: {ident.similaridade:.3f} (limiar {config.LIMIAR_COSSENO:.3f})",
                       f"  2º colocado: {ident.segunda_similaridade:.3f}",
                       f"  decisão: {d.resultado.value}",
                       f"  {d.mensagem}"]
            self.faixa_demo.definir(f"{tema.ROTULO_RESULTADO[d.resultado.value]}: {d.mensagem}",
                                    tema.COR_RESULTADO[d.resultado.value], tema.FUNDO)
        self._linhas_demo = linhas
        self._escrever(self.texto_demo, "\n".join(linhas))

    def salvar_painel(self) -> Path | None:
        """Grava o mosaico (com as linhas de dados no rodapé) em config.RELATORIOS_DIR."""
        if self._painel is None:
            self.faixa_demo.definir("Nada para salvar: rode a demonstração em uma imagem primeiro.",
                                    tema.LARANJA, tema.FUNDO)
            return None
        try:
            linhas = [l for l in self._linhas_demo if l.strip()]
            rodape = 20 * len(linhas) + 16
            painel = self._painel
            base = np.full((painel.shape[0] + rodape, painel.shape[1], 3), 20, np.uint8)
            base[:painel.shape[0]] = painel
            y = painel.shape[0] + 20
            for l in linhas:
                hud.texto(base, l, (10, y), 0.45, hud.BRANCO, 1)
                y += 20
            pasta = Path(config.RELATORIOS_DIR)
            pasta.mkdir(parents=True, exist_ok=True)
            stem = self._caminho_demo.stem if self._caminho_demo else "imagem"
            destino = pasta / f"demo_{stem}_{datetime.now():%Y%m%d_%H%M%S}.png"
            if not cv2.imwrite(str(destino), base):
                raise OSError("cv2.imwrite não conseguiu gravar o arquivo")
        except Exception as e:  # noqa: BLE001
            self.faixa_demo.definir(f"Não foi possível salvar o painel: {e}", tema.VERMELHO)
            return None
        self.faixa_demo.definir(f"Painel salvo em {destino}", tema.VERDE, tema.FUNDO)
        self.app.status.definir(f"Painel salvo: {destino.name}", None)
        return destino

    # ------------------------------------------------------------------ (b) autenticar por imagem
    def _escolher_imagem_auth(self) -> None:
        caminho = filedialog.askopenfilename(title="Imagem para autenticar", filetypes=TIPOS_IMAGEM)
        if caminho:
            self.autenticar(caminho)

    def autenticar(self, caminho: str | Path):
        """Autentica a imagem no nível escolhido e registra no log (roda na thread do Tk:
        `autenticar_imagem` grava no banco, que não aceita outra thread)."""
        if not self._pipeline_ou_aviso(self.faixa_auth):
            return None
        caminho = Path(caminho)
        self.lbl_auth_arquivo.configure(text=caminho.name)
        nivel = NIVEIS_ROTULO[self.nivel_auth.get()]
        try:
            frame = carregar_imagem(caminho)
            decisao, res = autenticar_imagem(self.app.banco, self.app.pipeline, frame, nivel)
        except Exception as e:  # noqa: BLE001
            self.faixa_auth.definir(f"Falha ao autenticar: {e}", tema.VERMELHO)
            return None
        self.ultima_decisao = decisao
        marcado = frame.copy()
        cor = hud.VERDE if decisao.concedido else hud.VERMELHO
        for r in res.rostos:
            hud.caixa_rosto(marcado, r.rosto, cor, rotulo=None)
        self.video_auth.mostrar(marcado)

        chave = decisao.resultado.value
        self.faixa_auth.definir(f"{tema.ROTULO_RESULTADO[chave]}: {decisao.mensagem}",
                                tema.COR_RESULTADO[chave], tema.FUNDO)
        ident = decisao.identificacao
        u = ident.usuario if ident and ident.reconhecido else None
        self.cartao_auth_usuario.definir(u.nome if u else "Desconhecido", tema.VERDE if u else tema.VERMELHO)
        if ident is not None:
            self.cartao_auth_sim.definir(f"{ident.similaridade:.3f}",
                                         tema.VERDE if ident.reconhecido else tema.VERMELHO)
        else:
            self.cartao_auth_sim.definir("-", tema.TEXTO_2)
        self.cartao_auth_nivel.definir(f"{u.nivel if u else '-'} / {nivel}",
                                       tema.COR_NIVEL.get(nivel, tema.TEXTO))
        self.cartao_auth_rostos.definir(len(res.rostos), tema.TEXTO if len(res.rostos) == 1 else tema.LARANJA)
        self.app.status.definir(f"Autenticação por imagem: {chave}", None)
        return decisao

    # ------------------------------------------------------------------ (c) avaliar reconhecedor
    def _escolher_pasta(self) -> None:
        pasta = filedialog.askdirectory(title="Pasta com subpastas por pessoa")
        if pasta:
            self._definir_pasta(Path(pasta))

    def usar_fotos_teste(self) -> None:
        self._definir_pasta(PASTA_FOTOS_TESTE)

    def _definir_pasta(self, pasta: Path) -> None:
        self.pasta_avaliacao = pasta
        self.lbl_aval_pasta.configure(text=str(pasta))
        self.faixa_aval.definir(f"Pasta escolhida: {pasta.name}. Clique em Avaliar.")

    def _avaliar_clicado(self) -> None:
        if self.pasta_avaliacao is None:
            self.faixa_aval.definir("Escolha uma pasta (ou use as fotos de teste) antes de avaliar.",
                                    tema.LARANJA, tema.FUNDO)
            return
        self.avaliar(self.pasta_avaliacao)

    def avaliar(self, pasta: str | Path) -> None:
        """Roda `avaliacao.avaliar_pasta` em thread e preenche resumo, cartões e varredura."""
        if not self._pipeline_ou_aviso(self.faixa_aval):
            return
        pasta = Path(pasta)
        if not pasta.is_dir():
            self.faixa_aval.definir(f"Pasta não encontrada: {pasta}", tema.VERMELHO)
            return
        if not any(p.is_dir() for p in pasta.iterdir()):
            self.faixa_aval.definir("A pasta precisa ter uma subpasta por pessoa (pasta/pessoa/*.jpg).",
                                    tema.LARANJA, tema.FUNDO)
            return
        self._definir_pasta(pasta)
        self.lbl_aval_status.configure(text="Avaliando...")
        self.bt_avaliar.configure(state="disabled")
        self.faixa_aval.definir("Avaliando todas as imagens, isso pode levar alguns segundos...", tema.CARTAO)
        pipeline = self.app.pipeline

        def trabalho():
            r = avaliar_pasta(pasta, pipeline)
            return lambda: self._avaliacao_pronta(r)

        def ao_terminar():
            self.lbl_aval_status.configure(text="")
            self.bt_avaliar.configure(state="normal")

        def trabalho_com_fecho():
            try:
                aplicar = trabalho()
            except Exception:
                self._fila.put(ao_terminar)
                raise
            return lambda: (ao_terminar(), aplicar())

        self._em_thread(trabalho_com_fecho, self.faixa_aval)

    def _avaliacao_pronta(self, r: ResultadoAvaliacao) -> None:
        self.ultima_avaliacao = r
        self._escrever(self.texto_aval, r.resumo())
        self.tabela_varredura.limpar()
        n_pares = len(r.genuinos) + len(r.impostores)
        if n_pares == 0:
            for c in (self.cartao_tar, self.cartao_far, self.cartao_frr, self.cartao_eer):
                c.definir("-")
            self.faixa_aval.definir(
                f"Nenhum par para comparar ({sum(r.pessoas.values())} imagem(ns) com rosto, "
                f"{len(r.sem_rosto)} sem rosto). São necessárias ao menos 2 imagens com rosto.",
                tema.LARANJA, tema.FUNDO)
            return
        t = r.taxas(config.LIMIAR_COSSENO)
        eer_l, eer_v = r.eer()
        self.cartao_tar.definir(_pct(t["TAR"]))
        self.cartao_far.definir(_pct(t["FAR"]))
        self.cartao_frr.definir(_pct(t["FRR"]))
        self.cartao_eer.definir(_pct(eer_v))
        self.cartao_eer.rotulo.configure(text=f"EER (limiar {eer_l:.3f})")
        mais_proximo = min(r.varredura(11), key=lambda v: abs(v["limiar"] - config.LIMIAR_COSSENO))["limiar"]
        for i, v in enumerate(r.varredura(11)):
            tag = "ok" if v["limiar"] == mais_proximo else None
            self.tabela_varredura.adicionar(f"v{i}", [f"{v['limiar']:.2f}", _pct(v["TAR"]), _pct(v["FRR"]),
                                                     _pct(v["FAR"])], tag)
        partes = [f"{len(r.pessoas)} pessoa(s), {sum(r.pessoas.values())} imagem(ns) com rosto, "
                  f"{len(r.genuinos)} par(es) genuíno(s) e {len(r.impostores)} impostor(es)."]
        cor, cor_texto = tema.VERDE, tema.FUNDO
        if r.sem_rosto:
            nomes = ", ".join(Path(s).name for s in r.sem_rosto[:3])
            extra = f" e mais {len(r.sem_rosto) - 3}" if len(r.sem_rosto) > 3 else ""
            partes.append(f"Ignoradas {len(r.sem_rosto)} sem rosto: {nomes}{extra}.")
            cor, cor_texto = tema.LARANJA, tema.FUNDO
        self.faixa_aval.definir(" ".join(partes), cor, cor_texto)
        self.app.status.definir(f"Avaliação concluída: EER {_pct(eer_v)}", None)

```

## `cofre/interface/tela_terminal.py` (504 linhas)

```python
"""
Tela "Terminal de acesso": o terminal na porta do cofre, em tempo real.

À esquerda, o vídeo da câmera com o HUD desenhado por `TerminalAutenticacao.desenhar()`
(e, opcionalmente, o painel didático com as 5 fases do pipeline). À direita, o painel de
controle: área/nível exigido, prova de vida, estado atual, similaridade, galeria, FPS,
últimos acessos e botões de manutenção. Atalhos de teclado iguais aos da versão CLI:
1/2/3 (área), l (prova de vida), d (painel didático) e r (recarregar galeria).

Divisão de trabalho entre threads
---------------------------------
A thread da câmera roda apenas a parte cara (`pipeline.processar`) e entrega
`(frame, resultado, sequencial)`. A máquina de estados (`passo`), o HUD (`desenhar`) e
o `status()` rodam na thread do Tk, dentro de `atualizar()`, porque `passo()` grava o
log de acessos no SQLite e a conexão do `Banco` só pode ser usada na thread que a criou
(a principal). Cada frame é processado uma única vez (controle pelo sequencial).
"""

from __future__ import annotations

import time
import tkinter as tk
import traceback
from typing import Any

import customtkinter as ctk

from .. import config, hud
from ..autenticacao import Estado, TerminalAutenticacao
from . import tema
from .base import Tela
from .widgets import Cartao, Faixa, Tabela, VideoWidget, botao, botao_secundario, titulo

# A cada quantos segundos o terminal confere se outro processo gravou no banco
# (cadastro feito em outra janela ou pela linha de comando).
INTERVALO_CHECAGEM_BANCO_SEG = 1.0

# Rótulos curtos do seletor de área (nível exigido -> rótulo) e o inverso.
ROTULO_NIVEL = {1: "1 Área comum", 2: "2 Diretores", 3: "3 Cofre do Ministro"}
NIVEL_DO_ROTULO = {v: k for k, v in ROTULO_NIVEL.items()}

AJUDA_CAMERA_MAC = "No macOS, permita o acesso à câmera em Ajustes > Privacidade e Segurança > Câmera."


def _mensagem(video: VideoWidget, texto: str) -> None:
    """Troca a imagem do VideoWidget por um texto.

    Contorna um problema de `VideoWidget.mensagem()`: ela zera a referência da imagem antes de
    tirá-la do `tk.Label` (e `configure(image=None)` é ignorado pelo tkinter), o que deixa o
    rótulo apontando para uma imagem já destruída e estoura `TclError` no próximo redesenho.
    """
    rotulo = getattr(video, "_label", None)
    if rotulo is not None:
        try:
            rotulo.configure(image="")
        except tk.TclError:
            pass
    video.mensagem(texto)


class TelaTerminal(Tela):
    """Terminal de autenticação facial com seleção de área, prova de vida e painel didático."""

    TITULO = "Terminal de acesso"

    def __init__(self, master, app):
        # Estado da tela (definido antes de `construir()` ser chamado pela base).
        self.terminal: TerminalAutenticacao | None = None
        self.nivel: int = 3
        self.liveness: bool = bool(config.LIVENESS_ATIVO)
        self.didatico: bool = False
        self.status: dict[str, Any] = {}       # último snapshot de terminal.status() (+ similaridade, fps, n_rostos)
        self._quer_camera = False
        self._iniciada = False
        self._seq = 0                          # contador incrementado na thread da câmera
        self._seq_visto = -1
        self._estado_anterior: str | None = None
        self._erro_mostrado: str | None = None
        self._funcid_tecla: str | None = None
        self._cache_cfg: dict[int, dict] = {}  # evita reconfigurar widgets com os mesmos valores a 30 Hz
        self._versao_banco: int | None = None  # PRAGMA data_version visto na última checagem
        self._ultima_checagem_banco = 0.0
        super().__init__(master, app)

    # ------------------------------------------------------------------ layout
    def construir(self) -> None:
        self.grid_columnconfigure(0, weight=65, uniform="colunas")
        self.grid_columnconfigure(1, weight=35, uniform="colunas")
        self.grid_rowconfigure(1, weight=1)

        titulo(self, self.TITULO, "Autenticação facial em tempo real com três níveis de permissão").grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(24, 12))

        # ---- esquerda: vídeo + painel didático
        esq = ctk.CTkFrame(self, fg_color="transparent")
        esq.grid(row=1, column=0, sticky="nsew", padx=(24, 6), pady=(0, 24))
        esq.grid_columnconfigure(0, weight=1)
        esq.grid_rowconfigure(0, weight=1)
        self.video = VideoWidget(esq, largura=640, altura=360)
        self.video.grid(row=0, column=0, sticky="nsew")
        self.video_didatico = VideoWidget(esq, largura=640, altura=220)
        self.video_didatico.configure(height=220)
        self.video_didatico.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.video_didatico.grid_remove()
        self._mensagem(self.video_didatico, "Painel didático: as 5 fases do pipeline aparecem aqui")
        # Botão sobreposto ao vídeo, exibido só quando a câmera falha.
        self.botao_tentar = botao(esq, "Tentar novamente", self.tentar_camera, width=180)

        # ---- direita: painel de controle
        painel = ctk.CTkFrame(self, fg_color="transparent")
        painel.grid(row=1, column=1, sticky="nsew", padx=(6, 24), pady=(0, 24))
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_rowconfigure(8, weight=1)

        ctk.CTkLabel(painel, text="Área / nível exigido", font=tema.PEQUENO, text_color=tema.TEXTO_2,
                     anchor="w").grid(row=0, column=0, sticky="ew")
        self.seletor_nivel = ctk.CTkSegmentedButton(
            painel, values=list(ROTULO_NIVEL.values()), command=self._ao_escolher_nivel, font=tema.CORPO,
            fg_color=tema.FUNDO_2, selected_color=tema.ACENTO, selected_hover_color=tema.ACENTO_HOVER,
            unselected_color=tema.CARTAO, unselected_hover_color=tema.BORDA, text_color=tema.TEXTO)
        self.seletor_nivel.set(ROTULO_NIVEL[self.nivel])
        self.seletor_nivel.grid(row=1, column=0, sticky="ew", pady=(2, 12))

        chaves = ctk.CTkFrame(painel, fg_color="transparent")
        chaves.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self._var_liveness = tk.BooleanVar(value=self.liveness)
        self._var_didatico = tk.BooleanVar(value=self.didatico)
        self.chave_liveness = ctk.CTkSwitch(chaves, text="Prova de vida", variable=self._var_liveness,
                                            onvalue=True, offvalue=False, command=self._ao_alternar_liveness,
                                            font=tema.CORPO, progress_color=tema.ACENTO)
        self.chave_liveness.pack(side="left", padx=(0, 20))
        self.chave_didatico = ctk.CTkSwitch(chaves, text="Painel didático", variable=self._var_didatico,
                                            onvalue=True, offvalue=False, command=self._ao_alternar_didatico,
                                            font=tema.CORPO, progress_color=tema.ACENTO)
        self.chave_didatico.pack(side="left")

        self.faixa = Faixa(painel)
        self.faixa.configure(height=112)
        self.faixa.texto.configure(wraplength=320, justify="left", anchor="w")
        self.faixa.bind("<Configure>", lambda e: self.faixa.texto.configure(wraplength=max(120, e.width - 40)))
        self.faixa.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        self._definir_faixa("Câmera desligada", tema.CARTAO, tema.TEXTO_2)

        sim = ctk.CTkFrame(painel, fg_color="transparent")
        sim.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        self.rotulo_similaridade = ctk.CTkLabel(sim, text="", font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w")
        self.rotulo_similaridade.pack(fill="x")
        self.barra_similaridade = ctk.CTkProgressBar(sim, height=12, fg_color=tema.BORDA, progress_color=tema.VERMELHO)
        self.barra_similaridade.set(0.0)
        self.barra_similaridade.pack(fill="x", pady=(4, 0))
        self._definir_similaridade(None)

        cartoes = ctk.CTkFrame(painel, fg_color="transparent")
        cartoes.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        cartoes.grid_columnconfigure((0, 1), weight=1, uniform="cartoes")
        self.cartao_galeria = Cartao(cartoes, "amostras na galeria", "0")
        self.cartao_galeria.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.cartao_fps = Cartao(cartoes, "FPS", "0")
        self.cartao_fps.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.aviso = ctk.CTkLabel(painel, text="", font=tema.CORPO, text_color=tema.AMARELO, anchor="w",
                                  justify="left", wraplength=320)
        self.aviso.grid(row=6, column=0, sticky="ew", pady=(0, 12))
        self.aviso.grid_remove()

        ctk.CTkLabel(painel, text="Últimos acessos", font=tema.PEQUENO, text_color=tema.TEXTO_2,
                     anchor="w").grid(row=7, column=0, sticky="ew")
        self.tabela = Tabela(painel, [("hora", "Hora", 64), ("nome", "Nome", 100), ("resultado", "Resultado", 130),
                                      ("nivel", "Nível", 44), ("sim", "Sim.", 44)], altura=8)
        self.tabela.grid(row=8, column=0, sticky="nsew", pady=(2, 12))

        botoes = ctk.CTkFrame(painel, fg_color="transparent")
        botoes.grid(row=9, column=0, sticky="ew")
        botoes.grid_columnconfigure((0, 1), weight=1, uniform="botoes")
        self.botao_recarregar = botao_secundario(botoes, "Recarregar galeria", self.recarregar_galeria)
        self.botao_recarregar.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.botao_camera = botao_secundario(botoes, "Tentar câmera novamente", self.tentar_camera)
        self.botao_camera.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    # ------------------------------------------------------------------ ciclo de vida
    def ao_mostrar(self) -> None:
        self._quer_camera = True
        self._iniciada = False
        self._seq_visto = -1
        self._estado_anterior = None
        self._erro_mostrado = None
        self.app.camera.erro = None          # parar() não limpa o erro anterior; só iniciar() limpa
        self.botao_tentar.place_forget()
        if self.terminal is not None:
            self.terminal.definir_nivel(self.nivel)      # volta a AGUARDANDO ao reabrir a tela
        self._mensagem(self.video, "Carregando modelos..." if not self.app.pipeline_pronto() else "Abrindo a câmera...")
        self._definir_faixa("Aguardando a câmera...", tema.CARTAO, tema.TEXTO_2)
        self.atualizar_acessos()
        self.verificar_usuarios()
        if self._funcid_tecla is None:
            self._funcid_tecla = self.app.bind("<KeyPress>", self._tecla, add="+")

    def ao_esconder(self) -> None:
        self._quer_camera = False
        self._iniciada = False
        try:
            self.app.camera.parar()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        if self._funcid_tecla is not None:
            try:
                self.app.unbind("<KeyPress>", self._funcid_tecla)
            except tk.TclError:
                pass
            self._funcid_tecla = None
        self._mensagem(self.video, "Câmera desligada")

    def atualizar(self) -> None:
        if not self._quer_camera:
            return
        cam = self.app.camera
        if cam.erro and not cam.ativo:               # a thread da câmera morreu (sem permissão, sem dispositivo...)
            self._mostrar_erro_camera(cam.erro)
            return
        if not self._iniciada:
            if not self.app.pipeline_pronto():
                erro = getattr(self.app, "_erro_pipeline", None)
                if erro:
                    self._mostrar_erro_camera(erro, retentar=False)
                return
            self._iniciar_camera()
            return
        self._checar_banco()
        pacote = cam.ultimo()
        if not isinstance(pacote, tuple) or len(pacote) != 3:
            return
        frame, res, seq = pacote
        if seq == self._seq_visto:
            return
        self._seq_visto = seq
        if self._erro_mostrado is not None:          # a câmera voltou
            self._erro_mostrado = None
            self.botao_tentar.place_forget()
        term = self.terminal
        try:
            term.passo(frame, res.principal, len(res.rostos))
            tela = term.desenhar(frame, res, cam.fps)
            st = term.status()
            ident = term.identificacao_atual(res.principal)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._definir_faixa(f"Erro no processamento: {e}", tema.VERMELHO, tema.TEXTO)
            return
        st["similaridade"] = float(ident.similaridade) if ident is not None else None
        st["fps"] = float(cam.fps)
        st["n_rostos"] = len(res.rostos)
        self.status = st
        self.video.mostrar(tela)
        if self.didatico:
            try:
                self.video_didatico.mostrar(hud.mosaico(res.etapas_didaticas(), lado=160, colunas=5))
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        if cam.erro:                                 # erro de processamento que não derrubou a câmera
            self._definir_faixa(cam.erro, tema.VERMELHO, tema.TEXTO)
        else:
            self._atualizar_painel(st)
        if st["estado"] == Estado.RESULTADO.value and self._estado_anterior != Estado.RESULTADO.value:
            self.atualizar_acessos()                 # a decisão (e um eventual bloqueio) acabou de ser registrada
        self._estado_anterior = st["estado"]

    # ------------------------------------------------------------------ câmera
    @staticmethod
    def _mensagem(video: VideoWidget, texto: str) -> None:
        _mensagem(video, texto)

    def _iniciar_camera(self) -> None:
        if self.terminal is None:
            self.terminal = TerminalAutenticacao(self.app.banco, self.app.pipeline, nivel_exigido=self.nivel,
                                                 liveness=self.liveness, didatico=self.didatico)
            self.verificar_usuarios()
        self.app.camera.definir_processador(self._processar)
        self.app.camera.iniciar()
        self._iniciada = True
        self._mensagem(self.video, "Abrindo a câmera...")

    def _processar(self, frame):
        """Roda NA THREAD DA CÂMERA: só a parte cara (detecção + embedding). Nada de Tk nem de banco aqui."""
        res = self.app.pipeline.processar(frame)
        self._seq += 1
        return (frame, res, self._seq)

    def tentar_camera(self) -> None:
        """Reabre a câmera (botão "Tentar novamente" / "Tentar câmera novamente")."""
        if not self._quer_camera:
            return
        try:
            self.app.camera.parar()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        self.app.camera.erro = None          # senão `atualizar()` continua no ramo de erro e nunca reabre
        self._iniciada = False
        self._seq_visto = -1
        self._erro_mostrado = None
        self.botao_tentar.place_forget()
        self._mensagem(self.video, "Abrindo a câmera...")
        self._definir_faixa("Tentando abrir a câmera...", tema.CARTAO, tema.TEXTO_2)
        self.app.status.definir("Reabrindo a câmera...", None)

    def _mostrar_erro_camera(self, erro: str, retentar: bool = True) -> None:
        if erro == self._erro_mostrado:
            return
        self._erro_mostrado = erro
        texto = f"Câmera indisponível\n\n{erro}"
        if retentar:
            texto += f"\n\n{AJUDA_CAMERA_MAC}"
            self.botao_tentar.place(in_=self.video, relx=0.5, rely=0.8, anchor="center")
        self._mensagem(self.video, texto)
        self._definir_faixa("Câmera indisponível" if retentar else "Modelos não carregados", tema.VERMELHO, tema.TEXTO)
        self._definir_similaridade(None)
        self.cartao_fps.definir("0")

    # ------------------------------------------------------------------ controles
    def definir_nivel(self, nivel: int) -> None:
        """Muda a área/nível exigido (seletor, atalhos 1/2/3)."""
        if nivel not in config.AREAS:
            return
        self.nivel = int(nivel)
        if self.seletor_nivel.get() != ROTULO_NIVEL[self.nivel]:
            self.seletor_nivel.set(ROTULO_NIVEL[self.nivel])
        if self.terminal is not None:
            self.terminal.definir_nivel(self.nivel)
        self.app.status.definir(f"Área exigida: {config.AREAS[self.nivel]} (nível {self.nivel})", None)

    def alternar_liveness(self, ativo: bool | None = None) -> None:
        """Liga/desliga a prova de vida (switch, atalho l). Sem argumento, inverte."""
        self.liveness = (not self.liveness) if ativo is None else bool(ativo)
        self._var_liveness.set(self.liveness)
        if self.terminal is not None:
            self.terminal.liveness_ativo = self.liveness
        self.app.status.definir(f"Prova de vida {'ligada' if self.liveness else 'desligada'}", None)

    def alternar_didatico(self, ativo: bool | None = None) -> None:
        """Mostra/esconde o painel didático com as 5 fases (switch, atalho d). Sem argumento, inverte."""
        self.didatico = (not self.didatico) if ativo is None else bool(ativo)
        self._var_didatico.set(self.didatico)
        if self.terminal is not None:
            self.terminal.didatico = self.didatico
        if self.didatico:
            self.video_didatico.grid()
        else:
            self.video_didatico.grid_remove()
            self._mensagem(self.video_didatico, "Painel didático: as 5 fases do pipeline aparecem aqui")

    def _checar_banco(self) -> None:
        """Recarrega a galeria quando outro processo grava no banco. Sem isso, um cadastro feito
        em outra janela ou pela linha de comando só valeria depois de "Recarregar galeria"."""
        agora = time.monotonic()
        if agora - self._ultima_checagem_banco < INTERVALO_CHECAGEM_BANCO_SEG:
            return
        self._ultima_checagem_banco = agora
        try:
            versao = self.app.banco.versao_dados()
        except Exception:  # noqa: BLE001
            return
        anterior, self._versao_banco = self._versao_banco, versao
        if anterior is not None and versao != anterior:
            self.recarregar_galeria()

    def recarregar_galeria(self) -> None:
        """Relê usuários ativos e amostras do banco (botão, atalho r)."""
        try:
            if self.terminal is not None:
                self.terminal.reconhecedor.recarregar()
                total = self.terminal.reconhecedor.total_amostras
            else:
                total = self.app.banco.estatisticas()["amostras"]
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._definir_faixa(f"Falha ao recarregar a galeria: {e}", tema.VERMELHO, tema.TEXTO)
            return
        self.cartao_galeria.definir(total)
        self.verificar_usuarios()
        self.atualizar_acessos()
        self.app.status.definir(f"Galeria recarregada: {total} amostras", None)

    def verificar_usuarios(self) -> None:
        """Avisa em amarelo quando não há usuário ativo (ou nenhum tem amostra biométrica)."""
        try:
            ativos = self.app.banco.listar_usuarios(apenas_ativos=True)
            if not ativos:
                texto = ("Nenhum usuário ativo cadastrado: todo rosto será negado. "
                         "Cadastre alguém em \"Cadastro biométrico\".")
            elif self.terminal is not None and self.terminal.reconhecedor.total_amostras == 0:
                texto = "Os usuários ativos não têm amostras biométricas: refaça o cadastro."
            else:
                texto = ""
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            texto = f"Não foi possível consultar os usuários: {e}"
        if texto:
            self.aviso.configure(text=texto)
            self.aviso.grid()
        else:
            self.aviso.grid_remove()

    def atualizar_acessos(self) -> None:
        """Recarrega a lista dos últimos 8 acessos registrados."""
        try:
            acessos = self.app.banco.listar_acessos(8)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._definir_faixa(f"Falha ao ler o log de acessos: {e}", tema.VERMELHO, tema.TEXTO)
            return
        self.tabela.limpar()
        for a in acessos:
            hora = a.data_hora[11:19] if len(a.data_hora) >= 19 else a.data_hora
            if a.resultado == "CONCEDIDO":
                tag = "ok"
            elif a.resultado == "NEGADO_NIVEL":
                tag = "aviso"
            else:
                tag = "neg"
            self.tabela.adicionar(str(a.id), (
                hora, a.nome_detectado or "-", tema.ROTULO_RESULTADO.get(a.resultado, a.resultado),
                f"N{a.nivel_exigido}", f"{a.similaridade:.2f}" if a.similaridade is not None else "-"), tag)

    # ------------------------------------------------------------------ eventos
    def _ao_escolher_nivel(self, rotulo: str) -> None:
        self.definir_nivel(NIVEL_DO_ROTULO.get(rotulo, self.nivel))

    def _ao_alternar_liveness(self) -> None:
        self.alternar_liveness(bool(self._var_liveness.get()))

    def _ao_alternar_didatico(self) -> None:
        self.alternar_didatico(bool(self._var_didatico.get()))

    def _tecla(self, evento) -> None:
        """Atalhos: 1/2/3 área, l prova de vida, d painel didático, r recarregar galeria."""
        if not self._quer_camera or isinstance(getattr(evento, "widget", None), (tk.Entry, tk.Text)):
            return
        ch = (getattr(evento, "char", "") or "").lower()
        if ch in ("1", "2", "3"):
            self.definir_nivel(int(ch))
        elif ch == "l":
            self.alternar_liveness()
        elif ch == "d":
            self.alternar_didatico()
        elif ch == "r":
            self.recarregar_galeria()

    # ------------------------------------------------------------------ painel
    def _atualizar_painel(self, st: dict) -> None:
        estado, d = st["estado"], st.get("decisao")
        if estado == Estado.RESULTADO.value and d:
            cor = tema.COR_RESULTADO.get(d["resultado"], tema.VERMELHO)
            linhas = [tema.ROTULO_RESULTADO.get(d["resultado"], d["resultado"])]
            if d.get("nome"):
                sim = d.get("similaridade")
                linhas.append(f"{d['nome']}" + (f"  ·  similaridade {sim:.2f}" if sim is not None else ""))
            if d.get("mensagem"):
                linhas.append(d["mensagem"])
            self._definir_faixa("\n".join(linhas), cor, tema.FUNDO if cor in (tema.VERDE, tema.LARANJA) else tema.TEXTO)
        elif estado == Estado.BLOQUEADO.value:
            self._definir_faixa(f"TERMINAL BLOQUEADO\nAguarde {st['bloqueado_restante']:.0f} s "
                                f"({config.MAX_TENTATIVAS_FALHAS} negações seguidas)", tema.VERMELHO, tema.TEXTO)
        elif estado == Estado.LIVENESS.value:
            self._definir_faixa(f"PROVA DE VIDA\n{st['liveness_instrucao']}\n{st['liveness_restante']:.0f} s restantes",
                                tema.LARANJA, tema.FUNDO)
        elif estado == Estado.CONFIRMANDO.value:
            self._definir_faixa(f"CONFIRMANDO {int(st['progresso_confirmacao'] * 100)}%\n"
                                f"Mantenha o rosto parado diante da câmera", tema.AZUL, tema.TEXTO)
        else:
            extra = "\nMais de uma pessoa diante do terminal" if st.get("n_rostos", 0) > 1 else \
                ("\n" + st["orientacao"]) if st.get("orientacao") else "\nPosicione-se de frente para a câmera"
            self._definir_faixa("AGUARDANDO" + extra, tema.CARTAO, tema.TEXTO_2)
        self._definir_similaridade(st.get("similaridade"))
        self._configurar(self.cartao_galeria.valor, text=str(st.get("galeria", 0)))
        self._configurar(self.cartao_fps.valor, text=f"{st.get('fps', 0.0):.0f}")

    def _definir_faixa(self, texto: str, cor: str, cor_texto: str) -> None:
        chave = id(self.faixa)
        valores = {"texto": texto, "cor": cor, "cor_texto": cor_texto}
        if self._cache_cfg.get(chave) == valores:
            return
        self._cache_cfg[chave] = valores
        self.faixa.definir(texto, cor, cor_texto)

    def _definir_similaridade(self, sim: float | None) -> None:
        limiar = config.LIMIAR_COSSENO
        if sim is None:
            texto, valor, cor = f"Similaridade  -   ·   limiar {limiar:.2f}", 0.0, tema.BORDA
        else:
            texto = f"Similaridade {sim:.2f}   ·   limiar {limiar:.2f}" + ("  (acima)" if sim >= limiar else "  (abaixo)")
            valor, cor = max(0.0, min(1.0, sim)), (tema.VERDE if sim >= limiar else tema.VERMELHO)
        self._configurar(self.rotulo_similaridade, text=texto)
        chave = id(self.barra_similaridade)
        valores = {"valor": round(valor, 3), "cor": cor}
        if self._cache_cfg.get(chave) != valores:
            self._cache_cfg[chave] = valores
            self.barra_similaridade.configure(progress_color=cor)
            self.barra_similaridade.set(valor)

    def _configurar(self, widget, **kw) -> None:
        chave = id(widget)
        if self._cache_cfg.get(chave) == kw:
            return
        self._cache_cfg[chave] = kw
        widget.configure(**kw)

```

## `cofre/interface/tela_usuarios.py` (386 linhas)

```python
"""Tela "Usuários": lista, busca e administra as pessoas cadastradas no banco.

Toda operação age sobre a linha selecionada na tabela. Depois de qualquer alteração a
tabela e os cartões são recarregados e, se a tela do terminal já existir e expuser
`recarregar_galeria()`, ela é avisada para o reconhecedor refletir a mudança.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from .. import config
from ..banco import Usuario
from . import tema, widgets
from .base import Tela

MARGEM = 24
ESPACO = 12
MINIATURA = 120
MINIATURAS_POR_LINHA = 4

COLUNAS = [
    ("id", "ID", 50),
    ("nome", "Nome", 220),
    ("matricula", "Matrícula", 110),
    ("cargo", "Cargo", 160),
    ("nivel", "Nível", 210),
    ("amostras", "Amostras", 80),
    ("ativo", "Ativo", 70),
    ("cadastro", "Cadastro", 140),
]


def _nivel_texto(nivel: int) -> str:
    return f"{nivel} - {config.NIVEIS.get(nivel, '?')}"


def _data_curta(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return iso or "-"


class TelaUsuarios(Tela):
    TITULO = "Usuários"

    # ------------------------------------------------------------------ construção
    def construir(self) -> None:
        self._usuarios: list[Usuario] = []
        self._amostras: dict[int, int] = {}
        self._selecionado: int | None = None
        self._janela_fotos: ctk.CTkToplevel | None = None
        self._janela_nivel: ctk.CTkToplevel | None = None
        self._precisa_recarregar = True

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        widgets.titulo(self, self.TITULO, "Pessoas autorizadas, nível de acesso e amostras biométricas").grid(
            row=0, column=0, sticky="ew", padx=MARGEM, pady=(MARGEM, ESPACO))

        # Cartões de resumo
        cartoes = ctk.CTkFrame(self, fg_color="transparent")
        cartoes.grid(row=1, column=0, sticky="ew", padx=MARGEM, pady=(0, ESPACO))
        self.cartao_total = widgets.Cartao(cartoes, "Usuários cadastrados", "0")
        self.cartao_ativos = widgets.Cartao(cartoes, "Ativos", "0", cor=tema.VERDE)
        self.cartoes_nivel = {
            n: widgets.Cartao(cartoes, f"Nível {n} - {config.NIVEIS[n]}", "0", cor=tema.COR_NIVEL[n])
            for n in sorted(config.NIVEIS)
        }
        for i, c in enumerate([self.cartao_total, self.cartao_ativos, *self.cartoes_nivel.values()]):
            cartoes.grid_columnconfigure(i, weight=1, uniform="cartao")
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else ESPACO, 0))

        # Busca e ações gerais
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=2, column=0, sticky="ew", padx=MARGEM, pady=(0, ESPACO))
        barra.grid_columnconfigure(0, weight=1)
        self.busca_var = tk.StringVar()
        self.busca_var.trace_add("write", lambda *_: self._filtrar())
        # Sem textvariable: com ela o CTkEntry não mostra o placeholder. A tecla copia o texto para busca_var.
        self.busca = ctk.CTkEntry(barra, placeholder_text="Buscar por nome ou matrícula",
                                  height=36, font=tema.CORPO, fg_color=tema.CARTAO, border_color=tema.BORDA)
        self.busca.grid(row=0, column=0, sticky="ew")
        self.busca.bind("<KeyRelease>", lambda _e: self.busca_var.set(self.busca.get()))
        self.btn_atualizar = widgets.botao_secundario(barra, "Atualizar", self.recarregar, height=36)
        self.btn_atualizar.grid(row=0, column=1, padx=(ESPACO, 0))
        self.btn_novo = widgets.botao(barra, "Novo cadastro", self.novo_cadastro, height=36)
        self.btn_novo.grid(row=0, column=2, padx=(ESPACO, 0))

        # Tabela
        self.tabela = widgets.Tabela(self, COLUNAS, altura=14, ao_selecionar=self._ao_selecionar,
                                     ao_duplo_clique=lambda iid: self.ver_fotos())
        self.tabela.grid(row=3, column=0, sticky="nsew", padx=MARGEM, pady=(0, ESPACO))
        self.tabela.tree.column("id", anchor="center")
        self.tabela.tree.column("amostras", anchor="center")
        self.tabela.tree.column("ativo", anchor="center")

        # Ações sobre a linha selecionada
        acoes = ctk.CTkFrame(self, fg_color="transparent")
        acoes.grid(row=4, column=0, sticky="ew", padx=MARGEM, pady=(0, MARGEM))
        acoes.grid_columnconfigure(4, weight=1)
        self.btn_nivel = widgets.botao_secundario(acoes, "Alterar nível", self.alterar_nivel)
        self.btn_ativo = widgets.botao_secundario(acoes, "Ativar/Desativar", self.ativar_desativar)
        self.btn_fotos = widgets.botao_secundario(acoes, "Ver fotos", self.ver_fotos)
        self.btn_remover = widgets.botao(acoes, "Remover", self.remover, cor=tema.VERMELHO)
        for i, b in enumerate([self.btn_nivel, self.btn_ativo, self.btn_fotos, self.btn_remover]):
            b.grid(row=0, column=i, padx=(0 if i == 0 else ESPACO, 0))
        self.mensagem = ctk.CTkLabel(acoes, text="", font=tema.CORPO, text_color=tema.TEXTO_2, anchor="e",
                                     wraplength=520, justify="right")
        self.mensagem.grid(row=0, column=4, sticky="ew", padx=(ESPACO, 0))
        self._atualizar_botoes()

    # ------------------------------------------------------------------ ciclo da tela
    def ao_mostrar(self) -> None:
        self._precisa_recarregar = True

    def ao_esconder(self) -> None:
        self._fechar_janelas()

    def atualizar(self) -> None:
        if self._precisa_recarregar:
            self._precisa_recarregar = False
            self.recarregar()

    # ------------------------------------------------------------------ dados
    def recarregar(self) -> None:
        """Relê o banco e redesenha cartões e tabela (mantém a seleção quando possível)."""
        try:
            self._usuarios = self.app.banco.listar_usuarios()
            self._amostras = {u.id: self.app.banco.contar_amostras(u.id) for u in self._usuarios}
        except Exception as e:  # noqa: BLE001
            self._usuarios, self._amostras = [], {}
            self._avisar(f"Falha ao ler o banco: {e}", erro=True)
        self._preencher_cartoes()
        self._filtrar()

    def _preencher_cartoes(self) -> None:
        self.cartao_total.definir(len(self._usuarios))
        self.cartao_ativos.definir(sum(1 for u in self._usuarios if u.ativo))
        for n, c in self.cartoes_nivel.items():
            c.definir(sum(1 for u in self._usuarios if u.nivel == n))

    def _filtrar(self) -> None:
        termo = self.busca_var.get().strip().casefold()
        anterior = self._selecionado
        self.tabela.limpar()
        for u in self._usuarios:
            if termo and termo not in u.nome.casefold() and termo not in u.matricula.casefold():
                continue
            self.tabela.adicionar(str(u.id), [
                u.id, u.nome, u.matricula, u.cargo or "-", _nivel_texto(u.nivel),
                self._amostras.get(u.id, 0), "Sim" if u.ativo else "Não", _data_curta(u.criado_em),
            ], tag=None if u.ativo else "inativo")
        self._selecionado = None
        if anterior is not None and self.tabela.tree.exists(str(anterior)):
            self.tabela.tree.selection_set(str(anterior))
            self._selecionado = anterior
        self._atualizar_botoes()

    def _ao_selecionar(self, iid: str) -> None:
        try:
            self._selecionado = int(iid)
        except ValueError:
            self._selecionado = None
        self._atualizar_botoes()

    def _atualizar_botoes(self) -> None:
        estado = "normal" if self._selecionado is not None else "disabled"
        for b in (self.btn_nivel, self.btn_ativo, self.btn_fotos, self.btn_remover):
            b.configure(state=estado)

    def usuario_selecionado(self) -> Usuario | None:
        """Usuário da linha selecionada (relido do banco, para não agir sobre dado velho)."""
        if self._selecionado is None:
            return None
        try:
            u = self.app.banco.obter_usuario(self._selecionado)
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Falha ao ler o usuário: {e}", erro=True)
            return None
        if u is None:
            self._avisar("O usuário selecionado não existe mais.", erro=True)
            self.recarregar()
        return u

    # ------------------------------------------------------------------ ações
    def novo_cadastro(self) -> None:
        self.app.mostrar("tela_cadastro")

    def alterar_nivel(self, nivel: int | None = None) -> None:
        """Abre o diálogo com os 3 níveis; com `nivel` informado aplica direto (sem diálogo)."""
        u = self.usuario_selecionado()
        if u is None:
            return
        if nivel is None:
            self._dialogo_nivel(u)
            return
        if nivel == u.nivel:
            self._avisar(f"{u.nome} já está no nível {nivel}.")
            return
        try:
            self.app.banco.alterar_nivel(u.id, int(nivel))
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Não foi possível alterar o nível: {e}", erro=True)
            return
        self._apos_alteracao(f"{u.nome}: nível alterado para {_nivel_texto(int(nivel))}.")

    def ativar_desativar(self) -> None:
        u = self.usuario_selecionado()
        if u is None:
            return
        try:
            self.app.banco.definir_ativo(u.id, not u.ativo)
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Não foi possível alterar o status: {e}", erro=True)
            return
        self._apos_alteracao(f"{u.nome} {'reativado' if not u.ativo else 'desativado'}.")

    def remover(self) -> None:
        u = self.usuario_selecionado()
        if u is None:
            return
        n = self._amostras.get(u.id, 0)
        if not messagebox.askyesno(
                "Remover usuário",
                f"Remover {u.nome} (matrícula {u.matricula})?\n\n"
                f"As {n} amostras biométricas serão apagadas do banco. Esta ação não pode ser desfeita.",
                icon="warning", parent=self.winfo_toplevel()):
            return
        try:
            self.app.banco.remover_usuario(u.id)
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Não foi possível remover: {e}", erro=True)
            return
        self._selecionado = None
        self._apos_alteracao(f"{u.nome} removido do banco.")

    def ver_fotos(self) -> None:
        u = self.usuario_selecionado()
        if u is None:
            return
        try:
            caminhos = self.app.banco.fotos_do_usuario(u.id)
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Não foi possível listar as fotos: {e}", erro=True)
            return
        self._fechar_janela_fotos()
        self._janela_fotos = self._montar_janela_fotos(u, caminhos)

    def _apos_alteracao(self, texto: str) -> None:
        self._avisar(texto)
        self.recarregar()
        self._avisar_terminal()

    def _avisar_terminal(self) -> None:
        """Pede ao terminal (se já instanciado) que recarregue a galeria do reconhecedor."""
        try:
            terminal = self.app.tela("tela_terminal")
            fn = getattr(terminal, "recarregar_galeria", None)
            if callable(fn):
                fn()
        except Exception as e:  # noqa: BLE001
            self._avisar(f"Alteração salva, mas o terminal não recarregou a galeria: {e}", erro=True)

    def _avisar(self, texto: str, erro: bool = False) -> None:
        self.mensagem.configure(text=texto, text_color=tema.VERMELHO if erro else tema.TEXTO_2)

    # ------------------------------------------------------------------ janelas auxiliares
    def _nova_janela(self, titulo: str, largura: int, altura: int) -> ctk.CTkToplevel:
        jan = ctk.CTkToplevel(self, fg_color=tema.FUNDO)
        jan.title(titulo)
        raiz = self.winfo_toplevel()
        x = raiz.winfo_rootx() + max(0, (raiz.winfo_width() - largura) // 2)
        y = raiz.winfo_rooty() + max(0, (raiz.winfo_height() - altura) // 2)
        jan.geometry(f"{largura}x{altura}+{x}+{y}")
        jan.transient(raiz)
        return jan

    def _dialogo_nivel(self, u: Usuario) -> None:
        self._fechar_janela_nivel()
        jan = self._nova_janela("Alterar nível de acesso", 460, 300)
        self._janela_nivel = jan
        ctk.CTkLabel(jan, text=f"Nível de acesso de {u.nome}", font=tema.SUBTITULO, text_color=tema.TEXTO,
                     anchor="w").pack(fill="x", padx=MARGEM, pady=(MARGEM, 4))
        ctk.CTkLabel(jan, text=f"Atual: {_nivel_texto(u.nivel)}", font=tema.PEQUENO, text_color=tema.TEXTO_2,
                     anchor="w").pack(fill="x", padx=MARGEM, pady=(0, ESPACO))
        var = tk.IntVar(master=jan, value=u.nivel)
        for n in sorted(config.NIVEIS):
            ctk.CTkRadioButton(jan, text=f"{_nivel_texto(n)}  (acesso: {config.AREAS.get(n, '')})",
                               variable=var, value=n, font=tema.CORPO, fg_color=tema.COR_NIVEL[n],
                               hover_color=tema.COR_NIVEL[n]).pack(anchor="w", padx=MARGEM, pady=4)
        rodape = ctk.CTkFrame(jan, fg_color="transparent")
        rodape.pack(fill="x", side="bottom", padx=MARGEM, pady=MARGEM)

        def confirmar() -> None:
            nivel = var.get()
            self._fechar_janela_nivel()
            self.alterar_nivel(nivel)

        widgets.botao(rodape, "Salvar", confirmar).pack(side="right")
        widgets.botao_secundario(rodape, "Cancelar", self._fechar_janela_nivel).pack(side="right", padx=(0, ESPACO))
        jan.protocol("WM_DELETE_WINDOW", self._fechar_janela_nivel)
        jan.bind("<Escape>", lambda e: self._fechar_janela_nivel())
        jan.bind("<Return>", lambda e: confirmar())
        jan.after(50, lambda: self._focar(jan))

    def _montar_janela_fotos(self, u: Usuario, caminhos: list[str]) -> ctk.CTkToplevel:
        largura = MINIATURAS_POR_LINHA * (MINIATURA + ESPACO) + 2 * MARGEM + 24
        jan = self._nova_janela(f"Fotos de {u.nome}", largura, 560)
        ctk.CTkLabel(jan, text=f"{u.nome}  -  matrícula {u.matricula}", font=tema.SUBTITULO, text_color=tema.TEXTO,
                     anchor="w").pack(fill="x", padx=MARGEM, pady=(MARGEM, 0))
        ctk.CTkLabel(jan, text=f"{len(caminhos)} foto(s) de referência em {config.FOTOS_DIR}", font=tema.PEQUENO,
                     text_color=tema.TEXTO_2, anchor="w", wraplength=largura - 2 * MARGEM,
                     justify="left").pack(fill="x", padx=MARGEM, pady=(0, ESPACO))
        area = ctk.CTkScrollableFrame(jan, fg_color=tema.FUNDO_2, corner_radius=10)
        area.pack(fill="both", expand=True, padx=MARGEM, pady=(0, ESPACO))
        jan.miniaturas = []  # referência viva das imagens (o Tk não as retém)
        if not caminhos:
            ctk.CTkLabel(area, text="Este usuário não tem fotos de referência salvas.", font=tema.CORPO,
                         text_color=tema.TEXTO_2).pack(padx=ESPACO, pady=ESPACO)
        for i, caminho in enumerate(caminhos):
            celula = ctk.CTkFrame(area, fg_color=tema.CARTAO, corner_radius=8, width=MINIATURA + 8)
            celula.grid(row=i // MINIATURAS_POR_LINHA, column=i % MINIATURAS_POR_LINHA, padx=ESPACO // 2,
                        pady=ESPACO // 2, sticky="n")
            img = self._miniatura(caminho)
            if img is None:
                ctk.CTkLabel(celula, text="arquivo\nnão encontrado", font=tema.PEQUENO, text_color=tema.VERMELHO,
                             width=MINIATURA, height=MINIATURA).pack(padx=4, pady=(4, 0))
            else:
                jan.miniaturas.append(img)
                ctk.CTkLabel(celula, text="", image=img, width=MINIATURA, height=MINIATURA).pack(padx=4, pady=(4, 0))
            ctk.CTkLabel(celula, text=Path(caminho).name, font=tema.PEQUENO, text_color=tema.TEXTO_2,
                         width=MINIATURA, wraplength=MINIATURA).pack(padx=4, pady=(2, 4))
        widgets.botao_secundario(jan, "Fechar", self._fechar_janela_fotos).pack(side="bottom", anchor="e",
                                                                                 padx=MARGEM, pady=(0, MARGEM))
        jan.protocol("WM_DELETE_WINDOW", self._fechar_janela_fotos)
        jan.bind("<Escape>", lambda e: self._fechar_janela_fotos())
        jan.after(50, lambda: self._focar(jan))
        return jan

    @staticmethod
    def _miniatura(caminho: str) -> ctk.CTkImage | None:
        try:
            with Image.open(caminho) as im:
                im = im.convert("RGB")
                im.thumbnail((MINIATURA, MINIATURA))
                return ctk.CTkImage(im.copy(), size=im.size)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _focar(jan: ctk.CTkToplevel) -> None:
        try:
            if jan.winfo_exists():
                jan.lift()
                jan.focus_force()
        except tk.TclError:
            pass

    def _fechar_janela_fotos(self) -> None:
        jan, self._janela_fotos = self._janela_fotos, None
        if jan is not None:
            try:
                jan.destroy()
            except tk.TclError:
                pass

    def _fechar_janela_nivel(self) -> None:
        jan, self._janela_nivel = self._janela_nivel, None
        if jan is not None:
            try:
                jan.destroy()
            except tk.TclError:
                pass

    def _fechar_janelas(self) -> None:
        self._fechar_janela_fotos()
        self._fechar_janela_nivel()

```

## `cofre/interface/tema.py` (66 linhas)

```python
"""Cores, fontes e utilitários visuais do aplicativo."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

# Paleta (hex) - fundo escuro, acento verde-água institucional
FUNDO = "#0f1419"
FUNDO_2 = "#161c24"
CARTAO = "#1d2530"
BORDA = "#2a3440"
TEXTO = "#e6edf3"
TEXTO_2 = "#8b98a5"
ACENTO = "#2bb0a0"
ACENTO_HOVER = "#239184"
VERDE = "#2ecc71"
VERMELHO = "#e74c3c"
AMARELO = "#f1c40f"
LARANJA = "#f39c12"
AZUL = "#3498db"

FONTE = "Helvetica"
TITULO = (FONTE, 22, "bold")
SUBTITULO = (FONTE, 15, "bold")
CORPO = (FONTE, 13)
PEQUENO = (FONTE, 11)
MONO = ("Menlo", 12)

COR_RESULTADO = {
    "CONCEDIDO": VERDE,
    "NEGADO_NIVEL": LARANJA,
    "NEGADO_DESCONHECIDO": VERMELHO,
    "NEGADO_LIVENESS": VERMELHO,
    "NEGADO_MULTIPLOS": VERMELHO,
    "BLOQUEADO": VERMELHO,
}

ROTULO_RESULTADO = {
    "CONCEDIDO": "Acesso concedido",
    "NEGADO_NIVEL": "Negado: nível insuficiente",
    "NEGADO_DESCONHECIDO": "Negado: não cadastrado",
    "NEGADO_LIVENESS": "Negado: prova de vida",
    "NEGADO_MULTIPLOS": "Negado: mais de uma pessoa",
    "BLOQUEADO": "Terminal bloqueado",
}

COR_NIVEL = {1: AZUL, 2: LARANJA, 3: VERMELHO}


def bgr_para_pil(img: np.ndarray) -> Image.Image:
    """Converte um frame BGR/cinza do OpenCV em imagem PIL (RGB)."""
    if img.ndim == 2:
        return Image.fromarray(img)
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def ajustar(img: np.ndarray, largura: int, altura: int) -> np.ndarray:
    """Redimensiona mantendo a proporção para caber em largura x altura."""
    h, w = img.shape[:2]
    if w == 0 or h == 0 or largura <= 1 or altura <= 1:
        return img
    esc = min(largura / w, altura / h)
    return cv2.resize(img, (max(1, int(w * esc)), max(1, int(h * esc))),
                      interpolation=cv2.INTER_AREA if esc < 1 else cv2.INTER_LINEAR)

```

## `cofre/interface/widgets.py` (179 linhas)

```python
"""Widgets reutilizáveis do aplicativo."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence

import customtkinter as ctk
import numpy as np

from . import tema


class VideoWidget(ctk.CTkLabel):
    """Exibe frames BGR do OpenCV, ajustando à área disponível."""

    def __init__(self, master, largura=640, altura=360, **kw):
        super().__init__(master, text="", fg_color=tema.FUNDO, corner_radius=8, **kw)
        self._largura, self._altura = largura, altura
        self._img: ctk.CTkImage | None = None
        self.configure(width=largura, height=altura)
        self.mensagem("Câmera desligada")

    def mostrar(self, frame: np.ndarray | None) -> None:
        if frame is None:
            return
        w = max(self.winfo_width(), 2)
        h = max(self.winfo_height(), 2)
        if w < 50 or h < 50:
            w, h = self._largura, self._altura
        red = tema.ajustar(frame, w - 4, h - 4)
        pil = tema.bgr_para_pil(red)
        self._img = ctk.CTkImage(pil, size=(red.shape[1], red.shape[0]))
        self.configure(image=self._img, text="")

    def mensagem(self, texto: str) -> None:
        self._img = None
        self.configure(image=None, text=texto, font=tema.SUBTITULO, text_color=tema.TEXTO_2)


class Cartao(ctk.CTkFrame):
    """Cartão com valor grande e rótulo pequeno (estatísticas)."""

    def __init__(self, master, rotulo: str, valor: str = "-", cor: str = tema.TEXTO, **kw):
        super().__init__(master, fg_color=tema.CARTAO, corner_radius=10, **kw)
        self.valor = ctk.CTkLabel(self, text=valor, font=(tema.FONTE, 26, "bold"), text_color=cor)
        self.valor.pack(padx=16, pady=(12, 0))
        self.rotulo = ctk.CTkLabel(self, text=rotulo, font=tema.PEQUENO, text_color=tema.TEXTO_2, justify="center")
        self.rotulo.pack(padx=16, pady=(0, 12))
        self.bind("<Configure>", self._ajustar_rotulo, add="+")

    def _ajustar_rotulo(self, evento) -> None:
        # Rótulos longos ("Nível 3 - Ministro do Meio Ambiente") quebram em vez de sair cortados.
        self.rotulo.configure(wraplength=max(60, evento.width - 32))

    def definir(self, valor, cor: str | None = None) -> None:
        self.valor.configure(text=str(valor), **({"text_color": cor} if cor else {}))


class Faixa(ctk.CTkFrame):
    """Faixa colorida de status com texto (veredito, instrução, aviso)."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=tema.CARTAO, corner_radius=10, height=64, **kw)
        self.pack_propagate(False)
        self.texto = ctk.CTkLabel(self, text="", font=(tema.FONTE, 16, "bold"), text_color=tema.TEXTO,
                                  wraplength=900, justify="left")
        self.texto.pack(fill="both", expand=True, padx=16, pady=8)

    def definir(self, texto: str, cor: str = tema.CARTAO, cor_texto: str = tema.TEXTO) -> None:
        self.configure(fg_color=cor)
        self.texto.configure(text=texto, text_color=cor_texto)


def estilo_tabela_escura() -> None:
    """Aplica tema escuro ao ttk.Treeview (uma vez por aplicativo)."""
    st = ttk.Style()
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure("Escura.Treeview", background=tema.CARTAO, fieldbackground=tema.CARTAO, foreground=tema.TEXTO,
                 rowheight=28, borderwidth=0, font=tema.CORPO, bordercolor=tema.CARTAO,
                 lightcolor=tema.CARTAO, darkcolor=tema.CARTAO)
    # O tema clam desenha uma moldura clara em volta do Treeview; o layout abaixo deixa só a área das linhas.
    st.layout("Escura.Treeview", [("Escura.Treeview.treearea", {"sticky": "nswe"})])
    st.configure("Escura.Treeview.Heading", background=tema.FUNDO_2, foreground=tema.TEXTO_2, relief="flat",
                 font=(tema.FONTE, 12, "bold"))
    st.map("Escura.Treeview", background=[("selected", tema.ACENTO)], foreground=[("selected", tema.FUNDO)])
    st.map("Escura.Treeview.Heading", background=[("active", tema.BORDA)])


class Tabela(ctk.CTkFrame):
    """ttk.Treeview com tema escuro, barra de rolagem e API simples."""

    def __init__(self, master, colunas: Sequence[tuple[str, str, int]], altura: int = 12,
                 ao_selecionar: Callable[[str], None] | None = None,
                 ao_duplo_clique: Callable[[str], None] | None = None,
                 rolagem_horizontal: bool = False, **kw):
        """colunas: lista de (id, título, largura_px). Com `rolagem_horizontal`, as colunas mantêm
        a largura dada e o que não couber fica acessível pela barra horizontal."""
        super().__init__(master, fg_color=tema.CARTAO, corner_radius=10, **kw)
        estilo_tabela_escura()
        ids = [c[0] for c in colunas]
        self.tree = ttk.Treeview(self, columns=ids, show="headings", height=altura, style="Escura.Treeview",
                                 selectmode="browse")
        for cid, titulo, larg in colunas:
            self.tree.heading(cid, text=titulo)
            self.tree.column(cid, width=larg, minwidth=40, anchor="w", stretch=not rolagem_horizontal)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        barra = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=barra.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 0 if rolagem_horizontal else 8))
        barra.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=8)
        if rolagem_horizontal:
            barra_h = ctk.CTkScrollbar(self, orientation="horizontal", command=self.tree.xview)
            self.tree.configure(xscrollcommand=barra_h.set)
            barra_h.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=(0, 4))
        self.tree.tag_configure("ok", foreground=tema.VERDE)
        self.tree.tag_configure("neg", foreground=tema.VERMELHO)
        self.tree.tag_configure("aviso", foreground=tema.LARANJA)
        self.tree.tag_configure("inativo", foreground=tema.TEXTO_2)
        if ao_selecionar:
            self.tree.bind("<<TreeviewSelect>>", lambda e: self._emitir(ao_selecionar))
        if ao_duplo_clique:
            self.tree.bind("<Double-1>", lambda e: self._emitir(ao_duplo_clique))

    def _emitir(self, fn):
        sel = self.tree.selection()
        if sel:
            fn(sel[0])

    def limpar(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def adicionar(self, iid: str, valores: Sequence, tag: str | None = None) -> None:
        self.tree.insert("", "end", iid=iid, values=list(valores), tags=(tag,) if tag else ())

    def selecionado(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None


class BarraStatus(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=tema.FUNDO_2, corner_radius=0, height=28, **kw)
        self.pack_propagate(False)
        self.esq = ctk.CTkLabel(self, text="", font=tema.PEQUENO, text_color=tema.TEXTO_2)
        self.esq.pack(side="left", padx=12)
        self.dir = ctk.CTkLabel(self, text="", font=tema.PEQUENO, text_color=tema.TEXTO_2)
        self.dir.pack(side="right", padx=12)

    def definir(self, esquerda: str | None = None, direita: str | None = None) -> None:
        if esquerda is not None:
            self.esq.configure(text=esquerda)
        if direita is not None:
            self.dir.configure(text=direita)


def titulo(master, texto: str, subtitulo: str | None = None) -> ctk.CTkFrame:
    f = ctk.CTkFrame(master, fg_color="transparent")
    ctk.CTkLabel(f, text=texto, font=tema.TITULO, text_color=tema.TEXTO, anchor="w").pack(fill="x")
    if subtitulo:
        ctk.CTkLabel(f, text=subtitulo, font=tema.CORPO, text_color=tema.TEXTO_2, anchor="w").pack(fill="x")
    return f


def botao(master, texto: str, comando, cor: str | None = None, **kw) -> ctk.CTkButton:
    extra = {"fg_color": cor, "hover_color": cor} if cor else {"fg_color": tema.ACENTO, "hover_color": tema.ACENTO_HOVER}
    return ctk.CTkButton(master, text=texto, command=comando, font=tema.CORPO, corner_radius=8,
                         text_color=tema.FUNDO if not cor else tema.TEXTO, **extra, **kw)


def botao_secundario(master, texto: str, comando, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=texto, command=comando, font=tema.CORPO, corner_radius=8,
                         fg_color=tema.CARTAO, hover_color=tema.BORDA, border_width=1, border_color=tema.BORDA,
                         text_color=tema.TEXTO, **kw)

```

## `cofre/qt/__init__.py` (13 linhas)

```python
"""Interface desktop em PySide6 + Qt Quick (QML).

Camadas:
  qml/Cofre/Ui/        telas e componentes visuais (só apresentação, nenhuma regra de negócio)
  vm_*.py              ViewModels: estado das telas exposto ao QML por propriedades e slots
  camera.py            captura em QThread; entrega só o último quadro (sem fila acumulando)
  video.py             componente de vídeo desenhado com QPainter (quadro + marcações do rosto)
  tarefas.py           trabalho pesado fora da thread da interface, com resultado via sinal
  modelos.py           modelos de lista genéricos para tabelas e listas do QML

A lógica (pipeline, máquina de estados do terminal, cadastro, banco, relatórios) continua
no pacote `cofre` e é a mesma usada pela linha de comando e pela interface customtkinter.
"""

```

## `cofre/qt/aplicacao.py` (201 linhas)

```python
"""
Controlador do aplicativo Qt: banco, pipeline (carregado em segundo plano), câmera,
tarefas, navegação entre páginas e notificações. Os ViewModels ficam pendurados aqui
e o QML os acessa por `app.terminal`, `app.cadastro` etc.
"""

from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, Signal, Slot

from .. import __version__, config
from ..banco import Banco
from .camera import ServicoCamera
from .imagens import criar_provedor
from .tarefas import Tarefas
from .vm_acessos import AcessosVM
from .vm_avaliacao import AvaliacaoVM
from .vm_cadastro import CadastroVM
from .vm_config import ConfigVM
from .vm_sessao import SessaoVM
from .vm_terminal import TerminalVM
from .vm_usuarios import UsuariosVM

PAGINAS = ("terminal", "cadastro", "usuarios", "acessos", "avaliacao", "config")


class Aplicacao(QObject):
    paginaMudou = Signal()
    modelosProntosMudou = Signal()
    erroModelosMudou = Signal()
    notificacao = Signal(str, str)          # (tipo: ok | info | aviso | erro, texto)
    encerrando = Signal()                   # o QML descarrega as páginas antes do motor ser destruído

    def __init__(self, caminho_db=config.DB_PATH, fonte_camera: Callable[[], Any] | None = None,
                 carregar_modelos: bool = True, parent=None):
        super().__init__(parent)
        self.banco = Banco(caminho_db)
        self.camera = ServicoCamera(fonte_camera, self)
        self.tarefas = Tarefas(self)
        self.imagens = criar_provedor()
        self.pipeline = None
        self._pagina = ""
        self._erro_modelos = ""
        self._fechado = False
        self.config_vm = ConfigVM(self, self)
        self.config_vm.carregar_inicial()           # aplica o config_usuario.json, se existir
        self.terminal_vm = TerminalVM(self, self)
        self.cadastro_vm = CadastroVM(self, self)
        self.usuarios_vm = UsuariosVM(self, self)
        self.acessos_vm = AcessosVM(self, self)
        self.avaliacao_vm = AvaliacaoVM(self, self)
        self.sessao_vm = SessaoVM(self, self)
        self.sessao_vm.aberta.connect(self._sessao_aberta)
        self.sessao_vm.encerrada.connect(self._sessao_encerrada)
        self._vms = {"terminal": self.terminal_vm, "cadastro": self.cadastro_vm, "usuarios": self.usuarios_vm,
                     "acessos": self.acessos_vm, "avaliacao": self.avaliacao_vm, "config": self.config_vm}
        self.config_vm.configAplicada.connect(self.terminal_vm.similaridadeMudou)   # o limiar exibido muda
        if carregar_modelos:
            self.carregar_modelos()

    # ------------------------------------------------------------------ modelos
    def carregar_modelos(self) -> None:
        def carregar():
            from ..pipeline import Pipeline
            return Pipeline()

        def pronto(pipeline, erro: str) -> None:
            if erro:
                self._erro_modelos = f"Falha ao carregar os modelos: {erro}"
                self.erroModelosMudou.emit()
                self.notificar("erro", self._erro_modelos)
                return
            self.usar_pipeline(pipeline)

        self.tarefas.executar(carregar, pronto)

    def usar_pipeline(self, pipeline) -> None:
        """Instala o pipeline carregado e avisa as páginas (os testes passam um já pronto)."""
        self.pipeline = pipeline
        self.modelosProntosMudou.emit()
        for vm in self._vms.values():
            try:
                vm.ao_pipeline_pronto()
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    def _get_modelos_prontos(self) -> bool:
        return self.pipeline is not None

    def _get_erro_modelos(self) -> str:
        return self._erro_modelos

    modelosProntos = Property(bool, _get_modelos_prontos, notify=modelosProntosMudou)
    erroModelos = Property(str, _get_erro_modelos, notify=erroModelosMudou)

    # ------------------------------------------------------------------ navegação
    def _get_pagina(self) -> str:
        return self._pagina

    pagina = Property(str, _get_pagina, notify=paginaMudou)

    @Slot(str)
    def navegar(self, pagina: str) -> None:
        if pagina not in PAGINAS or pagina == self._pagina or self.sessao_vm.ativa:
            return      # com a área liberada aberta a navegação fica travada até encerrar a sessão
        anterior = self._vms.get(self._pagina)
        if anterior is not None:
            try:
                anterior.desativar()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        self._pagina = pagina
        self.paginaMudou.emit()
        try:
            self._vms[pagina].ativar()
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.notificar("erro", f"Falha ao abrir a página: {e}")

    # ------------------------------------------------------------------ área liberada
    def _sessao_aberta(self) -> None:
        self.terminal_vm.pausar()        # câmera desligada enquanto a área está aberta

    def _sessao_encerrada(self, motivo: str) -> None:
        if self._pagina == "terminal":
            self.terminal_vm.retomar()

    # ------------------------------------------------------------------ eventos entre páginas
    def banco_alterado(self, origem=None) -> None:
        """Usuários, amostras ou log mudaram: recarrega a galeria do terminal e as listas abertas."""
        for vm in self._vms.values():
            if vm is origem:
                continue
            try:
                vm.ao_banco_alterado()
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    @Slot(str, str)
    def notificar(self, tipo: str, texto: str) -> None:
        self.notificacao.emit(tipo, texto)

    # ------------------------------------------------------------------ acesso pelo QML
    def _vm(nome):  # noqa: N805 (fábrica de propriedades)
        return Property(QObject, lambda self: self._vms[nome], constant=True)

    terminal = _vm("terminal")
    cadastro = _vm("cadastro")
    usuarios = _vm("usuarios")
    acessos = _vm("acessos")
    avaliacao = _vm("avaliacao")
    configuracoes = _vm("config")
    del _vm

    def _get_sessao(self):
        return self.sessao_vm

    sessao = Property(QObject, _get_sessao, constant=True)

    def _get_camera(self):
        return self.camera

    def _get_tarefas(self):
        return self.tarefas

    cameraServico = Property(QObject, _get_camera, constant=True)
    tarefasServico = Property(QObject, _get_tarefas, constant=True)

    @Slot(result=str)
    def versao(self) -> str:
        return __version__

    @Slot(result=str)
    def nomeBanco(self) -> str:
        return getattr(self.banco.caminho, "name", str(self.banco.caminho))

    @Slot(result="QVariantList")
    def niveis(self) -> list:
        return [{"nivel": n, "descricao": config.NIVEIS[n], "area": config.AREAS[n]} for n in sorted(config.NIVEIS)]

    # ------------------------------------------------------------------ encerramento
    def fechar(self) -> None:
        if self._fechado:
            return
        self._fechado = True
        self.encerrando.emit()
        vm = self._vms.get(self._pagina)
        try:
            self.sessao_vm.encerrar()
            if vm is not None:
                vm.desativar()
            if self.cadastro_vm.capturando:
                self.cadastro_vm.cancelar()      # cadastro pela metade não fica no banco
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        self.camera.parar()
        self.tarefas.esperar(5000)
        self.banco.fechar()

```

## `cofre/qt/app.py` (82 linhas)

```python
"""Inicialização do aplicativo Qt Quick: QGuiApplication, estilo, tipos nativos e QML."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuickControls2 import QQuickStyle

from .. import config
from .aplicacao import Aplicacao
from .video import VisorVideo

DIR_QML = Path(__file__).resolve().parent / "qml"
ARQUIVO_MAIN = DIR_QML / "Cofre" / "Ui" / "Main.qml"

_registrado = False


def registrar_tipos() -> None:
    global _registrado
    if not _registrado:
        qmlRegisterType(VisorVideo, "Cofre.Nativo", 1, 0, "VisorVideo")
        _registrado = True


def preparar_qt(argv: list[str] | None = None) -> QGuiApplication:
    """Cria (ou reaproveita) a QGuiApplication com o estilo e a fonte do aplicativo."""
    QQuickStyle.setStyle("Basic")            # estilo neutro, totalmente personalizado pelo Theme.qml
    app = QGuiApplication.instance() or QGuiApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Cofre MMA")
    app.setOrganizationName("APS PIVC")
    app.setApplicationDisplayName("Cofre MMA")
    fonte = QFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))
    fonte.setPixelSize(13)
    fonte.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(fonte)
    registrar_tipos()
    return app


def criar_motor(aplicacao: Aplicacao, avisos: list[str] | None = None) -> QQmlApplicationEngine:
    """Carrega o Main.qml. Avisos do QML vão para `avisos` (os testes falham se houver algum)."""
    motor = QQmlApplicationEngine()
    motor.addImageProvider("cofre", aplicacao.imagens)
    motor.addImportPath(str(DIR_QML))
    motor.rootContext().setContextProperty("app", aplicacao)
    if avisos is not None:
        motor.warnings.connect(lambda lista: avisos.extend(w.toString() for w in lista))
    motor.load(QUrl.fromLocalFile(str(ARQUIVO_MAIN)))
    return motor


def destruir_motor(motor: QQmlApplicationEngine) -> None:
    """Destrói a janela antes do motor: assim nenhum vínculo do QML é reavaliado com `app` nulo."""
    for obj in motor.rootObjects():
        obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    motor.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def executar(caminho_db=config.DB_PATH, fonte_camera: Callable[[], Any] | None = None) -> int:
    app = preparar_qt()
    icone = config.BASE_DIR / "docs" / "icone.png"
    if icone.exists():
        app.setWindowIcon(QIcon(str(icone)))
    aplicacao = Aplicacao(caminho_db, fonte_camera)
    motor = criar_motor(aplicacao)
    if not motor.rootObjects():
        print("Falha ao carregar a interface QML (veja as mensagens acima).", file=sys.stderr)
        aplicacao.fechar()
        return 1
    app.aboutToQuit.connect(aplicacao.fechar)
    aplicacao.navegar("terminal")
    codigo = app.exec()
    destruir_motor(motor)
    return codigo

```

## `cofre/qt/base.py` (58 linhas)

```python
"""Apoio aos ViewModels: propriedades observáveis pelo QML sem repetição de código.

Cada ViewModel guarda o estado em `self._v` e declara, no corpo da classe:

    estadoMudou = Signal()
    estado = prop(str, "estado", estadoMudou)

`self._definir("estado", valor)` só emite o sinal quando o valor muda de fato, o que
evita reavaliar bindings do QML a cada quadro da câmera sem necessidade.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal


def objeto(atributo: str) -> Property:
    """Expõe ao QML um objeto Python guardado em `self.<atributo>` (modelos, fontes de vídeo)."""
    return Property(QObject, lambda self: getattr(self, atributo), constant=True)


def prop(tipo: Any, nome: str, sinal: Signal) -> Property:
    """Propriedade somente leitura do QML ligada a `self._v[nome]`."""
    return Property(tipo, lambda self: self._v[nome], notify=sinal)


class ViewModel(QObject):
    """Base: estado em dicionário, emissão só quando muda e ganchos de ativação de página."""

    def __init__(self, aplicacao=None, parent: QObject | None = None):
        super().__init__(parent)
        self.app = aplicacao
        self._v: dict[str, Any] = {}

    def _definir(self, nome: str, valor: Any) -> bool:
        if nome in self._v and self._v[nome] == valor:
            return False
        self._v[nome] = valor
        getattr(self, nome + "Mudou").emit()
        return True

    def _iniciar(self, **valores: Any) -> None:
        self._v.update(valores)

    # Ganchos chamados pela Aplicacao quando a página aparece / some / os modelos carregam.
    def ativar(self) -> None:
        pass

    def desativar(self) -> None:
        pass

    def ao_pipeline_pronto(self) -> None:
        pass

    def ao_banco_alterado(self) -> None:
        """Outro ponto do aplicativo (ou outro processo) gravou no banco."""

```

## `cofre/qt/camera.py` (213 linhas)

```python
"""
Câmera em QThread, entregando à interface só o quadro mais recente.

Fluxo:
  thread da câmera:  lê o quadro -> roda o `processador(frame)` (parte cara: pipeline,
                     conversão para QImage) -> guarda o pacote e avisa por sinal
  thread da interface: recebe `quadroDisponivel`, pega o pacote com `ultimo()`

Se a interface atrasar, os quadros antigos são descartados (não há fila crescendo).
Cada abertura recebe um número de "geração"; avisos de uma thread antiga que ainda
esteja terminando são ignorados.

No macOS o dispositivo é criado na thread principal (`FonteCamera.preparar`): é a
única forma de o sistema mostrar o pedido de permissão da câmera.
"""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot

from .. import config
from ..fase1_aquisicao import ErroAquisicao, FonteCamera

DESLIGADA, ABRINDO, ATIVA, ERRO = "desligada", "abrindo", "ativa", "erro"


def fabrica_padrao() -> FonteCamera:
    """Lê índice e espelhamento de `config` a cada abertura (a tela de configurações pode mudar)."""
    return FonteCamera(config.CAMERA_INDEX, config.ESPELHAR_CAMERA)


@dataclass
class Pacote:
    frame: Any
    saida: Any
    seq: int
    fps: float


class _ThreadCaptura(QThread):
    def __init__(self, fonte, servico: "ServicoCamera", geracao: int):
        super().__init__()
        self.fonte, self.servico, self.geracao = fonte, servico, geracao
        self.setObjectName(f"camera-{geracao}")

    def run(self) -> None:
        s, g = self.servico, self.geracao
        try:
            with self.fonte as cam:
                s._sinalAberta.emit(g)
                for frame in cam.frames():
                    if self.isInterruptionRequested():
                        break
                    proc = s._processador
                    erro = ""
                    try:
                        saida = proc(frame) if proc is not None else None
                    except Exception as e:  # noqa: BLE001
                        traceback.print_exc()
                        saida, erro = None, f"Erro no processamento: {e}"
                    s._entregar(g, frame, saida, float(getattr(cam, "fps_medido", 0.0)), erro)
                    if self.isInterruptionRequested():
                        break
        except ErroAquisicao as e:
            s._sinalFalha.emit(g, str(e))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            s._sinalFalha.emit(g, f"Falha na câmera: {e}")
        finally:
            s._sinalEncerrada.emit(g)


class ServicoCamera(QObject):
    estadoMudou = Signal()
    erroMudou = Signal()
    fpsMudou = Signal()
    quadroDisponivel = Signal()
    erroProcessamento = Signal(str)

    # sinais internos emitidos pela thread de captura (entregues na thread da interface)
    _sinalAberta = Signal(int)
    _sinalFalha = Signal(int, str)
    _sinalEncerrada = Signal(int)

    def __init__(self, fonte_fabrica: Callable[[], Any] | None = None, parent=None):
        super().__init__(parent)
        self.fonte_fabrica: Callable[[], Any] = fonte_fabrica or fabrica_padrao
        self._estado = DESLIGADA
        self._erro = ""
        self._fps = 0.0
        self._processador: Callable[[Any], Any] | None = None
        self._thread: _ThreadCaptura | None = None
        self._encerrando: list[_ThreadCaptura] = []   # threads paradas que ainda não terminaram
        self._geracao = 0
        self._lock = threading.Lock()
        self._pacote: Pacote | None = None
        self._avisado = False
        self._seq = 0
        self._sinalAberta.connect(self._aberta)
        self._sinalFalha.connect(self._falha)
        self._sinalEncerrada.connect(self._encerrada)

    # ------------------------------------------------------------------ propriedades
    def _get_estado(self) -> str:
        return self._estado

    def _get_erro(self) -> str:
        return self._erro

    def _get_fps(self) -> float:
        return self._fps

    estado = Property(str, _get_estado, notify=estadoMudou)
    erro = Property(str, _get_erro, notify=erroMudou)
    fps = Property(float, _get_fps, notify=fpsMudou)

    @property
    def ativa(self) -> bool:
        return self._estado == ATIVA

    def _mudar_estado(self, estado: str, erro: str | None = None) -> None:
        if erro is not None and erro != self._erro:
            self._erro = erro
            self.erroMudou.emit()
        if estado != self._estado:
            self._estado = estado
            self.estadoMudou.emit()

    # ------------------------------------------------------------------ controle
    def iniciar(self, processador: Callable[[Any], Any] | None) -> None:
        """Abre a câmera (fechando a anterior) com o processador dado. Erros viram estado ERRO."""
        self.parar()
        self._processador = processador
        self._geracao += 1
        self._mudar_estado(ABRINDO, "")
        try:
            fonte = self.fonte_fabrica()
            if isinstance(fonte, FonteCamera):
                fonte.preparar()       # thread principal: permite o pedido de permissão no macOS
        except Exception as e:  # noqa: BLE001
            self._mudar_estado(ERRO, f"Falha na câmera: {e}")
            return
        self._thread = _ThreadCaptura(fonte, self, self._geracao)
        self._thread.start()

    def definir_processador(self, processador: Callable[[Any], Any] | None) -> None:
        self._processador = processador
        with self._lock:
            self._pacote = None

    def parar(self, espera_ms: int = 3000) -> None:
        t, self._thread = self._thread, None
        self._geracao += 1                 # avisos atrasados da thread antiga passam a ser ignorados
        if t is not None:
            t.requestInterruption()
            if not t.wait(espera_ms):
                self._encerrando.append(t)  # mantém a referência até terminar (evita destruir thread viva)
        with self._lock:
            self._pacote = None
            self._avisado = False
        if self._fps:
            self._fps = 0.0
            self.fpsMudou.emit()
        self._mudar_estado(DESLIGADA, "")

    def ultimo(self) -> Pacote | None:
        with self._lock:
            self._avisado = False
            return self._pacote

    # ------------------------------------------------------------------ vindo da thread de captura
    def _entregar(self, geracao: int, frame, saida, fps: float, erro: str) -> None:
        if geracao != self._geracao:
            return
        with self._lock:
            self._seq += 1
            self._pacote = Pacote(frame, saida, self._seq, fps)
            avisar = not self._avisado
            self._avisado = True
        if erro:
            self.erroProcessamento.emit(erro)
        if avisar:
            self.quadroDisponivel.emit()

    @Slot(int)
    def _aberta(self, geracao: int) -> None:
        if geracao == self._geracao:
            self._mudar_estado(ATIVA, "")

    @Slot(int, str)
    def _falha(self, geracao: int, erro: str) -> None:
        if geracao == self._geracao:
            self._thread = None
            self._mudar_estado(ERRO, erro)

    @Slot(int)
    def _encerrada(self, geracao: int) -> None:
        self._encerrando = [t for t in self._encerrando if t.isRunning()]
        if geracao == self._geracao and self._estado in (ABRINDO, ATIVA):
            # a fonte acabou sozinha (gerador terminou): trata como câmera desligada
            self._thread = None
            self._mudar_estado(DESLIGADA)

    def atualizar_fps(self, fps: float) -> None:
        fps = round(fps, 1)
        if abs(fps - self._fps) >= 0.5 or (fps == 0) != (self._fps == 0):
            self._fps = fps
            self.fpsMudou.emit()

```

## `cofre/qt/imagens.py` (66 linhas)

```python
"""Conversão entre as imagens do OpenCV (NumPy BGR) e QImage."""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage


def bgr_para_qimage(img: np.ndarray) -> QImage:
    """Copia a imagem para um QImage independente (o buffer do NumPy pode ser reutilizado)."""
    if img.ndim == 2:
        img = np.ascontiguousarray(img)
        h, w = img.shape
        return QImage(img.data, w, h, img.strides[0], QImage.Format.Format_Grayscale8).copy()
    if img.shape[2] == 4:
        img = img[:, :, :3]
    img = np.ascontiguousarray(img)
    h, w = img.shape[:2]
    return QImage(img.data, w, h, img.strides[0], QImage.Format.Format_BGR888).copy()


def hex_de_bgr(cor: tuple[int, int, int]) -> str:
    """Cor do HUD do OpenCV (B, G, R) para '#rrggbb'."""
    b, g, r = (int(c) for c in cor[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def criar_provedor():
    """Provedor de imagens em memória servidas ao QML por `image://cofre/<chave>`
    (miniaturas do cadastro, por exemplo)."""
    import threading

    from PySide6.QtQuick import QQuickImageProvider

    class _Provedor(QQuickImageProvider):
        def __init__(self):
            super().__init__(QQuickImageProvider.ImageType.Image)
            self._lock = threading.Lock()
            self._imagens: dict[str, QImage] = {}

        def guardar(self, chave: str, imagem: QImage) -> None:
            with self._lock:
                self._imagens[chave] = imagem

        def remover_prefixo(self, prefixo: str) -> None:
            with self._lock:
                for k in [k for k in self._imagens if k.startswith(prefixo)]:
                    del self._imagens[k]

        def requestImage(self, ident, tamanho, pedido):  # noqa: N802 (API do Qt)
            chave = ident.split("?", 1)[0]
            with self._lock:
                img = self._imagens.get(chave)
            if img is None:
                img = QImage(1, 1, QImage.Format.Format_ARGB32)
                img.fill(0)
            if pedido is not None and pedido.isValid() and pedido.width() > 0 and pedido.height() > 0:
                from PySide6.QtCore import Qt
                img = img.scaled(pedido, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
            if tamanho is not None:
                tamanho.setWidth(img.width())
                tamanho.setHeight(img.height())
            return img

    return _Provedor()

```

## `cofre/qt/modelos.py` (65 linhas)

```python
"""Modelo de lista genérico (QAbstractListModel) para tabelas e listas do QML."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QPersistentModelIndex, Qt, Property, Signal, Slot

_ModelIndex = QModelIndex | QPersistentModelIndex


class ModeloLista(QAbstractListModel):
    """Lista de dicionários; cada chave vira um papel (role) acessível no delegate do QML."""

    contagemMudou = Signal()

    def __init__(self, papeis: list[str], parent=None):
        super().__init__(parent)
        self._papeis = list(papeis)
        self._roles = {Qt.ItemDataRole.UserRole + 1 + i: p for i, p in enumerate(self._papeis)}
        self._itens: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ API Python
    def definir(self, itens: list[dict[str, Any]]) -> None:
        """Troca o conteúdo. Se nada mudou, não mexe no modelo (evita redesenhar a lista)."""
        itens = [dict(i) for i in itens]
        if itens == self._itens:
            return
        mudou_contagem = len(itens) != len(self._itens)
        if len(itens) == len(self._itens) and [i.get("id") for i in itens] == [i.get("id") for i in self._itens]:
            # mesmas linhas, valores diferentes: atualiza no lugar (mantém rolagem e seleção)
            self._itens = itens
            if itens:
                self.dataChanged.emit(self.index(0), self.index(len(itens) - 1))
            return
        self.beginResetModel()
        self._itens = itens
        self.endResetModel()
        if mudou_contagem:
            self.contagemMudou.emit()

    def itens(self) -> list[dict[str, Any]]:
        return [dict(i) for i in self._itens]

    # ------------------------------------------------------------------ Qt
    def rowCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._itens)

    def data(self, index: _ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._itens):
            return None
        papel = self._roles.get(role)
        return None if papel is None else self._itens[index.row()].get(papel)

    def roleNames(self) -> dict[int, QByteArray]:
        return {r: QByteArray(p.encode()) for r, p in self._roles.items()}

    def _contagem(self) -> int:
        return len(self._itens)

    contagem = Property(int, _contagem, notify=contagemMudou)

    @Slot(int, result="QVariantMap")
    def item(self, linha: int) -> dict:
        return dict(self._itens[linha]) if 0 <= linha < len(self._itens) else {}

```

## `cofre/qt/tarefas.py` (73 linhas)

```python
"""Trabalho pesado fora da thread da interface (QThreadPool), com resposta por sinal.

O `Banco` usa uma conexão SQLite presa à thread que a criou; tarefas que precisam do
banco abrem a própria conexão (`Banco(caminho)`) dentro da função executada.
"""

from __future__ import annotations

import itertools
import traceback
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, QRunnable, QThreadPool, Signal, Slot


class _Sinais(QObject):
    terminou = Signal(int, object, str)


class _Executavel(QRunnable):
    def __init__(self, ident: int, fn: Callable[[], Any], sinais: _Sinais):
        super().__init__()
        self.ident, self.fn, self.sinais = ident, fn, sinais
        self.setAutoDelete(True)

    def run(self) -> None:  # roda em uma thread do pool
        try:
            resultado, erro = self.fn(), ""
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            resultado, erro = None, (str(e) or e.__class__.__name__)
        self.sinais.terminou.emit(self.ident, resultado, erro)


class Tarefas(QObject):
    """Executa funções em segundo plano e chama `ao_terminar(resultado, erro)` na thread da interface."""

    ocupadaMudou = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self._sinais = _Sinais(self)
        self._sinais.terminou.connect(self._terminou)
        self._callbacks: dict[int, Callable[[Any, str], None]] = {}
        self._ids = itertools.count(1)

    def executar(self, fn: Callable[[], Any], ao_terminar: Callable[[Any, str], None]) -> int:
        ident = next(self._ids)
        self._callbacks[ident] = ao_terminar
        self._pool.start(_Executavel(ident, fn, self._sinais))
        self.ocupadaMudou.emit()
        return ident

    @Slot(int, object, str)
    def _terminou(self, ident: int, resultado: Any, erro: str) -> None:
        cb = self._callbacks.pop(ident, None)
        self.ocupadaMudou.emit()
        if cb is None:
            return
        try:
            cb(resultado, erro)
        except Exception:  # noqa: BLE001
            traceback.print_exc()

    def esperar(self, ms: int = 5000) -> bool:
        return self._pool.waitForDone(ms)

    def _ocupada(self) -> bool:
        return bool(self._callbacks)

    ocupada = Property(bool, _ocupada, notify=ocupadaMudou)

```

## `cofre/qt/tema.py` (46 linhas)

```python
"""Cores e rótulos usados pelo lado Python da interface Qt (o QML tem o seu Theme.qml,
com os mesmos valores)."""

ACENTO = "#2dd4bf"
VERDE = "#34d399"
VERMELHO = "#f87171"
AMARELO = "#fbbf24"
NEUTRO = "#94a3b8"

TITULO_RESULTADO = {
    "CONCEDIDO": "Acesso autorizado",
    "NEGADO_NIVEL": "Nível insuficiente",
    "NEGADO_DESCONHECIDO": "Rosto não reconhecido",
    "NEGADO_LIVENESS": "Prova de vida não concluída",
    "NEGADO_MULTIPLOS": "Mais de uma pessoa",
    "BLOQUEADO": "Terminal bloqueado",
}

ROTULO_CURTO_RESULTADO = {
    "CONCEDIDO": "Concedido",
    "NEGADO_NIVEL": "Nível insuficiente",
    "NEGADO_DESCONHECIDO": "Não cadastrado",
    "NEGADO_LIVENESS": "Prova de vida",
    "NEGADO_MULTIPLOS": "Mais de uma pessoa",
    "BLOQUEADO": "Bloqueio",
}

ETAPAS_DIDATICAS = {
    "1 original": ("Fase 1", "Aquisição"),
    "2 reduzida": ("Fase 2", "Redução"),
    "2 cinza": ("Fase 2", "Tons de cinza"),
    "2 suavizada": ("Fase 2", "Suavização"),
    "2 CLAHE": ("Fase 2", "Equalização CLAHE"),
    "3 deteccao+pontos": ("Fase 3", "Detecção e pontos"),
    "3 recorte": ("Fase 3", "Recorte"),
    "3 alinhado 112x112": ("Fase 3", "Alinhado 112×112"),
    "4 LBP (textura)": ("Fase 4", "Textura LBP"),
    "4 embedding 128-d": ("Fase 4", "Embedding 128-d"),
}


def rotulo_etapa(chave: str) -> tuple[str, str]:
    if chave in ETAPAS_DIDATICAS:
        return ETAPAS_DIDATICAS[chave]
    fase, _, nome = chave.partition(" ")
    return (f"Fase {fase}" if fase.isdigit() else "", nome or chave)

```

## `cofre/qt/video.py` (262 linhas)

```python
"""
Exibição de vídeo no QML: `FonteVideo` guarda o quadro (QImage) e as marcações dos rostos;
`VisorVideo` (item do QML) desenha tudo com QPainter.

As marcações são desenhadas pelo Qt (e não pelo OpenCV) para ficarem nítidas em qualquer
tamanho de janela e com a mesma tipografia do restante da interface.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen
from PySide6.QtQuick import QQuickPaintedItem


class FonteVideo(QObject):
    """Último quadro + marcações. `caixas` é uma lista de dicionários:
    {"x", "y", "w", "h", "cor": "#rrggbb", "rotulo": str, "pontos": [(x, y), ...]} em pixels do quadro."""

    mudou = Signal()
    temImagemMudou = Signal()

    def __init__(self, nome: str = "", parent=None):
        super().__init__(parent)
        self._nome = nome
        self._imagem = QImage()
        self._caixas: list[dict[str, Any]] = []

    def definir(self, imagem: QImage | None, caixas: list[dict[str, Any]] | None = None) -> None:
        tinha = not self._imagem.isNull()
        self._imagem = imagem if imagem is not None else QImage()
        self._caixas = list(caixas or [])
        if tinha != (not self._imagem.isNull()):
            self.temImagemMudou.emit()
        self.mudou.emit()

    def limpar(self) -> None:
        self.definir(None, [])

    @property
    def imagem(self) -> QImage:
        return self._imagem

    @property
    def caixas(self) -> list[dict[str, Any]]:
        return self._caixas

    def _tem_imagem(self) -> bool:
        return not self._imagem.isNull()

    def _get_nome(self) -> str:
        return self._nome

    temImagem = Property(bool, _tem_imagem, notify=temImagemMudou)
    nome = Property(str, _get_nome, constant=True)


class VisorVideo(QQuickPaintedItem):
    fonteMudou = Signal()
    preencherMudou = Signal()
    raioMudou = Signal()
    corFundoMudou = Signal()
    mostrarPontosMudou = Signal()
    varreduraMudou = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fonte: FonteVideo | None = None
        self._preencher = False
        self._raio = 0.0
        self._cor_fundo = QColor("#0b0d10")
        self._mostrar_pontos = True
        self._varredura = -1.0        # 0..1 = linha de varredura na caixa principal; < 0 = desligada
        self.setAntialiasing(True)
        self.setOpaquePainting(False)

    # ------------------------------------------------------------------ propriedades
    def _get_fonte(self):
        return self._fonte

    def _set_fonte(self, fonte) -> None:
        if fonte is self._fonte:
            return
        if self._fonte is not None:
            try:
                self._fonte.mudou.disconnect(self.update)
            except (RuntimeError, TypeError):
                pass
        self._fonte = fonte
        if fonte is not None:
            fonte.mudou.connect(self.update)
        self.fonteMudou.emit()
        self.update()

    def _get_preencher(self) -> bool:
        return self._preencher

    def _set_preencher(self, v: bool) -> None:
        if v != self._preencher:
            self._preencher = bool(v)
            self.preencherMudou.emit()
            self.update()

    def _get_raio(self) -> float:
        return self._raio

    def _set_raio(self, v: float) -> None:
        if v != self._raio:
            self._raio = float(v)
            self.raioMudou.emit()
            self.update()

    def _get_cor_fundo(self) -> QColor:
        return self._cor_fundo

    def _set_cor_fundo(self, v) -> None:
        cor = QColor(v)
        if cor != self._cor_fundo:
            self._cor_fundo = cor
            self.corFundoMudou.emit()
            self.update()

    def _get_mostrar_pontos(self) -> bool:
        return self._mostrar_pontos

    def _set_mostrar_pontos(self, v: bool) -> None:
        if v != self._mostrar_pontos:
            self._mostrar_pontos = bool(v)
            self.mostrarPontosMudou.emit()
            self.update()

    fonte = Property(QObject, _get_fonte, _set_fonte, notify=fonteMudou)
    preencher = Property(bool, _get_preencher, _set_preencher, notify=preencherMudou)
    raio = Property(float, _get_raio, _set_raio, notify=raioMudou)
    corFundo = Property(QColor, _get_cor_fundo, _set_cor_fundo, notify=corFundoMudou)
    mostrarPontos = Property(bool, _get_mostrar_pontos, _set_mostrar_pontos, notify=mostrarPontosMudou)

    def _get_varredura(self) -> float:
        return self._varredura

    def _set_varredura(self, v: float) -> None:
        if v != self._varredura:
            self._varredura = float(v)
            self.varreduraMudou.emit()
            self.update()

    varredura = Property(float, _get_varredura, _set_varredura, notify=varreduraMudou)

    # ------------------------------------------------------------------ desenho
    def paint(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        if w <= 1 or h <= 1:
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        area = QRectF(0, 0, w, h)
        recorte = QPainterPath()
        recorte.addRoundedRect(area, self._raio, self._raio)
        p.setClipPath(recorte)
        p.fillRect(area, self._cor_fundo)
        fonte = self._fonte
        if fonte is None or fonte.imagem.isNull():
            return
        img = fonte.imagem
        iw, ih = img.width(), img.height()
        esc = (max if self._preencher else min)(w / iw, h / ih)
        dw, dh = iw * esc, ih * esc
        ox, oy = (w - dw) / 2, (h - dh) / 2
        p.drawImage(QRectF(ox, oy, dw, dh), img)
        for caixa in fonte.caixas:
            self._desenhar_caixa(p, caixa, esc, ox, oy)

    @staticmethod
    def _desenhar_malha(p: QPainter, pts: list[QPointF], cor: QColor, caixa: QRectF) -> None:
        """Geometria usada pelo alinhamento: linha dos olhos (eixo de inclinação), eixo vertical do
        nariz (eixo de giro) e a malha olhos-nariz-boca. Os pontos vêm do detector (YuNet)."""
        od, oe, nz, bd, be = pts
        fraca = QColor(cor)
        fraca.setAlphaF(0.45)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(fraca, 1.0))
        for a, b in ((od, oe), (od, nz), (oe, nz), (nz, bd), (nz, be), (bd, be)):
            p.drawLine(a, b)
        # eixos: prolongam a linha dos olhos e ligam o meio dos olhos ao meio da boca pelo nariz
        meio_olhos = QPointF((od.x() + oe.x()) / 2, (od.y() + oe.y()) / 2)
        meio_boca = QPointF((bd.x() + be.x()) / 2, (bd.y() + be.y()) / 2)
        eixo = QPen(fraca, 1.0, Qt.PenStyle.DashLine)
        p.setPen(eixo)
        dx, dy = oe.x() - od.x(), oe.y() - od.y()
        p.drawLine(QPointF(od.x() - dx * 0.35, od.y() - dy * 0.35), QPointF(oe.x() + dx * 0.35, oe.y() + dy * 0.35))
        vx, vy = meio_boca.x() - meio_olhos.x(), meio_boca.y() - meio_olhos.y()
        p.drawLine(QPointF(meio_olhos.x() - vx * 0.45, meio_olhos.y() - vy * 0.45),
                   QPointF(meio_boca.x() + vx * 0.35, meio_boca.y() + vy * 0.35))

    def _desenhar_varredura(self, p: QPainter, caixa: QRectF, cor: QColor) -> None:
        y = caixa.top() + caixa.height() * self._varredura
        faixa = QColor(cor)
        faixa.setAlphaF(0.10)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(faixa)
        p.drawRect(QRectF(caixa.left() + 2, max(caixa.top(), y - 18), caixa.width() - 4, min(18.0, y - caixa.top())))
        linha = QColor(cor)
        linha.setAlphaF(0.85)
        p.setPen(QPen(linha, 1.5))
        p.drawLine(QPointF(caixa.left() + 2, y), QPointF(caixa.right() - 2, y))

    def _desenhar_caixa(self, p: QPainter, c: dict[str, Any], esc: float, ox: float, oy: float) -> None:
        cor = QColor(c.get("cor", "#2dd4bf"))
        x, y = ox + c["x"] * esc, oy + c["y"] * esc
        bw, bh = c["w"] * esc, c["h"] * esc
        caixa = QRectF(x, y, bw, bh)
        fraca = QColor(cor)
        fraca.setAlphaF(0.35)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(fraca, 1.2))
        p.drawRoundedRect(caixa, 6, 6)
        # cantos destacados
        canto = max(10.0, min(bw, bh) * 0.18)
        caneta = QPen(cor, 3.0)
        caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(caneta)
        for px, py, dx, dy in ((x, y, 1, 1), (x + bw, y, -1, 1), (x, y + bh, 1, -1), (x + bw, y + bh, -1, -1)):
            p.drawLine(QPointF(px, py), QPointF(px + dx * canto, py))
            p.drawLine(QPointF(px, py), QPointF(px, py + dy * canto))
        pontos = [QPointF(ox + px * esc, oy + py * esc) for px, py in c.get("pontos", ())]
        if c.get("malha") and len(pontos) == 5:
            self._desenhar_malha(p, pontos, cor, caixa)
        if c.get("principal") and 0.0 <= self._varredura <= 1.0:
            self._desenhar_varredura(p, caixa, cor)
        if self._mostrar_pontos:
            p.setPen(Qt.PenStyle.NoPen)
            ponto = QColor(cor)
            ponto.setAlphaF(0.9)
            p.setBrush(ponto)
            for pt in pontos:
                p.drawEllipse(pt, 2.6, 2.6)
            if c.get("malha") and len(pontos) == 5:
                anel = QPen(ponto, 1.0)
                p.setPen(anel)
                p.setBrush(Qt.BrushStyle.NoBrush)
                for pt in pontos:
                    p.drawEllipse(pt, 6.0, 6.0)
        rotulo = c.get("rotulo") or ""
        if rotulo:
            f = QFont(p.font())
            f.setPixelSize(12)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            m = QFontMetricsF(f)
            tw = m.horizontalAdvance(rotulo) + 16
            th = m.height() + 8
            ty = y - th - 6 if y - th - 6 >= 4 else y + bh + 6
            pilula = QRectF(x, ty, tw, th)
            fundo = QColor(cor)
            fundo.setAlphaF(0.92)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fundo)
            p.drawRoundedRect(pilula, th / 2, th / 2)
            p.setPen(QColor("#0b0d10"))
            p.drawText(pilula, Qt.AlignmentFlag.AlignCenter, rotulo)

```

## `cofre/qt/vm_acessos.py` (283 linhas)

```python
"""ViewModel do log de auditoria: filtros (pessoa, resultado, nível, período), indicadores,
resumos por pessoa e por dia, detalhe com evidência e exportação CSV/HTML em segundo plano.
Tudo aqui é leitura: o log de acessos nunca é alterado pela interface."""

from __future__ import annotations

import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from .. import config, relatorios
from ..banco import Banco
from . import tema
from .base import ViewModel, objeto, prop
from .modelos import ModeloLista

PERIODOS = ("tudo", "hoje", "7d", "30d")
LIMITES = (50, 200, 1000)


def _desde(periodo: str) -> str | None:
    if periodo == "hoje":
        return date.today().isoformat()
    if periodo == "7d":
        return (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    if periodo == "30d":
        return (datetime.now() - timedelta(days=30)).isoformat(timespec="seconds")
    return None


def _data_hora(iso: str) -> tuple[str, str]:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M:%S")
    except (TypeError, ValueError):
        return iso or "–", ""


def _abrir(caminho: Path) -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho)))


class AcessosVM(ViewModel):
    totalMudou = Signal()
    concedidosMudou = Signal()
    negadosMudou = Signal()
    taxaMudou = Signal()
    usuariosMudou = Signal()
    amostrasMudou = Signal()
    buscaMudou = Signal()
    filtroResultadoMudou = Signal()
    filtroNivelMudou = Signal()
    periodoMudou = Signal()
    limiteMudou = Signal()
    listadosMudou = Signal()
    exportandoMudou = Signal()
    ultimoExportadoMudou = Signal()
    negacoesMudou = Signal()
    diasMudou = Signal()

    total = prop(int, "total", totalMudou)
    concedidos = prop(int, "concedidos", concedidosMudou)
    negados = prop(int, "negados", negadosMudou)
    taxa = prop(float, "taxa", taxaMudou)                    # -1 sem tentativas
    usuarios = prop(int, "usuarios", usuariosMudou)
    amostras = prop(int, "amostras", amostrasMudou)
    busca = prop(str, "busca", buscaMudou)
    filtroResultado = prop(str, "filtroResultado", filtroResultadoMudou)   # "" = todos
    filtroNivel = prop(int, "filtroNivel", filtroNivelMudou)              # 0 = todos
    periodo = prop(str, "periodo", periodoMudou)
    limite = prop(int, "limite", limiteMudou)
    listados = prop(int, "listados", listadosMudou)
    exportando = prop(bool, "exportando", exportandoMudou)
    ultimoExportado = prop(str, "ultimoExportado", ultimoExportadoMudou)
    negacoes = prop("QVariantList", "negacoes", negacoesMudou)
    dias = prop("QVariantList", "dias", diasMudou)
    modelo = objeto("lista")
    modeloPessoas = objeto("pessoas")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(total=0, concedidos=0, negados=0, taxa=-1.0, usuarios=0, amostras=0, busca="",
                      filtroResultado="", filtroNivel=0, periodo="tudo", limite=200, listados=0,
                      exportando=False, ultimoExportado="", negacoes=[], dias=[])
        self.lista = ModeloLista(["id", "data", "hora", "nome", "nivelUsuario", "nivelExigido", "area",
                                  "similaridade", "resultado", "titulo", "concedido", "mensagem", "temEvidencia"], self)
        self.pessoas = ModeloLista(["id", "nome", "concedidos", "negados", "total"], self)
        self._acessos: dict[int, object] = {}
        self._carregado = False
        self._busca_timer = QTimer(self)
        self._busca_timer.setSingleShot(True)
        self._busca_timer.setInterval(250)
        self._busca_timer.timeout.connect(self.recarregar)

    @Slot(result="QVariantList")
    def opcoesResultado(self) -> list:
        return [{"chave": "", "titulo": "Todos os resultados"}] + [
            {"chave": k, "titulo": v} for k, v in tema.TITULO_RESULTADO.items()]

    def ativar(self) -> None:
        self.recarregar()

    def ao_banco_alterado(self) -> None:
        if self._carregado:
            self.recarregar()

    # ------------------------------------------------------------------ dados
    @Slot()
    def recarregar(self) -> None:
        try:
            est = self.app.banco.estatisticas()
            acessos = self.app.banco.filtrar_acessos(
                limite=self._v["limite"], resultado=self._v["filtroResultado"] or None,
                nivel_exigido=self._v["filtroNivel"] or None, desde=_desde(self._v["periodo"]),
                termo=self._v["busca"].strip() or None)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.app.notificar("erro", f"Não foi possível ler o banco: {e}")
            return
        self._carregado = True
        por = est["por_resultado"]
        total = int(est["total"])
        conc = int(por.get("CONCEDIDO", 0))
        self._definir("total", total)
        self._definir("concedidos", conc)
        self._definir("negados", total - conc)
        self._definir("taxa", round(conc / total, 4) if total else -1.0)
        self._definir("usuarios", int(est["usuarios"]))
        self._definir("amostras", int(est["amostras"]))
        self._definir("negacoes", [{"chave": k, "titulo": tema.ROTULO_CURTO_RESULTADO[k], "n": int(por.get(k, 0))}
                                   for k in ("NEGADO_DESCONHECIDO", "NEGADO_NIVEL", "NEGADO_LIVENESS",
                                             "NEGADO_MULTIPLOS", "BLOQUEADO")])
        dias = list(reversed(est["por_dia"][:14]))
        maior = max((d["total"] for d in dias), default=0) or 1
        self._definir("dias", [{"dia": d["dia"][8:10] + "/" + d["dia"][5:7], "total": int(d["total"]),
                                "concedidos": int(d["concedidos"] or 0), "fracao": d["total"] / maior} for d in dias])
        self.pessoas.definir([{"id": i, "nome": p["nome"], "concedidos": int(p["concedidos"] or 0),
                               "negados": int(p["negados"] or 0),
                               "total": int(p["concedidos"] or 0) + int(p["negados"] or 0)}
                              for i, p in enumerate(est["por_usuario"])])
        self._acessos = {a.id: a for a in acessos}
        itens = []
        for a in acessos:
            data, hora = _data_hora(a.data_hora)
            itens.append({
                "id": a.id, "data": data, "hora": hora, "nome": a.nome_detectado or "Não identificado",
                "nivelUsuario": int(a.nivel_usuario or 0), "nivelExigido": int(a.nivel_exigido), "area": a.area,
                "similaridade": f"{a.similaridade:.2f}" if a.similaridade is not None else "–",
                "resultado": a.resultado, "titulo": tema.ROTULO_CURTO_RESULTADO.get(a.resultado, a.resultado),
                "concedido": a.resultado == "CONCEDIDO", "mensagem": a.mensagem or "",
                "temEvidencia": bool(a.evidencia),
            })
        self.lista.definir(itens)
        self._definir("listados", len(itens))

    # ------------------------------------------------------------------ filtros
    @Slot(str)
    def definirBusca(self, termo: str) -> None:
        if self._definir("busca", termo or ""):
            self._busca_timer.start()            # debounce: recarrega 250 ms após a última tecla

    @Slot(str)
    def definirFiltroResultado(self, chave: str) -> None:
        if (not chave or chave in tema.TITULO_RESULTADO) and self._definir("filtroResultado", chave or ""):
            self.recarregar()

    @Slot(int)
    def definirFiltroNivel(self, nivel: int) -> None:
        if (nivel == 0 or nivel in config.NIVEIS) and self._definir("filtroNivel", int(nivel)):
            self.recarregar()

    @Slot(str)
    def definirPeriodo(self, periodo: str) -> None:
        if periodo in PERIODOS and self._definir("periodo", periodo):
            self.recarregar()

    @Slot(int)
    def definirLimite(self, limite: int) -> None:
        if limite in LIMITES and self._definir("limite", int(limite)):
            self.recarregar()

    @Slot()
    def limparFiltros(self) -> None:
        self._definir("busca", "")
        self._definir("filtroResultado", "")
        self._definir("filtroNivel", 0)
        self._definir("periodo", "tudo")
        self.recarregar()

    @Slot(str)
    def filtrarPessoa(self, nome: str) -> None:
        if nome == "DESCONHECIDO":         # rostos sem cadastro: filtra pelo resultado
            self._definir("busca", "")
            self._definir("filtroResultado", "NEGADO_DESCONHECIDO")
        else:
            self._definir("busca", nome)
        self.recarregar()

    # ------------------------------------------------------------------ detalhe
    @Slot(int, result="QVariantMap")
    def detalhe(self, ident: int) -> dict:
        a = self._acessos.get(int(ident))
        if a is None:
            return {}
        data, hora = _data_hora(a.data_hora)
        evid = None
        if a.evidencia:
            evid = Path(a.evidencia)
            if not evid.is_absolute():
                evid = config.BASE_DIR / evid
        return {
            "id": a.id, "data": data, "hora": hora, "nome": a.nome_detectado or "Não identificado",
            "resultado": a.resultado, "titulo": tema.TITULO_RESULTADO.get(a.resultado, a.resultado),
            "concedido": a.resultado == "CONCEDIDO",
            "nivelUsuario": int(a.nivel_usuario or 0),
            "nivelUsuarioDescricao": config.NIVEIS.get(a.nivel_usuario, "") if a.nivel_usuario else "",
            "nivelExigido": int(a.nivel_exigido), "area": a.area,
            "similaridade": f"{a.similaridade:.3f}" if a.similaridade is not None else "–",
            "limiar": f"{config.LIMIAR_COSSENO:.3f}",
            "mensagem": a.mensagem or "",
            "evidencia": str(evid) if evid else "",
            "evidenciaUrl": QUrl.fromLocalFile(str(evid)).toString() if evid and evid.exists() else "",
            "evidenciaExiste": bool(evid and evid.exists()),
        }

    # ------------------------------------------------------------------ exportação e arquivos
    @Slot(str)
    def exportar(self, formato: str) -> None:
        formato = (formato or "").lower()
        if self._v["exportando"] or formato not in ("csv", "html"):
            return
        self._definir("exportando", True)
        caminho_db = self.app.banco.caminho
        em_memoria = str(caminho_db) == ":memory:"
        banco_principal = self.app.banco

        def trabalho():
            banco = banco_principal if em_memoria else Banco(caminho_db)   # conexão própria, só leitura
            try:
                fn = relatorios.exportar_csv if formato == "csv" else relatorios.exportar_html
                return Path(fn(banco))
            finally:
                if banco is not banco_principal:
                    banco.fechar()

        def terminou(caminho, erro: str) -> None:
            self._definir("exportando", False)
            if erro:
                self.app.notificar("erro", f"Falha ao exportar: {erro}")
                return
            self._definir("ultimoExportado", str(caminho))
            self.app.notificar("ok", f"Relatório {formato.upper()} salvo em {caminho.name}")

        if em_memoria:
            try:
                terminou(trabalho(), "")
            except Exception as e:  # noqa: BLE001
                terminou(None, str(e))
        else:
            self.app.tarefas.executar(trabalho, terminou)

    @Slot()
    def abrirExportado(self) -> None:
        caminho = Path(self._v["ultimoExportado"]) if self._v["ultimoExportado"] else None
        if caminho is None or not caminho.exists():
            self.app.notificar("erro", "O arquivo exportado não foi encontrado.")
            return
        if not _abrir(caminho.resolve()):
            self.app.notificar("erro", f"Não foi possível abrir {caminho.name}.")

    @Slot()
    def abrirPastaEvidencias(self) -> None:
        pasta = Path(config.EVIDENCIAS_DIR)
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.app.notificar("erro", f"Não foi possível abrir a pasta de evidências: {e}")
            return
        if not _abrir(pasta.resolve()):
            self.app.notificar("erro", "Não foi possível abrir a pasta de evidências.")

```

## `cofre/qt/vm_avaliacao.py` (360 linhas)

```python
"""ViewModel de "Avaliação e demo": demonstração das 5 fases em uma imagem, autenticação por
imagem (registrada no log, como na versão anterior) e avaliação quantitativa TAR/FAR/FRR/EER.

As fases 2 a 4 e a avaliação de pasta rodam em segundo plano; a fase 5 da demonstração
(comparação com a galeria) usa a conexão principal do banco, na thread da interface."""

from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Property, QUrl, Signal, Slot

from .. import config, hud
from ..autenticacao import autenticar_imagem
from ..avaliacao import ResultadoAvaliacao, avaliar_pasta
from ..banco import Banco
from ..fase1_aquisicao import carregar_imagem
from ..fase5_reconhecimento import Reconhecedor, decidir_acesso
from . import tema
from .base import ViewModel, objeto, prop
from .imagens import bgr_para_qimage
from .modelos import ModeloLista
from .video import FonteVideo

PASTA_FOTOS_TESTE = config.BASE_DIR / "tests" / "fixtures" / "pessoas"


def _pct(v: float) -> str:
    return "–" if v != v else f"{v:.1%}".replace(".", ",")


def _local(url: str) -> Path:
    u = QUrl(url)
    return Path(u.toLocalFile() if u.isLocalFile() else url)


class AvaliacaoVM(ViewModel):
    # demo
    demoArquivoMudou = Signal()
    demoProcessandoMudou = Signal()
    demoFasesMudou = Signal()
    demoNivelMudou = Signal()
    demoResultadoMudou = Signal()
    demoEtapasMudou = Signal()
    # autenticação por imagem
    authArquivoMudou = Signal()
    authProcessandoMudou = Signal()
    authNivelMudou = Signal()
    authResultadoMudou = Signal()
    # avaliação
    avalPastaMudou = Signal()
    avalProcessandoMudou = Signal()
    avalResultadoMudou = Signal()

    demoArquivo = prop(str, "demoArquivo", demoArquivoMudou)
    demoProcessando = prop(bool, "demoProcessando", demoProcessandoMudou)
    demoFases = prop("QVariantList", "demoFases", demoFasesMudou)
    demoNivel = prop(int, "demoNivel", demoNivelMudou)
    demoResultado = prop("QVariantMap", "demoResultado", demoResultadoMudou)
    authArquivo = prop(str, "authArquivo", authArquivoMudou)
    authProcessando = prop(bool, "authProcessando", authProcessandoMudou)
    authNivel = prop(int, "authNivel", authNivelMudou)
    authResultado = prop("QVariantMap", "authResultado", authResultadoMudou)
    avalPasta = prop(str, "avalPasta", avalPastaMudou)
    avalProcessando = prop(bool, "avalProcessando", avalProcessandoMudou)
    avalResultado = prop("QVariantMap", "avalResultado", avalResultadoMudou)
    modeloVarredura = objeto("varredura")
    fonteDemo = objeto("demoImagem")
    fonteAuth = objeto("authImagem")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(demoArquivo="", demoProcessando=False, demoFases=[], demoNivel=3, demoResultado={},
                      authArquivo="", authProcessando=False, authNivel=3, authResultado={},
                      avalPasta="", avalProcessando=False, avalResultado={})
        self.demoImagem = FonteVideo("demo", self)
        self._demo_etapas: list[FonteVideo] = []
        self.authImagem = FonteVideo("auth", self)
        self.varredura = ModeloLista(["id", "limiar", "tar", "frr", "far", "atual"], self)
        self._demo_res = None
        self._demo_caminho: Path | None = None
        self._painel: np.ndarray | None = None
        self._linhas_demo: list[str] = []

    def _get_demo_etapas(self) -> list:
        return list(self._demo_etapas)

    demoEtapas = Property("QVariantList", _get_demo_etapas, notify=demoEtapasMudou)

    @Slot(result=str)
    def pastaFotosTeste(self) -> str:
        return QUrl.fromLocalFile(str(PASTA_FOTOS_TESTE)).toString()

    def _pipeline_ou_aviso(self) -> bool:
        if self.app.pipeline is None:
            self.app.notificar("aviso", "Os modelos ainda estão carregando. Tente novamente em instantes.")
            return False
        return True

    # ------------------------------------------------------------------ demo das 5 fases
    @Slot(str)
    def demonstrar(self, url: str) -> None:
        if self._v["demoProcessando"] or not self._pipeline_ou_aviso():
            return
        caminho = _local(url)
        self._demo_caminho = caminho
        self._definir("demoArquivo", caminho.name)
        self._definir("demoProcessando", True)
        pipeline = self.app.pipeline

        def trabalho():
            frame = carregar_imagem(caminho)
            res = pipeline.processar(frame)
            etapas = [(k, bgr_para_qimage(v if v.ndim == 3 else cv2.cvtColor(v, cv2.COLOR_GRAY2BGR)))
                      for k, v in res.etapas_didaticas().items()]
            painel = hud.mosaico(res.etapas_didaticas(), lado=200, colunas=4)
            return res, etapas, painel

        def terminou(r, erro: str) -> None:
            self._definir("demoProcessando", False)
            if erro:
                self._definir("demoResultado", {"tipo": "erro", "titulo": "Falha na demonstração", "mensagem": erro})
                self.app.notificar("erro", f"Falha na demonstração: {erro}")
                return
            res, etapas, painel = r
            self._demo_res, self._painel = res, painel
            fontes = []
            for chave, qimg in etapas:
                fase, nome = tema.rotulo_etapa(chave)
                f = FonteVideo(f"{fase} · {nome}" if fase else nome, self)
                f.definir(qimg, [])
                fontes.append(f)
            self._demo_etapas = fontes
            self.demoEtapasMudou.emit()
            p = res.principal
            caixas = []
            if p is not None:
                r_ = p.rosto
                caixas.append({"x": r_.x, "y": r_.y, "w": r_.w, "h": r_.h, "cor": tema.ACENTO, "rotulo": "",
                               "pontos": [r_.olho_dir, r_.olho_esq, r_.nariz, r_.boca_dir, r_.boca_esq]})
            self.demoImagem.definir(bgr_para_qimage(res.pre.original), caixas)
            self._montar_demo()

        self.app.tarefas.executar(trabalho, terminou)

    @Slot(int)
    def definirNivelDemo(self, nivel: int) -> None:
        if nivel in config.NIVEIS and self._definir("demoNivel", int(nivel)) and self._demo_res is not None:
            self._montar_demo()

    def _montar_demo(self) -> None:
        """Texto por fase. A fase 5 consulta a galeria (conexão principal) e NÃO grava no log."""
        res, nivel = self._demo_res, self._v["demoNivel"]
        frame = res.pre.original
        nome = self._demo_caminho.name if self._demo_caminho else "–"
        fases = [
            {"fase": 1, "titulo": "Aquisição", "linhas": [["Arquivo", nome],
                                                         ["Tamanho", f"{frame.shape[1]}×{frame.shape[0]} px"]]},
            {"fase": 2, "titulo": "Pré-processamento", "linhas": [
                ["Quadro reduzido", f"{res.pre.reduzida.shape[1]}×{res.pre.reduzida.shape[0]} px"],
                ["Escala", f"{res.pre.escala:.2f}"], ["Etapas", "cinza, suavização, CLAHE"]]},
            {"fase": 3, "titulo": "Segmentação", "linhas": [["Rostos detectados", str(len(res.rostos))]]},
        ]
        p = res.principal
        linhas_txt = [f"FASE 1  Aquisicao: {nome} {frame.shape[1]}x{frame.shape[0]}",
                      f"FASE 2  Pre-processamento: escala {res.pre.escala:.2f}",
                      f"FASE 3  Segmentacao: {len(res.rostos)} rosto(s)"]
        if p is None:
            fases += [{"fase": 4, "titulo": "Representação", "linhas": [["Embedding", "sem rosto, fase não executada"]]},
                      {"fase": 5, "titulo": "Reconhecimento", "linhas": [["Decisão", "sem rosto, fase não executada"]]}]
            resultado = {"tipo": "aviso", "titulo": "Nenhum rosto detectado",
                         "mensagem": "Tente uma foto frontal e bem iluminada."}
            linhas_txt.append("Nenhum rosto detectado")
        else:
            x, y, w, h = p.rosto.caixa
            norma = float(np.linalg.norm(p.embedding))
            reconhecedor = Reconhecedor(self.app.banco)
            ident = reconhecedor.identificar(p.embedding)
            d = decidir_acesso(ident, nivel)
            fases[2]["linhas"] += [["Caixa (x, y, w, h)", f"{x}, {y}, {w}, {h}"],
                                   ["Confiança", f"{p.rosto.confianca:.3f}"],
                                   ["Yaw (nariz/olhos)", f"{p.rosto.yaw():+.3f}"],
                                   ["Nitidez", f"{p.qualidade.nitidez:.1f} (mín. {config.MIN_NITIDEZ:.0f})"],
                                   ["Brilho", f"{p.qualidade.brilho:.1f} ({config.MIN_BRILHO:.0f} a {config.MAX_BRILHO:.0f})"],
                                   ["Qualidade", "aprovada" if p.qualidade.aprovada else f"reprovada ({p.qualidade.motivo})"]]
            fases.append({"fase": 4, "titulo": "Representação", "linhas": [
                ["Embedding", f"{p.embedding.shape[0]} dimensões"], ["Norma", f"{norma:.3f}"],
                ["Mín. / máx.", f"{float(p.embedding.min()):+.3f} / {float(p.embedding.max()):+.3f}"]]})
            fases.append({"fase": 5, "titulo": "Reconhecimento", "linhas": [
                ["Área", config.AREAS[nivel]], ["Galeria", f"{len(reconhecedor.usuarios)} usuário(s) ativo(s)"],
                ["Identificado", ident.usuario.nome if ident.reconhecido else "Não reconhecido"],
                ["Similaridade", f"{ident.similaridade:.3f} (limiar {config.LIMIAR_COSSENO:.3f})"],
                ["2º colocado", f"{ident.segunda_similaridade:.3f}"], ["Decisão", d.resultado.value]]})
            resultado = {"tipo": "ok" if d.concedido else "erro", "concedido": d.concedido,
                         "titulo": tema.TITULO_RESULTADO[d.resultado.value], "mensagem": d.mensagem}
            linhas_txt += [f"FASE 4  Embedding {p.embedding.shape[0]}-d, norma {norma:.3f}",
                           f"FASE 5  {ident.rotulo}  similaridade {ident.similaridade:.3f}  "
                           f"limiar {config.LIMIAR_COSSENO:.3f}  decisao {d.resultado.value}"]
        self._linhas_demo = linhas_txt
        self._definir("demoFases", fases)
        self._definir("demoResultado", resultado)

    @Slot(result=str)
    def salvarPainel(self) -> str:
        """Grava o mosaico das fases (com o resumo no rodapé) em config.RELATORIOS_DIR."""
        if self._painel is None:
            self.app.notificar("aviso", "Nada para salvar: rode a demonstração em uma imagem primeiro.")
            return ""
        try:
            linhas = [l for l in self._linhas_demo if l.strip()]
            painel = self._painel
            base = np.full((painel.shape[0] + 20 * len(linhas) + 16, painel.shape[1], 3), 20, np.uint8)
            base[:painel.shape[0]] = painel
            y = painel.shape[0] + 20
            for l in linhas:
                hud.texto(base, l, (10, y), 0.45, hud.BRANCO, 1)
                y += 20
            pasta = Path(config.RELATORIOS_DIR)
            pasta.mkdir(parents=True, exist_ok=True)
            stem = self._demo_caminho.stem if self._demo_caminho else "imagem"
            destino = pasta / f"demo_{stem}_{datetime.now():%Y%m%d_%H%M%S}.png"
            if not cv2.imwrite(str(destino), base):
                raise OSError("o OpenCV não conseguiu gravar o arquivo")
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.app.notificar("erro", f"Não foi possível salvar o painel: {e}")
            return ""
        self.app.notificar("ok", f"Painel salvo em {destino.name}")
        return str(destino)

    # ------------------------------------------------------------------ autenticar por imagem
    @Slot(int)
    def definirNivelAuth(self, nivel: int) -> None:
        if nivel in config.NIVEIS:
            self._definir("authNivel", int(nivel))

    @Slot(str)
    def autenticar(self, url: str) -> None:
        """Autentica a imagem no nível escolhido. Como antes, a tentativa entra no log de acessos."""
        if self._v["authProcessando"] or not self._pipeline_ou_aviso():
            return
        caminho = _local(url)
        nivel = self._v["authNivel"]
        self._definir("authArquivo", caminho.name)
        self._definir("authProcessando", True)
        caminho_db, pipeline = self.app.banco.caminho, self.app.pipeline
        em_memoria = str(caminho_db) == ":memory:"
        banco_principal = self.app.banco

        def trabalho():
            frame = carregar_imagem(caminho)
            banco = banco_principal if em_memoria else Banco(caminho_db)
            try:
                decisao, res = autenticar_imagem(banco, pipeline, frame, nivel)
            finally:
                if banco is not banco_principal:
                    banco.fechar()
            return frame, decisao, res

        def terminou(r, erro: str) -> None:
            self._definir("authProcessando", False)
            if erro:
                self._definir("authResultado", {"tipo": "erro", "titulo": "Falha ao autenticar", "mensagem": erro,
                                                "concedido": False})
                return
            frame, decisao, res = r
            cor = tema.VERDE if decisao.concedido else tema.VERMELHO
            caixas = [{"x": rp.rosto.x, "y": rp.rosto.y, "w": rp.rosto.w, "h": rp.rosto.h, "cor": cor, "rotulo": "",
                       "pontos": []} for rp in res.rostos]
            self.authImagem.definir(bgr_para_qimage(frame), caixas)
            ident = decisao.identificacao
            u = ident.usuario if ident and ident.reconhecido else None
            self._definir("authResultado", {
                "tipo": "ok" if decisao.concedido else "erro", "concedido": bool(decisao.concedido),
                "resultado": decisao.resultado.value, "titulo": tema.TITULO_RESULTADO[decisao.resultado.value],
                "mensagem": decisao.mensagem, "usuario": u.nome if u else "Não reconhecido",
                "nivelUsuario": int(u.nivel) if u else 0, "nivelExigido": int(nivel),
                "similaridade": f"{ident.similaridade:.3f}" if ident is not None else "–",
                "limiar": f"{config.LIMIAR_COSSENO:.3f}", "rostos": len(res.rostos),
            })
            self.app.banco_alterado()

        if em_memoria:
            try:
                terminou(trabalho(), "")
            except Exception as e:  # noqa: BLE001
                terminou(None, str(e))
        else:
            self.app.tarefas.executar(trabalho, terminou)

    # ------------------------------------------------------------------ avaliação do reconhecedor
    @Slot(str)
    def definirPasta(self, url: str) -> None:
        self._definir("avalPasta", str(_local(url)) if url else "")

    @Slot()
    def usarFotosTeste(self) -> None:
        self._definir("avalPasta", str(PASTA_FOTOS_TESTE))

    @Slot()
    def avaliar(self) -> None:
        if self._v["avalProcessando"] or not self._pipeline_ou_aviso():
            return
        if not self._v["avalPasta"]:
            self.app.notificar("aviso", "Escolha uma pasta (ou use as fotos de teste) antes de avaliar.")
            return
        pasta = Path(self._v["avalPasta"])
        if not pasta.is_dir():
            self.app.notificar("erro", f"Pasta não encontrada: {pasta}")
            return
        if not any(p.is_dir() for p in pasta.iterdir()):
            self.app.notificar("aviso", "A pasta precisa ter uma subpasta por pessoa (pasta/pessoa/*.jpg).")
            return
        self._definir("avalProcessando", True)
        pipeline = self.app.pipeline

        def terminou(r: ResultadoAvaliacao, erro: str) -> None:
            self._definir("avalProcessando", False)
            if erro:
                self.app.notificar("erro", f"Falha na avaliação: {erro}")
                return
            self._aplicar_avaliacao(r)

        self.app.tarefas.executar(lambda: avaliar_pasta(pasta, pipeline), terminou)

    def _aplicar_avaliacao(self, r: ResultadoAvaliacao) -> None:
        n_img = sum(r.pessoas.values())
        base = {"pessoas": len(r.pessoas), "imagens": n_img, "semRosto": len(r.sem_rosto),
                "genuinos": len(r.genuinos), "impostores": len(r.impostores), "resumo": r.resumo(),
                "limiar": float(config.LIMIAR_COSSENO)}
        if not r.genuinos and not r.impostores:
            self.varredura.definir([])
            self._definir("avalResultado", {**base, "valido": False, "aviso":
                f"Nenhum par para comparar ({n_img} imagem(ns) com rosto, {len(r.sem_rosto)} sem rosto). "
                "São necessárias ao menos 2 imagens com rosto."})
            return
        t = r.taxas(config.LIMIAR_COSSENO)
        eer_l, eer_v = r.eer()
        pontos = r.varredura(11)
        perto = min(pontos, key=lambda v: abs(v["limiar"] - config.LIMIAR_COSSENO))["limiar"]
        # tipos do NumPy não atravessam para o QML: tudo vira float/bool do Python
        self.varredura.definir([{"id": i, "limiar": f"{v['limiar']:.2f}", "tar": _pct(v["TAR"]),
                                 "frr": _pct(v["FRR"]), "far": _pct(v["FAR"]),
                                 "atual": bool(v["limiar"] == perto)}
                                for i, v in enumerate(pontos)])
        curva = [{"limiar": float(v["limiar"]), "tar": None if v["TAR"] != v["TAR"] else float(v["TAR"]),
                  "far": None if v["FAR"] != v["FAR"] else float(v["FAR"])} for v in r.varredura(51)]
        aviso = ""
        if r.sem_rosto:
            nomes = ", ".join(Path(s).name for s in r.sem_rosto[:3])
            extra = f" e mais {len(r.sem_rosto) - 3}" if len(r.sem_rosto) > 3 else ""
            aviso = f"Ignoradas {len(r.sem_rosto)} imagem(ns) sem rosto: {nomes}{extra}."
        self._definir("avalResultado", {**base, "valido": True, "aviso": aviso, "tar": _pct(t["TAR"]),
                                        "far": _pct(t["FAR"]), "frr": _pct(t["FRR"]), "eer": _pct(eer_v),
                                        "eerLimiar": f"{float(eer_l):.3f}", "curva": curva})
        self.app.notificar("ok", f"Avaliação concluída: EER {_pct(eer_v)}")

```

## `cofre/qt/vm_cadastro.py` (433 linhas)

```python
"""
ViewModel do cadastro biométrico: formulário, captura pela câmera (`SessaoCadastro`)
e importação de fotos (`cadastrar_de_imagens`).

Threads (iguais às da interface customtkinter):
  - câmera: só `pipeline.processar(frame, extrair_embedding=False)` e a conversão para QImage;
  - interface: `SessaoCadastro.passo()`, que grava as amostras no banco (conexão da thread principal);
  - importação de fotos: tarefa em segundo plano com conexão própria ao banco.
"""

from __future__ import annotations

import traceback
from pathlib import Path

import cv2
from PySide6.QtCore import Signal, Slot, QUrl

from .. import config, hud
from ..banco import Banco
from ..cadastro import INSTRUCOES_POSE, DadosCadastro, SessaoCadastro, cadastrar_de_imagens
from . import tema
from .base import ViewModel, objeto, prop
from .imagens import bgr_para_qimage
from .video import FonteVideo

LADO_MINIATURA = 160
MAX_AVISOS = 6
# Mesma ordem de cadastro.INSTRUCOES_POSE, com acentos (o HUD do OpenCV não desenha acentos).
POSES = [
    "Olhe para a câmera",
    "Vire um pouco o rosto para a esquerda",
    "Vire um pouco o rosto para a direita",
    "Incline a cabeça para a esquerda",
    "Incline a cabeça para a direita",
    "Levante um pouco o queixo",
    "Abaixe o queixo, como se olhasse o celular",
    "Olhe para a câmera de novo",
    "Sorria",
]
assert len(POSES) == len(INSTRUCOES_POSE)
_TIPO_COR = {hud.VERDE: "ok", hud.VERMELHO: "erro", hud.LARANJA: "aviso", hud.AMARELO: "neutro"}
_COR_TIPO = {"ok": tema.VERDE, "erro": tema.VERMELHO, "aviso": tema.AMARELO, "neutro": tema.ACENTO}


def _sem_acento_para_texto(status: str) -> str:
    """Os textos da SessaoCadastro não têm acento (o HUD do OpenCV não desenha acentos)."""
    trocas = {"camera": "câmera", "Posicione": "Posicione", "Apenas UMA pessoa deve aparecer":
              "Apenas uma pessoa deve aparecer", "Cadastro concluido!": "Cadastro concluído",
              "Capturando...": "Capturando…"}
    for a, b in trocas.items():
        status = status.replace(a, b)
    for i, pose in enumerate(INSTRUCOES_POSE):
        status = status.replace(pose, POSES[i])
    return status


def _miniatura(recorte) -> "object":
    h, w = recorte.shape[:2]
    m = min(h, w)
    y0, x0 = (h - m) // 2, (w - m) // 2
    quadrado = cv2.resize(recorte[y0:y0 + m, x0:x0 + m], (LADO_MINIATURA, LADO_MINIATURA),
                          interpolation=cv2.INTER_AREA)
    return bgr_para_qimage(quadrado)


def _caminho_local(url: str) -> str:
    u = QUrl(url)
    return u.toLocalFile() if u.isLocalFile() else url


class CadastroVM(ViewModel):
    faseMudou = Signal()
    erroMudou = Signal()
    erroCampoMudou = Signal()
    capturadasMudou = Signal()
    totalMudou = Signal()
    statusMudou = Signal()
    statusTipoMudou = Signal()
    poseMudou = Signal()
    poseIndiceMudou = Signal()
    nitidezMudou = Signal()
    brilhoMudou = Signal()
    qualidadeOkMudou = Signal()
    nRostosMudou = Signal()
    nomeMudou = Signal()
    nivelCadastroMudou = Signal()
    miniaturasMudou = Signal()
    revisaoMudou = Signal()
    sucessoMudou = Signal()
    pausadaMudou = Signal()
    amostraCapturada = Signal(int)

    fase = prop(str, "fase", faseMudou)       # formulario | preparando | capturando | importando
    erro = prop(str, "erro", erroMudou)
    erroCampo = prop(str, "erroCampo", erroCampoMudou)
    capturadas = prop(int, "capturadas", capturadasMudou)
    total = prop(int, "total", totalMudou)
    status = prop(str, "status", statusMudou)
    statusTipo = prop(str, "statusTipo", statusTipoMudou)
    pose = prop(str, "pose", poseMudou)
    poseIndice = prop(int, "poseIndice", poseIndiceMudou)
    nitidez = prop(float, "nitidez", nitidezMudou)
    brilho = prop(float, "brilho", brilhoMudou)
    qualidadeOk = prop(bool, "qualidadeOk", qualidadeOkMudou)
    nRostos = prop(int, "nRostos", nRostosMudou)
    nome = prop(str, "nome", nomeMudou)
    nivelCadastro = prop(int, "nivelCadastro", nivelCadastroMudou)
    miniaturas = prop(int, "miniaturas", miniaturasMudou)
    revisao = prop(int, "revisao", revisaoMudou)
    sucesso = prop("QVariantMap", "sucesso", sucessoMudou)
    pausada = prop(bool, "pausada", pausadaMudou)
    fonteVideo = objeto("video")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(fase="formulario", erro="", erroCampo="", capturadas=0, total=config.AMOSTRAS_POR_CADASTRO,
                      status="", statusTipo="neutro", pose=POSES[0], poseIndice=0, nitidez=0.0, brilho=0.0,
                      qualidadeOk=False, nRostos=0, nome="", nivelCadastro=1, miniaturas=0, revisao=0,
                      sucesso={}, pausada=False)
        self.video = FonteVideo("cadastro", self)
        self.sessao: SessaoCadastro | None = None
        self._dados_pendentes: DadosCadastro | None = None
        self._ativo = False
        self._seq_visto = -1
        aplicacao.camera.quadroDisponivel.connect(self._quadro)

    # ------------------------------------------------------------------ constantes para o QML
    @Slot(result="QVariantMap")
    def limites(self) -> dict:
        return {"minNitidez": float(config.MIN_NITIDEZ), "minBrilho": float(config.MIN_BRILHO),
                "maxBrilho": float(config.MAX_BRILHO), "poses": POSES, "intervalo": float(config.INTERVALO_AMOSTRAS_SEG)}

    @property
    def capturando(self) -> bool:
        return self._dados_pendentes is not None or (self.sessao is not None and not self.sessao.encerrada)

    # ------------------------------------------------------------------ ciclo de vida
    def ativar(self) -> None:
        self._ativo = True
        if self.capturando:
            self._definir("pausada", False)
            self._ligar_camera()

    def desativar(self) -> None:
        self._ativo = False
        if self.capturando:
            self._definir("pausada", True)     # a sessão continua; a câmera volta ao reabrir a tela
        self.app.camera.parar()

    def ao_pipeline_pronto(self) -> None:
        self._iniciar_sessao_se_pronto()

    # ------------------------------------------------------------------ formulário
    @Slot(str, result=str)
    def matriculaEmUso(self, matricula: str) -> str:
        """Nome de quem já usa a matrícula ('' se livre). Usado na validação ao digitar."""
        matricula = (matricula or "").strip()
        if not matricula:
            return ""
        try:
            u = self.app.banco.obter_por_matricula(matricula)
        except Exception:  # noqa: BLE001
            return ""
        return u.nome if u is not None else ""

    def _validar(self, nome: str, matricula: str, cargo: str, nivel: int) -> DadosCadastro | None:
        nome, matricula, cargo = (nome or "").strip(), (matricula or "").strip(), (cargo or "").strip()
        if not nome:
            return self._erro("nome", "Informe o nome do usuário.")
        if not matricula:
            return self._erro("matricula", "Informe a matrícula.")
        if int(nivel) not in config.NIVEIS:
            return self._erro("nivel", "Escolha um nível de acesso válido.")
        try:
            existente = self.app.banco.obter_por_matricula(matricula)
        except Exception as e:  # noqa: BLE001
            return self._erro("", f"Não foi possível consultar o banco: {e}")
        if existente is not None:
            return self._erro("matricula", f"Matrícula {matricula} já cadastrada para {existente.nome}.")
        self._definir("erro", "")
        self._definir("erroCampo", "")
        return DadosCadastro(nome, matricula, cargo, int(nivel))

    def _erro(self, campo: str, texto: str) -> None:
        self._definir("erroCampo", campo)
        self._definir("erro", texto)
        return None

    @Slot()
    def limparErro(self) -> None:
        self._definir("erro", "")
        self._definir("erroCampo", "")

    @Slot()
    def fecharSucesso(self) -> None:
        self._definir("sucesso", {})

    # ------------------------------------------------------------------ captura pela câmera
    @Slot(str, str, str, int, result=bool)
    def iniciarCaptura(self, nome: str, matricula: str, cargo: str, nivel: int) -> bool:
        if self.capturando or self._v["fase"] == "importando":
            return False
        dados = self._validar(nome, matricula, cargo, nivel)
        if dados is None:
            return False
        self._dados_pendentes = dados
        self._definir("sucesso", {})
        self._definir("nome", dados.nome)
        self._definir("nivelCadastro", dados.nivel)
        self._definir("fase", "preparando")
        self._definir("pausada", False)
        self._zerar_progresso(config.AMOSTRAS_POR_CADASTRO)
        self._definir("status", "Carregando os modelos…" if self.app.pipeline is None else "Ligando a câmera…")
        self._iniciar_sessao_se_pronto()
        return True

    def _zerar_progresso(self, total: int) -> None:
        self.app.imagens.remover_prefixo("cadastro/")
        self._definir("revisao", self._v["revisao"] + 1)
        self._definir("miniaturas", 0)
        self._definir("capturadas", 0)
        self._definir("total", int(total))
        self._definir("statusTipo", "neutro")
        self._definir("pose", POSES[0])
        self._definir("poseIndice", 0)
        self._definir("nitidez", 0.0)
        self._definir("brilho", 0.0)
        self._definir("qualidadeOk", False)
        self._definir("nRostos", 0)
        self.video.limpar()

    def _iniciar_sessao_se_pronto(self) -> None:
        if self._dados_pendentes is None or self.app.pipeline is None:
            return
        dados, self._dados_pendentes = self._dados_pendentes, None
        try:
            # quantidade explícita: o padrão do construtor é fixado na importação do módulo
            self.sessao = SessaoCadastro(self.app.banco, self.app.pipeline, dados,
                                         amostras=int(config.AMOSTRAS_POR_CADASTRO))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.sessao = None
            self._definir("fase", "formulario")
            self._erro("", f"Não foi possível iniciar o cadastro: {e}")
            return
        self._zerar_progresso(self.sessao.amostras)
        self._definir("fase", "capturando")
        self._definir("status", "Posicione o rosto na câmera")
        if self._ativo:
            self._ligar_camera()

    def _ligar_camera(self) -> None:
        if self.sessao is None or self.sessao.encerrada or self.app.pipeline is None:
            return
        self._seq_visto = -1
        self.app.camera.iniciar(self._processar)

    def _processar(self, frame):
        """Thread da câmera: só o pipeline e a conversão (sem banco, sem QML)."""
        res = self.app.pipeline.processar(frame, extrair_embedding=False)
        return res, bgr_para_qimage(frame)

    @Slot()
    def tentarCamera(self) -> None:
        self._ligar_camera()

    @Slot()
    def _quadro(self) -> None:
        sessao = self.sessao
        if not self._ativo or sessao is None or sessao.encerrada:
            return
        pacote = self.app.camera.ultimo()
        if pacote is None or pacote.seq == self._seq_visto or pacote.saida is None:
            return
        self._seq_visto = pacote.seq
        res, qimg = pacote.saida
        try:
            sessao.passo(pacote.frame, res)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._definir("status", f"Erro ao gravar a amostra: {e}")
            self._definir("statusTipo", "erro")
            return
        tipo = _TIPO_COR.get(tuple(sessao.cor), "neutro")
        self._definir("status", _sem_acento_para_texto(sessao.status))
        self._definir("statusTipo", tipo)
        pose = sessao.pose if sessao.pose in INSTRUCOES_POSE else INSTRUCOES_POSE[0]
        self._definir("poseIndice", INSTRUCOES_POSE.index(pose))
        self._definir("pose", POSES[INSTRUCOES_POSE.index(pose)])
        self._definir("nRostos", len(res.rostos))
        p = res.principal
        if p is not None and len(res.rostos) == 1:
            self._definir("nitidez", round(float(p.qualidade.nitidez), 1))
            self._definir("brilho", round(float(p.qualidade.brilho), 1))
            self._definir("qualidadeOk", bool(p.qualidade.aprovada))
        else:
            self._definir("qualidadeOk", False)
        self.video.definir(qimg, self._caixas(res, tipo))
        self.app.camera.atualizar_fps(pacote.fps)
        self._sincronizar_miniaturas()
        self._definir("capturadas", sessao.capturadas)
        if sessao.capturou_agora:
            self.amostraCapturada.emit(sessao.capturadas)

    def _caixas(self, res, tipo: str) -> list[dict]:
        caixas = []
        if len(res.rostos) > 1:
            for rp in res.rostos:
                r = rp.rosto
                caixas.append({"x": r.x, "y": r.y, "w": r.w, "h": r.h, "cor": tema.VERMELHO, "rotulo": "", "pontos": []})
        elif res.rostos:
            rp = res.principal
            r = rp.rosto
            ok = rp.qualidade.aprovada
            caixas.append({"x": r.x, "y": r.y, "w": r.w, "h": r.h, "cor": _COR_TIPO.get(tipo, tema.ACENTO),
                           "rotulo": "Qualidade OK" if ok else "",
                           "pontos": [r.olho_dir, r.olho_esq, r.nariz, r.boca_dir, r.boca_esq] if ok else []})
        return caixas

    def _sincronizar_miniaturas(self) -> None:
        sessao = self.sessao
        n = self._v["miniaturas"]
        novas = sessao.miniaturas[n:]
        if not novas:
            return
        for i, recorte in enumerate(novas, start=n):
            try:
                self.app.imagens.guardar(f"cadastro/{i}", _miniatura(recorte))
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        self._definir("miniaturas", len(sessao.miniaturas))

    @Slot()
    def cancelar(self) -> None:
        """Desfaz o cadastro em andamento (usuário e amostras já gravadas) e desliga a câmera."""
        sessao, self.sessao = self.sessao, None
        self._dados_pendentes = None
        if sessao is not None and not sessao.encerrada:
            try:
                sessao.cancelar()
            except Exception as e:  # noqa: BLE001
                self._erro("", f"Falha ao desfazer o cadastro: {e}")
        self._encerrar()
        self._zerar_progresso(config.AMOSTRAS_POR_CADASTRO)
        self.app.notificar("info", "Cadastro cancelado. Nada foi gravado.")

    @Slot()
    def concluir(self) -> None:
        sessao = self.sessao
        if sessao is None:
            return
        self.sessao = None
        try:
            usuario = sessao.concluir()
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            usuario = None
            self._erro("", f"Falha ao concluir o cadastro: {e}")
        self._encerrar()
        if usuario is None:
            self.app.notificar("aviso", "Nenhuma amostra capturada: o cadastro foi desfeito.")
            return
        self._anunciar_sucesso(usuario, sessao.capturadas, [])

    def _encerrar(self) -> None:
        self.app.camera.parar()
        self._definir("fase", "formulario")
        self._definir("pausada", False)
        self.video.limpar()

    def _anunciar_sucesso(self, usuario, n: int, avisos: list[str]) -> None:
        resumidos = []
        for a in avisos[:MAX_AVISOS]:
            caminho, sep, resto = a.partition(": ")
            resumidos.append(f"{Path(caminho).name}: {resto}" if sep and Path(caminho).suffix else a)
        if len(avisos) > MAX_AVISOS:
            resumidos.append(f"… e mais {len(avisos) - MAX_AVISOS} aviso(s)")
        self._definir("sucesso", {
            "nome": usuario.nome, "matricula": usuario.matricula, "cargo": usuario.cargo or "",
            "nivel": int(usuario.nivel), "nivelDescricao": config.NIVEIS.get(usuario.nivel, ""),
            "area": config.AREAS.get(usuario.nivel, ""), "amostras": int(n), "avisos": resumidos,
        })
        self.app.notificar("ok", f"{usuario.nome} cadastrado com {n} amostra(s).")
        self.app.banco_alterado()

    # ------------------------------------------------------------------ cadastro por fotos
    @Slot(str, str, str, int, "QVariantList", result=bool)
    def cadastrarPorFotos(self, nome: str, matricula: str, cargo: str, nivel: int, urls: list) -> bool:
        if self.capturando or self._v["fase"] == "importando":
            return False
        caminhos = [_caminho_local(str(u)) for u in (urls or []) if str(u)]
        if not caminhos:
            self._erro("", "Nenhuma foto escolhida.")
            return False
        dados = self._validar(nome, matricula, cargo, nivel)
        if dados is None:
            return False
        if self.app.pipeline is None:
            self._erro("", "Os modelos ainda estão carregando. Tente novamente em instantes.")
            return False
        self._definir("sucesso", {})
        self._definir("fase", "importando")
        self._definir("status", f"Processando {len(caminhos)} foto(s)…")
        caminho_db, pipeline = self.app.banco.caminho, self.app.pipeline
        em_memoria = str(caminho_db) == ":memory:"
        banco_principal = self.app.banco

        def trabalho():
            banco = banco_principal if em_memoria else Banco(caminho_db)
            try:
                return cadastrar_de_imagens(banco, pipeline, dados, caminhos)
            finally:
                if banco is not banco_principal:
                    banco.fechar()

        def terminou(resultado, erro: str) -> None:
            self._definir("fase", "formulario")
            if erro:
                self._erro("", f"Cadastro por fotos falhou: {erro}")
                return
            usuario, n, avisos = resultado
            usuario = self.app.banco.obter_usuario(usuario.id) or usuario   # relê pela conexão principal
            self._anunciar_sucesso(usuario, n, avisos)

        if em_memoria:      # banco em memória (testes): a conexão não pode mudar de thread
            try:
                terminou(trabalho(), "")
            except Exception as e:  # noqa: BLE001
                terminou(None, str(e))
        else:
            self.app.tarefas.executar(trabalho, terminou)
        return True

```

## `cofre/qt/vm_config.py` (232 linhas)

```python
"""ViewModel das configurações: formulário dos parâmetros de `cofre.parametros` com validação,
alterações pendentes, aplicar/descartar, padrões e arquivo `config_usuario.json`."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

import cv2
from PySide6.QtCore import Signal, Slot
from PySide6 import __version__ as versao_pyside

from .. import __version__, config, parametros
from .base import ViewModel, objeto, prop
from .modelos import ModeloLista

# Parâmetros que mudam o comportamento de segurança: a tela os destaca.
SEGURANCA = {"LIMIAR_COSSENO", "FRAMES_CONFIRMACAO", "LIVENESS_ATIVO", "LIVENESS_LIMIAR_YAW", "LIVENESS_TIMEOUT_SEG",
             "MAX_TENTATIVAS_FALHAS", "BLOQUEIO_SEG", "BLOQUEAR_MULTIPLOS_ROSTOS"}

# Quando cada parâmetro passa a valer NESTE aplicativo (conferido no código do backend).
# "importacao": Confirmador, DesafioMovimento e ControleTentativas recebem o valor como argumento
# padrão, avaliado quando o módulo é importado; mudar `config` depois não muda nada. Corrigir isso
# mexe em controles de segurança e depende de aprovação, então a tela não deixa editar esses campos.
EFEITO = {
    "LIMIAR_COSSENO": "imediato", "BLOQUEAR_MULTIPLOS_ROSTOS": "imediato", "MIN_NITIDEZ": "imediato",
    "INTERVALO_AMOSTRAS_SEG": "imediato", "TEMPO_EXIBIR_RESULTADO_SEG": "imediato",
    "SESSAO_LIBERADA_SEG": "imediato", "POSE_MAX_YAW": "imediato", "POSE_MAX_ROLL_GRAUS": "imediato",
    "POSE_RAZAO_NARIZ_MAX": "imediato", "POSE_RAZAO_NARIZ_MIN": "imediato",
    "AMOSTRAS_POR_CADASTRO": "cadastro", "CAMERA_INDEX": "camera", "ESPELHAR_CAMERA": "camera",
    "LIVENESS_ATIVO": "abertura",
    "FRAMES_CONFIRMACAO": "importacao", "LIVENESS_LIMIAR_YAW": "importacao", "LIVENESS_TIMEOUT_SEG": "importacao",
    "MAX_TENTATIVAS_FALHAS": "importacao", "BLOQUEIO_SEG": "importacao",
}
TEXTO_EFEITO = {
    "imediato": "Vale assim que aplicar",
    "cadastro": "Vale no próximo cadastro",
    "camera": "Vale na próxima vez que a câmera ligar",
    "abertura": "Define o estado inicial do terminal ao abrir o aplicativo; no terminal há um interruptor",
    "importacao": "Somente leitura: o backend fixa este valor quando o programa é carregado",
}
MENSAGEM_APLICADO = ("Aplicado. Cada campo indica quando passa a valer; os de somente leitura "
                     "não mudam nesta versão.")


class ConfigVM(ViewModel):
    pendentesMudou = Signal()
    mensagemMudou = Signal()
    mensagemTipoMudou = Signal()
    arquivoExisteMudou = Signal()
    configAplicada = Signal()

    pendentes = prop(int, "pendentes", pendentesMudou)
    mensagem = prop(str, "mensagem", mensagemMudou)
    mensagemTipo = prop(str, "mensagemTipo", mensagemTipoMudou)
    arquivoExiste = prop(bool, "arquivoExiste", arquivoExisteMudou)
    modeloCampos = objeto("campos")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(pendentes=0, mensagem="", mensagemTipo="info", arquivoExiste=False)
        self.padroes = parametros.valores_atuais()          # valores do módulo ao abrir o aplicativo
        self._form = dict(self.padroes)
        self.campos = ModeloLista(["id", "chave", "rotulo", "explicacao", "tipo", "minimo", "maximo", "passo", "casas",
                                   "secao", "valor", "texto", "aplicado", "textoAplicado", "padrao", "alterado",
                                   "diferePadrao", "seguranca", "efeito", "textoEfeito", "editavel"], self)
        self._atualizar()

    # ------------------------------------------------------------------ carga inicial
    def carregar_inicial(self) -> None:
        """Na abertura do aplicativo: se o usuário salvou um arquivo, aplica (como a tela antiga fazia
        ao ser aberta). Arquivo inválido é ignorado com aviso, sem aplicar nada pela metade."""
        caminho = parametros.caminho_arquivo()
        if not caminho.exists():
            self._msg("Valores atuais do sistema. Nenhum arquivo de configuração salvo.", "info")
            return
        try:
            lidos = parametros.ler_arquivo(caminho)
            lidos = {k: v for k, v in lidos.items() if EFEITO.get(k) != "importacao"}
            parametros.aplicar({**parametros.valores_atuais(), **lidos})
        except (OSError, ValueError, TypeError, KeyError) as e:
            self._msg(f"Arquivo {caminho.name} ignorado: {e}", "erro")
            return
        self._form = parametros.valores_atuais()
        self._atualizar()
        self._msg(f"Configuração carregada de {caminho.name} e aplicada.", "ok")

    # ------------------------------------------------------------------ estado
    def _msg(self, texto: str, tipo: str) -> None:
        self._definir("mensagem", texto)
        self._definir("mensagemTipo", tipo)

    def _atualizar(self) -> None:
        atuais = parametros.valores_atuais()
        itens, pendentes = [], 0
        for i, c in enumerate(parametros.CAMPOS):
            valor, aplicado, padrao = self._form[c.chave], atuais[c.chave], self.padroes[c.chave]
            alterado = valor != aplicado
            pendentes += alterado
            itens.append({
                "id": i, "chave": c.chave, "rotulo": c.rotulo, "explicacao": c.explicacao, "tipo": c.tipo,
                "minimo": float(c.minimo), "maximo": float(c.maximo), "passo": float(c.passo), "casas": c.casas,
                "secao": c.secao, "valor": valor, "texto": c.formatar(valor), "aplicado": aplicado,
                "textoAplicado": c.formatar(aplicado), "padrao": padrao, "alterado": bool(alterado),
                "diferePadrao": aplicado != padrao, "seguranca": c.chave in SEGURANCA,
                "efeito": EFEITO.get(c.chave, "imediato"), "textoEfeito": TEXTO_EFEITO[EFEITO.get(c.chave, "imediato")],
                "editavel": EFEITO.get(c.chave) != "importacao",
            })
        self.campos.definir(itens)
        self._definir("pendentes", int(pendentes))
        self._definir("arquivoExiste", parametros.caminho_arquivo().exists())

    @Slot(result="QVariantList")
    def secoes(self) -> list:
        vistas: list[str] = []
        for c in parametros.CAMPOS:
            if c.secao not in vistas:
                vistas.append(c.secao)
        return vistas

    @Slot(result=str)
    def caminhoArquivo(self) -> str:
        return str(parametros.caminho_arquivo())

    # ------------------------------------------------------------------ edição
    @Slot(str, "QVariant", result=bool)
    def definir(self, chave: str, valor) -> bool:
        campo = parametros.CAMPOS_POR_CHAVE.get(chave)
        if campo is None:
            return False
        if EFEITO.get(chave) == "importacao":
            self._msg(f"\"{campo.rotulo}\" é somente leitura nesta versão.", "aviso")
            return False
        try:
            if campo.tipo != "bool" and isinstance(valor, str):
                valor = float(valor.replace(",", "."))
            self._form[chave] = campo.normalizar(valor)
        except (ValueError, TypeError) as e:
            self._msg(f"Valor inválido em \"{campo.rotulo}\": {e}", "erro")
            self._atualizar()
            return False
        self._atualizar()
        if self._v["pendentes"]:
            self._msg(f"{self._v['pendentes']} alteração(ões) pendente(s). Clique em Aplicar para valer.", "aviso")
        else:
            self._msg("Sem alterações pendentes.", "info")
        return True

    @Slot(result=bool)
    def aplicar(self) -> bool:
        try:
            self._form = parametros.aplicar(self._form)
        except (ValueError, KeyError) as e:
            self._msg(f"Valor inválido: {e}", "erro")
            return False
        self._atualizar()
        self._msg(MENSAGEM_APLICADO, "ok")
        self.app.notificar("ok", "Configurações aplicadas.")
        self.configAplicada.emit()
        return True

    @Slot()
    def descartar(self) -> None:
        self._form = parametros.valores_atuais()
        self._atualizar()
        self._msg("Alterações descartadas.", "info")

    @Slot()
    def restaurarPadroes(self) -> None:
        atuais = parametros.valores_atuais()
        self._form = {k: (atuais[k] if EFEITO.get(k) == "importacao" else v) for k, v in self.padroes.items()}
        self._atualizar()
        self._msg("Padrões restaurados no formulário. Clique em Aplicar para valer.", "aviso")

    @Slot(result=bool)
    def salvar(self) -> bool:
        try:
            caminho = parametros.salvar_arquivo(self._form)
        except (OSError, ValueError, KeyError) as e:
            self._msg(f"Não foi possível salvar o arquivo: {e}", "erro")
            return False
        self._atualizar()
        self._msg(f"Salvo em {caminho.name}. O arquivo é aplicado ao abrir o aplicativo.", "ok")
        self.app.notificar("ok", f"Configuração salva em {caminho.name}")
        return True

    @Slot(result=bool)
    def carregar(self) -> bool:
        caminho = parametros.caminho_arquivo()
        if not caminho.exists():
            self._msg(f"Arquivo não encontrado: {caminho}", "erro")
            return False
        try:
            lidos = parametros.ler_arquivo(caminho)
        except (OSError, ValueError, TypeError) as e:
            self._msg(f"Arquivo inválido ({caminho.name}): {e}", "erro")
            return False
        self._form.update({k: v for k, v in lidos.items() if EFEITO.get(k) != "importacao"})
        if self.aplicar():
            self._msg(f"Carregado de {caminho.name} e aplicado. {MENSAGEM_APLICADO}", "ok")
            return True
        return False

    # ------------------------------------------------------------------ informações
    @Slot(result="QVariantList")
    def informacoes(self) -> list:
        def arquivo(p: Path) -> str:
            try:
                return f"{p.name} ({p.stat().st_size / 1024:.0f} KB)" if p.exists() else f"{p.name} (não encontrado)"
            except OSError:
                return str(p)
        banco = getattr(self.app, "banco", None)
        return [
            {"nome": "Banco de dados", "valor": str(getattr(banco, "caminho", config.DB_PATH))},
            {"nome": "Pasta de dados", "valor": str(config.DATA_DIR)},
            {"nome": "Arquivo de configuração", "valor": str(parametros.caminho_arquivo())},
            {"nome": "Detecção (YuNet)", "valor": arquivo(Path(config.MODELO_DETECCAO))},
            {"nome": "Reconhecimento (SFace)", "valor": arquivo(Path(config.MODELO_RECONHECIMENTO))},
            {"nome": "Captura", "valor": f"{config.CAMERA_LARGURA}×{config.CAMERA_ALTURA}, processamento em "
                                         f"{config.LARGURA_PROCESSAMENTO} px"},
            {"nome": "Embedding", "valor": "rosto alinhado 112×112 → vetor de 128 dimensões"},
            {"nome": "OpenCV", "valor": cv2.__version__},
            {"nome": "Qt / PySide6", "valor": versao_pyside},
            {"nome": "Python", "valor": f"{platform.python_version()} ({sys.platform})"},
            {"nome": "Versão do aplicativo", "valor": __version__},
        ]

    @Slot(result="QVariantList")
    def niveis(self) -> list:
        return [{"nivel": n, "descricao": config.NIVEIS[n], "area": config.AREAS.get(n, "–")}
                for n in sorted(config.NIVEIS)]

```

## `cofre/qt/vm_sessao.py` (133 linhas)

```python
"""ViewModel da área liberada: a tela que abre DEPOIS de uma autenticação concedida no terminal.

Só abre a partir de uma `Decisao` do backend (`TerminalAutenticacao.decisao_atual`) com
`concedido=True`, e ainda reconfere no banco que a pessoa existe, está ativa e tem nível
suficiente para a área pedida. O QML não consegue abrir a sessão nem ler conteúdo de uma área
acima do nível: `conteudo(n)` devolve vazio para o que não foi liberado."""

from __future__ import annotations

import traceback
from datetime import datetime

from PySide6.QtCore import QTimer, Signal, Slot

from .. import areas, config
from .base import ViewModel, prop


class SessaoVM(ViewModel):
    ativaMudou = Signal()
    nomeMudou = Signal()
    cargoMudou = Signal()
    nivelUsuarioMudou = Signal()
    nivelDescricaoMudou = Signal()
    areaSolicitadaMudou = Signal()
    areasMudou = Signal()
    tempoRestanteMudou = Signal()
    tempoTotalMudou = Signal()
    abertaEmMudou = Signal()
    similaridadeMudou = Signal()
    aberta = Signal()
    encerrada = Signal(str)          # motivo: "usuario" | "tempo" | "sistema"

    ativa = prop(bool, "ativa", ativaMudou)
    nome = prop(str, "nome", nomeMudou)
    cargo = prop(str, "cargo", cargoMudou)
    nivelUsuario = prop(int, "nivelUsuario", nivelUsuarioMudou)
    nivelDescricao = prop(str, "nivelDescricao", nivelDescricaoMudou)
    areaSolicitada = prop(int, "areaSolicitada", areaSolicitadaMudou)
    areas = prop("QVariantList", "areas", areasMudou)
    tempoRestante = prop(int, "tempoRestante", tempoRestanteMudou)
    tempoTotal = prop(int, "tempoTotal", tempoTotalMudou)
    abertaEm = prop(str, "abertaEm", abertaEmMudou)
    similaridade = prop(float, "similaridade", similaridadeMudou)

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(ativa=False, nome="", cargo="", nivelUsuario=0, nivelDescricao="", areaSolicitada=0,
                      areas=[], tempoRestante=0, tempoTotal=int(config.SESSAO_LIBERADA_SEG), abertaEm="",
                      similaridade=-1.0)
        self._liberadas: list[int] = []
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tique)

    # ------------------------------------------------------------------ abertura (só pelo backend)
    def abrir(self, decisao, nivel_exigido: int) -> bool:
        """Chamado pelo TerminalVM quando o terminal entra em RESULTADO. Negação por padrão:
        qualquer dado faltando ou inconsistente mantém a sessão fechada."""
        if self._v["ativa"] or decisao is None or not getattr(decisao, "concedido", False):
            return False
        ident = decisao.identificacao
        if ident is None or not ident.reconhecido or ident.usuario is None:
            return False
        try:
            u = self.app.banco.obter_usuario(ident.usuario.id)     # relê: nível e situação atuais
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return False
        nivel_exigido = int(nivel_exigido)
        if u is None or not u.ativo or nivel_exigido not in config.NIVEIS or u.nivel < nivel_exigido:
            return False
        self._liberadas = areas.areas_liberadas(u.nivel)
        if nivel_exigido not in self._liberadas:
            return False
        self._definir("nome", u.nome)
        self._definir("cargo", u.cargo or "")
        self._definir("nivelUsuario", int(u.nivel))
        self._definir("nivelDescricao", config.NIVEIS.get(u.nivel, ""))
        self._definir("areaSolicitada", nivel_exigido)
        self._definir("areas", areas.resumo_areas(u.nivel))
        self._definir("similaridade", round(float(ident.similaridade), 3))
        self._definir("abertaEm", datetime.now().strftime("%H:%M:%S"))
        self._definir("tempoTotal", int(config.SESSAO_LIBERADA_SEG))
        self._definir("tempoRestante", int(config.SESSAO_LIBERADA_SEG))
        self._definir("ativa", True)
        self._timer.start()
        self.aberta.emit()
        return True

    # ------------------------------------------------------------------ uso pelo QML
    @Slot(int, result="QVariantMap")
    def conteudo(self, nivel: int) -> dict:
        """Conteúdo da área, só se a sessão estiver ativa e a área liberada para este usuário."""
        if not self._v["ativa"] or int(nivel) not in self._liberadas:
            return {}
        try:
            return areas.conteudo(int(nivel))
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return {}

    @Slot(int, result=bool)
    def liberada(self, nivel: int) -> bool:
        return self._v["ativa"] and int(nivel) in self._liberadas

    @Slot()
    def renovar(self) -> None:
        """Qualquer interação na área renova o tempo de inatividade."""
        if self._v["ativa"]:
            self._definir("tempoRestante", int(config.SESSAO_LIBERADA_SEG))

    @Slot()
    def encerrar(self) -> None:
        self._fechar("usuario")

    def _tique(self) -> None:
        restante = self._v["tempoRestante"] - 1
        if restante <= 0:
            self._fechar("tempo")
            return
        self._definir("tempoRestante", restante)

    def _fechar(self, motivo: str) -> None:
        if not self._v["ativa"]:
            return
        self._timer.stop()
        self._liberadas = []
        self._definir("ativa", False)
        self._definir("tempoRestante", 0)
        if motivo == "tempo":
            self.app.notificar("info", f"Sessão de {self._v['nome']} encerrada por inatividade.")
        self.encerrada.emit(motivo)

```

## `cofre/qt/vm_terminal.py` (505 linhas)

```python
"""
ViewModel do terminal de acesso.

Divisão de trabalho (igual à da interface customtkinter):
  - thread da câmera: `pipeline.processar` + conversão do quadro para QImage
    (e, com o painel didático ligado, as imagens de cada fase);
  - thread da interface: `TerminalAutenticacao.passo()` (máquina de estados), leitura do
    `status()` e exposição ao QML. O `passo()` grava o log de acesso no SQLite, cuja
    conexão só aceita a thread que a criou.

A autorização é sempre a do backend: a interface só mostra "autorizado" quando o
`TerminalAutenticacao` está em RESULTADO com uma decisão `concedido`. Qualquer falha
no processamento deixa o painel em estado neutro, nunca em "autorizado".
"""

from __future__ import annotations

import time
import traceback

import cv2
import numpy as np
from PySide6.QtCore import Property, QTimer, Signal, Slot

from .. import config
from ..autenticacao import Estado, TerminalAutenticacao
from ..liveness import EtapaLiveness
from . import tema
from .base import ViewModel, objeto, prop
from .imagens import bgr_para_qimage
from .modelos import ModeloLista
from .video import FonteVideo

INTERVALO_CHECAGEM_BANCO_MS = 1000
INTERVALO_DIDATICO_SEG = 0.12          # painel didático a ~8 quadros/s (economiza CPU)
LADO_ETAPA = 240
PASSO_LIVENESS = {EtapaLiveness.VIRAR_ESQUERDA: 0, EtapaLiveness.VIRAR_DIREITA: 1, EtapaLiveness.VOLTAR_CENTRO: 2,
                  EtapaLiveness.APROVADO: 3}


def _reduzir(img, lado: int = LADO_ETAPA):
    h, w = img.shape[:2]
    esc = lado / max(h, w)
    if esc >= 1:
        return img
    return cv2.resize(img, (max(1, int(w * esc)), max(1, int(h * esc))), interpolation=cv2.INTER_AREA)


class TerminalVM(ViewModel):
    estadoMudou = Signal()
    nivelMudou = Signal()
    areaMudou = Signal()
    livenessMudou = Signal()
    didaticoMudou = Signal()
    similaridadeMudou = Signal()
    progressoMudou = Signal()
    livenessInstrucaoMudou = Signal()
    livenessRestanteMudou = Signal()
    livenessTotalMudou = Signal()
    livenessPassoMudou = Signal()
    bloqueadoRestanteMudou = Signal()
    bloqueioTotalMudou = Signal()
    resultadoTipoMudou = Signal()
    resultadoConcedidoMudou = Signal()
    resultadoTituloMudou = Signal()
    resultadoNomeMudou = Signal()
    resultadoMensagemMudou = Signal()
    resultadoSimilaridadeMudou = Signal()
    resultadoNivelMudou = Signal()
    galeriaMudou = Signal()
    usuariosAtivosMudou = Signal()
    nRostosMudou = Signal()
    avisoMudou = Signal()
    orientacaoMudou = Signal()
    poseYawMudou = Signal()
    poseRollMudou = Signal()
    poseRazaoMudou = Signal()
    assinaturaMudou = Signal()
    assinaturaReferenciaMudou = Signal()
    erroMudou = Signal()
    etapasMudou = Signal()
    decisaoTomada = Signal(bool, str)        # (concedido, resultado) para animações / feedback

    estado = prop(str, "estado", estadoMudou)
    nivel = prop(int, "nivel", nivelMudou)
    area = prop(str, "area", areaMudou)
    liveness = prop(bool, "liveness", livenessMudou)
    didatico = prop(bool, "didatico", didaticoMudou)
    similaridade = prop(float, "similaridade", similaridadeMudou)       # -1 = sem rosto
    progresso = prop(float, "progresso", progressoMudou)
    livenessInstrucao = prop(str, "livenessInstrucao", livenessInstrucaoMudou)
    livenessRestante = prop(float, "livenessRestante", livenessRestanteMudou)
    livenessTotal = prop(float, "livenessTotal", livenessTotalMudou)
    livenessPasso = prop(int, "livenessPasso", livenessPassoMudou)
    bloqueadoRestante = prop(float, "bloqueadoRestante", bloqueadoRestanteMudou)
    bloqueioTotal = prop(float, "bloqueioTotal", bloqueioTotalMudou)
    resultadoTipo = prop(str, "resultadoTipo", resultadoTipoMudou)
    resultadoConcedido = prop(bool, "resultadoConcedido", resultadoConcedidoMudou)
    resultadoTitulo = prop(str, "resultadoTitulo", resultadoTituloMudou)
    resultadoNome = prop(str, "resultadoNome", resultadoNomeMudou)
    resultadoMensagem = prop(str, "resultadoMensagem", resultadoMensagemMudou)
    resultadoSimilaridade = prop(float, "resultadoSimilaridade", resultadoSimilaridadeMudou)
    resultadoNivel = prop(int, "resultadoNivel", resultadoNivelMudou)
    galeria = prop(int, "galeria", galeriaMudou)
    usuariosAtivos = prop(int, "usuariosAtivos", usuariosAtivosMudou)
    nRostos = prop(int, "nRostos", nRostosMudou)
    aviso = prop(str, "aviso", avisoMudou)
    orientacao = prop(str, "orientacao", orientacaoMudou)     # "" ou instrução de pose/qualidade do backend
    poseYaw = prop(float, "poseYaw", poseYawMudou)            # medidas dos 5 pontos (-99 = sem rosto)
    poseRoll = prop(float, "poseRoll", poseRollMudou)
    poseRazao = prop(float, "poseRazao", poseRazaoMudou)
    assinatura = prop("QVariantList", "assinatura", assinaturaMudou)            # embedding ao vivo (128)
    assinaturaReferencia = prop("QVariantList", "assinaturaReferencia", assinaturaReferenciaMudou)
    erro = prop(str, "erro", erroMudou)
    ultimosAcessos = objeto("acessos")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        nivel = 3
        self._iniciar(
            estado=Estado.AGUARDANDO.value, nivel=nivel, area=config.AREAS[nivel],
            liveness=bool(config.LIVENESS_ATIVO), didatico=False, similaridade=-1.0, progresso=0.0,
            livenessInstrucao="", livenessRestante=0.0, livenessTotal=float(config.LIVENESS_TIMEOUT_SEG),
            livenessPasso=0, bloqueadoRestante=0.0, bloqueioTotal=float(config.BLOQUEIO_SEG),
            resultadoTipo="", resultadoConcedido=False, resultadoTitulo="", resultadoNome="",
            resultadoMensagem="", resultadoSimilaridade=-1.0, resultadoNivel=0,
            galeria=0, usuariosAtivos=0, nRostos=0, aviso="", erro="", orientacao="",
            poseYaw=-99.0, poseRoll=-99.0, poseRazao=-99.0, assinatura=[], assinaturaReferencia=[],
        )
        self.terminal: TerminalAutenticacao | None = None
        self.video = FonteVideo("camera", self)
        self._etapas: list[FonteVideo] = []
        self._etapa_por_chave: dict[str, FonteVideo] = {}
        self._didatico_thread = False          # lido pela thread da câmera
        self._ultimo_didatico = 0.0            # idem
        self._ultima_assinatura = 0.0
        self.acessos = ModeloLista(["id", "hora", "nome", "resultado", "titulo", "concedido", "nivelExigido",
                                    "similaridade"], self)
        self._ativo = False
        self._seq_visto = -1
        self._versao_banco: int | None = None
        self._timer_banco = QTimer(self)
        self._timer_banco.setInterval(INTERVALO_CHECAGEM_BANCO_MS)
        self._timer_banco.timeout.connect(self._checar_banco)
        aplicacao.camera.quadroDisponivel.connect(self._quadro)
        aplicacao.camera.erroProcessamento.connect(self._erro_processamento)

    # ------------------------------------------------------------------ propriedades extras
    def _get_etapas(self) -> list:
        return list(self._etapas)

    etapas = Property("QVariantList", _get_etapas, notify=etapasMudou)

    def _get_limiar(self) -> float:
        return float(config.LIMIAR_COSSENO)

    limiar = Property(float, _get_limiar, notify=similaridadeMudou)

    fonteVideo = objeto("video")

    # ------------------------------------------------------------------ ciclo de vida
    def ativar(self) -> None:
        self._ativo = True
        self._seq_visto = -1
        if self.terminal is not None:
            self.terminal.definir_nivel(self._v["nivel"])     # volta a AGUARDANDO ao reabrir a tela
        self._definir("erro", "")
        self.atualizar_acessos()
        self.verificar_usuarios()
        self._timer_banco.start()
        self._abrir_camera()

    def pausar(self) -> None:
        """Área liberada aberta: desliga a câmera sem perder o terminal (e o contador de falhas).
        O veredito fica na tela, por baixo da área, até a sessão encerrar."""
        self.app.camera.parar()
        self.video.limpar()
        self._atualizar_pose_e_assinatura(None)

    def retomar(self) -> None:
        if self._ativo and self.terminal is not None:
            self.terminal.encerrar_resultado()    # senão o RESULTADO ainda em exibição reabriria a sessão
            self._limpar_status()                  # nada de "autorizado" antigo enquanto a câmera reabre
            self._abrir_camera()

    def desativar(self) -> None:
        self._ativo = False
        self._timer_banco.stop()
        self.app.camera.parar()
        self.video.limpar()
        for e in self._etapas:
            e.limpar()
        self._limpar_status()

    def ao_pipeline_pronto(self) -> None:
        if self._ativo:
            self._abrir_camera()

    def ao_banco_alterado(self) -> None:
        self.recarregarGaleria(silencioso=True)

    def _abrir_camera(self) -> None:
        if not self._ativo or self.app.pipeline is None:
            return
        if self.terminal is None:
            self.terminal = TerminalAutenticacao(self.app.banco, self.app.pipeline, nivel_exigido=self._v["nivel"],
                                                 liveness=self._v["liveness"], didatico=self._v["didatico"])
            self._versao_banco = self._ler_versao()
            self.verificar_usuarios()
        self._seq_visto = -1
        self.app.camera.iniciar(self._processar)

    # ------------------------------------------------------------------ thread da câmera
    def _processar(self, frame):
        """Roda NA THREAD DA CÂMERA: só a parte cara. Nada de banco nem de objetos do QML aqui."""
        res = self.app.pipeline.processar(frame)
        qimg = bgr_para_qimage(frame)
        etapas = None
        agora = time.monotonic()
        if self._didatico_thread and agora - self._ultimo_didatico >= INTERVALO_DIDATICO_SEG:
            self._ultimo_didatico = agora
            etapas = [(chave, bgr_para_qimage(_reduzir(img))) for chave, img in res.etapas_didaticas().items()]
        return res, qimg, etapas

    # ------------------------------------------------------------------ thread da interface
    @Slot()
    def _quadro(self) -> None:
        if not self._ativo or self.terminal is None:
            return
        pacote = self.app.camera.ultimo()
        if pacote is None or pacote.seq == self._seq_visto or pacote.saida is None:
            return
        self._seq_visto = pacote.seq
        res, qimg, etapas = pacote.saida
        term = self.terminal
        try:
            term.passo(pacote.frame, res.principal, len(res.rostos))
            st = term.status()
            ident = term.identificacao_atual(res.principal)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._definir("erro", f"Erro no processamento: {e}")
            self._limpar_status()                 # nunca deixa um "autorizado" antigo na tela
            self.video.definir(qimg, [])
            return
        anterior = self._v["estado"]
        self.video.definir(qimg, self._caixas(res, st, ident))
        self._atualizar_pose_e_assinatura(res.principal)
        if etapas is not None:
            self._atualizar_etapas(etapas)
        self.app.camera.atualizar_fps(pacote.fps)
        self._aplicar_status(st, ident, len(res.rostos))
        if self._v["erro"]:
            self._definir("erro", "")
        estado = st["estado"]
        if estado == Estado.RESULTADO.value and anterior != Estado.RESULTADO.value:
            self.atualizar_acessos()             # a decisão (e um eventual bloqueio) acabou de ser gravada
            d = st.get("decisao") or {}
            self.decisaoTomada.emit(bool(d.get("concedido")), str(d.get("resultado", "")))
            if d.get("concedido"):
                # a área liberada abre só a partir da decisão do backend, já gravada no log
                self.app.sessao_vm.abrir(term.decisao_atual, term.nivel_exigido)

    @Slot(str)
    def _erro_processamento(self, texto: str) -> None:
        if self._ativo:
            self._definir("erro", texto)

    def _atualizar_pose_e_assinatura(self, principal) -> None:
        """Leituras só para exibição: medidas de pose dos 5 pontos e o vetor de 128 dimensões
        ao vivo ao lado da amostra da galeria mais parecida. Nada aqui influencia a decisão."""
        if principal is None:
            if self._v["poseYaw"] != -99.0:
                self._definir("poseYaw", -99.0)
                self._definir("poseRoll", -99.0)
                self._definir("poseRazao", -99.0)
            if self._v["assinatura"]:
                self._definir("assinatura", [])
                self._definir("assinaturaReferencia", [])
            return
        r = principal.rosto
        self._definir("poseYaw", round(float(r.yaw()), 2))
        self._definir("poseRoll", round(float(r.roll()), 1))
        self._definir("poseRazao", round(float(r.razao_nariz()), 2))
        agora = time.time()
        if agora - self._ultima_assinatura < 0.15:
            return
        self._ultima_assinatura = agora
        emb = np.asarray(principal.embedding, dtype=np.float32).reshape(-1)
        escala = float(np.abs(emb).max() or 1.0)
        self._definir("assinatura", [round(float(v) / escala, 3) for v in emb])
        ref = self.terminal.reconhecedor.amostra_mais_parecida(emb) if self.terminal is not None else None
        self._definir("assinaturaReferencia",
                      [] if ref is None else [round(float(v) / float(np.abs(ref).max() or 1.0), 3) for v in ref])

    def _caixas(self, res, st: dict, ident) -> list[dict]:
        """Marcações sobre o vídeo: mesma regra de cores do HUD da linha de comando."""
        estado = st["estado"]
        decisao = st.get("decisao")
        caixas = []
        for i, rp in enumerate(res.rostos):
            r = rp.rosto
            cor, rotulo = tema.ACENTO, "Analisando"
            if i == 0 and estado in (Estado.CONFIRMANDO.value, Estado.LIVENESS.value, Estado.RESULTADO.value):
                if ident is not None:
                    # antes da decisão: turquesa = reconhecido; verde fica reservado a "autorizado"
                    cor = tema.ACENTO if ident.reconhecido else tema.VERMELHO
                    nome = ident.usuario.nome if ident.reconhecido else "Não reconhecido"
                    rotulo = f"{nome} · {ident.similaridade:.2f}"
                    if ident.reconhecido:
                        rotulo += f" · N{ident.usuario.nivel}"
                if estado == Estado.RESULTADO.value and decisao is not None:
                    cor = tema.VERDE if decisao.get("concedido") else tema.VERMELHO
            elif i > 0:
                cor, rotulo = tema.VERMELHO, "Pessoa extra"
            if estado == Estado.BLOQUEADO.value:
                cor, rotulo = tema.VERMELHO, "Bloqueado"
            if i == 0 and estado in (Estado.AGUARDANDO.value, Estado.CONFIRMANDO.value) and st.get("orientacao"):
                cor, rotulo = tema.AMARELO, st["orientacao"]       # aviso: pose/qualidade fora do aceitável
            caixas.append({
                "x": r.x, "y": r.y, "w": r.w, "h": r.h, "cor": cor, "rotulo": rotulo,
                "pontos": [r.olho_dir, r.olho_esq, r.nariz, r.boca_dir, r.boca_esq],
                "principal": i == 0,
                "malha": i == 0 and estado in (Estado.AGUARDANDO.value, Estado.CONFIRMANDO.value, Estado.LIVENESS.value),
            })
        return caixas

    def _aplicar_status(self, st: dict, ident, n_rostos: int) -> None:
        term = self.terminal
        self._definir("estado", st["estado"])
        self._definir("nRostos", n_rostos)
        self._definir("progresso", round(float(st["progresso_confirmacao"]), 3))
        self._definir("similaridade", round(float(ident.similaridade), 3) if ident is not None else -1.0)
        self._definir("livenessInstrucao", st["liveness_instrucao"])
        self._definir("orientacao", st.get("orientacao", ""))
        self._definir("livenessRestante", round(float(st["liveness_restante"]), 1))
        self._definir("livenessTotal", float(term.desafio.timeout))
        self._definir("livenessPasso", PASSO_LIVENESS.get(term.desafio.etapa, 0))
        self._definir("bloqueadoRestante", round(float(st["bloqueado_restante"]), 1))
        self._definir("bloqueioTotal", float(term.tentativas.bloqueio))
        self._definir("galeria", int(st["galeria"]))
        d = st.get("decisao")
        if d is None or st["estado"] != Estado.RESULTADO.value:
            self._limpar_resultado()
            return
        decisao = term.decisao_atual
        u = decisao.identificacao.usuario if decisao and decisao.identificacao and decisao.identificacao.reconhecido \
            else None
        self._definir("resultadoTipo", d["resultado"])
        self._definir("resultadoConcedido", bool(d["concedido"]))
        self._definir("resultadoTitulo", tema.TITULO_RESULTADO.get(d["resultado"], d["resultado"]))
        self._definir("resultadoNome", u.nome if u is not None else "")
        self._definir("resultadoNivel", int(u.nivel) if u is not None else 0)
        self._definir("resultadoMensagem", d.get("mensagem") or "")
        sim = d.get("similaridade")
        self._definir("resultadoSimilaridade", round(float(sim), 3) if sim is not None else -1.0)

    def _limpar_resultado(self) -> None:
        self._definir("resultadoConcedido", False)
        self._definir("resultadoTipo", "")
        self._definir("resultadoTitulo", "")
        self._definir("resultadoNome", "")
        self._definir("resultadoNivel", 0)
        self._definir("resultadoMensagem", "")
        self._definir("resultadoSimilaridade", -1.0)

    def _limpar_status(self) -> None:
        self._limpar_resultado()
        self._definir("estado", Estado.AGUARDANDO.value)
        self._definir("similaridade", -1.0)
        self._definir("progresso", 0.0)
        self._definir("nRostos", 0)

    def _atualizar_etapas(self, etapas: list) -> None:
        mudou = False
        presentes = set()
        for chave, qimg in etapas:
            presentes.add(chave)
            fonte = self._etapa_por_chave.get(chave)
            if fonte is None:
                fase, nome = tema.rotulo_etapa(chave)
                fonte = FonteVideo(f"{fase} · {nome}" if fase else nome, self)
                self._etapa_por_chave[chave] = fonte
                self._etapas.append(fonte)
                mudou = True
            fonte.definir(qimg, [])
        for chave, fonte in self._etapa_por_chave.items():
            if chave not in presentes and fonte.temImagem:
                fonte.limpar()                      # fase sem dado neste quadro (ex.: nenhum rosto)
        if mudou:
            self.etapasMudou.emit()

    # ------------------------------------------------------------------ banco
    def _ler_versao(self) -> int | None:
        try:
            return self.app.banco.versao_dados()
        except Exception:  # noqa: BLE001
            return None

    @Slot()
    def _checar_banco(self) -> None:
        """Recarrega a galeria quando outro processo grava no banco (cadastro em outra janela, CLI...)."""
        versao = self._ler_versao()
        anterior, self._versao_banco = self._versao_banco, versao
        if anterior is not None and versao is not None and versao != anterior:
            self.recarregarGaleria(silencioso=True)

    @Slot()
    def recarregarGaleria(self, silencioso: bool = False) -> None:
        try:
            if self.terminal is not None:
                self.terminal.reconhecedor.recarregar()
                total = self.terminal.reconhecedor.total_amostras
            else:
                total = self.app.banco.estatisticas()["amostras"]
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.app.notificar("erro", f"Falha ao recarregar a galeria: {e}")
            return
        self._definir("galeria", int(total))
        self.verificar_usuarios()
        self.atualizar_acessos()
        if not silencioso:
            self.app.notificar("info", f"Galeria recarregada: {total} amostras")

    def verificar_usuarios(self) -> None:
        try:
            ativos = self.app.banco.listar_usuarios(apenas_ativos=True)
            self._definir("usuariosAtivos", len(ativos))
            if self.terminal is not None:
                self._definir("galeria", self.terminal.reconhecedor.total_amostras)
            if not ativos:
                texto = "Nenhum usuário ativo cadastrado: todo rosto será negado."
            elif self.terminal is not None and self.terminal.reconhecedor.total_amostras == 0:
                texto = "Os usuários ativos não têm amostras biométricas. Refaça o cadastro."
            else:
                texto = ""
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            texto = f"Não foi possível consultar os usuários: {e}"
        self._definir("aviso", texto)

    def atualizar_acessos(self) -> None:
        try:
            acessos = self.app.banco.listar_acessos(8)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.app.notificar("erro", f"Falha ao ler o log de acessos: {e}")
            return
        self.acessos.definir([{
            "id": a.id,
            "hora": a.data_hora[11:19] if len(a.data_hora) >= 19 else a.data_hora,
            "nome": a.nome_detectado or "Não identificado",
            "resultado": a.resultado,
            "titulo": tema.ROTULO_CURTO_RESULTADO.get(a.resultado, a.resultado),
            "concedido": a.resultado == "CONCEDIDO",
            "nivelExigido": a.nivel_exigido,
            "similaridade": f"{a.similaridade:.2f}" if a.similaridade is not None else "–",
        } for a in acessos])

    # ------------------------------------------------------------------ controles (QML)
    def _bloqueado(self) -> bool:
        """Durante o bloqueio os controles de área e prova de vida ficam travados (também pelos atalhos)."""
        if self._v["estado"] == "BLOQUEADO":
            self.app.notificar("aviso", "Terminal bloqueado: aguarde o fim da contagem para mudar a configuração.")
            return True
        return False

    @Slot(int)
    def definirNivel(self, nivel: int) -> None:
        if nivel not in config.AREAS or self._bloqueado():
            return
        self._definir("nivel", int(nivel))
        self._definir("area", config.AREAS[int(nivel)])
        if self.terminal is not None:
            self.terminal.definir_nivel(int(nivel))

    @Slot(bool)
    def definirLiveness(self, ativo: bool) -> None:
        if self._bloqueado():
            return
        self._definir("liveness", bool(ativo))
        if self.terminal is not None:
            self.terminal.liveness_ativo = bool(ativo)

    @Slot(bool)
    def definirDidatico(self, ativo: bool) -> None:
        self._definir("didatico", bool(ativo))
        self._didatico_thread = bool(ativo)
        self._ultimo_didatico = 0.0
        if self.terminal is not None:
            self.terminal.didatico = bool(ativo)
        if not ativo:
            for e in self._etapas:
                e.limpar()

    @Slot(result="QVariantMap")
    def limitesPose(self) -> dict:
        return {"yaw": float(config.POSE_MAX_YAW), "roll": float(config.POSE_MAX_ROLL_GRAUS),
                "razaoMin": float(config.POSE_RAZAO_NARIZ_MIN), "razaoMax": float(config.POSE_RAZAO_NARIZ_MAX)}

    @Slot()
    def tentarCamera(self) -> None:
        self._definir("erro", "")
        self._abrir_camera()

```

## `cofre/qt/vm_usuarios.py` (207 linhas)

```python
"""ViewModel da administração de usuários: lista com busca e filtros, níveis, ativação,
remoção (com confirmação no QML) e fotos de referência."""

from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl, Signal, Slot

from .. import config
from .base import ViewModel, objeto, prop
from .modelos import ModeloLista


def _data_curta(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso or "–"


def _iniciais(nome: str) -> str:
    partes = [p for p in (nome or "").split() if p]
    if not partes:
        return "?"
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


class UsuariosVM(ViewModel):
    totalMudou = Signal()
    ativosMudou = Signal()
    porNivelMudou = Signal()
    buscaMudou = Signal()
    filtroNivelMudou = Signal()
    filtroStatusMudou = Signal()
    carregadoMudou = Signal()

    total = prop(int, "total", totalMudou)
    ativos = prop(int, "ativos", ativosMudou)
    porNivel = prop("QVariantList", "porNivel", porNivelMudou)
    busca = prop(str, "busca", buscaMudou)
    filtroNivel = prop(int, "filtroNivel", filtroNivelMudou)          # 0 = todos
    filtroStatus = prop(str, "filtroStatus", filtroStatusMudou)       # todos | ativos | inativos
    carregado = prop(bool, "carregado", carregadoMudou)
    modelo = objeto("lista")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(total=0, ativos=0, porNivel=[0, 0, 0], busca="", filtroNivel=0, filtroStatus="todos",
                      carregado=False)
        self.lista = ModeloLista(["id", "nome", "iniciais", "matricula", "cargo", "nivel", "nivelDescricao", "area",
                                  "ativo", "amostras", "criadoEm", "emCadastro"], self)
        self._todos: list[dict] = []

    def ativar(self) -> None:
        self.recarregar()

    def ao_banco_alterado(self) -> None:
        if self._v["carregado"]:
            self.recarregar()

    # ------------------------------------------------------------------ dados
    @Slot()
    def recarregar(self) -> None:
        try:
            usuarios = self.app.banco.listar_usuarios()
            amostras = {u.id: self.app.banco.contar_amostras(u.id) for u in usuarios}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.app.notificar("erro", f"Falha ao ler o banco: {e}")
            return
        # usuário criado por uma captura de cadastro ainda aberta (pausada em outra tela)
        sessao = getattr(self.app.cadastro, "sessao", None)
        em_cadastro = sessao.usuario.id if sessao is not None and not sessao.encerrada else None
        self._todos = [{
            "id": u.id, "nome": u.nome, "iniciais": _iniciais(u.nome), "matricula": u.matricula,
            "cargo": u.cargo or "", "nivel": int(u.nivel), "nivelDescricao": config.NIVEIS.get(u.nivel, "?"),
            "area": config.AREAS.get(u.nivel, ""), "ativo": bool(u.ativo), "amostras": int(amostras.get(u.id, 0)),
            "criadoEm": _data_curta(u.criado_em), "emCadastro": u.id == em_cadastro,
        } for u in usuarios]
        self._definir("total", len(self._todos))
        self._definir("ativos", sum(1 for u in self._todos if u["ativo"]))
        self._definir("porNivel", [sum(1 for u in self._todos if u["nivel"] == n) for n in sorted(config.NIVEIS)])
        self._definir("carregado", True)
        self._filtrar()

    def _filtrar(self) -> None:
        termo = self._v["busca"].strip().casefold()
        nivel, status = self._v["filtroNivel"], self._v["filtroStatus"]
        itens = []
        for u in self._todos:
            if termo and termo not in u["nome"].casefold() and termo not in u["matricula"].casefold() \
                    and termo not in u["cargo"].casefold():
                continue
            if nivel and u["nivel"] != nivel:
                continue
            if status == "ativos" and not u["ativo"] or status == "inativos" and u["ativo"]:
                continue
            itens.append(u)
        self.lista.definir(itens)

    @Slot(str)
    def definirBusca(self, termo: str) -> None:
        if self._definir("busca", termo or ""):
            self._filtrar()

    @Slot(int)
    def definirFiltroNivel(self, nivel: int) -> None:
        if self._definir("filtroNivel", int(nivel)):
            self._filtrar()

    @Slot(str)
    def definirFiltroStatus(self, status: str) -> None:
        if status in ("todos", "ativos", "inativos") and self._definir("filtroStatus", status):
            self._filtrar()

    @Slot()
    def limparFiltros(self) -> None:
        self._definir("busca", "")
        self._definir("filtroNivel", 0)
        self._definir("filtroStatus", "todos")
        self._filtrar()

    # ------------------------------------------------------------------ ações
    def _obter(self, uid: int):
        """Relê do banco para não agir sobre dado velho."""
        try:
            u = self.app.banco.obter_usuario(int(uid))
        except Exception as e:  # noqa: BLE001
            self.app.notificar("erro", f"Falha ao ler o usuário: {e}")
            return None
        if u is None:
            self.app.notificar("erro", "O usuário selecionado não existe mais.")
            self.recarregar()
        return u

    def _apos(self, texto: str) -> None:
        self.recarregar()
        self.app.notificar("ok", texto)
        self.app.banco_alterado(origem=self)

    @Slot(int, int, result=bool)
    def alterarNivel(self, uid: int, nivel: int) -> bool:
        u = self._obter(uid)
        if u is None or int(nivel) not in config.NIVEIS:
            return False
        if int(nivel) == u.nivel:
            self.app.notificar("info", f"{u.nome} já está no nível {nivel}.")
            return False
        try:
            self.app.banco.alterar_nivel(u.id, int(nivel))
        except Exception as e:  # noqa: BLE001
            self.app.notificar("erro", f"Não foi possível alterar o nível: {e}")
            return False
        self._apos(f"{u.nome}: nível alterado para {nivel} ({config.NIVEIS[int(nivel)]}).")
        return True

    @Slot(int, result=bool)
    def alternarAtivo(self, uid: int) -> bool:
        u = self._obter(uid)
        if u is None or self._em_cadastro(u):
            return False
        try:
            self.app.banco.definir_ativo(u.id, not u.ativo)
        except Exception as e:  # noqa: BLE001
            self.app.notificar("erro", f"Não foi possível alterar o status: {e}")
            return False
        self._apos(f"{u.nome} {'reativado' if not u.ativo else 'desativado'}.")
        return True

    def _em_cadastro(self, u) -> bool:
        sessao = getattr(self.app.cadastro, "sessao", None)
        if sessao is not None and not sessao.encerrada and sessao.usuario.id == u.id:
            self.app.notificar("aviso", f"{u.nome} está com um cadastro em andamento. Conclua ou cancele na tela de cadastro.")
            return True
        return False

    @Slot(int, result=bool)
    def remover(self, uid: int) -> bool:
        """Remove o usuário e as amostras. A confirmação é feita antes, no QML."""
        u = self._obter(uid)
        if u is None or self._em_cadastro(u):
            return False
        try:
            self.app.banco.remover_usuario(u.id)
        except Exception as e:  # noqa: BLE001
            self.app.notificar("erro", f"Não foi possível remover: {e}")
            return False
        self._apos(f"{u.nome} removido do banco.")
        return True

    @Slot(int, result="QVariantList")
    def fotos(self, uid: int) -> list:
        try:
            caminhos = self.app.banco.fotos_do_usuario(int(uid))
        except Exception as e:  # noqa: BLE001
            self.app.notificar("erro", f"Não foi possível listar as fotos: {e}")
            return []
        saida = []
        for c in caminhos:
            p = Path(c)
            if not p.is_absolute():
                p = config.BASE_DIR / p
            saida.append({"url": QUrl.fromLocalFile(str(p)).toString(), "existe": p.exists(), "nome": p.name})
        return saida

```

## `cofre/qt/qml/Cofre/Ui/AcessosPagina.qml` (474 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Auditoria: indicadores, filtros, tabela de tentativas, resumos e detalhe com evidência.
// Somente leitura: nada aqui altera o log de acessos.
Item {
    id: pagina
    readonly property var a: app.acessos
    readonly property bool filtrando: a.busca !== "" || a.filtroResultado !== "" || a.filtroNivel !== 0 || a.periodo !== "tudo"
    readonly property bool compacta: width < 1180

    function porcentagem(x) { return x < 0 ? "–" : (x * 100).toFixed(x === 1 ? 0 : 1).replace(".", ",") + "%" }

    // ------------------------------------------------------------- detalhe da tentativa
    Popup {
        id: detalhe
        property var d: ({})
        function abrir(ident) { d = a.detalhe(ident); open() }
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(pagina.width - 60, 760)
        padding: 22
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.6) }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.medio } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.rapido } }
        background: Rectangle { radius: Theme.raioGrande; color: Theme.elevada; border.color: Theme.bordaForte }
        contentItem: ColumnLayout {
            spacing: 16
            RowLayout {
                spacing: 12
                Rectangle {
                    width: 36; height: 36; radius: 10
                    color: Theme.suaveResultado(detalhe.d.resultado || "")
                    Icone { anchors.centerIn: parent; nome: detalhe.d.concedido ? "escudoOk" : "escudoX"; tamanho: 20; cor: Theme.corResultado(detalhe.d.resultado || "") }
                }
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Text { text: detalhe.d.titulo || ""; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                    Text { text: "Tentativa nº " + (detalhe.d.id || "") + ", " + (detalhe.d.data || "") + " às " + (detalhe.d.hora || ""); color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                }
                BotaoIcone { icone: "fechar"; dica: "Fechar"; onClicked: detalhe.close() }
            }
            RowLayout {
                spacing: 18
                Layout.fillWidth: true
                Rectangle {
                    Layout.preferredWidth: 260
                    Layout.preferredHeight: 260
                    Layout.alignment: Qt.AlignTop
                    radius: Theme.raio
                    color: Theme.campo
                    border.color: Theme.borda
                    clip: true
                    Image {
                        anchors.fill: parent
                        anchors.margins: 1
                        visible: detalhe.d.evidenciaExiste === true
                        source: detalhe.d.evidenciaExiste ? detalhe.d.evidenciaUrl : ""
                        sourceSize: Qt.size(520, 520)
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                    }
                    ColumnLayout {
                        anchors.centerIn: parent
                        width: parent.width - 40
                        visible: detalhe.d.evidenciaExiste !== true
                        spacing: 6
                        Icone { Layout.alignment: Qt.AlignHCenter; nome: "imagem"; tamanho: 22; cor: Theme.texto3 }
                        Text {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: detalhe.d.evidencia ? "O arquivo de evidência não está mais na pasta." : "Esta tentativa não gerou imagem de evidência."
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                        }
                    }
                }
                GridLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    columns: 2
                    columnSpacing: 16
                    rowSpacing: 10
                    component Rotulo: Text { color: Theme.texto3; font.pixelSize: Theme.tPequeno; Layout.alignment: Qt.AlignTop }
                    component Valor: Text { color: Theme.texto; font.pixelSize: Theme.tCorpo; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Rotulo { text: "Pessoa" }
                    Valor { text: detalhe.d.nome || "" }
                    Rotulo { text: "Nível da pessoa" }
                    Valor { text: detalhe.d.nivelUsuario ? detalhe.d.nivelUsuario + ": " + detalhe.d.nivelUsuarioDescricao : "Sem nível (não reconhecida)"; color: detalhe.d.nivelUsuario ? Theme.corNivel(detalhe.d.nivelUsuario) : Theme.texto2 }
                    Rotulo { text: "Área solicitada" }
                    Valor { text: "Nível " + (detalhe.d.nivelExigido || "") + ": " + (detalhe.d.area || "") }
                    Rotulo { text: "Similaridade" }
                    Valor { text: (detalhe.d.similaridade || "–") + "   (limiar " + (detalhe.d.limiar || "") + ")"; font.features: { "tnum": 1 } }
                    Rotulo { text: "Registro" }
                    Valor { text: detalhe.d.mensagem || "–"; color: Theme.texto2 }
                    Rotulo { text: "Evidência"; visible: (detalhe.d.evidencia || "") !== "" }
                    Valor { visible: (detalhe.d.evidencia || "") !== ""; text: detalhe.d.evidencia || ""; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.WrapAnywhere }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Botao { text: "Pasta de evidências"; icone: "pasta"; onClicked: a.abrirPastaEvidencias() }
                Botao { text: "Fechar"; variante: "primario"; onClicked: detalhe.close() }
            }
        }
    }

    // ------------------------------------------------------------- página
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 18

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Auditoria de acessos"
            descricao: "Cada tentativa no terminal fica registrada com resultado, similaridade e evidência"
            Botao {
                visible: a.ultimoExportado !== ""
                text: "Abrir relatório"
                icone: "externo"
                variante: "fantasma"
                dica: a.ultimoExportado
                onClicked: a.abrirExportado()
            }
            Botao { text: "Exportar CSV"; icone: "baixar"; carregando: a.exportando; enabled: !a.exportando; onClicked: a.exportar("csv") }
            Botao { text: "Exportar HTML"; icone: "arquivo"; enabled: !a.exportando; onClicked: a.exportar("html") }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: false   // não herda o preenchimento dos indicadores
            spacing: 12
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Tentativas"; valor: a.total; icone: "pulso" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Autorizadas"; valor: a.concedidos; cor: Theme.sucesso; icone: "escudoOk" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Negadas ou bloqueadas"; valor: a.negados; cor: a.negados > 0 ? Theme.perigo : Theme.texto; icone: "escudoX" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Taxa de autorização"; valor: pagina.porcentagem(a.taxa); icone: "camadas" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Usuários cadastrados"; valor: a.usuarios; detalhe: a.amostras + " amostras biométricas"; icone: "usuarios" }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            // ------------------------------------------------- tabela
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.raioGrande
                color: Theme.superficie
                border.color: Theme.borda

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    Item {
                        Layout.fillWidth: true
                        implicitHeight: filtros.implicitHeight + 28
                    Flow {
                        id: filtros
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                        spacing: 10
                        Busca {
                            width: 180
                            placeholderText: "Buscar pessoa"
                            text: a.busca
                            onTextChanged: if (text !== a.busca) a.definirBusca(text)
                        }
                        Seletor {
                            width: 172
                            atual: a.filtroResultado
                            opcoes: a.opcoesResultado().map(function(o) { return { valor: o.chave, texto: o.titulo } })
                            onEscolhido: function(v) { a.definirFiltroResultado(v) }
                        }
                        Seletor {
                            width: 136
                            atual: a.filtroNivel
                            opcoes: [{ valor: 0, texto: "Todas as áreas" }, { valor: 1, texto: "Área nível 1" }, { valor: 2, texto: "Área nível 2" }, { valor: 3, texto: "Área nível 3" }]
                            onEscolhido: function(v) { a.definirFiltroNivel(v) }
                        }
                        Segmentado {
                            atual: a.periodo
                            opcoes: [{ valor: "tudo", texto: "Tudo" }, { valor: "hoje", texto: "Hoje" }, { valor: "7d", texto: "7 dias" }, { valor: "30d", texto: "30 dias" }]
                            onEscolhido: function(v) { a.definirPeriodo(v) }
                        }
                        Botao { visible: pagina.filtrando; text: "Limpar filtros"; icone: "fechar"; variante: "fantasma"; compacto: true; onClicked: a.limparFiltros() }
                    }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 34
                        color: Theme.campo
                        Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top } height: 1; color: Theme.borda }
                        Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 1; color: Theme.borda }
                        Colunas {
                            anchors.fill: parent
                            Cab { Layout.preferredWidth: pagina.cData; text: "Data e hora" }
                            Cab { Layout.fillWidth: true; Layout.minimumWidth: 140; text: "Pessoa" }
                            Cab { Layout.preferredWidth: pagina.cResultado; text: "Resultado" }
                            Cab { Layout.preferredWidth: pagina.cArea; text: "Área" }
                            Cab { Layout.preferredWidth: pagina.cSim; text: "Similaridade"; horizontalAlignment: Text.AlignRight }
                            Item { Layout.preferredWidth: 28 }
                        }
                    }

                    ListView {
                        id: tabela
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: a.modelo
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        delegate: Rectangle {
                            id: linha
                            required property var model
                            width: tabela.width
                            height: 46
                            color: areaLinha.containsMouse ? Qt.rgba(1, 1, 1, 0.03) : "transparent"
                            Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 14; rightMargin: 14 } height: 1; color: Theme.borda; opacity: 0.55 }
                            MouseArea {
                                id: areaLinha
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: detalhe.abrir(linha.model.id)
                            }
                            Colunas {
                                anchors.fill: parent
                                ColumnLayout {
                                    Layout.preferredWidth: pagina.cData
                                    spacing: 0
                                    Text { text: linha.model.hora; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.features: { "tnum": 1 } }
                                    Text { text: linha.model.data; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.features: { "tnum": 1 } }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 140
                                    spacing: 8
                                    Rectangle { width: 6; height: 6; radius: 3; color: Theme.corNivel(linha.model.nivelUsuario); visible: linha.model.nivelUsuario > 0 }
                                    Text {
                                        Layout.fillWidth: true
                                        text: linha.model.nome
                                        color: linha.model.nivelUsuario > 0 ? Theme.texto : Theme.texto2
                                        font.pixelSize: Theme.tCorpo
                                        font.italic: linha.model.nivelUsuario === 0
                                        elide: Text.ElideRight
                                    }
                                }
                                Item {
                                    Layout.preferredWidth: pagina.cResultado
                                    implicitHeight: 22
                                    Selo { anchors.verticalCenter: parent.verticalCenter; texto: linha.model.titulo; cor: Theme.corResultado(linha.model.resultado) }
                                }
                                Text {
                                    Layout.preferredWidth: pagina.cArea
                                    text: "Nível " + linha.model.nivelExigido
                                    color: Theme.texto2
                                    font.pixelSize: Theme.tPequeno
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.preferredWidth: pagina.cSim
                                    horizontalAlignment: Text.AlignRight
                                    text: linha.model.similaridade
                                    color: Theme.texto2
                                    font.pixelSize: Theme.tCorpo
                                    font.features: { "tnum": 1 }
                                }
                                Item {
                                    Layout.preferredWidth: 28
                                    implicitHeight: 16
                                    Icone { anchors.centerIn: parent; visible: linha.model.temEvidencia; nome: "imagem"; tamanho: 15; cor: Theme.texto3 }
                                }
                            }
                        }

                        Vazio {
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 40, 380)
                            visible: tabela.count === 0
                            icone: pagina.filtrando ? "filtro" : "relogio"
                            titulo: pagina.filtrando ? "Nenhuma tentativa com esses filtros" : "Nenhuma tentativa registrada"
                            texto: pagina.filtrando ? "Amplie o período ou limpe a busca para ver mais registros."
                                                    : "As tentativas do terminal aparecem aqui assim que alguém se posicionar diante da câmera."
                            acao: pagina.filtrando ? "Limpar filtros" : "Abrir terminal"
                            iconeAcao: pagina.filtrando ? "fechar" : "terminal"
                            onAcionado: pagina.filtrando ? a.limparFiltros() : app.navegar("terminal")
                        }
                    }

                    // rodapé: quantidade e limite
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 40
                        color: "transparent"
                        Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top } height: 1; color: Theme.borda }
                        RowLayout {
                            anchors { fill: parent; leftMargin: 16; rightMargin: 12 }
                            Text {
                                text: a.listados + (a.listados >= a.limite ? " registros mais recentes" : " registro(s)") + (pagina.filtrando ? " com os filtros" : "")
                                color: Theme.texto3
                                font.pixelSize: Theme.tPequeno
                            }
                            Item { Layout.fillWidth: true }
                            Text { text: "Mostrar"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Segmentado {
                                atual: a.limite
                                opcoes: [{ valor: 50, texto: "50" }, { valor: 200, texto: "200" }, { valor: 1000, texto: "1000" }]
                                onEscolhido: function(v) { a.definirLimite(v) }
                            }
                        }
                    }
                }
            }

            // ------------------------------------------------- resumos
            ScrollView {
                Layout.preferredWidth: pagina.compacta ? 270 : 310
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: parent.width
                    spacing: 16

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Motivos de negação"
                        subtitulo: "Todas as tentativas registradas"
                        Repeater {
                            model: a.negacoes
                            delegate: ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 5
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { text: modelData.titulo; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true; elide: Text.ElideRight }
                                    Text { text: modelData.n; color: modelData.n > 0 ? Theme.texto : Theme.texto3; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; font.features: { "tnum": 1 } }
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: 4
                                    radius: 2
                                    color: Theme.realce
                                    Rectangle {
                                        height: parent.height
                                        radius: 2
                                        width: a.negados > 0 ? parent.width * modelData.n / a.negados : 0
                                        color: Theme.corResultado(modelData.chave)
                                        Behavior on width { NumberAnimation { duration: Theme.medio } }
                                    }
                                }
                            }
                        }
                    }

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Últimos dias"
                        subtitulo: a.dias.length > 0 ? "Autorizadas em verde" : ""
                        Item {
                            Layout.fillWidth: true
                            implicitHeight: 96
                            visible: a.dias.length > 0
                            Row {
                                id: barras
                                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: 18 }
                                height: 74
                                spacing: 4
                                readonly property real largura: (width - spacing * Math.max(0, a.dias.length - 1)) / Math.max(1, a.dias.length)
                                Repeater {
                                    model: a.dias
                                    delegate: Item {
                                        required property var modelData
                                        width: Math.min(22, barras.largura)
                                        height: barras.height
                                        Rectangle {
                                            id: total
                                            anchors.bottom: parent.bottom
                                            width: parent.width
                                            height: Math.max(2, parent.height * modelData.fracao)
                                            radius: 3
                                            color: Theme.perigoSuave
                                            border.color: Qt.rgba(Theme.perigo.r, Theme.perigo.g, Theme.perigo.b, 0.35)
                                            Rectangle {
                                                anchors.bottom: parent.bottom
                                                width: parent.width
                                                height: modelData.total > 0 ? parent.height * modelData.concedidos / modelData.total : 0
                                                radius: 3
                                                color: Theme.sucesso
                                                opacity: 0.85
                                            }
                                        }
                                        Dica { visible: hoverBarra.hovered; text: modelData.dia + ": " + modelData.total + " tentativa(s), " + modelData.concedidos + " autorizada(s)" }
                                        HoverHandler { id: hoverBarra }
                                    }
                                }
                            }
                            Text { anchors { left: parent.left; bottom: parent.bottom } text: a.dias.length > 0 ? a.dias[0].dia : ""; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                            Text { anchors { right: parent.right; bottom: parent.bottom } text: a.dias.length > 0 ? a.dias[a.dias.length - 1].dia : ""; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                        }
                        Text { visible: a.dias.length === 0; text: "Sem tentativas registradas."; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                    }

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Por pessoa"
                        subtitulo: a.modeloPessoas.contagem > 0 ? "Clique para filtrar a tabela" : ""
                        espacamento: 2
                        Repeater {
                            model: a.modeloPessoas
                            delegate: Rectangle {
                                id: pessoa
                                required property var model
                                readonly property bool desconhecido: model.nome === "DESCONHECIDO"
                                Layout.fillWidth: true
                                implicitHeight: 34
                                radius: Theme.raioPequeno
                                color: areaPessoa.containsMouse ? Theme.realce : "transparent"
                                MouseArea {
                                    id: areaPessoa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: a.filtrarPessoa(pessoa.model.nome)
                                }
                                RowLayout {
                                    anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                                    spacing: 8
                                    Text {
                                        Layout.fillWidth: true
                                        text: pessoa.desconhecido ? "Não identificados" : pessoa.model.nome
                                        color: pessoa.desconhecido ? Theme.texto2 : Theme.texto
                                        font.italic: pessoa.desconhecido
                                        font.pixelSize: Theme.tPequeno
                                        elide: Text.ElideRight
                                    }
                                    Text { text: pessoa.model.concedidos; color: Theme.sucesso; font.pixelSize: Theme.tPequeno; font.features: { "tnum": 1 } }
                                    Text { text: pessoa.model.negados; color: pessoa.model.negados > 0 ? Theme.perigo : Theme.texto3; font.pixelSize: Theme.tPequeno; font.features: { "tnum": 1 }; Layout.preferredWidth: 22; horizontalAlignment: Text.AlignRight }
                                }
                            }
                        }
                        Text { visible: a.modeloPessoas.contagem === 0; text: "Ninguém tentou acessar ainda."; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                    }
                }
            }
        }
    }

    readonly property int cData: 92
    readonly property int cResultado: 150
    readonly property int cArea: 74
    readonly property int cSim: 86

    component Colunas: RowLayout {
        anchors.leftMargin: 18
        anchors.rightMargin: 12
        spacing: 12
    }
    component Cab: Text { color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
}

```

## `cofre/qt/qml/Cofre/Ui/AreaCofre.qml` (234 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Nível 3: o cofre de toxinas. Inventário, sensores e retiradas, tudo fictício.
ScrollView {
    id: pagina
    property var dados: ({})
    readonly property color cor: Theme.corNivel(3)
    readonly property var sensores: dados.sensores || []
    readonly property var temperatura: dados.temperatura || []
    readonly property var lotes: dados.lotes || []
    readonly property var retiradas: dados.retiradas || []
    readonly property var portas: dados.portas || []
    readonly property var totais: dados.totais || ({})
    contentWidth: availableWidth
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    function corRisco(r) { return r === "crítico" ? Theme.perigo : r === "alto" ? Theme.aviso : Theme.texto2 }
    function demo() { app.notificar("info", "Demonstração: nenhum comando é enviado ao cofre.") }

    ColumnLayout {
        width: pagina.availableWidth
        spacing: 18

        // faixa de acesso restrito
        Rectangle {
            Layout.fillWidth: true
            Layout.margins: 28
            Layout.bottomMargin: 0
            implicitHeight: faixa.implicitHeight + 36
            radius: Theme.raioGrande
            color: Qt.rgba(pagina.cor.r, pagina.cor.g, pagina.cor.b, 0.10)
            border.color: Qt.rgba(pagina.cor.r, pagina.cor.g, pagina.cor.b, 0.45)
            RowLayout {
                id: faixa
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 22; rightMargin: 22 }
                spacing: 16
                Rectangle {
                    width: 48; height: 48; radius: 14
                    color: Qt.rgba(pagina.cor.r, pagina.cor.g, pagina.cor.b, 0.2)
                    Icone { anchors.centerIn: parent; nome: "alerta"; tamanho: 24; traco: 2; cor: pagina.cor }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    RowLayout {
                        spacing: 8
                        Text { text: dados.titulo || ""; color: Theme.texto; font.pixelSize: Theme.tTitulo; font.weight: Font.DemiBold }
                        Selo { texto: "Acesso restrito · nível 3"; cor: pagina.cor; solido: true }
                    }
                    Text { Layout.fillWidth: true; text: "Material biológico de risco. Toda retirada exige dupla custódia e fica registrada."; color: Theme.texto2; font.pixelSize: Theme.tCorpo; wrapMode: Text.WordWrap }
                    Flow {
                        Layout.fillWidth: true
                        Layout.topMargin: 6
                        spacing: 18
                        Repeater {
                            model: pagina.portas
                            delegate: RowLayout {
                                required property var modelData
                                spacing: 5
                                Rectangle { width: 7; height: 7; radius: 3.5; color: modelData.estado === "aberta" ? Theme.perigo : Theme.sucesso }
                                Text { text: modelData.nome + ": "; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                                Text { text: modelData.estado; color: Theme.texto; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            spacing: 12
            Repeater {
                model: pagina.sensores
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: 80
                    radius: Theme.raio
                    color: Theme.superficie
                    border.color: modelData.ok ? Theme.borda : Theme.perigo
                    ColumnLayout {
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                        spacing: 3
                        RowLayout {
                            Text { text: modelData.nome; color: Theme.texto2; font.pixelSize: Theme.tLegenda; Layout.fillWidth: true }
                            Rectangle { width: 7; height: 7; radius: 3.5; color: modelData.ok ? Theme.sucesso : Theme.perigo }
                        }
                        RowLayout {
                            spacing: 5
                            Text { text: modelData.valor; color: Theme.texto; font.pixelSize: 24; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                            Text { text: modelData.unidade; color: Theme.texto3; font.pixelSize: Theme.tPequeno; Layout.alignment: Qt.AlignBottom; Layout.bottomMargin: 5 }
                            Item { Layout.fillWidth: true }
                            Text { text: "faixa " + modelData.faixa; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            Layout.bottomMargin: 28
            spacing: 16

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 16

                Painel {
                    Layout.fillWidth: true
                    titulo: "Inventário"
                    subtitulo: (totais.lotes || 0) + " lotes, " + (totais.criticos || 0) + " de risco crítico"
                    espacamento: 0
                    cabecalhoDireita: Botao { text: "Solicitar abertura"; icone: "cadeado"; compacto: true; onClicked: pagina.demo() }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.bottomMargin: 8
                        spacing: 12
                        Text { Layout.preferredWidth: 80; text: "Código"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.fillWidth: true; text: "Agente"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: 80; text: "Risco"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: 70; text: "Quant."; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                        Text { Layout.preferredWidth: 84; text: "Validade"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                        Text { Layout.preferredWidth: 40; text: "Prat."; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                    }
                    Repeater {
                        model: pagina.lotes
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 0
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda; opacity: 0.7 }
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.topMargin: 9
                                Layout.bottomMargin: 9
                                spacing: 12
                                Text { Layout.preferredWidth: 80; text: modelData.codigo; color: pagina.cor; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    // fillWidth também nos textos: senão o máximo da coluna vira o tamanho do texto e a linha não estica
                                    Text { Layout.fillWidth: true; text: modelData.agente; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium; elide: Text.ElideRight }
                                    Text { Layout.fillWidth: true; text: "Origem: " + modelData.origem; color: Theme.texto3; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight }
                                }
                                Item { Layout.preferredWidth: 80; implicitHeight: 20; Selo { texto: modelData.risco; cor: pagina.corRisco(modelData.risco) } }
                                Text { Layout.preferredWidth: 70; text: modelData.quantidade + " " + modelData.unidade; color: Theme.texto; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                Text { Layout.preferredWidth: 84; text: modelData.validade; color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                Text { Layout.preferredWidth: 40; text: modelData.prateleira; color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight }
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.preferredWidth: 340
                Layout.maximumWidth: 340
                Layout.alignment: Qt.AlignTop
                spacing: 16
                Painel {
                    Layout.fillWidth: true
                    titulo: "Temperatura da câmara"
                    subtitulo: "Últimas 24 h, faixa segura de -82 a -74 °C"
                    Canvas {
                        id: curva
                        Layout.fillWidth: true
                        implicitHeight: 96
                        readonly property var pontos: pagina.temperatura
                        onPontosChanged: requestPaint()
                        onWidthChanged: requestPaint()
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.reset()
                            var n = pontos.length
                            if (n < 2) return
                            var w = width, h = height, min = -83, max = -73
                            function py(v) { return h - 14 - (v - min) / (max - min) * (h - 22) }
                            ctx.fillStyle = Qt.rgba(Theme.sucesso.r, Theme.sucesso.g, Theme.sucesso.b, 0.08)
                            ctx.fillRect(0, py(-74), w, py(-82) - py(-74))
                            ctx.strokeStyle = String(Theme.borda); ctx.lineWidth = 1
                            ctx.beginPath(); ctx.moveTo(0, py(-74)); ctx.lineTo(w, py(-74)); ctx.moveTo(0, py(-82)); ctx.lineTo(w, py(-82)); ctx.stroke()
                            ctx.strokeStyle = String(pagina.cor); ctx.lineWidth = 2
                            ctx.beginPath()
                            for (var i = 0; i < n; ++i) {
                                var x = i / (n - 1) * w, y = py(pontos[i].valor)
                                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                            }
                            ctx.stroke()
                            ctx.fillStyle = String(Theme.texto3); ctx.font = "10px sans-serif"
                            ctx.fillText(pontos[0].hora, 0, h - 2)
                            ctx.fillText(pontos[n - 1].hora, w - 22, h - 2)
                        }
                    }
                }
                Painel {
                    Layout.fillWidth: true
                    titulo: "Retiradas registradas"
                    subtitulo: "Últimos 30 dias"
                    espacamento: 0
                    Repeater {
                        model: pagina.retiradas
                        delegate: ColumnLayout {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            spacing: 0
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda; visible: index > 0; opacity: 0.7 }
                            ColumnLayout {
                                Layout.topMargin: 9
                                Layout.bottomMargin: 9
                                spacing: 2
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { text: modelData.lote + " · " + modelData.agente; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; Layout.fillWidth: true; elide: Text.ElideRight }
                                    Text { text: modelData.quantidade; color: pagina.cor; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                                }
                                Text { text: modelData.data + " · " + modelData.responsavel + " · " + modelData.finalidade; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            }
                        }
                    }
                }
            }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/AreaComum.qml` (208 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Nível 1: o dia a dia de quem trabalha no Ministério.
ScrollView {
    id: pagina
    property var dados: ({})
    readonly property color cor: Theme.corNivel(1)
    readonly property var comunicados: dados.comunicados || []
    readonly property var agenda: dados.agenda || []
    readonly property var indicadores: dados.indicadores || []
    readonly property var ar: dados.qualidadeAr || []
    readonly property var ramais: dados.ramais || []
    contentWidth: availableWidth
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

    ColumnLayout {
        width: pagina.availableWidth
        spacing: 18

        ColumnLayout {
            Layout.margins: 28
            Layout.bottomMargin: 0
            spacing: 4
            Text {
                readonly property int hora: new Date().getHours()
                text: (hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite") + ", " + app.sessao.nome.split(" ")[0]
                color: Theme.texto; font.pixelSize: Theme.tTitulo; font.weight: Font.DemiBold
            }
            Text { text: dados.titulo || ""; color: Theme.texto2; font.pixelSize: Theme.tCorpo }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            spacing: 12
            Repeater {
                model: pagina.indicadores
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: 84
                    radius: Theme.raio
                    color: Theme.superficie
                    border.color: Theme.borda
                    ColumnLayout {
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                        spacing: 4
                        Text { text: modelData.nome; color: Theme.texto2; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                        RowLayout {
                            spacing: 8
                            Text { text: modelData.valor; color: Theme.texto; font.pixelSize: 24; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                            Text { text: modelData.unidade; color: Theme.texto3; font.pixelSize: Theme.tLegenda; Layout.alignment: Qt.AlignBottom; Layout.bottomMargin: 5 }
                            Item { Layout.fillWidth: true }
                            Selo {
                                texto: (modelData.variacao > 0 ? "+" : "") + modelData.variacao + (modelData.nome.indexOf("Qualidade") === 0 ? "" : "%")
                                cor: modelData.variacao <= 0 ? Theme.sucesso : Theme.aviso
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            Layout.bottomMargin: 28
            spacing: 16

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 16
                Painel {
                    Layout.fillWidth: true
                    titulo: "Comunicados internos"
                    subtitulo: pagina.comunicados.length + " avisos desta semana"
                    espacamento: 8
                    Repeater {
                        model: pagina.comunicados
                        delegate: Rectangle {
                            required property var modelData
                            readonly property color tom: modelData.tipo === "aviso" ? Theme.aviso : modelData.tipo === "ok" ? Theme.sucesso : pagina.cor
                            Layout.fillWidth: true
                            implicitHeight: linha.implicitHeight + 22
                            radius: Theme.raioPequeno + 1
                            color: Theme.campo
                            border.color: Theme.borda
                            Rectangle { anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 1 } width: 3; radius: 2; color: tom }
                            RowLayout {
                                id: linha
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 16; rightMargin: 12 }
                                spacing: 12
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3
                                    Text { text: modelData.titulo; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    Text { text: modelData.texto; color: Theme.texto2; font.pixelSize: Theme.tPequeno; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                }
                                Text { text: modelData.data; color: Theme.texto3; font.pixelSize: Theme.tLegenda; Layout.alignment: Qt.AlignTop; font.features: { "tnum": 1 } }
                            }
                        }
                    }
                }
                Painel {
                    Layout.fillWidth: true
                    titulo: "Qualidade do ar em Brasília"
                    subtitulo: "Índice IQAr dos últimos 7 dias, menor é melhor"
                    Item {
                        Layout.fillWidth: true
                        implicitHeight: 110
                        Row {
                            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: 18 }
                            height: 80
                            spacing: 8
                            Repeater {
                                model: pagina.ar
                                delegate: Item {
                                    required property var modelData
                                    width: (parent.width - 8 * Math.max(0, pagina.ar.length - 1)) / Math.max(1, pagina.ar.length)
                                    height: parent.height
                                    Rectangle {
                                        anchors.bottom: parent.bottom
                                        width: parent.width
                                        height: Math.max(4, parent.height * modelData.valor / 100)
                                        radius: 4
                                        color: modelData.valor <= 40 ? Theme.sucesso : modelData.valor <= 80 ? Theme.aviso : Theme.perigo
                                        opacity: 0.85
                                    }
                                    Text {
                                        anchors { top: parent.bottom; topMargin: 4; horizontalCenter: parent.horizontalCenter }
                                        text: modelData.dia; color: Theme.texto3; font.pixelSize: Theme.tLegenda
                                    }
                                }
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.preferredWidth: 330
                Layout.maximumWidth: 330
                Layout.alignment: Qt.AlignTop
                spacing: 16
                Painel {
                    Layout.fillWidth: true
                    titulo: "Agenda de hoje"
                    espacamento: 0
                    Repeater {
                        model: pagina.agenda
                        delegate: RowLayout {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            spacing: 12
                            Text { text: modelData.hora; color: pagina.cor; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold; font.features: { "tnum": 1 }; Layout.preferredWidth: 42; Layout.alignment: Qt.AlignTop; Layout.topMargin: 10 }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda; visible: index > 0 }
                                ColumnLayout {
                                    Layout.topMargin: 10
                                    Layout.bottomMargin: 10
                                    spacing: 2
                                    Text { text: modelData.titulo; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    Text { text: modelData.local; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                                }
                            }
                        }
                    }
                }
                Painel {
                    Layout.fillWidth: true
                    titulo: "Ramais úteis"
                    espacamento: 6
                    GridLayout {
                        columns: 2
                        columnSpacing: 10
                        rowSpacing: 6
                        Layout.fillWidth: true
                        Repeater {
                            model: pagina.ramais
                            delegate: Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                implicitHeight: 40
                                radius: Theme.raioPequeno
                                color: Theme.campo
                                border.color: Theme.borda
                                RowLayout {
                                    anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                                    Text { text: modelData.setor; color: Theme.texto2; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: modelData.ramal; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/AreaDiretores.qml` (171 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Nível 2: gestão das divisões. Dados fictícios; os botões de aprovação não executam nada.
ScrollView {
    id: pagina
    property var dados: ({})
    readonly property color cor: Theme.corNivel(2)
    readonly property var resumo: dados.resumo || ({})
    readonly property var divisoes: dados.divisoes || []
    readonly property var aprovacoes: dados.aprovacoes || []
    readonly property var metas: dados.metas || []
    contentWidth: availableWidth
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    function moeda(v) { return "R$ " + v.toFixed(1).replace(".", ",") + " mi" }
    function demo() { app.notificar("info", "Demonstração: a aprovação não é executada.") }

    ColumnLayout {
        width: pagina.availableWidth
        spacing: 18

        RowLayout {
            Layout.margins: 28
            Layout.bottomMargin: 0
            spacing: 14
            Rectangle {
                width: 44; height: 44; radius: 13
                color: Qt.rgba(pagina.cor.r, pagina.cor.g, pagina.cor.b, 0.16)
                Icone { anchors.centerIn: parent; nome: "camadas"; tamanho: 22; traco: 2; cor: pagina.cor }
            }
            ColumnLayout {
                spacing: 2
                Text { text: dados.titulo || ""; color: Theme.texto; font.pixelSize: Theme.tTitulo; font.weight: Font.DemiBold }
                Text { text: "Exercício 2026 · " + (resumo.divisoes || 0) + " divisões sob a Secretaria Executiva"; color: Theme.texto2; font.pixelSize: Theme.tCorpo }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            spacing: 12
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Orçamento anual"; valor: resumo.orcamento || "–"; icone: "banco" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Executado"; valor: resumo.executado || "–"; detalhe: resumo.fracao !== undefined ? Math.round(resumo.fracao * 100) + "% do previsto" : ""; cor: pagina.cor; icone: "pulso" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Aprovações pendentes"; valor: String(resumo.aprovacoesPendentes || 0); cor: (resumo.aprovacoesPendentes || 0) > 4 ? Theme.aviso : Theme.texto; icone: "arquivo" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Metas no alvo"; valor: pagina.metas.filter(function(m) { return m.atual >= m.alvo * 0.9 }).length + " de " + pagina.metas.length; icone: "foco" }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            Layout.bottomMargin: 28
            spacing: 16

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 16

                Painel {
                    Layout.fillWidth: true
                    titulo: "Execução orçamentária por divisão"
                    subtitulo: "Valores em milhões de reais"
                    espacamento: 0
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.bottomMargin: 8
                        Text { Layout.fillWidth: true; text: "Divisão"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: 90; text: "Previsto"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                        Text { Layout.preferredWidth: 90; text: "Executado"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                        Text { Layout.preferredWidth: 150; text: "Andamento"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                    }
                    Repeater {
                        model: pagina.divisoes
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 0
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda; opacity: 0.7 }
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.topMargin: 10
                                Layout.bottomMargin: 10
                                spacing: 12
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text { Layout.fillWidth: true; text: modelData.nome; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium; elide: Text.ElideRight }
                                    Text { Layout.fillWidth: true; text: modelData.servidores + " servidores · meta " + modelData.meta + "%"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight }
                                }
                                Text { Layout.preferredWidth: 90; text: pagina.moeda(modelData.orcamento); color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                Text { Layout.preferredWidth: 90; text: pagina.moeda(modelData.executado); color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                RowLayout {
                                    Layout.preferredWidth: 150
                                    spacing: 8
                                    Medidor { Layout.fillWidth: true; valor: modelData.fracao; cor: modelData.fracao >= modelData.meta / 100 ? Theme.sucesso : pagina.cor; altura: 5 }
                                    Text { text: Math.round(modelData.fracao * 100) + "%"; color: Theme.texto2; font.pixelSize: Theme.tLegenda; Layout.preferredWidth: 32; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                }
                            }
                        }
                    }
                }

                Painel {
                    Layout.fillWidth: true
                    titulo: "Aprovações pendentes"
                    subtitulo: "Processos que aguardam a assinatura de um diretor"
                    espacamento: 8
                    Repeater {
                        model: pagina.aprovacoes
                        delegate: Rectangle {
                            required property var modelData
                            readonly property color tom: modelData.prioridade === "alta" ? Theme.perigo : modelData.prioridade === "média" ? Theme.aviso : Theme.texto3
                            Layout.fillWidth: true
                            implicitHeight: la.implicitHeight + 22
                            radius: Theme.raioPequeno + 1
                            color: Theme.campo
                            border.color: Theme.borda
                            RowLayout {
                                id: la
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                                spacing: 12
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3
                                    RowLayout {
                                        spacing: 8
                                        Text { text: modelData.id; color: pagina.cor; font.pixelSize: Theme.tLegenda; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                                        Selo { texto: "prioridade " + modelData.prioridade; cor: tom }
                                        Text { text: "prazo " + modelData.prazo; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                                    }
                                    Text { text: modelData.assunto; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    Text { text: modelData.origem + " · " + modelData.valor; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                                }
                                Botao { text: "Devolver"; variante: "fantasma"; compacto: true; onClicked: pagina.demo() }
                                Botao { text: "Aprovar"; variante: "primario"; compacto: true; icone: "ok"; onClicked: pagina.demo() }
                            }
                        }
                    }
                }
            }

            Painel {
                Layout.preferredWidth: 320
                Layout.maximumWidth: 320
                Layout.alignment: Qt.AlignTop
                titulo: "Metas do ano"
                espacamento: 14
                Repeater {
                    model: pagina.metas
                    delegate: ColumnLayout {
                        required property var modelData
                        readonly property real fracao: Math.min(1, modelData.atual / modelData.alvo)
                        Layout.fillWidth: true
                        spacing: 5
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: modelData.nome; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; elide: Text.ElideRight }
                            Text { text: Math.round(fracao * 100) + "%"; color: fracao >= 0.9 ? Theme.sucesso : Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                        }
                        Medidor { Layout.fillWidth: true; valor: fracao; cor: fracao >= 0.9 ? Theme.sucesso : pagina.cor; altura: 6 }
                        Text { text: modelData.atual + " de " + modelData.alvo + (modelData.unidade ? " " + modelData.unidade : ""); color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.features: { "tnum": 1 } }
                    }
                }
            }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/AreaLiberada.qml` (175 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Sobreposição que abre depois de um acesso CONCEDIDO no terminal. Mostra as áreas que o nível
// da pessoa libera (nível N enxerga 1..N). O conteúdo vem de app.sessao.conteudo(n), que devolve
// vazio para qualquer área acima do nível: a tela nunca decide o que liberar.
Rectangle {
    id: area
    readonly property var s: app.sessao
    property int atual: s.areaSolicitada
    color: Theme.janela
    visible: opacity > 0
    opacity: s.ativa ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.lento; easing.type: Easing.OutCubic } }
    Connections {
        target: area.s
        function onAtivaChanged() { if (area.s.ativa) area.atual = area.s.areaSolicitada }
    }
    // clique em área vazia renova o tempo de inatividade
    MouseArea { anchors.fill: parent; onPressed: function(m) { m.accepted = false; s.renovar() } }

    readonly property color corArea: Theme.corNivel(atual)

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---------------------------------------------------------------- barra superior
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 64
            color: Theme.lateral
            Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 1; color: Theme.borda }
            RowLayout {
                anchors { fill: parent; leftMargin: 22; rightMargin: 22 }
                spacing: 14
                Rectangle {
                    width: 36; height: 36; radius: 11
                    color: Theme.sucessoSuave
                    Icone { anchors.centerIn: parent; nome: "escudoOk"; tamanho: 20; traco: 2; cor: Theme.sucesso }
                }
                ColumnLayout {
                    spacing: 1
                    Text { text: "Acesso liberado"; color: Theme.sucesso; font.pixelSize: Theme.tLegenda; font.weight: Font.DemiBold }
                    RowLayout {
                        spacing: 8
                        Text { text: s.nome; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                        Selo { texto: "Nível " + s.nivelUsuario + " · " + s.nivelDescricao; cor: Theme.corNivel(s.nivelUsuario) }
                        Text { visible: s.cargo !== ""; text: s.cargo; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                    }
                }
                Item { Layout.fillWidth: true }
                ColumnLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignVCenter
                    RowLayout {
                        spacing: 6
                        Icone { nome: "relogio"; tamanho: 13; cor: s.tempoRestante <= 15 ? Theme.aviso : Theme.texto3 }
                        Text {
                            text: "Fecha sozinha em " + s.tempoRestante + " s"
                            color: s.tempoRestante <= 15 ? Theme.aviso : Theme.texto3
                            font.pixelSize: Theme.tLegenda
                            font.features: { "tnum": 1 }
                        }
                    }
                    Rectangle {
                        implicitWidth: 150; implicitHeight: 3; radius: 1.5
                        color: Theme.realce
                        Rectangle {
                            width: s.tempoTotal > 0 ? parent.width * s.tempoRestante / s.tempoTotal : 0
                            height: parent.height; radius: 1.5
                            color: s.tempoRestante <= 15 ? Theme.aviso : Theme.acento
                            Behavior on width { NumberAnimation { duration: 900 } }
                        }
                    }
                }
                Botao { text: "Prolongar"; variante: "fantasma"; compacto: true; onClicked: s.renovar() }
                Botao { text: "Encerrar sessão"; icone: "cadeado"; variante: "perigo"; onClicked: s.encerrar() }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // ------------------------------------------------------------ trilho de áreas
            Rectangle {
                Layout.fillHeight: true
                Layout.preferredWidth: 250
                color: Theme.lateral
                Rectangle { anchors { right: parent.right; top: parent.top; bottom: parent.bottom } width: 1; color: Theme.borda }
                ColumnLayout {
                    anchors { fill: parent; margins: 14; topMargin: 18 }
                    spacing: 6
                    Text { Layout.leftMargin: 6; Layout.bottomMargin: 6; text: "Áreas do Ministério"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                    Repeater {
                        model: s.areas
                        delegate: Rectangle {
                            id: item
                            required property var modelData
                            readonly property bool escolhida: area.atual === modelData.nivel
                            readonly property color cor: Theme.corNivel(modelData.nivel)
                            Layout.fillWidth: true
                            implicitHeight: col.implicitHeight + 22
                            radius: Theme.raio
                            color: escolhida ? Theme.superficie : (hover.hovered && modelData.liberada ? Theme.realce : "transparent")
                            border.color: escolhida ? Qt.rgba(cor.r, cor.g, cor.b, 0.55) : "transparent"
                            opacity: modelData.liberada ? 1 : 0.55
                            HoverHandler { id: hover; cursorShape: item.modelData.liberada ? Qt.PointingHandCursor : Qt.ForbiddenCursor }
                            TapHandler { onTapped: { if (item.modelData.liberada) { area.atual = item.modelData.nivel; s.renovar() } } }
                            Dica { visible: hover.hovered && !item.modelData.liberada; text: "Exige nível " + item.modelData.nivel + ". Você tem nível " + s.nivelUsuario + "." }
                            RowLayout {
                                id: col
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                                spacing: 10
                                Rectangle {
                                    width: 30; height: 30; radius: 9
                                    Layout.alignment: Qt.AlignTop
                                    color: Qt.rgba(item.cor.r, item.cor.g, item.cor.b, item.modelData.liberada ? 0.16 : 0.06)
                                    Icone {
                                        anchors.centerIn: parent
                                        nome: item.modelData.liberada ? (item.modelData.nivel === 3 ? "alerta" : item.modelData.nivel === 2 ? "camadas" : "usuarios") : "cadeado"
                                        tamanho: 15; traco: 2
                                        cor: item.modelData.liberada ? item.cor : Theme.texto3
                                    }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text { text: "Nível " + item.modelData.nivel; color: item.cor; font.pixelSize: Theme.tLegenda; font.weight: Font.DemiBold }
                                    Text { Layout.fillWidth: true; text: item.modelData.titulo; color: item.modelData.liberada ? Theme.texto : Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; wrapMode: Text.WordWrap }
                                    Text { Layout.fillWidth: true; text: item.modelData.liberada ? item.modelData.descricao : "Bloqueada para o seu nível"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.WordWrap }
                                }
                            }
                        }
                    }
                    Item { Layout.fillHeight: true }
                    Rectangle {
                        Layout.fillWidth: true
                        radius: Theme.raio
                        color: Theme.superficie
                        border.color: Theme.borda
                        implicitHeight: rod.implicitHeight + 20
                        ColumnLayout {
                            id: rod
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                            spacing: 3
                            Text { text: "Autenticação facial"; color: Theme.texto2; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                            Text { text: "Liberada às " + s.abertaEm + " para a área de nível " + s.areaSolicitada; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            Text { visible: s.similaridade >= 0; text: "Similaridade " + s.similaridade.toFixed(3); color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.features: { "tnum": 1 } }
                            Text { text: "Dados de demonstração, fictícios."; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                        }
                    }
                }
            }

            // ------------------------------------------------------------ conteúdo
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                Loader {
                    id: conteudo
                    anchors.fill: parent
                    active: s.ativa
                    source: !s.ativa ? "" : area.atual === 3 ? "AreaCofre.qml" : area.atual === 2 ? "AreaDiretores.qml" : "AreaComum.qml"
                    onLoaded: { item.dados = s.conteudo(area.atual); entrada.restart() }
                    NumberAnimation { id: entrada; target: conteudo; property: "opacity"; from: 0; to: 1; duration: Theme.medio }
                }
            }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/AvaliacaoPagina.qml` (508 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import Cofre.Nativo

// Avaliação e demo: as 5 fases em uma imagem, autenticação por imagem (registrada no log)
// e avaliação quantitativa do reconhecedor (TAR, FAR, FRR e EER).
Item {
    id: pagina
    objectName: "paginaAvaliacao"
    readonly property var v: app.avaliacao
    property string aba: "demo"
    readonly property var filtroImagens: ["Imagens (*.jpg *.jpeg *.png *.bmp *.webp)", "Todos os arquivos (*)"]

    FileDialog {
        id: dialogoDemo
        title: "Imagem para a demonstração"
        nameFilters: pagina.filtroImagens
        onAccepted: v.demonstrar(selectedFile)
    }
    FileDialog {
        id: dialogoAuth
        title: "Imagem para autenticar"
        nameFilters: pagina.filtroImagens
        onAccepted: v.autenticar(selectedFile)
    }
    FolderDialog {
        id: dialogoPasta
        title: "Pasta com uma subpasta por pessoa"
        onAccepted: v.definirPasta(selectedFolder)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 18

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Avaliação e demonstração"
            descricao: "Veja o pipeline fase a fase e meça a precisão do reconhecedor"
            Segmentado {
                atual: pagina.aba
                opcoes: [
                    { valor: "demo", texto: "Fases do pipeline", dica: "Mostra o que cada fase produz em uma imagem" },
                    { valor: "auth", texto: "Autenticar imagem", dica: "Decide o acesso a partir de uma foto" },
                    { valor: "aval", texto: "Avaliar reconhecedor", dica: "TAR, FAR, FRR e EER em uma pasta de fotos" }
                ]
                onEscolhido: function(x) { pagina.aba = x }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: ["demo", "auth", "aval"].indexOf(pagina.aba)

            // ===================================================== demonstração das fases
            RowLayout {
                spacing: 16

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 16

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 240
                        radius: Theme.raioGrande
                        color: Theme.superficie
                        border.color: Theme.borda

                        VisorVideo {
                            anchors.fill: parent
                            anchors.margins: 1
                            fonte: v.fonteDemo
                            raio: Theme.raioGrande
                            corFundo: Theme.lateral
                            preencher: false
                            visible: v.fonteDemo.temImagem
                        }
                        Vazio {
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 40, 400)
                            visible: !v.fonteDemo.temImagem && !v.demoProcessando
                            icone: "camadas"
                            titulo: "Escolha uma foto com um rosto"
                            texto: "A imagem passa pelas 5 fases (aquisição, pré-processamento, segmentação, representação e reconhecimento). Nada é gravado no log."
                            acao: "Escolher imagem"
                            iconeAcao: "imagem"
                            onAcionado: dialogoDemo.open()
                        }
                        Carregando { anchors.centerIn: parent; visible: v.demoProcessando }

                        // resultado sobre a imagem
                        Rectangle {
                            visible: v.fonteDemo.temImagem && v.demoResultado.titulo !== undefined
                            anchors { left: parent.left; bottom: parent.bottom; margins: 14 }
                            radius: Theme.raio
                            color: Qt.rgba(0.06, 0.07, 0.09, 0.92)
                            border.color: v.demoResultado.tipo === "ok" ? Theme.sucesso : (v.demoResultado.tipo === "aviso" ? Theme.aviso : Theme.perigo)
                            implicitWidth: Math.min(parent.width - 28, resDemo.implicitWidth + 28)
                            implicitHeight: resDemo.implicitHeight + 20
                            ColumnLayout {
                                id: resDemo
                                anchors { fill: parent; margins: 10; leftMargin: 14; rightMargin: 14 }
                                spacing: 2
                                Text { text: v.demoResultado.titulo || ""; color: parent.parent.border.color; font.pixelSize: Theme.tCorpo; font.weight: Font.DemiBold }
                                Text { text: v.demoResultado.mensagem || ""; color: Theme.texto2; font.pixelSize: Theme.tPequeno; wrapMode: Text.WordWrap; Layout.maximumWidth: 460 }
                            }
                        }
                    }

                    // imagens intermediárias
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 150
                        visible: v.demoEtapas.length > 0
                        radius: Theme.raioGrande
                        color: Theme.superficie
                        border.color: Theme.borda
                        ListView {
                            anchors { fill: parent; margins: 12 }
                            orientation: ListView.Horizontal
                            spacing: 10
                            clip: true
                            model: v.demoEtapas
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
                            delegate: ColumnLayout {
                                required property var modelData
                                width: 108
                                spacing: 5
                                Rectangle {
                                    Layout.preferredWidth: 108
                                    Layout.preferredHeight: 100
                                    radius: Theme.raioPequeno
                                    color: Theme.lateral
                                    border.color: Theme.borda
                                    VisorVideo { anchors.fill: parent; anchors.margins: 1; fonte: modelData; raio: Theme.raioPequeno; corFundo: Theme.lateral; mostrarPontos: false }
                                }
                                Text { text: modelData.nome; color: Theme.texto2; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                            }
                        }
                    }
                }

                // painel lateral: controles e fases
                ScrollView {
                    Layout.preferredWidth: 340
                    Layout.fillHeight: true
                    contentWidth: availableWidth
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ColumnLayout {
                        width: parent.width
                        spacing: 16
                        Painel {
                            Layout.fillWidth: true
                            titulo: "Imagem"
                            subtitulo: v.demoArquivo !== "" ? v.demoArquivo : "Nenhuma imagem escolhida"
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Botao { Layout.fillWidth: true; text: v.demoArquivo !== "" ? "Trocar imagem" : "Escolher imagem"; icone: "imagem"; variante: "primario"; carregando: v.demoProcessando; enabled: !v.demoProcessando && app.modelosProntos; onClicked: dialogoDemo.open() }
                                Botao { text: "Salvar painel"; icone: "salvar"; enabled: v.demoEtapas.length > 0; dica: "Grava o mosaico das fases na pasta de relatórios"; onClicked: v.salvarPainel() }
                            }
                            Text { text: "Área usada na fase 5"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.topMargin: 4 }
                            Segmentado {
                                Layout.fillWidth: true
                                atual: v.demoNivel
                                opcoes: [{ valor: 1, texto: "Nível 1" }, { valor: 2, texto: "Nível 2" }, { valor: 3, texto: "Nível 3" }]
                                onEscolhido: function(x) { v.definirNivelDemo(x) }
                            }
                        }
                        Repeater {
                            model: v.demoFases
                            delegate: Painel {
                                required property var modelData
                                Layout.fillWidth: true
                                titulo: "Fase " + modelData.fase + ": " + modelData.titulo
                                espacamento: 6
                                Repeater {
                                    model: modelData.linhas
                                    delegate: RowLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: 12
                                        Text { text: modelData[0]; color: Theme.texto3; font.pixelSize: Theme.tPequeno; Layout.preferredWidth: 118; Layout.alignment: Qt.AlignTop }
                                        Text { text: modelData[1]; color: Theme.texto; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.features: { "tnum": 1 } }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ===================================================== autenticar por imagem
            RowLayout {
                spacing: 16
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: Theme.raioGrande
                    color: Theme.superficie
                    border.color: v.authResultado.tipo === "ok" ? Theme.sucesso : (v.authResultado.tipo === "erro" ? Theme.perigo : Theme.borda)
                    Behavior on border.color { ColorAnimation { duration: Theme.medio } }
                    VisorVideo {
                        anchors.fill: parent
                        anchors.margins: 1
                        fonte: v.fonteAuth
                        raio: Theme.raioGrande
                        corFundo: Theme.lateral
                        preencher: false
                        visible: v.fonteAuth.temImagem
                    }
                    Vazio {
                        anchors.centerIn: parent
                        width: Math.min(parent.width - 40, 400)
                        visible: !v.fonteAuth.temImagem && !v.authProcessando
                        icone: "escudo"
                        titulo: "Autentique a partir de uma foto"
                        texto: "Mesma decisão do terminal, sem prova de vida. A tentativa fica registrada na auditoria de acessos."
                        acao: "Escolher imagem"
                        iconeAcao: "imagem"
                        onAcionado: dialogoAuth.open()
                    }
                    Carregando { anchors.centerIn: parent; visible: v.authProcessando }
                }
                ColumnLayout {
                    Layout.preferredWidth: 340
                    Layout.maximumWidth: 340
                    Layout.fillHeight: true
                    spacing: 16
                    Painel {
                        Layout.fillWidth: true
                        titulo: "Área protegida"
                        subtitulo: "Nível exigido para liberar o acesso"
                        Segmentado {
                            Layout.fillWidth: true
                            atual: v.authNivel
                            habilitado: !v.authProcessando
                            opcoes: [{ valor: 1, texto: "Nível 1" }, { valor: 2, texto: "Nível 2" }, { valor: 3, texto: "Nível 3" }]
                            onEscolhido: function(x) { v.definirNivelAuth(x) }
                        }
                        Botao {
                            Layout.fillWidth: true
                            text: v.authArquivo !== "" ? "Autenticar outra imagem" : "Escolher imagem"
                            icone: "imagem"
                            variante: "primario"
                            carregando: v.authProcessando
                            enabled: !v.authProcessando && app.modelosProntos
                            onClicked: dialogoAuth.open()
                        }
                        RowLayout {
                            spacing: 6
                            Icone { nome: "info"; tamanho: 14; cor: Theme.texto3 }
                            Text { Layout.fillWidth: true; text: "Cada autenticação entra no log de acessos."; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.WordWrap }
                        }
                    }
                    Painel {
                        Layout.fillWidth: true
                        visible: v.authResultado.titulo !== undefined
                        titulo: v.authResultado.titulo || ""
                        subtitulo: v.authArquivo
                        cabecalhoDireita: Icone {
                            nome: v.authResultado.concedido ? "escudoOk" : "escudoX"
                            tamanho: 22
                            cor: v.authResultado.concedido ? Theme.sucesso : Theme.perigo
                        }
                        Text { Layout.fillWidth: true; text: v.authResultado.mensagem || ""; color: Theme.texto2; font.pixelSize: Theme.tPequeno; wrapMode: Text.WordWrap }
                        GridLayout {
                            visible: v.authResultado.usuario !== undefined
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 12
                            rowSpacing: 8
                            Text { text: "Pessoa"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: v.authResultado.usuario || ""; color: Theme.texto; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true; elide: Text.ElideRight }
                            Text { text: "Nível da pessoa"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: v.authResultado.nivelUsuario ? String(v.authResultado.nivelUsuario) : "–"; color: Theme.corNivel(v.authResultado.nivelUsuario || 0); font.pixelSize: Theme.tPequeno }
                            Text { text: "Nível exigido"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: String(v.authResultado.nivelExigido || ""); color: Theme.texto; font.pixelSize: Theme.tPequeno }
                            Text { text: "Similaridade"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: (v.authResultado.similaridade || "–") + " (limiar " + (v.authResultado.limiar || "") + ")"; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.features: { "tnum": 1 } }
                            Text { text: "Rostos na imagem"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: String(v.authResultado.rostos !== undefined ? v.authResultado.rostos : ""); color: v.authResultado.rostos > 1 ? Theme.aviso : Theme.texto; font.pixelSize: Theme.tPequeno }
                        }
                        Botao { text: "Ver na auditoria"; icone: "acessos"; variante: "fantasma"; compacto: true; visible: v.authResultado.usuario !== undefined; onClicked: app.navegar("acessos") }
                    }
                    Item { Layout.fillHeight: true }
                }
            }

            // ===================================================== avaliação do reconhecedor
            ScrollView {
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ColumnLayout {
                    width: parent.width
                    spacing: 16

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Conjunto de teste"
                        subtitulo: "Uma subpasta por pessoa (pasta/pessoa/foto.jpg). Pares da mesma pessoa são genuínos, os demais são impostores."
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 34
                                radius: Theme.raioPequeno
                                color: Theme.campo
                                border.color: Theme.borda
                                RowLayout {
                                    anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                                    spacing: 8
                                    Icone { nome: "pasta"; tamanho: 15; cor: Theme.texto3 }
                                    Text {
                                        Layout.fillWidth: true
                                        text: v.avalPasta !== "" ? v.avalPasta : "Nenhuma pasta escolhida"
                                        color: v.avalPasta !== "" ? Theme.texto : Theme.texto3
                                        font.pixelSize: Theme.tPequeno
                                        elide: Text.ElideMiddle
                                    }
                                }
                            }
                            Botao { text: "Escolher pasta"; icone: "pasta"; enabled: !v.avalProcessando; onClicked: dialogoPasta.open() }
                            Botao { text: "Usar fotos de teste"; variante: "fantasma"; enabled: !v.avalProcessando; dica: "tests/fixtures/pessoas, incluídas no projeto"; onClicked: v.usarFotosTeste() }
                            Botao { text: "Avaliar"; icone: "play"; variante: "primario"; carregando: v.avalProcessando; enabled: !v.avalProcessando && v.avalPasta !== "" && app.modelosProntos; onClicked: v.avaliar() }
                        }
                    }

                    Vazio {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 40
                        Layout.preferredWidth: 420
                        visible: v.avalResultado.valido === undefined && !v.avalProcessando
                        icone: "pulso"
                        titulo: "Nenhuma avaliação ainda"
                        texto: "Escolha uma pasta e clique em Avaliar. O resultado mostra as taxas no limiar atual e uma varredura de limiares."
                    }
                    ColumnLayout {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 40
                        visible: v.avalProcessando
                        spacing: 10
                        Carregando { Layout.alignment: Qt.AlignHCenter }
                        Text { text: "Extraindo embeddings e comparando pares..."; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        visible: (v.avalResultado.aviso || "") !== ""
                        implicitHeight: textoAviso.implicitHeight + 20
                        radius: Theme.raio
                        color: Theme.avisoSuave
                        border.color: Qt.rgba(Theme.aviso.r, Theme.aviso.g, Theme.aviso.b, 0.35)
                        RowLayout {
                            anchors { fill: parent; margins: 10; leftMargin: 12 }
                            spacing: 8
                            Icone { nome: "alerta"; tamanho: 16; cor: Theme.aviso; Layout.alignment: Qt.AlignTop }
                            Text { id: textoAviso; Layout.fillWidth: true; text: v.avalResultado.aviso || ""; color: Theme.texto; font.pixelSize: Theme.tPequeno; wrapMode: Text.WordWrap }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: v.avalResultado.valido === true && !v.avalProcessando
                        Layout.fillHeight: false   // não herda o preenchimento dos indicadores
                        spacing: 12
                        Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "TAR (aceitação correta)"; valor: v.avalResultado.tar || "–"; cor: Theme.sucesso; detalhe: "limiar " + Number(v.avalResultado.limiar || 0).toFixed(3) }
                        Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "FAR (impostor aceito)"; valor: v.avalResultado.far || "–"; cor: Theme.perigo; detalhe: (v.avalResultado.impostores || 0) + " pares impostores" }
                        Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "FRR (genuíno rejeitado)"; valor: v.avalResultado.frr || "–"; cor: Theme.aviso; detalhe: (v.avalResultado.genuinos || 0) + " pares genuínos" }
                        Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "EER"; valor: v.avalResultado.eer || "–"; cor: Theme.acento; detalhe: "no limiar " + (v.avalResultado.eerLimiar || "–") }
                        Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Conjunto"; valor: (v.avalResultado.pessoas || 0) + " pessoas"; detalhe: (v.avalResultado.imagens || 0) + " imagens, " + (v.avalResultado.semRosto || 0) + " sem rosto" }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: v.avalResultado.valido === true && !v.avalProcessando
                        spacing: 16

                        Painel {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            titulo: "Curva de decisão"
                            subtitulo: "TAR e FAR conforme o limiar de similaridade"
                            cabecalhoDireita: RowLayout {
                                spacing: 12
                                Legenda { cor: Theme.sucesso; texto: "TAR" }
                                Legenda { cor: Theme.perigo; texto: "FAR" }
                                Legenda { cor: Theme.texto2; texto: "limiar atual"; tracejada: true }
                            }
                            Canvas {
                                id: curva
                                Layout.fillWidth: true
                                implicitHeight: 240
                                readonly property var pontos: v.avalResultado.curva || []
                                readonly property real limiar: v.avalResultado.limiar || 0
                                onPontosChanged: requestPaint()
                                onWidthChanged: requestPaint()
                                onPaint: {
                                    var ctx = getContext("2d")
                                    ctx.reset()
                                    var esq = 38, dir = 10, topo = 8, base = 26
                                    var w = width - esq - dir, h = height - topo - base
                                    if (pontos.length === 0 || w <= 0) return
                                    var min = pontos[0].limiar, max = pontos[pontos.length - 1].limiar
                                    function px(l) { return esq + (l - min) / Math.max(1e-6, max - min) * w }
                                    function py(f) { return topo + (1 - f) * h }
                                    ctx.font = "11px sans-serif"
                                    ctx.lineWidth = 1
                                    for (var i = 0; i <= 4; ++i) {
                                        var y = py(i / 4)
                                        ctx.strokeStyle = String(Theme.borda)
                                        ctx.beginPath(); ctx.moveTo(esq, y); ctx.lineTo(esq + w, y); ctx.stroke()
                                        ctx.fillStyle = String(Theme.texto3)
                                        ctx.fillText((i * 25) + "%", 2, y + 4)
                                    }
                                    for (var k = 0; k <= 4; ++k) {
                                        var l = min + (max - min) * k / 4
                                        ctx.fillText(l.toFixed(2), px(l) - 12, height - 6)
                                    }
                                    function serie(campo, cor) {
                                        ctx.strokeStyle = cor
                                        ctx.lineWidth = 2
                                        ctx.beginPath()
                                        var iniciou = false
                                        for (var j = 0; j < pontos.length; ++j) {
                                            var val = pontos[j][campo]
                                            if (val === null || val === undefined) { iniciou = false; continue }
                                            if (!iniciou) { ctx.moveTo(px(pontos[j].limiar), py(val)); iniciou = true }
                                            else ctx.lineTo(px(pontos[j].limiar), py(val))
                                        }
                                        ctx.stroke()
                                    }
                                    serie("tar", String(Theme.sucesso))
                                    serie("far", String(Theme.perigo))
                                    if (limiar >= min && limiar <= max) {
                                        ctx.strokeStyle = String(Theme.texto2)
                                        ctx.lineWidth = 1
                                        ctx.setLineDash([4, 4])
                                        ctx.beginPath(); ctx.moveTo(px(limiar), topo); ctx.lineTo(px(limiar), topo + h); ctx.stroke()
                                        ctx.setLineDash([])
                                    }
                                }
                            }
                        }

                        Painel {
                            Layout.preferredWidth: 340
                            Layout.alignment: Qt.AlignTop
                            titulo: "Varredura de limiares"
                            subtitulo: "Linha destacada: mais próxima do limiar em uso"
                            espacamento: 0
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.topMargin: 8
                                Layout.bottomMargin: 6
                                Layout.leftMargin: 6
                                Layout.rightMargin: 6
                                Text { Layout.preferredWidth: 64; text: "Limiar"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                                Text { Layout.fillWidth: true; text: "TAR"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                                Text { Layout.fillWidth: true; text: "FRR"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                                Text { Layout.fillWidth: true; text: "FAR"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                            }
                            Repeater {
                                model: v.modeloVarredura
                                delegate: Rectangle {
                                    id: lv
                                    required property var model
                                    Layout.fillWidth: true
                                    implicitHeight: 26
                                    radius: 5
                                    color: model.atual ? Theme.acentoSuave : "transparent"
                                    RowLayout {
                                        anchors { fill: parent; leftMargin: 6; rightMargin: 6 }
                                        Text { Layout.preferredWidth: 64; text: lv.model.limiar; color: lv.model.atual ? Theme.acento : Theme.texto; font.pixelSize: Theme.tPequeno; font.features: { "tnum": 1 } }
                                        Text { Layout.fillWidth: true; text: lv.model.tar; color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                        Text { Layout.fillWidth: true; text: lv.model.frr; color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                        Text { Layout.fillWidth: true; text: lv.model.far; color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    component Legenda: RowLayout {
        property color cor
        property string texto
        property bool tracejada: false
        spacing: 5
        Rectangle { width: 14; height: 2; color: tracejada ? "transparent" : cor; border.width: tracejada ? 1 : 0; border.color: cor }
        Text { text: texto; color: Theme.texto2; font.pixelSize: Theme.tLegenda }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Botao.qml` (71 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Botão com variantes: "primario" (acento), "secundario", "fantasma" e "perigo".
Button {
    id: b
    property string variante: "secundario"
    property string icone: ""
    property bool compacto: false
    property string dica: ""
    property bool carregando: false

    readonly property color _fundo: {
        if (!enabled) return variante === "fantasma" ? "transparent" : Theme.elevada
        if (variante === "primario") return down ? Theme.acentoForte : (hovered ? Qt.lighter(Theme.acento, 1.08) : Theme.acento)
        if (variante === "perigo") return down ? Qt.darker(Theme.perigo, 1.15) : (hovered ? Qt.lighter(Theme.perigo, 1.06) : Theme.perigo)
        if (variante === "fantasma") return down ? Theme.realce : (hovered ? Theme.elevada : "transparent")
        return down ? Theme.bordaForte : (hovered ? Theme.realce : Theme.elevada)
    }
    readonly property color _texto: {
        if (!enabled) return Theme.texto3
        if (variante === "primario" || variante === "perigo") return Theme.sobreCor
        return variante === "fantasma" && !hovered ? Theme.texto2 : Theme.texto
    }

    implicitHeight: compacto ? 28 : 34
    leftPadding: compacto ? 10 : 14
    rightPadding: compacto ? 10 : 14
    font.pixelSize: compacto ? Theme.tPequeno : Theme.tCorpo
    font.weight: Font.Medium
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus

    contentItem: RowLayout {
        spacing: 7
        Item {
            visible: b.icone !== "" || b.carregando
            implicitWidth: b.compacto ? 14 : 16
            implicitHeight: implicitWidth
            Icone { anchors.centerIn: parent; visible: !b.carregando; nome: b.icone; cor: b._texto; tamanho: parent.width; traco: 2 }
            Carregando { anchors.centerIn: parent; visible: b.carregando; tamanho: parent.width; cor: b._texto }
        }
        Text {
            visible: b.text !== ""
            text: b.text
            color: b._texto
            font: b.font
            elide: Text.ElideRight
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
        }
    }
    background: Rectangle {
        radius: Theme.raioPequeno
        color: b._fundo
        border.width: b.variante === "secundario" ? 1 : 0
        border.color: b.hovered ? Theme.bordaForte : Theme.borda
        Behavior on color { ColorAnimation { duration: Theme.rapido } }
        Rectangle {        // anel de foco do teclado
            anchors.fill: parent
            anchors.margins: -3
            radius: parent.radius + 3
            color: "transparent"
            border.width: 2
            border.color: Theme.acento
            opacity: b.visualFocus ? 0.7 : 0
        }
    }
    Dica { visible: b.dica !== "" && b.hovered; text: b.dica }
}

```

## `cofre/qt/qml/Cofre/Ui/BotaoIcone.qml` (27 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic

// Botão só com ícone; `dica` é obrigatória para acessibilidade.
AbstractButton {
    id: b
    property string icone: ""
    property string dica: ""
    property color cor: Theme.texto2
    property real tamanho: 30
    implicitWidth: tamanho
    implicitHeight: tamanho
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: dica
    background: Rectangle {
        radius: Theme.raioPequeno
        color: b.down ? Theme.bordaForte : (b.hovered ? Theme.realce : "transparent")
        border.width: b.visualFocus ? 2 : 0
        border.color: Theme.acento
        Behavior on color { ColorAnimation { duration: Theme.rapido } }
    }
    contentItem: Item {
        Icone { anchors.centerIn: parent; nome: b.icone; tamanho: Math.round(b.tamanho * 0.55); cor: b.enabled ? (b.hovered ? Theme.texto : b.cor) : Theme.texto3 }
    }
    Dica { visible: b.dica !== "" && b.hovered; text: b.dica }
}

```

## `cofre/qt/qml/Cofre/Ui/Busca.qml` (33 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic

// Campo de busca com ícone e botão de limpar.
TextField {
    id: b
    implicitHeight: 34
    implicitWidth: 260
    color: Theme.texto
    placeholderTextColor: Theme.texto3
    selectionColor: Theme.acentoForte
    selectedTextColor: Theme.sobreCor
    font.pixelSize: Theme.tCorpo
    leftPadding: 34
    rightPadding: b.text !== "" ? 32 : 12
    background: Rectangle {
        radius: Theme.raioPequeno
        color: Theme.campo
        border.width: b.activeFocus ? 1.5 : 1
        border.color: b.activeFocus ? Theme.acento : (b.hovered ? Theme.bordaForte : Theme.borda)
        Icone { anchors.verticalCenter: parent.verticalCenter; x: 11; nome: "busca"; tamanho: 15; cor: Theme.texto3 }
    }
    BotaoIcone {
        visible: b.text !== ""
        anchors.right: parent.right
        anchors.rightMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        tamanho: 24
        icone: "fechar"
        dica: "Limpar busca"
        onClicked: { b.clear(); b.forceActiveFocus() }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Cabecalho.qml` (18 linhas)

```qml
import QtQuick
import QtQuick.Layouts

// Cabeçalho de página: título, descrição e ações à direita.
RowLayout {
    id: c
    property string titulo: ""
    property string descricao: ""
    default property alias acoes: acoes.data
    spacing: 16
    ColumnLayout {
        spacing: 3
        Layout.fillWidth: true
        Text { text: c.titulo; color: Theme.texto; font.pixelSize: Theme.tTitulo; font.weight: Font.DemiBold }
        Text { visible: c.descricao !== ""; text: c.descricao; color: Theme.texto2; font.pixelSize: Theme.tCorpo; elide: Text.ElideRight; Layout.fillWidth: true }
    }
    RowLayout { id: acoes; spacing: 8 }
}

```

## `cofre/qt/qml/Cofre/Ui/CadastroPagina.qml` (538 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import Cofre.Nativo

// Cadastro biométrico: formulário à direita, prévia da câmera e amostras à esquerda.
Item {
    id: pagina
    readonly property var c: app.cadastro
    readonly property var cam: app.cameraServico
    readonly property var lim: c.limites()
    readonly property bool ocupado: c.fase !== "formulario"
    property int nivelEscolhido: 1
    property string avisoMatricula: ""

    function iniciar() {
        if (c.iniciarCaptura(nome.texto, matricula.texto, cargo.texto, nivelEscolhido)) limparFormulario()
    }
    function limparFormulario() { nome.texto = ""; matricula.texto = ""; cargo.texto = ""; nivelEscolhido = 1; avisoMatricula = "" }

    FileDialog {
        id: dialogoFotos
        title: "Escolha as fotos do rosto"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Imagens (*.jpg *.jpeg *.png *.bmp *.webp)", "Todos os arquivos (*)"]
        onAccepted: {
            if (c.cadastrarPorFotos(nome.texto, matricula.texto, cargo.texto, pagina.nivelEscolhido, selectedFiles))
                pagina.limparFormulario()
        }
    }
    Confirmacao {
        id: confirmarCancelar
        titulo: "Cancelar o cadastro?"
        texto: "As " + c.capturadas + " amostras já capturadas de " + c.nome + " serão descartadas e o usuário não será criado."
        textoConfirmar: "Descartar cadastro"
        perigo: true
        onConfirmado: c.cancelar()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 18

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Cadastro biométrico"
            descricao: "Registre um rosto autorizado pela câmera ou a partir de fotos"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 18

            // ---------------------------------------------------- câmera e amostras
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                Rectangle {
                    id: moldura
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 280
                    radius: Theme.raioGrande + 2
                    color: Theme.lateral
                    border.width: c.fase === "capturando" ? 2 : 1
                    border.color: c.fase !== "capturando" ? Theme.borda
                                  : c.statusTipo === "ok" ? Theme.sucesso : c.statusTipo === "erro" ? Theme.perigo
                                  : c.statusTipo === "aviso" ? Theme.aviso : Theme.acento
                    Behavior on border.color { ColorAnimation { duration: Theme.medio } }

                    VisorVideo {
                        id: visor
                        anchors.fill: parent
                        anchors.margins: 2
                        fonte: c.fonteVideo
                        raio: Theme.raioGrande
                        corFundo: Theme.lateral
                    }
                    Rectangle {      // clarão a cada amostra capturada
                        id: clarao
                        anchors.fill: visor
                        radius: Theme.raioGrande
                        color: "white"
                        opacity: 0
                        NumberAnimation on opacity { id: animClarao; running: false; from: 0.28; to: 0; duration: 380; easing.type: Easing.OutCubic }
                    }
                    Connections { target: c; function onAmostraCapturada(n) { animClarao.restart() } }

                    // instrução de pose
                    Rectangle {
                        visible: c.fase === "capturando" && cam.estado === "ativa"
                        anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: 18 }
                        width: Math.min(parent.width - 40, 460)
                        height: colPose.implicitHeight + 26
                        radius: Theme.raio
                        color: Qt.rgba(0.06, 0.07, 0.08, 0.86)
                        border.color: Theme.borda
                        ColumnLayout {
                            id: colPose
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }
                            spacing: 8
                            RowLayout {
                                Text { text: "Pose " + (c.poseIndice + 1) + " de " + pagina.lim.poses.length; color: Theme.texto3; font.pixelSize: Theme.tLegenda; Layout.fillWidth: true }
                                Repeater {
                                    model: pagina.lim.poses.length
                                    delegate: Rectangle {
                                        required property int index
                                        width: index === c.poseIndice ? 18 : 6
                                        height: 6
                                        radius: 3
                                        color: index < c.poseIndice ? Theme.acento : index === c.poseIndice ? Theme.texto : Theme.bordaForte
                                        Behavior on width { NumberAnimation { duration: Theme.medio } }
                                    }
                                }
                            }
                            Text { text: c.pose; color: Theme.texto; font.pixelSize: 18; font.weight: Font.DemiBold; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        }
                    }

                    // estado da captura
                    Rectangle {
                        visible: c.fase === "capturando" && cam.estado === "ativa" && c.status !== ""
                        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 18 }
                        height: 34
                        width: linhaStatus.implicitWidth + 28
                        radius: 17
                        color: Qt.rgba(0.06, 0.07, 0.08, 0.86)
                        border.color: Qt.rgba(corStatus.r, corStatus.g, corStatus.b, 0.5)
                        readonly property color corStatus: Theme.corResultado(c.statusTipo)
                        RowLayout {
                            id: linhaStatus
                            anchors.centerIn: parent
                            spacing: 8
                            Rectangle { width: 8; height: 8; radius: 4; color: parent.parent.corStatus }
                            Text { text: c.status; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium }
                        }
                    }

                    // vazio, carregando, erro ou pausa
                    ColumnLayout {
                        anchors.centerIn: parent
                        width: Math.min(parent.width - 80, 420)
                        visible: c.fase === "formulario" || c.fase === "importando" || c.fase === "preparando" || cam.estado !== "ativa"
                        spacing: 12
                        Carregando {
                            Layout.alignment: Qt.AlignHCenter
                            visible: c.fase === "importando" || c.fase === "preparando" || (c.fase === "capturando" && cam.estado === "abrindo")
                            tamanho: 30
                        }
                        Rectangle {
                            Layout.alignment: Qt.AlignHCenter
                            visible: c.fase === "formulario" || (c.fase === "capturando" && cam.estado === "erro")
                            width: 56; height: 56; radius: 18
                            color: cam.estado === "erro" && c.fase === "capturando" ? Theme.perigoSuave : Theme.elevada
                            border.color: Theme.borda
                            Icone {
                                anchors.centerIn: parent
                                nome: cam.estado === "erro" && c.fase === "capturando" ? "cameraOff" : "camera"
                                tamanho: 24
                                cor: cam.estado === "erro" && c.fase === "capturando" ? Theme.perigo : Theme.texto2
                            }
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: c.fase === "importando" ? "Processando as fotos"
                                  : c.fase === "preparando" ? c.status
                                  : c.fase === "formulario" ? "A câmera liga quando a captura começar"
                                  : c.pausada ? "Captura pausada"
                                  : cam.estado === "erro" ? "Câmera indisponível" : "Abrindo a câmera"
                            color: Theme.texto
                            font.pixelSize: Theme.tDestaque
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            text: c.fase === "formulario" ? "Preencha os dados ao lado e clique em Iniciar captura. Serão gravadas " + c.total + " amostras, uma a cada " + pagina.lim.intervalo.toFixed(1).replace(".", ",") + " s, seguindo as instruções de pose."
                                  : c.fase === "importando" ? c.status
                                  : cam.estado === "erro" ? cam.erro : ""
                            visible: text !== ""
                            color: Theme.texto2
                            font.pixelSize: Theme.tPequeno
                            wrapMode: Text.Wrap
                        }
                        Botao {
                            Layout.alignment: Qt.AlignHCenter
                            visible: c.fase === "capturando" && (cam.estado === "erro" || cam.estado === "desligada")
                            text: "Tentar novamente"
                            icone: "recarregar"
                            variante: "primario"
                            onClicked: c.tentarCamera()
                        }
                    }
                }

                // amostras capturadas
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 104
                    radius: Theme.raioGrande
                    color: Theme.superficie
                    border.color: Theme.borda
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8
                        RowLayout {
                            Text { text: "Amostras"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium }
                            Text { text: c.capturadas + " de " + c.total; color: Theme.texto3; font.pixelSize: Theme.tPequeno; font.features: { "tnum": 1 } }
                            Item { Layout.fillWidth: true }
                        }
                        ListView {
                            id: faixa
                            // cabem todas as amostras sem rolagem; só encolhem até 34 px
                            readonly property real lado: Math.max(34, Math.min(52, (width - spacing * (c.total - 1)) / Math.max(1, c.total)))
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            orientation: ListView.Horizontal
                            spacing: 8
                            clip: true
                            model: c.total
                            boundsBehavior: Flickable.StopAtBounds
                            delegate: Rectangle {
                                required property int index
                                readonly property bool cheia: index < c.miniaturas
                                width: faixa.lado; height: faixa.lado
                                anchors.verticalCenter: parent ? parent.verticalCenter : undefined
                                radius: Theme.raioPequeno
                                color: Theme.campo
                                border.color: cheia ? Theme.bordaForte : Theme.borda
                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 1
                                    visible: parent.cheia
                                    source: parent.cheia ? "image://cofre/cadastro/" + index + "?r=" + c.revisao : ""
                                    sourceSize: Qt.size(104, 104)
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: false
                                }
                                Text { anchors.centerIn: parent; visible: !parent.cheia; text: index + 1; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                            }
                        }
                    }
                }
            }

            // ---------------------------------------------------- formulário / progresso
            ScrollView {
                id: rolagem
                Layout.preferredWidth: 380
                Layout.minimumWidth: 330
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: rolagem.availableWidth
                    spacing: 12

                    // sucesso
                    Painel {
                        Layout.fillWidth: true
                        visible: c.sucesso.nome !== undefined
                        border.color: Qt.rgba(0.239, 0.839, 0.549, 0.4)
                        RowLayout {
                            spacing: 12
                            Rectangle {
                                width: 40; height: 40; radius: 12
                                color: Theme.sucessoSuave
                                Icone { anchors.centerIn: parent; nome: "usuarioOk"; tamanho: 20; cor: Theme.sucesso }
                            }
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Text { text: "Cadastro concluído"; color: Theme.sucesso; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                                Text { text: (c.sucesso.amostras || 0) + " amostras gravadas"; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                            }
                        }
                        GridLayout {
                            columns: 2
                            columnSpacing: 14
                            rowSpacing: 6
                            Text { text: "Nome"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: c.sucesso.nome || ""; color: Theme.texto; font.pixelSize: Theme.tCorpo; elide: Text.ElideRight; Layout.fillWidth: true }
                            Text { text: "Matrícula"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: c.sucesso.matricula || ""; color: Theme.texto; font.pixelSize: Theme.tCorpo }
                            Text { text: "Nível"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Selo { texto: (c.sucesso.nivel || "") + " · " + (c.sucesso.nivelDescricao || ""); cor: Theme.corNivel(c.sucesso.nivel || 0) }
                        }
                        Repeater {
                            model: c.sucesso.avisos || []
                            delegate: RowLayout {
                                required property string modelData
                                Layout.fillWidth: true
                                spacing: 6
                                Icone { nome: "alerta"; tamanho: 13; cor: Theme.aviso }
                                Text { text: modelData; color: Theme.texto2; font.pixelSize: Theme.tLegenda; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            }
                        }
                        RowLayout {
                            spacing: 8
                            Botao { text: "Ir para o terminal"; icone: "terminal"; onClicked: { c.fecharSucesso(); app.navegar("terminal") } }
                            Botao { text: "Fechar"; variante: "fantasma"; onClicked: c.fecharSucesso() }
                        }
                    }

                    // progresso da captura
                    Painel {
                        Layout.fillWidth: true
                        visible: c.fase === "capturando" || c.fase === "preparando"
                        titulo: "Capturando " + c.nome
                        subtitulo: "Nível " + c.nivelCadastro + ". Siga as instruções sobre o vídeo."
                        ColumnLayout {
                            spacing: 6
                            RowLayout {
                                Text { text: "Progresso"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true }
                                Text { text: c.capturadas + " / " + c.total; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                            }
                            Medidor { Layout.fillWidth: true; valor: c.total > 0 ? c.capturadas / c.total : 0; cor: c.capturadas >= c.total ? Theme.sucesso : Theme.acento }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda }
                        Text { text: "Qualidade da amostra"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium }
                        BarraQualidade {
                            Layout.fillWidth: true
                            rotulo: "Nitidez"
                            valor: c.nitidez
                            maximo: pagina.lim.minNitidez * 4
                            minimo: pagina.lim.minNitidez
                            limite: -1
                            ativo: c.nRostos === 1
                        }
                        BarraQualidade {
                            Layout.fillWidth: true
                            rotulo: "Brilho"
                            valor: c.brilho
                            maximo: 255
                            minimo: pagina.lim.minBrilho
                            limite: pagina.lim.maxBrilho
                            ativo: c.nRostos === 1
                        }
                        Text {
                            Layout.fillWidth: true
                            text: c.nRostos === 0 ? "Nenhum rosto no quadro." : c.nRostos > 1 ? "Mais de um rosto: só uma pessoa pode aparecer."
                                  : c.qualidadeOk ? "Amostra aprovada: o rosto está nítido e bem iluminado." : "Ajuste a posição ou a luz até as barras ficarem dentro da faixa."
                            color: c.nRostos > 1 ? Theme.aviso : (c.qualidadeOk ? Theme.sucesso : Theme.texto3)
                            font.pixelSize: Theme.tLegenda
                            wrapMode: Text.Wrap
                        }
                        RowLayout {
                            spacing: 8
                            Botao {
                                Layout.fillWidth: true
                                text: c.capturadas >= c.total ? "Concluir cadastro" : "Aguardando amostras"
                                icone: "ok"
                                variante: "primario"
                                enabled: c.fase === "capturando" && c.capturadas >= c.total
                                onClicked: c.concluir()
                            }
                            Botao {
                                text: "Cancelar"
                                onClicked: c.capturadas > 0 ? confirmarCancelar.open() : c.cancelar()
                            }
                        }
                        Text {
                            visible: c.pausada
                            text: "A câmera foi desligada ao sair da tela. A captura continua quando você voltar."
                            color: Theme.aviso
                            font.pixelSize: Theme.tLegenda
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                    }

                    // formulário
                    Painel {
                        Layout.fillWidth: true
                        titulo: "Dados do usuário"
                        subtitulo: "A matrícula identifica a pessoa e não pode se repetir"
                        visible: c.fase === "formulario" || c.fase === "importando"
                        enabled: !pagina.ocupado
                        opacity: enabled ? 1 : 0.5
                        espacamento: 14
                        Campo {
                            id: nome
                            Layout.fillWidth: true
                            rotulo: "Nome completo"
                            obrigatorio: true
                            placeholder: "Ex.: Ana Souza"
                            erro: c.erroCampo === "nome" ? c.erro : ""
                            entrada.onTextChanged: if (c.erroCampo === "nome") c.limparErro()
                            onConfirmado: matricula.entrada.forceActiveFocus()
                        }
                        Campo {
                            id: matricula
                            Layout.fillWidth: true
                            rotulo: "Matrícula"
                            obrigatorio: true
                            placeholder: "Ex.: M0042"
                            erro: c.erroCampo === "matricula" ? c.erro : pagina.avisoMatricula
                            entrada.onTextChanged: {
                                if (c.erroCampo === "matricula") c.limparErro()
                                var dono = c.matriculaEmUso(texto)
                                pagina.avisoMatricula = dono !== "" ? "Matrícula já cadastrada para " + dono + "." : ""
                            }
                            onConfirmado: cargo.entrada.forceActiveFocus()
                        }
                        Campo {
                            id: cargo
                            Layout.fillWidth: true
                            rotulo: "Cargo"
                            placeholder: "Opcional"
                            onConfirmado: pagina.iniciar()
                        }
                        ColumnLayout {
                            spacing: 6
                            Text { text: "Nível de acesso"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium }
                            Repeater {
                                model: app.niveis()
                                delegate: Rectangle {
                                    id: opcaoNivel
                                    required property var modelData
                                    readonly property bool ativo: pagina.nivelEscolhido === modelData.nivel
                                    Layout.fillWidth: true
                                    implicitHeight: linhaNivel.implicitHeight + 18
                                    radius: Theme.raioPequeno + 1
                                    color: ativo ? Theme.realce : (areaNivel.containsMouse ? Theme.elevada : Theme.campo)
                                    border.color: ativo ? Theme.corNivel(modelData.nivel) : Theme.borda
                                    border.width: ativo ? 1.5 : 1
                                    Behavior on color { ColorAnimation { duration: Theme.rapido } }
                                    RowLayout {
                                        id: linhaNivel
                                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                                        spacing: 10
                                        Rectangle {
                                            width: 16; height: 16; radius: 8
                                            color: "transparent"
                                            border.width: 1.5
                                            border.color: opcaoNivel.ativo ? Theme.corNivel(opcaoNivel.modelData.nivel) : Theme.bordaForte
                                            Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: 4; visible: opcaoNivel.ativo; color: Theme.corNivel(opcaoNivel.modelData.nivel) }
                                        }
                                        ColumnLayout {
                                            spacing: 1
                                            Layout.fillWidth: true
                                            Text { text: "Nível " + opcaoNivel.modelData.nivel + ": " + opcaoNivel.modelData.descricao; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium }
                                            Text { text: "Libera até: " + opcaoNivel.modelData.area; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                        }
                                    }
                                    MouseArea { id: areaNivel; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pagina.nivelEscolhido = opcaoNivel.modelData.nivel }
                                }
                            }
                        }
                        Text {
                            visible: c.erro !== "" && c.erroCampo === ""
                            text: c.erro
                            color: Theme.perigo
                            font.pixelSize: Theme.tPequeno
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                        RowLayout {
                            spacing: 8
                            Botao {
                                Layout.fillWidth: true
                                text: "Iniciar captura"
                                icone: "camera"
                                variante: "primario"
                                enabled: pagina.avisoMatricula === ""
                                onClicked: pagina.iniciar()
                            }
                            Botao {
                                text: "Importar fotos"
                                icone: "imagem"
                                dica: "Cadastrar a partir de arquivos de imagem (scanner ou câmera externa)"
                                enabled: pagina.avisoMatricula === ""
                                carregando: c.fase === "importando"
                                onClicked: dialogoFotos.open()
                            }
                        }
                    }
                }
            }
        }
    }

    component BarraQualidade: ColumnLayout {
        id: bq
        property string rotulo
        property real valor
        property real maximo: 1
        property real minimo: 0
        property real limite: -1
        property bool ativo: true
        readonly property bool dentro: valor >= minimo && (limite < 0 || valor <= limite)
        spacing: 4
        RowLayout {
            Text { text: bq.rotulo; color: Theme.texto3; font.pixelSize: Theme.tLegenda; Layout.fillWidth: true }
            Text {
                text: bq.ativo ? Math.round(bq.valor) : "–"
                color: !bq.ativo ? Theme.texto3 : bq.dentro ? Theme.sucesso : Theme.aviso
                font.pixelSize: Theme.tPequeno
                font.features: { "tnum": 1 }
            }
        }
        Item {
            Layout.fillWidth: true
            implicitHeight: 10
            Rectangle {
                id: trilhoQ
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                height: 5; radius: 3; color: Theme.realce
                Rectangle {     // faixa aceita
                    x: parent.width * Math.min(1, bq.minimo / bq.maximo)
                    width: parent.width * Math.min(1, (bq.limite < 0 ? bq.maximo : bq.limite) / bq.maximo) - x
                    height: parent.height; radius: 3
                    color: Theme.sucessoSuave
                }
            }
            Rectangle {
                visible: bq.ativo
                width: 10; height: 10; radius: 5
                anchors.verticalCenter: parent.verticalCenter
                x: Math.max(0, Math.min(trilhoQ.width - width, trilhoQ.width * bq.valor / bq.maximo - 5))
                color: bq.dentro ? Theme.sucesso : Theme.aviso
                border.color: Theme.janela
                border.width: 2
                Behavior on x { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
            }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Campo.qml` (52 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Campo de texto com rótulo, dica e mensagem de erro.
ColumnLayout {
    id: c
    property string rotulo: ""
    property string ajuda: ""
    property string erro: ""
    property alias texto: entrada.text
    property alias placeholder: entrada.placeholderText
    property alias entrada: entrada
    property bool obrigatorio: false
    signal confirmado()
    spacing: 6

    RowLayout {
        visible: c.rotulo !== ""
        spacing: 4
        Text { text: c.rotulo; color: Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium }
        Text { visible: c.obrigatorio; text: "obrigatório"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
    }
    TextField {
        id: entrada
        Layout.fillWidth: true
        implicitHeight: 36
        color: Theme.texto
        placeholderTextColor: Theme.texto3
        selectionColor: Theme.acentoForte
        selectedTextColor: Theme.sobreCor
        font.pixelSize: Theme.tCorpo
        leftPadding: 12
        rightPadding: 12
        onAccepted: c.confirmado()
        background: Rectangle {
            radius: Theme.raioPequeno
            color: entrada.enabled ? Theme.campo : Theme.superficie
            border.width: entrada.activeFocus || c.erro !== "" ? 1.5 : 1
            border.color: c.erro !== "" ? Theme.perigo : (entrada.activeFocus ? Theme.acento : (entrada.hovered ? Theme.bordaForte : Theme.borda))
            Behavior on border.color { ColorAnimation { duration: Theme.rapido } }
        }
    }
    Text {
        visible: c.erro !== "" || c.ajuda !== ""
        text: c.erro !== "" ? c.erro : c.ajuda
        color: c.erro !== "" ? Theme.perigo : Theme.texto3
        font.pixelSize: Theme.tLegenda
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Carregando.qml` (27 linhas)

```qml
import QtQuick
import QtQuick.Shapes

// Indicador de carregamento (arco girando).
Item {
    id: c
    property real tamanho: 20
    property color cor: Theme.acento
    implicitWidth: tamanho
    implicitHeight: tamanho
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        RotationAnimator on rotation { from: 0; to: 360; duration: 900; loops: Animation.Infinite; running: c.visible }
        ShapePath {
            strokeColor: c.cor
            strokeWidth: Math.max(1.5, c.tamanho / 9)
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: c.tamanho / 2; centerY: c.tamanho / 2
                radiusX: c.tamanho / 2 - 2; radiusY: c.tamanho / 2 - 2
                startAngle: 0; sweepAngle: 270
            }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Chave.qml` (49 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Interruptor com título e descrição.
Switch {
    id: ch
    property string descricao: ""
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    padding: 0
    rightPadding: 48
    spacing: 12
    indicator: Rectangle {
        x: ch.width - width
        anchors.verticalCenter: parent.verticalCenter
        implicitWidth: 36
        implicitHeight: 20
        radius: 10
        color: ch.checked ? Theme.acento : Theme.realce
        border.color: ch.checked ? Theme.acento : Theme.bordaForte
        opacity: ch.enabled ? 1 : 0.45
        Behavior on color { ColorAnimation { duration: Theme.medio } }
        Rectangle {
            x: ch.checked ? parent.width - width - 3 : 3
            anchors.verticalCenter: parent.verticalCenter
            width: 14; height: 14; radius: 7
            color: ch.checked ? Theme.sobreCor : Theme.texto2
            Behavior on x { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
        }
        Rectangle {
            anchors.fill: parent; anchors.margins: -3; radius: 13
            color: "transparent"; border.width: 2; border.color: Theme.acento
            opacity: ch.visualFocus ? 0.7 : 0
        }
    }
    contentItem: ColumnLayout {
        spacing: 1
        Text { text: ch.text; color: ch.enabled ? Theme.texto : Theme.texto3; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium }
        Text {
            visible: ch.descricao !== ""
            text: ch.descricao
            color: Theme.texto3
            font.pixelSize: Theme.tPequeno
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/ConfigPagina.qml` (342 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Configurações: parâmetros de cofre.config agrupados por seção, com validação, alterações
// pendentes, aplicar/descartar e o arquivo config_usuario.json. Cada campo diz quando passa a valer.
Item {
    id: pagina
    readonly property var c: app.configuracoes

    Confirmacao {
        id: confirmarPadroes
        titulo: "Restaurar os valores padrão?"
        texto: "O formulário volta aos valores com que o aplicativo abriu. Nada muda até você clicar em Aplicar."
        textoConfirmar: "Restaurar no formulário"
        icone: "desfazer"
        onConfirmado: c.restaurarPadroes()
    }
    Confirmacao {
        id: confirmarCarregar
        titulo: "Carregar o arquivo salvo?"
        texto: "Os valores de " + c.caminhoArquivo() + " substituem o formulário e são aplicados na hora."
        textoConfirmar: "Carregar e aplicar"
        icone: "arquivo"
        onConfirmado: c.carregar()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 16

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Configurações"
            descricao: "Parâmetros do reconhecimento, da prova de vida, do cadastro e da câmera"
            Botao { visible: c.pendentes > 0; text: "Descartar"; icone: "desfazer"; variante: "fantasma"; onClicked: c.descartar() }
            Botao {
                text: c.pendentes > 0 ? (c.pendentes === 1 ? "Aplicar 1 alteração" : "Aplicar " + c.pendentes + " alterações") : "Aplicar"
                icone: "ok"
                variante: "primario"
                enabled: c.pendentes > 0
                onClicked: c.aplicar()
            }
        }

        // mensagem de estado
        Rectangle {
            Layout.fillWidth: true
            visible: c.mensagem !== ""
            implicitHeight: msg.implicitHeight + 18
            radius: Theme.raio
            readonly property color tom: c.mensagemTipo === "ok" ? Theme.sucesso : c.mensagemTipo === "erro" ? Theme.perigo
                                       : c.mensagemTipo === "aviso" ? Theme.aviso : Theme.acento
            color: Qt.rgba(tom.r, tom.g, tom.b, 0.09)
            border.color: Qt.rgba(tom.r, tom.g, tom.b, 0.3)
            RowLayout {
                anchors { fill: parent; margins: 9; leftMargin: 12; rightMargin: 12 }
                spacing: 10
                Icone {
                    nome: c.mensagemTipo === "ok" ? "ok" : c.mensagemTipo === "erro" ? "erro" : c.mensagemTipo === "aviso" ? "alerta" : "info"
                    tamanho: 16
                    cor: parent.parent.tom
                }
                Text { id: msg; Layout.fillWidth: true; text: c.mensagem; color: Theme.texto; font.pixelSize: Theme.tPequeno; wrapMode: Text.WordWrap }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            // ------------------------------------------------- campos por seção
            ScrollView {
                id: rolagem
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: rolagem.availableWidth
                    spacing: 16

                    Repeater {
                        model: c.secoes()
                        delegate: Painel {
                            id: secao
                            required property var modelData
                            Layout.fillWidth: true
                            titulo: modelData
                            espacamento: 0
                            Repeater {
                                model: c.modeloCampos
                                delegate: CampoConfig {
                                    Layout.fillWidth: true
                                    visible: model.secao === secao.modelData
                                }
                            }
                        }
                    }
                    Item { implicitHeight: 4 }
                }
            }

            // ------------------------------------------------- arquivo e sistema
            ScrollView {
                Layout.preferredWidth: pagina.width < 1150 ? 270 : 320
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ColumnLayout {
                    width: parent.width
                    spacing: 16

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Arquivo de configuração"
                        subtitulo: c.arquivoExiste ? "Aplicado automaticamente ao abrir o aplicativo" : "Nenhum arquivo salvo ainda"
                        Text {
                            Layout.fillWidth: true
                            text: c.caminhoArquivo()
                            color: Theme.texto3
                            font.pixelSize: Theme.tLegenda
                            wrapMode: Text.WrapAnywhere
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Botao { Layout.fillWidth: true; text: "Salvar"; icone: "salvar"; dica: "Grava o formulário no arquivo"; onClicked: c.salvar() }
                            Botao { Layout.fillWidth: true; text: "Carregar"; icone: "arquivo"; enabled: c.arquivoExiste; dica: "Lê o arquivo e aplica"; onClicked: confirmarCarregar.open() }
                        }
                        Botao { Layout.fillWidth: true; text: "Restaurar padrões"; icone: "desfazer"; variante: "fantasma"; onClicked: confirmarPadroes.open() }
                    }

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Níveis de acesso"
                        subtitulo: "Quem tem nível N acessa as áreas de nível N ou menor"
                        espacamento: 10
                        Repeater {
                            model: c.niveis()
                            delegate: RowLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 10
                                Rectangle {
                                    width: 24; height: 24; radius: 7
                                    Layout.alignment: Qt.AlignTop
                                    color: Qt.rgba(Theme.corNivel(modelData.nivel).r, Theme.corNivel(modelData.nivel).g, Theme.corNivel(modelData.nivel).b, 0.15)
                                    Text { anchors.centerIn: parent; text: modelData.nivel; color: Theme.corNivel(modelData.nivel); font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text { text: modelData.descricao; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; Layout.fillWidth: true; elide: Text.ElideRight }
                                    Text { text: modelData.area; color: Theme.texto3; font.pixelSize: Theme.tLegenda; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                                }
                            }
                        }
                    }

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Sistema"
                        espacamento: 8
                        Repeater {
                            model: c.informacoes()
                            delegate: ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 1
                                Text { text: modelData.nome; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                                Text { text: modelData.valor; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                            }
                        }
                    }
                }
            }
        }
    }

    // Uma linha de parâmetro: rótulo, selos, explicação, quando vale e o controle.
    component CampoConfig: Item {
        id: cc
        required property var model
        required property int index
        readonly property bool numero: model.tipo !== "bool"
        implicitHeight: visible ? corpo.implicitHeight + 28 : 0

        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 1
            color: Theme.borda
            opacity: 0.7
        }
        Rectangle {
            visible: cc.model.alterado
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom; topMargin: 14; bottomMargin: 14; leftMargin: -18 }
            width: 2
            radius: 1
            color: Theme.aviso
        }

        RowLayout {
            id: corpo
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: pagina.width < 1150 ? 14 : 24

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                RowLayout {
                    spacing: 8
                    Text { text: cc.model.rotulo; color: cc.model.editavel ? Theme.texto : Theme.texto2; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium }
                    Selo { visible: cc.model.seguranca; texto: "Segurança"; icone: "escudo"; cor: Theme.acento }
                    Selo { visible: cc.model.alterado; texto: "Pendente"; cor: Theme.aviso }
                    Selo { visible: !cc.model.alterado && cc.model.diferePadrao; texto: "Alterado"; cor: Theme.texto2 }
                }
                Text {
                    Layout.fillWidth: true
                    text: cc.model.explicacao
                    color: Theme.texto2
                    font.pixelSize: Theme.tPequeno
                    wrapMode: Text.WordWrap
                    lineHeight: 1.15
                }
                RowLayout {
                    spacing: 6
                    Layout.topMargin: 2
                    Icone { nome: cc.model.editavel ? "relogio" : "cadeado"; tamanho: 13; cor: cc.model.editavel ? Theme.texto3 : Theme.aviso }
                    Text {
                        Layout.fillWidth: true
                        text: cc.model.textoEfeito + (cc.model.alterado ? ". Em uso: " + cc.model.textoAplicado : "")
                        color: cc.model.editavel ? Theme.texto3 : Theme.aviso
                        font.pixelSize: Theme.tLegenda
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // controle
            Item {
                Layout.preferredWidth: pagina.width < 1150 ? 180 : 250
                Layout.alignment: Qt.AlignVCenter
                implicitHeight: cc.numero ? 36 : 22

                Switch {
                    id: chave
                    visible: !cc.numero
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    enabled: cc.model.editavel
                    checked: cc.model.valor === true
                    hoverEnabled: true
                    padding: 0
                    implicitWidth: 36
                    implicitHeight: 20
                    onToggled: c.definir(cc.model.chave, checked)
                    indicator: Rectangle {
                        implicitWidth: 36
                        implicitHeight: 20
                        radius: 10
                        color: chave.checked ? Theme.acento : Theme.realce
                        border.color: chave.checked ? Theme.acento : Theme.bordaForte
                        opacity: chave.enabled ? 1 : 0.45
                        Behavior on color { ColorAnimation { duration: Theme.medio } }
                        Rectangle {
                            x: chave.checked ? parent.width - width - 3 : 3
                            anchors.verticalCenter: parent.verticalCenter
                            width: 14; height: 14; radius: 7
                            color: chave.checked ? Theme.sobreCor : Theme.texto2
                            Behavior on x { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
                        }
                    }
                    contentItem: Item {}
                    Dica { visible: chave.hovered && !chave.enabled; text: "Somente leitura nesta versão" }
                }

                RowLayout {
                    visible: cc.numero
                    anchors.fill: parent
                    spacing: 10
                    Slider {
                        id: deslizador
                        Layout.fillWidth: true
                        enabled: cc.model.editavel
                        from: cc.model.minimo
                        to: cc.model.maximo
                        stepSize: cc.model.passo
                        snapMode: Slider.SnapAlways
                        value: cc.numero ? Number(cc.model.valor) : 0
                        onMoved: c.definir(cc.model.chave, value)
                        background: Rectangle {
                            x: deslizador.leftPadding
                            y: deslizador.topPadding + deslizador.availableHeight / 2 - height / 2
                            width: deslizador.availableWidth
                            height: 4
                            radius: 2
                            color: Theme.realce
                            opacity: deslizador.enabled ? 1 : 0.5
                            Rectangle { width: deslizador.visualPosition * parent.width; height: parent.height; radius: 2; color: cc.model.alterado ? Theme.aviso : Theme.acento }
                        }
                        handle: Rectangle {
                            x: deslizador.leftPadding + deslizador.visualPosition * (deslizador.availableWidth - width)
                            y: deslizador.topPadding + deslizador.availableHeight / 2 - height / 2
                            width: 14; height: 14; radius: 7
                            color: deslizador.enabled ? Theme.texto : Theme.texto3
                            border.color: deslizador.pressed ? Theme.acento : "transparent"
                            border.width: 2
                        }
                    }
                    TextField {
                        id: entrada
                        Layout.preferredWidth: 72
                        implicitHeight: 32
                        enabled: cc.model.editavel
                        horizontalAlignment: Text.AlignRight
                        text: cc.model.texto
                        color: acceptableInput || !activeFocus ? Theme.texto : Theme.perigo
                        font.pixelSize: Theme.tCorpo
                        font.features: { "tnum": 1 }
                        selectByMouse: true
                        validator: RegularExpressionValidator { regularExpression: cc.model.tipo === "int" ? /-?\d{0,4}/ : /-?\d{0,4}([.,]\d{0,3})?/ }
                        onEditingFinished: if (text !== cc.model.texto) c.definir(cc.model.chave, text)
                        background: Rectangle {
                            radius: Theme.raioPequeno
                            color: Theme.campo
                            opacity: entrada.enabled ? 1 : 0.5
                            border.width: entrada.activeFocus ? 1.5 : 1
                            border.color: entrada.activeFocus ? Theme.acento : (cc.model.alterado ? Qt.rgba(Theme.aviso.r, Theme.aviso.g, Theme.aviso.b, 0.6) : Theme.borda)
                        }
                        Dica { visible: entrada.hovered; text: "Entre " + cc.model.minimo + " e " + cc.model.maximo + (cc.model.editavel ? "" : ". Somente leitura nesta versão") }
                    }
                }
            }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Confirmacao.qml` (55 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Diálogo modal de confirmação (ações destrutivas usam perigo: true).
Popup {
    id: d
    property string titulo: ""
    property string texto: ""
    property string textoConfirmar: "Confirmar"
    property bool perigo: false
    property string icone: perigo ? "alerta" : "info"
    signal confirmado()
    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(440, parent ? parent.width - 48 : 440)
    padding: 22
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.55) }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.medio }
            NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.medio; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.rapido } }
    background: Rectangle { radius: Theme.raioGrande; color: Theme.elevada; border.color: Theme.bordaForte }
    contentItem: ColumnLayout {
        spacing: 14
        RowLayout {
            spacing: 12
            Rectangle {
                width: 36; height: 36; radius: 10
                color: d.perigo ? Theme.perigoSuave : Theme.acentoSuave
                Icone { anchors.centerIn: parent; nome: d.icone; tamanho: 18; cor: d.perigo ? Theme.perigo : Theme.acento }
            }
            Text { text: d.titulo; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
        Text { text: d.texto; color: Theme.texto2; font.pixelSize: Theme.tCorpo; wrapMode: Text.Wrap; Layout.fillWidth: true; lineHeight: 1.15 }
        RowLayout {
            Layout.topMargin: 6
            spacing: 8
            Item { Layout.fillWidth: true }
            Botao { text: "Cancelar"; onClicked: d.close() }
            Botao {
                id: confirmar
                text: d.textoConfirmar
                variante: d.perigo ? "perigo" : "primario"
                onClicked: { d.close(); d.confirmado() }
            }
        }
    }
    onOpened: confirmar.forceActiveFocus()
}

```

## `cofre/qt/qml/Cofre/Ui/Dica.qml` (24 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic

// Dica (tooltip) no estilo do aplicativo. Uso: Dica { visible: alvo.hovered; text: "..." }
ToolTip {
    id: dica
    delay: 450
    timeout: 6000
    padding: 8
    contentItem: Text {
        text: dica.text
        color: Theme.texto
        font.pixelSize: Theme.tPequeno
        wrapMode: Text.Wrap
        width: Math.min(implicitWidth, 300)
    }
    background: Rectangle {
        color: Theme.realce
        radius: Theme.raioPequeno
        border.color: Theme.bordaForte
    }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.rapido } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.rapido } }
}

```

## `cofre/qt/qml/Cofre/Ui/Icone.qml` (30 linhas)

```qml
import QtQuick
import QtQuick.Shapes
import "Icones.js" as Icones

// Ícone vetorial em traço. `nome` vem de Icones.js.
Item {
    id: raiz
    property string nome: ""
    property color cor: Theme.texto2
    property real tamanho: 18
    property real traco: 1.8
    implicitWidth: tamanho
    implicitHeight: tamanho

    Shape {
        width: 24; height: 24
        scale: raiz.tamanho / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        visible: raiz.nome !== ""
        ShapePath {
            strokeColor: raiz.cor
            strokeWidth: raiz.traco
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: Icones.caminho(raiz.nome) }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Indicador.qml` (35 linhas)

```qml
import QtQuick
import QtQuick.Layouts

// Número com legenda (indicadores de resumo).
Rectangle {
    id: i
    property string rotulo: ""
    property string valor: "0"
    property string detalhe: ""
    property string icone: ""
    property color cor: Theme.texto
    color: Theme.superficie
    radius: Theme.raio
    border.color: Theme.borda
    implicitHeight: col.implicitHeight + 28
    implicitWidth: 150
    ColumnLayout {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
        spacing: 4
        RowLayout {
            spacing: 6
            Icone { visible: i.icone !== ""; nome: i.icone; tamanho: 14; cor: Theme.texto3 }
            Text { text: i.rotulo; color: Theme.texto2; font.pixelSize: Theme.tPequeno; elide: Text.ElideRight; Layout.fillWidth: true }
        }
        Text {
            text: i.valor
            color: i.cor
            font.pixelSize: 24
            font.weight: Font.DemiBold
            font.features: { "tnum": 1 }
        }
        Text { visible: i.detalhe !== ""; text: i.detalhe; color: Theme.texto3; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/ItemNavegacao.qml` (41 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Item da navegação lateral.
AbstractButton {
    id: it
    property string icone: ""
    property bool ativo: false
    property string atalho: ""
    implicitHeight: 36
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    background: Rectangle {
        radius: Theme.raioPequeno
        color: it.ativo ? Theme.realce : (it.hovered ? Qt.rgba(1, 1, 1, 0.035) : "transparent")
        border.width: it.visualFocus ? 2 : 0
        border.color: Theme.acento
        Behavior on color { ColorAnimation { duration: Theme.rapido } }
        Rectangle {
            visible: it.ativo
            width: 3; height: 16; radius: 2
            color: Theme.acento
            anchors { left: parent.left; leftMargin: -10; verticalCenter: parent.verticalCenter }
        }
    }
    contentItem: RowLayout {
        spacing: 11
        Item { implicitWidth: 2 }
        Icone { nome: it.icone; tamanho: 17; cor: it.ativo ? Theme.acento : (it.hovered ? Theme.texto : Theme.texto2) }
        Text {
            text: it.text
            color: it.ativo ? Theme.texto : (it.hovered ? Theme.texto : Theme.texto2)
            font.pixelSize: Theme.tCorpo
            font.weight: it.ativo ? Font.DemiBold : Font.Normal
            Layout.fillWidth: true
        }
        Text { visible: it.atalho !== ""; text: it.atalho; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Main.qml` (185 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
    id: janela
    width: 1360
    height: 860
    minimumWidth: 1080
    minimumHeight: 680
    visible: true
    color: Theme.janela
    title: "Cofre MMA · Autenticação biométrica"

    // Ao fechar, as páginas são descarregadas antes de o Python liberar os ViewModels.
    property bool encerrando: false
    Connections {
        target: app
        function onEncerrando() { janela.encerrando = true }
    }

    readonly property var paginas: [
        { id: "terminal", texto: "Terminal de acesso", icone: "terminal" },
        { id: "cadastro", texto: "Cadastro biométrico", icone: "cadastro" },
        { id: "usuarios", texto: "Usuários", icone: "usuarios" },
        { id: "acessos", texto: "Auditoria de acessos", icone: "acessos" },
        { id: "avaliacao", texto: "Avaliação e demo", icone: "avaliacao" },
        { id: "config", texto: "Configurações", icone: "config" }
    ]
    function indicePagina(id) {
        for (var i = 0; i < paginas.length; ++i) if (paginas[i].id === id) return i
        return 0
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ------------------------------------------------------------ navegação lateral
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: 232
            color: Theme.lateral
            Rectangle { anchors { right: parent.right; top: parent.top; bottom: parent.bottom } width: 1; color: Theme.borda }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                anchors.topMargin: 20
                spacing: 2

                RowLayout {
                    Layout.leftMargin: 6
                    Layout.bottomMargin: 22
                    spacing: 10
                    Rectangle {
                        width: 32; height: 32; radius: 9
                        color: Theme.acentoSuave
                        border.color: Qt.rgba(0.208, 0.816, 0.753, 0.35)
                        Icone { anchors.centerIn: parent; nome: "escudo"; tamanho: 17; cor: Theme.acento; traco: 2 }
                    }
                    ColumnLayout {
                        spacing: 0
                        Text { text: "Cofre MMA"; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                        Text { text: "Autenticação facial"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                    }
                }

                Repeater {
                    model: janela.paginas
                    delegate: ItemNavegacao {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        text: modelData.texto
                        icone: modelData.icone
                        atalho: "⌘" + (index + 1)
                        ativo: app.pagina === modelData.id
                        onClicked: app.navegar(modelData.id)
                    }
                }

                Item { Layout.fillHeight: true }

                // estado do sistema
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: sistema.implicitHeight + 24
                    radius: Theme.raio
                    color: Theme.superficie
                    border.color: Theme.borda
                    ColumnLayout {
                        id: sistema
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                        spacing: 8
                        LinhaSistema {
                            rotulo: "Modelos"
                            valor: app.erroModelos !== "" ? "falha" : (app.modelosProntos ? "carregados" : "carregando")
                            cor: app.erroModelos !== "" ? Theme.perigo : (app.modelosProntos ? Theme.sucesso : Theme.aviso)
                        }
                        LinhaSistema {
                            rotulo: "Câmera"
                            valor: ({ "desligada": "desligada", "abrindo": "abrindo", "ativa": "ativa", "erro": "indisponível" })[app.cameraServico.estado]
                            cor: app.cameraServico.estado === "ativa" ? Theme.sucesso : (app.cameraServico.estado === "erro" ? Theme.perigo
                                 : (app.cameraServico.estado === "abrindo" ? Theme.aviso : Theme.texto3))
                        }
                        LinhaSistema { rotulo: "Banco"; valor: app.nomeBanco(); cor: Theme.texto3 }
                    }
                }
                Text {
                    Layout.topMargin: 10
                    Layout.leftMargin: 6
                    text: "Versão " + app.versao() + "  ·  APS PIVC"
                    color: Theme.texto3
                    font.pixelSize: Theme.tLegenda
                }
            }
        }

        // ------------------------------------------------------------ páginas
        StackLayout {
            id: pilha
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: janela.indicePagina(app.pagina)

            Pagina { fonte: "TerminalPagina.qml"; id_: "terminal" }
            Pagina { fonte: "CadastroPagina.qml"; id_: "cadastro" }
            Pagina { fonte: "UsuariosPagina.qml"; id_: "usuarios" }
            Pagina { fonte: "AcessosPagina.qml"; id_: "acessos" }
            Pagina { fonte: "AvaliacaoPagina.qml"; id_: "avaliacao" }
            Pagina { fonte: "ConfigPagina.qml"; id_: "config" }
        }
    }

    component LinhaSistema: RowLayout {
        property string rotulo
        property string valor
        property color cor
        spacing: 8
        Rectangle { width: 6; height: 6; radius: 3; color: parent.cor }
        Text { text: parent.rotulo; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true }
        Text { text: parent.valor; color: Theme.texto3; font.pixelSize: Theme.tPequeno; elide: Text.ElideMiddle; Layout.maximumWidth: 110 }
    }

    // Cada página só é criada na primeira visita (abre mais rápido).
    component Pagina: Loader {
        property string fonte
        property string id_
        active: false
        asynchronous: false
        source: active && !janela.encerrando ? fonte : ""
        readonly property bool atual: app.pagina === id_
        onAtualChanged: if (atual) active = true
        Component.onCompleted: if (atual) active = true
    }

    // área liberada depois de um acesso concedido: cobre a janela inteira até a sessão encerrar
    Loader {
        anchors.fill: parent
        z: 50
        active: !janela.encerrando
        sourceComponent: AreaLiberada {}
    }

    Notificacoes {
        anchors { right: parent.right; bottom: parent.bottom; margins: 20 }
        height: parent.height - 40
        z: 100
    }

    Repeater {
        model: janela.paginas
        delegate: Item {
            required property var modelData
            required property int index
            Shortcut {
                sequence: "Ctrl+" + (index + 1)
                context: Qt.ApplicationShortcut
                enabled: !app.sessao.ativa
                onActivated: app.navegar(modelData.id)
            }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Medidor.qml` (39 linhas)

```qml
import QtQuick
import QtQuick.Layouts

// Barra 0..1 com marca do limiar (similaridade) ou progresso simples.
Item {
    id: m
    property real valor: 0           // < 0 = sem leitura
    property real limiar: -1         // < 0 = sem marca
    property color cor: valor >= limiar && limiar >= 0 ? Theme.sucesso : (limiar >= 0 ? Theme.perigo : Theme.acento)
    property real altura: 6
    implicitHeight: altura + (limiar >= 0 ? 6 : 0)
    implicitWidth: 200
    Rectangle {
        id: trilho
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
        height: m.altura
        radius: height / 2
        color: Theme.realce
        Rectangle {
            width: m.valor < 0 ? 0 : Math.max(height, parent.width * Math.min(1, m.valor))
            height: parent.height
            radius: parent.radius
            color: m.cor
            visible: m.valor >= 0
            Behavior on width { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: Theme.medio } }
        }
    }
    Rectangle {
        visible: m.limiar >= 0
        x: trilho.width * m.limiar - 1
        anchors.verticalCenter: parent.verticalCenter
        width: 2
        height: m.altura + 8
        radius: 1
        color: Theme.texto
        opacity: 0.85
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Notificacoes.qml` (49 linhas)

```qml
import QtQuick
import QtQuick.Layouts

// Pilha de notificações temporárias (canto inferior direito), alimentada por app.notificacao.
Item {
    id: n
    width: 380
    ListModel { id: fila }
    Connections {
        target: app
        function onNotificacao(tipo, texto) {
            fila.append({ tipo: tipo, texto: texto })
            if (fila.count > 4) fila.remove(0)
        }
    }
    Column {
        anchors { right: parent.right; bottom: parent.bottom }
        spacing: 8
        Repeater {
            model: fila
            delegate: Rectangle {
                id: t
                required property string tipo
                required property string texto
                required property int index
                width: n.width
                height: linha.implicitHeight + 22
                radius: Theme.raio
                color: Theme.elevada
                border.color: Theme.bordaForte
                opacity: 0
                Component.onCompleted: opacity = 1
                Behavior on opacity { NumberAnimation { duration: Theme.medio } }
                readonly property color cor: tipo === "ok" ? Theme.sucesso : tipo === "erro" ? Theme.perigo
                                            : tipo === "aviso" ? Theme.aviso : Theme.acento
                Rectangle { width: 3; radius: 2; color: t.cor; anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 8 } }
                RowLayout {
                    id: linha
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 20; rightMargin: 8 }
                    spacing: 10
                    Icone { nome: t.tipo === "ok" ? "ok" : t.tipo === "erro" ? "erro" : t.tipo === "aviso" ? "alerta" : "info"; cor: t.cor; tamanho: 16 }
                    Text { text: t.texto; color: Theme.texto; font.pixelSize: Theme.tCorpo; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    BotaoIcone { icone: "fechar"; dica: "Fechar"; tamanho: 24; onClicked: fila.remove(t.index) }
                }
                Timer { interval: t.tipo === "erro" ? 7000 : 4200; running: true; onTriggered: if (t.index >= 0 && t.index < fila.count) fila.remove(t.index) }
            }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Painel.qml` (44 linhas)

```qml
import QtQuick
import QtQuick.Layouts

// Superfície elevada com borda sutil. O conteúdo vai para uma ColumnLayout interna.
Rectangle {
    id: p
    default property alias conteudo: corpo.data
    property int preenchimento: 18
    property int espacamento: 12
    property string titulo: ""
    property string subtitulo: ""
    property alias cabecalhoDireita: direita.data
    color: Theme.superficie
    radius: Theme.raioGrande
    border.color: Theme.borda
    implicitHeight: corpo.implicitHeight + 2 * preenchimento + (cab.visible ? cab.implicitHeight + espacamento : 0)
    implicitWidth: Math.max(corpo.implicitWidth, cab.implicitWidth) + 2 * preenchimento

    RowLayout {
        id: cab
        visible: p.titulo !== ""
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: p.preenchimento }
        spacing: 8
        ColumnLayout {
            spacing: 2
            Layout.fillWidth: true
            Text { text: p.titulo; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
            Text { visible: p.subtitulo !== ""; text: p.subtitulo; color: Theme.texto3; font.pixelSize: Theme.tPequeno; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
        RowLayout { id: direita; spacing: 6 }
    }
    ColumnLayout {
        id: corpo
        spacing: p.espacamento
        anchors {
            left: parent.left; right: parent.right
            top: cab.visible ? cab.bottom : parent.top
            bottom: parent.bottom
            leftMargin: p.preenchimento; rightMargin: p.preenchimento
            topMargin: cab.visible ? p.espacamento : p.preenchimento
            bottomMargin: p.preenchimento
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Segmentado.qml` (58 linhas)

```qml
import QtQuick
import QtQuick.Layouts

// Controle segmentado. `opcoes`: lista de { valor, texto, dica? }.
Rectangle {
    id: seg
    property var opcoes: []
    property var atual
    property bool habilitado: true
    signal escolhido(var valor)
    implicitHeight: 32
    implicitWidth: linha.implicitWidth + 6
    radius: Theme.raioPequeno + 2
    color: Theme.campo
    border.color: Theme.borda
    opacity: habilitado ? 1 : 0.5

    RowLayout {
        id: linha
        anchors.fill: parent
        anchors.margins: 3
        spacing: 2
        Repeater {
            model: seg.opcoes
            delegate: Rectangle {
                id: item
                required property var modelData
                required property int index
                readonly property bool ativo: seg.atual === modelData.valor
                Layout.fillWidth: true
                Layout.fillHeight: true
                implicitWidth: rotulo.implicitWidth + 22
                radius: Theme.raioPequeno
                color: ativo ? Theme.realce : (area.containsMouse && seg.habilitado ? Qt.rgba(1, 1, 1, 0.03) : "transparent")
                border.width: ativo ? 1 : 0
                border.color: Theme.bordaForte
                Behavior on color { ColorAnimation { duration: Theme.rapido } }
                Text {
                    id: rotulo
                    anchors.centerIn: parent
                    text: item.modelData.texto
                    color: item.ativo ? Theme.texto : Theme.texto2
                    font.pixelSize: Theme.tPequeno
                    font.weight: item.ativo ? Font.DemiBold : Font.Normal
                }
                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: seg.habilitado
                    cursorShape: Qt.PointingHandCursor
                    onClicked: seg.escolhido(item.modelData.valor)
                }
                Dica { visible: area.containsMouse && (item.modelData.dica || "") !== ""; text: item.modelData.dica || "" }
            }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Seletor.qml` (68 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic

// Lista suspensa. `opcoes`: lista de { valor, texto }.
ComboBox {
    id: cb
    property var opcoes: []
    property var atual
    signal escolhido(var valor)
    model: opcoes
    textRole: "texto"
    valueRole: "valor"
    implicitHeight: 34
    implicitWidth: 180
    font.pixelSize: Theme.tCorpo
    hoverEnabled: true
    currentIndex: {
        for (var i = 0; i < opcoes.length; ++i) if (opcoes[i].valor === atual) return i
        return 0
    }
    onActivated: function(indice) { cb.escolhido(opcoes[indice].valor) }

    contentItem: Text {
        leftPadding: 12
        rightPadding: 30
        text: cb.displayText
        color: Theme.texto
        font: cb.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Icone { x: cb.width - width - 10; anchors.verticalCenter: parent.verticalCenter; nome: "baixo"; tamanho: 14; cor: Theme.texto3 }
    background: Rectangle {
        radius: Theme.raioPequeno
        color: cb.hovered ? Theme.realce : Theme.elevada
        border.width: cb.visualFocus ? 1.5 : 1
        border.color: cb.visualFocus ? Theme.acento : Theme.borda
    }
    delegate: ItemDelegate {
        id: opc
        required property var modelData
        required property int index
        width: ListView.view ? ListView.view.width : 0
        height: 32
        hoverEnabled: true
        contentItem: Text {
            text: opc.modelData.texto
            color: cb.currentIndex === opc.index ? Theme.acento : Theme.texto
            font.pixelSize: Theme.tCorpo
            verticalAlignment: Text.AlignVCenter
            leftPadding: 4
        }
        background: Rectangle { radius: Theme.raioPequeno - 2; color: opc.hovered ? Theme.realce : "transparent" }
    }
    popup: Popup {
        y: cb.height + 4
        width: Math.max(cb.width, 200)
        padding: 4
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 320)
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: cb.popup.visible ? cb.delegateModel : null
            currentIndex: cb.highlightedIndex
        }
        background: Rectangle { radius: Theme.raio; color: Theme.elevada; border.color: Theme.bordaForte }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Selo.qml` (29 linhas)

```qml
import QtQuick
import QtQuick.Layouts

// Selo compacto (estado, nível, resultado).
Rectangle {
    id: s
    property string texto: ""
    property color cor: Theme.texto2
    property string icone: ""
    property bool solido: false
    implicitHeight: 22
    implicitWidth: linha.implicitWidth + 16
    radius: height / 2
    color: solido ? cor : Qt.rgba(cor.r, cor.g, cor.b, 0.13)
    border.width: solido ? 0 : 1
    border.color: Qt.rgba(cor.r, cor.g, cor.b, 0.28)
    RowLayout {
        id: linha
        anchors.centerIn: parent
        spacing: 5
        Icone { visible: s.icone !== ""; nome: s.icone; tamanho: 12; traco: 2.2; cor: s.solido ? Theme.sobreCor : s.cor }
        Text {
            text: s.texto
            color: s.solido ? Theme.sobreCor : s.cor
            font.pixelSize: Theme.tLegenda
            font.weight: Font.DemiBold
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/TerminalPagina.qml` (752 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Cofre.Nativo

// Terminal de acesso: câmera dominante à esquerda, painel compacto à direita.
// Toda decisão exibida vem do TerminalAutenticacao (app.terminal); esta tela só a apresenta.
Item {
    id: pagina
    readonly property var t: app.terminal
    readonly property var cam: app.cameraServico
    readonly property string estado: t.estado
    readonly property var poseLimites: t.limitesPose()
    readonly property bool emResultado: estado === "RESULTADO" && t.resultadoTipo !== ""
    readonly property bool bloqueado: estado === "BLOQUEADO"
    readonly property bool concedido: emResultado && t.resultadoConcedido === true
    readonly property color corEstado: {
        if (bloqueado) return Theme.perigo
        if (emResultado) return concedido ? Theme.sucesso : Theme.perigo
        if (estado === "CONFIRMANDO" || estado === "LIVENESS") return Theme.acento
        return Theme.bordaForte
    }

    // atalhos iguais aos da versão de linha de comando
    Shortcut { sequences: ["1"]; enabled: pagina.visible && !pagina.bloqueado; onActivated: t.definirNivel(1) }
    Shortcut { sequences: ["2"]; enabled: pagina.visible && !pagina.bloqueado; onActivated: t.definirNivel(2) }
    Shortcut { sequences: ["3"]; enabled: pagina.visible && !pagina.bloqueado; onActivated: t.definirNivel(3) }
    Shortcut { sequences: ["L"]; enabled: pagina.visible && !pagina.bloqueado; onActivated: t.definirLiveness(!t.liveness) }
    Shortcut { sequences: ["D"]; enabled: pagina.visible; onActivated: t.definirDidatico(!t.didatico) }
    Shortcut { sequences: ["R"]; enabled: pagina.visible; onActivated: t.recarregarGaleria() }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 18

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Terminal de acesso"
            descricao: "Nível " + t.nivel + " exigido: " + t.area
            Selo {
                texto: cam.estado === "ativa" ? Math.round(cam.fps) + " fps" : (cam.estado === "abrindo" ? "abrindo câmera" : (cam.estado === "erro" ? "câmera indisponível" : "câmera desligada"))
                cor: cam.estado === "ativa" ? Theme.sucesso : (cam.estado === "erro" ? Theme.perigo : Theme.texto2)
                icone: cam.estado === "erro" ? "cameraOff" : "camera"
            }
            Selo { texto: t.galeria + " amostras na galeria"; cor: Theme.texto2; icone: "banco" }
            BotaoIcone { icone: "recarregar"; dica: "Recarregar galeria (R)"; onClicked: t.recarregarGaleria() }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 18

            // -------------------------------------------------------- vídeo
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                Rectangle {
                    id: moldura
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 300
                    radius: Theme.raioGrande + 2
                    color: Theme.lateral
                    border.width: 2
                    border.color: pagina.corEstado
                    Behavior on border.color { ColorAnimation { duration: Theme.lento } }

                    // brilho breve quando a decisão chega
                    Rectangle {
                        id: brilho
                        anchors.fill: parent
                        anchors.margins: -5
                        radius: parent.radius + 5
                        color: "transparent"
                        border.width: 5
                        border.color: pagina.corEstado
                        opacity: 0
                        SequentialAnimation {
                            id: pulso
                            NumberAnimation { target: brilho; property: "opacity"; to: 0.35; duration: 140 }
                            NumberAnimation { target: brilho; property: "opacity"; to: 0; duration: 650; easing.type: Easing.OutCubic }
                        }
                    }
                    Connections { target: t; function onDecisaoTomada(c, r) { pulso.restart() } }

                    VisorVideo {
                        id: visor
                        anchors.fill: parent
                        anchors.margins: 2
                        fonte: t.fonteVideo
                        raio: Theme.raioGrande
                        corFundo: Theme.lateral
                        preencher: false
                        // linha de varredura enquanto a identidade é confirmada quadro a quadro
                        varredura: -1
                        NumberAnimation on varredura {
                            running: pagina.estado === "CONFIRMANDO"
                            from: 0; to: 1; duration: 1100; loops: Animation.Infinite
                            onRunningChanged: if (!running) visor.varredura = -1
                        }
                    }

                    // área exigida (canto superior esquerdo)
                    Rectangle {
                        visible: cam.estado === "ativa"
                        anchors { left: parent.left; top: parent.top; margins: 16 }
                        height: 30
                        width: linhaArea.implicitWidth + 22
                        radius: 15
                        color: Qt.rgba(0.06, 0.07, 0.08, 0.78)
                        border.color: Theme.borda
                        RowLayout {
                            id: linhaArea
                            anchors.centerIn: parent
                            spacing: 7
                            Icone { nome: "cadeado"; tamanho: 13; cor: Theme.corNivel(t.nivel); traco: 2 }
                            Text { text: "Nível " + t.nivel; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold }
                            Text { text: t.area; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                        }
                    }

                    // instrução de base (aguardando / confirmando)
                    Rectangle {
                        id: instrucao
                        readonly property bool mostrar: cam.estado === "ativa" && (pagina.estado === "AGUARDANDO" || pagina.estado === "CONFIRMANDO")
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 22 }
                        width: Math.min(parent.width - 48, 420)
                        height: colInstrucao.implicitHeight + 24
                        radius: Theme.raio
                        color: Qt.rgba(0.06, 0.07, 0.08, 0.84)
                        border.color: Theme.borda
                        opacity: mostrar ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity { NumberAnimation { duration: Theme.medio } }
                        ColumnLayout {
                            id: colInstrucao
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }
                            spacing: 8
                            RowLayout {
                                spacing: 8
                                Icone {
                                    nome: t.nRostos > 1 || t.orientacao !== "" ? "alerta" : pagina.estado === "CONFIRMANDO" ? "foco" : "rosto"
                                    tamanho: 16
                                    cor: t.nRostos > 1 || t.orientacao !== "" ? Theme.aviso : pagina.estado === "CONFIRMANDO" ? Theme.acento : Theme.texto2
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: t.nRostos > 1 ? "Mais de uma pessoa diante do terminal"
                                          : t.orientacao !== "" ? t.orientacao
                                          : pagina.estado === "CONFIRMANDO" ? "Confirmando identidade, mantenha o rosto parado"
                                          : "Posicione o rosto de frente para a câmera"
                                    color: t.nRostos > 1 || t.orientacao !== "" ? Theme.aviso : Theme.texto
                                    font.pixelSize: Theme.tCorpo
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                }
                            }
                            Medidor {
                                visible: pagina.estado === "CONFIRMANDO"
                                Layout.fillWidth: true
                                valor: t.progresso
                                cor: Theme.acento
                                altura: 4
                            }
                        }
                    }

                    // prova de vida
                    Rectangle {
                        id: cartaoLiveness
                        readonly property bool mostrar: pagina.estado === "LIVENESS"
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 22 }
                        width: Math.min(parent.width - 48, 460)
                        height: colLiveness.implicitHeight + 32
                        radius: Theme.raioGrande
                        color: Qt.rgba(0.06, 0.07, 0.08, 0.88)
                        border.color: Qt.rgba(0.208, 0.816, 0.753, 0.4)
                        opacity: mostrar ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity { NumberAnimation { duration: Theme.medio } }
                        ColumnLayout {
                            id: colLiveness
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 20 }
                            spacing: 12
                            RowLayout {
                                spacing: 8
                                Icone { nome: "pulso"; tamanho: 16; cor: Theme.acento }
                                Text { text: "Prova de vida"; color: Theme.acento; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: Math.ceil(t.livenessRestante) + " s"
                                    color: t.livenessRestante <= 3 ? Theme.aviso : Theme.texto2
                                    font.pixelSize: Theme.tPequeno
                                    font.features: { "tnum": 1 }
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: ({ 0: "Vire o rosto para a esquerda", 1: "Agora vire para a direita", 2: "Olhe de novo para a câmera", 3: "Prova de vida concluída" })[t.livenessPasso]
                                color: Theme.texto
                                font.pixelSize: 22
                                font.weight: Font.DemiBold
                                wrapMode: Text.Wrap
                            }
                            RowLayout {
                                spacing: 6
                                Repeater {
                                    model: ["Esquerda", "Direita", "Centro"]
                                    delegate: RowLayout {
                                        required property string modelData
                                        required property int index
                                        spacing: 6
                                        Rectangle {
                                            width: 18; height: 18; radius: 9
                                            color: index < t.livenessPasso ? Theme.acento : "transparent"
                                            border.width: 1.5
                                            border.color: index <= t.livenessPasso ? Theme.acento : Theme.bordaForte
                                            Icone { anchors.centerIn: parent; visible: index < t.livenessPasso; nome: "ok"; tamanho: 11; traco: 3; cor: Theme.sobreCor }
                                        }
                                        Text { text: modelData; color: index === t.livenessPasso ? Theme.texto : Theme.texto3; font.pixelSize: Theme.tPequeno }
                                        Rectangle { visible: index < 2; width: 22; height: 1; color: Theme.bordaForte }
                                    }
                                }
                            }
                            Medidor {
                                Layout.fillWidth: true
                                valor: t.livenessTotal > 0 ? t.livenessRestante / t.livenessTotal : 0
                                cor: t.livenessRestante <= 3 ? Theme.aviso : Theme.acento
                                altura: 3
                            }
                        }
                    }

                    // veredito
                    Rectangle {
                        id: veredito
                        readonly property bool mostrar: pagina.emResultado
                        // o veredito some com um fade; o texto fica congelado durante a saída
                        property var congelado: ({ concedido: false, nome: "", nivel: 0, mensagem: "" })
                        readonly property bool vConcedido: mostrar ? pagina.concedido : congelado.concedido
                        readonly property string vNome: mostrar ? t.resultadoNome : congelado.nome
                        readonly property int vNivel: mostrar ? t.resultadoNivel : congelado.nivel
                        readonly property string vMensagem: mostrar ? t.resultadoMensagem : congelado.mensagem
                        onMostrarChanged: if (!mostrar) congelado = { concedido: pagina.concedido, nome: t.resultadoNome, nivel: t.resultadoNivel, mensagem: t.resultadoMensagem }
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: mostrar ? 22 : 8 }
                        width: Math.min(parent.width - 48, 520)
                        height: colVeredito.implicitHeight + 36
                        radius: Theme.raioGrande
                        color: Qt.rgba(0.07, 0.08, 0.10, 0.93)
                        border.width: 1
                        readonly property color corV: vConcedido ? Theme.sucesso : Theme.perigo
                        border.color: Qt.rgba(corV.r, corV.g, corV.b, 0.55)
                        opacity: mostrar ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity { NumberAnimation { duration: Theme.medio } }
                        Behavior on anchors.bottomMargin { NumberAnimation { duration: Theme.lento; easing.type: Easing.OutCubic } }
                        RowLayout {
                            id: colVeredito
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 20 }
                            spacing: 16
                            Rectangle {
                                Layout.alignment: Qt.AlignTop
                                width: 52; height: 52; radius: 16
                                color: veredito.vConcedido ? Theme.sucessoSuave : Theme.perigoSuave
                                Icone { anchors.centerIn: parent; nome: veredito.vConcedido ? "escudoOk" : "escudoX"; tamanho: 26; traco: 2; cor: veredito.corV }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 5
                                Text {
                                    text: veredito.vConcedido ? "Acesso autorizado" : "Acesso negado"
                                    color: veredito.corV
                                    font.pixelSize: 22
                                    font.weight: Font.Bold
                                }
                                RowLayout {
                                    spacing: 8
                                    visible: veredito.vNome !== ""
                                    Text { text: veredito.vNome; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.maximumWidth: 260 }
                                    Selo { visible: veredito.vNivel > 0; texto: "Nível " + veredito.vNivel; cor: Theme.corNivel(veredito.vNivel) }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: veredito.vMensagem
                                    color: Theme.texto2
                                    font.pixelSize: Theme.tCorpo
                                    wrapMode: Text.Wrap
                                    maximumLineCount: 3
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }

                    // bloqueio
                    Rectangle {
                        anchors.fill: visor
                        radius: Theme.raioGrande
                        color: Qt.rgba(0.05, 0.06, 0.07, 0.82)
                        opacity: pagina.bloqueado ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity { NumberAnimation { duration: Theme.lento } }
                        ColumnLayout {
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 60, 380)
                            spacing: 12
                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                width: 64; height: 64; radius: 20
                                color: Theme.perigoSuave
                                border.color: Qt.rgba(0.941, 0.416, 0.416, 0.35)
                                Icone { anchors.centerIn: parent; nome: "cadeado"; tamanho: 30; traco: 2; cor: Theme.perigo }
                            }
                            Text { Layout.alignment: Qt.AlignHCenter; text: "Terminal bloqueado"; color: Theme.texto; font.pixelSize: 22; font.weight: Font.Bold }
                            Text {
                                Layout.alignment: Qt.AlignHCenter
                                text: "Liberação em " + Math.ceil(t.bloqueadoRestante) + " s"
                                color: Theme.perigo
                                font.pixelSize: Theme.tDestaque
                                font.weight: Font.DemiBold
                                font.features: { "tnum": 1 }
                            }
                            Medidor {
                                Layout.fillWidth: true
                                valor: t.bloqueioTotal > 0 ? t.bloqueadoRestante / t.bloqueioTotal : 0
                                cor: Theme.perigo
                                altura: 4
                            }
                            Text {
                                Layout.fillWidth: true
                                horizontalAlignment: Text.AlignHCenter
                                text: "Várias tentativas negadas em sequência. Nenhuma autenticação é feita até o fim do bloqueio."
                                color: Theme.texto2
                                font.pixelSize: Theme.tPequeno
                                wrapMode: Text.Wrap
                            }
                        }
                    }

                    // câmera não disponível / carregando
                    ColumnLayout {
                        anchors.centerIn: parent
                        width: Math.min(parent.width - 80, 420)
                        visible: cam.estado !== "ativa"
                        spacing: 12
                        Carregando {
                            Layout.alignment: Qt.AlignHCenter
                            visible: cam.estado === "abrindo" || (!app.modelosProntos && app.erroModelos === "")
                            tamanho: 30
                        }
                        Rectangle {
                            Layout.alignment: Qt.AlignHCenter
                            visible: cam.estado === "erro" || app.erroModelos !== ""
                            width: 56; height: 56; radius: 18
                            color: Theme.perigoSuave
                            Icone { anchors.centerIn: parent; nome: "cameraOff"; tamanho: 26; cor: Theme.perigo }
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: app.erroModelos !== "" ? "Modelos não carregados"
                                  : !app.modelosProntos ? "Carregando os modelos de reconhecimento"
                                  : cam.estado === "abrindo" ? "Abrindo a câmera"
                                  : cam.estado === "erro" ? "Câmera indisponível" : "Câmera desligada"
                            color: Theme.texto
                            font.pixelSize: Theme.tDestaque
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: text !== ""
                            horizontalAlignment: Text.AlignHCenter
                            text: app.erroModelos !== "" ? app.erroModelos
                                  : cam.estado === "erro" ? cam.erro + "\n\nNo macOS, permita o acesso em Ajustes do Sistema › Privacidade e Segurança › Câmera."
                                  : ""
                            color: Theme.texto2
                            font.pixelSize: Theme.tPequeno
                            wrapMode: Text.Wrap
                        }
                        Botao {
                            Layout.alignment: Qt.AlignHCenter
                            visible: cam.estado === "erro" || cam.estado === "desligada" && app.modelosProntos
                            text: "Tentar novamente"
                            icone: "recarregar"
                            variante: "primario"
                            onClicked: t.tentarCamera()
                        }
                    }
                }

                // painel didático: as fases do pipeline em tempo real
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: t.didatico ? 168 : 0
                    visible: Layout.preferredHeight > 0
                    clip: true
                    radius: Theme.raioGrande
                    color: Theme.superficie
                    border.color: Theme.borda
                    Behavior on Layout.preferredHeight { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
                    ListView {
                        anchors.fill: parent
                        anchors.margins: 12
                        orientation: ListView.Horizontal
                        spacing: 10
                        model: t.etapas
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded; height: 6 }
                        delegate: ColumnLayout {
                            required property var modelData
                            width: 150
                            height: ListView.view.height - 8
                            spacing: 6
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: Theme.raioPequeno
                                color: Theme.lateral
                                border.color: Theme.borda
                                VisorVideo { anchors.fill: parent; anchors.margins: 1; fonte: modelData; raio: Theme.raioPequeno; corFundo: Theme.lateral; mostrarPontos: false }
                                Text { anchors.centerIn: parent; visible: !modelData.temImagem; text: "sem rosto"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                            }
                            Text { text: modelData.nome; color: Theme.texto2; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: parent.count === 0
                            text: "As imagens de cada fase aparecem aqui enquanto a câmera estiver ativa."
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                        }
                    }
                }
            }

            // -------------------------------------------------------- painel lateral
            ScrollView {
                id: rolagem
                Layout.preferredWidth: 360
                Layout.minimumWidth: 320
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: rolagem.availableWidth
                    spacing: 12

                    // área exigida
                    Painel {
                        Layout.fillWidth: true
                        titulo: "Área protegida"
                        subtitulo: "Nível mínimo exigido para liberar a porta"
                        Segmentado {
                            Layout.fillWidth: true
                            habilitado: !pagina.bloqueado
                            atual: t.nivel
                            opcoes: [
                                { valor: 1, texto: "Nível 1", dica: "Área comum do Ministério (atalho 1)" },
                                { valor: 2, texto: "Nível 2", dica: "Sala dos diretores de divisão (atalho 2)" },
                                { valor: 3, texto: "Nível 3", dica: "Cofre de toxinas, exclusivo do Ministro (atalho 3)" }
                            ]
                            onEscolhido: function(v) { t.definirNivel(v) }
                        }
                        RowLayout {
                            spacing: 8
                            Rectangle { width: 8; height: 8; radius: 4; color: Theme.corNivel(t.nivel) }
                            Text { text: t.area; color: Theme.texto2; font.pixelSize: Theme.tPequeno; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        }
                    }

                    // estado e leitura
                    Painel {
                        Layout.fillWidth: true
                        espacamento: 14
                        RowLayout {
                            spacing: 12
                            Rectangle {
                                width: 40; height: 40; radius: 12
                                color: Qt.rgba(pagina.corEstado.r, pagina.corEstado.g, pagina.corEstado.b, 0.14)
                                Behavior on color { ColorAnimation { duration: Theme.medio } }
                                Icone {
                                    anchors.centerIn: parent
                                    tamanho: 20
                                    traco: 2
                                    cor: pagina.estado === "AGUARDANDO" ? Theme.texto2 : pagina.corEstado
                                    nome: pagina.bloqueado ? "cadeado" : pagina.emResultado ? (pagina.concedido ? "escudoOk" : "escudoX")
                                          : pagina.estado === "LIVENESS" ? "pulso" : pagina.estado === "CONFIRMANDO" ? "foco" : "rosto"
                                }
                            }
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Text {
                                    text: pagina.bloqueado ? "Bloqueado" : pagina.emResultado ? (pagina.concedido ? "Autorizado" : "Negado")
                                          : pagina.estado === "LIVENESS" ? "Prova de vida" : pagina.estado === "CONFIRMANDO" ? "Confirmando" : "Aguardando"
                                    color: pagina.estado === "AGUARDANDO" ? Theme.texto : pagina.corEstado
                                    font.pixelSize: Theme.tDestaque
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: pagina.bloqueado ? "Aguarde " + Math.ceil(t.bloqueadoRestante) + " s para nova tentativa"
                                          : pagina.emResultado ? t.resultadoTitulo
                                          : pagina.estado === "LIVENESS" ? t.livenessInstrucao.charAt(0) + t.livenessInstrucao.slice(1).toLowerCase()
                                          : pagina.estado === "CONFIRMANDO" ? "Mesma identidade em " + Math.round(t.progresso * 100) + "% dos quadros"
                                          : (t.nRostos > 1 ? "Mais de uma pessoa no quadro" : t.orientacao !== "" ? "Pose fora do aceitável, sem tentativa" : "Nenhum rosto em análise")
                                    color: Theme.texto2
                                    font.pixelSize: Theme.tPequeno
                                    elide: Text.ElideRight
                                }
                            }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda }
                        ColumnLayout {
                            spacing: 8
                            RowLayout {
                                Text { text: "Similaridade"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true }
                                Text {
                                    text: t.similaridade < 0 ? "sem leitura" : t.similaridade.toFixed(3)
                                    // verde fica reservado para "autorizado": aqui só se indica se o rosto bate com alguém da galeria
                                    color: t.similaridade < 0 || pagina.estado === "BLOQUEADO" ? Theme.texto3 : (t.similaridade >= t.limiar ? Theme.acento : Theme.texto2)
                                    font.pixelSize: Theme.tCorpo
                                    font.weight: Font.DemiBold
                                    font.features: { "tnum": 1 }
                                }
                            }
                            Medidor {
                                Layout.fillWidth: true
                                valor: t.similaridade
                                limiar: t.limiar
                                cor: pagina.estado === "BLOQUEADO" ? Theme.texto3 : (t.similaridade >= t.limiar ? Theme.acento : Theme.texto2)
                            }
                            Text { text: "Limiar " + t.limiar.toFixed(3) + ". Acima dele o rosto é considerado da mesma pessoa."; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        }
                        GridLayout {
                            columns: 3
                            columnSpacing: 8
                            rowSpacing: 8
                            Layout.fillWidth: true
                            Metrica { rotulo: "Rostos"; valor: String(t.nRostos); cor: t.nRostos > 1 ? Theme.aviso : Theme.texto }
                            Metrica { rotulo: "FPS"; valor: cam.estado === "ativa" ? String(Math.round(cam.fps)) : "–" }
                            Metrica { rotulo: "Usuários ativos"; valor: String(t.usuariosAtivos) }
                        }
                    }

                    // geometria do rosto e assinatura biométrica (só exibição; a decisão é do backend)
                    Painel {
                        Layout.fillWidth: true
                        titulo: "Leitura do rosto"
                        subtitulo: "Pose pelos 5 pontos do detector e o vetor de 128 dimensões do SFace"
                        espacamento: 10
                        readonly property bool semRosto: t.poseYaw <= -90
                        readonly property bool poseRuim: t.orientacao !== ""
                        GridLayout {
                            columns: 3
                            columnSpacing: 8
                            rowSpacing: 8
                            Layout.fillWidth: true
                            Metrica {
                                rotulo: "Giro (yaw)"
                                valor: parent.parent.semRosto ? "–" : (t.poseYaw >= 0 ? "+" : "") + t.poseYaw.toFixed(2)
                                cor: parent.parent.poseRuim ? Theme.aviso : Theme.texto
                                Dica { visible: hoverYaw.hovered; text: "Nariz em relação ao meio dos olhos. 0 = de frente. Aceito até ±" + pagina.poseLimites.yaw }
                                HoverHandler { id: hoverYaw }
                            }
                            Metrica {
                                rotulo: "Inclinação"
                                valor: parent.parent.semRosto ? "–" : (t.poseRoll >= 0 ? "+" : "") + t.poseRoll.toFixed(0) + "°"
                                cor: parent.parent.poseRuim ? Theme.aviso : Theme.texto
                                Dica { visible: hoverRoll.hovered; text: "Ângulo da linha dos olhos. Aceito até ±" + pagina.poseLimites.roll + "°" }
                                HoverHandler { id: hoverRoll }
                            }
                            Metrica {
                                rotulo: "Nariz (pitch)"
                                valor: parent.parent.semRosto ? "–" : t.poseRazao.toFixed(2)
                                cor: parent.parent.poseRuim ? Theme.aviso : Theme.texto
                                Dica { visible: hoverPitch.hovered; text: "Posição do nariz entre os olhos (0) e a boca (1). Aceito entre " + pagina.poseLimites.razaoMin + " e " + pagina.poseLimites.razaoMax }
                                HoverHandler { id: hoverPitch }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: "Assinatura biométrica"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true }
                            Text {
                                text: t.assinatura.length > 0 ? t.assinatura.length + " dimensões" : "sem rosto"
                                color: Theme.texto3
                                font.pixelSize: Theme.tLegenda
                                font.features: { "tnum": 1 }
                            }
                        }
                        Canvas {
                            id: assinatura
                            Layout.fillWidth: true
                            implicitHeight: 64
                            readonly property var viva: t.assinatura
                            readonly property var ref: t.assinaturaReferencia
                            readonly property color corViva: pagina.bloqueado ? Theme.texto3 : (t.similaridade >= t.limiar ? Theme.acento : Theme.texto2)
                            onVivaChanged: requestPaint()
                            onCorVivaChanged: requestPaint()
                            onWidthChanged: requestPaint()
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.reset()
                                var n = viva.length, w = width, h = height, meio = h / 2
                                ctx.strokeStyle = String(Theme.borda)
                                ctx.lineWidth = 1
                                ctx.beginPath(); ctx.moveTo(0, meio); ctx.lineTo(w, meio); ctx.stroke()
                                if (n === 0) return
                                var passo = w / n, amp = meio - 3
                                // referência da galeria (amostra mais parecida), atrás, apagada
                                if (ref.length === n) {
                                    ctx.fillStyle = Qt.rgba(Theme.texto3.r, Theme.texto3.g, Theme.texto3.b, 0.45)
                                    for (var i = 0; i < n; ++i) {
                                        var rv = ref[i] * amp
                                        ctx.fillRect(i * passo, rv < 0 ? meio : meio - rv, Math.max(1, passo - 0.6), Math.abs(rv))
                                    }
                                }
                                ctx.fillStyle = String(corViva)
                                for (var j = 0; j < n; ++j) {
                                    var v = viva[j] * amp
                                    ctx.fillRect(j * passo + passo * 0.25, v < 0 ? meio : meio - v, Math.max(1, passo * 0.5), Math.abs(v))
                                }
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: t.assinatura.length === 0 ? "Cada rosto alinhado vira um vetor de 128 números; a similaridade é o cosseno entre dois vetores."
                                  : t.assinaturaReferencia.length > 0 ? "Barras claras: rosto ao vivo. Barras apagadas: amostra mais parecida da galeria."
                                  : "Galeria vazia: não há amostra para comparar."
                            color: Theme.texto3
                            font.pixelSize: Theme.tLegenda
                            wrapMode: Text.WordWrap
                        }
                    }

                    // aviso de galeria vazia (amarelo: é um aviso)
                    Rectangle {
                        Layout.fillWidth: true
                        visible: t.aviso !== "" || t.erro !== ""
                        implicitHeight: linhaAviso.implicitHeight + 24
                        radius: Theme.raio
                        color: t.erro !== "" ? Theme.perigoSuave : Theme.avisoSuave
                        border.color: Qt.rgba(1, 1, 1, 0.04)
                        RowLayout {
                            id: linhaAviso
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                            spacing: 10
                            Icone { Layout.alignment: Qt.AlignTop; nome: "alerta"; tamanho: 16; cor: t.erro !== "" ? Theme.perigo : Theme.aviso }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                Text { text: t.erro !== "" ? t.erro : t.aviso; color: Theme.texto; font.pixelSize: Theme.tPequeno; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                Botao {
                                    visible: t.erro === "" && t.usuariosAtivos === 0
                                    compacto: true
                                    text: "Cadastrar usuário"
                                    icone: "cadastro"
                                    onClicked: app.navegar("cadastro")
                                }
                            }
                        }
                    }

                    // controles
                    Painel {
                        Layout.fillWidth: true
                        espacamento: 14
                        Chave {
                            Layout.fillWidth: true
                            text: "Prova de vida"
                            descricao: "Pede que a pessoa vire o rosto antes de liberar (atalho L)"
                            checked: t.liveness
                            enabled: !pagina.bloqueado
                            onToggled: t.definirLiveness(checked)
                        }
                        Chave {
                            Layout.fillWidth: true
                            text: "Painel didático"
                            descricao: "Mostra cada fase do pipeline abaixo do vídeo (atalho D)"
                            checked: t.didatico
                            onToggled: t.definirDidatico(checked)
                        }
                    }

                    // últimos acessos
                    Painel {
                        Layout.fillWidth: true
                        titulo: "Últimos acessos"
                        espacamento: 4
                        cabecalhoDireita: Botao { text: "Ver auditoria"; variante: "fantasma"; compacto: true; onClicked: app.navegar("acessos") }
                        Text {
                            visible: t.ultimosAcessos.contagem === 0
                            text: "Nenhuma tentativa registrada ainda."
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                            Layout.topMargin: 4
                        }
                        Repeater {
                            model: t.ultimosAcessos
                            delegate: RowLayout {
                                required property string hora
                                required property string nome
                                required property string titulo
                                required property bool concedido
                                required property int nivelExigido
                                required property string similaridade
                                Layout.fillWidth: true
                                Layout.topMargin: 4
                                Layout.bottomMargin: 4
                                spacing: 10
                                Rectangle {
                                    width: 6; height: 6; radius: 3
                                    color: concedido ? Theme.sucesso : Theme.perigo
                                }
                                ColumnLayout {
                                    spacing: 1
                                    Layout.fillWidth: true
                                    Text { text: nome; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: titulo + ", nível " + nivelExigido; color: concedido ? Theme.sucesso : Theme.texto3; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                                }
                                Text { text: hora; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.features: { "tnum": 1 } }
                            }
                        }
                    }
                }
            }
        }
    }

    component Metrica: Rectangle {
        property string rotulo
        property string valor
        property color cor: Theme.texto
        Layout.fillWidth: true
        implicitHeight: 54
        radius: Theme.raioPequeno
        color: Theme.campo
        border.color: Theme.borda
        ColumnLayout {
            anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 10 }
            spacing: 1
            Text { text: parent.parent.valor; color: parent.parent.cor; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
            Text { text: parent.parent.rotulo; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
        }
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Theme.qml` (71 linhas)

```qml
pragma Singleton
import QtQuick

// Tokens visuais do Cofre MMA. Grafite em camadas, acento turquesa;
// verde e vermelho são reservados às decisões de acesso e amarelo só a avisos.
QtObject {
    // superfícies (da mais funda para a mais elevada)
    readonly property color janela: "#0f1215"
    readonly property color lateral: "#0c0e11"
    readonly property color superficie: "#151a1f"
    readonly property color elevada: "#1b2026"
    readonly property color realce: "#232931"
    readonly property color campo: "#12161a"
    readonly property color borda: "#252b33"
    readonly property color bordaForte: "#333b45"

    // texto
    readonly property color texto: "#e7ebef"
    readonly property color texto2: "#9aa3ae"
    readonly property color texto3: "#68717d"

    // acento e estados
    readonly property color acento: "#35d0c0"
    readonly property color acentoForte: "#22b8a8"
    readonly property color acentoSuave: Qt.rgba(0.208, 0.816, 0.753, 0.12)
    readonly property color sucesso: "#3dd68c"
    readonly property color sucessoSuave: Qt.rgba(0.239, 0.839, 0.549, 0.13)
    readonly property color perigo: "#f06a6a"
    readonly property color perigoSuave: Qt.rgba(0.941, 0.416, 0.416, 0.13)
    readonly property color aviso: "#f2b544"
    readonly property color avisoSuave: Qt.rgba(0.949, 0.710, 0.267, 0.13)
    readonly property color sobreCor: "#0b0e11"     // texto sobre fundos coloridos

    // níveis de acesso (sem vermelho/verde/amarelo, que têm significado próprio)
    readonly property var coresNivel: ["#8b97a6", "#6ea8fe", "#b197fc"]
    function corNivel(n) { return n >= 1 && n <= 3 ? coresNivel[n - 1] : texto3 }

    function corResultado(tipo) {
        if (tipo === "CONCEDIDO" || tipo === "ok") return sucesso
        if (tipo === "aviso") return aviso
        if (tipo === "" || tipo === undefined || tipo === "info" || tipo === "neutro") return acento
        return perigo
    }
    function suaveResultado(tipo) {
        if (tipo === "CONCEDIDO" || tipo === "ok") return sucessoSuave
        if (tipo === "aviso") return avisoSuave
        if (tipo === "" || tipo === undefined || tipo === "info" || tipo === "neutro") return acentoSuave
        return perigoSuave
    }

    // tipografia (fonte do sistema: SF Pro no macOS)
    readonly property string familia: Qt.application.font.family
    readonly property int tLegenda: 11
    readonly property int tPequeno: 12
    readonly property int tCorpo: 13
    readonly property int tDestaque: 15
    readonly property int tTitulo: 20
    readonly property int tGrande: 28

    // geometria
    readonly property int raio: 10
    readonly property int raioPequeno: 7
    readonly property int raioGrande: 14
    readonly property int espaco: 16
    readonly property int margemPagina: 28

    // movimento
    readonly property int rapido: 120
    readonly property int medio: 200
    readonly property int lento: 320
}

```

## `cofre/qt/qml/Cofre/Ui/UsuariosPagina.qml` (355 linhas)

```qml
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Administração de usuários: busca, filtros, nível, ativação, remoção e fotos.
Item {
    id: pagina
    readonly property var u: app.usuarios
    // cópia dos campos da linha escolhida: a referência ao item do modelo some quando a linha é removida
    property var selecionado: ({ id: 0, nome: "", matricula: "", nivel: 0, amostras: 0, ativo: false })
    function escolher(m) {
        selecionado = { id: m.id, nome: m.nome, matricula: m.matricula, nivel: m.nivel, amostras: m.amostras, ativo: m.ativo }
    }

    Confirmacao {
        id: confirmarRemocao
        titulo: "Remover " + (pagina.selecionado.nome || "") + "?"
        texto: "O cadastro (matrícula " + (pagina.selecionado.matricula || "") + ") e as " + (pagina.selecionado.amostras || 0)
               + " amostras biométricas serão apagados do banco. O histórico de acessos é mantido. Esta ação não pode ser desfeita."
        textoConfirmar: "Remover usuário"
        perigo: true
        onConfirmado: u.remover(pagina.selecionado.id)
    }
    Confirmacao {
        id: confirmarAtivo
        readonly property bool desativar: pagina.selecionado.ativo === true
        titulo: (desativar ? "Desativar " : "Reativar ") + (pagina.selecionado.nome || "") + "?"
        texto: desativar ? "A pessoa deixa de ser reconhecida pelo terminal até ser reativada. Os dados biométricos são mantidos."
                         : "A pessoa volta a ser reconhecida pelo terminal com o nível " + (pagina.selecionado.nivel || "") + "."
        textoConfirmar: desativar ? "Desativar" : "Reativar"
        icone: desativar ? "usuarioX" : "usuarioOk"
        onConfirmado: u.alternarAtivo(pagina.selecionado.id)
    }

    // escolha do nível
    Popup {
        id: escolhaNivel
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: 420
        padding: 20
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.55) }
        background: Rectangle { radius: Theme.raioGrande; color: Theme.elevada; border.color: Theme.bordaForte }
        contentItem: ColumnLayout {
            spacing: 10
            Text { text: "Nível de acesso"; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
            Text { text: (pagina.selecionado.nome || "") + " está no nível " + (pagina.selecionado.nivel || "") + "."; color: Theme.texto2; font.pixelSize: Theme.tCorpo }
            Repeater {
                model: app.niveis()
                delegate: Rectangle {
                    id: opc
                    required property var modelData
                    readonly property bool atual: pagina.selecionado.nivel === modelData.nivel
                    Layout.fillWidth: true
                    implicitHeight: lin.implicitHeight + 18
                    radius: Theme.raioPequeno + 1
                    color: area.containsMouse && !atual ? Theme.realce : Theme.campo
                    border.color: atual ? Theme.corNivel(modelData.nivel) : Theme.borda
                    RowLayout {
                        id: lin
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                        spacing: 10
                        Rectangle { width: 8; height: 8; radius: 4; color: Theme.corNivel(opc.modelData.nivel) }
                        ColumnLayout {
                            spacing: 1
                            Layout.fillWidth: true
                            Text { text: "Nível " + opc.modelData.nivel + ": " + opc.modelData.descricao; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium }
                            Text { text: opc.modelData.area; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                        }
                        Text { visible: opc.atual; text: "atual"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                    }
                    MouseArea {
                        id: area
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: !opc.atual
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { escolhaNivel.close(); u.alterarNivel(pagina.selecionado.id, opc.modelData.nivel) }
                    }
                }
            }
            Botao { Layout.alignment: Qt.AlignRight; text: "Cancelar"; onClicked: escolhaNivel.close() }
        }
    }

    // fotos de referência
    Popup {
        id: galeriaFotos
        property var fotos: []
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(pagina.width - 80, 760)
        height: Math.min(pagina.height - 80, 600)
        padding: 20
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.6) }
        background: Rectangle { radius: Theme.raioGrande; color: Theme.elevada; border.color: Theme.bordaForte }
        contentItem: ColumnLayout {
            spacing: 14
            RowLayout {
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Text { text: "Fotos de referência"; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                    Text { text: (pagina.selecionado.nome || "") + ", " + galeriaFotos.fotos.length + " foto(s)"; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                }
                BotaoIcone { icone: "fechar"; dica: "Fechar"; onClicked: galeriaFotos.close() }
            }
            GridView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                cellWidth: 132
                cellHeight: 132
                model: galeriaFotos.fotos
                delegate: Item {
                    required property var modelData
                    width: 132; height: 132
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 6
                        radius: Theme.raio
                        color: Theme.campo
                        border.color: Theme.borda
                        clip: true
                        Image {
                            anchors.fill: parent
                            anchors.margins: 1
                            visible: modelData.existe
                            source: modelData.existe ? modelData.url : ""
                            sourceSize: Qt.size(240, 240)
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                        }
                        Text { anchors.centerIn: parent; visible: !modelData.existe; text: "arquivo ausente"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                    }
                }
                Vazio {
                    anchors.centerIn: parent
                    visible: galeriaFotos.fotos.length === 0
                    icone: "imagem"
                    titulo: "Sem fotos gravadas"
                    texto: "Este usuário não tem fotos de referência na pasta de dados."
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 18

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Usuários"
            descricao: "Pessoas cadastradas, níveis de acesso e situação no terminal"
            Botao { text: "Novo cadastro"; icone: "cadastro"; variante: "primario"; onClicked: app.navegar("cadastro") }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: false   // não herda o preenchimento dos indicadores
            spacing: 12
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Cadastrados"; valor: u.total; icone: "usuarios" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Ativos"; valor: u.ativos; detalhe: (u.total - u.ativos) + " inativo(s)"; icone: "usuarioOk" }
            Repeater {
                model: 3
                delegate: Indicador {
                    required property int index
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    rotulo: "Nível " + (index + 1)
                    valor: u.porNivel[index] !== undefined ? u.porNivel[index] : 0
                    cor: Theme.corNivel(index + 1)
                    icone: "escudo"
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.raioGrande
            color: Theme.superficie
            border.color: Theme.borda

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.margins: 14
                    spacing: 10
                    Busca {
                        id: busca
                        Layout.preferredWidth: 300
                        placeholderText: "Buscar por nome, matrícula ou cargo"
                        text: u.busca
                        onTextChanged: u.definirBusca(text)
                    }
                    Segmentado {
                        atual: u.filtroStatus
                        opcoes: [{ valor: "todos", texto: "Todos" }, { valor: "ativos", texto: "Ativos" }, { valor: "inativos", texto: "Inativos" }]
                        onEscolhido: function(v) { u.definirFiltroStatus(v) }
                    }
                    Seletor {
                        atual: u.filtroNivel
                        opcoes: [{ valor: 0, texto: "Todos os níveis" }, { valor: 1, texto: "Nível 1" }, { valor: 2, texto: "Nível 2" }, { valor: 3, texto: "Nível 3" }]
                        onEscolhido: function(v) { u.definirFiltroNivel(v) }
                    }
                    Item { Layout.fillWidth: true }
                    Text { text: lista.count + " de " + u.total; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                }

                // cabeçalho da tabela
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 34
                    color: Theme.campo
                    Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top } height: 1; color: Theme.borda }
                    Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 1; color: Theme.borda }
                    LinhaColunas {
                        anchors.fill: parent
                        Text { Layout.fillWidth: true; Layout.minimumWidth: 150; text: "Nome"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: colMatricula; text: "Matrícula"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: colNivel; text: "Nível"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { visible: !pagina.compacta; Layout.preferredWidth: colAmostras; text: "Amostras"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: colSituacao; text: "Situação"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { visible: !pagina.compacta; Layout.preferredWidth: colData; text: "Cadastro"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Item { Layout.preferredWidth: pagina.colAcoes }
                    }
                }

                ListView {
                    id: lista
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: u.modelo
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: Rectangle {
                        id: linha
                        required property var model
                        required property int index
                        width: lista.width
                        height: 58
                        color: areaLinha.containsMouse ? Qt.rgba(1, 1, 1, 0.025) : "transparent"
                        Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 14; rightMargin: 14 } height: 1; color: Theme.borda; opacity: 0.6 }
                        MouseArea { id: areaLinha; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
                        LinhaColunas {
                            anchors.fill: parent
                            opacity: linha.model.ativo ? 1 : 0.55
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 150
                                spacing: 10
                                Rectangle {
                                    width: 32; height: 32; radius: 16
                                    color: Qt.rgba(Theme.corNivel(linha.model.nivel).r, Theme.corNivel(linha.model.nivel).g, Theme.corNivel(linha.model.nivel).b, 0.16)
                                    Text { anchors.centerIn: parent; text: linha.model.iniciais; color: Theme.corNivel(linha.model.nivel); font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold }
                                }
                                ColumnLayout {
                                    spacing: 1
                                    Layout.fillWidth: true
                                    Text { text: linha.model.nome; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: linha.model.cargo !== "" ? linha.model.cargo : "Sem cargo informado"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                                }
                            }
                            Text { Layout.preferredWidth: colMatricula; text: linha.model.matricula; color: Theme.texto2; font.pixelSize: Theme.tCorpo; elide: Text.ElideRight; font.features: { "tnum": 1 } }
                            Item {
                                Layout.preferredWidth: colNivel
                                implicitHeight: seloNivel.implicitHeight
                                Selo { id: seloNivel; texto: linha.model.nivel + " · " + linha.model.nivelDescricao; cor: Theme.corNivel(linha.model.nivel) }
                                Dica { visible: hover.hovered; text: "Libera até: " + linha.model.area }
                                HoverHandler { id: hover }
                            }
                            Text {
                                visible: !pagina.compacta
                                Layout.preferredWidth: colAmostras
                                text: linha.model.amostras
                                color: linha.model.amostras === 0 ? Theme.aviso : Theme.texto2
                                font.pixelSize: Theme.tCorpo
                                font.features: { "tnum": 1 }
                            }
                            Item {
                                Layout.preferredWidth: colSituacao
                                implicitHeight: 22
                                Selo {
                                    texto: linha.model.emCadastro ? "Em cadastro" : (linha.model.ativo ? "Ativo" : "Inativo")
                                    cor: linha.model.emCadastro ? Theme.aviso : (linha.model.ativo ? Theme.acento : Theme.texto3)
                                }
                            }
                            Text { visible: !pagina.compacta; Layout.preferredWidth: colData; text: linha.model.criadoEm; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            RowLayout {
                                Layout.preferredWidth: pagina.colAcoes
                                spacing: 2
                                Item { Layout.fillWidth: true }
                                opacity: areaLinha.containsMouse || hoverAcoes.hovered ? 1 : 0.55
                                HoverHandler { id: hoverAcoes }
                                BotaoIcone { icone: "imagem"; dica: "Ver fotos de referência"; onClicked: { pagina.escolher(linha.model); galeriaFotos.fotos = u.fotos(linha.model.id); galeriaFotos.open() } }
                                BotaoIcone { icone: "escudo"; dica: "Alterar nível de acesso"; onClicked: { pagina.escolher(linha.model); escolhaNivel.open() } }
                                BotaoIcone {
                                    visible: !linha.model.emCadastro
                                    icone: linha.model.ativo ? "usuarioX" : "usuarioOk"; dica: linha.model.ativo ? "Desativar" : "Reativar"
                                    onClicked: { pagina.escolher(linha.model); confirmarAtivo.open() }
                                }
                                BotaoIcone {
                                    visible: !linha.model.emCadastro
                                    icone: "lixeira"; dica: "Remover usuário"; cor: Theme.perigo
                                    onClicked: { pagina.escolher(linha.model); confirmarRemocao.open() }
                                }
                                BotaoIcone {
                                    visible: linha.model.emCadastro
                                    icone: "direita"; dica: "Voltar ao cadastro em andamento"; cor: Theme.aviso
                                    onClicked: app.navegar("cadastro")
                                }
                            }
                        }
                    }

                    Vazio {
                        anchors.centerIn: parent
                        visible: lista.count === 0 && u.carregado
                        icone: u.total === 0 ? "usuarios" : "busca"
                        titulo: u.total === 0 ? "Nenhum usuário cadastrado" : "Nenhum usuário encontrado"
                        texto: u.total === 0 ? "Cadastre a primeira pessoa autorizada para o terminal começar a reconhecer rostos."
                                             : "Nenhum cadastro corresponde à busca e aos filtros escolhidos."
                        acao: u.total === 0 ? "Cadastrar usuário" : "Limpar filtros"
                        iconeAcao: u.total === 0 ? "cadastro" : "fechar"
                        onAcionado: u.total === 0 ? app.navegar("cadastro") : u.limparFiltros()
                    }
                }
            }
        }
    }

    readonly property bool compacta: width < 980
    readonly property int colAcoes: 128
    readonly property int colMatricula: compacta ? 90 : 110
    readonly property int colNivel: compacta ? 180 : 210
    readonly property int colAmostras: 80
    readonly property int colSituacao: 90
    readonly property int colData: 100

    component LinhaColunas: RowLayout {
        anchors.leftMargin: 18
        anchors.rightMargin: 14
        spacing: 12
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Vazio.qml` (41 linhas)

```qml
import QtQuick
import QtQuick.Layouts

// Estado vazio com orientação para a próxima ação.
ColumnLayout {
    id: v
    property string icone: "caixa"
    property string titulo: ""
    property string texto: ""
    property string acao: ""
    property string iconeAcao: ""
    signal acionado()
    spacing: 10
    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        width: 48; height: 48; radius: 14
        color: Theme.elevada
        border.color: Theme.borda
        Icone { anchors.centerIn: parent; nome: v.icone; tamanho: 22; cor: Theme.texto2 }
    }
    Text { Layout.alignment: Qt.AlignHCenter; text: v.titulo; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
    Text {
        Layout.alignment: Qt.AlignHCenter
        Layout.maximumWidth: 380
        text: v.texto
        visible: text !== ""
        color: Theme.texto2
        font.pixelSize: Theme.tCorpo
        wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignHCenter
    }
    Botao {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 4
        visible: v.acao !== ""
        text: v.acao
        icone: v.iconeAcao
        variante: "primario"
        onClicked: v.acionado()
    }
}

```

## `cofre/qt/qml/Cofre/Ui/Icones.js` (52 linhas)

```javascript
.pragma library
// Ícones vetoriais em traço (grade 24×24, estilo Lucide), desenhados com PathSvg.
var caminhos = {
    "terminal": "M3 7V5a2 2 0 0 1 2-2h2 M17 3h2a2 2 0 0 1 2 2v2 M21 17v2a2 2 0 0 1-2 2h-2 M7 21H5a2 2 0 0 1-2-2v-2 M8 14s1.5 2 4 2 4-2 4-2 M9 9h.01 M15 9h.01",
    "cadastro": "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M5 7a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M19 8v6 M22 11h-6",
    "usuarios": "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M5 7a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M22 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",
    "acessos": "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8 M3 3v5h5 M12 7v5l4 2",
    "avaliacao": "M3 3v18h18 M18 17V9 M13 17V5 M8 17v-3",
    "config": "M4 21v-7 M4 10V3 M12 21v-9 M12 8V3 M20 21v-5 M20 12V3 M1 14h6 M9 8h6 M17 16h6",
    "escudo": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
    "escudoOk": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z M9 12l2 2 4-4",
    "escudoX": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z M14.5 9.5l-5 5 M9.5 9.5l5 5",
    "cadeado": "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z M7 11V7a5 5 0 0 1 10 0v4",
    "camera": "M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z M9 13a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
    "cameraOff": "M2 2l20 20 M7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16 M9.5 4h5L17 7h3a2 2 0 0 1 2 2v7.5 M14.12 15.12A3 3 0 1 1 9.88 10.88",
    "recarregar": "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8 M21 3v5h-5 M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16 M8 16H3v5",
    "busca": "M3 11a8 8 0 1 0 16 0a8 8 0 1 0-16 0 M21 21l-4.3-4.3",
    "fechar": "M18 6L6 18 M6 6l12 12",
    "ok": "M20 6L9 17l-5-5",
    "alerta": "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01",
    "info": "M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0 M12 16v-4 M12 8h.01",
    "erro": "M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0 M15 9l-6 6 M9 9l6 6",
    "lixeira": "M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2 M10 11v6 M14 11v6",
    "imagem": "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M7 9a2 2 0 1 0 4 0a2 2 0 1 0-4 0 M21 15l-5-5L5 21",
    "enviar": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12",
    "baixar": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3",
    "pasta": "M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2z",
    "olho": "M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z M9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
    "camadas": "M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5",
    "pulso": "M22 12h-4l-3 9L9 3l-3 9H2",
    "usuarioX": "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M5 7a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M17 8l5 5 M22 8l-5 5",
    "usuarioOk": "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M5 7a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M16 11l2 2 4-4",
    "usuario": "M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2 M8 7a4 4 0 1 0 8 0a4 4 0 1 0-8 0",
    "relogio": "M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0 M12 6v6l4 2",
    "velocimetro": "M12 14l4-4 M3.34 19a10 10 0 1 1 17.32 0",
    "banco": "M3 5a9 3 0 1 0 18 0a9 3 0 1 0-18 0 M3 5v14a9 3 0 0 0 18 0V5 M3 12a9 3 0 0 0 18 0",
    "salvar": "M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z M17 21v-8H7v8 M7 3v5h8",
    "desfazer": "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8 M3 3v5h5",
    "direita": "M9 18l6-6-6-6",
    "baixo": "M6 9l6 6 6-6",
    "filtro": "M22 3H2l8 9.46V19l4 2v-8.54L22 3z",
    "play": "M6 3l14 9-14 9V3z",
    "parar": "M6 6h12v12H6z",
    "externo": "M15 3h6v6 M10 14L21 3 M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6",
    "arquivo": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
    "caixa": "M22 12h-6l-2 3h-4l-2-3H2 M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
    "rosto": "M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0 M8 14s1.5 2 4 2 4-2 4-2 M9 9h.01 M15 9h.01",
    "sol": "M8 12a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M12 2v2 M12 20v2 M4.93 4.93l1.41 1.41 M17.66 17.66l1.41 1.41 M2 12h2 M20 12h2 M6.34 17.66l-1.41 1.41 M19.07 4.93l-1.41 1.41",
    "foco": "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0 M8 12a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M11 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0",
    "teclado": "M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z M6 9h.01 M10 9h.01 M14 9h.01 M18 9h.01 M7 15h10"
}
function caminho(nome) { return caminhos[nome] !== undefined ? caminhos[nome] : "" }

```

## `cofre/qt/qml/Cofre/Ui/qmldir` (2 linhas)

```text
module Cofre.Ui
singleton Theme 1.0 Theme.qml

```

## `tests/__init__.py` (0 linhas)

```python

```

## `tests/apoio_interface.py` (78 linhas)

```python
"""Apoio para testar o aplicativo desktop sem webcam e sem interação humana.

    from tests.apoio_interface import criar_app, FonteFalsa, girar
    app = criar_app(tmp_path / "t.db", imagens=[...])   # câmera falsa com as fotos dadas
    app.mostrar("tela_terminal"); girar(app, 1.0)       # roda o loop do Tk por 1 s
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2

FIX = Path(__file__).resolve().parent / "fixtures" / "pessoas"
FOTO_OBAMA = FIX / "obama" / "obama_2012.jpg"
FOTO_OBAMA_2 = FIX / "obama" / "obama_2009.jpg"
FOTO_BIDEN = FIX / "biden" / "biden_2021.jpg"
FOTO_BIDEN_2 = FIX / "biden" / "biden_2013.jpg"


class FonteFalsa:
    """Substitui `FonteCamera`: repete as imagens dadas como se fossem frames (~30 fps)."""

    fps_medido = 30.0

    def __init__(self, imagens, intervalo=1 / 30):
        self.imagens = [cv2.imread(str(c)) if isinstance(c, (str, Path)) else c for c in imagens]
        self.intervalo = intervalo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def frames(self):
        while True:
            for im in self.imagens:
                time.sleep(self.intervalo)
                yield im.copy()


class SemCamera:
    """Fonte que falha como uma câmera ausente (para testes que não passam imagens)."""

    fps_medido = 0.0

    def __enter__(self):
        from cofre.fase1_aquisicao import ErroAquisicao
        raise ErroAquisicao("Sem câmera (teste)")

    def __exit__(self, *exc):
        return False


def criar_app(caminho_db, imagens=None, esperar_pipeline=True):
    """Cria o App com banco temporário e câmera falsa; espera os modelos carregarem.
    A webcam real nunca é aberta: sem `imagens`, a câmera se comporta como ausente."""
    from cofre.interface.app import App
    fonte = (lambda: FonteFalsa(imagens)) if imagens is not None else SemCamera
    app = App(caminho_db, fonte_camera=fonte)
    app.update()
    if esperar_pipeline:
        inicio = time.time()
        while app.pipeline is None and time.time() - inicio < 20:
            app.update()
            time.sleep(0.02)
        assert app.pipeline is not None, app._erro_pipeline
    return app


def girar(app, segundos: float) -> None:
    """Processa eventos do Tk por `segundos` (equivalente a deixar o mainloop rodar)."""
    fim = time.time() + segundos
    while time.time() < fim:
        app.update()
        time.sleep(0.01)

```

## `tests/apoio_qt.py` (75 linhas)

```python
"""Apoio para testar o aplicativo Qt Quick sem tela, sem webcam e sem interação humana.

Roda com a plataforma `offscreen` e o renderizador por software, com banco e pastas temporários.
A webcam real nunca é aberta: a câmera é a `FonteFalsa` (fotos do repositório) ou `SemCamera`.
"""

from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QEventLoop  # noqa: E402

from tests.apoio_interface import FonteFalsa, SemCamera  # noqa: E402,F401

# avisos que não vêm do nosso QML (fonte ausente no modo offscreen)
_AVISOS_IGNORADOS = ("Sans Serif", "propagateSizeHints")


class Contexto:
    """Aplicacao + motor QML + janela, com utilidades para girar o loop de eventos."""

    def __init__(self, qapp, aplicacao, motor, avisos):
        self.qapp = qapp
        self.apl = aplicacao
        self.motor = motor
        self.avisos = avisos
        self.janela = motor.rootObjects()[0] if motor.rootObjects() else None

    def girar(self, segundos: float) -> None:
        fim = time.time() + segundos
        while time.time() < fim:
            self.qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            time.sleep(0.005)

    def esperar(self, condicao, segundos: float = 15.0) -> bool:
        fim = time.time() + segundos
        while time.time() < fim:
            if condicao():
                return True
            self.girar(0.05)
        return bool(condicao())

    def avisos_qml(self) -> list[str]:
        return [a for a in self.avisos if not any(i in a for i in _AVISOS_IGNORADOS)]

    def fechar(self) -> None:
        from cofre.qt.app import destruir_motor
        self.apl.fechar()
        self.girar(0.05)
        self.janela = None
        destruir_motor(self.motor)
        self.motor = None
        self.girar(0.05)


def criar_contexto(qapp, caminho_db, pipeline=None, imagens=None) -> Contexto:
    """Cria a Aplicacao com câmera falsa e carrega o Main.qml. Com `pipeline`, reaproveita o da
    sessão de testes em vez de carregar os modelos de novo."""
    from cofre.qt.aplicacao import Aplicacao
    from cofre.qt.app import criar_motor
    fonte = (lambda: FonteFalsa(imagens)) if imagens is not None else SemCamera
    apl = Aplicacao(str(caminho_db), fonte_camera=fonte, carregar_modelos=pipeline is None)
    avisos: list[str] = []
    motor = criar_motor(apl, avisos)
    ctx = Contexto(qapp, apl, motor, avisos)
    if pipeline is not None:
        apl.usar_pipeline(pipeline)
    else:
        assert ctx.esperar(lambda: apl.pipeline is not None, 30), apl.erroModelos
    ctx.girar(0.1)
    return ctx

```

## `tests/conftest.py` (48 linhas)

```python
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

```

## `tests/test_areas.py` (30 linhas)

```python
"""Conteúdo das áreas liberadas depois da autenticação: herança por nível e dados fictícios."""
from datetime import date

import pytest

from cofre import areas, config


def test_heranca_de_niveis():
    assert areas.areas_liberadas(1) == [1]
    assert areas.areas_liberadas(2) == [1, 2]
    assert areas.areas_liberadas(3) == [1, 2, 3]
    assert areas.areas_liberadas(0) == []
    resumo = areas.resumo_areas(2)
    assert [r["nivel"] for r in resumo] == [1, 2, 3]
    assert [r["liberada"] for r in resumo] == [True, True, False]
    assert resumo[2]["titulo"] == config.AREAS[3]


def test_conteudo_por_nivel_e_deterministico():
    hoje = date(2026, 11, 4)
    c1, c2, c3 = (areas.conteudo(n, hoje) for n in (1, 2, 3))
    assert c1["titulo"] == config.AREAS[1] and len(c1["comunicados"]) == 4 and len(c1["qualidadeAr"]) == 7
    assert c2["resumo"]["divisoes"] == len(c2["divisoes"]) == 5 and c2["resumo"]["aprovacoesPendentes"] == 6
    assert all(0 < d["fracao"] <= 1 for d in c2["divisoes"])
    assert len(c3["lotes"]) == 8 and c3["totais"]["criticos"] == 3 and len(c3["temperatura"]) == 24
    assert all(-82 <= t["valor"] <= -74 for t in c3["temperatura"])
    assert areas.conteudo(3, hoje)["lotes"] == c3["lotes"]            # mesma semente, mesmo conteúdo
    with pytest.raises(ValueError):
        areas.conteudo(4, hoje)

```

## `tests/test_banco_reconhecimento.py` (112 linhas)

```python
"""Banco, identificação 1:N, decisão por nível, relatórios e avaliação."""
import numpy as np
import pytest

from cofre import config, relatorios
from cofre.avaliacao import avaliar_pasta
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from cofre.fase1_aquisicao import carregar_imagem
from cofre.fase5_reconhecimento import Identificacao, Reconhecedor, Resultado, decidir_acesso
from tests.conftest import FIX


def test_crud_usuario_e_amostras(banco):
    u = banco.criar_usuario("Ana", "M001", "Diretora", 2)
    assert u.nivel == 2 and u.ativo
    banco.adicionar_amostra(u.id, np.ones(128, np.float32))
    assert banco.contar_amostras(u.id) == 1
    assert banco.embeddings_do_usuario(u.id)[0].shape == (128,)
    banco.alterar_nivel(u.id, 3)
    assert banco.obter_usuario(u.id).nivel == 3
    banco.definir_ativo(u.id, False)
    assert banco.listar_usuarios(apenas_ativos=True) == []
    banco.remover_usuario(u.id)
    assert banco.obter_usuario(u.id) is None
    assert banco.contar_amostras(u.id) == 0  # cascade


def test_matricula_unica_e_nivel_invalido(banco):
    banco.criar_usuario("A", "X1", "", 1)
    with pytest.raises(Exception):
        banco.criar_usuario("B", "X1", "", 1)
    with pytest.raises(ValueError):
        banco.criar_usuario("C", "X2", "", 4)


def _ident(nivel):
    from cofre.banco import Usuario
    u = Usuario(1, "Fulano", "m", "c", nivel, True, "")
    return Identificacao(u, 0.8)


@pytest.mark.parametrize("nivel_usuario,nivel_exigido,esperado", [
    (1, 1, Resultado.CONCEDIDO), (1, 2, Resultado.NEGADO_NIVEL), (1, 3, Resultado.NEGADO_NIVEL),
    (2, 1, Resultado.CONCEDIDO), (2, 2, Resultado.CONCEDIDO), (2, 3, Resultado.NEGADO_NIVEL),
    (3, 1, Resultado.CONCEDIDO), (3, 2, Resultado.CONCEDIDO), (3, 3, Resultado.CONCEDIDO),
])
def test_esquema_de_permissoes(nivel_usuario, nivel_exigido, esperado):
    assert decidir_acesso(_ident(nivel_usuario), nivel_exigido).resultado is esperado


def test_desconhecido_negado():
    assert decidir_acesso(Identificacao(None, 0.1), 1).resultado is Resultado.NEGADO_DESCONHECIDO
    assert decidir_acesso(None, 1).resultado is Resultado.NEGADO_DESCONHECIDO


def test_identificacao_1_para_n_com_fotos_reais(banco, pipeline, fotos):
    # cadastra cada pessoa com UMA foto e consulta com a OUTRA
    ob, _, _ = cadastrar_de_imagens(banco, pipeline, DadosCadastro("Obama", "001", "Ministro", 3), [fotos["obama"][0]])
    bi, _, _ = cadastrar_de_imagens(banco, pipeline, DadosCadastro("Biden", "002", "Diretor", 2), [fotos["biden"][0]])
    rec = Reconhecedor(banco)
    assert rec.total_amostras == 2
    q_ob = pipeline.processar(carregar_imagem(fotos["obama"][1])).principal.embedding
    q_bi = pipeline.processar(carregar_imagem(fotos["biden"][1])).principal.embedding
    i1, i2 = rec.identificar(q_ob), rec.identificar(q_bi)
    assert i1.reconhecido and i1.usuario.id == ob.id
    assert i2.reconhecido and i2.usuario.id == bi.id
    assert decidir_acesso(i1, 3).concedido
    assert decidir_acesso(i2, 3).resultado is Resultado.NEGADO_NIVEL
    assert decidir_acesso(i2, 2).concedido
    # usuário desativado some da galeria
    banco.definir_ativo(bi.id, False)
    rec.recarregar()
    assert not rec.identificar(q_bi).reconhecido


def test_galeria_vazia(banco):
    assert not Reconhecedor(banco).identificar(np.ones(128, np.float32)).reconhecido


def test_autenticar_imagem_registra_log_e_evidencia(banco, pipeline, fotos, tmp_path, monkeypatch):
    from cofre.autenticacao import autenticar_imagem
    monkeypatch.setattr(config, "EVIDENCIAS_DIR", tmp_path / "ev")
    cadastrar_de_imagens(banco, pipeline, DadosCadastro("Obama", "001", "Ministro", 3), [fotos["obama"][0]])
    d1, _ = autenticar_imagem(banco, pipeline, carregar_imagem(fotos["obama"][1]), 3)
    d2, _ = autenticar_imagem(banco, pipeline, carregar_imagem(fotos["biden"][0]), 1)
    assert d1.concedido and d2.resultado is Resultado.NEGADO_DESCONHECIDO
    acessos = banco.listar_acessos()
    assert [a.resultado for a in acessos] == ["NEGADO_DESCONHECIDO", "CONCEDIDO"]
    assert acessos[0].evidencia and (tmp_path / "ev").exists()
    e = banco.estatisticas()
    assert e["total"] == 2 and e["por_resultado"]["CONCEDIDO"] == 1


def test_relatorios_exportam(banco, tmp_path):
    u = banco.criar_usuario("Ana", "M1", "Dir", 2)
    banco.registrar_acesso(usuario_id=u.id, nome_detectado="Ana", nivel_usuario=2, nivel_exigido=3,
                           similaridade=0.7, resultado="NEGADO_NIVEL", mensagem="x")
    assert "Ana" in relatorios.texto_usuarios(banco)
    assert "nível insuficiente" in relatorios.texto_acessos(banco)
    csv_p = relatorios.exportar_csv(banco, tmp_path / "a.csv")
    html_p = relatorios.exportar_html(banco, tmp_path / "a.html")
    assert "NEGADO_NIVEL" in csv_p.read_text(encoding="utf-8")
    assert "<table" in html_p.read_text(encoding="utf-8") and "Ana" in html_p.read_text(encoding="utf-8")


def test_avaliacao_em_pasta_rotulada(pipeline):
    r = avaliar_pasta(FIX, pipeline)
    assert r.pessoas == {"biden": 2, "obama": 2}
    assert len(r.genuinos) == 2 and len(r.impostores) == 4
    t = r.taxas(config.LIMIAR_COSSENO)
    assert t["TAR"] == 1.0 and t["FAR"] == 0.0
    assert "EER" in r.resumo()

```

## `tests/test_interface_acessos.py` (127 linhas)

```python
"""Tela "Acessos e relatórios" do aplicativo desktop, com banco temporário e câmera falsa."""
import time

import numpy as np
import pytest

from cofre.interface import tela_acessos
from tests.apoio_interface import FOTO_OBAMA, criar_app, girar


def _popular(banco, tmp_path):
    import cv2
    u = banco.criar_usuario("Obama", "001", "Ministro", 3)
    banco.adicionar_amostra(u.id, np.zeros(128, dtype=np.float32), None)
    ev = tmp_path / "ev" / "neg.jpg"
    ev.parent.mkdir(parents=True)
    cv2.imwrite(str(ev), np.full((1200, 900, 3), 90, dtype=np.uint8))
    banco.registrar_acesso(usuario_id=u.id, nome_detectado="Obama", nivel_usuario=3, nivel_exigido=3,
                           similaridade=0.71, resultado="CONCEDIDO", mensagem="ok")
    banco.registrar_acesso(usuario_id=u.id, nome_detectado="Obama", nivel_usuario=3, nivel_exigido=1,
                           similaridade=0.65, resultado="CONCEDIDO")
    banco.registrar_acesso(usuario_id=None, nome_detectado="DESCONHECIDO", nivel_usuario=None, nivel_exigido=2,
                           similaridade=0.21, resultado="NEGADO_DESCONHECIDO", mensagem="sem match",
                           evidencia=str(ev))
    banco.registrar_acesso(usuario_id=None, nome_detectado="Biden", nivel_usuario=2, nivel_exigido=3,
                           similaridade=0.55, resultado="NEGADO_NIVEL")
    return ev


@pytest.fixture
def app(tmp_path):
    a = criar_app(tmp_path / "t.db", imagens=[FOTO_OBAMA])
    _popular(a.banco, tmp_path)
    yield a
    a.fechar()


def _esperar(app, cond, seg=10.0):
    fim = time.time() + seg
    while time.time() < fim:
        girar(app, 0.05)
        if cond():
            return True
    return False


def test_cartoes_tabela_e_resumos(app):
    app.mostrar("tela_acessos")
    girar(app, 0.5)
    t = app.tela("tela_acessos")
    assert t.cartoes["total"].valor.cget("text") == "4"
    assert t.cartoes["CONCEDIDO"].valor.cget("text") == "2"
    assert t.cartoes["negados"].valor.cget("text") == "2"
    assert t.cartoes["NEGADO_NIVEL"].valor.cget("text") == "1"
    assert t.cartoes["usuarios"].valor.cget("text") == "1"
    assert t.cartoes["amostras"].valor.cget("text") == "1"
    assert len(t.tabela.tree.get_children()) == 4
    # banco.estatisticas() agrupa por u.nome (alias ignorado pelo SQLite): não cadastrados viram um grupo só
    assert len(t.tabela_pessoas.tree.get_children()) >= 2
    assert len(t.tabela_dias.tree.get_children()) == 1
    iid = t.tabela.tree.get_children()[0]
    assert t.tabela.tree.item(iid, "values")[6] in tema_rotulos()


def tema_rotulos():
    from cofre.interface import tema
    return set(tema.ROTULO_RESULTADO.values())


def test_filtros_resultado_e_busca(app):
    app.mostrar("tela_acessos")
    girar(app, 0.3)
    t = app.tela("tela_acessos")
    t.var_resultado.set("Negado: nível insuficiente")
    t.recarregar()
    assert len(t.tabela.tree.get_children()) == 1
    t.var_resultado.set("Todos")
    t.var_busca.set("oba")
    t._agendar_busca()
    assert _esperar(app, lambda: len(t.tabela.tree.get_children()) == 2, 3)
    t.var_busca.set("")
    t.var_limite.set("50")
    t.recarregar()
    assert len(t.tabela.tree.get_children()) == 4


def test_detalhe_com_evidencia(app):
    app.mostrar("tela_acessos")
    girar(app, 0.3)
    t = app.tela("tela_acessos")
    com_ev = next(iid for iid, a in t._acessos.items() if a.evidencia)
    t._abrir_detalhe(com_ev)
    girar(app, 0.3)
    assert t._detalhe is not None and t._detalhe.winfo_exists()
    img = t._detalhe._imagem_evidencia
    w, h = img.cget("size")
    assert w <= 800 and h <= 600
    sem_ev = next(iid for iid, a in t._acessos.items() if not a.evidencia)
    t._abrir_detalhe(sem_ev)  # substitui a janela anterior sem erro
    girar(app, 0.2)
    assert not hasattr(t._detalhe, "_imagem_evidencia")
    app.mostrar("tela_usuarios")  # ao_esconder fecha o detalhe
    assert t._detalhe is None


def test_exportar_csv_e_html_em_thread(app, monkeypatch, tmp_path):
    abertos = []
    monkeypatch.setattr(tela_acessos, "_abrir_no_sistema", lambda c: abertos.append(c))
    monkeypatch.setattr(tela_acessos.webbrowser, "open", lambda u: abertos.append(u))
    app.mostrar("tela_acessos")
    girar(app, 0.3)
    t = app.tela("tela_acessos")
    t.btn_csv.invoke()
    assert _esperar(app, lambda: t._ultimo_exportado is not None and t._ultimo_exportado.suffix == ".csv")
    csv = t._ultimo_exportado
    assert csv.exists() and csv.parent == tmp_path / "relatorios"
    assert "NEGADO_DESCONHECIDO" in csv.read_text(encoding="utf-8")
    t.btn_abrir.invoke()
    assert abertos[-1] == csv.resolve()
    t.btn_html.invoke()
    assert _esperar(app, lambda: t._ultimo_exportado is not None and t._ultimo_exportado.suffix == ".html")
    assert t._ultimo_exportado.exists()
    t.btn_abrir.invoke()
    assert str(abertos[-1]).startswith("file://")
    t.btn_evidencias.invoke()
    assert abertos[-1] == (tmp_path / "evidencias").resolve()
    assert t.btn_csv.cget("state") == "normal"

```

## `tests/test_interface_cadastro.py` (145 linhas)

```python
"""Tela de cadastro biométrico com câmera falsa (sem webcam, sem interação humana)."""
import time

import pytest

from cofre import config
from cofre.fase1_aquisicao import ErroAquisicao
from tests.apoio_interface import FOTO_BIDEN, FOTO_OBAMA, FOTO_OBAMA_2, criar_app, girar


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INTERVALO_AMOSTRAS_SEG", 0.05)  # 12 amostras em ~1 s
    a = criar_app(tmp_path / "t.db", imagens=[FOTO_OBAMA, FOTO_OBAMA_2])
    a.mostrar("tela_cadastro")
    yield a
    a.fechar()


def _esperar(app, condicao, seg=10.0):
    fim = time.time() + seg
    while time.time() < fim:
        girar(app, 0.1)
        if condicao():
            return True
    return False


def test_validacao_do_formulario(app):
    tela = app.tela("tela_cadastro")
    assert tela.iniciar_captura() is False
    assert "nome" in tela.rotulo_erro.cget("text").lower()
    tela.preencher(nome="Fulano")
    assert tela.iniciar_captura() is False
    assert "matrícula" in tela.rotulo_erro.cget("text").lower()
    app.banco.criar_usuario("Outro", "123", "Cargo", 1)
    tela.preencher(nome="Fulano", matricula="123")
    assert tela.iniciar_captura() is False
    assert "já cadastrada" in tela.rotulo_erro.cget("text")
    assert not tela.capturando and not app.camera.ativo


def test_captura_pela_camera_ate_concluir(app):
    tela = app.tela("tela_cadastro")
    tela.preencher(nome="Barack Obama", matricula="001", cargo="Ministro", nivel=3)
    assert tela.iniciar_captura() is True
    assert tela.capturando
    assert tela.entrada_nome.cget("state") == "disabled"
    assert _esperar(app, lambda: tela.sessao is not None and tela.sessao.concluida, 15)
    assert app.camera.ativo
    assert tela.rotulo_amostras.cget("text") == f"Amostras {config.AMOSTRAS_POR_CADASTRO}/{config.AMOSTRAS_POR_CADASTRO}"
    assert len(tela._miniaturas_widgets) == config.AMOSTRAS_POR_CADASTRO
    assert tela.botao_concluir.cget("state") == "normal"
    tela.botao_concluir.invoke()
    girar(app, 0.3)
    u = app.banco.obter_por_matricula("001")
    assert u is not None and u.nivel == 3
    assert app.banco.contar_amostras(u.id) == config.AMOSTRAS_POR_CADASTRO
    assert not tela.capturando and not app.camera.ativo
    assert tela.entrada_nome.get() == "" and tela.entrada_nome.cget("state") == "normal"
    assert "Barack Obama" in tela.rotulo_msg.cget("text")


def test_cancelar_desfaz_o_cadastro(app):
    tela = app.tela("tela_cadastro")
    tela.preencher(nome="Joe Biden", matricula="002", nivel=2)
    tela.botao_iniciar.invoke()
    assert _esperar(app, lambda: tela.sessao is not None and tela.sessao.capturadas >= 2, 10)
    tela.botao_cancelar.invoke()
    girar(app, 0.3)
    assert app.banco.obter_por_matricula("002") is None
    assert not tela.capturando and not app.camera.ativo
    assert tela.entrada_nome.cget("state") == "normal"


def test_trocar_de_tela_desliga_e_religa_a_camera(app):
    tela = app.tela("tela_cadastro")
    tela.preencher(nome="Joe Biden", matricula="002", nivel=2)
    tela.iniciar_captura()
    assert _esperar(app, lambda: app.camera.ativo, 10)
    app.mostrar("tela_usuarios")
    girar(app, 0.3)
    assert not app.camera.ativo and tela.capturando
    app.mostrar("tela_cadastro")
    assert _esperar(app, lambda: app.camera.ativo, 10)
    tela.cancelar()


def test_cadastrar_por_fotos(app):
    tela = app.tela("tela_cadastro")
    tela.preencher(nome="Joe Biden", matricula="002", cargo="Diretor", nivel=2)
    assert tela.cadastrar_por_fotos([str(FOTO_BIDEN), str(FOTO_OBAMA)]) is True
    assert tela.entrada_nome.cget("state") == "disabled"
    assert _esperar(app, lambda: not tela.importando_fotos and tela.entrada_nome.cget("state") == "normal", 20)
    u = app.banco.obter_por_matricula("002")
    assert u is not None and app.banco.contar_amostras(u.id) == 2
    assert "Joe Biden" in tela.rotulo_msg.cget("text")

    # mesma matrícula de novo: validação barra antes de abrir a thread
    tela.preencher(nome="Joe Biden", matricula="002")
    assert tela.cadastrar_por_fotos([str(FOTO_BIDEN)]) is False
    assert "já cadastrada" in tela.rotulo_erro.cget("text")


def test_cadastrar_por_fotos_sem_rosto_mostra_erro(app, tmp_path):
    import cv2
    import numpy as np
    vazia = tmp_path / "vazia.jpg"
    cv2.imwrite(str(vazia), np.full((300, 300, 3), 120, np.uint8))
    tela = app.tela("tela_cadastro")
    tela.preencher(nome="Ninguém", matricula="999")
    assert tela.cadastrar_por_fotos([str(vazia)]) is True
    assert _esperar(app, lambda: tela.rotulo_erro.cget("text") != "", 20)
    assert "falhou" in tela.rotulo_erro.cget("text")
    assert app.banco.obter_por_matricula("999") is None


class _FonteQueFalha:
    fps_medido = 0.0

    def __enter__(self):
        raise ErroAquisicao("Câmera não encontrada (teste)")

    def __exit__(self, *exc):
        return False

    def frames(self):
        yield from ()


def test_camera_indisponivel_mostra_tentar_novamente(app):
    tela = app.tela("tela_cadastro")
    app.camera.fonte_fabrica = _FonteQueFalha
    tela.preencher(nome="Fulano", matricula="010")
    tela.iniciar_captura()
    assert _esperar(app, lambda: tela.botao_tentar.winfo_ismapped(), 10)
    assert "Câmera indisponível" in tela.video.cget("text")
    # a câmera volta a funcionar: Tentar novamente retoma a mesma sessão
    from tests.apoio_interface import FonteFalsa
    app.camera.fonte_fabrica = lambda: FonteFalsa([FOTO_OBAMA])
    tela.botao_tentar.invoke()
    assert _esperar(app, lambda: tela.sessao is not None and tela.sessao.capturadas >= 1, 10)
    assert not tela.botao_tentar.winfo_ismapped()
    tela.cancelar()
    assert app.banco.obter_por_matricula("010") is None

```

## `tests/test_interface_config.py` (129 linhas)

```python
"""Testes da tela de Configurações (sem câmera real, sem interação humana)."""

import json

import pytest

from cofre import config
from cofre.interface.tela_config import ARQUIVO_CONFIG_NOME, CAMPOS, MENSAGEM_APLICADO
from tests.apoio_interface import FOTO_OBAMA, criar_app, girar


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """Arquivo de usuário em tmp e valores de config restaurados ao final do teste."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    for c in CAMPOS:
        monkeypatch.setattr(config, c.chave, getattr(config, c.chave))
    return tmp_path


@pytest.fixture
def app(ambiente):
    app = criar_app(ambiente / "t.db", imagens=[FOTO_OBAMA], esperar_pipeline=False)
    yield app
    app.fechar()


def _abrir(app):
    app.mostrar("tela_config")
    girar(app, 0.3)
    return app.tela("tela_config")


def test_formulario_reflete_config_e_aplica(app):
    tela = _abrir(app)
    assert tela.valores()["LIMIAR_COSSENO"] == pytest.approx(config.LIMIAR_COSSENO)
    assert tela.valores()["LIVENESS_ATIVO"] == config.LIVENESS_ATIVO

    tela.definir("LIMIAR_COSSENO", 0.5)
    tela.definir("FRAMES_CONFIRMACAO", 9)
    tela.definir("LIVENESS_ATIVO", False)
    assert config.LIMIAR_COSSENO != 0.5          # ainda não aplicado
    assert tela.btn_aplicar.invoke() is True
    assert config.LIMIAR_COSSENO == 0.5
    assert config.FRAMES_CONFIRMACAO == 9
    assert config.LIVENESS_ATIVO is False
    assert tela.mensagem.texto.cget("text") == MENSAGEM_APLICADO
    girar(app, 0.2)


def test_definir_limita_ao_intervalo_e_tipo(app):
    tela = _abrir(app)
    tela.definir("BLOQUEIO_SEG", 9999)
    tela.definir("CAMERA_INDEX", -3)
    tela.definir("LIMIAR_COSSENO", 0.01)
    assert tela.valores()["BLOQUEIO_SEG"] == 300
    assert tela.valores()["CAMERA_INDEX"] == 0
    assert tela.valores()["LIMIAR_COSSENO"] == 0.20
    with pytest.raises(ValueError):
        tela.definir("MIN_NITIDEZ", "alto")


def test_restaurar_padroes(app):
    tela = _abrir(app)
    original = tela.padroes["MAX_TENTATIVAS_FALHAS"]
    tela.definir("MAX_TENTATIVAS_FALHAS", 7)
    tela.aplicar()
    assert config.MAX_TENTATIVAS_FALHAS == 7
    tela.btn_restaurar.invoke()
    assert tela.valores()["MAX_TENTATIVAS_FALHAS"] == original
    assert config.MAX_TENTATIVAS_FALHAS == 7    # restaurar só muda o formulário
    tela.aplicar()
    assert config.MAX_TENTATIVAS_FALHAS == original


def test_salvar_e_carregar_arquivo(app, ambiente):
    tela = _abrir(app)
    caminho = ambiente / "data" / ARQUIVO_CONFIG_NOME
    assert tela.caminho_arquivo == caminho
    tela.definir("AMOSTRAS_POR_CADASTRO", 20)
    tela.definir("ESPELHAR_CAMERA", False)
    assert tela.btn_salvar.invoke() is True
    dados = json.loads(caminho.read_text())
    assert dados["AMOSTRAS_POR_CADASTRO"] == 20 and dados["ESPELHAR_CAMERA"] is False
    assert set(dados) == {c.chave for c in CAMPOS}

    tela.restaurar_padroes()
    assert tela.valores()["AMOSTRAS_POR_CADASTRO"] != 20
    assert tela.btn_carregar.invoke() is True
    assert tela.valores()["AMOSTRAS_POR_CADASTRO"] == 20
    assert config.AMOSTRAS_POR_CADASTRO == 20 and config.ESPELHAR_CAMERA is False


def test_carregar_arquivo_inexistente_ou_invalido(app, ambiente):
    tela = _abrir(app)
    assert tela.carregar_arquivo() is False
    assert "não encontrado" in tela.mensagem.texto.cget("text")
    caminho = ambiente / "data" / ARQUIVO_CONFIG_NOME
    caminho.parent.mkdir(parents=True)
    caminho.write_text("{isso nao é json")
    assert tela.carregar_arquivo() is False
    assert "inválido" in tela.mensagem.texto.cget("text")
    caminho.write_text(json.dumps({"LIMIAR_COSSENO": "texto"}))
    assert tela.carregar_arquivo() is False
    girar(app, 0.1)


def test_arquivo_existente_e_aplicado_ao_abrir(ambiente):
    caminho = ambiente / "data" / ARQUIVO_CONFIG_NOME
    caminho.parent.mkdir(parents=True)
    caminho.write_text(json.dumps({"LIMIAR_COSSENO": 0.45, "BLOQUEIO_SEG": 77, "CHAVE_DESCONHECIDA": 1}))
    app = criar_app(ambiente / "t.db", imagens=[FOTO_OBAMA], esperar_pipeline=False)
    try:
        tela = _abrir(app)
        assert config.LIMIAR_COSSENO == 0.45
        assert config.BLOQUEIO_SEG == 77
        assert tela.padroes["BLOQUEIO_SEG"] == 30     # padrão lido antes do arquivo
        assert tela.valores()["LIMIAR_COSSENO"] == 0.45
        assert "carregada" in tela.mensagem.texto.cget("text")
    finally:
        app.fechar()


def test_informacoes_e_tabela(app):
    tela = _abrir(app)
    nomes = dict(tela.informacoes())
    assert str(app.banco.caminho) == nomes["Banco de dados"]
    assert "128" in nomes["Dimensões dos modelos"]
    assert len(tela.tabela_niveis.tree.get_children()) == len(config.NIVEIS)

```

## `tests/test_interface_ferramentas.py` (114 linhas)

```python
"""Tela "Avaliação e demo" com câmera falsa e banco temporário (sem interação humana)."""

import time

import cv2
import numpy as np
import pytest

from cofre import config
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from tests.apoio_interface import FIX, FOTO_BIDEN, FOTO_OBAMA, FOTO_OBAMA_2, criar_app, girar


def _esperar(app, tela, seg=15):
    fim = time.time() + seg
    girar(app, 0.1)
    while tela.ocupado and time.time() < fim:
        girar(app, 0.1)
    girar(app, 0.2)  # consome a fila
    assert not tela.ocupado


@pytest.fixture
def app(tmp_path):
    a = criar_app(tmp_path / "t.db", imagens=[FOTO_OBAMA])
    cadastrar_de_imagens(a.banco, a.pipeline, DadosCadastro("Barack", "001", "Presidente", 2), [FOTO_OBAMA_2])
    a.mostrar("tela_ferramentas")
    girar(a, 0.3)
    yield a
    a.fechar()


def test_demo_identifica_e_salva_painel(app, tmp_path):
    tela = app.tela("tela_ferramentas")
    tela.nivel_demo.set("Nível 2")
    tela.demonstrar(FOTO_OBAMA)
    _esperar(app, tela)
    assert tela.ultimo_demo is not None and tela.ultimo_demo.principal is not None
    texto = tela.texto_demo.get("1.0", "end")
    assert "identificado: Barack" in texto and "CONCEDIDO" in texto
    # trocar o nível refaz só a fase 5
    tela.nivel_demo.set("Nível 3")
    tela._nivel_demo_alterado()
    assert "NEGADO_NIVEL" in tela.texto_demo.get("1.0", "end")
    destino = tela.salvar_painel()
    assert destino is not None and destino.exists() and destino.parent == config.RELATORIOS_DIR
    assert cv2.imread(str(destino)) is not None


def test_demo_sem_rosto(app, tmp_path):
    tela = app.tela("tela_ferramentas")
    sem_rosto = tmp_path / "cinza.jpg"
    cv2.imwrite(str(sem_rosto), np.full((300, 400, 3), 120, np.uint8))
    tela.demonstrar(sem_rosto)
    _esperar(app, tela)
    assert tela.ultimo_demo.principal is None
    assert "nenhum rosto" in tela.texto_demo.get("1.0", "end")
    assert "Nenhum rosto" in tela.faixa_demo.texto.cget("text")


def test_demo_arquivo_invalido(app, tmp_path):
    tela = app.tela("tela_ferramentas")
    tela.demonstrar(tmp_path / "nao_existe.jpg")
    _esperar(app, tela)
    assert "Falha" in tela.faixa_demo.texto.cget("text")
    assert tela.salvar_painel() is None


def test_autenticar_por_imagem_registra_log(app):
    tela = app.tela("tela_ferramentas")
    tela.nivel_auth.set("Nível 2")
    d = tela.autenticar(FOTO_OBAMA)
    assert d.concedido and tela.ultima_decisao is d
    tela.nivel_auth.set("Nível 3")
    d2 = tela.autenticar(FOTO_OBAMA)
    assert d2.resultado.value == "NEGADO_NIVEL"
    d3 = tela.autenticar(FOTO_BIDEN)
    assert d3.resultado.value == "NEGADO_DESCONHECIDO"
    acessos = app.banco.listar_acessos()
    assert sorted(a.resultado for a in acessos) == ["CONCEDIDO", "NEGADO_DESCONHECIDO", "NEGADO_NIVEL"]
    assert tela.cartao_auth_usuario.valor.cget("text") == "Desconhecido"
    assert tela.cartao_auth_rostos.valor.cget("text") == "1"


def test_avaliar_fotos_de_teste(app):
    tela = app.tela("tela_ferramentas")
    tela.bt_aval_teste.invoke()
    assert tela.pasta_avaliacao == FIX
    tela.bt_avaliar.invoke()
    assert tela.lbl_aval_status.cget("text") == "Avaliando..."
    _esperar(app, tela, 60)
    r = tela.ultima_avaliacao
    assert r is not None and len(r.genuinos) == 2 and len(r.impostores) == 4
    assert "Pessoas: 2" in tela.texto_aval.get("1.0", "end")
    assert len(tela.tabela_varredura.tree.get_children()) == 11
    assert tela.cartao_tar.valor.cget("text").endswith("%")
    assert tela.lbl_aval_status.cget("text") == "" and tela.bt_avaliar.cget("state") == "normal"


def test_avaliar_pasta_vazia_e_sem_rosto(app, tmp_path):
    tela = app.tela("tela_ferramentas")
    tela.avaliar(tmp_path / "vazia")
    assert "não encontrada" in tela.faixa_aval.texto.cget("text")
    (tmp_path / "plana").mkdir()
    tela.avaliar(tmp_path / "plana")
    assert "subpasta" in tela.faixa_aval.texto.cget("text")
    pessoa = tmp_path / "conj" / "ninguem"
    pessoa.mkdir(parents=True)
    cv2.imwrite(str(pessoa / "a.jpg"), np.full((200, 200, 3), 90, np.uint8))
    tela.avaliar(tmp_path / "conj")
    _esperar(app, tela, 30)
    assert tela.ultima_avaliacao is not None and tela.ultima_avaliacao.sem_rosto
    assert "Nenhum par" in tela.faixa_aval.texto.cget("text")
    assert tela.cartao_tar.valor.cget("text") == "-"

```

## `tests/test_interface_terminal.py` (132 linhas)

```python
"""Tela "Terminal de acesso" com câmera falsa: concessão, negação por nível, controles e erro de câmera."""
import time
import types

import pytest

from cofre import config
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from cofre.fase1_aquisicao import ErroAquisicao
from tests.apoio_interface import FOTO_BIDEN, FOTO_BIDEN_2, FOTO_OBAMA, FOTO_OBAMA_2, FonteFalsa, criar_app, girar


class FonteQuebrada:
    """Simula câmera sem permissão / sem dispositivo."""

    def __enter__(self):
        raise ErroAquisicao("Não foi possível abrir a câmera (teste)")

    def __exit__(self, *exc):
        return False


def _esperar(app, cond, seg=15.0):
    fim = time.time() + seg
    while time.time() < fim and not cond():
        girar(app, 0.1)
    return cond()


def _esperar_decisao(app, tela, seg=15.0):
    _esperar(app, lambda: not tela.status.get("decisao"), seg)   # deixa expirar um RESULTADO anterior
    assert _esperar(app, lambda: bool(tela.status.get("decisao")), seg), tela.status
    return tela.status["decisao"]


@pytest.fixture
def app(tmp_path):
    a = criar_app(tmp_path / "t.db", imagens=[FOTO_OBAMA])
    yield a
    a.fechar()


def test_terminal_concede_e_nega_por_nivel(app, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 1.0)
    tela = app.tela("tela_terminal")
    assert type(tela).__name__ == "TelaTerminal"
    girar(app, 0.5)
    assert tela.aviso.winfo_manager() == "grid"            # sem usuários ativos: aviso em amarelo
    assert app.camera.ativo and tela.terminal is not None
    cadastrar_de_imagens(app.banco, app.pipeline, DadosCadastro("Obama", "001", "Presidente", 2), [FOTO_OBAMA_2])
    tela.botao_recarregar.invoke()
    assert tela.aviso.winfo_manager() == ""
    assert tela.cartao_galeria.valor.cget("text") == "1"
    tela.alternar_liveness(False)
    tela.definir_nivel(2)
    d = _esperar_decisao(app, tela)
    assert d["concedido"] and d["nome"] == "Obama" and d["similaridade"] >= config.LIMIAR_COSSENO
    assert tela.faixa.cget("fg_color") == "#2ecc71"
    assert "Obama" in tela.faixa.texto.cget("text")
    assert "acima" in tela.rotulo_similaridade.cget("text")
    assert app.banco.listar_acessos(1)[0].resultado == "CONCEDIDO"
    assert len(tela.tabela.tree.get_children()) >= 1
    # nível 3 exigido: Obama (nível 2) é negado por nível -> faixa laranja
    tela.definir_nivel(3)
    assert tela.seletor_nivel.get() == "3 Cofre do Ministro" and tela.terminal.nivel_exigido == 3
    d = _esperar_decisao(app, tela)
    assert d["resultado"] == "NEGADO_NIVEL"
    assert tela.faixa.cget("fg_color") == "#f39c12"
    assert app.banco.listar_acessos(1)[0].resultado == "NEGADO_NIVEL"


def test_cadastro_feito_em_outra_janela_entra_sem_recarregar(app, tmp_path):
    """Outra janela (outro processo) grava no mesmo banco: o terminal percebe e recarrega."""
    from cofre.banco import Banco
    tela = app.tela("tela_terminal")
    girar(app, 1.5)
    assert tela.terminal is not None and tela.terminal.reconhecedor.total_amostras == 0
    outra = Banco(app.banco.caminho)                     # conexão separada, como a de outra janela
    try:
        cadastrar_de_imagens(outra, app.pipeline, DadosCadastro("Obama", "001", "Presidente", 2), [FOTO_OBAMA_2])
    finally:
        outra.fechar()
    assert _esperar(app, lambda: tela.terminal.reconhecedor.total_amostras == 1, 5.0)
    assert tela.cartao_galeria.valor.cget("text") == "1"
    assert tela.aviso.winfo_manager() == ""


def test_controles_atalhos_e_painel_didatico(app):
    tela = app.tela("tela_terminal")
    girar(app, 0.5)
    tela._tecla(types.SimpleNamespace(char="1", widget=None))
    assert tela.nivel == 1 and tela.terminal.nivel_exigido == 1 and tela.seletor_nivel.get() == "1 Área comum"
    tela.seletor_nivel.set("2 Diretores"); tela._ao_escolher_nivel("2 Diretores")
    assert tela.terminal.nivel_exigido == 2
    antes = tela.liveness
    tela._tecla(types.SimpleNamespace(char="l", widget=None))
    assert tela.liveness is (not antes) and tela.terminal.liveness_ativo is tela.liveness
    tela.chave_liveness.toggle()
    assert tela.terminal.liveness_ativo is antes
    tela.chave_didatico.toggle()
    # Espera pela condição em vez de um tempo fixo: com a máquina carregada o frame atrasa.
    assert _esperar(app, lambda: tela.didatico and tela.video_didatico.winfo_manager() == "grid"
                    and tela.video_didatico._img is not None, 5.0)
    tela._tecla(types.SimpleNamespace(char="d", widget=None))
    assert _esperar(app, lambda: not tela.didatico and tela.video_didatico.winfo_manager() == "", 3.0)
    tela._tecla(types.SimpleNamespace(char="r", widget=None))     # recarregar não pode quebrar
    assert _esperar(app, lambda: tela.video._img is not None and tela.cartao_fps.valor.cget("text") != "0", 3.0)


def test_erro_de_camera_e_tentar_novamente(app):
    tela = app.tela("tela_terminal")
    girar(app, 0.5)
    app.camera.fonte_fabrica = FonteQuebrada
    tela.botao_camera.invoke()
    assert _esperar(app, lambda: tela.botao_tentar.winfo_manager() == "place", 5.0)
    assert "Câmera indisponível" in tela.video.cget("text")
    assert tela.faixa.cget("fg_color") == "#e74c3c"
    app.camera.fonte_fabrica = lambda: FonteFalsa([FOTO_BIDEN])
    tela.botao_tentar.invoke()
    assert _esperar(app, lambda: app.camera.ativo and tela.botao_tentar.winfo_manager() == "", 5.0)
    assert tela.status.get("estado") in {"AGUARDANDO", "CONFIRMANDO", "RESULTADO", "LIVENESS"}


def test_troca_de_tela_desliga_e_religa_camera(app):
    tela = app.tela("tela_terminal")
    girar(app, 0.5)
    assert app.camera.ativo
    app.mostrar("tela_usuarios")
    girar(app, 0.3)
    assert not app.camera.ativo
    app.mostrar("tela_terminal")
    assert _esperar(app, lambda: app.camera.ativo and tela.video._img is not None, 5.0)

```

## `tests/test_interface_usuarios.py` (128 linhas)

```python
"""Tela "Usuários" do aplicativo desktop, exercitada sem webcam e sem interação humana."""
from tkinter import messagebox

import pytest

from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from tests.apoio_interface import FOTO_OBAMA, criar_app, girar


@pytest.fixture
def app(tmp_path, fotos):
    app = criar_app(tmp_path / "t.db", imagens=[FOTO_OBAMA])
    cadastrar_de_imagens(app.banco, app.pipeline, DadosCadastro("Barack Obama", "001", "Ministro", 3), fotos["obama"])
    cadastrar_de_imagens(app.banco, app.pipeline, DadosCadastro("Joe Biden", "002", "Diretor", 2), fotos["biden"][:1])
    app.mostrar("tela_usuarios")
    girar(app, 0.3)
    yield app
    app.fechar()


def _tela(app):
    return app.tela("tela_usuarios")


def _selecionar(app, iid: str):
    t = _tela(app)
    t.tabela.tree.selection_set(iid)
    t.tabela.tree.event_generate("<<TreeviewSelect>>")
    girar(app, 0.1)
    return t


def _linhas(t):
    return [t.tabela.tree.item(i, "values") for i in t.tabela.tree.get_children()]


def test_tabela_e_cartoes(app):
    t = _tela(app)
    linhas = _linhas(t)
    assert len(linhas) == 2
    por_nome = {l[1]: l for l in linhas}
    assert por_nome["Barack Obama"][4] == "3 - Ministro do Meio Ambiente"
    assert int(por_nome["Barack Obama"][5]) == 2 and int(por_nome["Joe Biden"][5]) == 1
    assert t.cartao_total.valor.cget("text") == "2" and t.cartao_ativos.valor.cget("text") == "2"
    assert t.cartoes_nivel[3].valor.cget("text") == "1" and t.cartoes_nivel[1].valor.cget("text") == "0"
    # sem seleção os botões de ação ficam desabilitados
    assert all(b.cget("state") == "disabled" for b in (t.btn_nivel, t.btn_ativo, t.btn_fotos, t.btn_remover))


def test_busca_filtra_por_nome_e_matricula(app):
    t = _tela(app)
    t.busca_var.set("biden")
    girar(app, 0.1)
    assert [l[1] for l in _linhas(t)] == ["Joe Biden"]
    t.busca_var.set("001")
    girar(app, 0.1)
    assert [l[1] for l in _linhas(t)] == ["Barack Obama"]
    t.busca_var.set("")
    girar(app, 0.1)
    assert len(_linhas(t)) == 2


def test_alterar_nivel_ativar_desativar(app):
    t = _selecionar(app, "2")  # Biden
    assert t.btn_nivel.cget("state") == "normal"
    t.alterar_nivel(1)
    girar(app, 0.1)
    assert app.banco.obter_usuario(2).nivel == 1
    assert t.tabela.tree.item("2", "values")[4].startswith("1 -")
    assert t.cartoes_nivel[1].valor.cget("text") == "1"
    assert t.tabela.selecionado() == "2"  # seleção mantida após recarregar
    t.btn_ativo.invoke()
    girar(app, 0.1)
    assert app.banco.obter_usuario(2).ativo is False
    assert "inativo" in t.tabela.tree.item("2", "tags")
    assert t.cartao_ativos.valor.cget("text") == "1"
    t.btn_ativo.invoke()
    girar(app, 0.1)
    assert app.banco.obter_usuario(2).ativo is True


def test_dialogo_de_nivel_abre_e_fecha(app):
    t = _selecionar(app, "1")
    t.btn_nivel.invoke()
    girar(app, 0.2)
    assert t._janela_nivel is not None and t._janela_nivel.winfo_exists()
    t._fechar_janela_nivel()
    girar(app, 0.1)
    assert t._janela_nivel is None


def test_ver_fotos_abre_toplevel_com_miniaturas(app):
    t = _selecionar(app, "1")  # Obama, 2 fotos
    t.btn_fotos.invoke()
    girar(app, 0.3)
    jan = t._janela_fotos
    assert jan is not None and jan.winfo_exists()
    assert len(jan.miniaturas) == 2
    app.mostrar("tela_acessos")  # trocar de tela fecha a janela auxiliar
    girar(app, 0.1)
    assert t._janela_fotos is None


def test_remover_pede_confirmacao(app, monkeypatch):
    t = _selecionar(app, "2")
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
    t.btn_remover.invoke()
    girar(app, 0.1)
    assert app.banco.obter_usuario(2) is not None
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    t.btn_remover.invoke()
    girar(app, 0.1)
    assert app.banco.obter_usuario(2) is None
    assert len(_linhas(t)) == 1 and t.cartao_total.valor.cget("text") == "1"
    assert t.btn_remover.cget("state") == "disabled"


def test_avisa_terminal_e_novo_cadastro(app):
    chamadas = []
    app.mostrar("tela_terminal")
    app.tela("tela_terminal").recarregar_galeria = lambda: chamadas.append(1)
    app.mostrar("tela_usuarios")
    t = _selecionar(app, "1")
    t.alterar_nivel(2)
    assert chamadas == [1]
    t.btn_novo.invoke()
    girar(app, 0.1)
    assert app._atual == "tela_cadastro"

```

## `tests/test_liveness.py` (76 linhas)

```python
"""Anti-fraude: desafio de movimento, bloqueio por tentativas e confirmador de frames."""
from cofre.liveness import ControleTentativas, DesafioMovimento, EtapaLiveness


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_desafio_aprova_esquerda_direita_centro():
    rl = Relogio()
    d = DesafioMovimento(limiar=0.2, timeout=10, relogio=rl)
    d.iniciar()
    assert d.atualizar(0.0) is EtapaLiveness.VIRAR_ESQUERDA
    assert d.atualizar(-0.3) is EtapaLiveness.VIRAR_DIREITA
    assert d.atualizar(-0.3) is EtapaLiveness.VIRAR_DIREITA   # ainda virado p/ esquerda
    assert d.atualizar(0.35) is EtapaLiveness.VOLTAR_CENTRO
    assert d.atualizar(0.02) is EtapaLiveness.APROVADO
    assert not d.ativo


def test_desafio_falha_por_timeout_e_ignora_none():
    rl = Relogio()
    d = DesafioMovimento(limiar=0.2, timeout=5, relogio=rl)
    d.iniciar()
    assert d.atualizar(None) is EtapaLiveness.VIRAR_ESQUERDA
    rl.t = 6
    assert d.atualizar(-0.5) is EtapaLiveness.FALHOU


def test_foto_estatica_nao_passa():
    rl = Relogio()
    d = DesafioMovimento(limiar=0.2, timeout=5, relogio=rl)
    d.iniciar()
    for _ in range(50):
        d.atualizar(0.01)
    assert d.etapa is EtapaLiveness.VIRAR_ESQUERDA


def test_bloqueio_apos_tres_falhas_e_expira():
    rl = Relogio()
    c = ControleTentativas(max_falhas=3, janela=60, bloqueio=30, relogio=rl)
    assert not c.registrar_falha() and not c.registrar_falha()
    assert c.registrar_falha() and c.bloqueado
    rl.t = 31
    assert not c.bloqueado
    c.registrar_falha(); c.registrar_sucesso(); c.registrar_falha(); c.registrar_falha()
    assert not c.bloqueado  # sucesso zera a contagem


def test_falhas_fora_da_janela_nao_contam():
    rl = Relogio()
    c = ControleTentativas(max_falhas=3, janela=10, bloqueio=30, relogio=rl)
    c.registrar_falha(); rl.t = 20; c.registrar_falha(); rl.t = 21
    assert not c.registrar_falha()


def test_confirmador_exige_identidade_estavel():
    from cofre.autenticacao import Confirmador
    from cofre.banco import Usuario
    from cofre.fase5_reconhecimento import Identificacao
    u1 = Usuario(1, "A", "a", "", 1, True, ""); u2 = Usuario(2, "B", "b", "", 1, True, "")
    c = Confirmador(3)
    assert c.adicionar(Identificacao(u1, 0.8)) is None
    assert c.adicionar(Identificacao(u2, 0.8)) is None
    assert c.adicionar(Identificacao(u1, 0.8)) is None     # misturou identidades
    assert c.adicionar(Identificacao(u1, 0.6)) is None
    r = c.adicionar(Identificacao(u1, 0.7))
    assert r is not None and r.usuario.id == 1 and abs(r.similaridade - 0.7) < 1e-6
    c.limpar()
    for _ in range(3):
        r = c.adicionar(Identificacao(None, 0.1))
    assert r is not None and not r.reconhecido

```

## `tests/test_pipeline.py` (62 linhas)

```python
"""Fases 2-4: pré-processamento, detecção, alinhamento e embedding."""
import numpy as np

from cofre import config
from cofre import fase2_preprocessamento as f2
from cofre import fase4_representacao as f4
from cofre.fase1_aquisicao import carregar_imagem


def test_preprocessamento_gera_todas_etapas():
    img = carregar_imagem(__import__("tests.conftest", fromlist=["FIX"]).FIX / "obama" / "obama_2012.jpg")
    pre = f2.preprocessar(img)
    assert pre.reduzida.shape[1] == config.LARGURA_PROCESSAMENTO
    assert pre.cinza.ndim == 2
    assert pre.equalizada.shape == pre.reduzida.shape
    assert set(pre.etapas) >= {"1 original", "2 cinza", "2 CLAHE"}


def test_qualidade_rejeita_borrado_e_escuro():
    nitida = np.random.default_rng(0).integers(0, 255, (112, 112), np.uint8)
    assert f2.avaliar_qualidade(nitida).aprovada
    escura = np.zeros((112, 112), np.uint8)
    q = f2.avaliar_qualidade(escura)
    assert not q.aprovada and q.motivo in ("imagem borrada", "muito escura")


def test_detecta_um_rosto_e_embedding_normalizado(pipeline, fotos):
    res = pipeline.processar(carregar_imagem(fotos["obama"][0]))
    assert len(res.rostos) == 1
    p = res.principal
    assert p.alinhado.shape == (112, 112, 3)
    assert p.embedding.shape == (128,)
    assert abs(np.linalg.norm(p.embedding) - 1.0) < 1e-4
    assert p.rosto.confianca >= config.DETECCAO_SCORE_MIN
    assert abs(p.rosto.yaw()) < 0.3  # retrato frontal


def test_sem_rosto_em_imagem_vazia(pipeline):
    res = pipeline.processar(np.zeros((480, 640, 3), np.uint8))
    assert res.rostos == []


def test_mesma_pessoa_acima_do_limiar_e_outra_abaixo(pipeline, fotos):
    emb = {n: [pipeline.processar(carregar_imagem(c)).principal.embedding for c in cs] for n, cs in fotos.items()}
    genuino = f4.similaridade_cosseno(emb["obama"][0], emb["obama"][1])
    impostor = f4.similaridade_cosseno(emb["obama"][0], emb["biden"][0])
    assert genuino >= config.LIMIAR_COSSENO
    assert impostor < config.LIMIAR_COSSENO
    assert genuino - impostor > 0.3


def test_lbp_codigos_e_histograma():
    img = np.random.default_rng(1).integers(0, 255, (64, 64), np.uint8)
    mapa = f4.lbp_mapa(img)
    assert mapa.shape == (62, 62) and mapa.dtype == np.uint8
    hist = f4.lbp_histograma(img, (2, 2))
    assert hist.shape == (4 * 256,) and abs(hist.sum() - 1.0) < 1e-5


def test_etapas_didaticas_incluem_as_cinco_fases(pipeline, fotos):
    etapas = pipeline.processar(carregar_imagem(fotos["biden"][0])).etapas_didaticas()
    assert any(k.startswith("3 ") for k in etapas) and any(k.startswith("4 ") for k in etapas)

```

## `tests/test_pose.py` (101 linhas)

```python
"""Filtro de pose do terminal (pelos 5 pontos do detector) e as 9 poses do cadastro.

Regra: entrada que não serve (rosto virado, inclinado, cabeça baixa/erguida, borrado) é ignorada
pelo terminal: nada é decidido, nada entra no log e nada conta para o bloqueio. A prova de vida,
que pede o giro da cabeça, não passa pelo filtro."""
import numpy as np

from cofre import config
from cofre.autenticacao import Estado, TerminalAutenticacao
from cofre.cadastro import INSTRUCOES_POSE, DadosCadastro, SessaoCadastro, cadastrar_de_imagens
from cofre.fase1_aquisicao import carregar_imagem
from cofre.fase3_segmentacao import Rosto, rosto_de_linha


def _rosto(olho_dir=(40, 40), olho_esq=(80, 40), nariz=(60, 62), boca_dir=(45, 85), boca_esq=(75, 85)) -> Rosto:
    linha = np.array([20, 10, 80, 100, *olho_dir, *olho_esq, *nariz, *boca_dir, *boca_esq, 0.95], np.float32)
    return rosto_de_linha(linha)


def test_medidas_de_pose_e_limites():
    frontal = _rosto()
    assert abs(frontal.yaw()) < 0.01 and abs(frontal.roll()) < 0.01 and 0.45 < frontal.razao_nariz() < 0.55
    assert frontal.problema_pose() == ""
    assert "Vire o rosto" in _rosto(nariz=(100, 62)).problema_pose()            # yaw 1,0
    assert "Endireite" in _rosto(olho_esq=(80, 70)).problema_pose()             # roll ~37°
    assert "Levante a cabeça" in _rosto(nariz=(60, 80)).problema_pose()          # nariz perto da boca
    assert "Abaixe o queixo" in _rosto(nariz=(60, 50)).problema_pose()           # nariz perto dos olhos
    # os limites são lidos de config na hora (ajustáveis na tela de configurações)
    assert _rosto(nariz=(72, 62)).problema_pose() == ""                           # yaw 0,3
    antes = config.POSE_MAX_YAW
    try:
        config.POSE_MAX_YAW = 0.2
        assert "Vire o rosto" in _rosto(nariz=(72, 62)).problema_pose()
    finally:
        config.POSE_MAX_YAW = antes


def _terminal(banco, pipeline, fotos, nivel, liveness, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EVIDENCIAS_DIR", tmp_path / "ev")
    cadastrar_de_imagens(banco, pipeline, DadosCadastro("Obama", "001", "Ministro", 3), [fotos["obama"][0]])
    return TerminalAutenticacao(banco, pipeline, nivel_exigido=nivel, liveness=liveness)


def _alimentar(term, pipeline, frame, n):
    for _ in range(n):
        res = pipeline.processar(frame)
        term.passo(frame, res.principal, len(res.rostos))
        term.desenhar(frame, res, 30.0)
    return res


def test_pose_ruim_nao_tenta_nem_conta_falha(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 3, False, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    monkeypatch.setattr(Rosto, "problema_pose", lambda self: "Vire o rosto para a câmera")
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO + 3)
    assert t.estado is Estado.AGUARDANDO and t.confirmador.progresso == 0
    assert t.status()["orientacao"] == "Vire o rosto para a câmera"
    assert banco.listar_acessos() == [] and not t.tentativas.bloqueado and t.tentativas._falhas == []
    # pose corrigida: volta a funcionar normalmente
    monkeypatch.undo()
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO)
    assert t.estado is Estado.RESULTADO and t._decisao.concedido and t.status()["orientacao"] == ""


def test_imagem_borrada_nao_tenta(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 3, False, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    monkeypatch.setattr(config, "MIN_NITIDEZ", 1e9)
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO + 1)
    assert t.estado is Estado.AGUARDANDO and "borrada" in t.status()["orientacao"]
    assert banco.listar_acessos() == []


def test_prova_de_vida_nao_passa_pelo_filtro(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 3, True, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO)
    assert t.estado is Estado.LIVENESS
    # girar a cabeça para o desafio deixa o rosto "fora da pose": o desafio continua mesmo assim
    monkeypatch.setattr(Rosto, "problema_pose", lambda self: "Vire o rosto para a câmera")
    for yaw in (-0.9, 0.9, 0.0):
        monkeypatch.setattr(Rosto, "yaw", lambda self, y=yaw: y)
        _alimentar(t, pipeline, frame, 1)
        assert t.status()["orientacao"] == ""
    assert t.estado is Estado.RESULTADO and t._decisao.concedido


def test_cadastro_percorre_as_nove_poses(banco, pipeline, fotos, monkeypatch):
    assert len(INSTRUCOES_POSE) == 9 and config.AMOSTRAS_POR_CADASTRO == 18
    monkeypatch.setattr(config, "INTERVALO_AMOSTRAS_SEG", 0.0)
    s = SessaoCadastro(banco, pipeline, DadosCadastro("Obama", "001", "", 3), amostras=18)
    frame = carregar_imagem(fotos["obama"][1])
    vistas = []
    while not s.concluida:
        res = pipeline.processar(frame)
        s.passo(frame, res)
        vistas.append(s.pose)
    assert s.capturadas == 18 and [vistas.count(p) for p in INSTRUCOES_POSE] == [2] * 9
    assert vistas == [p for p in INSTRUCOES_POSE for _ in (0, 1)]
    s.cancelar()

```

## `tests/test_qt_app.py` (420 linhas)

```python
"""Aplicativo Qt Quick (PySide6 + QML) sem tela: carga das páginas, terminal, cadastro, usuários,
auditoria, avaliação e configurações. Câmera falsa, banco temporário e pipeline real."""

from __future__ import annotations

import pytest

from cofre import config, parametros
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from tests.apoio_interface import FOTO_BIDEN, FOTO_BIDEN_2, FOTO_OBAMA, FOTO_OBAMA_2, FIX
from tests.apoio_qt import criar_contexto

PAGINAS = ("terminal", "cadastro", "usuarios", "acessos", "avaliacao", "config")


@pytest.fixture(autouse=True)
def _config_isolada(tmp_path, monkeypatch):
    """Pasta de dados temporária (config_usuario.json) e parâmetros restaurados ao fim do teste."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    antes = parametros.valores_atuais()
    yield
    parametros.aplicar(antes)


def _contexto(qapp, tmp_path, pipeline, imagens=None):
    return criar_contexto(qapp, tmp_path / "t.db", pipeline=pipeline, imagens=imagens)


def _cadastrar(ctx, nome, matricula, nivel, fotos):
    u, n, _ = cadastrar_de_imagens(ctx.apl.banco, ctx.apl.pipeline, DadosCadastro(nome, matricula, "", nivel), fotos)
    assert n == len(fotos)
    ctx.apl.banco_alterado()
    return u


# ---------------------------------------------------------------------------- estrutura
def test_todas_as_paginas_carregam_sem_avisos_qml(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        assert ctx.janela is not None, ctx.avisos
        for pagina in PAGINAS:
            ctx.apl.navegar(pagina)
            ctx.girar(0.4)
            assert ctx.apl.pagina == pagina
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_sem_camera_mostra_erro_e_nao_decide(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)          # SemCamera: falha ao abrir
    try:
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: ctx.apl.camera.estado == "erro", 5)
        t = ctx.apl.terminal
        assert ctx.apl.camera.erro != ""                    # a tela mostra o erro do serviço da câmera
        assert t.resultadoConcedido is False and t.estado != "RESULTADO"
        assert ctx.apl.banco.listar_acessos() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- terminal
def test_terminal_concede_quando_o_backend_concede(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    try:
        _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA_2])
        t = ctx.apl.terminal
        t.definirLiveness(False)
        t.definirNivel(3)
        decisoes = []
        t.decisaoTomada.connect(lambda ok, tipo: decisoes.append((ok, tipo)))
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: t.estado == "RESULTADO", 20)
        assert t.resultadoTipo == "CONCEDIDO" and t.resultadoConcedido is True
        assert t.resultadoNome == "Barack Obama"
        # a tela só repete o que o backend decidiu e registrou
        assert ctx.apl.terminal_vm.terminal.decisao_atual.concedido is True
        assert ctx.apl.banco.listar_acessos()[0].resultado == "CONCEDIDO"
        assert decisoes and decisoes[0] == (True, "CONCEDIDO")
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_terminal_nega_e_bloqueia_sem_nunca_mostrar_concedido(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.5)
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_BIDEN])
    try:
        _cadastrar(ctx, "Joe Biden", "D1", 2, [FOTO_BIDEN_2])
        t = ctx.apl.terminal
        t.definirLiveness(False)
        t.definirNivel(3)                                  # Biden tem nível 2: negado por nível
        vistos = []
        t.estadoMudou.connect(lambda: vistos.append((t.estado, t.resultadoConcedido)))
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: t.estado == "BLOQUEADO", 40), ctx.apl.banco.listar_acessos()
        assert not any(concedido for _, concedido in vistos)
        assert t.resultadoConcedido is False and t.bloqueadoRestante > 0
        resultados = [a.resultado for a in ctx.apl.banco.listar_acessos()]
        assert "CONCEDIDO" not in resultados and "BLOQUEADO" in resultados
        assert resultados.count("NEGADO_NIVEL") >= config.MAX_TENTATIVAS_FALHAS
        # controles travados durante o bloqueio (também pelos atalhos de teclado)
        t.definirNivel(1)
        t.definirLiveness(True)
        assert t.nivel == 3 and t.liveness is False
        ctx.girar(1.0)
        assert t.estado == "BLOQUEADO" and t.resultadoConcedido is False
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_fechar_libera_a_camera(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    ctx.apl.navegar("terminal")
    assert ctx.esperar(lambda: ctx.apl.camera.estado == "ativa", 10)
    camera = ctx.apl.camera
    ctx.fechar()
    assert camera.estado == "desligada"
    assert camera._thread is None or not camera._thread.isRunning()


# ---------------------------------------------------------------------------- cadastro
def test_cadastro_valida_campos(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        c = ctx.apl.cadastro
        assert c.iniciarCaptura("", "X1", "", 1) is False and c.erroCampo == "nome"
        assert c.iniciarCaptura("Ana", "", "", 1) is False and c.erroCampo == "matricula"
        _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        assert c.matriculaEmUso("M1") == "Barack Obama"
        assert c.cadastrarPorFotos("Outra", "M1", "", 1, [str(FOTO_BIDEN)]) is False
        assert c.erroCampo == "matricula" and "já cadastrada" in c.erro
    finally:
        ctx.fechar()


def test_cadastro_por_fotos_em_segundo_plano(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        c = ctx.apl.cadastro
        urls = ["file://" + str(FOTO_OBAMA), "file://" + str(FOTO_OBAMA_2)]
        assert c.cadastrarPorFotos("Barack Obama", "M1", "Ministro", 3, urls) is True
        assert ctx.esperar(lambda: c.fase == "formulario" and c.sucesso.get("nome") == "Barack Obama", 20)
        u = ctx.apl.banco.obter_por_matricula("M1")
        assert u is not None and u.nivel == 3 and ctx.apl.banco.contar_amostras(u.id) == 2
        assert ctx.apl.terminal.usuariosAtivos == 1          # o terminal recarregou a galeria
    finally:
        ctx.fechar()


def test_cadastro_pela_camera_conclui_e_cancela(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(config, "AMOSTRAS_POR_CADASTRO", 3)
    monkeypatch.setattr(config, "INTERVALO_AMOSTRAS_SEG", 0.2)
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    try:
        c = ctx.apl.cadastro
        ctx.apl.navegar("cadastro")
        assert c.iniciarCaptura("Barack Obama", "M1", "", 3) is True
        assert ctx.esperar(lambda: c.capturadas >= 3, 20), c.status
        assert c.total == 3 and c.sessao.amostras == 3      # a quantidade configurada vale de fato
        c.concluir()
        u = ctx.apl.banco.obter_por_matricula("M1")
        assert u is not None and ctx.apl.banco.contar_amostras(u.id) == 3
        assert c.fase == "formulario" and c.sucesso.get("amostras") == 3

        assert c.iniciarCaptura("Outro", "M2", "", 1) is True
        assert ctx.esperar(lambda: c.capturadas >= 1, 20)
        c.cancelar()
        assert ctx.apl.banco.obter_por_matricula("M2") is None   # nada fica gravado
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_fechar_no_meio_do_cadastro_desfaz(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    c = ctx.apl.cadastro
    ctx.apl.navegar("cadastro")
    assert c.iniciarCaptura("Barack Obama", "M1", "", 3)
    assert ctx.esperar(lambda: c.capturadas >= 1, 20)
    banco_path = ctx.apl.banco.caminho
    ctx.fechar()
    from cofre.banco import Banco
    b = Banco(banco_path)
    try:
        assert b.obter_por_matricula("M1") is None
    finally:
        b.fechar()


# ---------------------------------------------------------------------------- usuários
def test_usuarios_filtros_e_acoes(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        ob = _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        bi = _cadastrar(ctx, "Joe Biden", "D1", 2, [FOTO_BIDEN])
        u = ctx.apl.usuarios
        ctx.apl.navegar("usuarios")
        assert u.total == 2 and u.modelo.contagem == 2 and list(u.porNivel) == [0, 1, 1]
        u.definirBusca("bid")
        assert [i["nome"] for i in u.modelo.itens()] == ["Joe Biden"]
        u.limparFiltros()
        u.definirFiltroNivel(3)
        assert [i["nome"] for i in u.modelo.itens()] == ["Barack Obama"]
        u.limparFiltros()

        assert u.alterarNivel(bi.id, 1) is True and ctx.apl.banco.obter_usuario(bi.id).nivel == 1
        assert u.alterarNivel(bi.id, 9) is False
        assert u.alternarAtivo(bi.id) is True and not ctx.apl.banco.obter_usuario(bi.id).ativo
        assert ctx.apl.terminal.usuariosAtivos == 1
        u.definirFiltroStatus("inativos")
        assert [i["nome"] for i in u.modelo.itens()] == ["Joe Biden"]
        assert u.fotos(ob.id) and all(f["existe"] for f in u.fotos(ob.id))
        assert u.remover(bi.id) is True and ctx.apl.banco.obter_usuario(bi.id) is None
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_usuario_em_cadastro_nao_pode_ser_removido(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    try:
        c, u = ctx.apl.cadastro, ctx.apl.usuarios
        ctx.apl.navegar("cadastro")
        assert c.iniciarCaptura("Barack Obama", "M1", "", 3)
        assert ctx.esperar(lambda: c.sessao is not None, 10)
        ctx.apl.navegar("usuarios")                         # captura pausada em outra tela
        linha = u.modelo.itens()[0]
        assert linha["emCadastro"] is True
        assert u.remover(linha["id"]) is False and u.alternarAtivo(linha["id"]) is False
        assert ctx.apl.banco.obter_usuario(linha["id"]) is not None
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- auditoria
def test_acessos_filtros_detalhe_e_exportacao(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        ob = _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        b = ctx.apl.banco
        b.registrar_acesso(usuario_id=ob.id, nome_detectado=ob.nome, nivel_usuario=3, nivel_exigido=3,
                           similaridade=0.8, resultado="CONCEDIDO")
        b.registrar_acesso(usuario_id=None, nome_detectado=None, nivel_usuario=None, nivel_exigido=1,
                           similaridade=0.1, resultado="NEGADO_DESCONHECIDO")
        a = ctx.apl.acessos
        ctx.apl.navegar("acessos")
        assert a.total == 2 and a.concedidos == 1 and a.negados == 1 and a.taxa == 0.5
        a.definirFiltroResultado("CONCEDIDO")
        assert [i["nome"] for i in a.modelo.itens()] == ["Barack Obama"]
        a.limparFiltros()
        a.filtrarPessoa("DESCONHECIDO")
        assert [i["resultado"] for i in a.modelo.itens()] == ["NEGADO_DESCONHECIDO"]
        a.limparFiltros()
        a.definirFiltroNivel(3)
        assert a.listados == 1
        a.definirFiltroResultado("NAO_EXISTE")              # valor inválido é ignorado
        assert a.filtroResultado == ""
        d = a.detalhe(a.modelo.itens()[0]["id"])
        assert d["concedido"] is True and d["limiar"] == f"{config.LIMIAR_COSSENO:.3f}"

        a.exportar("csv")
        assert ctx.esperar(lambda: not a.exportando and a.ultimoExportado != "", 10)
        from pathlib import Path
        assert Path(a.ultimoExportado).exists()
        assert len(b.listar_acessos()) == 2                  # a auditoria nunca grava no log
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- avaliação
def test_avaliacao_demo_autenticacao_e_metricas(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        _cadastrar(ctx, "Joe Biden", "D1", 2, [FOTO_BIDEN_2])
        v = ctx.apl.avaliacao
        ctx.apl.navegar("avaliacao")
        v.demonstrar(str(FOTO_OBAMA))
        assert ctx.esperar(lambda: not v.demoProcessando and len(v.demoFases) == 5, 20)
        assert len(v.demoEtapas) >= 5 and v.fonteDemo.temImagem
        assert ctx.apl.banco.listar_acessos() == []           # a demonstração não grava no log

        v.definirNivelAuth(3)
        v.autenticar(str(FOTO_BIDEN))
        assert ctx.esperar(lambda: not v.authProcessando and v.authResultado.get("resultado"), 20)
        assert v.authResultado["resultado"] == "NEGADO_NIVEL" and v.authResultado["concedido"] is False
        assert [a.resultado for a in ctx.apl.banco.listar_acessos()] == ["NEGADO_NIVEL"]   # registrada

        v.usarFotosTeste()
        v.avaliar()
        assert ctx.esperar(lambda: not v.avalProcessando and v.avalResultado.get("valido") is not None, 60)
        r = v.avalResultado
        assert r["valido"] is True and r["pessoas"] == len([p for p in FIX.iterdir() if p.is_dir()])
        assert all(isinstance(p["limiar"], float) for p in r["curva"])
        atuais = [i for i in v.modeloVarredura.itens() if i["atual"] is True]
        assert len(atuais) == 1
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- configurações
def test_config_valida_aplica_e_salva(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        c = ctx.apl.configuracoes
        ctx.apl.navegar("config")
        limiar = config.LIMIAR_COSSENO
        assert c.definir("LIMIAR_COSSENO", "0,4") is True and c.pendentes == 1
        assert config.LIMIAR_COSSENO == limiar                 # só vale depois de aplicar
        assert c.definir("LIMIAR_COSSENO", "abc") is False and c.mensagemTipo == "erro"
        assert c.definir("LIMIAR_COSSENO", 5) is True           # fora do intervalo: limitado
        campo = next(i for i in c.modeloCampos.itens() if i["chave"] == "LIMIAR_COSSENO")
        assert campo["valor"] == parametros.CAMPOS_POR_CHAVE["LIMIAR_COSSENO"].maximo
        c.definir("LIMIAR_COSSENO", 0.4)
        assert c.aplicar() is True and config.LIMIAR_COSSENO == 0.4 and c.pendentes == 0
        assert ctx.apl.terminal.limiar == 0.4
        c.descartar()

        # parâmetros fixados na importação são somente leitura (sem efeito real se mudados)
        bloqueio = config.BLOQUEIO_SEG
        assert c.definir("BLOQUEIO_SEG", 5) is False and config.BLOQUEIO_SEG == bloqueio
        campo = next(i for i in c.modeloCampos.itens() if i["chave"] == "MAX_TENTATIVAS_FALHAS")
        assert campo["editavel"] is False and campo["seguranca"] is True

        assert c.salvar() is True and parametros.caminho_arquivo().exists()
        assert parametros.caminho_arquivo().parent == tmp_path
        assert c.carregar() is True
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_terminal_mostra_orientacao_de_pose_e_leituras(qapp, tmp_path, pipeline, monkeypatch):
    from cofre.fase3_segmentacao import Rosto
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    try:
        _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA_2])
        t = ctx.apl.terminal
        t.definirLiveness(False)
        monkeypatch.setattr(Rosto, "problema_pose", lambda self: "Endireite a cabeça")
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: t.orientacao == "Endireite a cabeça", 15)
        ctx.girar(1.0)
        assert t.estado == "AGUARDANDO" and t.resultadoTipo == "" and ctx.apl.banco.listar_acessos() == []
        assert t.poseYaw > -90 and len(t.assinatura) == 128 and len(t.assinaturaReferencia) == 128
        assert t.limitesPose()["yaw"] == config.POSE_MAX_YAW
        monkeypatch.undo()
        assert ctx.esperar(lambda: t.estado == "RESULTADO", 20)
        assert t.orientacao == "" and t.resultadoTipo == "CONCEDIDO"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- área liberada
def test_area_liberada_abre_so_com_concessao_do_backend(qapp, tmp_path, pipeline, monkeypatch):
    import numpy as np
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.5)
    imagens = [FOTO_BIDEN]
    ctx = criar_contexto(qapp, tmp_path / "t.db", pipeline=pipeline, imagens=imagens)
    try:
        bi = _cadastrar(ctx, "Joe Biden", "D1", 2, [FOTO_BIDEN_2])
        t, s = ctx.apl.terminal, ctx.apl.sessao
        t.definirLiveness(False)
        t.definirNivel(3)                                   # nível 2 numa área de nível 3: negado
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: t.estado == "RESULTADO", 20) and t.resultadoTipo == "NEGADO_NIVEL"
        assert s.ativa is False and s.conteudo(1) == {}     # negado: nada abre, nada é lido
        # o QML não consegue abrir a sessão por conta própria
        assert s.abrir(None, 1) is False and s.ativa is False

        # troca a área já: mais duas negações seguidas bloqueariam o terminal
        ctx.apl.terminal.definirNivel(2)                    # agora a área é compatível: concedido
        assert ctx.esperar(lambda: s.ativa, 25), (t.estado, t.resultadoTipo)
        assert s.nome == "Joe Biden" and s.nivelUsuario == 2 and s.areaSolicitada == 2
        assert [a["nivel"] for a in s.areas if a["liberada"]] == [1, 2]
        assert s.liberada(1) and s.liberada(2) and not s.liberada(3)
        assert s.conteudo(1)["titulo"] == config.AREAS[1] and s.conteudo(2)["divisoes"]
        assert s.conteudo(3) == {}                          # acima do nível: vazio
        assert ctx.esperar(lambda: ctx.apl.camera.estado == "desligada", 5)   # câmera pausada
        ctx.apl.navegar("usuarios")
        assert ctx.apl.pagina == "terminal"                 # navegação travada com a sessão aberta
        assert len(ctx.apl.banco.listar_acessos()) == 2     # só as duas decisões do backend no log

        imagens[0] = np.zeros((480, 640, 3), np.uint8)      # ninguém na frente da câmera ao encerrar
        s.encerrar()
        assert s.ativa is False and s.conteudo(1) == {}
        assert ctx.esperar(lambda: ctx.apl.camera.estado == "ativa", 10)      # câmera volta
        assert ctx.esperar(lambda: t.estado == "AGUARDANDO", 5)
        ctx.girar(1.0)
        assert s.ativa is False and len(ctx.apl.banco.listar_acessos()) == 2  # nada reabriu sozinho
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_area_liberada_fecha_por_inatividade_e_respeita_usuario_desativado(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(config, "SESSAO_LIBERADA_SEG", 2)
    ctx = criar_contexto(qapp, tmp_path / "t.db", pipeline=pipeline, imagens=[FOTO_OBAMA])
    try:
        ob = _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA_2])
        t, s = ctx.apl.terminal, ctx.apl.sessao
        t.definirLiveness(False)
        t.definirNivel(1)
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: s.ativa, 25)
        assert s.tempoTotal == 2 and [a["liberada"] for a in s.areas] == [True, True, True]
        s.renovar()
        assert ctx.esperar(lambda: not s.ativa, 6)          # fechou sozinha
        # usuário desativado depois da decisão: a sessão não abre mesmo com decisão concedida
        ctx.apl.banco.definir_ativo(ob.id, False)
        from cofre.fase5_reconhecimento import Decisao, Identificacao, Resultado
        falsa = Decisao(Resultado.CONCEDIDO, Identificacao(ctx.apl.banco.obter_usuario(ob.id), 0.9), 1, "ok")
        assert s.abrir(falsa, 1) is False and s.ativa is False
    finally:
        ctx.fechar()

```

## `tests/test_terminal.py` (93 linhas)

```python
"""Máquina de estados do terminal de autenticação, alimentada com imagens (sem webcam)."""
import numpy as np

from cofre import config
from cofre.autenticacao import Estado, TerminalAutenticacao
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from cofre.fase1_aquisicao import carregar_imagem
from cofre.fase5_reconhecimento import Resultado


def _terminal(banco, pipeline, fotos, nivel, liveness, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EVIDENCIAS_DIR", tmp_path / "ev")
    cadastrar_de_imagens(banco, pipeline, DadosCadastro("Obama", "001", "Ministro", 3), [fotos["obama"][0]])
    cadastrar_de_imagens(banco, pipeline, DadosCadastro("Biden", "002", "Diretor", 2), [fotos["biden"][0]])
    return TerminalAutenticacao(banco, pipeline, nivel_exigido=nivel, liveness=liveness)


def _alimentar(term, pipeline, frame, n):
    for _ in range(n):
        res = pipeline.processar(frame)
        term.passo(frame, res.principal, len(res.rostos))
        term.desenhar(frame, res, 30.0)  # HUD não pode quebrar em nenhum estado
    return res


def test_concede_apos_frames_de_confirmacao_sem_liveness(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 3, False, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO - 1)
    assert t.estado is Estado.CONFIRMANDO
    _alimentar(t, pipeline, frame, 1)
    assert t.estado is Estado.RESULTADO and t._decisao.concedido
    assert banco.listar_acessos()[0].resultado == "CONCEDIDO"


def test_nega_nivel_e_bloqueia_apos_tres_falhas(banco, pipeline, fotos, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.0)
    t = _terminal(banco, pipeline, fotos, 3, False, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["biden"][1])
    for i in range(3):
        _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO)
        assert t._decisao.resultado is Resultado.NEGADO_NIVEL
        _alimentar(t, pipeline, frame, 1)  # sai do estado RESULTADO
    assert t.estado is Estado.BLOQUEADO
    resultados = [a.resultado for a in banco.listar_acessos()]
    assert resultados[0] == "BLOQUEADO" and resultados.count("NEGADO_NIVEL") == 3
    assert any(a.evidencia for a in banco.listar_acessos())


def test_desconhecido_negado(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 1, False, tmp_path, monkeypatch)
    banco.remover_usuario(1); t.reconhecedor.recarregar()  # Obama deixa de existir
    _alimentar(t, pipeline, carregar_imagem(fotos["obama"][1]), config.FRAMES_CONFIRMACAO)
    assert t._decisao.resultado is Resultado.NEGADO_DESCONHECIDO


def test_liveness_exige_movimento(banco, pipeline, fotos, tmp_path, monkeypatch):
    from cofre.fase3_segmentacao import Rosto
    t = _terminal(banco, pipeline, fotos, 3, True, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO)
    assert t.estado is Estado.LIVENESS
    # foto parada: nunca passa
    _alimentar(t, pipeline, frame, 5)
    assert t.estado is Estado.LIVENESS
    # simula a cabeça virando: esquerda, direita, centro
    for yaw in (-0.4, 0.4, 0.0):
        monkeypatch.setattr(Rosto, "yaw", lambda self, y=yaw: y)
        _alimentar(t, pipeline, frame, 1)
    assert t.estado is Estado.RESULTADO and t._decisao.concedido


def test_sem_rosto_volta_a_aguardar(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 1, False, tmp_path, monkeypatch)
    _alimentar(t, pipeline, carregar_imagem(fotos["obama"][1]), 2)
    assert t.estado is Estado.CONFIRMANDO
    _alimentar(t, pipeline, np.zeros((480, 640, 3), np.uint8), 1)
    assert t.estado is Estado.AGUARDANDO and t.confirmador.progresso == 0


def test_prova_de_vida_exige_a_identidade_confirmada(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 3, True, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO)
    assert t.estado is Estado.LIVENESS

    outro_rosto = carregar_imagem(fotos["biden"][1])
    _alimentar(t, pipeline, outro_rosto, 1)

    assert t.estado is Estado.RESULTADO
    assert t.decisao_atual.resultado is Resultado.NEGADO_LIVENESS
    assert t.decisao_atual.identificacao is None
    assert [acesso.resultado for acesso in banco.listar_acessos()] == ["NEGADO_LIVENESS"]

```

## `ferramentas/listar_codigo.py` (29 linhas)

```python
#!/usr/bin/env python3
"""Gera docs/LISTAGEM-CODIGO.md com todos os arquivos-fonte do projeto
(item "Relatório com as linhas de código" exigido pela APS)."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
QML = RAIZ / "cofre" / "qt" / "qml" / "Cofre" / "Ui"
ARQUIVOS = [RAIZ / "main.py", RAIZ / "app.py", RAIZ / "app_qt.py", *sorted((RAIZ / "cofre").glob("*.py")),
            *sorted((RAIZ / "cofre" / "interface").glob("*.py")), *sorted((RAIZ / "cofre" / "qt").glob("*.py")),
            *sorted(QML.glob("*.qml")), *sorted(QML.glob("*.js")), QML / "qmldir",
            *sorted((RAIZ / "tests").glob("*.py")),
            RAIZ / "ferramentas" / "listar_codigo.py", RAIZ / "requirements.txt"]
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

```

## `requirements.txt` (6 linhas)

```text
opencv-contrib-python>=4.10
numpy>=1.26
PySide6-Essentials>=6.10
customtkinter>=5.2
pillow>=10
pytest>=8

```
