"""Fase 5: interpretação do registro de decisões (regras e selo).

Confere, por contagem, que as regras do backend valem no registro de acessos (13 regras, cada uma com
o ponto do código que a garante) e calcula um selo encadeado (SHA-256) que detecta alteração e remoção
de registros anteriores a ele. Só lê o banco (por `leitura_ro`): não corrige nada. O caminho do arquivo
de evidência nunca sai deste módulo; só o nome do arquivo é examinado.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import leitura_ro
from .base_demo import MARCA_MENSAGEM

RESULTADOS = ("CONCEDIDO", "NEGADO_NIVEL", "NEGADO_DESCONHECIDO", "NEGADO_LIVENESS", "NEGADO_MULTIPLOS", "BLOQUEADO")
COLUNAS_SELO = ("id", "data_hora", "nome_detectado", "nivel_usuario", "nivel_exigido", "area", "similaridade",
                "resultado", "mensagem", "evidencia")
OBSERVACAO_SELO = ("Selo consultivo: detecta alteração e remoção de registros anteriores a este selo. Não cobre o "
                   "vínculo com o usuário, que a remoção de um usuário esvazia.")
MAX_EXEMPLOS = 20
TOLERANCIA_EVIDENCIA_SEG = 2.0
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_RE_EVIDENCIA = re.compile(r"^(\d{8}_\d{6})_([A-Z_]+)\.jpg$")


@dataclass(frozen=True)
class Regra:
    id: str
    titulo: str
    consultiva: bool
    garantia: str        # "arquivo.py:linha" do backend que garante


@dataclass(frozen=True)
class ResultadoRegra:
    regra: Regra
    violacoes: int
    ids: tuple[int, ...]  # até 20 ids de exemplo
    observacao: str


@dataclass(frozen=True)
class Selo:
    sha256: str
    registros: int
    ultimo_id: int
    gerado_em: str


REGRAS: tuple[Regra, ...] = (
    Regra("I1", "Acesso concedido só com nível suficiente", False, "fase5_reconhecimento.py:132"),
    Regra("I2", "Acesso concedido com similaridade no limiar em vigor", True, "fase5_reconhecimento.py:118, 126"),
    Regra("I3", "Acesso concedido sempre identifica a pessoa", False, "autenticacao.py:73-79"),
    Regra("I4", "Acesso concedido não guarda evidência", False, "autenticacao.py:75"),
    Regra("I5", "Negação sempre guarda evidência", False, "autenticacao.py:75-76"),
    Regra("I6", "Rosto não cadastrado fica abaixo do limiar em vigor", True, "fase5_reconhecimento.py:118-119"),
    Regra("I7", "Negação por nível só com nível menor que o exigido", False, "fase5_reconhecimento.py:132-141"),
    Regra("I8", "A hora não regride na ordem dos registros", True, "banco.py:91-92"),
    Regra("I9", "Bloqueio vem logo depois de uma negação", False, "autenticacao.py:116-121"),
    Regra("I10", "Resultado, nível e data em formato válido", False, "fase5_reconhecimento.py:24-30, banco.py:92"),
    Regra("I11", "Numeração contínua, sem remoção de registros", False, "banco.py:174-185"),
    Regra("I12", "Negações seguidas na janela levam ao bloqueio", True, "liveness.py:95-104"),
    Regra("I13", "Arquivo de evidência bate com o resultado e a hora", False, "autenticacao.py:63-68"),
)

_SQL_REGRAS = ("SELECT id, data_hora, (nome_detectado IS NOT NULL) AS tem_nome, nivel_usuario, nivel_exigido, "
               "similaridade, resultado, evidencia, (mensagem IS NOT NULL AND instr(mensagem, ?) = 1) AS ficticia "
               "FROM acessos WHERE id > ? ORDER BY id LIMIT ?")
_SQL_SELO = "SELECT " + ", ".join(COLUNAS_SELO) + " FROM acessos WHERE id > ? ORDER BY id LIMIT ?"


def _num(v: float, casas: int = 3) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def _momento(iso) -> datetime | None:
    if not isinstance(iso, str) or not _RE_DATA.match(iso):
        return None
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


def _linhas_regras(caminho, tamanho: int = 2000):
    ultimo = 0
    while True:
        linhas = leitura_ro.consultar(caminho, _SQL_REGRAS, (MARCA_MENSAGEM, ultimo, tamanho))
        if not linhas:
            return
        yield linhas
        if len(linhas) < tamanho:
            return
        ultimo = linhas[-1]["id"]


def _sequencia(caminho) -> tuple[int, int, int]:
    """(maior id, quantidade de linhas, valor de sqlite_sequence para acessos; 0 se não houver)."""
    maximo, n = leitura_ro.consultar(caminho, "SELECT COALESCE(MAX(id), 0), COUNT(*) FROM acessos")[0]
    existe = leitura_ro.consultar(
        caminho, "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'")
    seq = 0
    if existe:
        linha = leitura_ro.consultar(caminho, "SELECT seq FROM sqlite_sequence WHERE name = 'acessos'")
        seq = int(linha[0][0]) if linha else 0
    return int(maximo), int(n), seq


def conferir(caminho, *, limiar: float, janela_seg: float, max_falhas: int, demonstracao: bool = False,
             sinal=None) -> list[ResultadoRegra]:
    ids: dict[str, list[int]] = {r.id: [] for r in REGRAS}
    contagem: dict[str, int] = {r.id: 0 for r in REGRAS}

    def acusar(regra: str, ident: int) -> None:
        contagem[regra] += 1
        if len(ids[regra]) < MAX_EXEMPLOS:
            ids[regra].append(int(ident))

    anterior = None                 # linha anterior (para I9)
    hora_anterior: str | None = None
    lacunas, esperado = 0, 1
    falhas: list[datetime] = []
    pendente_bloqueio = None        # id da negação que completou max_falhas sem bloqueio ainda
    for fatia in _linhas_regras(caminho):
        if sinal is not None:
            sinal.conferir()
        for l in fatia:
            ident, res, dh = int(l["id"]), l["resultado"], l["data_hora"]
            sim, nu, ne = l["similaridade"], l["nivel_usuario"], l["nivel_exigido"]
            negacao = isinstance(res, str) and res.startswith("NEGADO_")
            momento = _momento(dh)
            # I11: lacunas de id
            if ident > esperado:                # a contagem de I11 sai no fim, com o total de números faltando
                lacunas += ident - esperado
                if len(ids["I11"]) < MAX_EXEMPLOS:
                    ids["I11"].append(ident)
            esperado = ident + 1
            if res == "CONCEDIDO":
                if nu is None or ne is None or nu < ne:
                    acusar("I1", ident)
                if sim is None or sim < limiar:
                    acusar("I2", ident)
                if not l["tem_nome"]:
                    acusar("I3", ident)
                if l["evidencia"] is not None:
                    acusar("I4", ident)
            if negacao and l["evidencia"] is None and not (demonstracao and l["ficticia"]):
                acusar("I5", ident)
            if res == "NEGADO_DESCONHECIDO" and sim is not None and sim >= limiar:
                acusar("I6", ident)
            if res == "NEGADO_NIVEL" and nu is not None and ne is not None and nu >= ne:
                acusar("I7", ident)
            if isinstance(dh, str) and hora_anterior is not None and dh < hora_anterior:
                acusar("I8", ident)
            if isinstance(dh, str):
                hora_anterior = dh
            if res == "BLOQUEADO" and (anterior is None or not str(anterior["resultado"]).startswith("NEGADO_")):
                acusar("I9", ident)
            if res not in RESULTADOS or ne not in (1, 2, 3) or momento is None:
                acusar("I10", ident)
            # I12: o contador do terminal, refeito sobre o registro
            if pendente_bloqueio is not None:
                if res != "BLOQUEADO":
                    acusar("I12", pendente_bloqueio)
                pendente_bloqueio = None
            if res in ("CONCEDIDO", "BLOQUEADO"):
                falhas = []
            elif negacao and momento is not None:
                falhas = [t for t in falhas if (momento - t).total_seconds() <= janela_seg] + [momento]
                if len(falhas) >= max_falhas:
                    pendente_bloqueio = ident
                    falhas = []
            # I13: só o nome do arquivo de evidência
            if l["evidencia"] is not None:
                nome = Path(str(l["evidencia"])).name
                m = _RE_EVIDENCIA.match(nome)
                ok = False
                if m and m.group(2) == res and momento is not None:
                    try:
                        hora_nome = datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
                        ok = abs((hora_nome - momento).total_seconds()) <= TOLERANCIA_EVIDENCIA_SEG
                    except ValueError:
                        ok = False
                if not ok:
                    acusar("I13", ident)
            anterior = l
    if pendente_bloqueio is not None:
        acusar("I12", pendente_bloqueio)

    maximo, _, seq = _sequencia(caminho)
    contagem["I11"] = lacunas + (1 if seq != maximo else 0)
    if seq != maximo and len(ids["I11"]) < MAX_EXEMPLOS and seq > 0:
        ids["I11"].append(seq)

    observacoes = {
        "I2": f"Usa o limiar em vigor hoje ({_num(limiar)}): um acesso antigo pode ter vindo de outro limiar.",
        "I5": "As linhas fictícias da base de demonstração não contam." if demonstracao else "",
        "I6": f"Usa o limiar em vigor hoje ({_num(limiar)}).",
        "I8": "A hora vem do relógio local: um ajuste de relógio ou de fuso produz a regressão sem adulteração.",
        "I11": f"Sequência {seq}, maior número {maximo}, {lacunas} faltando na numeração.",
        "I12": (f"{max_falhas} negações em {janela_seg:.0f} s. O contador fica em memória: reiniciar o aplicativo o "
                "zera, e a linha de comando grava sem bloquear."),
        "I13": "Só o nome do arquivo é examinado; o caminho não sai desta conferência.",
    }
    return [ResultadoRegra(r, contagem[r.id], tuple(ids[r.id]), observacoes.get(r.id, "")) for r in REGRAS]


# ---------------------------------------------------------------------------- selo encadeado
def _passo(h: bytes, linha) -> bytes:
    dados = {c: linha[c] for c in COLUNAS_SELO}
    texto = json.dumps(dados, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(h + texto.encode("utf-8")).digest()


def _cadeia(caminho, alvos: set[int], ate_id: int | None, sinal=None) -> tuple[bytes, int, int, dict[int, tuple[str, int]]]:
    """Percorre o registro em fatias. Devolve (hash final, registros, último id, {alvo: (hash, registros)})."""
    h, n, ultimo = bytes(32), 0, 0
    marcados: dict[int, tuple[str, int]] = {}
    pendentes = sorted(alvos)
    for fatia in leitura_ro.fatias(caminho, _SQL_SELO):
        if sinal is not None:
            sinal.conferir()
        for linha in fatia:
            ident = int(linha["id"])
            if ate_id is not None and ident > ate_id:
                break
            while pendentes and pendentes[0] < ident:
                marcados[pendentes.pop(0)] = (h.hex(), n)
            h, n, ultimo = _passo(h, linha), n + 1, ident
        else:
            continue
        break
    for alvo in pendentes:
        marcados[alvo] = (h.hex(), n)
    return h, n, ultimo, marcados


def selar(caminho, ate_id: int | None = None, sinal=None) -> Selo:
    h, n, ultimo, _ = _cadeia(caminho, set(), ate_id, sinal)
    return Selo(sha256=h.hex(), registros=n, ultimo_id=ultimo, gerado_em=datetime.now().isoformat(timespec="seconds"))


def gravar_selo(selo: Selo, pasta: Path, *, base: str, demonstracao: bool) -> Path:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    try:
        carimbo = datetime.fromisoformat(selo.gerado_em).strftime("%Y%m%d_%H%M%S")
    except ValueError:
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = pasta / f"selo_{carimbo}.json"
    k = 2
    while destino.exists():
        destino = pasta / f"selo_{carimbo}_{k}.json"
        k += 1
    conteudo = {"sha256": selo.sha256, "registros": selo.registros, "ultimo_id": selo.ultimo_id,
                "gerado_em": selo.gerado_em, "base": base, "demonstracao": bool(demonstracao),
                "colunas": list(COLUNAS_SELO), "observacao": OBSERVACAO_SELO}
    provisorio = destino.with_suffix(".json.tmp")
    provisorio.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8")
    provisorio.replace(destino)
    return destino


def conferir_selos(caminho, pasta: Path, sinal=None) -> dict:
    pasta = Path(pasta)
    gravados = []
    for arquivo in sorted(pasta.glob("selo_*.json")) if pasta.is_dir() else []:
        try:
            d = json.loads(arquivo.read_text(encoding="utf-8"))
            gravados.append((arquivo.name, str(d["sha256"]), int(d["registros"]), int(d["ultimo_id"]),
                             str(d.get("gerado_em", ""))))
        except (OSError, ValueError, KeyError, TypeError):
            gravados.append((arquivo.name, None, -1, -1, ""))
    if not gravados:
        return {"total": 0, "conferem": 0, "divergentes": [], "ultimo": None}
    alvos = {g[3] for g in gravados if g[1] is not None}
    _, _, _, marcados = _cadeia(caminho, alvos, max(alvos) if alvos else 0, sinal)
    conferem, divergentes, situacao = 0, [], {}
    for nome, sha, registros, ultimo_id, _ in gravados:
        ok = sha is not None and marcados.get(ultimo_id) == (sha, registros)
        situacao[nome] = ok
        if ok:
            conferem += 1
        else:
            divergentes.append({"arquivo": nome, "ultimo_id": ultimo_id if sha is not None else None})
    recente = max(gravados, key=lambda g: (g[4], g[0]))
    ultimo = {"arquivo": recente[0], "ultimo_id": recente[3], "registros": recente[2], "gerado_em": recente[4],
              "confere": situacao[recente[0]]}
    return {"total": len(gravados), "conferem": conferem, "divergentes": divergentes, "ultimo": ultimo}


def estrutura(caminho) -> dict:
    maximo, n, seq = _sequencia(caminho)
    try:
        modo = str(leitura_ro.consultar(caminho, "PRAGMA journal_mode")[0][0])
    except Exception:  # noqa: BLE001
        modo = "–"
    return {"lacunas_id": max(0, maximo - n), "seq_menos_max": seq - maximo, "modo_diario": modo}
