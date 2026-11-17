"""Técnica base da versão 2: leitura somente leitura do banco, descritores em lote, degradações,
medidas de qualidade, composição instrumentada do pipeline e formatos de texto.

Os dois casos que comparam com o núcleo (`test_lote_igual_ao_nucleo` e
`test_preparar_padrao_identico_ao_pipeline`) travam que a técnica nova calcula o mesmo que ele."""

from __future__ import annotations

import ast
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from cofre import amostra_lab, config, degradacoes, leitura_ro, parametros, qualidade
from cofre.banco import Banco
from cofre.fase1_aquisicao import carregar_imagem
from cofre.lote_sface import LoteSFace

RAIZ = Path(__file__).resolve().parent.parent
PRIMEIRAS_LINHAS = {
    "leitura_ro": "Fase 5 (reconhecimento e interpretação): leitura do registro e da galeria, sem escrita.",
    "lote_sface": "Fase 4 (representação e descrição): descritores SFace em lote.",
    "degradacoes": "Fase 1 (aquisição): condições de captura simuladas.",
    "qualidade": "Fases 2 a 4: medidas informativas de qualidade do rosto.",
    "amostra_lab": "Fases 1 a 4: composição instrumentada do pipeline.",
    "base_demo": "Apoio (dados de demonstração; não é fase do PDI): gerador e marcador da base de demonstração.",
}
ESCRITAS = (
    "INSERT INTO usuarios (nome, matricula, cargo, nivel, ativo, criado_em) VALUES ('x', 'y', '', 1, 1, 'z')",
    "UPDATE usuarios SET nivel = 1",
    "DELETE FROM usuarios",
    "CREATE TABLE intrusa (a)",
)


def _vetor(rng) -> np.ndarray:
    v = rng.standard_normal(128).astype(np.float32)
    return v / np.linalg.norm(v)


def _alinhados(pipeline, fotos) -> list[np.ndarray]:
    """Rosto alinhado de cada uma das quatro fotos de teste, pelo pipeline do núcleo."""
    return [pipeline.processar(carregar_imagem(c)).principal.alinhado for grupo in fotos.values() for c in grupo]


def _config_inteira() -> dict:
    return {nome: getattr(config, nome) for nome in dir(config) if nome.isupper()}


# ---------------------------------------------------------------------------- leitura_ro
def test_conexao_ro_recusa_escrita(banco):
    banco.criar_usuario("Ana", "M001", "", 2)
    con = leitura_ro.abrir(banco.caminho)
    try:
        for sql in ESCRITAS:
            with pytest.raises(sqlite3.OperationalError):
                con.execute(sql)
            con.execute("PRAGMA query_only = OFF")       # mesmo desligando a trava da conexão, o arquivo foi aberto só para leitura
            with pytest.raises(sqlite3.OperationalError):
                con.execute(sql)
            con.execute("PRAGMA query_only = ON")
    finally:
        con.close()
    linhas = leitura_ro.consultar(banco.caminho, "SELECT nome, nivel FROM usuarios WHERE matricula = ?", ("M001",))
    assert [tuple(linha) for linha in linhas] == [("Ana", 2)]
    assert leitura_ro.consultar(banco.caminho, "SELECT name FROM sqlite_master WHERE name = 'intrusa'") == []


def test_memoria_e_arquivo_ausente_dao_indisponivel(tmp_path):
    ausente = tmp_path / "nao_existe.db"
    for caminho in (":memory:", ausente, tmp_path):
        with pytest.raises(leitura_ro.BancoIndisponivel):
            leitura_ro.abrir(caminho)
        with pytest.raises(leitura_ro.BancoIndisponivel):
            leitura_ro.consultar(caminho, "SELECT 1")
        with pytest.raises(leitura_ro.BancoIndisponivel):
            leitura_ro.galeria(caminho)
        with pytest.raises(leitura_ro.BancoIndisponivel):
            list(leitura_ro.fatias(caminho, "SELECT id FROM acessos WHERE id > ? ORDER BY id LIMIT ?"))
        assert leitura_ro.eh_base_demonstracao(caminho) is False
    assert not ausente.exists() and list(tmp_path.iterdir()) == []      # nenhum arquivo é criado
    assert not Path(":memory:").exists()


def test_caminho_com_caracteres_especiais(tmp_path):
    caminho = tmp_path / "a?b#c%d e" / "t.db"
    with Banco(caminho) as banco:
        banco.criar_usuario("Ana", "M001", "", 1)
    assert [linha["matricula"] for linha in leitura_ro.consultar(caminho, "SELECT matricula FROM usuarios")] == ["M001"]
    assert leitura_ro.ids_usuarios(caminho) == [1]
    con = leitura_ro.abrir(caminho)
    try:
        for sql in ESCRITAS:
            with pytest.raises(sqlite3.OperationalError):
                con.execute(sql)
    finally:
        con.close()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a?b#c%d e"]  # a URI não criou arquivo com outro nome


def test_galeria_ro_bate_com_o_banco(banco, tmp_path):
    rng = np.random.default_rng(0)
    quantas = {"Ana": 3, "Bia": 2, "Caio": 4, "Davi": 1}
    usuarios = [banco.criar_usuario(nome, f"M{i}", "", (i % 3) + 1) for i, nome in enumerate(quantas)]
    for rodada in range(max(quantas.values())):              # amostras intercaladas: a ordem da galeria não é a de gravação
        for u in usuarios:
            if rodada < quantas[u.nome]:
                banco.adicionar_amostra(u.id, _vetor(rng))
    banco.definir_ativo(usuarios[2].id, False)

    g = leitura_ro.galeria(banco.caminho)
    ativos = [u for u in usuarios if u.id != usuarios[2].id]
    assert g.matriz.shape == (6, 128) and g.matriz.dtype == np.float32
    assert g.donos.dtype == np.int64 and g.amostras.dtype == np.int64
    assert g.donos.tolist() == [u.id for u in ativos for _ in range(quantas[u.nome])]      # por pessoa, em ordem de id
    assert g.amostras.tolist() == [n for u in ativos for n in range(1, quantas[u.nome] + 1)]
    assert g.niveis == {u.id: u.nivel for u in ativos} and g.inativos == 1
    esperada = np.vstack([emb for u in ativos for emb in banco.embeddings_do_usuario(u.id)])
    assert np.array_equal(g.matriz, esperada)                 # os mesmos vetores que o terminal carrega

    todos = leitura_ro.galeria(banco.caminho, apenas_ativos=False)
    assert todos.matriz.shape == (10, 128) and todos.inativos == 0
    assert sorted(set(todos.donos.tolist())) == [u.id for u in usuarios]
    assert leitura_ro.nomes(banco.caminho) == {u.id: u.nome for u in usuarios}
    assert leitura_ro.ids_usuarios(banco.caminho) == [u.id for u in usuarios]

    vazio = tmp_path / "vazio.db"
    Banco(vazio).fechar()
    gv = leitura_ro.galeria(vazio)
    assert gv.matriz.shape == (0, 128) and gv.donos.shape == (0,) and gv.amostras.shape == (0,)
    assert gv.niveis == {} and gv.inativos == 0


def test_fatias_percorrem_tudo_sem_repetir(banco):
    u = banco.criar_usuario("Ana", "M001", "", 1)
    rng = np.random.default_rng(1)
    for _ in range(7):
        banco.adicionar_amostra(u.id, _vetor(rng))
    sql = "SELECT id FROM amostras WHERE id > ? ORDER BY id LIMIT ?"
    assert [[linha["id"] for linha in fatia] for fatia in leitura_ro.fatias(banco.caminho, sql, 3)] == [[1, 2, 3], [4, 5, 6], [7]]
    assert [len(fatia) for fatia in leitura_ro.fatias(banco.caminho, sql, 7)] == [7]
    assert [len(fatia) for fatia in leitura_ro.fatias(banco.caminho, sql)] == [7]


def test_rotulos_anonimos():
    assert leitura_ro.rotulos_anonimos([3, 1, 2]) == {1: "Pessoa A", 2: "Pessoa B", 3: "Pessoa C"}
    assert leitura_ro.rotulos_anonimos([40, 7, 7]) == {7: "Pessoa A", 40: "Pessoa B"}      # pela ordem do id, sem repetir
    muitos = leitura_ro.rotulos_anonimos(range(1, 29))
    assert (muitos[26], muitos[27], muitos[28]) == ("Pessoa Z", "Pessoa AA", "Pessoa AB")
    assert leitura_ro.rotulos_anonimos([]) == {}


# ---------------------------------------------------------------------------- lote_sface
def test_lote_igual_ao_nucleo(pipeline, fotos):
    alinhados = _alinhados(pipeline, fotos)
    assert len(alinhados) == 4
    do_nucleo = np.vstack([pipeline.extrator.extrair(a) for a in alinhados])
    lote = LoteSFace.instancia()
    assert LoteSFace.instancia() is lote
    for tamanho in (32, 1, 3):
        embeddings, normas = lote.embeddings(alinhados, tamanho_lote=tamanho)
        assert embeddings.shape == (4, 128) and embeddings.dtype == np.float32
        assert normas.shape == (4,) and normas.dtype == np.float32
        assert float(np.abs(embeddings - do_nucleo).max()) <= 1e-6
    vazios, normas_vazias = lote.embeddings([])
    assert vazios.shape == (0, 128) and normas_vazias.shape == (0,)


def test_norma_crua_positiva(pipeline, fotos):
    alinhados = _alinhados(pipeline, fotos)
    embeddings, normas = LoteSFace.instancia().embeddings(alinhados)
    assert bool((normas > 0).all())
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-5)
    cruas = [float(np.linalg.norm(pipeline.extrator.sface.feature(a))) for a in alinhados]      # a saída da rede, antes de normalizar
    assert np.allclose(normas, cruas, rtol=1e-5)


def test_lote_confere_o_sinal_entre_lotes(pipeline, fotos):
    class Contador:
        chamadas = 0

        def conferir(self):
            self.chamadas += 1

    class Cancela:
        def conferir(self):
            raise InterruptedError

    alinhados = _alinhados(pipeline, fotos) * 3
    contador = Contador()
    LoteSFace.instancia().embeddings(alinhados, tamanho_lote=5, sinal=contador)
    assert contador.chamadas == 3                             # 12 imagens em lotes de 5
    with pytest.raises(InterruptedError):
        LoteSFace.instancia().embeddings(alinhados, sinal=Cancela())


# ---------------------------------------------------------------------------- degradacoes
def test_degradacoes_deterministicas_e_nivel_zero_identico(pipeline, fotos):
    alinhado = _alinhados(pipeline, fotos)[0]
    original = alinhado.copy()
    for chave in degradacoes.FAMILIAS:
        zero = degradacoes.aplicar(alinhado, chave, 0.0)
        assert np.array_equal(zero, original) and zero is not alinhado
        for nivel in (0.3, 1.0):
            a = degradacoes.aplicar(alinhado, chave, nivel, semente=3)
            b = degradacoes.aplicar(alinhado, chave, nivel, semente=3)
            assert np.array_equal(a, b), chave
        assert not np.array_equal(degradacoes.aplicar(alinhado, chave, 1.0), original), chave
    assert np.array_equal(alinhado, original)                 # a entrada nunca é alterada
    ruido_a = degradacoes.aplicar(alinhado, "ruido", 0.5, semente=1)
    assert not np.array_equal(ruido_a, degradacoes.aplicar(alinhado, "ruido", 0.5, semente=2))

    quadro = carregar_imagem(fotos["obama"][0])
    for chave in degradacoes.FAMILIAS_DE_QUADRO:
        assert np.array_equal(degradacoes.aplicar_no_quadro(quadro, chave, 0.0), quadro)
        a = degradacoes.aplicar_no_quadro(quadro, chave, 0.6, semente=4)
        assert np.array_equal(a, degradacoes.aplicar_no_quadro(quadro, chave, 0.6, semente=4))
        assert not np.array_equal(a, quadro)


def test_degradacoes_mantem_formato(pipeline, fotos):
    assert list(degradacoes.FAMILIAS) == ["desfoque", "ruido", "escuro", "claro", "rotacao", "oclusao_olhos",
                                          "oclusao_baixo", "resolucao"]
    niveis = degradacoes.NIVEIS_PADRAO
    assert len(niveis) == 12 and niveis[0] == 0.0 and niveis[-1] == 1.0 and list(niveis) == sorted(niveis)
    alinhado = _alinhados(pipeline, fotos)[1]
    for chave, familia in degradacoes.FAMILIAS.items():
        assert familia.chave == chave and familia.nome and familia.unidade
        for nivel in niveis:
            saida = degradacoes.aplicar(alinhado, chave, nivel)
            assert saida.shape == (112, 112, 3) and saida.dtype == np.uint8, (chave, nivel)
    extremos = {"desfoque": (0, 8), "ruido": (0, 60), "escuro": (1.0, 0.05), "claro": (1.0, 3.0), "rotacao": (0, 40),
                "oclusao_olhos": (0, 48), "oclusao_baixo": (0, 64), "resolucao": (112, 12)}
    for chave, (inicio, fim) in extremos.items():
        familia = degradacoes.FAMILIAS[chave]
        assert familia.parametro(0.0) == pytest.approx(inicio) and familia.parametro(1.0) == pytest.approx(fim)
    assert degradacoes.FAMILIAS["desfoque"].rotulo(0.4) == "σ = 3,2"
    assert degradacoes.FAMILIAS["rotacao"].rotulo(0.45) == "18°"
    assert degradacoes.FAMILIAS["escuro"].rotulo(1.0) == "ganho × 0,05"
    assert degradacoes.FAMILIAS["oclusao_baixo"].rotulo(1.0) == "64 px"
    assert degradacoes.FAMILIAS["resolucao"].rotulo(1.0) == "12 px"

    quadro = carregar_imagem(fotos["biden"][0])
    for chave in ("escuro", "claro", "desfoque", "ruido", "rotacao"):
        saida = degradacoes.aplicar_no_quadro(quadro, chave, 0.5)
        assert saida.shape == quadro.shape and saida.dtype == np.uint8
    for chave in ("oclusao_olhos", "oclusao_baixo", "resolucao"):
        with pytest.raises(ValueError):
            degradacoes.aplicar_no_quadro(quadro, chave, 0.5)
    with pytest.raises(ValueError):
        degradacoes.aplicar(alinhado, "inexistente", 0.5)
    with pytest.raises(ValueError):
        degradacoes.aplicar(quadro, "desfoque", 0.5)           # aplicar é só para o rosto alinhado 112x112


# ---------------------------------------------------------------------------- amostra_lab
def test_preparar_padrao_identico_ao_pipeline(pipeline, fotos):
    for grupo in fotos.values():
        for caminho in grupo:
            img = carregar_imagem(caminho)
            res = pipeline.processar(img)
            ref = res.principal
            a = amostra_lab.preparar(img, pipeline, origem="foto_teste", rotulo="Foto de teste")
            assert a.tem_rosto and a.n_rostos == len(res.rostos) and a.parametros.padrao
            assert np.array_equal(a.alinhado, ref.alinhado)
            assert float(np.abs(a.embedding - ref.embedding).max()) == 0.0
            assert np.array_equal(a.reduzida, res.pre.reduzida) and np.array_equal(a.cinza, res.pre.cinza)
            assert np.array_equal(a.suavizada, res.pre.suavizada) and np.array_equal(a.equalizada, res.pre.equalizada)
            assert a.escala == res.pre.escala and np.array_equal(a.recorte, ref.recorte)
            assert a.rosto.caixa == ref.rosto.caixa and a.rosto_reduzido.caixa == ref.rosto_reduzido.caixa
            assert (a.qualidade.nitidez, a.qualidade.brilho) == (ref.qualidade.nitidez, ref.qualidade.brilho)
            assert a.norma_crua > 0 and (a.origem, a.rotulo) == ("foto_teste", "Foto de teste")
            assert set(a.tempos_ms) == {"fase2", "fase3_deteccao", "fase3_alinhamento", "fase4", "total"}
            assert all(t >= 0 for t in a.tempos_ms.values()) and a.tempos_ms["fase4"] > 0
            assert a.frame is not img and np.array_equal(a.frame, img)


def test_preparar_com_parametro_de_estudo_nao_muda_config(pipeline, fotos):
    img = carregar_imagem(fotos["obama"][0])
    config_antes, parametros_antes = _config_inteira(), parametros.valores_atuais()
    padrao = amostra_lab.preparar(img, pipeline)
    estudo = amostra_lab.ParametrosEstudo(largura=480, kernel=5, clip=4.0, grade=4)
    a = amostra_lab.preparar(img, pipeline, estudo)
    assert not a.parametros.padrao and a.reduzida.shape[1] == 480
    assert a.tem_rosto and not np.array_equal(a.embedding, padrao.embedding)         # o resultado é hipotético
    sem_filtro = amostra_lab.preparar(img, pipeline, amostra_lab.ParametrosEstudo(kernel=1))
    assert not sem_filtro.parametros.padrao and np.array_equal(sem_filtro.suavizada, sem_filtro.reduzida)
    assert _config_inteira() == config_antes and parametros.valores_atuais() == parametros_antes
    assert amostra_lab.ParametrosEstudo().padrao
    depois = amostra_lab.preparar(img, pipeline)                                      # nada ficou preso de uma chamada para outra
    assert np.array_equal(depois.embedding, padrao.embedding) and np.array_equal(depois.alinhado, padrao.alinhado)
    for invalido in ({"kernel": 4}, {"kernel": 0}, {"largura": 0}, {"clip": 0.0}, {"grade": 0}):
        with pytest.raises(ValueError):
            amostra_lab.ParametrosEstudo(**invalido)


def test_preparar_sem_rosto(pipeline):
    liso = np.full((480, 800, 3), 127, np.uint8)
    a = amostra_lab.preparar(liso, pipeline, origem="arquivo", rotulo="Imagem lisa")
    assert not a.tem_rosto and a.n_rostos == 0
    assert a.frame.shape == liso.shape                                                # fase 1
    assert a.reduzida.shape == (384, 640, 3) and a.cinza.shape == (384, 640)          # fase 2
    assert a.suavizada.shape == a.reduzida.shape and a.equalizada.shape == a.reduzida.shape and a.escala == 0.8
    assert a.rosto is None and a.rosto_reduzido is None and a.alinhado is None and a.recorte is None
    assert a.embedding is None and a.norma_crua is None and a.qualidade is None
    assert a.tempos_ms["fase2"] > 0 and a.tempos_ms["fase3_deteccao"] > 0
    assert a.tempos_ms["fase3_alinhamento"] == 0.0 and a.tempos_ms["fase4"] == 0.0


def test_fotos_de_teste_e_pasta_rotulada(tmp_path, monkeypatch):
    conjunto = amostra_lab.fotos_de_teste()
    assert list(conjunto) == ["Pessoa de teste A", "Pessoa de teste B"]
    subpastas = sorted(p for p in amostra_lab.PASTA_FOTOS_TESTE.iterdir() if p.is_dir())
    for (rotulo, caminhos), subpasta in zip(conjunto.items(), subpastas):
        assert len(caminhos) == 2 and caminhos == sorted(caminhos)
        assert all(c.parent == subpasta and c.is_file() for c in caminhos)
        assert subpasta.name.lower() not in rotulo.lower()                            # o rótulo nunca traz o nome da subpasta

    rotulada = amostra_lab.pasta_rotulada(amostra_lab.PASTA_FOTOS_TESTE)
    assert list(rotulada) == ["Pessoa 1", "Pessoa 2"] and list(rotulada.values()) == list(conjunto.values())
    assert amostra_lab.pasta_rotulada(str(amostra_lab.PASTA_FOTOS_TESTE)) == rotulada

    assert amostra_lab.pasta_rotulada(tmp_path / "nao_existe") == {}
    assert amostra_lab.pasta_rotulada(subpastas[0]) == {}                             # só arquivos, nenhuma subpasta
    imagem = subpastas[0] / conjunto["Pessoa de teste A"][0].name
    for nome in ("c", "a", "b_vazia"):
        (tmp_path / "conjunto" / nome).mkdir(parents=True)
    for nome in ("c", "a"):
        (tmp_path / "conjunto" / nome / "foto.jpg").write_bytes(imagem.read_bytes())
    (tmp_path / "conjunto" / "b_vazia" / "notas.txt").write_text("sem imagem")
    com_vazia = amostra_lab.pasta_rotulada(tmp_path / "conjunto")
    assert list(com_vazia) == ["Pessoa 1", "Pessoa 2"]
    assert [c[0].parent.name for c in com_vazia.values()] == ["a", "c"]               # a subpasta sem imagem fica de fora

    monkeypatch.setattr(amostra_lab, "PASTA_FOTOS_TESTE", tmp_path / "nao_existe")
    assert amostra_lab.fotos_de_teste() == {}


# ---------------------------------------------------------------------------- qualidade
def test_componentes_de_qualidade_no_intervalo(pipeline, fotos):
    assert qualidade.COMPONENTES == ("nitidez", "exposicao", "ruido", "simetria", "pose", "resolucao", "confianca", "norma")
    for grupo in fotos.values():
        for caminho in grupo:
            a = amostra_lab.preparar(carregar_imagem(caminho), pipeline)
            comp = qualidade.componentes(a.alinhado, a.rosto, a.norma_crua)
            assert tuple(comp) == qualidade.COMPONENTES
            assert all(v is not None and 0.0 <= v <= 1.0 for v in comp.values()), comp
            brutos = qualidade.brutos(a.alinhado, a.rosto, a.norma_crua)
            assert tuple(brutos) == qualidade.COMPONENTES and all(v is not None and v >= 0 for v in brutos.values())
            indice = qualidade.indice(comp)
            assert isinstance(indice, int) and 0 <= indice <= 100
            assert indice > 60                                                        # retratos oficiais: boa qualidade

            so_imagem = qualidade.componentes(a.alinhado)
            assert [k for k, v in so_imagem.items() if v is None] == ["pose", "resolucao", "confianca", "norma"]
            assert all(0.0 <= v <= 1.0 for v in so_imagem.values() if v is not None)
            assert isinstance(qualidade.indice(so_imagem), int)

            borrado = qualidade.componentes(degradacoes.aplicar(a.alinhado, "desfoque", 1.0))
            escuro = qualidade.componentes(degradacoes.aplicar(a.alinhado, "escuro", 0.9))
            assert borrado["nitidez"] < comp["nitidez"] and escuro["exposicao"] < comp["exposicao"]

    rng = np.random.default_rng(0)
    extremos = (np.zeros((112, 112, 3), np.uint8), np.full((112, 112, 3), 255, np.uint8),
                rng.integers(0, 256, (112, 112, 3), dtype=np.uint8))
    for img in extremos:
        for norma in (0.0, 9.5, 500.0):
            comp = qualidade.componentes(img, None, norma)
            assert all(v is None or 0.0 <= v <= 1.0 for v in comp.values()), comp
    assert qualidade.indice(dict.fromkeys(qualidade.COMPONENTES)) is None
    assert qualidade.indice({"nitidez": 1.0, "exposicao": 0.5, "ruido": None}) == 75


# ---------------------------------------------------------------------------- formatos
def test_formatos():
    from PySide6.QtGui import QImage

    from cofre.qt import formatos as f

    assert f.num(0.3634) == "0,363" and f.num(12.5, 1) == "12,5" and f.num(3, 0) == "3"
    assert f.num(None) == "–" and f.num(float("nan")) == "–" and f.num(-0.0001) == "0,000"
    assert f.inteiro(2236) == "2 236" and f.inteiro(1234567) == "1 234 567"
    assert f.inteiro(0) == "0" and f.inteiro(None) == "–"
    assert f.pct(43, 882) == "4,88 %" and f.pct(1, 0) == "–" and f.pct(1, 3, 0) == "33 %"
    assert f.pct_valor(0.0488) == "4,88 %" and f.pct_valor(None) == "–" and f.pct_valor(float("nan")) == "–"
    assert f.hora("2026-11-10T20:41:07") == "20:41:07"
    assert f.hora("ontem") == "–" and f.hora(None) == "–" and f.hora("") == "–"
    assert f.dia_hora("2026-11-10T20:41:07") == "10/11 · 20:41" and f.dia_hora("x") == "–" and f.dia_hora(None) == "–"
    assert f.carimbo_arquivo(datetime(2026, 11, 10, 20, 41, 7)) == "20261110_204107"
    assert len(f.carimbo_arquivo()) == 15 and f.carimbo_arquivo()[8] == "_"
    assert f.caminho_de_url("file:///tmp/a%20b/c.png") == Path("/tmp/a b/c.png")
    assert f.caminho_de_url("/tmp/x y.png") == Path("/tmp/x y.png") and f.caminho_de_url("") is None

    bgra = np.zeros((3, 5, 4), np.uint8)
    bgra[...] = (10, 20, 30, 77)
    bgra[0, 0] = (1, 2, 3, 0)
    img = f.bgra_para_qimage(bgra)
    bgra[...] = 255                                             # a imagem é independente do vetor de origem
    assert (img.width(), img.height()) == (5, 3) and img.format() == QImage.Format.Format_ARGB32
    cor = img.pixelColor(4, 2)
    assert (cor.red(), cor.green(), cor.blue(), cor.alpha()) == (30, 20, 10, 77)
    assert img.pixelColor(0, 0).alpha() == 0                    # o canal alfa é preservado
    with pytest.raises(ValueError):
        f.bgra_para_qimage(np.zeros((3, 5, 3), np.uint8))


# ---------------------------------------------------------------------------- estrutura dos módulos
def test_modulos_declaram_a_fase_e_nao_importam_qt():
    for modulo, primeira_linha in PRIMEIRAS_LINHAS.items():
        arvore = ast.parse((RAIZ / "cofre" / f"{modulo}.py").read_text(encoding="utf-8"))
        assert ast.get_docstring(arvore).splitlines()[0] == primeira_linha, modulo
        importados = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                importados.update(alias.name for alias in no.names)
            elif isinstance(no, ast.ImportFrom):
                importados.add(("." * no.level) + (no.module or ""))
        assert not any(nome.startswith("PySide6") or nome in (".qt", "cofre.qt") or nome.startswith((".qt.", "cofre.qt."))
                       for nome in importados), (modulo, importados)
