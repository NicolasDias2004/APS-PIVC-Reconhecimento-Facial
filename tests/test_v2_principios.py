"""Princípios da versão 2 provados por leitura do código, sem Qt: as regras transversais T1, T2, T5, T8,
T9 (atalhos), T13, T14 e T15, a fase do PDI de cada módulo de técnica, o `.gitignore`, o manifesto dos
lotes, as edições só de acréscimo e a lógica do portão dos lotes.

Cada regra é uma função que recebe as fontes a varrer e devolve as violações ("caminho:linha: motivo").
O caso parametrizado `test_regra_pega_e_poupa` cria em `tmp_path`, para cada regra, arquivos com a violação
(têm de ser pegos) e limpos (têm de passar): a cerca é provada antes de valer para o código que os lotes
ainda vão escrever. "Arquivo novo" é o que não está no manifesto de congelados nem entre os editáveis; dos cinco
editáveis de código, só as linhas acrescentadas são varridas. Com `COFRE_V2_LOTE=<lote>`, a varredura olha
só os arquivos daquele lote em `tests/v2_lotes.json` (é o que o portão do lote usa)."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import threading
import time
import types
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
UI = "cofre/qt/qml/Cofre/Ui"
CONGELADOS = json.loads((RAIZ / "tests" / "v2_congelados.json").read_text(encoding="utf-8"))
ARQUIVOS_CONGELADOS = frozenset(CONGELADOS["arquivos"])
ORIGINAIS: dict[str, list[str]] = CONGELADOS["editaveis"]
# editáveis de integração que não são código varrido (a lista da seção 4.1 da especificação)
EDITAVEIS = frozenset(ORIGINAIS) | {".gitignore", "README.md", "ferramentas/listar_codigo.py",
                                    "docs/DETALHES-PARA-DOCUMENTACAO.md", "docs/LISTAGEM-CODIGO.md"}
MANIFESTO_LOTES = RAIZ / "tests" / "v2_lotes.json"
PORTAO = RAIZ / "ferramentas" / "portao_lote.py"
EXTENSOES = (".py", ".qml", ".js")
LOTES_PARALELOS = ("L1", "L2", "L3", "L4", "L5", "L5B", "L6", "L7", "L8")
# as três linhas originais que a fundação troca (ganham conteúdo no fim), por arquivo
TROCAVEIS = {"cofre/qt/aplicacao.py": lambda linha: linha.startswith("PAGINAS ="),
             f"{UI}/Main.qml": lambda linha: 'id: "config"' in linha,
             f"{UI}/Icones.js": lambda linha: linha.strip().startswith('"teclado"')}


# ------------------------------------------------------------------ o que varrer

class Fonte:
    """Um arquivo a varrer. Para editável, `texto` traz só as linhas acrescentadas (as originais viram linha
    vazia, para os números de linha continuarem certos) e não há árvore sintática."""

    def __init__(self, caminho: str, texto: str, editavel: bool = False):
        self.caminho = caminho
        self.texto = texto
        self.editavel = editavel
        self._arvore: ast.AST | None = None

    @property
    def py(self) -> bool:
        return self.caminho.endswith(".py")

    @property
    def qml(self) -> bool:
        return self.caminho.endswith((".qml", ".js"))

    @property
    def de_teste(self) -> bool:
        return self.caminho.startswith("tests/")

    @property
    def arvore(self) -> ast.AST | None:
        """A AST do arquivo .py novo (None para editável e para QML)."""
        if self.py and not self.editavel and self._arvore is None:
            self._arvore = ast.parse(self.texto, filename=self.caminho)
        return self._arvore


def casar_originais(originais: list[str], atuais: list[str], trocavel=lambda linha: False) -> list[int | None]:
    """Para cada linha original, o índice da linha atual que a guarda (na mesma ordem), ou None se sumiu.
    Uma linha trocável casa com a atual que começa com ela (a linha que só ganhou conteúdo no fim)."""
    casados: list[int | None] = []
    j = 0
    for original in originais:
        k = j
        while k < len(atuais) and not (atuais[k] == original or
                                       (trocavel(original) and atuais[k].startswith(original.rstrip()))):
            k += 1
        if k < len(atuais):
            casados.append(k)
            j = k + 1
        else:
            casados.append(None)        # sumiu: as próximas continuam a busca do mesmo ponto
    return casados


def so_acrescimos(caminho: str, texto: str, originais: list[str]) -> str:
    """O texto do editável com as linhas originais (intactas) apagadas; as trocadas continuam visíveis."""
    atuais = texto.split("\n")
    trocavel = TROCAVEIS.get(caminho, lambda linha: False)
    for original, indice in zip(originais, casar_originais(originais, atuais, trocavel)):
        if indice is not None and atuais[indice] == original:
            atuais[indice] = ""
    return "\n".join(atuais)


def fontes(caminhos: list[str], raiz: Path = RAIZ, originais: dict[str, list[str]] | None = None) -> list[Fonte]:
    originais = ORIGINAIS if originais is None else originais
    saida = []
    for caminho in caminhos:
        texto = (raiz / caminho).read_text(encoding="utf-8")
        if caminho in originais:
            saida.append(Fonte(caminho, so_acrescimos(caminho, texto, originais[caminho]), editavel=True))
        else:
            saida.append(Fonte(caminho, texto))
    return saida


def _lote_em_vigor() -> list[str] | None:
    lote = os.environ.get("COFRE_V2_LOTE")
    if not lote:
        return None
    lotes = json.loads(MANIFESTO_LOTES.read_text(encoding="utf-8"))["lotes"]
    assert lote in lotes, f"COFRE_V2_LOTE={lote} não existe em tests/v2_lotes.json"
    return lotes[lote]


def caminhos_novos() -> list[str]:
    """Arquivos de código novos (.py, .qml, .js): todos, ou só os do lote em `COFRE_V2_LOTE`."""
    do_lote = _lote_em_vigor()
    if do_lote is None:
        candidatos = [p for p in RAIZ.glob("*.py")]
        for pasta in ("cofre", "ferramentas", "tests"):
            candidatos += [p for p in (RAIZ / pasta).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        relativos = {p.relative_to(RAIZ).as_posix() for p in candidatos}
    else:
        relativos = {c for c in do_lote if (RAIZ / c).is_file()}
    return sorted(c for c in relativos if c.endswith(EXTENSOES) and c not in ARQUIVOS_CONGELADOS and c not in EDITAVEIS)


def caminhos_editados() -> list[str]:
    """Os cinco editáveis de código (só as linhas acrescentadas são varridas); com lote, só os da lista dele."""
    do_lote = _lote_em_vigor()
    return sorted(c for c in ORIGINAIS if (RAIZ / c).is_file() and (do_lote is None or c in do_lote))


def _novas() -> list[Fonte]:
    return fontes(caminhos_novos())


def _novas_e_acrescimos() -> list[Fonte]:
    return fontes(caminhos_novos() + caminhos_editados())


# ------------------------------------------------------------------ ferramentas de leitura

_TOKEN_QML = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`|//[^\n]*|/\*.*?\*/', re.S)


def sem_comentarios(texto: str) -> str:
    """QML/JS sem comentários (trocados por espaços, mantendo as quebras de linha) e com as cadeias intactas."""
    def trocar(m: re.Match) -> str:
        t = m.group(0)
        return t if t[0] in "\"'`" else re.sub(r"[^\n]", " ", t)
    return _TOKEN_QML.sub(trocar, texto)


def so_codigo(texto: str) -> str:
    """QML/JS sem comentários e com o conteúdo das cadeias apagado (as aspas ficam): só o código."""
    def trocar(m: re.Match) -> str:
        t = m.group(0)
        if t[0] in "\"'`":
            return t[0] + re.sub(r"[^\n]", " ", t[1:-1]) + t[-1]
        return re.sub(r"[^\n]", " ", t)
    return _TOKEN_QML.sub(trocar, texto)


def literais_qml(texto: str) -> list[tuple[int, str]]:
    """(linha, conteúdo) de cada cadeia de QML/JS fora de comentário."""
    saida = []
    for m in _TOKEN_QML.finditer(texto):
        t = m.group(0)
        if t[0] in "\"'`":
            saida.append((texto.count("\n", 0, m.start()) + 1, t[1:-1]))
    return saida


def _linha(texto: str, posicao: int) -> int:
    return texto.count("\n", 0, posicao) + 1


def _docstrings(arvore: ast.AST) -> set[int]:
    """ids dos nós Constant que são docstring (módulo, classe, função)."""
    ids = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and no.body:
            primeiro = no.body[0]
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant) \
                    and isinstance(primeiro.value.value, str):
                ids.add(id(primeiro.value))
    return ids


def cadeias_py(arvore: ast.AST) -> list[tuple[int, str]]:
    """(linha, conteúdo) de cada cadeia do Python que não é docstring (inclui os pedaços de f-string)."""
    docs = _docstrings(arvore)
    return [(no.lineno, no.value) for no in ast.walk(arvore)
            if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in docs]


def nomes_py(arvore: ast.AST) -> list[tuple[int, str]]:
    """(linha, identificador) de nomes, atributos, importações, definições, argumentos e palavras-chave."""
    saida = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name):
            saida.append((no.lineno, no.id))
        elif isinstance(no, ast.Attribute):
            saida.append((no.lineno, no.attr))
        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            saida.append((no.lineno, no.name))
        elif isinstance(no, ast.alias):
            saida.append((no.lineno, no.name.rsplit(".", 1)[-1]))
            if no.asname:
                saida.append((no.lineno, no.asname))
        elif isinstance(no, ast.arg):
            saida.append((no.lineno, no.arg))
        elif isinstance(no, ast.keyword) and no.arg:
            saida.append((no.value.lineno, no.arg))
    return saida


def _nome_chamado(no: ast.Call) -> str | None:
    if isinstance(no.func, ast.Name):
        return no.func.id
    if isinstance(no.func, ast.Attribute):
        return no.func.attr
    return None


def _apelidos_de_config(arvore: ast.AST) -> set[str]:
    """Nomes ligados ao módulo `cofre.config` (importação com ou sem `as`, e `x = config`)."""
    apelidos = {"config"}
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom):
            for a in no.names:
                if a.name == "config":
                    apelidos.add(a.asname or "config")
        elif isinstance(no, ast.Import):
            for a in no.names:
                if a.name.endswith(".config") and a.asname:
                    apelidos.add(a.asname)
    mudou = True
    while mudou:
        mudou = False
        for no in ast.walk(arvore):
            if isinstance(no, ast.Assign) and isinstance(no.value, ast.Name) and no.value.id in apelidos:
                for alvo in no.targets:
                    if isinstance(alvo, ast.Name) and alvo.id not in apelidos:
                        apelidos.add(alvo.id)
                        mudou = True
    return apelidos


def _e_config(no: ast.AST, apelidos: set[str]) -> bool:
    return (isinstance(no, ast.Name) and no.id in apelidos) or (isinstance(no, ast.Attribute) and no.attr == "config")


def _alvos(alvo: ast.AST):
    if isinstance(alvo, (ast.Tuple, ast.List)):
        for elt in alvo.elts:
            yield from _alvos(elt)
    elif isinstance(alvo, ast.Starred):
        yield from _alvos(alvo.value)
    else:
        yield alvo


def escritas_em_config(arvore: ast.AST) -> list[tuple[int, str | None]]:
    """(linha, nome) de cada escrita em `config`: atribuição, `del`, `setattr` e `delattr`. O nome é None
    quando não dá para saber qual variável (setattr com nome calculado)."""
    apelidos = _apelidos_de_config(arvore)
    saida: list[tuple[int, str | None]] = []
    for no in ast.walk(arvore):
        alvos = []
        if isinstance(no, ast.Assign):
            alvos = no.targets
        elif isinstance(no, (ast.AugAssign, ast.AnnAssign)):
            alvos = [no.target]
        elif isinstance(no, ast.Delete):
            alvos = no.targets
        for alvo in alvos:
            for a in _alvos(alvo):
                if isinstance(a, ast.Attribute) and _e_config(a.value, apelidos):
                    saida.append((a.lineno, a.attr))
        if isinstance(no, ast.Call) and _nome_chamado(no) in ("setattr", "delattr") and no.args \
                and _e_config(no.args[0], apelidos):
            nome = no.args[1].value if len(no.args) > 1 and isinstance(no.args[1], ast.Constant) else None
            saida.append((no.lineno, nome))
    return saida


# ------------------------------------------------------------------ T1: nada novo toca na decisão

NOMES_DA_DECISAO = ("decidir_acesso", "registrar_acesso", "autenticar_imagem", "registrar_sucesso", "registrar_falha",
                    "salvar_arquivo", "liveness_ativo", "_bloqueado_ate", "definirNivel", "definirLiveness",
                    "decisaoTomada")
CADEIAS_DA_DECISAO = ("sessao_vm.abrir", "parametros.aplicar", "setattr(config")
# o grep da seção 9.3 da especificação (por palavra, em todo `cofre/`, inclusive comentário e docstring)
NOMES_DO_GREP = ("decisaoTomada", "definirLiveness", "definirNivel")
PASTAS_DE_CONFIG = frozenset({"DATA_DIR", "DB_PATH", "FOTOS_DIR", "EVIDENCIAS_DIR", "RELATORIOS_DIR"})
LANCADORES = frozenset({"app_demo.py", "ferramentas/capturar_telas.py"})
NOMES_DA_CAPTURA = frozenset({"definirNivel", "definirLiveness", "registrar_falha", "registrar_acesso"})
_RE_NOMES = re.compile(r"\b(" + "|".join(NOMES_DA_DECISAO) + r")\b")
_RE_GREP = re.compile(r"\b(" + "|".join(NOMES_DO_GREP) + r")\b")
_RE_PASSO = re.compile(r"\.\s*passo\s*\(")
_RE_CONFIG_ATRIBUIDO = re.compile(r"\bconfig\s*\.\s*(\w+)\s*(?:[-+*/%|&^]|//|\*\*|<<|>>)?=(?!=)")
_RE_SETATTR_CONFIG = re.compile(r"\bsetattr\s*\(\s*config\b")


def violacoes_decisao(lista: list[Fonte]) -> list[str]:
    """T1. Em .py novo, por identificador da AST; em QML e nas linhas acrescentadas dos editáveis, por
    expressão com limite de palavra. Testes ficam de fora; os lançadores têm as exceções nomeadas."""
    v = []
    for f in lista:
        if f.de_teste:
            continue
        permitidos = NOMES_DA_CAPTURA if f.caminho == "ferramentas/capturar_telas.py" else frozenset()
        if f.caminho.startswith("cofre/"):
            for m in _RE_GREP.finditer(f.texto):
                v.append(f"{f.caminho}:{_linha(f.texto, m.start())}: '{m.group(1)}' (aparece no grep da seção 9.3)")
        if f.arvore is not None:
            for linha, nome in nomes_py(f.arvore):
                if nome in NOMES_DA_DECISAO and nome not in permitidos:
                    v.append(f"{f.caminho}:{linha}: usa '{nome}'")
            for linha, cadeia in cadeias_py(f.arvore):
                if cadeia in NOMES_DA_DECISAO and cadeia not in permitidos:
                    v.append(f"{f.caminho}:{linha}: nome '{cadeia}' em cadeia (getattr disfarçado)")
            for no in ast.walk(f.arvore):
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) and no.func.attr == "passo":
                    v.append(f"{f.caminho}:{no.lineno}: chama '.passo('")
                if isinstance(no, ast.ImportFrom) and (no.module or "").endswith("parametros") \
                        and any(a.name == "aplicar" for a in no.names):
                    v.append(f"{f.caminho}:{no.lineno}: importa 'aplicar' de parametros")
            for linha, nome in escritas_em_config(f.arvore):
                if not (f.caminho in LANCADORES and nome in PASTAS_DE_CONFIG):
                    v.append(f"{f.caminho}:{linha}: escreve em config ({nome or 'nome calculado'})")
            for cadeia in ("sessao_vm.abrir", "parametros.aplicar"):
                for m in re.finditer(re.escape(cadeia) + r"\b", f.texto):
                    v.append(f"{f.caminho}:{_linha(f.texto, m.start())}: '{cadeia}'")
        else:
            texto = f.texto
            for m in _RE_NOMES.finditer(texto):
                if m.group(1) not in permitidos:
                    v.append(f"{f.caminho}:{_linha(texto, m.start())}: usa '{m.group(1)}'")
            for m in _RE_PASSO.finditer(texto):
                v.append(f"{f.caminho}:{_linha(texto, m.start())}: chama '.passo('")
            for cadeia in CADEIAS_DA_DECISAO:
                for m in re.finditer(re.escape(cadeia).replace(r"\(", r"\s*\(\s*") + r"\b", texto):
                    v.append(f"{f.caminho}:{_linha(texto, m.start())}: '{cadeia}'")
            for m in _RE_CONFIG_ATRIBUIDO.finditer(texto):
                if not (f.caminho in LANCADORES and m.group(1) in PASTAS_DE_CONFIG):
                    v.append(f"{f.caminho}:{_linha(texto, m.start())}: escreve em config.{m.group(1)}")
    return v


# ------------------------------------------------------------------ T2: banco só por leitura_ro

DONOS_DO_BANCO = frozenset({"cofre/base_demo.py", "ferramentas/capturar_telas.py"})
ABRE_SQLITE = DONOS_DO_BANCO | {"cofre/leitura_ro.py"}
ESCRITAS_NO_BANCO = frozenset({"criar_usuario", "alterar_nivel", "definir_ativo", "remover_usuario", "adicionar_amostra",
                               "cadastrar_de_imagens", "cadastrar_pela_camera"})


def violacoes_banco(lista: list[Fonte]) -> list[str]:
    """T2. Fora dos testes: `Banco(` só em base_demo e capturar_telas; conexão sqlite3 só em leitura_ro e
    nesses dois; nenhuma chamada que escreve no banco (nem `_con`, a conexão interna do `Banco`)."""
    v = []
    for f in lista:
        if f.de_teste or f.arvore is None:
            continue
        for no in ast.walk(f.arvore):
            if isinstance(no, ast.Call):
                nome = _nome_chamado(no)
                if nome == "Banco" and f.caminho not in DONOS_DO_BANCO:
                    v.append(f"{f.caminho}:{no.lineno}: cria 'Banco(' (análise lê por cofre.leitura_ro)")
                elif nome in ESCRITAS_NO_BANCO and f.caminho not in DONOS_DO_BANCO:
                    v.append(f"{f.caminho}:{no.lineno}: chama '{nome}', que escreve no banco")
                elif nome == "connect" and isinstance(no.func, ast.Attribute) \
                        and isinstance(no.func.value, ast.Name) and no.func.value.id == "sqlite3" \
                        and f.caminho not in ABRE_SQLITE:
                    v.append(f"{f.caminho}:{no.lineno}: abre 'sqlite3.connect' (análise lê por cofre.leitura_ro)")
            elif isinstance(no, ast.ImportFrom) and no.module == "sqlite3" and f.caminho not in ABRE_SQLITE \
                    and any(a.name == "connect" for a in no.names):
                v.append(f"{f.caminho}:{no.lineno}: importa 'connect' de sqlite3")
            elif isinstance(no, ast.Attribute) and no.attr == "_con" and f.caminho not in DONOS_DO_BANCO:
                v.append(f"{f.caminho}:{no.lineno}: usa '_con', a conexão de escrita do Banco")
    return v


# ------------------------------------------------------------------ T5: verde só para concedido

DONOS_DA_COR_CONCEDIDO = frozenset({"cofre/qt/graficos.py", "cofre/qt/tema_v2.py", "cofre/analitica.py",
                                    "cofre/qt/vm_painel_geral.py", "cofre/qt/vm_painel_incidentes.py",
                                    "cofre/qt/relatorio_pdf.py"})
_RE_VERDE = re.compile(r"\bTheme\s*\.\s*sucesso\b|\bsucessoSuave\b|\bcorResultado\s*\(|\bsuaveResultado\s*\(|#3dd68c",
                       re.I)
_RE_JUSTIFICA_VERDE = re.compile(r"concedido|CONCEDIDO|sessao\.ativa|\bs\.ativa\b")
_RE_MEDIDOR = re.compile(r"\bMedidor\s*\{")
_RE_NOTIFICA_OK = re.compile(r"\bnotificar\s*\(\s*[\"']ok[\"']")


def violacoes_verde(lista: list[Fonte]) -> list[str]:
    """T5. Em QML novo, verde (`Theme.sucesso`, `sucessoSuave`, `corResultado(`, `suaveResultado(`, o hex de
    `sucesso`) só em linha com `concedido`/`CONCEDIDO`/`sessao.ativa`/`s.ativa`; nada de `Medidor`; nada de
    `notificar("ok", ...)`. Em Python novo fora dos testes, a cor "concedido" só nos seis donos."""
    v = []
    for f in lista:
        if f.qml:
            texto = sem_comentarios(f.texto)
            for numero, linha in enumerate(texto.split("\n"), 1):
                if _RE_VERDE.search(linha) and not _RE_JUSTIFICA_VERDE.search(linha):
                    v.append(f"{f.caminho}:{numero}: verde fora de concedido/sessão ativa")
                if _RE_MEDIDOR.search(linha):
                    v.append(f"{f.caminho}:{numero}: usa 'Medidor' (verde acima do limiar); use Anel ou BarraSimilaridade")
                if _RE_NOTIFICA_OK.search(linha):
                    v.append(f"{f.caminho}:{numero}: notificar(\"ok\") pinta verde; use \"info\"")
        elif f.arvore is not None and not f.de_teste:
            if f.caminho not in DONOS_DA_COR_CONCEDIDO:
                for linha, cadeia in cadeias_py(f.arvore):
                    if cadeia == "concedido":
                        v.append(f"{f.caminho}:{linha}: cor de gráfico 'concedido' fora dos donos")
            for no in ast.walk(f.arvore):
                if isinstance(no, ast.Call) and _nome_chamado(no) == "notificar":
                    valores = list(no.args[:1]) + [k.value for k in no.keywords if k.arg == "tipo"]
                    if any(isinstance(a, ast.Constant) and a.value == "ok" for a in valores):
                        v.append(f"{f.caminho}:{no.lineno}: notificar(\"ok\") pinta verde; use \"info\"")
    return v


# ------------------------------------------------------------------ T8: ninguém lista fotos ou evidências

DONOS_DAS_PASTAS = frozenset({"app_demo.py", "cofre/base_demo.py", "ferramentas/capturar_telas.py"})
_RE_FOTOS = re.compile(r"\b(FOTOS_DIR|EVIDENCIAS_DIR|fotos_do_usuario|evidenciaUrl)\b")


def violacoes_fotos(lista: list[Fonte]) -> list[str]:
    """T8. Fora dos testes e dos três donos: nem `FOTOS_DIR`, `EVIDENCIAS_DIR`, `fotos_do_usuario`,
    `evidenciaUrl` (por palavra), nem caminho literal `data/fotos` ou `data/evidencias` em cadeia do Python."""
    v = []
    for f in lista:
        if f.de_teste or f.caminho in DONOS_DAS_PASTAS:
            continue
        for m in _RE_FOTOS.finditer(f.texto):
            v.append(f"{f.caminho}:{_linha(f.texto, m.start())}: '{m.group(1)}'")
        if f.arvore is not None:
            for linha, cadeia in cadeias_py(f.arvore):
                if re.search(r"data/(fotos|evidencias)\b", cadeia):
                    v.append(f"{f.caminho}:{linha}: caminho de fotos/evidências '{cadeia}'")
    return v


# ------------------------------------------------------------------ T13: QML estático

_RE_PROIBIDOS_QML = re.compile(r"\b(MultiEffect|layer\s*\.\s*effect|ShaderEffect\w*|RectangularShadow|ImageParticle|"
                               r"Settings|console\s*\.\s*\w+)\b")
_RE_THEME = re.compile(r"\bTheme\s*\.\s*([A-Za-z_]\w*)")
_RE_PROP_ICONE = re.compile(r"\b(\w*[iI]cone\w*)\s*:")
_RE_BLOCO_ICONE = re.compile(r"\bIcone\s*\{")
_RE_CAMINHO_ICONE = re.compile(r"\bIcones\s*\.\s*caminho\s*\(\s*([\"'])([^\"']*)\1")


def nomes_do_theme(raiz: Path = RAIZ) -> set[str]:
    texto = (raiz / UI / "Theme.qml").read_text(encoding="utf-8")
    return set(re.findall(r"\bproperty\s+[\w.<>]+\s+(\w+)", texto)) | set(re.findall(r"\bfunction\s+(\w+)\s*\(", texto))


def nomes_de_icones(raiz: Path = RAIZ) -> set[str]:
    texto = (raiz / UI / "Icones.js").read_text(encoding="utf-8")
    return set(re.findall(r"^\s*\"(\w+)\"\s*:", texto, re.M))


def _cadeias_da_expressao(texto: str, inicio: int) -> list[str]:
    """Cadeias que são valor de uma expressão QML que começa em `inicio`, até a vírgula, ponto e vírgula,
    chave ou quebra de linha de nível zero: os dois lados de um `a ? "x" : "y"` contam; a cadeia comparada
    na condição (`tipo === "aviso"`) ou concatenada não conta."""
    cadeias, i, nivel, anterior = [], inicio, 0, ":"
    while i < len(texto):
        c = texto[i]
        if c in "\"'":
            fim = i + 1
            while fim < len(texto) and texto[fim] != c:
                fim += 2 if texto[fim] == "\\" else 1
            seguinte = texto[fim + 1:].lstrip(" \t")[:1] or "\n"
            if anterior in "?:([" and seguinte in ":)],;}\n":
                cadeias.append(texto[i + 1:fim])
            anterior = c
            i = fim + 1
            continue
        if not c.isspace():
            anterior = c
        if c in "([":
            nivel += 1
        elif c in ")]":
            if nivel == 0:
                break
            nivel -= 1
        elif c in ",;}\n" and nivel == 0:
            break
        i += 1
    return cadeias


def _blocos(texto: str, abertura: re.Pattern) -> list[tuple[int, str]]:
    """(posição, corpo) de cada bloco `Tipo { ... }`, casando as chaves (o texto já vem sem comentários)."""
    blocos = []
    for m in abertura.finditer(texto):
        nivel, i = 1, m.end()
        while i < len(texto) and nivel:
            if texto[i] in "\"'":
                aspas, i = texto[i], i + 1
                while i < len(texto) and texto[i] != aspas:
                    i += 2 if texto[i] == "\\" else 1
            elif texto[i] == "{":
                nivel += 1
            elif texto[i] == "}":
                nivel -= 1
            i += 1
        blocos.append((m.start(), texto[m.end():i - 1]))
    return blocos


def icones_literais(texto: str) -> list[tuple[int, str]]:
    """(linha, nome) de cada nome de ícone literal num QML sem comentários: valor de propriedade cujo nome
    contém "icone"/"Icone", `nome:` direto de um `Icone { }` e `Icones.caminho("...")`. Cor (#...) não conta."""
    achados = []
    for m in _RE_PROP_ICONE.finditer(texto):
        for cadeia in _cadeias_da_expressao(texto, m.end()):
            achados.append((_linha(texto, m.start()), cadeia))
    for posicao, corpo in _blocos(texto, _RE_BLOCO_ICONE):
        base = posicao + texto[posicao:].index("{") + 1
        nivel = 0
        for i, c in enumerate(corpo):
            if c == "{":
                nivel += 1
            elif c == "}":
                nivel -= 1
            elif nivel == 0 and corpo.startswith("nome", i) and (i == 0 or not (corpo[i - 1].isalnum() or corpo[i - 1] == "_")):
                resto = re.match(r"nome\s*:", corpo[i:])
                if resto:
                    for cadeia in _cadeias_da_expressao(corpo, i + resto.end()):
                        achados.append((_linha(texto, base + i), cadeia))
    for m in _RE_CAMINHO_ICONE.finditer(texto):
        achados.append((_linha(texto, m.start()), m.group(2)))
    return [(linha, nome) for linha, nome in achados if nome and not nome.startswith("#")]


def violacoes_qml_estatico(lista: list[Fonte], tema: set[str] | None = None, icones: set[str] | None = None) -> list[str]:
    """T13. Em QML novo: nenhum efeito pesado, `Settings` nem `console.*`; todo `Theme.<x>` existe; todo ícone
    literal existe em Icones.js. Em Python novo fora dos testes, ícone literal de modelo (`"icone": "..."` ou
    `icone="..."`) também precisa existir."""
    tema = nomes_do_theme() if tema is None else tema
    icones = nomes_de_icones() if icones is None else icones
    v = []
    for f in lista:
        if f.qml:
            codigo = so_codigo(f.texto)
            for m in _RE_PROIBIDOS_QML.finditer(codigo):
                v.append(f"{f.caminho}:{_linha(codigo, m.start())}: usa '{m.group(1)}'")
            for m in _RE_THEME.finditer(codigo):
                if m.group(1) not in tema:
                    v.append(f"{f.caminho}:{_linha(codigo, m.start())}: 'Theme.{m.group(1)}' não existe em Theme.qml")
            for linha, nome in icones_literais(sem_comentarios(f.texto)):
                if nome not in icones:
                    v.append(f"{f.caminho}:{linha}: ícone '{nome}' não existe em Icones.js")
        elif f.arvore is not None and not f.de_teste:
            for no in ast.walk(f.arvore):
                valores = []
                if isinstance(no, ast.Dict):
                    valores = [val for chave, val in zip(no.keys, no.values)
                               if isinstance(chave, ast.Constant) and chave.value == "icone"]
                elif isinstance(no, ast.Call):
                    valores = [k.value for k in no.keywords if k.arg == "icone"]
                for val in valores:
                    if isinstance(val, ast.Constant) and isinstance(val.value, str) and val.value \
                            and val.value not in icones:
                        v.append(f"{f.caminho}:{val.lineno}: ícone '{val.value}' não existe em Icones.js")
    return v


# ------------------------------------------------------------------ T9 (parte estática): atalhos novos

_RE_SHORTCUT = re.compile(r"\bShortcut\s*\{")


def violacoes_atalhos(lista: list[Fonte]) -> list[str]:
    """T9. Todo `Shortcut` de QML novo inclui `!app.v2.sobreposicaoAberta` em `enabled` (o guarda de teclas do
    Main.qml é editável e fica de fora)."""
    v = []
    for f in lista:
        if not f.qml or f.editavel:
            continue
        texto = sem_comentarios(f.texto)
        for posicao, corpo in _blocos(texto, _RE_SHORTCUT):
            m = re.search(r"\benabled\s*:", corpo)
            expressao = "".join(_trecho_ate_fim(corpo, m.end()).split()) if m else ""
            if "!app.v2.sobreposicaoAberta" not in conjuncoes(expressao):
                v.append(f"{f.caminho}:{_linha(texto, posicao)}: Shortcut sem '!app.v2.sobreposicaoAberta' em enabled")
    return v


def conjuncoes(expressao: str) -> list[str]:
    """Os termos ligados por `&&` no nível de fora, cada um sem os parênteses externos. Com `||` no nível de
    fora a expressão inteira é um termo só: `a || !guarda` não garante a guarda."""
    expressao = _sem_parenteses_externos(expressao)
    termos, nivel, inicio, i = [], 0, 0, 0
    while i < len(expressao):
        c = expressao[i]
        if c in "([":
            nivel += 1
        elif c in ")]":
            nivel -= 1
        elif nivel == 0 and expressao.startswith("||", i):
            return [expressao]
        elif nivel == 0 and expressao.startswith("&&", i):
            termos.append(expressao[inicio:i])
            inicio, i = i + 2, i + 2
            continue
        i += 1
    return [_sem_parenteses_externos(termo) for termo in termos + [expressao[inicio:]]]


def _sem_parenteses_externos(expressao: str) -> str:
    """Tira parênteses que envolvem a expressão inteira: `((a && b))` vira `a && b`; `(a) && (b)` fica."""
    while expressao.startswith("(") and expressao.endswith(")"):
        nivel = 0
        for i, c in enumerate(expressao):
            nivel += c == "("
            nivel -= c == ")"
            if nivel == 0 and i < len(expressao) - 1:
                return expressao
        expressao = expressao[1:-1]
    return expressao


def _trecho_ate_fim(texto: str, inicio: int) -> str:
    fim = inicio
    while fim < len(texto) and texto[fim] not in ";\n":
        fim += 1
    return texto[inicio:fim]


# ------------------------------------------------------------------ T14: laboratório não fala em autorização

_RE_AUTORIZACAO = re.compile(r"\b(autorizad|concedid|negad)[oa]s?\b", re.I)
_RE_ARQUIVO_LAB = re.compile(r"^(Lab\w*|Res\w*|LaboratorioPagina|ResultadosPagina)\.qml$")
TECNICA_DO_LAB = frozenset({"fases_lab.py", "robustez.py", "explicabilidade.py", "metricas.py", "protocolos.py",
                            "galeria_analise.py", "qualidade_erc.py",
                            # técnica do Lote 0 que só o Laboratório e Resultados usam
                            "amostra_lab.py", "degradacoes.py", "lote_sface.py", "qualidade.py"})


def e_do_laboratorio(caminho: str) -> bool:
    pasta, _, nome = caminho.rpartition("/")
    if pasta == UI:
        return bool(_RE_ARQUIVO_LAB.match(nome))
    if pasta == "cofre/qt":
        return nome.startswith(("vm_lab_", "vm_res_")) or nome in ("vm_laboratorio.py", "vm_resultados.py")
    return pasta == "cofre" and nome in TECNICA_DO_LAB


def violacoes_autorizacao(lista: list[Fonte]) -> list[str]:
    """T14. Nas telas e na técnica do Laboratório e de Resultados, nenhum texto de interface (cadeia fora de
    comentário e de docstring) diz autorizado, concedido ou negado, em qualquer grafia."""
    v = []
    for f in lista:
        if not e_do_laboratorio(f.caminho):
            continue
        if f.arvore is not None:
            cadeias = cadeias_py(f.arvore)
        elif f.qml:
            cadeias = literais_qml(f.texto)
        else:
            continue
        for linha, cadeia in cadeias:
            for m in _RE_AUTORIZACAO.finditer(cadeia):
                v.append(f"{f.caminho}:{linha}: '{m.group(0)}' em texto de interface")
    return v


# ------------------------------------------------------------------ T15: abrir no sistema num lugar só

DONO_DO_ABRIR = "cofre/qt/vm_figuras.py"


def violacoes_abrir_no_sistema(lista: list[Fonte]) -> list[str]:
    """T15. `QDesktopServices` só em vm_figuras.py, dentro de `abrir_no_sistema(caminho)`; ninguém faz
    `from ... import abrir_no_sistema`; nada de `webbrowser`, `os.startfile` nem `Qt.openUrlExternally`."""
    v = []
    for f in lista:
        if f.qml:
            texto = sem_comentarios(f.texto)
            for m in re.finditer(r"\bQt\s*\.\s*openUrlExternally\b", texto):
                v.append(f"{f.caminho}:{_linha(texto, m.start())}: 'Qt.openUrlExternally' (use vm_figuras.abrir_no_sistema)")
            continue
        if f.arvore is None:
            continue
        dentro = set()
        if f.caminho == DONO_DO_ABRIR:
            funcoes = [no for no in f.arvore.body if isinstance(no, ast.FunctionDef) and no.name == "abrir_no_sistema"]
            if not funcoes:
                v.append(f"{f.caminho}: não define abrir_no_sistema(caminho) no nível do módulo")
            for fn in funcoes:
                if [a.arg for a in fn.args.args][:1] != ["caminho"]:
                    v.append(f"{f.caminho}:{fn.lineno}: abrir_no_sistema não recebe 'caminho'")
                dentro |= {id(no) for no in ast.walk(fn)}
                if not any(isinstance(no, (ast.Name, ast.Attribute)) and
                           (getattr(no, "id", None) == "QDesktopServices" or getattr(no, "attr", None) == "QDesktopServices")
                           for no in ast.walk(fn)):
                    v.append(f"{f.caminho}:{fn.lineno}: abrir_no_sistema não usa QDesktopServices")
        for no in ast.walk(f.arvore):
            if isinstance(no, (ast.Import, ast.ImportFrom)):
                for a in no.names:
                    if a.name == "abrir_no_sistema":
                        v.append(f"{f.caminho}:{no.lineno}: importa abrir_no_sistema pelo nome (chame vm_figuras.abrir_no_sistema)")
                    if a.name.split(".")[0] == "webbrowser" or (isinstance(no, ast.ImportFrom) and no.module == "webbrowser"):
                        v.append(f"{f.caminho}:{no.lineno}: usa webbrowser (use vm_figuras.abrir_no_sistema)")
                    if a.name == "QDesktopServices" and f.caminho != DONO_DO_ABRIR:
                        v.append(f"{f.caminho}:{no.lineno}: importa QDesktopServices")
            elif (isinstance(no, ast.Name) and no.id == "QDesktopServices") or \
                    (isinstance(no, ast.Attribute) and no.attr == "QDesktopServices"):
                if f.caminho != DONO_DO_ABRIR or id(no) not in dentro:
                    v.append(f"{f.caminho}:{no.lineno}: QDesktopServices fora de vm_figuras.abrir_no_sistema")
            elif isinstance(no, ast.Attribute) and no.attr == "startfile":
                v.append(f"{f.caminho}:{no.lineno}: usa os.startfile (use vm_figuras.abrir_no_sistema)")
    return v


# ------------------------------------------------------------------ 4.3: módulos declaram a fase do PDI

RE_FASE = re.compile(r"^(Fases? [1-5]( (a|e) [1-5])?( \([^)]*\))?|Apoio \([^)]*\)): \S")


def violacoes_fase(lista: list[Fonte]) -> list[str]:
    """4.3. Todo `cofre/*.py` novo (sem recursão) começa a docstring com a fase do PDI."""
    v = []
    for f in lista:
        if f.arvore is None or f.caminho.count("/") != 1 or not f.caminho.startswith("cofre/"):
            continue
        doc = ast.get_docstring(f.arvore)
        primeira = doc.split("\n", 1)[0] if doc else ""
        if not RE_FASE.match(primeira):
            v.append(f"{f.caminho}:1: primeira linha da docstring não declara a fase: {primeira!r}")
    return v


# ------------------------------------------------------------------ .gitignore, manifesto, edições

COBREM_DEMO = frozenset({"data/demo/", "data/demo", "data/demo/*", "data/demo/**", "data/", "data", "data/*", "data/**"})


def gitignore_cobre_demo(texto: str) -> bool:
    """Alguma linha ignora `data/demo/` e nenhuma linha posterior desfaz isso com `!`."""
    cobre = False
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        negada = linha.startswith("!")
        padrao = linha.lstrip("!").lstrip("/")
        if padrao in COBREM_DEMO or (negada and padrao.startswith("data/demo")):
            cobre = not negada
    return cobre


def problemas_do_manifesto_de_lotes(manifesto: dict, congelados: frozenset[str]) -> list[str]:
    """Nenhum caminho em dois lotes paralelos; nenhum caminho de lote congelado; as sobreposições com L0 são
    só os 21 esqueletos; o selo da fundação só cobre arquivos de L0 que não são de lote paralelo."""
    p = []
    lotes = manifesto.get("lotes", {})
    esperadas = {"L0", *LOTES_PARALELOS, "INT"}
    if manifesto.get("commit") != "049a8ac":
        p.append(f"commit {manifesto.get('commit')!r} (esperado '049a8ac')")
    if set(lotes) != esperadas:
        p.append(f"chaves dos lotes {sorted(lotes)} (esperadas {sorted(esperadas)})")
    dono: dict[str, str] = {}
    for chave, lista in lotes.items():
        if len(lista) != len(set(lista)):
            p.append(f"{chave}: caminho repetido na lista")
        for c in lista:
            if c.startswith(("/", "./")) or ".." in c.split("/") or "\\" in c:
                p.append(f"{chave}: caminho não relativo à raiz: {c}")
            if c in congelados:
                p.append(f"{chave}: {c} está no manifesto de congelados")
            if chave in LOTES_PARALELOS:
                if c in dono:
                    p.append(f"{c} aparece em {dono[c]} e em {chave}")
                dono[c] = chave
    esqueletos = [c for c in lotes.get("L0", []) if c in dono]
    vms = [c for c in esqueletos if c.startswith("cofre/qt/vm_") and c.endswith(".py")]
    qmls = [c for c in esqueletos if c.startswith(UI + "/") and c.endswith(".qml")]
    if len(vms) != 10 or len(qmls) != 11 or len(esqueletos) != 21:
        p.append(f"L0 ∩ lotes paralelos deveria ser os 21 esqueletos (10 VM, 11 QML): {sorted(esqueletos)}")
    fundacao = manifesto.get("fundacao_sha256")
    if not isinstance(fundacao, dict):
        p.append("fundacao_sha256 não é um dicionário")
    else:
        permitidos = {c for c in lotes.get("L0", []) if c not in dono and c != "tests/v2_lotes.json"}
        for c, sha in fundacao.items():
            if c not in permitidos:
                p.append(f"fundacao_sha256 cobre {c}, que não é arquivo completo da fundação")
            if not (isinstance(sha, str) and len(sha) == 64):
                p.append(f"fundacao_sha256 de {c} não é um SHA-256")
    return p


def linhas_originais_perdidas(caminho: str, texto: str, originais: list[str]) -> list[str]:
    atuais = texto.split("\n")
    casados = casar_originais(originais, atuais, TROCAVEIS.get(caminho, lambda linha: False))
    return [f"{caminho}: linha original {i + 1} sumiu ou saiu de ordem: {originais[i]!r}"
            for i, indice in enumerate(casados) if indice is None]


# ================================================================== testes no código do repositório

def _sem_violacoes(violacoes: list[str]) -> None:
    assert not violacoes, "\n" + "\n".join(violacoes)


def test_nada_novo_toca_na_decisao():
    _sem_violacoes(violacoes_decisao(_novas_e_acrescimos()))


def test_banco_so_por_leitura_ro():
    _sem_violacoes(violacoes_banco(_novas()))


def test_verde_so_para_concedido():
    _sem_violacoes(violacoes_verde(_novas_e_acrescimos()))


def test_ninguem_lista_fotos_ou_evidencias():
    _sem_violacoes(violacoes_fotos(_novas_e_acrescimos()))


def test_qml_estatico():
    _sem_violacoes(violacoes_qml_estatico(_novas_e_acrescimos()))


def test_atalhos_novos_respeitam_a_sobreposicao():
    _sem_violacoes(violacoes_atalhos(_novas()))


def test_laboratorio_nao_fala_em_autorizacao():
    _sem_violacoes(violacoes_autorizacao(_novas()))


def test_abrir_no_sistema_em_um_lugar_so():
    _sem_violacoes(violacoes_abrir_no_sistema(_novas()))


def test_modulos_declaram_a_fase():
    _sem_violacoes(violacoes_fase(_novas()))


def test_gitignore_cobre_demo():
    assert gitignore_cobre_demo((RAIZ / ".gitignore").read_text(encoding="utf-8")), ".gitignore não cobre data/demo/"


def test_manifesto_de_lotes_sem_arquivo_em_dois_lotes():
    if not MANIFESTO_LOTES.is_file():
        pytest.skip("tests/v2_lotes.json não existe (andaime apagado depois da entrega)")
    manifesto = json.loads(MANIFESTO_LOTES.read_text(encoding="utf-8"))
    _sem_violacoes(problemas_do_manifesto_de_lotes(manifesto, ARQUIVOS_CONGELADOS))


def test_edicoes_sao_so_acrescimos():
    perdidas = []
    for caminho, originais in ORIGINAIS.items():
        perdidas += linhas_originais_perdidas(caminho, (RAIZ / caminho).read_text(encoding="utf-8"), originais)
    _sem_violacoes(perdidas)


# ================================================================== cada regra pega a violação e poupa o limpo

def _caso(id_, regra, caminho, conteudo, pega):
    return pytest.param(regra, caminho, conteudo, pega, id=id_)


QMLV = f"{UI}/LabNovo.qml"
VM = "cofre/qt/vm_novo.py"
TEC = "cofre/tecnica_nova.py"
DOC_TEC = '"""Fase 4 (representação e descrição): teste."""\n'
TEMA_FALSO = {"sucesso", "sucessoSuave", "acento", "texto2", "corResultado", "aviso"}
ICONES_FALSOS = {"painel", "porta", "alerta", "ok"}


def _qml_estatico(lista):
    return violacoes_qml_estatico(lista, TEMA_FALSO, ICONES_FALSOS)


CASOS = [
    # T1
    _caso("t1-py-atributo", violacoes_decisao, VM, "def f(b):\n    b.registrar_acesso(x=1)\n", True),
    _caso("t1-py-nome-importado", violacoes_decisao, VM, "from cofre.autenticacao import decidir_acesso\n", True),
    _caso("t1-py-palavra-chave", violacoes_decisao, VM, "def f(T):\n    return T(liveness_ativo=False)\n", True),
    _caso("t1-py-getattr", violacoes_decisao, VM, "def f(t):\n    return getattr(t, '_bloqueado_ate')\n", True),
    _caso("t1-py-passo", violacoes_decisao, VM, "def f(term, q):\n    term.passo(q)\n", True),
    _caso("t1-py-sessao-abrir", violacoes_decisao, VM, "def f(a):\n    a.sessao_vm.abrir(None, 1)\n", True),
    _caso("t1-py-parametros-aplicar", violacoes_decisao, VM, "from cofre import parametros\nparametros.aplicar({})\n", True),
    _caso("t1-py-importa-aplicar", violacoes_decisao, VM, "from cofre.parametros import aplicar as ap\n", True),
    _caso("t1-py-config-atribuido", violacoes_decisao, VM, "from cofre import config\nconfig.LIMIAR_COSSENO = 0.1\n", True),
    _caso("t1-py-config-apelido", violacoes_decisao, VM, "from cofre import config as c\nx = c\nx.LIMIAR_COSSENO += 1\n", True),
    _caso("t1-py-setattr-config", violacoes_decisao, VM, "from cofre import config\nsetattr(config, 'LIVENESS_ATIVO', 0)\n", True),
    _caso("t1-py-comentario-grep", violacoes_decisao, VM, "# chama definirNivel no terminal\nx = 1\n", True),
    _caso("t1-py-limpo-palavra-maior", violacoes_decisao, VM,
          "def f(vm, config):\n    vm.definirNivelDemo(2)\n    p = vm.passos(1)\n    return config.LIMIAR_COSSENO == p\n", False),
    _caso("t1-py-teste-pode", violacoes_decisao, "tests/test_novo.py", "def test_x(t):\n    t.definirNivel(2)\n", False),
    _caso("t1-py-lancador-pastas", violacoes_decisao, "app_demo.py",
          "from cofre import config\nconfig.DATA_DIR = 1\nsetattr(config, 'DB_PATH', 2)\n", False),
    _caso("t1-py-lancador-outra", violacoes_decisao, "app_demo.py", "from cofre import config\nconfig.LIMIAR_COSSENO = 1\n", True),
    _caso("t1-py-lancador-setattr-calculado", violacoes_decisao, "app_demo.py",
          "from cofre import config\nfor n in ('DATA_DIR',):\n    setattr(config, n, 1)\n", True),
    _caso("t1-py-captura-pode", violacoes_decisao, "ferramentas/capturar_telas.py",
          "def f(t, b):\n    t.definirNivel(3)\n    t.definirLiveness(False)\n    b.registrar_acesso(x=1)\n", False),
    _caso("t1-py-captura-nao-pode-passo", violacoes_decisao, "ferramentas/capturar_telas.py", "def f(t, q):\n    t.passo(q)\n", True),
    _caso("t1-qml-nome", violacoes_decisao, QMLV, "Item { Component.onCompleted: app.terminal.definirLiveness(false) }\n", True),
    _caso("t1-qml-decisao", violacoes_decisao, QMLV, "Item { Connections { function onDecisaoTomada() {} } property var d: t.decisaoTomada }\n", True),
    _caso("t1-qml-passo", violacoes_decisao, QMLV, "Item { function f() { vm.passo (1) } }\n", True),
    _caso("t1-qml-config", violacoes_decisao, QMLV, "Item { function f() { app.config.LIMIAR = 1 } }\n", True),
    _caso("t1-qml-limpo", violacoes_decisao, QMLV,
          "Item { function f() { vm.definirNivelDemo(1); if (config.LIMIAR == 1) vm.passos(2) } }\n", False),
    _caso("t1-editavel-acrescimo", violacoes_decisao, f"{UI}/Main.qml",
          "Item {\n    id: janela\n    Keys.onPressed: app.terminal.definirNivel(2)\n}\n", True),
    _caso("t1-editavel-original-intacto", violacoes_decisao, f"{UI}/Main.qml",
          "Item {\n    id: janela\n    Botao { onClicked: t.definirNivel(1) }\n    Item { }\n}\n", False),
    # T2
    _caso("t2-banco", violacoes_banco, VM, "from cofre.banco import Banco\nb = Banco('x.db')\n", True),
    _caso("t2-banco-atributo", violacoes_banco, VM, "import cofre.banco as cb\nb = cb.Banco('x.db')\n", True),
    _caso("t2-sqlite", violacoes_banco, VM, "import sqlite3\ncon = sqlite3.connect('x.db')\n", True),
    _caso("t2-sqlite-importado", violacoes_banco, VM, "from sqlite3 import connect\n", True),
    _caso("t2-escrita", violacoes_banco, VM, "def f(app):\n    app.banco.remover_usuario(3)\n", True),
    _caso("t2-conexao-interna", violacoes_banco, VM, "def f(app):\n    app.banco._con.execute('DELETE FROM acessos')\n", True),
    _caso("t2-limpo", violacoes_banco, VM,
          "import sqlite3\nfrom cofre import leitura_ro\n\ndef f(app):\n    try:\n"
          "        return leitura_ro.consultar(app.banco.caminho, 'SELECT 1')\n    except sqlite3.Error:\n        return []\n", False),
    _caso("t2-base-demo-pode", violacoes_banco, "cofre/base_demo.py", "import sqlite3\nfrom cofre.banco import Banco\nb = Banco('x')\n", False),
    _caso("t2-leitura-ro-conecta", violacoes_banco, "cofre/leitura_ro.py", "import sqlite3\nc = sqlite3.connect('x')\n", False),
    _caso("t2-leitura-ro-nao-cria-banco", violacoes_banco, "cofre/leitura_ro.py", "from cofre.banco import Banco\nBanco('x')\n", True),
    _caso("t2-teste-pode", violacoes_banco, "tests/test_novo.py", "from cofre.banco import Banco\nb = Banco('x')\n", False),
    # T5
    _caso("t5-qml-verde", violacoes_verde, QMLV, "Rectangle { color: Theme.sucesso }\n", True),
    _caso("t5-qml-suave", violacoes_verde, QMLV, "Rectangle { color: ok ? Theme.sucessoSuave : Theme.aviso }\n", True),
    _caso("t5-qml-cor-resultado", violacoes_verde, QMLV, "Selo { cor: Theme.corResultado(vm.tipo) }\n", True),
    _caso("t5-qml-hex", violacoes_verde, QMLV, "Rectangle { color: \"#3DD68C\" }\n", True),
    _caso("t5-qml-resultado-concedido-nao-basta", violacoes_verde, QMLV,
          "Rectangle { color: t.resultadoConcedido ? Theme.sucesso : Theme.acento }\n", True),
    _caso("t5-qml-medidor", violacoes_verde, QMLV, "Item { Medidor { valor: 0.5 } }\n", True),
    _caso("t5-qml-notifica-ok", violacoes_verde, QMLV, "Item { function f() { app.notificar(\"ok\", \"Salvo\") } }\n", True),
    _caso("t5-qml-limpo", violacoes_verde, QMLV,
          "Item {\n    Rectangle { color: app.sessao.ativa ? Theme.sucesso : Theme.acento }\n"
          "    Selo { cor: Theme.corResultado(concedido ? \"CONCEDIDO\" : \"erro\") }\n"
          "    // Theme.sucesso só no comentário\n    Rectangle { color: Theme.acento }\n"
          "    function f() { app.notificar(\"info\", \"Salvo\") }\n}\n", False),
    _caso("t5-py-cor-concedido", violacoes_verde, VM, "SERIE = {'cor': 'concedido'}\n", True),
    _caso("t5-py-notifica-ok", violacoes_verde, VM, "def f(app):\n    app.notificar('ok', 'Pronto')\n", True),
    _caso("t5-py-dono-da-cor", violacoes_verde, "cofre/analitica.py", "SERIE = {'cor': 'concedido'}\n", False),
    _caso("t5-py-limpo", violacoes_verde, VM, "TIPO = 'CONCEDIDO'\n\ndef f(app):\n    app.notificar('info', 'Pronto')\n", False),
    # T8
    _caso("t8-fotos-dir", violacoes_fotos, VM, "from cofre import config\np = config.FOTOS_DIR\n", True),
    _caso("t8-evidencia-qml", violacoes_fotos, QMLV, "Image { source: vm.evidenciaUrl }\n", True),
    _caso("t8-fotos-do-usuario", violacoes_fotos, VM, "def f(b):\n    return b.fotos_do_usuario(1)\n", True),
    _caso("t8-caminho-literal", violacoes_fotos, VM, "from pathlib import Path\nP = Path('data/fotos')\n", True),
    _caso("t8-limpo", violacoes_fotos, VM,
          "from cofre import config\np = config.RELATORIOS_DIR\nq = 'FOTOS_DIRETAS'\n\ndef evidencias_ausentes():\n    return 0\n", False),
    _caso("t8-dono", violacoes_fotos, "cofre/base_demo.py", "from cofre import config\np = config.FOTOS_DIR\n", False),
    # T13
    _caso("t13-multieffect", _qml_estatico, QMLV, "import QtQuick.Effects\nItem { MultiEffect { } }\n", True),
    _caso("t13-layer-effect", _qml_estatico, QMLV, "Item { layer.enabled: true; layer.effect: Item { } }\n", True),
    _caso("t13-shader", _qml_estatico, QMLV, "Item { ShaderEffect { } }\n", True),
    _caso("t13-sombra", _qml_estatico, QMLV, "Item { RectangularShadow { } }\n", True),
    _caso("t13-particula", _qml_estatico, QMLV, "Item { ImageParticle { } }\n", True),
    _caso("t13-settings", _qml_estatico, QMLV, "import QtCore\nItem { Settings { property int x: 1 } }\n", True),
    _caso("t13-console", _qml_estatico, QMLV, "Item { Component.onCompleted: console.log(\"oi\") }\n", True),
    _caso("t13-theme-inexistente", _qml_estatico, QMLV, "Rectangle { color: Theme.verdeLimao }\n", True),
    _caso("t13-icone-inexistente", _qml_estatico, QMLV, "Botao { icone: \"foguete\" }\n", True),
    _caso("t13-icone-ternario", _qml_estatico, QMLV, "Botao { icone: vm.ok ? \"ok\" : \"foguete\" }\n", True),
    _caso("t13-icone-bloco", _qml_estatico, QMLV, "Item { Icone { tamanho: 14; nome: \"foguete\" } }\n", True),
    _caso("t13-icone-caminho", _qml_estatico, QMLV, "Item { property string p: Icones.caminho(\"foguete\") }\n", True),
    _caso("t13-icone-modelo-py", _qml_estatico, VM, "ITENS = [{'id': 'a', 'icone': 'foguete'}]\n", True),
    _caso("t13-limpo", _qml_estatico, QMLV,
          "Item {\n    // MultiEffect e console.log só no comentário\n    Rectangle { color: Theme.acento }\n"
          "    Botao { icone: vm.ok ? \"ok\" : \"alerta\"; text: \"Configurações\" }\n"
          "    EstadoBloco { vazioIcone: \"painel\"; vazioTitulo: \"Settings\" }\n"
          "    Icone { nome: \"porta\"; cor: \"#ffffff\" }\n"
          "    property var itens: [{ id: \"a\", texto: \"Painel\", icone: \"painel\", grupo: \"Análise\" }]\n"
          "    property color corIcone: \"#35d0c0\"\n    property string iconeAcao: \"\"\n}\n", False),
    _caso("t13-icone-condicao-nao-conta", _qml_estatico, QMLV,
          "Item { Icone { nome: a.tipo === \"aviso\" ? \"alerta\" : (a.tipo !== \"x\" ? \"ok\" : \"painel\") } }\n", False),
    _caso("t13-limpo-py", _qml_estatico, VM, "ITENS = [{'id': 'a', 'icone': 'porta'}, {'icone': ''}]\n", False),
    # T9 (atalhos)
    _caso("t9-atalho-sem-guarda", violacoes_atalhos, QMLV, "Item { Shortcut { sequence: \"Ctrl+K\"; onActivated: f() } }\n", True),
    _caso("t9-atalho-guarda-errada", violacoes_atalhos, QMLV,
          "Item { Shortcut { sequence: \"Ctrl+K\"; enabled: app.v2.sobreposicaoAberta } }\n", True),
    _caso("t9-atalho-guarda-com-ou", violacoes_atalhos, QMLV,
          "Item { Shortcut { sequence: \"Ctrl+K\"; enabled: vm.pronto || !app.v2.sobreposicaoAberta } }\n", True),
    _caso("t9-atalho-guarda-dupla-negacao", violacoes_atalhos, QMLV,
          "Item { Shortcut { sequence: \"Ctrl+K\"; enabled: !!app.v2.sobreposicaoAberta } }\n", True),
    _caso("t9-atalho-limpo-parenteses", violacoes_atalhos, QMLV,
          "Item { Shortcut { sequence: \"Ctrl+K\"; enabled: (a || b) && (!app.v2.sobreposicaoAberta) } }\n", False),
    _caso("t9-atalho-limpo", violacoes_atalhos, QMLV,
          "Item {\n    Shortcut {\n        sequence: \"Ctrl+K\"\n        enabled: !app.sessao.ativa && ! app.v2.sobreposicaoAberta\n"
          "        onActivated: { f() }\n    }\n}\n", False),
    # T14
    _caso("t14-qml", violacoes_autorizacao, QMLV, "Text { text: \"Acesso concedido\" }\n", True),
    _caso("t14-qml-maiusculas", violacoes_autorizacao, f"{UI}/ResultadosPagina.qml", "Text { text: \"NEGADOS: \" + n }\n", True),
    _caso("t14-py", violacoes_autorizacao, "cofre/qt/vm_res_nova.py", "ROTULO = 'Pessoas autorizadas'\n", True),
    _caso("t14-tecnica", violacoes_autorizacao, "cofre/metricas.py", "def f(n):\n    return f'{n} negado'\n", True),
    _caso("t14-limpo", violacoes_autorizacao, QMLV,
          "Item {\n    // nada de concedido aqui: só no comentário\n    Text { text: \"Acima do limiar em vigor\" }\n"
          "    Text { text: \"Autorização\"; visible: vm.negacao }\n}\n", False),
    _caso("t14-limpo-docstring", violacoes_autorizacao, "cofre/qt/vm_lab_novo.py",
          '"""Aba que nunca diz concedido nem negado."""\nROTULO = "Similaridade"\n', False),
    _caso("t14-fora-do-laboratorio", violacoes_autorizacao, f"{UI}/PainelNovo.qml", "Text { text: \"Concedido\" }\n", False),
    # T15
    _caso("t15-qdesktop-fora", violacoes_abrir_no_sistema, VM,
          "from PySide6.QtGui import QDesktopServices\nQDesktopServices.openUrl(1)\n", True),
    _caso("t15-importa-pelo-nome", violacoes_abrir_no_sistema, VM, "from cofre.qt.vm_figuras import abrir_no_sistema\n", True),
    _caso("t15-teste-importa-pelo-nome", violacoes_abrir_no_sistema, "tests/test_novo.py",
          "from cofre.qt.vm_figuras import abrir_no_sistema as a\n", True),
    _caso("t15-webbrowser", violacoes_abrir_no_sistema, VM, "import webbrowser\nwebbrowser.open('x')\n", True),
    _caso("t15-startfile", violacoes_abrir_no_sistema, VM, "import os\nos.startfile('x')\n", True),
    _caso("t15-qml", violacoes_abrir_no_sistema, QMLV, "Item { function f() { Qt.openUrlExternally(\"file:///x\") } }\n", True),
    _caso("t15-dono-fora-da-funcao", violacoes_abrir_no_sistema, DONO_DO_ABRIR,
          "from PySide6.QtGui import QDesktopServices\n\ndef abrir_no_sistema(caminho):\n"
          "    QDesktopServices.openUrl(caminho)\n\nX = QDesktopServices\n", True),
    _caso("t15-dono-sem-funcao", violacoes_abrir_no_sistema, DONO_DO_ABRIR, "def abrir(caminho):\n    return caminho\n", True),
    _caso("t15-limpo", violacoes_abrir_no_sistema, VM,
          "from cofre.qt import vm_figuras\n\ndef abrir(p):\n    vm_figuras.abrir_no_sistema(p)\n", False),
    _caso("t15-dono-limpo", violacoes_abrir_no_sistema, DONO_DO_ABRIR,
          "from PySide6.QtCore import QUrl\nfrom PySide6.QtGui import QDesktopServices\n\n"
          "def abrir_no_sistema(caminho):\n    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho)))\n", False),
    # 4.3
    _caso("fase-sem-docstring", violacoes_fase, TEC, "X = 1\n", True),
    _caso("fase-errada", violacoes_fase, TEC, '"""Fase 6: nada."""\n', True),
    _caso("fase-sem-texto", violacoes_fase, TEC, '"""Fases 1 a 4:"""\n', True),
    _caso("fase-limpa", violacoes_fase, TEC, DOC_TEC, False),
    _caso("fase-apoio", violacoes_fase, TEC, '"""Apoio (apresentação; não é fase do PDI): passos."""\n', False),
    _caso("fase-fora-do-alcance", violacoes_fase, VM, "X = 1\n", False),
]


@pytest.mark.parametrize("regra,caminho,conteudo,pega", CASOS)
def test_regra_pega_e_poupa(tmp_path, regra, caminho, conteudo, pega):
    arquivo = tmp_path / caminho
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(conteudo, encoding="utf-8")
    originais = {f"{UI}/Main.qml": ["Item {", "    id: janela", "    Botao { onClicked: t.definirNivel(1) }", "}"]}
    violacoes = regra(fontes([caminho], raiz=tmp_path, originais=originais))
    if pega:
        assert violacoes, f"a regra deixou passar:\n{conteudo}"
    else:
        assert violacoes == [], violacoes


def test_varredura_ve_todos_os_novos_e_respeita_o_lote(monkeypatch):
    novos = caminhos_novos()
    monkeypatch.delenv("COFRE_V2_LOTE", raising=False)
    todos = caminhos_novos()
    assert "tests/test_v2_principios.py" in todos and "cofre/leitura_ro.py" in todos
    assert not set(todos) & (ARQUIVOS_CONGELADOS | EDITAVEIS)
    assert set(novos) <= set(todos)
    if MANIFESTO_LOTES.is_file():
        monkeypatch.setenv("COFRE_V2_LOTE", "L8")
        do_l8 = caminhos_novos()
        lista = json.loads(MANIFESTO_LOTES.read_text(encoding="utf-8"))["lotes"]["L8"]
        assert set(do_l8) <= set(lista) and caminhos_editados() == []


def test_gitignore_pega_e_poupa():
    assert gitignore_cobre_demo("data/cofre.db\ndata/demo/\n")
    assert gitignore_cobre_demo("/data/\n")
    assert not gitignore_cobre_demo("data/cofre.db\ndata/fotos/\n")
    assert not gitignore_cobre_demo("# data/demo/\n")
    assert not gitignore_cobre_demo("data/demo/\n!data/demo/\n")


def _manifesto_valido() -> dict:
    vms = [f"cofre/qt/vm_aba{i}.py" for i in range(10)]
    qmls = [f"{UI}/Aba{i}.qml" for i in range(11)]
    paralelos = {chave: [] for chave in LOTES_PARALELOS}
    for i, c in enumerate(vms + qmls):
        paralelos[LOTES_PARALELOS[i % len(LOTES_PARALELOS)]].append(c)
    paralelos["L3"].append("cofre/fases_lab.py")
    return {"commit": "049a8ac",
            "lotes": {"L0": ["cofre/leitura_ro.py", "tests/v2_lotes.json", *vms, *qmls], **paralelos,
                      "INT": ["cofre/roteiro.py", "cofre/fases_lab.py"]},
            "fundacao_sha256": {"cofre/leitura_ro.py": "0" * 64}}


def test_manifesto_de_lotes_pega_e_poupa():
    assert problemas_do_manifesto_de_lotes(_manifesto_valido(), frozenset({"cofre/banco.py"})) == []
    em_dois = _manifesto_valido()
    em_dois["lotes"]["L4"].append("cofre/fases_lab.py")
    assert any("aparece em L3 e em L4" in p for p in problemas_do_manifesto_de_lotes(em_dois, frozenset()))
    congelado = _manifesto_valido()
    congelado["lotes"]["L7"].append("cofre/banco.py")
    assert any("congelados" in p for p in problemas_do_manifesto_de_lotes(congelado, frozenset({"cofre/banco.py"})))
    selo_de_lote = _manifesto_valido()
    selo_de_lote["fundacao_sha256"]["cofre/qt/vm_aba0.py"] = "1" * 64
    assert any("fundacao_sha256 cobre" in p for p in problemas_do_manifesto_de_lotes(selo_de_lote, frozenset()))
    sem_esqueleto = _manifesto_valido()
    sem_esqueleto["lotes"]["L0"].remove(f"{UI}/Aba3.qml")
    assert any("21 esqueletos" in p for p in problemas_do_manifesto_de_lotes(sem_esqueleto, frozenset()))


def test_edicoes_so_acrescimos_pega_e_poupa():
    originais = ["import x", 'PAGINAS = ("terminal", "config")', "", "class A:", "    pass"]
    acrescido = "import x\nfrom .extensoes import PAGINAS_V2\nPAGINAS = (\"terminal\", \"config\") + PAGINAS_V2\n\nclass A:\n    v2 = 1\n    pass"
    assert linhas_originais_perdidas("cofre/qt/aplicacao.py", acrescido, originais) == []
    trocada_errada = acrescido.replace('"config") + PAGINAS_V2', '"cfg") + PAGINAS_V2')
    assert linhas_originais_perdidas("cofre/qt/aplicacao.py", trocada_errada, originais)
    fora_de_ordem = "import x\nPAGINAS = (\"terminal\", \"config\")\n\n    pass\nclass A:"
    assert linhas_originais_perdidas("cofre/qt/aplicacao.py", fora_de_ordem, originais)
    # só as três linhas nomeadas podem ganhar conteúdo: qualquer outra mudada é perda
    assert linhas_originais_perdidas("cofre/qt/app.py", acrescido, originais)
    visivel = so_acrescimos("cofre/qt/aplicacao.py", acrescido, originais).split("\n")
    assert visivel == ["", "from .extensoes import PAGINAS_V2", 'PAGINAS = ("terminal", "config") + PAGINAS_V2',
                       "", "", "    v2 = 1", ""]


# ================================================================== o portão dos lotes (lógica, sem rodar a suíte)

def _portao():
    if not PORTAO.is_file():
        pytest.skip("ferramentas/portao_lote.py não existe (andaime apagado depois da entrega)")
    # carregado sem importar (nem gravar bytecode): ferramentas/ não é pacote e não ganha __pycache__
    modulo = types.ModuleType("portao_lote_em_teste")
    modulo.__file__ = str(PORTAO)
    exec(compile(PORTAO.read_text(encoding="utf-8"), str(PORTAO), "exec"), modulo.__dict__)
    return modulo


def _saida_pytest(*falhas: tuple[str, str]) -> str:
    """Uma saída do `pytest -q` com as seções de falha e o resumo curto."""
    partes = ["..F.F", "=================================== FAILURES ==================================="]
    for no, corpo in falhas:
        partes += [f"________________________ {no.split('::', 1)[1]} ________________________", corpo]
    partes.append("=========================== short test summary info ============================")
    partes += [f"FAILED {no} - AssertionError" for no, _ in falhas]
    partes.append(f"{len(falhas)} failed, 3 passed in 1.23s")
    return "\n".join(partes) + "\n"


def test_portao_classifica_falha_propria_e_alheia():
    p = _portao()
    raiz = "/repo/cofre-v2"
    congelados = {"arquivos": {"tests/test_qt_app.py": "x", "tests/test_areas.py": "x", "cofre/qt/vm_terminal.py": "y"}}
    cena = f"{UI}/CenaAbertura.qml"
    saida = _saida_pytest(
        ("tests/test_qt_app.py::test_navega", f"E   AssertionError: avisos\n{raiz}/{cena}:12:5: QML Item: Binding loop\n"
                                              f"{raiz}/tests/test_qt_app.py:97: AssertionError"),
        ("tests/test_qt_app.py::test_terminal", f"{raiz}/cofre/qt/vm_terminal.py:40: TimeoutError\n"
                                                f"{raiz}/.venv/lib/python3.14/site-packages/x.py:3: in f"))
    proprias, alheias, citados = p.classificar_falhas(saida, ["cofre/qt/vm_quiosque.py", cena], congelados, raiz)
    assert proprias == ["tests/test_qt_app.py::test_navega"]
    assert alheias == ["tests/test_qt_app.py::test_terminal"]
    assert citados == ["tests/test_qt_app.py"]          # só cita congelado: fica o arquivo do teste
    proprias, alheias, citados = p.classificar_falhas(saida, ["cofre/fases_lab.py"], congelados, raiz)
    assert proprias == [] and len(alheias) == 2 and citados == [cena, "tests/test_qt_app.py"]
    # pelo nome do módulo, com fronteira de nome: cofre.qualidade_erc não é cofre.qualidade
    saida_modulo = _saida_pytest(("tests/test_areas.py::test_a", "ModuleNotFoundError: No module named 'cofre.qualidade_erc'"))
    assert p.classificar_falhas(saida_modulo, ["cofre/qualidade.py"], congelados, raiz)[0] == []
    assert p.classificar_falhas(saida_modulo, ["cofre/qualidade_erc.py"], congelados, raiz)[0] == ["tests/test_areas.py::test_a"]
    # traceback do pytest cita o caminho relativo: entra na lista de citados da falha alheia
    saida_relativa = _saida_pytest(("tests/test_areas.py::test_b", "cofre/qt/vm_res_galeria.py:12: in recarregar\nE  ValueError"))
    assert p.classificar_falhas(saida_relativa, ["cofre/fases_lab.py"], congelados, raiz)[2] == ["cofre/qt/vm_res_galeria.py"]
    # processo abortado sem teste identificado: não há como inocentar o lote
    assert p.classificar_falhas("Fatal Python error: Aborted\n", ["cofre/x.py"], congelados, raiz)[0]
    assert p.resumo_do_pytest(saida) == "2 failed, 3 passed in 1.23s"


def test_portao_le_o_git_status():
    p = _portao()
    linhas = [" M cofre/qt/app.py", "?? tests/v2_lotes.json", 'R  velho.py -> "novo com espaço.py"',
              '?? "a\\"b.qml"', "?? data/demo/x.db"]
    caminhos = p.caminhos_do_status(linhas)
    assert caminhos == ["cofre/qt/app.py", "tests/v2_lotes.json", "novo com espaço.py", 'a"b.qml', "data/demo/x.db"]
    assert p.sobras(caminhos, {"cofre/qt/app.py", "tests/v2_lotes.json", 'a"b.qml'}) == ["data/demo/x.db", "novo com espaço.py"]


def test_portao_trava_e_exclusiva(tmp_path):
    p = _portao()
    import fcntl
    caminho = str(tmp_path / "trava.lock")
    saida = io.StringIO()
    with p.Trava(caminho, saida):
        fd = os.open(caminho, os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
        liberada = threading.Event()
        entrou: list[float] = []

        def segundo():
            with p.Trava(caminho, saida):
                entrou.append(time.monotonic())
            liberada.set()

        fio = threading.Thread(target=segundo)
        fio.start()
        time.sleep(0.3)
        assert entrou == [], "a segunda trava entrou com a primeira ainda pega"
        soltou = time.monotonic()
    assert liberada.wait(5) and entrou[0] >= soltou
    fio.join(5)
    assert "aguardando a vez" in saida.getvalue()


def _repo_falso(tmp_path: Path, selado: bool = True) -> dict:
    """Um repositório mínimo para o portão: manifestos, um teste antigo, a fundação e o lote L4."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "cofre" / "qt").mkdir(parents=True)
    arquivos = {"tests/test_antigo.py": "def test_a(): pass\n", "cofre/leitura_ro.py": "X = 1\n",
                "cofre/robustez.py": "Y = 2\n", "cofre/qt/vm_lab_robustez.py": "Z = 3\n",
                "tests/test_v2_robustez.py": "def test_r(): pass\n"}
    for caminho, texto in arquivos.items():
        (tmp_path / caminho).write_text(texto, encoding="utf-8")
    congelados = {"commit": "049a8ac", "arquivos": {"tests/test_antigo.py": "0" * 64}, "editaveis": {}}
    lotes = {"commit": "049a8ac",
             "lotes": {"L0": ["cofre/leitura_ro.py", "cofre/qt/vm_lab_robustez.py", "tests/v2_lotes.json"],
                       **{c: [] for c in LOTES_PARALELOS}, "INT": ["cofre/roteiro.py"]},
             "fundacao_sha256": {}}
    lotes["lotes"]["L4"] = ["cofre/robustez.py", "cofre/qt/vm_lab_robustez.py", "tests/test_v2_robustez.py"]
    if selado:
        lotes["fundacao_sha256"] = {"cofre/leitura_ro.py": hashlib.sha256(b"X = 1\n").hexdigest()}
    (tmp_path / "tests" / "v2_congelados.json").write_text(json.dumps(congelados), encoding="utf-8")
    (tmp_path / "tests" / "v2_lotes.json").write_text(json.dumps(lotes), encoding="utf-8")
    return lotes


class _PytestFalso:
    """Devolve, em ordem, os resultados pedidos e anota cada chamada (argumentos e lote dos estáticos)."""

    def __init__(self, modulo, *resultados):
        self.modulo = modulo
        self.resultados = list(resultados)
        self.chamadas: list[tuple[list[str], str | None]] = []

    def __call__(self, argumentos, lote_estatico=None):
        self.chamadas.append((list(argumentos), lote_estatico))
        codigo, saida = self.resultados.pop(0) if self.resultados else (0, "1 passed in 0.01s\n")
        return self.modulo.Resultado(codigo, saida, 0.01)


def _rodar_portao(p, tmp_path, lote, pytest_falso, status=()):
    saida, pausas = io.StringIO(), []
    portao = p.Portao(str(tmp_path), pytest=pytest_falso, git=lambda argumentos: list(status),
                      dormir=pausas.append, caminho_trava=str(tmp_path / "trava.lock"), saida=saida)
    return portao.executar(lote), saida.getvalue(), pausas


def test_portao_de_lote_codigos_de_saida(tmp_path):
    p = _portao()
    _repo_falso(tmp_path)
    alheia = (1, _saida_pytest(("tests/test_antigo.py::test_a", f"{tmp_path}/{UI}/CenaAbertura.qml:3: aviso")))
    propria = (1, _saida_pytest(("tests/test_antigo.py::test_a", f"{tmp_path}/cofre/robustez.py:2: ValueError")))

    falso = _PytestFalso(p)
    codigo, texto, pausas = _rodar_portao(p, tmp_path, "L4", falso, status=["?? cofre/robustez.py"])
    assert codigo == p.PASSOU and "PORTAO L4: OK" in texto and "?? cofre/robustez.py" in texto and pausas == []
    assert falso.chamadas[0] == (["tests/test_v2_robustez.py"], None)
    assert falso.chamadas[1] == (["tests/test_v2_principios.py", "tests/test_v2_congelados.py"], "L4")
    assert falso.chamadas[2] == (["tests/test_antigo.py"], None)

    codigo, texto, _ = _rodar_portao(p, tmp_path, "L4", _PytestFalso(p, (1, "1 failed in 0.1s\n")))
    assert codigo == p.FALHOU and "PORTAO L4: FALHOU no passo 3" in texto

    codigo, texto, _ = _rodar_portao(p, tmp_path, "L4", _PytestFalso(p, (0, ""), (1, "1 failed in 0.1s\n")))
    assert codigo == p.FALHOU and "FALHOU no passo 4" in texto

    codigo, texto, pausas = _rodar_portao(p, tmp_path, "L4", _PytestFalso(p, (0, ""), (0, ""), alheia, alheia))
    assert codigo == p.PENDENTE and pausas == [p.ESPERA_REPETICAO_S]
    assert f"PORTAO L4: PENDENTE (falha alheia em {UI}/CenaAbertura.qml)" in texto

    codigo, texto, _ = _rodar_portao(p, tmp_path, "L4", _PytestFalso(p, (0, ""), (0, ""), alheia, (0, "")))
    assert codigo == p.PASSOU, "a segunda tentativa passou: o portão segue"

    codigo, texto, _ = _rodar_portao(p, tmp_path, "L4", _PytestFalso(p, (0, ""), (0, ""), propria, propria))
    assert codigo == p.FALHOU and "falha própria: tests/test_antigo.py::test_a" in texto and "FALHOU no passo 5" in texto

    (tmp_path / "cofre" / "leitura_ro.py").write_text("X = 2\n", encoding="utf-8")
    codigo, texto, _ = _rodar_portao(p, tmp_path, "L4", _PytestFalso(p))
    assert codigo == p.FALHOU and "FALHOU no passo 2" in texto and "cofre/leitura_ro.py (relate, não conserte)" in texto

    (tmp_path / "cofre" / "robustez.py").unlink()
    codigo, texto, _ = _rodar_portao(p, tmp_path, "L4", _PytestFalso(p))
    assert codigo == p.FALHOU and "FALHOU no passo 1" in texto and "cofre/robustez.py: não existe" in texto


def test_portao_recusa_lote_sem_fundacao_selada_ou_com_congelado(tmp_path):
    p = _portao()
    lotes = _repo_falso(tmp_path, selado=False)
    codigo, texto, _ = _rodar_portao(p, tmp_path, "L4", _PytestFalso(p))
    assert codigo == p.FALHOU and "fundação ainda não selada" in texto
    lotes["lotes"]["L4"].append("tests/test_antigo.py")
    (tmp_path / "tests" / "v2_lotes.json").write_text(json.dumps(lotes), encoding="utf-8")
    codigo, texto, _ = _rodar_portao(p, tmp_path, "L4", _PytestFalso(p))
    assert codigo == p.FALHOU and "tests/test_antigo.py: está no manifesto de congelados" in texto


def test_portao_da_fundacao_e_da_integracao(tmp_path):
    p = _portao()
    _repo_falso(tmp_path)
    falso = _PytestFalso(p)
    codigo, texto, _ = _rodar_portao(p, tmp_path, "L0", falso, status=["?? cofre/leitura_ro.py"])
    assert codigo == p.PASSOU and "PORTAO L0: OK" in texto
    assert [c for c, _ in falso.chamadas] == [["tests"]] * 3

    codigo, texto, _ = _rodar_portao(p, tmp_path, "L0", _PytestFalso(p, (0, ""), (1, "1 failed in 1s\n")))
    assert codigo == p.FALHOU and "FALHOU no passo 2" in texto and "execução 2" in texto

    codigo, texto, _ = _rodar_portao(p, tmp_path, "L0", _PytestFalso(p), status=["?? solto.py"])
    assert codigo == p.FALHOU and "FALHOU no passo 3" in texto and "solto.py" in texto

    falso = _PytestFalso(p)
    codigo, texto, _ = _rodar_portao(p, tmp_path, "INT", falso, status=[" M cofre/roteiro.py"])
    assert codigo == p.PASSOU and [c for c, _ in falso.chamadas] == [["tests"], ["tests"], ["tests", "--durations=10"]]
    codigo, texto, _ = _rodar_portao(p, tmp_path, "INT", _PytestFalso(p), status=["?? solto.py"])
    assert codigo == p.FALHOU and "FALHOU no passo 1" in texto


def test_portao_sela_a_fundacao(tmp_path):
    p = _portao()
    _repo_falso(tmp_path, selado=False)
    saida = io.StringIO()
    assert p.selar_fundacao(str(tmp_path), saida) == p.PASSOU
    selado = json.loads((tmp_path / "tests" / "v2_lotes.json").read_text(encoding="utf-8"))["fundacao_sha256"]
    # vm_lab_robustez.py é esqueleto (também está em L4) e o próprio manifesto fica de fora
    assert selado == {"cofre/leitura_ro.py": hashlib.sha256(b"X = 1\n").hexdigest()}
    assert [c.name for c in (tmp_path / "tests").iterdir() if c.name.startswith(".v2_lotes.")] == []
    (tmp_path / "cofre" / "leitura_ro.py").unlink()
    antes = (tmp_path / "tests" / "v2_lotes.json").read_bytes()
    assert p.selar_fundacao(str(tmp_path), saida) == p.FALHOU
    assert (tmp_path / "tests" / "v2_lotes.json").read_bytes() == antes
