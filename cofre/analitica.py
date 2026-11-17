"""Fase 5: interpretação do registro de decisões (agregações do painel).

Lê o registro de acessos em modo somente leitura e resume o que o terminal decidiu: quantas
tentativas, com que folga em relação ao limiar e quando. Nada aqui participa da decisão: são
funções puras sobre linhas já gravadas. As consultas nunca selecionam o nome detectado, a
mensagem, a evidência nem o vínculo com o usuário.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from . import leitura_ro

RESULTADOS = ("CONCEDIDO", "NEGADO_NIVEL", "NEGADO_DESCONHECIDO", "NEGADO_LIVENESS", "NEGADO_MULTIPLOS", "BLOQUEADO")
NEGADOS = ("NEGADO_NIVEL", "NEGADO_DESCONHECIDO", "NEGADO_LIVENESS", "NEGADO_MULTIPLOS")

ROTULOS = {
    "CONCEDIDO": "Concedido",
    "NEGADO_NIVEL": "Nível insuficiente",
    "NEGADO_DESCONHECIDO": "Não cadastrado",
    "NEGADO_LIVENESS": "Prova de vida",
    "NEGADO_MULTIPLOS": "Mais de uma pessoa",
    "BLOQUEADO": "Bloqueio",
}

_SQL_EVENTOS = "SELECT id, data_hora, resultado, nivel_exigido, similaridade FROM acessos"
_DIAS_SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


@dataclass(frozen=True)
class Evento:
    id: int
    data_hora: str
    resultado: str
    nivel_exigido: int
    similaridade: float | None


def ler_eventos(caminho, desde: str | None = None, limite: int = 20000) -> list[Evento]:
    """Os `limite` eventos mais recentes (desde `desde`, se dado), em ordem crescente de id."""
    sql = _SQL_EVENTOS + (" WHERE data_hora >= ?" if desde else "") + " ORDER BY id DESC LIMIT ?"
    params = ((desde,) if desde else ()) + (int(limite),)
    linhas = leitura_ro.consultar(caminho, sql, params)
    eventos = [Evento(int(l["id"]), str(l["data_hora"]), str(l["resultado"]), int(l["nivel_exigido"]),
                      None if l["similaridade"] is None else float(l["similaridade"])) for l in linhas]
    eventos.reverse()
    return eventos


def _num(v: float) -> str:
    return f"{v:.3f}".replace(".", ",")


def _int(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def resumo(eventos: Sequence[Evento]) -> dict:
    por = {r: 0 for r in RESULTADOS}
    dias = set()
    for e in eventos:
        if e.resultado in por:
            por[e.resultado] += 1
        dias.add(e.data_hora[:10])
    return {
        "total": len(eventos),
        "por_resultado": por,
        "dias_distintos": len(dias),
        "primeiro": eventos[0].data_hora if eventos else None,
        "ultimo": eventos[-1].data_hora if eventos else None,
        "bloqueios": por["BLOQUEADO"],
        "negadas": sum(por[r] for r in NEGADOS),
    }


def folga(eventos: Sequence[Evento], limiar: float) -> dict:
    concedidas = [e.similaridade for e in eventos if e.resultado == "CONCEDIDO" and e.similaridade is not None]
    desconhecidas = [e.similaridade for e in eventos
                     if e.resultado == "NEGADO_DESCONHECIDO" and e.similaridade is not None]
    menor = min(concedidas) if concedidas else None
    maior = max(desconhecidas) if desconhecidas else None
    return {
        "menor_concedida": menor,
        "maior_desconhecida": maior,
        "concedidas_abaixo": sum(1 for s in concedidas if s < limiar),
        "folga_acima": None if menor is None else menor - limiar,
        "folga_abaixo": None if maior is None else limiar - maior,
    }


def manchete(res: dict, fol: dict, limiar: float) -> tuple[str, list[str]]:
    total = int(res.get("total", 0))
    if total == 0:
        return "Ainda não há tentativas registradas.", []
    autorizadas = res["por_resultado"]["CONCEDIDO"]
    tentativas = "tentativa" if total == 1 else "tentativas"
    aut = "autorizada" if autorizadas == 1 else "autorizadas"
    frase = f"{_int(total)} {tentativas}, {_int(autorizadas)} {aut}."
    dias = res["dias_distintos"]
    bloq = res["bloqueios"]
    leituras = [f"{dias} {'dia' if dias == 1 else 'dias'} com registro · "
                f"{_int(bloq)} {'bloqueio' if bloq == 1 else 'bloqueios'}"]
    abaixo = fol["concedidas_abaixo"]
    if abaixo == 0:
        leituras.append(f"Nenhuma autorização abaixo do limiar de {_num(limiar)}")
    else:
        leituras.append(f"{abaixo} {'autorização' if abaixo == 1 else 'autorizações'} abaixo do limiar de "
                        f"{_num(limiar)} (limiar mudou desde então?)")
    partes = []
    if fol["menor_concedida"] is not None:
        partes.append(f"Menor similaridade autorizada: {_num(fol['menor_concedida'])}")
    if fol["maior_desconhecida"] is not None:
        partes.append(f"maior não reconhecida: {_num(fol['maior_desconhecida'])}")
    if partes:
        texto = " · ".join(partes)
        leituras.append(texto[0].upper() + texto[1:])
    return frase, leituras


def dados_composicao(res: dict) -> dict:
    por = res.get("por_resultado", {r: 0 for r in RESULTADOS})
    negados = sorted(NEGADOS, key=lambda r: (-por.get(r, 0), NEGADOS.index(r)))
    cores = ["negado", "negado2", "negado3", "negado4"]
    series = [{"nome": ROTULOS["CONCEDIDO"], "cor": "concedido", "valores": [por.get("CONCEDIDO", 0)]}]
    series += [{"nome": ROTULOS[r], "cor": cores[i], "valores": [por.get(r, 0)]} for i, r in enumerate(negados)]
    series.append({"nome": ROTULOS["BLOQUEADO"], "cor": "bloqueio", "valores": [por.get("BLOQUEADO", 0)]})
    total = int(res.get("total", 0))
    return {
        "categorias": ["Tentativas"],
        "series": series,
        "orientacao": "h",
        "empilhado": True,
        "rotulosValor": False,
        "eixoX": {"min": 0, "max": max(1, total), "formato": "int"},
        "n": f"N = {_int(total)}",
        "resumo": " · ".join(f"{s['nome']} {s['valores'][0]}" for s in series),
        "vazio": "Nenhuma tentativa no período",
    }


def _hora_decimal(iso: str) -> float:
    return int(iso[11:13]) + int(iso[14:16]) / 60 + int(iso[17:19]) / 3600


def _texto_evento(e: Evento) -> str:
    partes = [e.data_hora[11:16], ROTULOS.get(e.resultado, e.resultado), f"nível {e.nivel_exigido}"]
    if e.similaridade is not None:
        partes.append(_num(e.similaridade))
    return " · ".join(partes)


def _tipo_fita(resultado: str) -> str:
    if resultado == "CONCEDIDO":
        return "concedido"
    return "bloqueio" if resultado == "BLOQUEADO" else "negado"


def dados_fita(eventos: Sequence[Evento], duracao_bloqueio_seg: float, max_faixas: int = 7) -> dict:
    """Uma faixa por dia com registro (os `max_faixas` mais recentes, do mais antigo ao mais novo)."""
    por_dia: dict[str, list[Evento]] = {}
    for e in eventos:
        if len(e.data_hora) >= 19:
            por_dia.setdefault(e.data_hora[:10], []).append(e)
    dias = sorted(por_dia)[-max_faixas:] if max_faixas > 0 else []
    faixas = []
    for dia in dias:
        try:
            d = datetime.fromisoformat(dia)
            rotulo = f"{_DIAS_SEMANA[d.weekday()]} {d:%d/%m}"
        except ValueError:
            rotulo = dia
        evs, intervalos = [], []
        for e in por_dia[dia]:
            try:
                t = _hora_decimal(e.data_hora)
            except ValueError:
                continue
            evs.append({"t": round(t, 5), "tipo": _tipo_fita(e.resultado), "id": e.id, "texto": _texto_evento(e)})
            if e.resultado == "BLOQUEADO":
                intervalos.append({"t0": round(t, 5), "t1": round(min(24.0, t + duracao_bloqueio_seg / 3600), 5)})
        faixas.append({"rotulo": rotulo, "eventos": evs, "intervalos": intervalos})
    n = sum(len(f["eventos"]) for f in faixas)
    return {
        "faixas": faixas,
        "eixoX": {"min": 0.0, "max": 24.0, "formato": "hora"},
        "n": f"N = {_int(n)} · {len(faixas)} {'dia' if len(faixas) == 1 else 'dias'}",
        "resumo": f"{n} tentativas em {len(faixas)} dias com registro",
        "vazio": "Nenhuma tentativa no período",
    }


def dados_espectro(eventos: Sequence[Evento], limiar: float, limiar_forte: float, faixas: int = 50) -> dict:
    bordas = [round(i / faixas, 6) for i in range(faixas + 1)]

    def contar(filtro) -> list[int]:
        c = [0] * faixas
        for e in eventos:
            if e.similaridade is None or not filtro(e):
                continue
            k = min(faixas - 1, max(0, int(e.similaridade * faixas)))
            c[k] += 1
        return c

    aut = contar(lambda e: e.resultado == "CONCEDIDO")
    neg = contar(lambda e: e.resultado in NEGADOS)
    nao_vazias = [v for v in aut + neg if v > 0]
    truncar = max(12, int(3 * statistics.median(nao_vazias))) if nao_vazias else None
    n_aut, n_neg = sum(aut), sum(neg)
    return {
        "bordas": bordas,
        "series": [{"nome": "Autorizadas", "cor": "concedido", "contagens": aut, "sentido": 1},
                   {"nome": "Negadas com similaridade", "cor": "negado", "contagens": neg, "sentido": -1}],
        "marcadoresV": [{"x": limiar, "rotulo": f"limiar em vigor {_num(limiar)}", "estilo": "vigor"},
                        {"x": limiar_forte, "rotulo": f"forte {_num(limiar_forte)}", "estilo": "nota"}],
        "truncarEm": truncar,
        "eixoX": {"min": 0.0, "max": 1.0, "formato": "0.00", "rotulo": "similaridade"},
        "n": f"N = {_int(n_aut)} autorizadas · {_int(n_neg)} negadas",
        "resumo": f"{n_aut} autorizadas e {n_neg} negadas com similaridade registrada",
        "vazio": "Nenhuma tentativa com similaridade no período",
    }


def ultimos(eventos: Sequence[Evento], referencia: datetime, minutos: int = 15) -> list[Evento]:
    corte = (referencia - timedelta(minutes=minutos)).isoformat(timespec="seconds")
    fim = referencia.isoformat(timespec="seconds")
    return [e for e in eventos if corte <= e.data_hora[:19] <= fim]
