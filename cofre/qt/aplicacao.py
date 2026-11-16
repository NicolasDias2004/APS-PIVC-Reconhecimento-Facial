"""
Controlador do aplicativo Qt: banco, pipeline (carregado em segundo plano), câmera,
tarefas, navegação entre páginas e notificações. Os ViewModels ficam pendurados aqui
e o QML os acessa por `app.terminal`, `app.cadastro` etc.
"""

from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, Signal, Slot

from .. import __version__, config
from ..banco import Banco
from .camera import ServicoCamera
from .imagens import criar_provedor
from .tarefas import Tarefas
from .vm_acessos import AcessosVM
from .vm_avaliacao import AvaliacaoVM
from .vm_cadastro import CadastroVM
from .vm_config import ConfigVM
from .vm_sessao import SessaoVM
from .vm_terminal import TerminalVM
from .vm_usuarios import UsuariosVM

PAGINAS = ("terminal", "cadastro", "usuarios", "acessos", "avaliacao", "config")


class Aplicacao(QObject):
    paginaMudou = Signal()
    modelosProntosMudou = Signal()
    erroModelosMudou = Signal()
    notificacao = Signal(str, str)          # (tipo: ok | info | aviso | erro, texto)
    encerrando = Signal()                   # o QML descarrega as páginas antes do motor ser destruído

    def __init__(self, caminho_db=config.DB_PATH, fonte_camera: Callable[[], Any] | None = None,
                 carregar_modelos: bool = True, parent=None):
        super().__init__(parent)
        self.banco = Banco(caminho_db)
        self.camera = ServicoCamera(fonte_camera, self)
        self.tarefas = Tarefas(self)
        self.imagens = criar_provedor()
        self.pipeline = None
        self._pagina = ""
        self._erro_modelos = ""
        self._fechado = False
        self.config_vm = ConfigVM(self, self)
        self.config_vm.carregar_inicial()           # aplica o config_usuario.json, se existir
        self.terminal_vm = TerminalVM(self, self)
        self.cadastro_vm = CadastroVM(self, self)
        self.usuarios_vm = UsuariosVM(self, self)
        self.acessos_vm = AcessosVM(self, self)
        self.avaliacao_vm = AvaliacaoVM(self, self)
        self.sessao_vm = SessaoVM(self, self)
        self.sessao_vm.aberta.connect(self._sessao_aberta)
        self.sessao_vm.encerrada.connect(self._sessao_encerrada)
        self._vms = {"terminal": self.terminal_vm, "cadastro": self.cadastro_vm, "usuarios": self.usuarios_vm,
                     "acessos": self.acessos_vm, "avaliacao": self.avaliacao_vm, "config": self.config_vm}
        self.config_vm.configAplicada.connect(self.terminal_vm.similaridadeMudou)   # o limiar exibido muda
        if carregar_modelos:
            self.carregar_modelos()

    # ------------------------------------------------------------------ modelos
    def carregar_modelos(self) -> None:
        def carregar():
            from ..pipeline import Pipeline
            return Pipeline()

        def pronto(pipeline, erro: str) -> None:
            if erro:
                self._erro_modelos = f"Falha ao carregar os modelos: {erro}"
                self.erroModelosMudou.emit()
                self.notificar("erro", self._erro_modelos)
                return
            self.usar_pipeline(pipeline)

        self.tarefas.executar(carregar, pronto)

    def usar_pipeline(self, pipeline) -> None:
        """Instala o pipeline carregado e avisa as páginas (os testes passam um já pronto)."""
        self.pipeline = pipeline
        self.modelosProntosMudou.emit()
        for vm in self._vms.values():
            try:
                vm.ao_pipeline_pronto()
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    def _get_modelos_prontos(self) -> bool:
        return self.pipeline is not None

    def _get_erro_modelos(self) -> str:
        return self._erro_modelos

    modelosProntos = Property(bool, _get_modelos_prontos, notify=modelosProntosMudou)
    erroModelos = Property(str, _get_erro_modelos, notify=erroModelosMudou)

    # ------------------------------------------------------------------ navegação
    def _get_pagina(self) -> str:
        return self._pagina

    pagina = Property(str, _get_pagina, notify=paginaMudou)

    @Slot(str)
    def navegar(self, pagina: str) -> None:
        if pagina not in PAGINAS or pagina == self._pagina or self.sessao_vm.ativa:
            return      # com a área liberada aberta a navegação fica travada até encerrar a sessão
        anterior = self._vms.get(self._pagina)
        if anterior is not None:
            try:
                anterior.desativar()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        self._pagina = pagina
        self.paginaMudou.emit()
        try:
            self._vms[pagina].ativar()
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.notificar("erro", f"Falha ao abrir a página: {e}")

    # ------------------------------------------------------------------ área liberada
    def _sessao_aberta(self) -> None:
        self.terminal_vm.pausar()        # câmera desligada enquanto a área está aberta

    def _sessao_encerrada(self, motivo: str) -> None:
        if self._pagina == "terminal":
            self.terminal_vm.retomar()

    # ------------------------------------------------------------------ eventos entre páginas
    def banco_alterado(self, origem=None) -> None:
        """Usuários, amostras ou log mudaram: recarrega a galeria do terminal e as listas abertas."""
        for vm in self._vms.values():
            if vm is origem:
                continue
            try:
                vm.ao_banco_alterado()
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    @Slot(str, str)
    def notificar(self, tipo: str, texto: str) -> None:
        self.notificacao.emit(tipo, texto)

    # ------------------------------------------------------------------ acesso pelo QML
    def _vm(nome):  # noqa: N805 (fábrica de propriedades)
        return Property(QObject, lambda self: self._vms[nome], constant=True)

    terminal = _vm("terminal")
    cadastro = _vm("cadastro")
    usuarios = _vm("usuarios")
    acessos = _vm("acessos")
    avaliacao = _vm("avaliacao")
    configuracoes = _vm("config")
    del _vm

    def _get_sessao(self):
        return self.sessao_vm

    sessao = Property(QObject, _get_sessao, constant=True)

    def _get_camera(self):
        return self.camera

    def _get_tarefas(self):
        return self.tarefas

    cameraServico = Property(QObject, _get_camera, constant=True)
    tarefasServico = Property(QObject, _get_tarefas, constant=True)

    @Slot(result=str)
    def versao(self) -> str:
        return __version__

    @Slot(result=str)
    def nomeBanco(self) -> str:
        return getattr(self.banco.caminho, "name", str(self.banco.caminho))

    @Slot(result="QVariantList")
    def niveis(self) -> list:
        return [{"nivel": n, "descricao": config.NIVEIS[n], "area": config.AREAS[n]} for n in sorted(config.NIVEIS)]

    # ------------------------------------------------------------------ encerramento
    def fechar(self) -> None:
        if self._fechado:
            return
        self._fechado = True
        self.encerrando.emit()
        vm = self._vms.get(self._pagina)
        try:
            self.sessao_vm.encerrar()
            if vm is not None:
                vm.desativar()
            if self.cadastro_vm.capturando:
                self.cadastro_vm.cancelar()      # cadastro pela metade não fica no banco
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        self.camera.parar()
        self.tarefas.esperar(5000)
        self.banco.fechar()
