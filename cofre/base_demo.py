"""Apoio (dados de demonstração; não é fase do PDI): gerador e marcador da base de demonstração.

A base de demonstração é um banco separado (`data/demo/cofre_demo.db`, com as suas próprias pastas
de fotos, evidências e relatórios) para apresentar o aplicativo sem tocar nos dados reais:

  * as duas pessoas cadastradas são os dois retratos de domínio público das fotos de teste, pelo
    caminho normal de cadastro do núcleo (os mesmos vetores que o terminal compara);
  * o histórico é fictício, gravado direto no arquivo com datas passadas, seguindo linha a linha as
    regras do terminal (limiar, níveis, bloqueio por tentativas). Cada linha fictícia começa com
    `MARCA_MENSAGEM` e não tem evidência;
  * o arquivo leva um marcador (tabela `demonstracao` e `PRAGMA application_id`), que é como o
    aplicativo reconhece a base e mostra o selo "Base de demonstração".

O gerador recusa o banco real, recusa escrever fora da raiz combinada e recusa rodar enquanto as
pastas de `config` não apontarem para a raiz da base (o cadastro grava os recortes em
`config.FOTOS_DIR`). Quem chama troca as cinco variáveis de `VARIAVEIS` antes: o `app_demo.py`
faz isso e restaura no fim.
"""

from __future__ import annotations

import os
import random
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from . import amostra_lab, config, leitura_ro
from .banco import Banco
from .cadastro import DadosCadastro, cadastrar_de_imagens
from .fase5_reconhecimento import Resultado
from .liveness import ControleTentativas
from .pipeline import Pipeline

APPLICATION_ID = 0x434D4D44                               # "CMMD", gravado em PRAGMA application_id
RAIZ_PADRAO = config.BASE_DIR / "data" / "demo"           # calculado de BASE_DIR, não de DATA_DIR (que pode ser trocado)
BANCO_REAL = (config.BASE_DIR / "data" / "cofre.db").resolve()
MARCA_MENSAGEM = "[demonstração] "
VARIAVEIS = ("DATA_DIR", "DB_PATH", "FOTOS_DIR", "EVIDENCIAS_DIR", "RELATORIOS_DIR")
VERSAO = 1                                                # formato da base; vai para o marcador
PREFIXO_MATRICULA = "DEMO-"

# (nome, matrícula, cargo, nível) de cada pessoa de teste, na ordem de `amostra_lab.fotos_de_teste()`
IDENTIDADES = (
    ("Retrato público 1 (demonstração)", "DEMO-001", "Ministro (demonstração)", 3),
    ("Retrato público 2 (demonstração)", "DEMO-002", "Diretor (demonstração)", 2),
)
FOTOS_POR_IDENTIDADE = 2

_PASTAS_APAGAVEIS = ("FOTOS_DIR", "EVIDENCIAS_DIR", "RELATORIOS_DIR")
_TENTATIVAS_DIA_UTIL = (15, 40)
_TENTATIVAS_FIM_DE_SEMANA = (0, 4)
_FAIXAS_DO_DIA = ((8, 11), (13, 15), (7, 19))            # horas; as duas primeiras são os picos
_PESOS_DAS_FAIXAS = (55, 25, 20)
_MISTURA = (                                              # proporção aproximada das tentativas sorteadas
    (Resultado.CONCEDIDO, 55), (Resultado.NEGADO_DESCONHECIDO, 20), (Resultado.NEGADO_LIVENESS, 10),
    (Resultado.NEGADO_NIVEL, 8), (Resultado.NEGADO_MULTIPLOS, 2),
)
# tipo das negações de cada bloqueio plantado, em rodízio
_EPISODIOS = (Resultado.NEGADO_DESCONHECIDO, Resultado.NEGADO_NIVEL, Resultado.NEGADO_LIVENESS)
_MIN_EPISODIOS = 3
_HORAS_DE_EPISODIO = (9, 14, 10, 16, 8, 11, 13, 15, 17)  # a hora muda com o dia; episódios do mesmo dia nunca repetem
_PASSO_SEG = 5                                            # segundos entre duas tentativas, no mínimo
_SQL_ACESSO = """INSERT INTO acessos (data_hora, usuario_id, nome_detectado, nivel_usuario, nivel_exigido, area,
                                      similaridade, resultado, mensagem, evidencia)
                 VALUES (?,?,?,?,?,?,?,?,?,NULL)"""


class RecusaBaseDemo(RuntimeError):
    """O gerador se recusou a criar ou refazer a base (nada foi escrito)."""


def pastas(raiz: Path | None = None) -> dict[str, Path]:
    """Os valores das cinco variáveis de `config` para uma raiz (a padrão é `data/demo`)."""
    raiz = Path(raiz) if raiz is not None else RAIZ_PADRAO
    return {"DATA_DIR": raiz, "DB_PATH": raiz / "cofre_demo.db", "FOTOS_DIR": raiz / "fotos",
            "EVIDENCIAS_DIR": raiz / "evidencias", "RELATORIOS_DIR": raiz / "relatorios"}


def caminho_banco(raiz: Path | None = None) -> Path:
    """Arquivo do banco de demonstração dentro da raiz."""
    return pastas(raiz)["DB_PATH"]


def marcador(caminho: str | Path) -> dict | None:
    """O que o gerador anotou na base (`gerado_em`, `semente`, `dias`, `versao`, todos em texto), lido
    em modo somente leitura. None se o arquivo não for uma base de demonstração."""
    if not leitura_ro.eh_base_demonstracao(caminho):
        return None
    try:
        linhas = leitura_ro.consultar(caminho, "SELECT chave, valor FROM demonstracao ORDER BY chave")
    except (leitura_ro.BancoIndisponivel, sqlite3.Error):
        return None
    return {linha["chave"]: linha["valor"] for linha in linhas}


def gerar(raiz: Path | None = None, *, dias: int = 30, semente: int = 7, recriar: bool = False,
          apagar_cadastros: bool = False, raiz_permitida: Path | None = None, pipeline=None,
          agora: datetime | None = None) -> Path:
    """Cria a base de demonstração na raiz e devolve o caminho do banco.

    Se a base já existe (arquivo com o marcador), devolve o caminho sem mexer; com `recriar`, apaga o
    banco e as pastas de fotos, evidências e relatórios dessa raiz e gera de novo. O histórico cobre
    `dias` dias terminando na véspera de `agora` e depende só de `semente`, `dias` e dessa data.
    Toda recusa levanta `RecusaBaseDemo` antes de escrever qualquer coisa."""
    raiz = Path(raiz) if raiz is not None else RAIZ_PADRAO
    alvo = pastas(raiz)
    caminho = alvo["DB_PATH"]
    _conferir_destino(raiz, alvo, raiz_permitida)
    if dias < 1:
        raise ValueError("dias precisa ser pelo menos 1")
    if caminho.exists():
        if marcador(caminho) is None:
            raise RecusaBaseDemo(f"{caminho} existe e não é uma base de demonstração (não tem o marcador). "
                                 "Nada foi alterado.")
        if not recriar:
            return caminho
        _conferir_cadastros(caminho, alvo, apagar_cadastros)
    fotos = _fotos_das_identidades()
    if caminho.exists():
        _apagar(alvo)
    _criar(alvo, fotos, dias, semente, pipeline, agora if agora is not None else datetime.now())
    return caminho


# ---------------------------------------------------------------------------- recusas
def _conferir_destino(raiz: Path, alvo: dict[str, Path], raiz_permitida: Path | None) -> None:
    """As três recusas que não dependem do que já existe na raiz."""
    raiz_real = raiz.resolve()
    if alvo["DB_PATH"].resolve() == BANCO_REAL or raiz_real == BANCO_REAL.parent:
        raise RecusaBaseDemo("A base de demonstração nunca é criada na pasta do banco real (data/).")
    permitida = Path(raiz_permitida).resolve() if raiz_permitida is not None else raiz_real
    if not raiz_real.is_relative_to(permitida):
        raise RecusaBaseDemo(f"A raiz {raiz_real} fica fora da pasta permitida ({permitida}).")
    for nome in _PASTAS_APAGAVEIS:
        if Path(getattr(config, nome)).resolve() != alvo[nome].resolve():
            raise RecusaBaseDemo(
                f"config.{nome} não aponta para a base de demonstração ({alvo[nome]}): o cadastro gravaria "
                "fora dela. Abra pelo app_demo.py, que troca as pastas antes de gerar.")


def _conferir_cadastros(caminho: Path, alvo: dict[str, Path], apagar_cadastros: bool) -> None:
    """Refazer apagaria o que alguém cadastrou ou tentou pelo aplicativo nesta base (biometria real):
    só com `apagar_cadastros`."""
    cadastros = int(leitura_ro.consultar(
        caminho, "SELECT COUNT(*) FROM usuarios WHERE substr(matricula, 1, ?) <> ?",
        (len(PREFIXO_MATRICULA), PREFIXO_MATRICULA))[0][0])
    pasta = alvo["EVIDENCIAS_DIR"]
    evidencias = sum(1 for arquivo in pasta.rglob("*") if arquivo.is_file()) if pasta.is_dir() else 0
    if (cadastros or evidencias) and not apagar_cadastros:
        raise RecusaBaseDemo(
            f"Refazer a base apagaria {cadastros} cadastro(s) e {evidencias} evidência(s) feitos nela. "
            "Para apagar assim mesmo: --recriar --apagar-cadastros (apagar_cadastros=True).")


def _fotos_das_identidades() -> list[list[Path]]:
    """As fotos de cada identidade, na ordem das pessoas de teste; recusa se o repositório não as tiver."""
    grupos = list(amostra_lab.fotos_de_teste().values())[:len(IDENTIDADES)]
    if len(grupos) < len(IDENTIDADES) or any(len(grupo) < FOTOS_POR_IDENTIDADE for grupo in grupos):
        raise RecusaBaseDemo(f"Faltam as fotos de teste em {amostra_lab.PASTA_FOTOS_TESTE}: a base precisa de "
                             f"{len(IDENTIDADES)} pessoas com {FOTOS_POR_IDENTIDADE} fotos cada.")
    return [grupo[:FOTOS_POR_IDENTIDADE] for grupo in grupos]


# ---------------------------------------------------------------------------- criação
def _apagar(alvo: dict[str, Path]) -> None:
    """Remove o banco de demonstração e as três subpastas da raiz (só isso)."""
    _remover_banco(alvo["DB_PATH"])
    for nome in _PASTAS_APAGAVEIS:
        if alvo[nome].is_dir():
            shutil.rmtree(alvo[nome])


def _criar(alvo: dict[str, Path], fotos: list[list[Path]], dias: int, semente: int, pipeline,
           agora: datetime) -> None:
    """Monta a base em um arquivo provisório e só no fim o põe no lugar: uma geração interrompida não
    deixa um banco pela metade com o nome da base."""
    caminho = alvo["DB_PATH"]
    provisorio = caminho.with_name(caminho.name + ".gerando")
    havia_fotos = alvo["FOTOS_DIR"].exists()
    try:
        _remover_banco(provisorio)                       # resto de uma geração interrompida
        pessoas = _cadastrar_identidades(provisorio, fotos, pipeline if pipeline is not None else Pipeline())
        _gravar_historico_e_marcador(provisorio, pessoas, dias, semente, agora)
        _remover_banco(caminho)
        os.replace(provisorio, caminho)
    except BaseException:
        _remover_banco(provisorio)
        if not havia_fotos:
            shutil.rmtree(alvo["FOTOS_DIR"], ignore_errors=True)
        raise


def _remover_banco(arquivo: Path) -> None:
    """Apaga um arquivo de banco e o diário de transação que o SQLite possa ter deixado ao lado dele
    (um diário antigo junto de um banco novo seria aplicado sobre ele na primeira abertura)."""
    arquivo.unlink(missing_ok=True)
    arquivo.with_name(arquivo.name + "-journal").unlink(missing_ok=True)


@dataclass(frozen=True)
class _Pessoa:
    """O que o histórico precisa saber de cada identidade cadastrada."""

    usuario_id: int
    nome: str
    nivel: int


def _cadastrar_identidades(caminho: Path, fotos: list[list[Path]], pipeline) -> list[_Pessoa]:
    """Cadastra as identidades pelo caminho normal do núcleo (esquema, recortes e vetores iguais aos de
    um cadastro por arquivo)."""
    pessoas = []
    with Banco(caminho) as banco:
        for (nome, matricula, cargo, nivel), caminhos in zip(IDENTIDADES, fotos):
            usuario, amostras, avisos = cadastrar_de_imagens(
                banco, pipeline, DadosCadastro(nome, matricula, cargo, nivel), caminhos)
            if amostras != len(caminhos):
                raise RuntimeError("Foto de teste sem amostra válida: " + "; ".join(avisos))
            pessoas.append(_Pessoa(usuario.id, usuario.nome, usuario.nivel))
    return pessoas


def _gravar_historico_e_marcador(caminho: Path, pessoas: list[_Pessoa], dias: int, semente: int,
                                 agora: datetime) -> None:
    """Histórico fictício e marcador, em uma transação só, pela conexão deste arquivo (o registro do
    núcleo sempre grava a hora atual; aqui as datas são passadas)."""
    linhas = _historico(pessoas, dias, semente, agora.date())
    con = sqlite3.connect(str(caminho))
    try:
        con.execute("CREATE TABLE demonstracao (chave TEXT PRIMARY KEY, valor TEXT)")
        con.executemany("INSERT INTO demonstracao (chave, valor) VALUES (?, ?)", [
            ("gerado_em", agora.isoformat(timespec="seconds")), ("semente", str(semente)),
            ("dias", str(dias)), ("versao", str(VERSAO))])
        con.executemany(_SQL_ACESSO, linhas)
        con.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------------------- histórico fictício
@dataclass(frozen=True)
class _Tentativa:
    """Uma tentativa do histórico antes de virar linha."""

    segundo: int                        # segundo do dia em que foi marcada
    resultado: Resultado
    pessoa: _Pessoa | None = None       # só nas plantadas: a mesma pessoa em todo o episódio
    exigido: int | None = None          # só nas plantadas: o mesmo nível em todo o episódio
    plantada: bool = False              # faz parte de um episódio de bloqueio


def _historico(pessoas: list[_Pessoa], dias: int, semente: int, hoje: date) -> list[tuple]:
    """Linhas do registro em ordem cronológica, dos `dias` dias que terminam na véspera de `hoje`.

    O bloqueio segue a regra do terminal, com os valores de um `ControleTentativas` descartável (só
    leitura dos atributos): a negação que completa `max_falhas` dentro da janela é seguida, no mesmo
    segundo, de uma linha BLOQUEADO; durante o bloqueio não há tentativa; um acesso concedido zera a
    contagem."""
    rng = random.Random(semente)
    controle = ControleTentativas()
    max_falhas, janela, bloqueio = controle.max_falhas, controle.janela, controle.bloqueio
    calendario = [hoje - timedelta(days=dias - i) for i in range(dias)]
    episodios = _sortear_episodios(rng, calendario, pessoas, max_falhas, janela)
    folga_antes = timedelta(seconds=max(janela, bloqueio) + 2 * _PASSO_SEG)
    folga_depois = timedelta(seconds=bloqueio + 2 * _PASSO_SEG)

    linhas: list[tuple] = []
    falhas: list[datetime] = []
    livre = datetime.combine(calendario[0], time())      # antes disso o terminal está ocupado ou bloqueado
    for dia in calendario:
        meia_noite = datetime.combine(dia, time())
        do_dia = episodios.get(dia, [])
        # em volta de cada episódio não entra tentativa sorteada: ele acontece como foi plantado
        reservas = [(meia_noite + timedelta(seconds=episodio[0].segundo) - folga_antes,
                     meia_noite + timedelta(seconds=episodio[-1].segundo) + folga_depois) for episodio in do_dia]
        for tentativa in _tentativas_do_dia(rng, dia, do_dia):
            momento = max(livre, meia_noite + timedelta(seconds=tentativa.segundo))
            if not tentativa.plantada and any(antes <= momento <= depois for antes, depois in reservas):
                continue
            linhas.append(_linha(rng, momento, tentativa, pessoas))
            livre = momento + timedelta(seconds=_PASSO_SEG)
            if tentativa.resultado is Resultado.CONCEDIDO:
                falhas = []
                continue
            falhas = [t for t in falhas if (momento - t).total_seconds() <= janela] + [momento]
            if len(falhas) >= max_falhas:
                exigido = linhas[-1][4]
                linhas.append((momento.isoformat(timespec="seconds"), None, None, None, exigido,
                               config.AREAS[exigido], None, Resultado.BLOQUEADO.value,
                               MARCA_MENSAGEM + f"Terminal bloqueado por {bloqueio:.0f}s após {max_falhas} falhas"))
                falhas = []
                livre = momento + timedelta(seconds=bloqueio + _PASSO_SEG)
    return linhas


def _sortear_episodios(rng: random.Random, calendario: list[date], pessoas: list[_Pessoa], max_falhas: int,
                       janela: float) -> dict[date, list[list[_Tentativa]]]:
    """Episódios de bloqueio plantados: em cada um, `max_falhas` negações do mesmo tipo, da mesma pessoa
    e no mesmo nível, dentro da janela. Pelo menos três, em dias úteis diferentes quando houver; os
    episódios de um mesmo dia caem em horas diferentes."""
    uteis = [dia for dia in calendario if dia.weekday() < 5] or calendario
    quantos = min(max(_MIN_EPISODIOS, len(uteis) // 5), len(_HORAS_DE_EPISODIO))
    if len(uteis) >= quantos:
        dias_sorteados = rng.sample(uteis, quantos)
    else:
        dias_sorteados = [uteis[i % len(uteis)] for i in range(quantos)]
    maior_intervalo = max(_PASSO_SEG, int(janela * 0.7 / max(1, max_falhas - 1)))
    episodios: dict[date, list[list[_Tentativa]]] = {}
    for i, dia in enumerate(dias_sorteados):
        do_dia = episodios.setdefault(dia, [])
        resultado = _EPISODIOS[i % len(_EPISODIOS)]
        pessoa, exigido = None, rng.choice((1, 2, 3, 3))
        if resultado is Resultado.NEGADO_NIVEL:
            pessoa, exigido = min(pessoas, key=lambda p: p.nivel), max(config.NIVEIS)
        elif resultado is Resultado.NEGADO_LIVENESS:
            pessoa = rng.choice(pessoas)
        hora = _HORAS_DE_EPISODIO[(dia.toordinal() + len(do_dia)) % len(_HORAS_DE_EPISODIO)]
        segundo = hora * 3600 + rng.randrange(0, 2400)
        episodio = []
        for _ in range(max_falhas):
            episodio.append(_Tentativa(segundo, resultado, pessoa, exigido, plantada=True))
            segundo += rng.randint(_PASSO_SEG, maior_intervalo)
        do_dia.append(episodio)
    return episodios


def _tentativas_do_dia(rng: random.Random, dia: date, episodios: list[list[_Tentativa]]) -> list[_Tentativa]:
    """As tentativas do dia em ordem de horário: as sorteadas (15 a 40 em dia útil, com pico de manhã e
    no começo da tarde; quase nada no fim de semana) mais as negações dos episódios plantados."""
    minimo, maximo = _TENTATIVAS_DIA_UTIL if dia.weekday() < 5 else _TENTATIVAS_FIM_DE_SEMANA
    resultados, pesos = zip(*_MISTURA)
    tentativas = [tentativa for episodio in episodios for tentativa in episodio]
    for _ in range(rng.randint(minimo, maximo)):
        inicio, fim = rng.choices(_FAIXAS_DO_DIA, weights=_PESOS_DAS_FAIXAS)[0]
        tentativas.append(_Tentativa(rng.randrange(inicio * 3600, fim * 3600), rng.choices(resultados, weights=pesos)[0]))
    return sorted(tentativas, key=lambda tentativa: tentativa.segundo)


def _linha(rng: random.Random, momento: datetime, tentativa: _Tentativa, pessoas: list[_Pessoa]) -> tuple:
    """Uma linha fictícia com os campos que o terminal gravaria para esse resultado."""
    resultado = tentativa.resultado
    pessoa = tentativa.pessoa
    exigido = tentativa.exigido if tentativa.exigido is not None else rng.choice((1, 2, 3, 3))
    similaridade: float | None = None
    if resultado is Resultado.CONCEDIDO:
        pessoa = rng.choice(pessoas)
        exigido = rng.randint(1, pessoa.nivel)
        similaridade = rng.uniform(0.50, 0.93)
        frase = f"Bem-vindo(a), {pessoa.nome}. Acesso liberado: {config.AREAS[exigido]}."
    elif resultado is Resultado.NEGADO_NIVEL:
        pessoa = min(pessoas, key=lambda p: p.nivel)
        exigido = max(config.NIVEIS)
        similaridade = rng.uniform(0.55, 0.90)
        frase = (f"{pessoa.nome} possui nível {pessoa.nivel} ({config.NIVEIS[pessoa.nivel]}); "
                 f"a área exige nível {exigido}.")
    elif resultado is Resultado.NEGADO_LIVENESS:
        pessoa = pessoa or rng.choice(pessoas)
        similaridade = rng.uniform(0.50, 0.88)
        frase = "Prova de vida falhou (rosto estático?)."
    elif resultado is Resultado.NEGADO_DESCONHECIDO:
        similaridade = rng.uniform(0.00, 0.33)
        frase = "Rosto não cadastrado. Acesso negado."
    else:
        frase = "Mais de uma pessoa diante do terminal."
    return (momento.isoformat(timespec="seconds"),
            pessoa.usuario_id if pessoa else None, pessoa.nome if pessoa else None, pessoa.nivel if pessoa else None,
            exigido, config.AREAS[exigido], None if similaridade is None else round(similaridade, 4),
            resultado.value, MARCA_MENSAGEM + frase)
