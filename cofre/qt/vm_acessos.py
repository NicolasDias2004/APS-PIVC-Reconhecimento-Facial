"""ViewModel do log de auditoria: filtros (pessoa, resultado, nível, período), indicadores,
resumos por pessoa e por dia, detalhe com evidência e exportação CSV/HTML em segundo plano.
Tudo aqui é leitura: o log de acessos nunca é alterado pela interface."""

from __future__ import annotations

import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from .. import config, relatorios
from ..banco import Banco
from . import tema
from .base import ViewModel, objeto, prop
from .modelos import ModeloLista

PERIODOS = ("tudo", "hoje", "7d", "30d")
LIMITES = (50, 200, 1000)


def _desde(periodo: str) -> str | None:
    if periodo == "hoje":
        return date.today().isoformat()
    if periodo == "7d":
        return (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    if periodo == "30d":
        return (datetime.now() - timedelta(days=30)).isoformat(timespec="seconds")
    return None


def _data_hora(iso: str) -> tuple[str, str]:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M:%S")
    except (TypeError, ValueError):
        return iso or "–", ""


def _abrir(caminho: Path) -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho)))


class AcessosVM(ViewModel):
    totalMudou = Signal()
    concedidosMudou = Signal()
    negadosMudou = Signal()
    taxaMudou = Signal()
    usuariosMudou = Signal()
    amostrasMudou = Signal()
    buscaMudou = Signal()
    filtroResultadoMudou = Signal()
    filtroNivelMudou = Signal()
    periodoMudou = Signal()
    limiteMudou = Signal()
    listadosMudou = Signal()
    exportandoMudou = Signal()
    ultimoExportadoMudou = Signal()
    negacoesMudou = Signal()
    diasMudou = Signal()

    total = prop(int, "total", totalMudou)
    concedidos = prop(int, "concedidos", concedidosMudou)
    negados = prop(int, "negados", negadosMudou)
    taxa = prop(float, "taxa", taxaMudou)                    # -1 sem tentativas
    usuarios = prop(int, "usuarios", usuariosMudou)
    amostras = prop(int, "amostras", amostrasMudou)
    busca = prop(str, "busca", buscaMudou)
    filtroResultado = prop(str, "filtroResultado", filtroResultadoMudou)   # "" = todos
    filtroNivel = prop(int, "filtroNivel", filtroNivelMudou)              # 0 = todos
    periodo = prop(str, "periodo", periodoMudou)
    limite = prop(int, "limite", limiteMudou)
    listados = prop(int, "listados", listadosMudou)
    exportando = prop(bool, "exportando", exportandoMudou)
    ultimoExportado = prop(str, "ultimoExportado", ultimoExportadoMudou)
    negacoes = prop("QVariantList", "negacoes", negacoesMudou)
    dias = prop("QVariantList", "dias", diasMudou)
    modelo = objeto("lista")
    modeloPessoas = objeto("pessoas")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(total=0, concedidos=0, negados=0, taxa=-1.0, usuarios=0, amostras=0, busca="",
                      filtroResultado="", filtroNivel=0, periodo="tudo", limite=200, listados=0,
                      exportando=False, ultimoExportado="", negacoes=[], dias=[])
        self.lista = ModeloLista(["id", "data", "hora", "nome", "nivelUsuario", "nivelExigido", "area",
                                  "similaridade", "resultado", "titulo", "concedido", "mensagem", "temEvidencia"], self)
        self.pessoas = ModeloLista(["id", "nome", "concedidos", "negados", "total"], self)
        self._acessos: dict[int, object] = {}
        self._carregado = False
        self._busca_timer = QTimer(self)
        self._busca_timer.setSingleShot(True)
        self._busca_timer.setInterval(250)
        self._busca_timer.timeout.connect(self.recarregar)

    @Slot(result="QVariantList")
    def opcoesResultado(self) -> list:
        return [{"chave": "", "titulo": "Todos os resultados"}] + [
            {"chave": k, "titulo": v} for k, v in tema.TITULO_RESULTADO.items()]

    def ativar(self) -> None:
        self.recarregar()

    def ao_banco_alterado(self) -> None:
        if self._carregado:
            self.recarregar()

    # ------------------------------------------------------------------ dados
    @Slot()
    def recarregar(self) -> None:
        try:
            est = self.app.banco.estatisticas()
            acessos = self.app.banco.filtrar_acessos(
                limite=self._v["limite"], resultado=self._v["filtroResultado"] or None,
                nivel_exigido=self._v["filtroNivel"] or None, desde=_desde(self._v["periodo"]),
                termo=self._v["busca"].strip() or None)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.app.notificar("erro", f"Não foi possível ler o banco: {e}")
            return
        self._carregado = True
        por = est["por_resultado"]
        total = int(est["total"])
        conc = int(por.get("CONCEDIDO", 0))
        self._definir("total", total)
        self._definir("concedidos", conc)
        self._definir("negados", total - conc)
        self._definir("taxa", round(conc / total, 4) if total else -1.0)
        self._definir("usuarios", int(est["usuarios"]))
        self._definir("amostras", int(est["amostras"]))
        self._definir("negacoes", [{"chave": k, "titulo": tema.ROTULO_CURTO_RESULTADO[k], "n": int(por.get(k, 0))}
                                   for k in ("NEGADO_DESCONHECIDO", "NEGADO_NIVEL", "NEGADO_LIVENESS",
                                             "NEGADO_MULTIPLOS", "BLOQUEADO")])
        dias = list(reversed(est["por_dia"][:14]))
        maior = max((d["total"] for d in dias), default=0) or 1
        self._definir("dias", [{"dia": d["dia"][8:10] + "/" + d["dia"][5:7], "total": int(d["total"]),
                                "concedidos": int(d["concedidos"] or 0), "fracao": d["total"] / maior} for d in dias])
        self.pessoas.definir([{"id": i, "nome": p["nome"], "concedidos": int(p["concedidos"] or 0),
                               "negados": int(p["negados"] or 0),
                               "total": int(p["concedidos"] or 0) + int(p["negados"] or 0)}
                              for i, p in enumerate(est["por_usuario"])])
        self._acessos = {a.id: a for a in acessos}
        itens = []
        for a in acessos:
            data, hora = _data_hora(a.data_hora)
            itens.append({
                "id": a.id, "data": data, "hora": hora, "nome": a.nome_detectado or "Não identificado",
                "nivelUsuario": int(a.nivel_usuario or 0), "nivelExigido": int(a.nivel_exigido), "area": a.area,
                "similaridade": f"{a.similaridade:.2f}" if a.similaridade is not None else "–",
                "resultado": a.resultado, "titulo": tema.ROTULO_CURTO_RESULTADO.get(a.resultado, a.resultado),
                "concedido": a.resultado == "CONCEDIDO", "mensagem": a.mensagem or "",
                "temEvidencia": bool(a.evidencia),
            })
        self.lista.definir(itens)
        self._definir("listados", len(itens))

    # ------------------------------------------------------------------ filtros
    @Slot(str)
    def definirBusca(self, termo: str) -> None:
        if self._definir("busca", termo or ""):
            self._busca_timer.start()            # debounce: recarrega 250 ms após a última tecla

    @Slot(str)
    def definirFiltroResultado(self, chave: str) -> None:
        if (not chave or chave in tema.TITULO_RESULTADO) and self._definir("filtroResultado", chave or ""):
            self.recarregar()

    @Slot(int)
    def definirFiltroNivel(self, nivel: int) -> None:
        if (nivel == 0 or nivel in config.NIVEIS) and self._definir("filtroNivel", int(nivel)):
            self.recarregar()

    @Slot(str)
    def definirPeriodo(self, periodo: str) -> None:
        if periodo in PERIODOS and self._definir("periodo", periodo):
            self.recarregar()

    @Slot(int)
    def definirLimite(self, limite: int) -> None:
        if limite in LIMITES and self._definir("limite", int(limite)):
            self.recarregar()

    @Slot()
    def limparFiltros(self) -> None:
        self._definir("busca", "")
        self._definir("filtroResultado", "")
        self._definir("filtroNivel", 0)
        self._definir("periodo", "tudo")
        self.recarregar()

    @Slot(str)
    def filtrarPessoa(self, nome: str) -> None:
        if nome == "DESCONHECIDO":         # rostos sem cadastro: filtra pelo resultado
            self._definir("busca", "")
            self._definir("filtroResultado", "NEGADO_DESCONHECIDO")
        else:
            self._definir("busca", nome)
        self.recarregar()

    # ------------------------------------------------------------------ detalhe
    @Slot(int, result="QVariantMap")
    def detalhe(self, ident: int) -> dict:
        a = self._acessos.get(int(ident))
        if a is None:
            return {}
        data, hora = _data_hora(a.data_hora)
        evid = None
        if a.evidencia:
            evid = Path(a.evidencia)
            if not evid.is_absolute():
                evid = config.BASE_DIR / evid
        return {
            "id": a.id, "data": data, "hora": hora, "nome": a.nome_detectado or "Não identificado",
            "resultado": a.resultado, "titulo": tema.TITULO_RESULTADO.get(a.resultado, a.resultado),
            "concedido": a.resultado == "CONCEDIDO",
            "nivelUsuario": int(a.nivel_usuario or 0),
            "nivelUsuarioDescricao": config.NIVEIS.get(a.nivel_usuario, "") if a.nivel_usuario else "",
            "nivelExigido": int(a.nivel_exigido), "area": a.area,
            "similaridade": f"{a.similaridade:.3f}" if a.similaridade is not None else "–",
            "limiar": f"{config.LIMIAR_COSSENO:.3f}",
            "mensagem": a.mensagem or "",
            "evidencia": str(evid) if evid else "",
            "evidenciaUrl": QUrl.fromLocalFile(str(evid)).toString() if evid and evid.exists() else "",
            "evidenciaExiste": bool(evid and evid.exists()),
        }

    # ------------------------------------------------------------------ exportação e arquivos
    @Slot(str)
    def exportar(self, formato: str) -> None:
        formato = (formato or "").lower()
        if self._v["exportando"] or formato not in ("csv", "html"):
            return
        self._definir("exportando", True)
        caminho_db = self.app.banco.caminho
        em_memoria = str(caminho_db) == ":memory:"
        banco_principal = self.app.banco

        def trabalho():
            banco = banco_principal if em_memoria else Banco(caminho_db)   # conexão própria, só leitura
            try:
                fn = relatorios.exportar_csv if formato == "csv" else relatorios.exportar_html
                return Path(fn(banco))
            finally:
                if banco is not banco_principal:
                    banco.fechar()

        def terminou(caminho, erro: str) -> None:
            self._definir("exportando", False)
            if erro:
                self.app.notificar("erro", f"Falha ao exportar: {erro}")
                return
            self._definir("ultimoExportado", str(caminho))
            self.app.notificar("ok", f"Relatório {formato.upper()} salvo em {caminho.name}")

        if em_memoria:
            try:
                terminou(trabalho(), "")
            except Exception as e:  # noqa: BLE001
                terminou(None, str(e))
        else:
            self.app.tarefas.executar(trabalho, terminou)

    @Slot()
    def abrirExportado(self) -> None:
        caminho = Path(self._v["ultimoExportado"]) if self._v["ultimoExportado"] else None
        if caminho is None or not caminho.exists():
            self.app.notificar("erro", "O arquivo exportado não foi encontrado.")
            return
        if not _abrir(caminho.resolve()):
            self.app.notificar("erro", f"Não foi possível abrir {caminho.name}.")

    @Slot()
    def abrirPastaEvidencias(self) -> None:
        pasta = Path(config.EVIDENCIAS_DIR)
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.app.notificar("erro", f"Não foi possível abrir a pasta de evidências: {e}")
            return
        if not _abrir(pasta.resolve()):
            self.app.notificar("erro", "Não foi possível abrir a pasta de evidências.")
