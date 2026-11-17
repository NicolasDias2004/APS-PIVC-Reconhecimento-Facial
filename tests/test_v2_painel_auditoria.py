"""Abas Incidentes e Integridade do Painel (L2): ViewModels e telas, com banco temporário e câmera ausente."""

from __future__ import annotations

import json
from pathlib import Path

from cofre import config
from tests import apoio_v2
from tests.apoio_v2 import _config_isolada  # noqa: F401

NOME = "Joana Teste Pereira"


def _episodio(db, hora="2026-11-10T20:41", uid=None):
    """Três negações e o bloqueio, como o terminal grava."""
    linhas = [{"data_hora": f"{hora}:{s:02d}", "resultado": "NEGADO_DESCONHECIDO", "similaridade": 0.12,
               "evidencia": f"/x/{hora[:10].replace('-', '')}_{hora[11:13]}{hora[14:16]}{s:02d}_NEGADO_DESCONHECIDO.jpg"}
              for s in (0, 10, 22)]
    linhas.append({"data_hora": f"{hora}:22", "resultado": "BLOQUEADO"})
    apoio_v2.semear_acessos(db, linhas)


def _com_pessoa(db):
    apoio_v2.semear_acessos(db, [
        {"data_hora": f"2026-11-11T08:0{m}:00", "resultado": "NEGADO_NIVEL", "usuario_id": 1, "nome_detectado": NOME,
         "nivel_usuario": 1, "nivel_exigido": 3, "similaridade": 0.81, "mensagem": f"{NOME} possui nível 1",
         "evidencia": f"/x/20261111_080{m}00_NEGADO_NIVEL.jpg"} for m in (0, 2, 4)])


def _abrir(ctx, aba):
    vm = apoio_v2.abrir_aba(ctx, "painel", aba)
    apoio_v2.esperar_estado(ctx, vm)
    ctx.girar(0.2)
    return vm


def test_incidentes_anonimo_por_padrao(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        db = tmp_path / "t.db"
        ctx.apl.banco.criar_usuario(NOME, "M-77", "", 1)
        _com_pessoa(db)
        vm = _abrir(ctx, "incidentes")
        assert vm.estado == "pronto" and vm.contagens["acima_do_nivel"] == 1
        itens = vm.incidentes.itens()
        assert itens[0]["pessoa"] == "Pessoa A" and itens[0]["gravidade"] == "alta"
        nomes = apoio_v2.nomes_do_banco(db)
        assert NOME in nomes
        tudo = repr(apoio_v2.props_do_vm(vm)) + repr(itens)
        textos = " ".join(apoio_v2.textos_visiveis(ctx.janela))
        for nome in nomes:
            assert nome not in tudo and nome not in textos
        assert "Pessoa A" in textos
        ctx.apl.extensoes.obter("privacidade").definirMostrarNomes(True)      # a chave da sessão mostra o nome
        apoio_v2.esperar_estado(ctx, vm)
        assert vm.incidentes.itens()[0]["pessoa"] == NOME
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_incidente_aparece_ao_voltar_ao_painel(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        vm = _abrir(ctx, "incidentes")
        assert vm.estado == "vazio" and vm.contagens["todos"] == 0
        assert "Nenhum incidente no período" in apoio_v2.textos_visiveis(ctx.janela)
        ctx.apl.navegar("terminal")
        ctx.girar(0.3)
        _episodio(tmp_path / "t.db")                       # sem banco_alterado, como o terminal
        ctx.apl.navegar("painel")
        ctx.girar(0.2)
        apoio_v2.esperar_estado(ctx, vm)
        assert vm.estado == "pronto" and vm.contagens["bloqueio"] == 1 and vm.contagens["todos"] == 1
        (item,) = vm.incidentes.itens()
        assert item["tipo"] == "bloqueio" and item["tentativas"] == 4 and item["pessoa"] == ""
        assert vm.selecionado == item["id"] and sum(1 for l in vm.linhaTempo if l["doIncidente"]) == 4
        vm.definirFiltroTipo("multiplos")
        assert vm.incidentes.itens() == [] and vm.selecionado == ""
        vm.definirFiltroTipo("")
        assert vm.selecionado == item["id"]
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_abrir_na_auditoria_usa_slots_existentes(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        _episodio(tmp_path / "t.db")
        vm = _abrir(ctx, "incidentes")
        ctx.apl.acessos_vm.definirFiltroNivel(2)          # filtro antigo: abrirNaAuditoria limpa antes
        vm.abrirNaAuditoria()
        ctx.girar(0.3)
        assert ctx.apl.pagina == "acessos"
        assert ctx.apl.acessos_vm.filtroResultado == "BLOQUEADO"
        assert ctx.apl.acessos_vm.filtroNivel == 0
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_selar_agora_grava_json_em_relatorios(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        db = tmp_path / "t.db"
        _episodio(db)
        vm = _abrir(ctx, "integridade")
        assert vm.selos["total"] == 0
        antes = apoio_v2.retrato_banco(db)
        vm.selarAgora()
        assert ctx.esperar(lambda: not vm.selando, 15)
        apoio_v2.esperar_estado(ctx, vm)
        arquivos = sorted(Path(config.RELATORIOS_DIR).glob("selo_*.json"))
        assert len(arquivos) == 1
        dados = json.loads(arquivos[0].read_text(encoding="utf-8"))
        assert dados["registros"] == 4 and dados["ultimo_id"] == 4 and dados["sha256"] == vm.selo["sha256"]
        assert dados["base"] == "t.db" and dados["demonstracao"] is False
        assert apoio_v2.retrato_banco(db) == antes
        assert vm.selos["total"] == 1 and vm.selos["ultimoTexto"] == "Último selo gravado: confere"
        assert "Último selo gravado: confere" in apoio_v2.textos_visiveis(ctx.janela)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_abrir_pasta_de_selos_nao_abre_o_sistema(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        vm = _abrir(ctx, "integridade")
        vm.abrirPastaSelos()
        assert apoio_v2.ABERTOS == [Path(config.RELATORIOS_DIR)]
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_integridade_confere_em_turquesa_no_modelo(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        db = tmp_path / "t.db"
        _episodio(db)
        vm = _abrir(ctx, "integridade")
        assert vm.estado == "pronto" and len(vm.regras) == 13
        assert {r["situacao"] for r in vm.regras} == {"confere"}
        assert vm.resumo == "13 regras conferidas em 4 registros: nenhuma violação"
        assert len(vm.selo["grupos"]) == 16 and all(len(g) == 4 for g in vm.selo["grupos"])
        apoio_v2.semear_acessos(db, [{"data_hora": "2026-11-10T20:50:00", "resultado": "NEGADO_DESCONHECIDO",
                                      "similaridade": 0.9, "evidencia": "/x/20261110_205000_NEGADO_DESCONHECIDO.jpg"}])
        vm.recarregar()
        apoio_v2.esperar_estado(ctx, vm)
        por_id = {r["id"]: r for r in vm.regras}
        assert por_id["I6"]["situacao"] == "observar" and por_id["I6"]["marca"] == "1 a observar"
        textos = apoio_v2.textos_visiveis(ctx.janela)
        assert "confere" in textos and "1 a observar" in textos
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_sem_avisos_nas_duas_abas(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        db = tmp_path / "t.db"
        _episodio(db)
        _com_pessoa(db)
        vm_inc = _abrir(ctx, "incidentes")
        assert vm_inc.contagens["todos"] == 2
        vm_int = apoio_v2.abrir_aba(ctx, "painel", "integridade")
        apoio_v2.esperar_estado(ctx, vm_int)
        ctx.girar(0.2)
        for vm in (vm_inc, vm_int):
            assert apoio_v2.sem_vetor_128(apoio_v2.props_do_vm(vm))
        assert apoio_v2.sem_vetor_128(vm_inc.incidentes.itens())
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
