"""Integração da v2 (seção 8.8, escopo enxuto): ligações entre telas e uma visita com o cálculo real de
cada aba, conferindo que nada grava no banco, nada muda parâmetro, nenhum nome aparece por padrão e
nenhuma propriedade nova carrega vetor. A paleta (F14), o roteiro (F15) e o PDF (F16) ficaram fora.
"""

from __future__ import annotations

from PySide6.QtCore import QMetaObject

from cofre.qt import extensoes as mod_extensoes
from tests import apoio_v2
from tests.apoio_v2 import _config_isolada  # noqa: F401
from tests.apoio_interface import FOTO_BIDEN, FOTO_OBAMA, FOTO_OBAMA_2

NOMES = ("Barack Teste Integracao", "Joe Teste Integracao")


def _clicar(ctx, nome: str) -> None:
    visiveis = [b for b in apoio_v2.itens(ctx.janela, lambda i: i.objectName() == nome) if b.isVisible()]
    assert visiveis, f"botão {nome!r} não está visível na tela"
    botao = visiveis[0]
    QMetaObject.invokeMethod(botao, "clicked")
    ctx.girar(0.3)


def _onde(ctx) -> tuple[str, str]:
    pagina = ctx.apl.pagina
    vm = ctx.apl.extensoes.obter(pagina) if pagina in mod_extensoes.PAGINAS_V2 else None
    return pagina, (vm.aba if vm is not None else "")


def _preparar_foto(ctx) -> None:
    lab = ctx.apl.extensoes.obter("laboratorio")
    lab.usarFotoTeste(0)
    assert apoio_v2.esperar_ocioso(ctx) and not lab.processando, lab.erro


def test_irPara_escolhe_a_aba_e_navega(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        x = ctx.apl.extensoes
        for pagina, abas in mod_extensoes.ABAS.items():
            for valor, *_ in abas:
                x.irPara(pagina, valor)
                ctx.girar(0.15)
                assert _onde(ctx) == (pagina, valor)
        x.irPara("inexistente", "geral")                 # página fora da v2: não faz nada
        assert _onde(ctx)[0] in mod_extensoes.PAGINAS_V2
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_todas_as_ligacoes_levam_ao_destino(qapp, tmp_path, pipeline):
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        x = ctx.apl.extensoes
        # Painel · Visão geral: postura (limiar) e diagnóstico
        for botao, destino in (("botaoVerSeparacao", ("resultados", "separacao")),
                               ("botaoVerSaudeCadastro", ("resultados", "galeria"))):
            vm = apoio_v2.abrir_aba(ctx, "painel", "geral")
            apoio_v2.esperar_estado(ctx, vm)
            ctx.girar(0.2)
            _clicar(ctx, botao)
            assert _onde(ctx) == destino, botao

        # Laboratório · Fases, estação 5 -> Robustez
        _preparar_foto(ctx)
        vm = apoio_v2.abrir_aba(ctx, "laboratorio", "fases")
        apoio_v2.esperar_estado(ctx, vm)
        vm.definirEstacao(5)
        ctx.girar(0.3)
        _clicar(ctx, "botaoTestarRobustez")
        assert _onde(ctx) == ("laboratorio", "robustez")

        # Laboratório · Robustez, quebra de oclusão dos olhos -> Explicabilidade
        rob = x.obter("labRobustez")
        apoio_v2.esperar_estado(ctx, rob)
        rob.varrer()
        assert apoio_v2.esperar_ocioso(ctx, 60) and any(q["familia"] == "oclusao_olhos" for q in rob.quebras)
        ctx.girar(0.3)
        _clicar(ctx, "botaoVerOndeOlha")
        assert _onde(ctx) == ("laboratorio", "explicabilidade")

        # Laboratório · Explicabilidade -> Robustez
        apoio_v2.esperar_estado(ctx, x.obter("labExplicabilidade"))
        ctx.girar(0.2)
        _clicar(ctx, "botaoVerCurvasOclusao")
        assert _onde(ctx) == ("laboratorio", "robustez")

        # Resultados · Separação, clássico × profundo -> Laboratório · Explicabilidade
        sep = apoio_v2.abrir_aba(ctx, "resultados", "separacao")
        sep.definirProtocolo("fotos_teste")
        sep.calcular()
        apoio_v2.esperar_estado(ctx, sep, 60)
        assert sep.descritores
        ctx.girar(0.3)
        _clicar(ctx, "botaoVerOndeOlhaSeparacao")
        assert _onde(ctx) == ("laboratorio", "explicabilidade")
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_visitar_tudo_preenchido_nao_altera_banco_nem_parametros(qapp, tmp_path, pipeline):
    """T3 com o cálculo real de cada aba; na mesma visita, nenhum nome por padrão e nenhum vetor nas props."""
    caminho = tmp_path / "t.db"
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apl, x = ctx.apl, ctx.apl.extensoes
        obama = apoio_v2.cadastrar(ctx, NOMES[0], "M1", 3, [FOTO_OBAMA, FOTO_OBAMA_2])
        apoio_v2.cadastrar(ctx, NOMES[1], "M2", 2, [FOTO_BIDEN])
        apoio_v2.semear_acessos(caminho, [
            {"data_hora": "2026-11-05T10:00:00", "resultado": "CONCEDIDO", "usuario_id": obama.id,
             "nome_detectado": NOMES[0], "nivel_usuario": 3, "nivel_exigido": 2, "similaridade": 0.71},
            {"data_hora": "2026-11-05T10:02:00", "resultado": "NEGADO_DESCONHECIDO", "similaridade": 0.2},
            {"data_hora": "2026-11-05T10:02:30", "resultado": "NEGADO_NIVEL", "usuario_id": obama.id,
             "nome_detectado": NOMES[0], "nivel_usuario": 3, "nivel_exigido": 3, "similaridade": 0.66}])
        apl.banco_alterado()
        banco_antes, parametros_antes = apoio_v2.retrato_banco(caminho), apoio_v2.retrato_parametros()
        assert x.obter("privacidade").mostrarNomes is False

        _preparar_foto(ctx)
        vistos: list[str] = []
        for pagina, abas in mod_extensoes.ABAS.items():
            for valor, _texto, chave, _fonte in abas:
                vm = apoio_v2.abrir_aba(ctx, pagina, valor)
                apoio_v2.esperar_estado(ctx, vm, 60)
                if chave == "painelGeral":
                    vm.executarDiagnostico()
                elif chave == "labRobustez":
                    vm.varrer()
                elif chave in ("labExplicabilidade", "resQualidade"):
                    if chave == "resQualidade":
                        vm.usarFotosTeste()
                    vm.calcular()
                elif chave == "resSeparacao":
                    vm.definirProtocolo("fotos_teste")
                    vm.calcular()
                apoio_v2.esperar_ocioso(ctx, 60)
                apoio_v2.esperar_estado(ctx, vm, 60)
                ctx.girar(0.3)
                vistos.extend(apoio_v2.textos_visiveis(ctx.janela))
                assert vm.estado != "carregando", chave
        assert apoio_v2.esperar_ocioso(ctx, 60)

        texto = "\n".join(vistos).lower()
        for nome in NOMES:
            for parte in nome.lower().split():
                if parte not in ("teste",):
                    assert parte not in texto, f"{parte!r} apareceu numa tela nova"
        for chave, *_ in mod_extensoes.REGISTRO:
            props = apoio_v2.props_do_vm(x.obter(chave))
            for nome, valor in props.items():
                assert apoio_v2.sem_vetor_128(valor), f"{chave}.{nome} carrega algo com cara de vetor"

        assert apoio_v2.retrato_banco(caminho) == banco_antes
        assert apoio_v2.retrato_parametros() == parametros_antes
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()


def test_desligar_nomes_tira_os_nomes_na_hora(qapp, tmp_path, pipeline):
    """Revisão de segurança: com a chave desligada, nenhum nome fica nas propriedades da Galeria, nem com
    a aba fora da tela nem depois de cancelar o recálculo (antes ficava o resultado antigo, com nome)."""
    ctx = apoio_v2.contexto(qapp, tmp_path, pipeline)
    try:
        apoio_v2.cadastrar(ctx, NOMES[0], "R-1", 1, [FOTO_OBAMA, FOTO_OBAMA_2])
        apoio_v2.cadastrar(ctx, NOMES[1], "R-2", 2, [FOTO_BIDEN])
        vm = apoio_v2.abrir_aba(ctx, "resultados", "galeria")
        apoio_v2.esperar_estado(ctx, vm, 30)
        privacidade = ctx.apl.extensoes.obter("privacidade")
        privacidade.definirMostrarNomes(True)
        apoio_v2.esperar_estado(ctx, vm, 30)

        def tudo() -> str:
            return repr(apoio_v2.props_do_vm(vm)) + repr(vm.saude.itens()) + " ".join(apoio_v2.textos_visiveis(ctx.janela))

        assert NOMES[0] in tudo()
        ctx.apl.navegar("painel")
        ctx.girar(0.3)
        privacidade.definirMostrarNomes(False)
        assert NOMES[0] not in tudo()
        ctx.apl.navegar("resultados")
        vm.cancelar()
        ctx.girar(0.3)
        assert all(nome not in tudo() for nome in NOMES)
        assert ctx.avisos_qml() == []
    finally:
        ctx.fechar()
