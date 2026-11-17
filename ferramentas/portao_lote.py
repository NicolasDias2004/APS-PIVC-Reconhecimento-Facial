#!/usr/bin/env python3
"""Portão dos lotes da versão 2: confere, com um comando, se um lote pode ser entregue.

Andaime de construção (fica fora da listagem de código; o dono pode apagar depois da entrega).
Uso:
  python ferramentas/portao_lote.py L4                  portão de um lote paralelo (L1 a L8, e L5B)
  python ferramentas/portao_lote.py L0                  portão da fundação
  python ferramentas/portao_lote.py INT                 portão da integração
  python ferramentas/portao_lote.py --selar-fundacao    grava fundacao_sha256 (último passo do Lote 0)

Códigos de saída: 0 = passou; 1 = falhou; 3 = pendente (só falha alheia nos testes antigos).
Só usa a biblioteca padrão, não importa Qt nem `cofre`, e do git só usa `status`.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFESTO_LOTES = "tests/v2_lotes.json"
MANIFESTO_CONGELADOS = "tests/v2_congelados.json"
LOTES_PARALELOS = ("L1", "L2", "L3", "L4", "L5", "L5B", "L6", "L7", "L8")
LOTES = ("L0", *LOTES_PARALELOS, "INT")
CAMINHO_TRAVA = os.path.join(tempfile.gettempdir(), "cofre-v2-portao.lock")
ESPERA_REPETICAO_S = 60.0
TETO_SUITE_S = 240.0
PASSOU, FALHOU, PENDENTE = 0, 1, 3
EXTENSOES_CITAVEIS = (".py", ".qml", ".js")
_CARACTERES_DE_NOME = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"


# ------------------------------------------------------------------ manifestos e arquivos

def ler_json(raiz: str, caminho: str) -> dict:
    with open(os.path.join(raiz, caminho), encoding="utf-8") as arq:
        return json.load(arq)


def sha256_de(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as arq:
        for bloco in iter(lambda: arq.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def testes_antigos(congelados: dict) -> list[str]:
    """Os arquivos `tests/test_*.py` do manifesto de congelados (os testes da versão 1)."""
    return sorted(c for c in congelados["arquivos"] if _e_arquivo_de_teste(c))


def testes_do_lote(lista: list[str]) -> list[str]:
    return sorted(c for c in lista if _e_arquivo_de_teste(c))


def _e_arquivo_de_teste(caminho: str) -> bool:
    pasta, nome = os.path.split(caminho)
    return pasta == "tests" and nome.startswith("test_") and nome.endswith(".py")


def conferir_manifesto(lista: list[str], congelados: dict, raiz: str) -> list[str]:
    """Passo 1: todo arquivo da lista existe e nenhum está no manifesto de congelados."""
    problemas = [f"{c}: não existe" for c in lista if not os.path.isfile(os.path.join(raiz, c))]
    problemas += [f"{c}: está no manifesto de congelados" for c in lista if c in congelados["arquivos"]]
    return problemas


def arquivos_da_fundacao(lotes: dict) -> list[str]:
    """Os arquivos de L0 que não pertencem a nenhum lote paralelo, menos o próprio manifesto dos lotes."""
    paralelos = {c for chave in LOTES_PARALELOS for c in lotes.get(chave, [])}
    return [c for c in lotes["L0"] if c not in paralelos and c != MANIFESTO_LOTES]


def conferir_fundacao(fundacao: dict, raiz: str) -> list[str]:
    """Passo 2: os arquivos selados cujo SHA-256 não confere (ou que sumiram)."""
    alterados = []
    for caminho, esperado in sorted(fundacao.items()):
        arquivo = os.path.join(raiz, caminho)
        if not os.path.isfile(arquivo):
            alterados.append(f"{caminho} (ausente)")
        elif sha256_de(arquivo) != esperado:
            alterados.append(caminho)
    return alterados


def selar_fundacao(raiz: str = RAIZ, saida=sys.stdout) -> int:
    """Grava `fundacao_sha256` no manifesto dos lotes (escrita atômica). Recusa se faltar arquivo."""
    manifesto = ler_json(raiz, MANIFESTO_LOTES)
    caminhos = arquivos_da_fundacao(manifesto["lotes"])
    faltando = [c for c in caminhos if not os.path.isfile(os.path.join(raiz, c))]
    if faltando:
        _escrever(saida, "SELAR: recusado, arquivos da fundação ausentes: " + ", ".join(faltando))
        return FALHOU
    manifesto["fundacao_sha256"] = {c: sha256_de(os.path.join(raiz, c)) for c in caminhos}
    destino = os.path.join(raiz, MANIFESTO_LOTES)
    fd, provisorio = tempfile.mkstemp(prefix=".v2_lotes.", suffix=".json", dir=os.path.dirname(destino))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arq:
            arq.write(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n")
        os.replace(provisorio, destino)
    finally:
        if os.path.exists(provisorio):
            os.unlink(provisorio)
    _escrever(saida, f"SELAR: {len(caminhos)} arquivos da fundação selados em {MANIFESTO_LOTES}")
    return PASSOU


# ------------------------------------------------------------------ git status

def caminhos_do_status(linhas: list[str]) -> list[str]:
    """Caminhos de `git status --short` (formato XY caminho; renomeação "a -> b" vale pelo destino)."""
    caminhos = []
    for linha in linhas:
        if len(linha) < 4:
            continue
        caminho = linha[3:]
        if " -> " in caminho:
            caminho = caminho.split(" -> ")[-1]
        caminhos.append(_sem_aspas(caminho))
    return caminhos


def _sem_aspas(caminho: str) -> str:
    """Desfaz as aspas que o git põe em caminho com espaço, aspas ou barra invertida."""
    if len(caminho) < 2 or not (caminho.startswith('"') and caminho.endswith('"')):
        return caminho
    corpo, bytes_, i = caminho[1:-1], bytearray(), 0
    escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
    while i < len(corpo):
        c = corpo[i]
        if c == "\\" and i + 1 < len(corpo):
            seguinte = corpo[i + 1]
            if seguinte in escapes:
                bytes_ += escapes[seguinte].encode()
                i += 2
                continue
            if corpo[i + 1:i + 4].isdigit():
                bytes_.append(int(corpo[i + 1:i + 4], 8))
                i += 4
                continue
        bytes_ += c.encode()
        i += 1
    return bytes_.decode("utf-8", errors="replace")


def sobras(caminhos: list[str], permitidos: set[str]) -> list[str]:
    """O que aparece no `git status` e não está na lista permitida."""
    return sorted(c for c in caminhos if c not in permitidos)


def git_status(raiz: str, argumentos: list[str]) -> list[str]:
    comando = ["git", "-c", "core.quotePath=false", "status", "--short", *argumentos]
    feito = subprocess.run(comando, cwd=raiz, capture_output=True, text=True, check=True)
    return [linha for linha in feito.stdout.splitlines() if linha.strip()]


# ------------------------------------------------------------------ saída do pytest

def secoes_do_pytest(saida: str) -> list[tuple[str, str]]:
    """Seções de falha e erro (cabeçalho "____ nome ____" e o corpo até o próximo cabeçalho)."""
    secoes: list[tuple[str, list[str]]] = []
    for linha in saida.splitlines():
        limpa = linha.strip()
        if len(limpa) > 6 and limpa.startswith("___") and limpa.endswith("___") and limpa.strip("_ "):
            secoes.append((limpa.strip("_ "), []))
        elif limpa.startswith("=") and limpa.endswith("=") and len(limpa) > 6:
            if secoes and secoes[-1][0] != "":
                secoes.append(("", []))      # separador "=== ... ===" fecha a seção corrente
        elif secoes:
            secoes[-1][1].append(linha)
    return [(cabecalho, "\n".join(corpo)) for cabecalho, corpo in secoes if cabecalho]


def falhas_do_pytest(saida: str) -> list[tuple[str, str]]:
    """Cada teste que falhou ou deu erro, com o texto que a saída traz sobre ele (resumo + seção)."""
    resumo: list[tuple[str, str]] = []
    for linha in saida.splitlines():
        for prefixo in ("FAILED ", "ERROR "):
            if linha.startswith(prefixo):
                no = linha[len(prefixo):].split(" - ", 1)[0].strip()
                resumo.append((no, linha))
    secoes = secoes_do_pytest(saida)
    falhas = []
    for no, linha in resumo:
        arquivo, _, resto = no.partition("::")
        curto = resto.replace("::", ".")
        textos = [linha]
        for cabecalho, corpo in secoes:
            if (curto and (cabecalho == curto or cabecalho.endswith(" of " + curto))) or \
                    (not curto and cabecalho == "ERROR collecting " + arquivo):
                textos.append(corpo)
        falhas.append((no, "\n".join(textos)))
    return falhas


def cita(texto: str, caminho: str) -> bool:
    """O texto cita o arquivo: pelo caminho relativo (também dentro do absoluto e da URL file://) ou,
    para .py, pelo nome do módulo com pontos. A ocorrência precisa terminar em fronteira de nome."""
    termos = [caminho]
    if caminho.endswith(".py"):
        termos.append(caminho[:-3].replace("/", "."))
    for termo in termos:
        inicio = texto.find(termo)
        while inicio >= 0:
            fim = inicio + len(termo)
            antes = texto[inicio - 1] if inicio > 0 else " "
            depois = texto[fim] if fim < len(texto) else " "
            if antes not in _CARACTERES_DE_NOME and depois not in _CARACTERES_DE_NOME:
                return True
            inicio = texto.find(termo, inicio + 1)
    return False


def arquivos_citados(texto: str, raiz: str) -> list[str]:
    """Caminhos relativos de arquivos de código do repositório citados no texto: pelo caminho relativo
    (traceback do pytest), absoluto ou em URL file:// (aviso de QML), com ou sem ":linha" no fim. Fica de
    fora o que está fora da raiz e o que começa com ponto (o ambiente virtual)."""
    prefixo = raiz.rstrip("/") + "/"
    for separador in "\t\r\n\"'(),;<>[]{}":
        texto = texto.replace(separador, " ")
    achados: set[str] = set()
    for pedaco in texto.split(" "):
        if pedaco.startswith("file://"):
            pedaco = pedaco[len("file://"):]
        if pedaco.startswith(prefixo):
            pedaco = pedaco[len(prefixo):]
        caminho = pedaco.split(":", 1)[0]
        if "/" in caminho and caminho.endswith(EXTENSOES_CITAVEIS) and not caminho.startswith((".", "/")):
            achados.add(caminho)
    return sorted(achados)


def classificar_falhas(saida: str, lista_do_lote: list[str], congelados: dict,
                       raiz: str) -> tuple[list[str], list[str], list[str]]:
    """Separa falhas próprias (a saída do teste cita arquivo do lote) de alheias. Devolve
    (próprias, alheias, arquivos citados pelas alheias). Teste que falhou sem aparecer na saída
    (processo abortado, erro interno) conta como próprio: não há como inocentar o lote."""
    proprias, alheias, citados = [], [], set()
    falhas = falhas_do_pytest(saida)
    if not falhas:
        return ["(nenhum teste identificado na saída do pytest)"], [], []
    for no, texto in falhas:
        if any(cita(texto, c) for c in lista_do_lote):
            proprias.append(no)
        else:
            alheias.append(no)
            novos = [c for c in arquivos_citados(texto, raiz) if c not in congelados["arquivos"]]
            citados.update(novos or [no.split("::")[0]])
    return proprias, alheias, sorted(citados)


def resumo_do_pytest(saida: str) -> str:
    """A linha final do pytest (contagem e tempo), sem os sinais de igual."""
    palavras = ("passed", "failed", "error", "skipped", "no tests ran", "deselected")
    for linha in reversed(saida.splitlines()):
        limpa = linha.strip().strip("=").strip()
        if " in " in limpa and any(p in limpa for p in palavras):
            return limpa
    return "(sem linha de resumo do pytest)"


# ------------------------------------------------------------------ execução

class Resultado:
    """O que uma execução do pytest devolveu: código, saída completa e duração."""

    def __init__(self, codigo: int, saida: str, segundos: float):
        self.codigo = codigo
        self.saida = saida
        self.segundos = segundos

    @property
    def ok(self) -> bool:
        return self.codigo == 0


def ambiente_pytest(lote: str | None) -> dict[str, str]:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_QUICK_BACKEND"] = "software"
    env.pop("COFRE_V2_LOTE", None)
    if lote is not None:
        env["COFRE_V2_LOTE"] = lote
    return env


def comando_pytest(argumentos: list[str]) -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *argumentos]


def rodar_pytest(argumentos: list[str], raiz: str, lote_estatico: str | None = None,
                 saida=sys.stdout) -> Resultado:
    """Roda o pytest a partir da raiz, repassando a saída linha a linha, e guarda o texto."""
    inicio = time.monotonic()
    processo = subprocess.Popen(comando_pytest(argumentos), cwd=raiz, env=ambiente_pytest(lote_estatico),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    linhas = []
    for linha in processo.stdout:
        linhas.append(linha)
        saida.write(linha)
    processo.stdout.close()
    codigo = processo.wait()
    saida.flush()
    return Resultado(codigo, "".join(linhas), time.monotonic() - inicio)


class Trava:
    """Trava exclusiva entre processos (`fcntl.flock`); quem chega depois espera a vez."""

    def __init__(self, caminho: str = CAMINHO_TRAVA, saida=sys.stdout):
        self.caminho = caminho
        self.saida = saida
        self._fd: int | None = None

    def __enter__(self) -> "Trava":
        self._fd = os.open(self.caminho, os.O_RDWR | os.O_CREAT, 0o666)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _escrever(self.saida, f"aguardando a vez (trava {self.caminho} ocupada por outro portão)...")
            fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc) -> None:
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        self._fd = None


def _escrever(saida, texto: str) -> None:
    saida.write(texto + "\n")
    saida.flush()


class Portao:
    """Os portões L0, INT e dos lotes paralelos. As dependências externas (pytest, git, relógio e trava)
    entram pelo construtor para a lógica poder ser testada com falsos."""

    def __init__(self, raiz: str = RAIZ, *, pytest=None, git=None, dormir=time.sleep,
                 caminho_trava: str = CAMINHO_TRAVA, espera_s: float = ESPERA_REPETICAO_S, saida=sys.stdout):
        self.raiz = raiz
        self.saida = saida
        self.pytest = pytest or (lambda argumentos, lote_estatico=None:
                                 rodar_pytest(argumentos, self.raiz, lote_estatico, self.saida))
        self.git = git or (lambda argumentos: git_status(self.raiz, argumentos))
        self.dormir = dormir
        self.caminho_trava = caminho_trava
        self.espera_s = espera_s
        self.lotes = ler_json(raiz, MANIFESTO_LOTES)
        self.congelados = ler_json(raiz, MANIFESTO_CONGELADOS)

    # ---------------------------------------------------------- comum
    def _diz(self, texto: str) -> None:
        _escrever(self.saida, texto)

    def _falhou(self, lote: str, passo: int, detalhes: list[str]) -> int:
        for detalhe in detalhes:
            self._diz("  - " + detalhe)
        self._diz(f"PORTAO {lote}: FALHOU no passo {passo}")
        return FALHOU

    def _trava(self) -> Trava:
        return Trava(self.caminho_trava, self.saida)

    def executar(self, lote: str) -> int:
        if lote not in LOTES:
            raise ValueError(f"lote desconhecido: {lote}")
        if lote == "L0":
            return self.fundacao()
        if lote == "INT":
            return self.integracao()
        return self.paralelo(lote)

    # ---------------------------------------------------------- lote paralelo
    def paralelo(self, lote: str) -> int:
        lista = self.lotes["lotes"][lote]
        tempos: list[tuple[str, float]] = []

        self._diz(f"PORTAO {lote}: passo 1, manifesto")
        problemas = conferir_manifesto(lista, self.congelados, self.raiz)
        if problemas:
            return self._falhou(lote, 1, problemas)

        self._diz(f"PORTAO {lote}: passo 2, fundação intacta")
        fundacao = self.lotes.get("fundacao_sha256") or {}
        if not fundacao:
            return self._falhou(lote, 2, ["fundação ainda não selada (o Lote 0 termina com --selar-fundacao)"])
        alterados = conferir_fundacao(fundacao, self.raiz)
        if alterados:
            return self._falhou(lote, 2, [f"arquivo da fundação alterado: {c} (relate, não conserte)"
                                          for c in alterados])

        self._diz(f"PORTAO {lote}: passo 3, testes do lote")
        r = self.pytest(testes_do_lote(lista))
        tempos.append(("testes do lote", r.segundos))
        if not r.ok:
            return self._falhou(lote, 3, [resumo_do_pytest(r.saida)])

        self._diz(f"PORTAO {lote}: passo 4, estáticos do lote (COFRE_V2_LOTE={lote})")
        r = self.pytest(["tests/test_v2_principios.py", "tests/test_v2_congelados.py"], lote_estatico=lote)
        tempos.append(("estáticos", r.segundos))
        if not r.ok:
            return self._falhou(lote, 4, [resumo_do_pytest(r.saida)])

        self._diz(f"PORTAO {lote}: passo 5, testes antigos (um lote por vez)")
        antigos = testes_antigos(self.congelados)
        with self._trava():
            r = self.pytest(antigos)
        tempos.append(("antigos", r.segundos))
        if not r.ok:
            self._diz(f"PORTAO {lote}: testes antigos falharam; nova tentativa em {self.espera_s:.0f} s")
            self.dormir(self.espera_s)
            with self._trava():
                r = self.pytest(antigos)
            tempos.append(("antigos, 2ª tentativa", r.segundos))
        if not r.ok:
            proprias, alheias, citados = classificar_falhas(r.saida, lista, self.congelados, self.raiz)
            for no in proprias:
                self._diz(f"  - falha própria: {no}")
            for no in alheias:
                self._diz(f"  - falha alheia: {no}")
            if proprias:
                self._diz(f"PORTAO {lote}: FALHOU no passo 5")
                return FALHOU
            self._diz(f"PORTAO {lote}: PENDENTE (falha alheia em {', '.join(citados)})")
            return PENDENTE

        self._diz(f"PORTAO {lote}: passo 6, git status do lote")
        for linha in self.git(["--", *lista]):
            self._diz("  " + linha)
        self._diz(f"PORTAO {lote}: OK ({_tempos(tempos)})")
        return PASSOU

    # ---------------------------------------------------------- fundação e integração
    def _suite_tres_vezes(self, lote: str, passo: int, ultima_com_duracoes: bool) -> list[Resultado] | None:
        resultados = []
        with self._trava():
            for vez in range(1, 4):
                extra = ["--durations=10"] if ultima_com_duracoes and vez == 3 else []
                self._diz(f"PORTAO {lote}: suíte inteira, execução {vez} de 3")
                r = self.pytest(["tests", *extra])
                resultados.append(r)
                self._diz(f"PORTAO {lote}: execução {vez}: {resumo_do_pytest(r.saida)} ({r.segundos:.1f} s)")
                if not r.ok:
                    self._falhou(lote, passo, [f"execução {vez}: {resumo_do_pytest(r.saida)}"])
                    return None
        return resultados

    def _status_contido(self, lote: str, passo: int, permitidos: set[str]) -> int | None:
        sobrou = sobras(caminhos_do_status(self.git(["--untracked-files=all"])), permitidos)
        if sobrou:
            return self._falhou(lote, passo, [f"fora do manifesto dos lotes: {c}" for c in sobrou])
        return None

    def fundacao(self) -> int:
        lista = self.lotes["lotes"]["L0"]
        self._diz("PORTAO L0: passo 1, manifesto")
        problemas = conferir_manifesto(lista, self.congelados, self.raiz)
        if problemas:
            return self._falhou("L0", 1, problemas)
        self._diz("PORTAO L0: passo 2, suíte inteira três vezes")
        resultados = self._suite_tres_vezes("L0", 2, ultima_com_duracoes=False)
        if resultados is None:
            return FALHOU
        self._diz("PORTAO L0: passo 3, git status contido na lista L0")
        falha = self._status_contido("L0", 3, set(lista))
        if falha is not None:
            return falha
        self._diz(f"PORTAO L0: OK ({_tempos([(f'suíte {i}', r.segundos) for i, r in enumerate(resultados, 1)])}; "
                  f"{resumo_do_pytest(resultados[-1].saida)})")
        return PASSOU

    def integracao(self) -> int:
        todos = {c for lista in self.lotes["lotes"].values() for c in lista}
        self._diz("PORTAO INT: passo 1, git status contido na união das listas")
        falha = self._status_contido("INT", 1, todos)
        if falha is not None:
            return falha
        self._diz("PORTAO INT: passo 2, suíte inteira três vezes (a última com --durations=10)")
        resultados = self._suite_tres_vezes("INT", 2, ultima_com_duracoes=True)
        if resultados is None:
            return FALHOU
        for i, r in enumerate(resultados, 1):
            if r.segundos > TETO_SUITE_S:
                self._diz(f"AVISO: a execução {i} levou {r.segundos:.1f} s, acima do teto de {TETO_SUITE_S:.0f} s")
        self._diz(f"PORTAO INT: OK ({_tempos([(f'suíte {i}', r.segundos) for i, r in enumerate(resultados, 1)])}; "
                  f"{resumo_do_pytest(resultados[-1].saida)})")
        return PASSOU


def _tempos(tempos: list[tuple[str, float]]) -> str:
    return ", ".join(f"{nome} {s:.1f} s" for nome, s in tempos)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = p.add_mutually_exclusive_group(required=True)
    grupo.add_argument("lote", nargs="?", choices=LOTES, help="lote a conferir")
    grupo.add_argument("--selar-fundacao", action="store_true", help="grava fundacao_sha256 no manifesto")
    args = p.parse_args(argv)
    if args.selar_fundacao:
        return selar_fundacao()
    return Portao().executar(args.lote)


if __name__ == "__main__":
    sys.exit(main())
