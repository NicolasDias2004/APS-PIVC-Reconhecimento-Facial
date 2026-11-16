"""
ViewModel do terminal de acesso.

Divisão de trabalho (igual à da interface customtkinter):
  - thread da câmera: `pipeline.processar` + conversão do quadro para QImage
    (e, com o painel didático ligado, as imagens de cada fase);
  - thread da interface: `TerminalAutenticacao.passo()` (máquina de estados), leitura do
    `status()` e exposição ao QML. O `passo()` grava o log de acesso no SQLite, cuja
    conexão só aceita a thread que a criou.

A autorização é sempre a do backend: a interface só mostra "autorizado" quando o
`TerminalAutenticacao` está em RESULTADO com uma decisão `concedido`. Qualquer falha
no processamento deixa o painel em estado neutro, nunca em "autorizado".
"""

from __future__ import annotations

import time
import traceback

import cv2
import numpy as np
from PySide6.QtCore import Property, QTimer, Signal, Slot

from .. import config
from ..autenticacao import Estado, TerminalAutenticacao
from ..liveness import EtapaLiveness
from . import tema
from .base import ViewModel, objeto, prop
from .imagens import bgr_para_qimage
from .modelos import ModeloLista
from .video import FonteVideo

INTERVALO_CHECAGEM_BANCO_MS = 1000
INTERVALO_DIDATICO_SEG = 0.12          # painel didático a ~8 quadros/s (economiza CPU)
LADO_ETAPA = 240
PASSO_LIVENESS = {EtapaLiveness.VIRAR_ESQUERDA: 0, EtapaLiveness.VIRAR_DIREITA: 1, EtapaLiveness.VOLTAR_CENTRO: 2,
                  EtapaLiveness.APROVADO: 3}


def _reduzir(img, lado: int = LADO_ETAPA):
    h, w = img.shape[:2]
    esc = lado / max(h, w)
    if esc >= 1:
        return img
    return cv2.resize(img, (max(1, int(w * esc)), max(1, int(h * esc))), interpolation=cv2.INTER_AREA)


class TerminalVM(ViewModel):
    estadoMudou = Signal()
    nivelMudou = Signal()
    areaMudou = Signal()
    livenessMudou = Signal()
    didaticoMudou = Signal()
    similaridadeMudou = Signal()
    progressoMudou = Signal()
    livenessInstrucaoMudou = Signal()
    livenessRestanteMudou = Signal()
    livenessTotalMudou = Signal()
    livenessPassoMudou = Signal()
    bloqueadoRestanteMudou = Signal()
    bloqueioTotalMudou = Signal()
    resultadoTipoMudou = Signal()
    resultadoConcedidoMudou = Signal()
    resultadoTituloMudou = Signal()
    resultadoNomeMudou = Signal()
    resultadoMensagemMudou = Signal()
    resultadoSimilaridadeMudou = Signal()
    resultadoNivelMudou = Signal()
    galeriaMudou = Signal()
    usuariosAtivosMudou = Signal()
    nRostosMudou = Signal()
    avisoMudou = Signal()
    orientacaoMudou = Signal()
    poseYawMudou = Signal()
    poseRollMudou = Signal()
    poseRazaoMudou = Signal()
    assinaturaMudou = Signal()
    assinaturaReferenciaMudou = Signal()
    erroMudou = Signal()
    etapasMudou = Signal()
    decisaoTomada = Signal(bool, str)        # (concedido, resultado) para animações / feedback

    estado = prop(str, "estado", estadoMudou)
    nivel = prop(int, "nivel", nivelMudou)
    area = prop(str, "area", areaMudou)
    liveness = prop(bool, "liveness", livenessMudou)
    didatico = prop(bool, "didatico", didaticoMudou)
    similaridade = prop(float, "similaridade", similaridadeMudou)       # -1 = sem rosto
    progresso = prop(float, "progresso", progressoMudou)
    livenessInstrucao = prop(str, "livenessInstrucao", livenessInstrucaoMudou)
    livenessRestante = prop(float, "livenessRestante", livenessRestanteMudou)
    livenessTotal = prop(float, "livenessTotal", livenessTotalMudou)
    livenessPasso = prop(int, "livenessPasso", livenessPassoMudou)
    bloqueadoRestante = prop(float, "bloqueadoRestante", bloqueadoRestanteMudou)
    bloqueioTotal = prop(float, "bloqueioTotal", bloqueioTotalMudou)
    resultadoTipo = prop(str, "resultadoTipo", resultadoTipoMudou)
    resultadoConcedido = prop(bool, "resultadoConcedido", resultadoConcedidoMudou)
    resultadoTitulo = prop(str, "resultadoTitulo", resultadoTituloMudou)
    resultadoNome = prop(str, "resultadoNome", resultadoNomeMudou)
    resultadoMensagem = prop(str, "resultadoMensagem", resultadoMensagemMudou)
    resultadoSimilaridade = prop(float, "resultadoSimilaridade", resultadoSimilaridadeMudou)
    resultadoNivel = prop(int, "resultadoNivel", resultadoNivelMudou)
    galeria = prop(int, "galeria", galeriaMudou)
    usuariosAtivos = prop(int, "usuariosAtivos", usuariosAtivosMudou)
    nRostos = prop(int, "nRostos", nRostosMudou)
    aviso = prop(str, "aviso", avisoMudou)
    orientacao = prop(str, "orientacao", orientacaoMudou)     # "" ou instrução de pose/qualidade do backend
    poseYaw = prop(float, "poseYaw", poseYawMudou)            # medidas dos 5 pontos (-99 = sem rosto)
    poseRoll = prop(float, "poseRoll", poseRollMudou)
    poseRazao = prop(float, "poseRazao", poseRazaoMudou)
    assinatura = prop("QVariantList", "assinatura", assinaturaMudou)            # embedding ao vivo (128)
    assinaturaReferencia = prop("QVariantList", "assinaturaReferencia", assinaturaReferenciaMudou)
    erro = prop(str, "erro", erroMudou)
    ultimosAcessos = objeto("acessos")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        nivel = 3
        self._iniciar(
            estado=Estado.AGUARDANDO.value, nivel=nivel, area=config.AREAS[nivel],
            liveness=bool(config.LIVENESS_ATIVO), didatico=False, similaridade=-1.0, progresso=0.0,
            livenessInstrucao="", livenessRestante=0.0, livenessTotal=float(config.LIVENESS_TIMEOUT_SEG),
            livenessPasso=0, bloqueadoRestante=0.0, bloqueioTotal=float(config.BLOQUEIO_SEG),
            resultadoTipo="", resultadoConcedido=False, resultadoTitulo="", resultadoNome="",
            resultadoMensagem="", resultadoSimilaridade=-1.0, resultadoNivel=0,
            galeria=0, usuariosAtivos=0, nRostos=0, aviso="", erro="", orientacao="",
            poseYaw=-99.0, poseRoll=-99.0, poseRazao=-99.0, assinatura=[], assinaturaReferencia=[],
        )
        self.terminal: TerminalAutenticacao | None = None
        self.video = FonteVideo("camera", self)
        self._etapas: list[FonteVideo] = []
        self._etapa_por_chave: dict[str, FonteVideo] = {}
        self._didatico_thread = False          # lido pela thread da câmera
        self._ultimo_didatico = 0.0            # idem
        self._ultima_assinatura = 0.0
        self.acessos = ModeloLista(["id", "hora", "nome", "resultado", "titulo", "concedido", "nivelExigido",
                                    "similaridade"], self)
        self._ativo = False
        self._seq_visto = -1
        self._versao_banco: int | None = None
        self._timer_banco = QTimer(self)
        self._timer_banco.setInterval(INTERVALO_CHECAGEM_BANCO_MS)
        self._timer_banco.timeout.connect(self._checar_banco)
        aplicacao.camera.quadroDisponivel.connect(self._quadro)
        aplicacao.camera.erroProcessamento.connect(self._erro_processamento)

    # ------------------------------------------------------------------ propriedades extras
    def _get_etapas(self) -> list:
        return list(self._etapas)

    etapas = Property("QVariantList", _get_etapas, notify=etapasMudou)

    def _get_limiar(self) -> float:
        return float(config.LIMIAR_COSSENO)

    limiar = Property(float, _get_limiar, notify=similaridadeMudou)

    fonteVideo = objeto("video")

    # ------------------------------------------------------------------ ciclo de vida
    def ativar(self) -> None:
        self._ativo = True
        self._seq_visto = -1
        if self.terminal is not None:
            self.terminal.definir_nivel(self._v["nivel"])     # volta a AGUARDANDO ao reabrir a tela
        self._definir("erro", "")
        self.atualizar_acessos()
        self.verificar_usuarios()
        self._timer_banco.start()
        self._abrir_camera()

    def pausar(self) -> None:
        """Área liberada aberta: desliga a câmera sem perder o terminal (e o contador de falhas).
        O veredito fica na tela, por baixo da área, até a sessão encerrar."""
        self.app.camera.parar()
        self.video.limpar()
        self._atualizar_pose_e_assinatura(None)

    def retomar(self) -> None:
        if self._ativo and self.terminal is not None:
            self.terminal.encerrar_resultado()    # senão o RESULTADO ainda em exibição reabriria a sessão
            self._limpar_status()                  # nada de "autorizado" antigo enquanto a câmera reabre
            self._abrir_camera()

    def desativar(self) -> None:
        self._ativo = False
        self._timer_banco.stop()
        self.app.camera.parar()
        self.video.limpar()
        for e in self._etapas:
            e.limpar()
        self._limpar_status()

    def ao_pipeline_pronto(self) -> None:
        if self._ativo:
            self._abrir_camera()

    def ao_banco_alterado(self) -> None:
        self.recarregarGaleria(silencioso=True)

    def _abrir_camera(self) -> None:
        if not self._ativo or self.app.pipeline is None:
            return
        if self.terminal is None:
            self.terminal = TerminalAutenticacao(self.app.banco, self.app.pipeline, nivel_exigido=self._v["nivel"],
                                                 liveness=self._v["liveness"], didatico=self._v["didatico"])
            self._versao_banco = self._ler_versao()
            self.verificar_usuarios()
        self._seq_visto = -1
        self.app.camera.iniciar(self._processar)

    # ------------------------------------------------------------------ thread da câmera
    def _processar(self, frame):
        """Roda NA THREAD DA CÂMERA: só a parte cara. Nada de banco nem de objetos do QML aqui."""
        res = self.app.pipeline.processar(frame)
        qimg = bgr_para_qimage(frame)
        etapas = None
        agora = time.monotonic()
        if self._didatico_thread and agora - self._ultimo_didatico >= INTERVALO_DIDATICO_SEG:
            self._ultimo_didatico = agora
            etapas = [(chave, bgr_para_qimage(_reduzir(img))) for chave, img in res.etapas_didaticas().items()]
        return res, qimg, etapas

    # ------------------------------------------------------------------ thread da interface
    @Slot()
    def _quadro(self) -> None:
        if not self._ativo or self.terminal is None:
            return
        pacote = self.app.camera.ultimo()
        if pacote is None or pacote.seq == self._seq_visto or pacote.saida is None:
            return
        self._seq_visto = pacote.seq
        res, qimg, etapas = pacote.saida
        term = self.terminal
        try:
            term.passo(pacote.frame, res.principal, len(res.rostos))
            st = term.status()
            ident = term.identificacao_atual(res.principal)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._definir("erro", f"Erro no processamento: {e}")
            self._limpar_status()                 # nunca deixa um "autorizado" antigo na tela
            self.video.definir(qimg, [])
            return
        anterior = self._v["estado"]
        self.video.definir(qimg, self._caixas(res, st, ident))
        self._atualizar_pose_e_assinatura(res.principal)
        if etapas is not None:
            self._atualizar_etapas(etapas)
        self.app.camera.atualizar_fps(pacote.fps)
        self._aplicar_status(st, ident, len(res.rostos))
        if self._v["erro"]:
            self._definir("erro", "")
        estado = st["estado"]
        if estado == Estado.RESULTADO.value and anterior != Estado.RESULTADO.value:
            self.atualizar_acessos()             # a decisão (e um eventual bloqueio) acabou de ser gravada
            d = st.get("decisao") or {}
            self.decisaoTomada.emit(bool(d.get("concedido")), str(d.get("resultado", "")))
            if d.get("concedido"):
                # a área liberada abre só a partir da decisão do backend, já gravada no log
                self.app.sessao_vm.abrir(term.decisao_atual, term.nivel_exigido)

    @Slot(str)
    def _erro_processamento(self, texto: str) -> None:
        if self._ativo:
            self._definir("erro", texto)

    def _atualizar_pose_e_assinatura(self, principal) -> None:
        """Leituras só para exibição: medidas de pose dos 5 pontos e o vetor de 128 dimensões
        ao vivo ao lado da amostra da galeria mais parecida. Nada aqui influencia a decisão."""
        if principal is None:
            if self._v["poseYaw"] != -99.0:
                self._definir("poseYaw", -99.0)
                self._definir("poseRoll", -99.0)
                self._definir("poseRazao", -99.0)
            if self._v["assinatura"]:
                self._definir("assinatura", [])
                self._definir("assinaturaReferencia", [])
            return
        r = principal.rosto
        self._definir("poseYaw", round(float(r.yaw()), 2))
        self._definir("poseRoll", round(float(r.roll()), 1))
        self._definir("poseRazao", round(float(r.razao_nariz()), 2))
        agora = time.time()
        if agora - self._ultima_assinatura < 0.15:
            return
        self._ultima_assinatura = agora
        emb = np.asarray(principal.embedding, dtype=np.float32).reshape(-1)
        escala = float(np.abs(emb).max() or 1.0)
        self._definir("assinatura", [round(float(v) / escala, 3) for v in emb])
        ref = self.terminal.reconhecedor.amostra_mais_parecida(emb) if self.terminal is not None else None
        self._definir("assinaturaReferencia",
                      [] if ref is None else [round(float(v) / float(np.abs(ref).max() or 1.0), 3) for v in ref])

    def _caixas(self, res, st: dict, ident) -> list[dict]:
        """Marcações sobre o vídeo: mesma regra de cores do HUD da linha de comando."""
        estado = st["estado"]
        decisao = st.get("decisao")
        caixas = []
        for i, rp in enumerate(res.rostos):
            r = rp.rosto
            cor, rotulo = tema.ACENTO, "Analisando"
            if i == 0 and estado in (Estado.CONFIRMANDO.value, Estado.LIVENESS.value, Estado.RESULTADO.value):
                if ident is not None:
                    # antes da decisão: turquesa = reconhecido; verde fica reservado a "autorizado"
                    cor = tema.ACENTO if ident.reconhecido else tema.VERMELHO
                    nome = ident.usuario.nome if ident.reconhecido else "Não reconhecido"
                    rotulo = f"{nome} · {ident.similaridade:.2f}"
                    if ident.reconhecido:
                        rotulo += f" · N{ident.usuario.nivel}"
                if estado == Estado.RESULTADO.value and decisao is not None:
                    cor = tema.VERDE if decisao.get("concedido") else tema.VERMELHO
            elif i > 0:
                cor, rotulo = tema.VERMELHO, "Pessoa extra"
            if estado == Estado.BLOQUEADO.value:
                cor, rotulo = tema.VERMELHO, "Bloqueado"
            if i == 0 and estado in (Estado.AGUARDANDO.value, Estado.CONFIRMANDO.value) and st.get("orientacao"):
                cor, rotulo = tema.AMARELO, st["orientacao"]       # aviso: pose/qualidade fora do aceitável
            caixas.append({
                "x": r.x, "y": r.y, "w": r.w, "h": r.h, "cor": cor, "rotulo": rotulo,
                "pontos": [r.olho_dir, r.olho_esq, r.nariz, r.boca_dir, r.boca_esq],
                "principal": i == 0,
                "malha": i == 0 and estado in (Estado.AGUARDANDO.value, Estado.CONFIRMANDO.value, Estado.LIVENESS.value),
            })
        return caixas

    def _aplicar_status(self, st: dict, ident, n_rostos: int) -> None:
        term = self.terminal
        self._definir("estado", st["estado"])
        self._definir("nRostos", n_rostos)
        self._definir("progresso", round(float(st["progresso_confirmacao"]), 3))
        self._definir("similaridade", round(float(ident.similaridade), 3) if ident is not None else -1.0)
        self._definir("livenessInstrucao", st["liveness_instrucao"])
        self._definir("orientacao", st.get("orientacao", ""))
        self._definir("livenessRestante", round(float(st["liveness_restante"]), 1))
        self._definir("livenessTotal", float(term.desafio.timeout))
        self._definir("livenessPasso", PASSO_LIVENESS.get(term.desafio.etapa, 0))
        self._definir("bloqueadoRestante", round(float(st["bloqueado_restante"]), 1))
        self._definir("bloqueioTotal", float(term.tentativas.bloqueio))
        self._definir("galeria", int(st["galeria"]))
        d = st.get("decisao")
        if d is None or st["estado"] != Estado.RESULTADO.value:
            self._limpar_resultado()
            return
        decisao = term.decisao_atual
        u = decisao.identificacao.usuario if decisao and decisao.identificacao and decisao.identificacao.reconhecido \
            else None
        self._definir("resultadoTipo", d["resultado"])
        self._definir("resultadoConcedido", bool(d["concedido"]))
        self._definir("resultadoTitulo", tema.TITULO_RESULTADO.get(d["resultado"], d["resultado"]))
        self._definir("resultadoNome", u.nome if u is not None else "")
        self._definir("resultadoNivel", int(u.nivel) if u is not None else 0)
        self._definir("resultadoMensagem", d.get("mensagem") or "")
        sim = d.get("similaridade")
        self._definir("resultadoSimilaridade", round(float(sim), 3) if sim is not None else -1.0)

    def _limpar_resultado(self) -> None:
        self._definir("resultadoConcedido", False)
        self._definir("resultadoTipo", "")
        self._definir("resultadoTitulo", "")
        self._definir("resultadoNome", "")
        self._definir("resultadoNivel", 0)
        self._definir("resultadoMensagem", "")
        self._definir("resultadoSimilaridade", -1.0)

    def _limpar_status(self) -> None:
        self._limpar_resultado()
        self._definir("estado", Estado.AGUARDANDO.value)
        self._definir("similaridade", -1.0)
        self._definir("progresso", 0.0)
        self._definir("nRostos", 0)

    def _atualizar_etapas(self, etapas: list) -> None:
        mudou = False
        presentes = set()
        for chave, qimg in etapas:
            presentes.add(chave)
            fonte = self._etapa_por_chave.get(chave)
            if fonte is None:
                fase, nome = tema.rotulo_etapa(chave)
                fonte = FonteVideo(f"{fase} · {nome}" if fase else nome, self)
                self._etapa_por_chave[chave] = fonte
                self._etapas.append(fonte)
                mudou = True
            fonte.definir(qimg, [])
        for chave, fonte in self._etapa_por_chave.items():
            if chave not in presentes and fonte.temImagem:
                fonte.limpar()                      # fase sem dado neste quadro (ex.: nenhum rosto)
        if mudou:
            self.etapasMudou.emit()

    # ------------------------------------------------------------------ banco
    def _ler_versao(self) -> int | None:
        try:
            return self.app.banco.versao_dados()
        except Exception:  # noqa: BLE001
            return None

    @Slot()
    def _checar_banco(self) -> None:
        """Recarrega a galeria quando outro processo grava no banco (cadastro em outra janela, CLI...)."""
        versao = self._ler_versao()
        anterior, self._versao_banco = self._versao_banco, versao
        if anterior is not None and versao is not None and versao != anterior:
            self.recarregarGaleria(silencioso=True)

    @Slot()
    def recarregarGaleria(self, silencioso: bool = False) -> None:
        try:
            if self.terminal is not None:
                self.terminal.reconhecedor.recarregar()
                total = self.terminal.reconhecedor.total_amostras
            else:
                total = self.app.banco.estatisticas()["amostras"]
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.app.notificar("erro", f"Falha ao recarregar a galeria: {e}")
            return
        self._definir("galeria", int(total))
        self.verificar_usuarios()
        self.atualizar_acessos()
        if not silencioso:
            self.app.notificar("info", f"Galeria recarregada: {total} amostras")

    def verificar_usuarios(self) -> None:
        try:
            ativos = self.app.banco.listar_usuarios(apenas_ativos=True)
            self._definir("usuariosAtivos", len(ativos))
            if self.terminal is not None:
                self._definir("galeria", self.terminal.reconhecedor.total_amostras)
            if not ativos:
                texto = "Nenhum usuário ativo cadastrado: todo rosto será negado."
            elif self.terminal is not None and self.terminal.reconhecedor.total_amostras == 0:
                texto = "Os usuários ativos não têm amostras biométricas. Refaça o cadastro."
            else:
                texto = ""
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            texto = f"Não foi possível consultar os usuários: {e}"
        self._definir("aviso", texto)

    def atualizar_acessos(self) -> None:
        try:
            acessos = self.app.banco.listar_acessos(8)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.app.notificar("erro", f"Falha ao ler o log de acessos: {e}")
            return
        self.acessos.definir([{
            "id": a.id,
            "hora": a.data_hora[11:19] if len(a.data_hora) >= 19 else a.data_hora,
            "nome": a.nome_detectado or "Não identificado",
            "resultado": a.resultado,
            "titulo": tema.ROTULO_CURTO_RESULTADO.get(a.resultado, a.resultado),
            "concedido": a.resultado == "CONCEDIDO",
            "nivelExigido": a.nivel_exigido,
            "similaridade": f"{a.similaridade:.2f}" if a.similaridade is not None else "–",
        } for a in acessos])

    # ------------------------------------------------------------------ controles (QML)
    def _bloqueado(self) -> bool:
        """Durante o bloqueio os controles de área e prova de vida ficam travados (também pelos atalhos)."""
        if self._v["estado"] == "BLOQUEADO":
            self.app.notificar("aviso", "Terminal bloqueado: aguarde o fim da contagem para mudar a configuração.")
            return True
        return False

    @Slot(int)
    def definirNivel(self, nivel: int) -> None:
        if nivel not in config.AREAS or self._bloqueado():
            return
        self._definir("nivel", int(nivel))
        self._definir("area", config.AREAS[int(nivel)])
        if self.terminal is not None:
            self.terminal.definir_nivel(int(nivel))

    @Slot(bool)
    def definirLiveness(self, ativo: bool) -> None:
        if self._bloqueado():
            return
        self._definir("liveness", bool(ativo))
        if self.terminal is not None:
            self.terminal.liveness_ativo = bool(ativo)

    @Slot(bool)
    def definirDidatico(self, ativo: bool) -> None:
        self._definir("didatico", bool(ativo))
        self._didatico_thread = bool(ativo)
        self._ultimo_didatico = 0.0
        if self.terminal is not None:
            self.terminal.didatico = bool(ativo)
        if not ativo:
            for e in self._etapas:
                e.limpar()

    @Slot(result="QVariantMap")
    def limitesPose(self) -> dict:
        return {"yaw": float(config.POSE_MAX_YAW), "roll": float(config.POSE_MAX_ROLL_GRAUS),
                "razaoMin": float(config.POSE_RAZAO_NARIZ_MIN), "razaoMax": float(config.POSE_RAZAO_NARIZ_MAX)}

    @Slot()
    def tentarCamera(self) -> None:
        self._definir("erro", "")
        self._abrir_camera()
