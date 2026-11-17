"""Aba Visão geral do Painel (L1): ViewModel e tela, com banco temporário e câmera ausente."""

from __future__ import annotations

from datetime import datetime, timedelta

from tests import apoio_v2
from tests.apoio_v2 import _config_isolada  # noqa: F401

NOME = "Maria Exemplo da Silva"


def _linhas(n: int, base: datetime | None = None) -> list[dict]:
    base = base or datetime(2026, 11, 3, 8, 0, 0)
    tipos = ["CONCEDIDO", "CONCEDIDO", "NEGADO_DESCONHECIDO", "NEGADO_NIVEL", "CONCEDIDO"]
    linhas = []
    for i in range(n):
        res = tipos[i % len(tipos)]
        linha = {"data_hora": (base + timedelta(hours=7 * i)).isoformat(timespec="seconds"), "resultado": res,
                 "similaridade": 0.62 if res != "NEGADO_DESCONHECIDO" else 0.21}
        if res != "NEGADO_DESCONHECIDO":
            linha.update(usuario_id=None, nome_detectado=NOME, nivel_usuario=3 if res == "CONCEDIDO" else 1,
                         mensagem=f"{NOME}: mensagem do terminal")
        linhas.append(linha)
    return linhas


def _abrir(ctx):
    vm = apoio_v2.abrir_aba(ctx, "painel", "geral")
    apoio_v2.esperar_estado(ctx, vm)
    ctx.girar(0.2)
    return vm


def test_painel_vazio_mostra_convite(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        vm = _abrir(ctx)
        assert vm.estado == "vazio" and vm.total == 0
        textos = apoio_v2.textos_visiveis(ctx.janela)
        assert "Ainda não há tentativas registradas" in textos and "Abrir terminal" in textos
        assert len(vm.postura) >= 9 and "Prova de vida no terminal" in textos     # a postura aparece mesmo vazia
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_painel_reflete_o_registro(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apoio_v2.semear_acessos(tmp_path / "t.db", _linhas(40))
        vm = _abrir(ctx)
        assert vm.estado == "pronto" and vm.total == 40
        series = {s["nome"]: s["valores"][0] for s in vm.composicao["series"]}
        assert series["Concedido"] == 24 and series["Não cadastrado"] == 8 and series["Nível insuficiente"] == 8
        assert series["Bloqueio"] == 0 and sum(series.values()) == 40
        assert vm.manchete == "40 tentativas, 24 autorizadas."
        assert vm.limiar > 0 and len(vm.fita["faixas"]) == 7
        assert sum(sum(s["contagens"]) for s in vm.espectro["series"]) == 40
        assert "40 tentativas, 24 autorizadas." in apoio_v2.textos_visiveis(ctx.janela)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_painel_recalcula_ao_voltar_sem_aviso(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        vm = _abrir(ctx)
        assert vm.total == 0
        ctx.apl.navegar("terminal")
        ctx.girar(0.3)
        apoio_v2.semear_acessos(tmp_path / "t.db", _linhas(5))      # sem banco_alterado, como o terminal
        ctx.apl.navegar("painel")
        ctx.girar(0.2)
        apoio_v2.esperar_estado(ctx, vm)
        assert vm.total == 5 and vm.estado == "poucos"
        assert "Poucos registros (N = 5): leia como tendência" in apoio_v2.textos_visiveis(ctx.janela)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_painel_anonimo_por_padrao(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        agora = datetime.now() - timedelta(minutes=5)
        apoio_v2.semear_acessos(tmp_path / "t.db", _linhas(12, base=agora - timedelta(hours=100)) + [
            {"data_hora": agora.isoformat(timespec="seconds"), "resultado": "CONCEDIDO", "nome_detectado": NOME,
             "nivel_usuario": 3, "similaridade": 0.7, "mensagem": f"Bem-vinda, {NOME}"}])
        vm = _abrir(ctx)
        assert vm.total == 13 and len(vm.agora) == 1
        nomes = apoio_v2.nomes_do_banco(tmp_path / "t.db")
        assert NOME in nomes
        props = repr(apoio_v2.props_do_vm(vm))
        textos = " ".join(apoio_v2.textos_visiveis(ctx.janela))
        for nome in nomes:
            assert nome not in props and nome not in textos
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_postura_avisa_prova_de_vida_desligada(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        vm = _abrir(ctx)
        linha = {p["chave"]: p for p in vm.postura}["liveness"]
        ligada = ctx.apl.terminal_vm.liveness
        assert linha["situacao"] == ("ok" if ligada else "aviso")
        ctx.apl.terminal_vm.definirLiveness(False)
        vm.recarregar()
        apoio_v2.esperar_estado(ctx, vm)
        linha = {p["chave"]: p for p in vm.postura}["liveness"]
        assert linha["situacao"] == "aviso" and linha["valor"] == "desligada"
        assert "o terminal decide sem o desafio" in linha["texto"]
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_diagnostico_nao_grava(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apoio_v2.semear_acessos(tmp_path / "t.db", _linhas(6) + [
            {"data_hora": "2026-11-10T08:00:00", "resultado": "NEGADO_DESCONHECIDO", "similaridade": 0.1,
             "evidencia": str(tmp_path / "sumiu" / "20261110_080000_NEGADO_DESCONHECIDO.jpg")}])
        vm = _abrir(ctx)
        antes = apoio_v2.retrato_banco(tmp_path / "t.db")
        vm.executarDiagnostico()
        assert ctx.esperar(lambda: not vm.diagnosticando, 30)
        apoio_v2.esperar_ocioso(ctx)
        assert apoio_v2.retrato_banco(tmp_path / "t.db") == antes
        itens = {d["item"]: d for d in vm.diagnostico}
        for item in ("Modelos carregados", "Banco em somente leitura", "Evidências ausentes", "Câmera", "Galeria",
                     "Tempo total"):
            assert item in itens, item
        assert itens["Modelos carregados"]["situacao"] == "ok"
        assert itens["Evidências ausentes"]["valor"] == "1 de 1" and itens["Evidências ausentes"]["situacao"] == "atencao"
        assert len(itens["Modelo de detecção · SHA-256"]["valor"]) == 8
        assert ctx.apl.camera.estado == "desligada"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_erro_de_leitura_nao_deixa_numero_antigo(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apoio_v2.semear_acessos(tmp_path / "t.db", _linhas(35))
        vm = _abrir(ctx)
        assert vm.total == 35
        (tmp_path / "t.db").unlink()
        vm.recarregar()
        apoio_v2.esperar_estado(ctx, vm)
        assert vm.estado == "erro" and vm.total == 0 and vm.manchete == ""
        assert vm.composicao == {} and vm.leituras == [] and vm.erro != ""
        assert "Não foi possível calcular" in apoio_v2.textos_visiveis(ctx.janela)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_sem_vetor_e_sem_avisos(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apoio_v2.semear_acessos(tmp_path / "t.db", _linhas(40))
        vm = _abrir(ctx)
        assert vm.estado == "pronto"
        assert apoio_v2.sem_vetor_128(apoio_v2.props_do_vm(vm))
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
