"""Fase 5: interpretação do registro de decisões (incidentes).

Agrupa linhas do registro em fatos com nome (bloqueio por tentativas, tentativa acima do nível,
prova de vida não concluída com identidade forte, mais de uma pessoa). Função pura sobre o registro
lido em modo somente leitura: nada é gravado e o texto descreve um padrão, sem acusar ninguém e sem
nome de pessoa (o nome detectado, a mensagem e a evidência nunca são lidos).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from . import leitura_ro

TITULOS = {"bloqueio": "Bloqueio por tentativas", "acima_do_nivel": "Tentativa acima do nível",
           "prova_de_vida": "Prova de vida não concluída com identidade forte", "multiplos": "Mais de uma pessoa"}
TIPOS = tuple(TITULOS)
TIPOS_COM_PESSOA = ("acima_do_nivel", "prova_de_vida")
NEGACOES = ("NEGADO_NIVEL", "NEGADO_DESCONHECIDO", "NEGADO_LIVENESS", "NEGADO_MULTIPLOS")
VIZINHAS_PESSOA_SEG = 600.0
VIZINHAS_MULTIPLOS_SEG = 120.0
TEXTO_PROVA_DE_VIDA = "padrão compatível com foto ou vídeo apresentado, ou com desistência no desafio"


@dataclass(frozen=True)
class Linha:
    id: int
    data_hora: str
    resultado: str
    similaridade: float | None
    nivel_usuario: int | None
    nivel_exigido: int
    usuario_id: int | None


@dataclass(frozen=True)
class Incidente:
    chave: str                    # f"{tipo}:{ids[0]}-{ids[-1]}" (estável)
    tipo: str                     # "bloqueio" | "acima_do_nivel" | "prova_de_vida" | "multiplos"
    gravidade: str                # "alta" | "media"
    ids: tuple[int, ...]
    inicio: str
    fim: str
    usuario_id: int | None
    nivel_exigido: int
    resumo: str


def ler_linhas(caminho, desde: str | None = None) -> list[Linha]:
    sql = ("SELECT id, data_hora, resultado, similaridade, nivel_usuario, nivel_exigido, usuario_id FROM acessos"
           + (" WHERE data_hora >= ?" if desde else "") + " ORDER BY id")
    linhas = leitura_ro.consultar(caminho, sql, (desde,) if desde else ())
    return [Linha(int(l["id"]), str(l["data_hora"]), str(l["resultado"]),
                  None if l["similaridade"] is None else float(l["similaridade"]),
                  None if l["nivel_usuario"] is None else int(l["nivel_usuario"]), int(l["nivel_exigido"]),
                  None if l["usuario_id"] is None else int(l["usuario_id"])) for l in linhas]


def _segundos(iso: str) -> float | None:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (TypeError, ValueError):
        return None


def _duracao(seg: float) -> str:
    seg = max(0, int(round(seg)))
    if seg < 120:
        return f"{seg} s"
    minutos = seg // 60
    if minutos < 120:
        return f"{minutos} min"
    return f"{minutos // 60} h {minutos % 60:02d} min"


def _incidente(tipo: str, gravidade: str, grupo: list[Linha], usuario_id: int | None, resumo: str) -> Incidente:
    ids = tuple(sorted(l.id for l in grupo))
    ordenado = sorted(grupo, key=lambda l: l.id)
    return Incidente(chave=f"{tipo}:{ids[0]}-{ids[-1]}", tipo=tipo, gravidade=gravidade, ids=ids,
                     inicio=ordenado[0].data_hora, fim=ordenado[-1].data_hora, usuario_id=usuario_id,
                     nivel_exigido=max(l.nivel_exigido for l in grupo), resumo=resumo)


def _agrupar_por_pessoa(linhas: list[tuple[Linha, float]], vizinhas: float) -> list[list[Linha]]:
    """Grupos de linhas da mesma pessoa com menos de `vizinhas` segundos entre linhas vizinhas. Linha sem
    vínculo de usuário fica sozinha (duas nulas podem ser pessoas removidas diferentes)."""
    abertos: dict[int, tuple[list[Linha], float]] = {}
    grupos: list[list[Linha]] = []
    for linha, t in linhas:
        if linha.usuario_id is None:
            grupos.append([linha])
            continue
        atual = abertos.get(linha.usuario_id)
        if atual is not None and t - atual[1] < vizinhas:
            atual[0].append(linha)
            abertos[linha.usuario_id] = (atual[0], t)
        else:
            grupo = [linha]
            grupos.append(grupo)
            abertos[linha.usuario_id] = (grupo, t)
    return grupos


def detectar(linhas: Sequence[Linha], *, janela_seg: float, limiar_forte: float) -> list[Incidente]:
    ordenadas = sorted(linhas, key=lambda l: l.id)
    com_tempo = [(l, t) for l in ordenadas if (t := _segundos(l.data_hora)) is not None]
    incidentes: list[Incidente] = []

    # bloqueio: cada BLOQUEADO mais as negações anteriores dentro da janela, até o último CONCEDIDO ou BLOQUEADO
    for k, (linha, t) in enumerate(com_tempo):
        if linha.resultado != "BLOQUEADO":
            continue
        negacoes: list[tuple[Linha, float]] = []
        for anterior, ta in reversed(com_tempo[:k]):
            if anterior.resultado in ("CONCEDIDO", "BLOQUEADO") or t - ta > janela_seg:
                break
            if anterior.resultado in NEGACOES:
                negacoes.append((anterior, ta))
        n = len(negacoes)
        if n:
            resumo = f"{n} {'negação' if n == 1 else 'negações'} em {_duracao(t - negacoes[-1][1])} antes do bloqueio"
        else:
            resumo = "Bloqueio sem negação registrada na janela"
        incidentes.append(_incidente("bloqueio", "alta", [linha] + [l for l, _ in negacoes], None, resumo))

    # acima do nível e prova de vida: mesma pessoa, menos de 600 s entre vizinhas
    nivel = [(l, t) for l, t in com_tempo if l.resultado == "NEGADO_NIVEL"]
    for grupo in _agrupar_por_pessoa(nivel, VIZINHAS_PESSOA_SEG):
        n = len(grupo)
        exigido = max(l.nivel_exigido for l in grupo)
        da_pessoa = next((l.nivel_usuario for l in grupo if l.nivel_usuario is not None), None)
        quem = f"nível {da_pessoa}" if da_pessoa is not None else "nível da pessoa"
        resumo = (f"{n} {'tentativa' if n == 1 else 'tentativas'} em área de nível {exigido} com {quem}"
                  + (f" em {_duracao(_segundos(grupo[-1].data_hora) - _segundos(grupo[0].data_hora))}" if n > 1 else ""))
        incidentes.append(_incidente("acima_do_nivel", "alta" if n >= 3 else "media", grupo, grupo[0].usuario_id,
                                     resumo))
    vida = [(l, t) for l, t in com_tempo
            if l.resultado == "NEGADO_LIVENESS" and l.similaridade is not None and l.similaridade >= limiar_forte]
    for grupo in _agrupar_por_pessoa(vida, VIZINHAS_PESSOA_SEG):
        n = len(grupo)
        resumo = f"{n} {'tentativa' if n == 1 else 'tentativas'}: {TEXTO_PROVA_DE_VIDA}"
        incidentes.append(_incidente("prova_de_vida", "media", grupo, grupo[0].usuario_id, resumo))

    # mais de uma pessoa: menos de 120 s entre vizinhas
    grupo: list[Linha] = []
    ultimo = None
    for linha, t in com_tempo:
        if linha.resultado != "NEGADO_MULTIPLOS":
            continue
        if grupo and ultimo is not None and t - ultimo < VIZINHAS_MULTIPLOS_SEG:
            grupo.append(linha)
        else:
            if grupo:
                incidentes.append(_multiplos(grupo))
            grupo = [linha]
        ultimo = t
    if grupo:
        incidentes.append(_multiplos(grupo))

    incidentes.sort(key=lambda i: (i.inicio, i.ids[0]), reverse=True)
    return incidentes


def _multiplos(grupo: list[Linha]) -> Incidente:
    n = len(grupo)
    resumo = f"{n} {'tentativa' if n == 1 else 'tentativas'} com mais de um rosto diante do terminal"
    return _incidente("multiplos", "media", grupo, None, resumo)


def contexto(linhas: Sequence[Linha], incidente: Incidente, margem_seg: float = 120.0) -> list[Linha]:
    """Linhas do incidente e as vizinhas até `margem_seg` antes do início e depois do fim, em ordem de id."""
    t0, t1 = _segundos(incidente.inicio), _segundos(incidente.fim)
    ids = set(incidente.ids)
    saida = []
    for linha in sorted(linhas, key=lambda l: l.id):
        if linha.id in ids:
            saida.append(linha)
            continue
        t = _segundos(linha.data_hora)
        if t is not None and t0 is not None and t1 is not None and t0 - margem_seg <= t <= t1 + margem_seg:
            saida.append(linha)
    return saida


def regras_em_texto(janela_seg: float, max_falhas: int, limiar_forte: float) -> list[dict]:
    forte = f"{limiar_forte:.2f}".replace(".", ",")
    janela = f"{janela_seg:.0f} s"
    return [
        {"tipo": "bloqueio", "titulo": TITULOS["bloqueio"],
         "regra": f"Cada bloqueio do terminal, com as negações dos {janela} anteriores (o terminal bloqueia após "
                  f"{max_falhas} negações nessa janela), voltando até o último acesso concedido ou bloqueio."},
        {"tipo": "acima_do_nivel", "titulo": TITULOS["acima_do_nivel"],
         "regra": "Negações por nível insuficiente da mesma pessoa, com menos de 10 min entre uma e a próxima. "
                  "Três ou mais é gravidade alta."},
        {"tipo": "prova_de_vida", "titulo": TITULOS["prova_de_vida"],
         "regra": f"Prova de vida não concluída com similaridade de pelo menos {forte} (identidade forte), da mesma "
                  "pessoa, com menos de 10 min entre uma e a próxima."},
        {"tipo": "multiplos", "titulo": TITULOS["multiplos"],
         "regra": "Negações por mais de um rosto diante do terminal, com menos de 2 min entre uma e a próxima."},
    ]
