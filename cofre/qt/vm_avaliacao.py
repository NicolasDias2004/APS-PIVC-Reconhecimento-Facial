"""ViewModel de "Avaliação e demo": demonstração das 5 fases em uma imagem, autenticação por
imagem (registrada no log, como na versão anterior) e avaliação quantitativa TAR/FAR/FRR/EER.

As fases 2 a 4 e a avaliação de pasta rodam em segundo plano; a fase 5 da demonstração
(comparação com a galeria) usa a conexão principal do banco, na thread da interface."""

from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Property, QUrl, Signal, Slot

from .. import config, hud
from ..autenticacao import autenticar_imagem
from ..avaliacao import ResultadoAvaliacao, avaliar_pasta
from ..banco import Banco
from ..fase1_aquisicao import carregar_imagem
from ..fase5_reconhecimento import Reconhecedor, decidir_acesso
from . import tema
from .base import ViewModel, objeto, prop
from .imagens import bgr_para_qimage
from .modelos import ModeloLista
from .video import FonteVideo

PASTA_FOTOS_TESTE = config.BASE_DIR / "tests" / "fixtures" / "pessoas"


def _pct(v: float) -> str:
    return "–" if v != v else f"{v:.1%}".replace(".", ",")


def _local(url: str) -> Path:
    u = QUrl(url)
    return Path(u.toLocalFile() if u.isLocalFile() else url)


class AvaliacaoVM(ViewModel):
    # demo
    demoArquivoMudou = Signal()
    demoProcessandoMudou = Signal()
    demoFasesMudou = Signal()
    demoNivelMudou = Signal()
    demoResultadoMudou = Signal()
    demoEtapasMudou = Signal()
    # autenticação por imagem
    authArquivoMudou = Signal()
    authProcessandoMudou = Signal()
    authNivelMudou = Signal()
    authResultadoMudou = Signal()
    # avaliação
    avalPastaMudou = Signal()
    avalProcessandoMudou = Signal()
    avalResultadoMudou = Signal()

    demoArquivo = prop(str, "demoArquivo", demoArquivoMudou)
    demoProcessando = prop(bool, "demoProcessando", demoProcessandoMudou)
    demoFases = prop("QVariantList", "demoFases", demoFasesMudou)
    demoNivel = prop(int, "demoNivel", demoNivelMudou)
    demoResultado = prop("QVariantMap", "demoResultado", demoResultadoMudou)
    authArquivo = prop(str, "authArquivo", authArquivoMudou)
    authProcessando = prop(bool, "authProcessando", authProcessandoMudou)
    authNivel = prop(int, "authNivel", authNivelMudou)
    authResultado = prop("QVariantMap", "authResultado", authResultadoMudou)
    avalPasta = prop(str, "avalPasta", avalPastaMudou)
    avalProcessando = prop(bool, "avalProcessando", avalProcessandoMudou)
    avalResultado = prop("QVariantMap", "avalResultado", avalResultadoMudou)
    modeloVarredura = objeto("varredura")
    fonteDemo = objeto("demoImagem")
    fonteAuth = objeto("authImagem")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(demoArquivo="", demoProcessando=False, demoFases=[], demoNivel=3, demoResultado={},
                      authArquivo="", authProcessando=False, authNivel=3, authResultado={},
                      avalPasta="", avalProcessando=False, avalResultado={})
        self.demoImagem = FonteVideo("demo", self)
        self._demo_etapas: list[FonteVideo] = []
        self.authImagem = FonteVideo("auth", self)
        self.varredura = ModeloLista(["id", "limiar", "tar", "frr", "far", "atual"], self)
        self._demo_res = None
        self._demo_caminho: Path | None = None
        self._painel: np.ndarray | None = None
        self._linhas_demo: list[str] = []

    def _get_demo_etapas(self) -> list:
        return list(self._demo_etapas)

    demoEtapas = Property("QVariantList", _get_demo_etapas, notify=demoEtapasMudou)

    @Slot(result=str)
    def pastaFotosTeste(self) -> str:
        return QUrl.fromLocalFile(str(PASTA_FOTOS_TESTE)).toString()

    def _pipeline_ou_aviso(self) -> bool:
        if self.app.pipeline is None:
            self.app.notificar("aviso", "Os modelos ainda estão carregando. Tente novamente em instantes.")
            return False
        return True

    # ------------------------------------------------------------------ demo das 5 fases
    @Slot(str)
    def demonstrar(self, url: str) -> None:
        if self._v["demoProcessando"] or not self._pipeline_ou_aviso():
            return
        caminho = _local(url)
        self._demo_caminho = caminho
        self._definir("demoArquivo", caminho.name)
        self._definir("demoProcessando", True)
        pipeline = self.app.pipeline

        def trabalho():
            frame = carregar_imagem(caminho)
            res = pipeline.processar(frame)
            etapas = [(k, bgr_para_qimage(v if v.ndim == 3 else cv2.cvtColor(v, cv2.COLOR_GRAY2BGR)))
                      for k, v in res.etapas_didaticas().items()]
            painel = hud.mosaico(res.etapas_didaticas(), lado=200, colunas=4)
            return res, etapas, painel

        def terminou(r, erro: str) -> None:
            self._definir("demoProcessando", False)
            if erro:
                self._definir("demoResultado", {"tipo": "erro", "titulo": "Falha na demonstração", "mensagem": erro})
                self.app.notificar("erro", f"Falha na demonstração: {erro}")
                return
            res, etapas, painel = r
            self._demo_res, self._painel = res, painel
            fontes = []
            for chave, qimg in etapas:
                fase, nome = tema.rotulo_etapa(chave)
                f = FonteVideo(f"{fase} · {nome}" if fase else nome, self)
                f.definir(qimg, [])
                fontes.append(f)
            self._demo_etapas = fontes
            self.demoEtapasMudou.emit()
            p = res.principal
            caixas = []
            if p is not None:
                r_ = p.rosto
                caixas.append({"x": r_.x, "y": r_.y, "w": r_.w, "h": r_.h, "cor": tema.ACENTO, "rotulo": "",
                               "pontos": [r_.olho_dir, r_.olho_esq, r_.nariz, r_.boca_dir, r_.boca_esq]})
            self.demoImagem.definir(bgr_para_qimage(res.pre.original), caixas)
            self._montar_demo()

        self.app.tarefas.executar(trabalho, terminou)

    @Slot(int)
    def definirNivelDemo(self, nivel: int) -> None:
        if nivel in config.NIVEIS and self._definir("demoNivel", int(nivel)) and self._demo_res is not None:
            self._montar_demo()

    def _montar_demo(self) -> None:
        """Texto por fase. A fase 5 consulta a galeria (conexão principal) e NÃO grava no log."""
        res, nivel = self._demo_res, self._v["demoNivel"]
        frame = res.pre.original
        nome = self._demo_caminho.name if self._demo_caminho else "–"
        fases = [
            {"fase": 1, "titulo": "Aquisição", "linhas": [["Arquivo", nome],
                                                         ["Tamanho", f"{frame.shape[1]}×{frame.shape[0]} px"]]},
            {"fase": 2, "titulo": "Pré-processamento", "linhas": [
                ["Quadro reduzido", f"{res.pre.reduzida.shape[1]}×{res.pre.reduzida.shape[0]} px"],
                ["Escala", f"{res.pre.escala:.2f}"], ["Etapas", "cinza, suavização, CLAHE"]]},
            {"fase": 3, "titulo": "Segmentação", "linhas": [["Rostos detectados", str(len(res.rostos))]]},
        ]
        p = res.principal
        linhas_txt = [f"FASE 1  Aquisicao: {nome} {frame.shape[1]}x{frame.shape[0]}",
                      f"FASE 2  Pre-processamento: escala {res.pre.escala:.2f}",
                      f"FASE 3  Segmentacao: {len(res.rostos)} rosto(s)"]
        if p is None:
            fases += [{"fase": 4, "titulo": "Representação", "linhas": [["Embedding", "sem rosto, fase não executada"]]},
                      {"fase": 5, "titulo": "Reconhecimento", "linhas": [["Decisão", "sem rosto, fase não executada"]]}]
            resultado = {"tipo": "aviso", "titulo": "Nenhum rosto detectado",
                         "mensagem": "Tente uma foto frontal e bem iluminada."}
            linhas_txt.append("Nenhum rosto detectado")
        else:
            x, y, w, h = p.rosto.caixa
            norma = float(np.linalg.norm(p.embedding))
            reconhecedor = Reconhecedor(self.app.banco)
            ident = reconhecedor.identificar(p.embedding)
            d = decidir_acesso(ident, nivel)
            fases[2]["linhas"] += [["Caixa (x, y, w, h)", f"{x}, {y}, {w}, {h}"],
                                   ["Confiança", f"{p.rosto.confianca:.3f}"],
                                   ["Yaw (nariz/olhos)", f"{p.rosto.yaw():+.3f}"],
                                   ["Nitidez", f"{p.qualidade.nitidez:.1f} (mín. {config.MIN_NITIDEZ:.0f})"],
                                   ["Brilho", f"{p.qualidade.brilho:.1f} ({config.MIN_BRILHO:.0f} a {config.MAX_BRILHO:.0f})"],
                                   ["Qualidade", "aprovada" if p.qualidade.aprovada else f"reprovada ({p.qualidade.motivo})"]]
            fases.append({"fase": 4, "titulo": "Representação", "linhas": [
                ["Embedding", f"{p.embedding.shape[0]} dimensões"], ["Norma", f"{norma:.3f}"],
                ["Mín. / máx.", f"{float(p.embedding.min()):+.3f} / {float(p.embedding.max()):+.3f}"]]})
            fases.append({"fase": 5, "titulo": "Reconhecimento", "linhas": [
                ["Área", config.AREAS[nivel]], ["Galeria", f"{len(reconhecedor.usuarios)} usuário(s) ativo(s)"],
                ["Identificado", ident.usuario.nome if ident.reconhecido else "Não reconhecido"],
                ["Similaridade", f"{ident.similaridade:.3f} (limiar {config.LIMIAR_COSSENO:.3f})"],
                ["2º colocado", f"{ident.segunda_similaridade:.3f}"], ["Decisão", d.resultado.value]]})
            resultado = {"tipo": "ok" if d.concedido else "erro", "concedido": d.concedido,
                         "titulo": tema.TITULO_RESULTADO[d.resultado.value], "mensagem": d.mensagem}
            linhas_txt += [f"FASE 4  Embedding {p.embedding.shape[0]}-d, norma {norma:.3f}",
                           f"FASE 5  {ident.rotulo}  similaridade {ident.similaridade:.3f}  "
                           f"limiar {config.LIMIAR_COSSENO:.3f}  decisao {d.resultado.value}"]
        self._linhas_demo = linhas_txt
        self._definir("demoFases", fases)
        self._definir("demoResultado", resultado)

    @Slot(result=str)
    def salvarPainel(self) -> str:
        """Grava o mosaico das fases (com o resumo no rodapé) em config.RELATORIOS_DIR."""
        if self._painel is None:
            self.app.notificar("aviso", "Nada para salvar: rode a demonstração em uma imagem primeiro.")
            return ""
        try:
            linhas = [l for l in self._linhas_demo if l.strip()]
            painel = self._painel
            base = np.full((painel.shape[0] + 20 * len(linhas) + 16, painel.shape[1], 3), 20, np.uint8)
            base[:painel.shape[0]] = painel
            y = painel.shape[0] + 20
            for l in linhas:
                hud.texto(base, l, (10, y), 0.45, hud.BRANCO, 1)
                y += 20
            pasta = Path(config.RELATORIOS_DIR)
            pasta.mkdir(parents=True, exist_ok=True)
            stem = self._demo_caminho.stem if self._demo_caminho else "imagem"
            destino = pasta / f"demo_{stem}_{datetime.now():%Y%m%d_%H%M%S}.png"
            if not cv2.imwrite(str(destino), base):
                raise OSError("o OpenCV não conseguiu gravar o arquivo")
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.app.notificar("erro", f"Não foi possível salvar o painel: {e}")
            return ""
        self.app.notificar("ok", f"Painel salvo em {destino.name}")
        return str(destino)

    # ------------------------------------------------------------------ autenticar por imagem
    @Slot(int)
    def definirNivelAuth(self, nivel: int) -> None:
        if nivel in config.NIVEIS:
            self._definir("authNivel", int(nivel))

    @Slot(str)
    def autenticar(self, url: str) -> None:
        """Autentica a imagem no nível escolhido. Como antes, a tentativa entra no log de acessos."""
        if self._v["authProcessando"] or not self._pipeline_ou_aviso():
            return
        caminho = _local(url)
        nivel = self._v["authNivel"]
        self._definir("authArquivo", caminho.name)
        self._definir("authProcessando", True)
        caminho_db, pipeline = self.app.banco.caminho, self.app.pipeline
        em_memoria = str(caminho_db) == ":memory:"
        banco_principal = self.app.banco

        def trabalho():
            frame = carregar_imagem(caminho)
            banco = banco_principal if em_memoria else Banco(caminho_db)
            try:
                decisao, res = autenticar_imagem(banco, pipeline, frame, nivel)
            finally:
                if banco is not banco_principal:
                    banco.fechar()
            return frame, decisao, res

        def terminou(r, erro: str) -> None:
            self._definir("authProcessando", False)
            if erro:
                self._definir("authResultado", {"tipo": "erro", "titulo": "Falha ao autenticar", "mensagem": erro,
                                                "concedido": False})
                return
            frame, decisao, res = r
            cor = tema.VERDE if decisao.concedido else tema.VERMELHO
            caixas = [{"x": rp.rosto.x, "y": rp.rosto.y, "w": rp.rosto.w, "h": rp.rosto.h, "cor": cor, "rotulo": "",
                       "pontos": []} for rp in res.rostos]
            self.authImagem.definir(bgr_para_qimage(frame), caixas)
            ident = decisao.identificacao
            u = ident.usuario if ident and ident.reconhecido else None
            self._definir("authResultado", {
                "tipo": "ok" if decisao.concedido else "erro", "concedido": bool(decisao.concedido),
                "resultado": decisao.resultado.value, "titulo": tema.TITULO_RESULTADO[decisao.resultado.value],
                "mensagem": decisao.mensagem, "usuario": u.nome if u else "Não reconhecido",
                "nivelUsuario": int(u.nivel) if u else 0, "nivelExigido": int(nivel),
                "similaridade": f"{ident.similaridade:.3f}" if ident is not None else "–",
                "limiar": f"{config.LIMIAR_COSSENO:.3f}", "rostos": len(res.rostos),
            })
            self.app.banco_alterado()

        if em_memoria:
            try:
                terminou(trabalho(), "")
            except Exception as e:  # noqa: BLE001
                terminou(None, str(e))
        else:
            self.app.tarefas.executar(trabalho, terminou)

    # ------------------------------------------------------------------ avaliação do reconhecedor
    @Slot(str)
    def definirPasta(self, url: str) -> None:
        self._definir("avalPasta", str(_local(url)) if url else "")

    @Slot()
    def usarFotosTeste(self) -> None:
        self._definir("avalPasta", str(PASTA_FOTOS_TESTE))

    @Slot()
    def avaliar(self) -> None:
        if self._v["avalProcessando"] or not self._pipeline_ou_aviso():
            return
        if not self._v["avalPasta"]:
            self.app.notificar("aviso", "Escolha uma pasta (ou use as fotos de teste) antes de avaliar.")
            return
        pasta = Path(self._v["avalPasta"])
        if not pasta.is_dir():
            self.app.notificar("erro", f"Pasta não encontrada: {pasta}")
            return
        if not any(p.is_dir() for p in pasta.iterdir()):
            self.app.notificar("aviso", "A pasta precisa ter uma subpasta por pessoa (pasta/pessoa/*.jpg).")
            return
        self._definir("avalProcessando", True)
        pipeline = self.app.pipeline

        def terminou(r: ResultadoAvaliacao, erro: str) -> None:
            self._definir("avalProcessando", False)
            if erro:
                self.app.notificar("erro", f"Falha na avaliação: {erro}")
                return
            self._aplicar_avaliacao(r)

        self.app.tarefas.executar(lambda: avaliar_pasta(pasta, pipeline), terminou)

    def _aplicar_avaliacao(self, r: ResultadoAvaliacao) -> None:
        n_img = sum(r.pessoas.values())
        base = {"pessoas": len(r.pessoas), "imagens": n_img, "semRosto": len(r.sem_rosto),
                "genuinos": len(r.genuinos), "impostores": len(r.impostores), "resumo": r.resumo(),
                "limiar": float(config.LIMIAR_COSSENO)}
        if not r.genuinos and not r.impostores:
            self.varredura.definir([])
            self._definir("avalResultado", {**base, "valido": False, "aviso":
                f"Nenhum par para comparar ({n_img} imagem(ns) com rosto, {len(r.sem_rosto)} sem rosto). "
                "São necessárias ao menos 2 imagens com rosto."})
            return
        t = r.taxas(config.LIMIAR_COSSENO)
        eer_l, eer_v = r.eer()
        pontos = r.varredura(11)
        perto = min(pontos, key=lambda v: abs(v["limiar"] - config.LIMIAR_COSSENO))["limiar"]
        # tipos do NumPy não atravessam para o QML: tudo vira float/bool do Python
        self.varredura.definir([{"id": i, "limiar": f"{v['limiar']:.2f}", "tar": _pct(v["TAR"]),
                                 "frr": _pct(v["FRR"]), "far": _pct(v["FAR"]),
                                 "atual": bool(v["limiar"] == perto)}
                                for i, v in enumerate(pontos)])
        curva = [{"limiar": float(v["limiar"]), "tar": None if v["TAR"] != v["TAR"] else float(v["TAR"]),
                  "far": None if v["FAR"] != v["FAR"] else float(v["FAR"])} for v in r.varredura(51)]
        aviso = ""
        if r.sem_rosto:
            nomes = ", ".join(Path(s).name for s in r.sem_rosto[:3])
            extra = f" e mais {len(r.sem_rosto) - 3}" if len(r.sem_rosto) > 3 else ""
            aviso = f"Ignoradas {len(r.sem_rosto)} imagem(ns) sem rosto: {nomes}{extra}."
        self._definir("avalResultado", {**base, "valido": True, "aviso": aviso, "tar": _pct(t["TAR"]),
                                        "far": _pct(t["FAR"]), "frr": _pct(t["FRR"]), "eer": _pct(eer_v),
                                        "eerLimiar": f"{float(eer_l):.3f}", "curva": curva})
        self.app.notificar("ok", f"Avaliação concluída: EER {_pct(eer_v)}")
