"""Aba Galeria de Resultados (lote L7), no aplicativo Qt completo e com banco temporário."""

from __future__ import annotations

from tests import apoio_v2
from tests.apoio_interface import FOTO_BIDEN, FOTO_BIDEN_2, FOTO_OBAMA, FOTO_OBAMA_2
from tests.apoio_v2 import _config_isolada  # noqa: F401

NOMES = ("Fulano Teste", "Beltrano Teste")


def _abrir(ctx):
    vm = apoio_v2.abrir_aba(ctx, "resultados", "galeria")
    apoio_v2.esperar_estado(ctx, vm, 30)
    return vm


def _cadastrar_dois(ctx):
    a = apoio_v2.cadastrar(ctx, NOMES[0], "T-1", 1, [FOTO_BIDEN, FOTO_BIDEN_2])
    b = apoio_v2.cadastrar(ctx, NOMES[1], "T-2", 2, [FOTO_OBAMA, FOTO_OBAMA_2])
    return a, b


def _tudo_em_texto(ctx, vm) -> str:
    return repr(apoio_v2.props_do_vm(vm)) + repr(vm.saude.itens()) + " ".join(apoio_v2.textos_visiveis(ctx.janela))


def test_galeria_vazia_convida_ao_cadastro(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        vm = _abrir(ctx)
        assert vm.estado == "vazio"
        textos = apoio_v2.textos_visiveis(ctx.janela)
        assert "Cadastre ao menos duas pessoas para comparar" in textos and "Novo cadastro" in textos
        vm.abrirCadastro()
        ctx.girar(0.2)
        assert ctx.apl.pagina == "cadastro"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_duas_pessoas_de_teste_aparecem_anonimas(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        _cadastrar_dois(ctx)
        vm = _abrir(ctx)
        assert vm.estado == "poucos"
        assert [g["nome"] for g in vm.dispersao["grupos"]] == ["Pessoa A", "Pessoa B"]
        assert vm.dispersao["grupos"][1]["rotulos"] == ["Pessoa B · amostra 1", "Pessoa B · amostra 2"]
        assert vm.matriz["linhas"] == ["Pessoa A", "Pessoa B"] and len(vm.matriz["valores"]) == 2
        assert [l["rotulo"] for l in vm.saude.itens()] == ["Pessoa A", "Pessoa B"]
        assert all(l["situacao"] == "poucas" for l in vm.saude.itens())
        assert vm.resumo["pessoas"] == "2" and vm.resumo["amostras"] == "4"
        texto = _tudo_em_texto(ctx, vm)
        for nome in apoio_v2.nomes_do_banco(tmp_path / "t.db"):
            assert nome not in texto
        assert apoio_v2.sem_vetor_128(apoio_v2.props_do_vm(vm))
        assert "Alertas consultivos: esta tela não desativa, não remove e não bloqueia ninguém." in \
            apoio_v2.textos_visiveis(ctx.janela)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_mostrar_nomes_troca_rotulos(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        _cadastrar_dois(ctx)
        vm = _abrir(ctx)
        ctx.apl.extensoes.obter("privacidade").definirMostrarNomes(True)
        apoio_v2.esperar_estado(ctx, vm, 30)
        assert [g["nome"] for g in vm.dispersao["grupos"]] == list(NOMES)
        ctx.apl.extensoes.obter("privacidade").definirMostrarNomes(False)
        apoio_v2.esperar_estado(ctx, vm, 30)
        assert [g["nome"] for g in vm.dispersao["grupos"]] == ["Pessoa A", "Pessoa B"]
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_duplicidade_e_so_texto(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apoio_v2.cadastrar(ctx, NOMES[0], "T-1", 1, [FOTO_BIDEN, FOTO_BIDEN_2])
        apoio_v2.cadastrar(ctx, NOMES[1], "T-2", 1, [FOTO_BIDEN, FOTO_BIDEN_2])     # a mesma pessoa, duas vezes
        antes = apoio_v2.retrato_banco(tmp_path / "t.db")
        vm = _abrir(ctx)
        itens = vm.saude.itens()
        assert [l["situacao"] for l in itens] == ["duplicidade", "duplicidade"]
        assert itens[0]["recomendacao"] == "Possível duplicidade com Pessoa B: conferir os dois cadastros."
        assert vm.matriz["destaques"] == [[0, 1], [1, 0]]
        assert vm.resumo["paresDeRisco"] == "1"
        assert apoio_v2.retrato_banco(tmp_path / "t.db") == antes
        assert all(u.ativo for u in ctx.apl.banco.listar_usuarios())
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_inativo_fica_fora(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        a, _ = _cadastrar_dois(ctx)
        apoio_v2.cadastrar(ctx, "Sicrano Teste", "T-3", 1, [FOTO_OBAMA, FOTO_BIDEN])
        ctx.apl.banco.definir_ativo(a.id, False)
        ctx.apl.banco_alterado()
        vm = _abrir(ctx)
        assert vm.resumo["pessoas"] == "2" and vm.resumo["inativos"] == "1"
        assert [g["nome"] for g in vm.dispersao["grupos"]] == ["Pessoa B", "Pessoa C"]   # o rótulo não muda com o filtro
        assert "inativa" in vm.notaInativos
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_sem_avisos(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        _cadastrar_dois(ctx)
        apoio_v2.cadastrar(ctx, "Sicrano Teste", "T-3", 3, [FOTO_OBAMA, FOTO_BIDEN])
        vm = _abrir(ctx)
        assert vm.estado == "pronto"
        assert len(vm.dispersao["grupos"]) == 3 and vm.dispersao["rotularCentros"] is True
        vm.recarregar()
        apoio_v2.esperar_estado(ctx, vm, 30)
        vm.abrirUsuarios()
        ctx.girar(0.2)
        assert ctx.apl.pagina == "usuarios"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
