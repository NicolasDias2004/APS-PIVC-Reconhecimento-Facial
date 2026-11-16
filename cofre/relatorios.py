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
