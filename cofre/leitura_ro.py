"""Fase 5 (reconhecimento e interpretação): leitura do registro e da galeria, sem escrita.

Toda análise nova lê o banco por aqui. A conexão é aberta em modo somente leitura (`mode=ro` na URI
do SQLite, mais `PRAGMA query_only`), devolve o resultado inteiro de uma vez e fecha em seguida:
nenhum cursor fica pendurado atrasando a gravação do terminal, e nenhuma função deste módulo
consegue inserir, alterar ou apagar uma linha. Banco em memória ou arquivo ausente não é aberto
(e nunca é criado): levanta `BancoIndisponivel`.

Os vetores da galeria saem daqui só como matriz NumPy para cálculo; nunca vão para a tela nem para arquivo.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import numpy as np

DIMENSAO = 128      # tamanho do vetor gravado pelo cadastro (float32)


class BancoIndisponivel(RuntimeError):
    """Não há arquivo de banco para ler (banco em memória ou caminho inexistente)."""


def abrir(caminho: str | Path, timeout: float = 2.0) -> sqlite3.Connection:
    """Conexão somente leitura com o arquivo do banco. Quem abre fecha, na mesma thread."""
    if str(caminho) == ":memory:":
        raise BancoIndisponivel("Banco em memória: a análise precisa de um banco em arquivo.")
    arquivo = Path(caminho).resolve()
    if not arquivo.is_file():
        raise BancoIndisponivel(f"Banco não encontrado: {arquivo}")
    # as_uri() escapa o caminho: um "?", "#" ou "%" no nome de uma pasta não quebra a URI
    con = sqlite3.connect(arquivo.as_uri() + "?mode=ro", uri=True, timeout=timeout)
    try:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only = ON")
    except Exception:
        con.close()
        raise
    return con


def consultar(caminho: str | Path, sql: str, params: Sequence = ()) -> list[sqlite3.Row]:
    """Abre, executa uma consulta, lê todas as linhas e fecha."""
    con = abrir(caminho)
    try:
        return con.execute(sql, tuple(params)).fetchall()
    finally:
        con.close()


def fatias(caminho: str | Path, sql_com_id: str, tamanho: int = 2000) -> Iterator[list[sqlite3.Row]]:
    """Percorre uma tabela grande em pedaços, com uma conexão por pedaço e nenhum cursor aberto entre eles.

    `sql_com_id` seleciona a coluna `id` e termina em `WHERE id > ? ORDER BY id LIMIT ?`: os dois
    parâmetros são o último `id` já entregue e o tamanho da fatia."""
    ultimo = 0
    while True:
        linhas = consultar(caminho, sql_com_id, (ultimo, tamanho))
        if not linhas:
            return
        yield linhas
        if len(linhas) < tamanho:
            return
        ultimo = linhas[-1]["id"]


def eh_base_demonstracao(caminho: str | Path) -> bool:
    """True só se o arquivo tem a tabela `demonstracao` e a identificação gravada pelo gerador
    (`PRAGMA application_id`). Qualquer erro vira False. Espera no máximo 0,2 s por uma trava do
    banco: é a única leitura que o aplicativo faz na thread da interface."""
    try:
        from . import base_demo     # importado aqui: `base_demo` importa este módulo
        con = abrir(caminho, timeout=0.2)
        try:
            identificacao = con.execute("PRAGMA application_id").fetchone()[0]
            tabela = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'demonstracao'").fetchone()
        finally:
            con.close()
        return identificacao == base_demo.APPLICATION_ID and tabela is not None
    except Exception:  # noqa: BLE001
        return False


@dataclass(frozen=True)
class GaleriaRO:
    """Galeria lida do banco, na ordem `usuario_id`, `id` da amostra."""

    donos: np.ndarray            # int64 (N,): usuario_id de cada amostra
    matriz: np.ndarray           # float32 (N, 128): vetores gravados (nunca sai do Python)
    amostras: np.ndarray         # int64 (N,): número da amostra dentro da pessoa, começando em 1
    niveis: dict[int, int]       # usuario_id -> nível
    inativos: int                # pessoas inativas deixadas de fora


def galeria(caminho: str | Path, apenas_ativos: bool = True) -> GaleriaRO:
    """Todas as amostras cadastradas como uma matriz. Com `apenas_ativos`, é a mesma galeria que o
    terminal compara (só pessoas ativas); a ordem aqui é por pessoa e por amostra."""
    filtro = "WHERE u.ativo = 1 " if apenas_ativos else ""
    con = abrir(caminho)
    try:
        linhas = con.execute(
            "SELECT a.usuario_id, a.embedding, u.nivel FROM amostras a JOIN usuarios u ON u.id = a.usuario_id "
            + filtro + "ORDER BY a.usuario_id, a.id").fetchall()
        inativos = con.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = 0").fetchone()[0] if apenas_ativos else 0
    finally:
        con.close()
    if any(len(linha["embedding"]) != DIMENSAO * 4 for linha in linhas):
        raise ValueError(f"Há amostra gravada com tamanho diferente de {DIMENSAO} valores float32.")
    donos = np.array([linha["usuario_id"] for linha in linhas], dtype=np.int64)
    bruto = b"".join(linha["embedding"] for linha in linhas)
    matriz = np.frombuffer(bruto, dtype=np.float32).reshape(-1, DIMENSAO).copy()
    _, inicio, inverso = np.unique(donos, return_index=True, return_inverse=True)
    amostras = (np.arange(donos.shape[0]) - inicio[inverso] + 1).astype(np.int64)
    niveis = {int(linha["usuario_id"]): int(linha["nivel"]) for linha in linhas}
    return GaleriaRO(donos=donos, matriz=matriz, amostras=amostras, niveis=niveis, inativos=int(inativos))


def nomes(caminho: str | Path) -> dict[int, str]:
    """usuario_id -> nome. Só `vm_privacidade.rotulos_para` chama, dentro de um trabalho em segundo
    plano e com a chave "Mostrar nomes" ligada."""
    linhas = consultar(caminho, "SELECT id, nome FROM usuarios ORDER BY id")
    return {int(linha["id"]): linha["nome"] for linha in linhas}


def ids_usuarios(caminho: str | Path) -> list[int]:
    """Ids de todas as pessoas cadastradas (ativas e inativas), em ordem crescente."""
    return [int(linha["id"]) for linha in consultar(caminho, "SELECT id FROM usuarios ORDER BY id")]


def letras(indice: int) -> str:
    """Letras de uma posição, como as colunas de uma planilha: 0 -> "A", 25 -> "Z", 26 -> "AA"."""
    texto = ""
    indice += 1
    while indice > 0:
        indice, resto = divmod(indice - 1, 26)
        texto = chr(ord("A") + resto) + texto
    return texto


def rotulos_anonimos(ids: Iterable[int]) -> dict[int, str]:
    """Rótulo estável e sem nome para cada pessoa: os ids em ordem crescente viram "Pessoa A",
    "Pessoa B", ..., "Pessoa Z", "Pessoa AA". Função pura."""
    return {uid: f"Pessoa {letras(i)}" for i, uid in enumerate(sorted({int(u) for u in ids}))}
