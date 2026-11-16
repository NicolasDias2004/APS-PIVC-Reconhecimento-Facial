"""Aplicativo Qt Quick (PySide6 + QML) sem tela: carga das páginas, terminal, cadastro, usuários,
auditoria, avaliação e configurações. Câmera falsa, banco temporário e pipeline real."""

from __future__ import annotations

import pytest

from cofre import config, parametros
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from tests.apoio_interface import FOTO_BIDEN, FOTO_BIDEN_2, FOTO_OBAMA, FOTO_OBAMA_2, FIX
from tests.apoio_qt import criar_contexto

PAGINAS = ("terminal", "cadastro", "usuarios", "acessos", "avaliacao", "config")


@pytest.fixture(autouse=True)
def _config_isolada(tmp_path, monkeypatch):
    """Pasta de dados temporária (config_usuario.json) e parâmetros restaurados ao fim do teste."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    antes = parametros.valores_atuais()
    yield
    parametros.aplicar(antes)


def _contexto(qapp, tmp_path, pipeline, imagens=None):
    return criar_contexto(qapp, tmp_path / "t.db", pipeline=pipeline, imagens=imagens)


def _cadastrar(ctx, nome, matricula, nivel, fotos):
    u, n, _ = cadastrar_de_imagens(ctx.apl.banco, ctx.apl.pipeline, DadosCadastro(nome, matricula, "", nivel), fotos)
    assert n == len(fotos)
    ctx.apl.banco_alterado()
    return u


# ---------------------------------------------------------------------------- estrutura
def test_todas_as_paginas_carregam_sem_avisos_qml(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        assert ctx.janela is not None, ctx.avisos
        for pagina in PAGINAS:
            ctx.apl.navegar(pagina)
            ctx.girar(0.4)
            assert ctx.apl.pagina == pagina
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_sem_camera_mostra_erro_e_nao_decide(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)          # SemCamera: falha ao abrir
    try:
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: ctx.apl.camera.estado == "erro", 5)
        t = ctx.apl.terminal
        assert ctx.apl.camera.erro != ""                    # a tela mostra o erro do serviço da câmera
        assert t.resultadoConcedido is False and t.estado != "RESULTADO"
        assert ctx.apl.banco.listar_acessos() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- terminal
def test_terminal_concede_quando_o_backend_concede(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    try:
        _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA_2])
        t = ctx.apl.terminal
        t.definirLiveness(False)
        t.definirNivel(3)
        decisoes = []
        t.decisaoTomada.connect(lambda ok, tipo: decisoes.append((ok, tipo)))
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: t.estado == "RESULTADO", 20)
        assert t.resultadoTipo == "CONCEDIDO" and t.resultadoConcedido is True
        assert t.resultadoNome == "Barack Obama"
        # a tela só repete o que o backend decidiu e registrou
        assert ctx.apl.terminal_vm.terminal.decisao_atual.concedido is True
        assert ctx.apl.banco.listar_acessos()[0].resultado == "CONCEDIDO"
        assert decisoes and decisoes[0] == (True, "CONCEDIDO")
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_terminal_nega_e_bloqueia_sem_nunca_mostrar_concedido(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.5)
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_BIDEN])
    try:
        _cadastrar(ctx, "Joe Biden", "D1", 2, [FOTO_BIDEN_2])
        t = ctx.apl.terminal
        t.definirLiveness(False)
        t.definirNivel(3)                                  # Biden tem nível 2: negado por nível
        vistos = []
        t.estadoMudou.connect(lambda: vistos.append((t.estado, t.resultadoConcedido)))
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: t.estado == "BLOQUEADO", 40), ctx.apl.banco.listar_acessos()
        assert not any(concedido for _, concedido in vistos)
        assert t.resultadoConcedido is False and t.bloqueadoRestante > 0
        resultados = [a.resultado for a in ctx.apl.banco.listar_acessos()]
        assert "CONCEDIDO" not in resultados and "BLOQUEADO" in resultados
        assert resultados.count("NEGADO_NIVEL") >= config.MAX_TENTATIVAS_FALHAS
        # controles travados durante o bloqueio (também pelos atalhos de teclado)
        t.definirNivel(1)
        t.definirLiveness(True)
        assert t.nivel == 3 and t.liveness is False
        ctx.girar(1.0)
        assert t.estado == "BLOQUEADO" and t.resultadoConcedido is False
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_fechar_libera_a_camera(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    ctx.apl.navegar("terminal")
    assert ctx.esperar(lambda: ctx.apl.camera.estado == "ativa", 10)
    camera = ctx.apl.camera
    ctx.fechar()
    assert camera.estado == "desligada"
    assert camera._thread is None or not camera._thread.isRunning()


# ---------------------------------------------------------------------------- cadastro
def test_cadastro_valida_campos(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        c = ctx.apl.cadastro
        assert c.iniciarCaptura("", "X1", "", 1) is False and c.erroCampo == "nome"
        assert c.iniciarCaptura("Ana", "", "", 1) is False and c.erroCampo == "matricula"
        _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        assert c.matriculaEmUso("M1") == "Barack Obama"
        assert c.cadastrarPorFotos("Outra", "M1", "", 1, [str(FOTO_BIDEN)]) is False
        assert c.erroCampo == "matricula" and "já cadastrada" in c.erro
    finally:
        ctx.fechar()


def test_cadastro_por_fotos_em_segundo_plano(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        c = ctx.apl.cadastro
        urls = ["file://" + str(FOTO_OBAMA), "file://" + str(FOTO_OBAMA_2)]
        assert c.cadastrarPorFotos("Barack Obama", "M1", "Ministro", 3, urls) is True
        assert ctx.esperar(lambda: c.fase == "formulario" and c.sucesso.get("nome") == "Barack Obama", 20)
        u = ctx.apl.banco.obter_por_matricula("M1")
        assert u is not None and u.nivel == 3 and ctx.apl.banco.contar_amostras(u.id) == 2
        assert ctx.apl.terminal.usuariosAtivos == 1          # o terminal recarregou a galeria
    finally:
        ctx.fechar()


def test_cadastro_pela_camera_conclui_e_cancela(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(config, "AMOSTRAS_POR_CADASTRO", 3)
    monkeypatch.setattr(config, "INTERVALO_AMOSTRAS_SEG", 0.2)
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    try:
        c = ctx.apl.cadastro
        ctx.apl.navegar("cadastro")
        assert c.iniciarCaptura("Barack Obama", "M1", "", 3) is True
        assert ctx.esperar(lambda: c.capturadas >= 3, 20), c.status
        assert c.total == 3 and c.sessao.amostras == 3      # a quantidade configurada vale de fato
        c.concluir()
        u = ctx.apl.banco.obter_por_matricula("M1")
        assert u is not None and ctx.apl.banco.contar_amostras(u.id) == 3
        assert c.fase == "formulario" and c.sucesso.get("amostras") == 3

        assert c.iniciarCaptura("Outro", "M2", "", 1) is True
        assert ctx.esperar(lambda: c.capturadas >= 1, 20)
        c.cancelar()
        assert ctx.apl.banco.obter_por_matricula("M2") is None   # nada fica gravado
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_fechar_no_meio_do_cadastro_desfaz(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    c = ctx.apl.cadastro
    ctx.apl.navegar("cadastro")
    assert c.iniciarCaptura("Barack Obama", "M1", "", 3)
    assert ctx.esperar(lambda: c.capturadas >= 1, 20)
    banco_path = ctx.apl.banco.caminho
    ctx.fechar()
    from cofre.banco import Banco
    b = Banco(banco_path)
    try:
        assert b.obter_por_matricula("M1") is None
    finally:
        b.fechar()


# ---------------------------------------------------------------------------- usuários
def test_usuarios_filtros_e_acoes(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        ob = _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        bi = _cadastrar(ctx, "Joe Biden", "D1", 2, [FOTO_BIDEN])
        u = ctx.apl.usuarios
        ctx.apl.navegar("usuarios")
        assert u.total == 2 and u.modelo.contagem == 2 and list(u.porNivel) == [0, 1, 1]
        u.definirBusca("bid")
        assert [i["nome"] for i in u.modelo.itens()] == ["Joe Biden"]
        u.limparFiltros()
        u.definirFiltroNivel(3)
        assert [i["nome"] for i in u.modelo.itens()] == ["Barack Obama"]
        u.limparFiltros()

        assert u.alterarNivel(bi.id, 1) is True and ctx.apl.banco.obter_usuario(bi.id).nivel == 1
        assert u.alterarNivel(bi.id, 9) is False
        assert u.alternarAtivo(bi.id) is True and not ctx.apl.banco.obter_usuario(bi.id).ativo
        assert ctx.apl.terminal.usuariosAtivos == 1
        u.definirFiltroStatus("inativos")
        assert [i["nome"] for i in u.modelo.itens()] == ["Joe Biden"]
        assert u.fotos(ob.id) and all(f["existe"] for f in u.fotos(ob.id))
        assert u.remover(bi.id) is True and ctx.apl.banco.obter_usuario(bi.id) is None
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_usuario_em_cadastro_nao_pode_ser_removido(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    try:
        c, u = ctx.apl.cadastro, ctx.apl.usuarios
        ctx.apl.navegar("cadastro")
        assert c.iniciarCaptura("Barack Obama", "M1", "", 3)
        assert ctx.esperar(lambda: c.sessao is not None, 10)
        ctx.apl.navegar("usuarios")                         # captura pausada em outra tela
        linha = u.modelo.itens()[0]
        assert linha["emCadastro"] is True
        assert u.remover(linha["id"]) is False and u.alternarAtivo(linha["id"]) is False
        assert ctx.apl.banco.obter_usuario(linha["id"]) is not None
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- auditoria
def test_acessos_filtros_detalhe_e_exportacao(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        ob = _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA])
        b = ctx.apl.banco
        b.registrar_acesso(usuario_id=ob.id, nome_detectado=ob.nome, nivel_usuario=3, nivel_exigido=3,
                           similaridade=0.8, resultado="CONCEDIDO")
        b.registrar_acesso(usuario_id=None, nome_detectado=None, nivel_usuario=None, nivel_exigido=1,
                           similaridade=0.1, resultado="NEGADO_DESCONHECIDO")
        a = ctx.apl.acessos
        ctx.apl.navegar("acessos")
        assert a.total == 2 and a.concedidos == 1 and a.negados == 1 and a.taxa == 0.5
        a.definirFiltroResultado("CONCEDIDO")
        assert [i["nome"] for i in a.modelo.itens()] == ["Barack Obama"]
        a.limparFiltros()
        a.filtrarPessoa("DESCONHECIDO")
        assert [i["resultado"] for i in a.modelo.itens()] == ["NEGADO_DESCONHECIDO"]
        a.limparFiltros()
        a.definirFiltroNivel(3)
        assert a.listados == 1
        a.definirFiltroResultado("NAO_EXISTE")              # valor inválido é ignorado
        assert a.filtroResultado == ""
        d = a.detalhe(a.modelo.itens()[0]["id"])
        assert d["concedido"] is True and d["limiar"] == f"{config.LIMIAR_COSSENO:.3f}"

        a.exportar("csv")
        assert ctx.esperar(lambda: not a.exportando and a.ultimoExportado != "", 10)
        from pathlib import Path
        assert Path(a.ultimoExportado).exists()
        assert len(b.listar_acessos()) == 2                  # a auditoria nunca grava no log
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- avaliação
def test_avaliacao_demo_autenticacao_e_metricas(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        _cadastrar(ctx, "Joe Biden", "D1", 2, [FOTO_BIDEN_2])
        v = ctx.apl.avaliacao
        ctx.apl.navegar("avaliacao")
        v.demonstrar(str(FOTO_OBAMA))
        assert ctx.esperar(lambda: not v.demoProcessando and len(v.demoFases) == 5, 20)
        assert len(v.demoEtapas) >= 5 and v.fonteDemo.temImagem
        assert ctx.apl.banco.listar_acessos() == []           # a demonstração não grava no log

        v.definirNivelAuth(3)
        v.autenticar(str(FOTO_BIDEN))
        assert ctx.esperar(lambda: not v.authProcessando and v.authResultado.get("resultado"), 20)
        assert v.authResultado["resultado"] == "NEGADO_NIVEL" and v.authResultado["concedido"] is False
        assert [a.resultado for a in ctx.apl.banco.listar_acessos()] == ["NEGADO_NIVEL"]   # registrada

        v.usarFotosTeste()
        v.avaliar()
        assert ctx.esperar(lambda: not v.avalProcessando and v.avalResultado.get("valido") is not None, 60)
        r = v.avalResultado
        assert r["valido"] is True and r["pessoas"] == len([p for p in FIX.iterdir() if p.is_dir()])
        assert all(isinstance(p["limiar"], float) for p in r["curva"])
        atuais = [i for i in v.modeloVarredura.itens() if i["atual"] is True]
        assert len(atuais) == 1
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- configurações
def test_config_valida_aplica_e_salva(qapp, tmp_path, pipeline):
    ctx = _contexto(qapp, tmp_path, pipeline)
    try:
        c = ctx.apl.configuracoes
        ctx.apl.navegar("config")
        limiar = config.LIMIAR_COSSENO
        assert c.definir("LIMIAR_COSSENO", "0,4") is True and c.pendentes == 1
        assert config.LIMIAR_COSSENO == limiar                 # só vale depois de aplicar
        assert c.definir("LIMIAR_COSSENO", "abc") is False and c.mensagemTipo == "erro"
        assert c.definir("LIMIAR_COSSENO", 5) is True           # fora do intervalo: limitado
        campo = next(i for i in c.modeloCampos.itens() if i["chave"] == "LIMIAR_COSSENO")
        assert campo["valor"] == parametros.CAMPOS_POR_CHAVE["LIMIAR_COSSENO"].maximo
        c.definir("LIMIAR_COSSENO", 0.4)
        assert c.aplicar() is True and config.LIMIAR_COSSENO == 0.4 and c.pendentes == 0
        assert ctx.apl.terminal.limiar == 0.4
        c.descartar()

        # parâmetros fixados na importação são somente leitura (sem efeito real se mudados)
        bloqueio = config.BLOQUEIO_SEG
        assert c.definir("BLOQUEIO_SEG", 5) is False and config.BLOQUEIO_SEG == bloqueio
        campo = next(i for i in c.modeloCampos.itens() if i["chave"] == "MAX_TENTATIVAS_FALHAS")
        assert campo["editavel"] is False and campo["seguranca"] is True

        assert c.salvar() is True and parametros.caminho_arquivo().exists()
        assert parametros.caminho_arquivo().parent == tmp_path
        assert c.carregar() is True
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_terminal_mostra_orientacao_de_pose_e_leituras(qapp, tmp_path, pipeline, monkeypatch):
    from cofre.fase3_segmentacao import Rosto
    ctx = _contexto(qapp, tmp_path, pipeline, imagens=[FOTO_OBAMA])
    try:
        _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA_2])
        t = ctx.apl.terminal
        t.definirLiveness(False)
        monkeypatch.setattr(Rosto, "problema_pose", lambda self: "Endireite a cabeça")
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: t.orientacao == "Endireite a cabeça", 15)
        ctx.girar(1.0)
        assert t.estado == "AGUARDANDO" and t.resultadoTipo == "" and ctx.apl.banco.listar_acessos() == []
        assert t.poseYaw > -90 and len(t.assinatura) == 128 and len(t.assinaturaReferencia) == 128
        assert t.limitesPose()["yaw"] == config.POSE_MAX_YAW
        monkeypatch.undo()
        assert ctx.esperar(lambda: t.estado == "RESULTADO", 20)
        assert t.orientacao == "" and t.resultadoTipo == "CONCEDIDO"
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


# ---------------------------------------------------------------------------- área liberada
def test_area_liberada_abre_so_com_concessao_do_backend(qapp, tmp_path, pipeline, monkeypatch):
    import numpy as np
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.5)
    imagens = [FOTO_BIDEN]
    ctx = criar_contexto(qapp, tmp_path / "t.db", pipeline=pipeline, imagens=imagens)
    try:
        bi = _cadastrar(ctx, "Joe Biden", "D1", 2, [FOTO_BIDEN_2])
        t, s = ctx.apl.terminal, ctx.apl.sessao
        t.definirLiveness(False)
        t.definirNivel(3)                                   # nível 2 numa área de nível 3: negado
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: t.estado == "RESULTADO", 20) and t.resultadoTipo == "NEGADO_NIVEL"
        assert s.ativa is False and s.conteudo(1) == {}     # negado: nada abre, nada é lido
        # o QML não consegue abrir a sessão por conta própria
        assert s.abrir(None, 1) is False and s.ativa is False

        # troca a área já: mais duas negações seguidas bloqueariam o terminal
        ctx.apl.terminal.definirNivel(2)                    # agora a área é compatível: concedido
        assert ctx.esperar(lambda: s.ativa, 25), (t.estado, t.resultadoTipo)
        assert s.nome == "Joe Biden" and s.nivelUsuario == 2 and s.areaSolicitada == 2
        assert [a["nivel"] for a in s.areas if a["liberada"]] == [1, 2]
        assert s.liberada(1) and s.liberada(2) and not s.liberada(3)
        assert s.conteudo(1)["titulo"] == config.AREAS[1] and s.conteudo(2)["divisoes"]
        assert s.conteudo(3) == {}                          # acima do nível: vazio
        assert ctx.esperar(lambda: ctx.apl.camera.estado == "desligada", 5)   # câmera pausada
        ctx.apl.navegar("usuarios")
        assert ctx.apl.pagina == "terminal"                 # navegação travada com a sessão aberta
        assert len(ctx.apl.banco.listar_acessos()) == 2     # só as duas decisões do backend no log

        imagens[0] = np.zeros((480, 640, 3), np.uint8)      # ninguém na frente da câmera ao encerrar
        s.encerrar()
        assert s.ativa is False and s.conteudo(1) == {}
        assert ctx.esperar(lambda: ctx.apl.camera.estado == "ativa", 10)      # câmera volta
        assert ctx.esperar(lambda: t.estado == "AGUARDANDO", 5)
        ctx.girar(1.0)
        assert s.ativa is False and len(ctx.apl.banco.listar_acessos()) == 2  # nada reabriu sozinho
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_area_liberada_fecha_por_inatividade_e_respeita_usuario_desativado(qapp, tmp_path, pipeline, monkeypatch):
    monkeypatch.setattr(config, "SESSAO_LIBERADA_SEG", 2)
    ctx = criar_contexto(qapp, tmp_path / "t.db", pipeline=pipeline, imagens=[FOTO_OBAMA])
    try:
        ob = _cadastrar(ctx, "Barack Obama", "M1", 3, [FOTO_OBAMA_2])
        t, s = ctx.apl.terminal, ctx.apl.sessao
        t.definirLiveness(False)
        t.definirNivel(1)
        ctx.apl.navegar("terminal")
        assert ctx.esperar(lambda: s.ativa, 25)
        assert s.tempoTotal == 2 and [a["liberada"] for a in s.areas] == [True, True, True]
        s.renovar()
        assert ctx.esperar(lambda: not s.ativa, 6)          # fechou sozinha
        # usuário desativado depois da decisão: a sessão não abre mesmo com decisão concedida
        ctx.apl.banco.definir_ativo(ob.id, False)
        from cofre.fase5_reconhecimento import Decisao, Identificacao, Resultado
        falsa = Decisao(Resultado.CONCEDIDO, Identificacao(ctx.apl.banco.obter_usuario(ob.id), 0.9), 1, "ok")
        assert s.abrir(falsa, 1) is False and s.ativa is False
    finally:
        ctx.fechar()
