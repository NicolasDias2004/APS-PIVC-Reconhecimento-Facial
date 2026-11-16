"""ViewModel da administração de usuários: lista com busca e filtros, níveis, ativação,
remoção (com confirmação no QML) e fotos de referência."""

from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl, Signal, Slot

from .. import config
from .base import ViewModel, objeto, prop
from .modelos import ModeloLista


def _data_curta(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso or "–"


def _iniciais(nome: str) -> str:
    partes = [p for p in (nome or "").split() if p]
    if not partes:
        return "?"
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


class UsuariosVM(ViewModel):
    totalMudou = Signal()
    ativosMudou = Signal()
    porNivelMudou = Signal()
    buscaMudou = Signal()
    filtroNivelMudou = Signal()
    filtroStatusMudou = Signal()
    carregadoMudou = Signal()

    total = prop(int, "total", totalMudou)
    ativos = prop(int, "ativos", ativosMudou)
    porNivel = prop("QVariantList", "porNivel", porNivelMudou)
    busca = prop(str, "busca", buscaMudou)
    filtroNivel = prop(int, "filtroNivel", filtroNivelMudou)          # 0 = todos
    filtroStatus = prop(str, "filtroStatus", filtroStatusMudou)       # todos | ativos | inativos
    carregado = prop(bool, "carregado", carregadoMudou)
    modelo = objeto("lista")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(total=0, ativos=0, porNivel=[0, 0, 0], busca="", filtroNivel=0, filtroStatus="todos",
                      carregado=False)
        self.lista = ModeloLista(["id", "nome", "iniciais", "matricula", "cargo", "nivel", "nivelDescricao", "area",
                                  "ativo", "amostras", "criadoEm", "emCadastro"], self)
        self._todos: list[dict] = []

    def ativar(self) -> None:
        self.recarregar()

    def ao_banco_alterado(self) -> None:
        if self._v["carregado"]:
            self.recarregar()

    # ------------------------------------------------------------------ dados
    @Slot()
    def recarregar(self) -> None:
        try:
            usuarios = self.app.banco.listar_usuarios()
            amostras = {u.id: self.app.banco.contar_amostras(u.id) for u in usuarios}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.app.notificar("erro", f"Falha ao ler o banco: {e}")
            return
        # usuário criado por uma captura de cadastro ainda aberta (pausada em outra tela)
        sessao = getattr(self.app.cadastro, "sessao", None)
        em_cadastro = sessao.usuario.id if sessao is not None and not sessao.encerrada else None
        self._todos = [{
            "id": u.id, "nome": u.nome, "iniciais": _iniciais(u.nome), "matricula": u.matricula,
            "cargo": u.cargo or "", "nivel": int(u.nivel), "nivelDescricao": config.NIVEIS.get(u.nivel, "?"),
            "area": config.AREAS.get(u.nivel, ""), "ativo": bool(u.ativo), "amostras": int(amostras.get(u.id, 0)),
            "criadoEm": _data_curta(u.criado_em), "emCadastro": u.id == em_cadastro,
        } for u in usuarios]
        self._definir("total", len(self._todos))
        self._definir("ativos", sum(1 for u in self._todos if u["ativo"]))
        self._definir("porNivel", [sum(1 for u in self._todos if u["nivel"] == n) for n in sorted(config.NIVEIS)])
        self._definir("carregado", True)
        self._filtrar()

    def _filtrar(self) -> None:
        termo = self._v["busca"].strip().casefold()
        nivel, status = self._v["filtroNivel"], self._v["filtroStatus"]
        itens = []
        for u in self._todos:
            if termo and termo not in u["nome"].casefold() and termo not in u["matricula"].casefold() \
                    and termo not in u["cargo"].casefold():
                continue
            if nivel and u["nivel"] != nivel:
                continue
            if status == "ativos" and not u["ativo"] or status == "inativos" and u["ativo"]:
                continue
            itens.append(u)
        self.lista.definir(itens)

    @Slot(str)
    def definirBusca(self, termo: str) -> None:
        if self._definir("busca", termo or ""):
            self._filtrar()

    @Slot(int)
    def definirFiltroNivel(self, nivel: int) -> None:
        if self._definir("filtroNivel", int(nivel)):
            self._filtrar()

    @Slot(str)
    def definirFiltroStatus(self, status: str) -> None:
        if status in ("todos", "ativos", "inativos") and self._definir("filtroStatus", status):
            self._filtrar()

    @Slot()
    def limparFiltros(self) -> None:
        self._definir("busca", "")
        self._definir("filtroNivel", 0)
        self._definir("filtroStatus", "todos")
        self._filtrar()

    # ------------------------------------------------------------------ ações
    def _obter(self, uid: int):
        """Relê do banco para não agir sobre dado velho."""
        try:
            u = self.app.banco.obter_usuario(int(uid))
        except Exception as e:  # noqa: BLE001
            self.app.notificar("erro", f"Falha ao ler o usuário: {e}")
            return None
        if u is None:
            self.app.notificar("erro", "O usuário selecionado não existe mais.")
            self.recarregar()
        return u

    def _apos(self, texto: str) -> None:
        self.recarregar()
        self.app.notificar("ok", texto)
        self.app.banco_alterado(origem=self)

    @Slot(int, int, result=bool)
    def alterarNivel(self, uid: int, nivel: int) -> bool:
        u = self._obter(uid)
        if u is None or int(nivel) not in config.NIVEIS:
            return False
        if int(nivel) == u.nivel:
            self.app.notificar("info", f"{u.nome} já está no nível {nivel}.")
            return False
        try:
            self.app.banco.alterar_nivel(u.id, int(nivel))
        except Exception as e:  # noqa: BLE001
            self.app.notificar("erro", f"Não foi possível alterar o nível: {e}")
            return False
        self._apos(f"{u.nome}: nível alterado para {nivel} ({config.NIVEIS[int(nivel)]}).")
        return True

    @Slot(int, result=bool)
    def alternarAtivo(self, uid: int) -> bool:
        u = self._obter(uid)
        if u is None or self._em_cadastro(u):
            return False
        try:
            self.app.banco.definir_ativo(u.id, not u.ativo)
        except Exception as e:  # noqa: BLE001
            self.app.notificar("erro", f"Não foi possível alterar o status: {e}")
            return False
        self._apos(f"{u.nome} {'reativado' if not u.ativo else 'desativado'}.")
        return True

    def _em_cadastro(self, u) -> bool:
        sessao = getattr(self.app.cadastro, "sessao", None)
        if sessao is not None and not sessao.encerrada and sessao.usuario.id == u.id:
            self.app.notificar("aviso", f"{u.nome} está com um cadastro em andamento. Conclua ou cancele na tela de cadastro.")
            return True
        return False

    @Slot(int, result=bool)
    def remover(self, uid: int) -> bool:
        """Remove o usuário e as amostras. A confirmação é feita antes, no QML."""
        u = self._obter(uid)
        if u is None or self._em_cadastro(u):
            return False
        try:
            self.app.banco.remover_usuario(u.id)
        except Exception as e:  # noqa: BLE001
            self.app.notificar("erro", f"Não foi possível remover: {e}")
            return False
        self._apos(f"{u.nome} removido do banco.")
        return True

    @Slot(int, result="QVariantList")
    def fotos(self, uid: int) -> list:
        try:
            caminhos = self.app.banco.fotos_do_usuario(int(uid))
        except Exception as e:  # noqa: BLE001
            self.app.notificar("erro", f"Não foi possível listar as fotos: {e}")
            return []
        saida = []
        for c in caminhos:
            p = Path(c)
            if not p.is_absolute():
                p = config.BASE_DIR / p
            saida.append({"url": QUrl.fromLocalFile(str(p)).toString(), "existe": p.exists(), "nome": p.name})
        return saida
