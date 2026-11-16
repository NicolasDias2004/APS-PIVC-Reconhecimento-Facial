"""
ViewModel do cadastro biométrico: formulário, captura pela câmera (`SessaoCadastro`)
e importação de fotos (`cadastrar_de_imagens`).

Threads (iguais às da interface customtkinter):
  - câmera: só `pipeline.processar(frame, extrair_embedding=False)` e a conversão para QImage;
  - interface: `SessaoCadastro.passo()`, que grava as amostras no banco (conexão da thread principal);
  - importação de fotos: tarefa em segundo plano com conexão própria ao banco.
"""

from __future__ import annotations

import traceback
from pathlib import Path

import cv2
from PySide6.QtCore import Signal, Slot, QUrl

from .. import config, hud
from ..banco import Banco
from ..cadastro import INSTRUCOES_POSE, DadosCadastro, SessaoCadastro, cadastrar_de_imagens
from . import tema
from .base import ViewModel, objeto, prop
from .imagens import bgr_para_qimage
from .video import FonteVideo

LADO_MINIATURA = 160
MAX_AVISOS = 6
# Mesma ordem de cadastro.INSTRUCOES_POSE, com acentos (o HUD do OpenCV não desenha acentos).
POSES = [
    "Olhe para a câmera",
    "Vire um pouco o rosto para a esquerda",
    "Vire um pouco o rosto para a direita",
    "Incline a cabeça para a esquerda",
    "Incline a cabeça para a direita",
    "Levante um pouco o queixo",
    "Abaixe o queixo, como se olhasse o celular",
    "Olhe para a câmera de novo",
    "Sorria",
]
assert len(POSES) == len(INSTRUCOES_POSE)
_TIPO_COR = {hud.VERDE: "ok", hud.VERMELHO: "erro", hud.LARANJA: "aviso", hud.AMARELO: "neutro"}
_COR_TIPO = {"ok": tema.VERDE, "erro": tema.VERMELHO, "aviso": tema.AMARELO, "neutro": tema.ACENTO}


def _sem_acento_para_texto(status: str) -> str:
    """Os textos da SessaoCadastro não têm acento (o HUD do OpenCV não desenha acentos)."""
    trocas = {"camera": "câmera", "Posicione": "Posicione", "Apenas UMA pessoa deve aparecer":
              "Apenas uma pessoa deve aparecer", "Cadastro concluido!": "Cadastro concluído",
              "Capturando...": "Capturando…"}
    for a, b in trocas.items():
        status = status.replace(a, b)
    for i, pose in enumerate(INSTRUCOES_POSE):
        status = status.replace(pose, POSES[i])
    return status


def _miniatura(recorte) -> "object":
    h, w = recorte.shape[:2]
    m = min(h, w)
    y0, x0 = (h - m) // 2, (w - m) // 2
    quadrado = cv2.resize(recorte[y0:y0 + m, x0:x0 + m], (LADO_MINIATURA, LADO_MINIATURA),
                          interpolation=cv2.INTER_AREA)
    return bgr_para_qimage(quadrado)


def _caminho_local(url: str) -> str:
    u = QUrl(url)
    return u.toLocalFile() if u.isLocalFile() else url


class CadastroVM(ViewModel):
    faseMudou = Signal()
    erroMudou = Signal()
    erroCampoMudou = Signal()
    capturadasMudou = Signal()
    totalMudou = Signal()
    statusMudou = Signal()
    statusTipoMudou = Signal()
    poseMudou = Signal()
    poseIndiceMudou = Signal()
    nitidezMudou = Signal()
    brilhoMudou = Signal()
    qualidadeOkMudou = Signal()
    nRostosMudou = Signal()
    nomeMudou = Signal()
    nivelCadastroMudou = Signal()
    miniaturasMudou = Signal()
    revisaoMudou = Signal()
    sucessoMudou = Signal()
    pausadaMudou = Signal()
    amostraCapturada = Signal(int)

    fase = prop(str, "fase", faseMudou)       # formulario | preparando | capturando | importando
    erro = prop(str, "erro", erroMudou)
    erroCampo = prop(str, "erroCampo", erroCampoMudou)
    capturadas = prop(int, "capturadas", capturadasMudou)
    total = prop(int, "total", totalMudou)
    status = prop(str, "status", statusMudou)
    statusTipo = prop(str, "statusTipo", statusTipoMudou)
    pose = prop(str, "pose", poseMudou)
    poseIndice = prop(int, "poseIndice", poseIndiceMudou)
    nitidez = prop(float, "nitidez", nitidezMudou)
    brilho = prop(float, "brilho", brilhoMudou)
    qualidadeOk = prop(bool, "qualidadeOk", qualidadeOkMudou)
    nRostos = prop(int, "nRostos", nRostosMudou)
    nome = prop(str, "nome", nomeMudou)
    nivelCadastro = prop(int, "nivelCadastro", nivelCadastroMudou)
    miniaturas = prop(int, "miniaturas", miniaturasMudou)
    revisao = prop(int, "revisao", revisaoMudou)
    sucesso = prop("QVariantMap", "sucesso", sucessoMudou)
    pausada = prop(bool, "pausada", pausadaMudou)
    fonteVideo = objeto("video")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(fase="formulario", erro="", erroCampo="", capturadas=0, total=config.AMOSTRAS_POR_CADASTRO,
                      status="", statusTipo="neutro", pose=POSES[0], poseIndice=0, nitidez=0.0, brilho=0.0,
                      qualidadeOk=False, nRostos=0, nome="", nivelCadastro=1, miniaturas=0, revisao=0,
                      sucesso={}, pausada=False)
        self.video = FonteVideo("cadastro", self)
        self.sessao: SessaoCadastro | None = None
        self._dados_pendentes: DadosCadastro | None = None
        self._ativo = False
        self._seq_visto = -1
        aplicacao.camera.quadroDisponivel.connect(self._quadro)

    # ------------------------------------------------------------------ constantes para o QML
    @Slot(result="QVariantMap")
    def limites(self) -> dict:
        return {"minNitidez": float(config.MIN_NITIDEZ), "minBrilho": float(config.MIN_BRILHO),
                "maxBrilho": float(config.MAX_BRILHO), "poses": POSES, "intervalo": float(config.INTERVALO_AMOSTRAS_SEG)}

    @property
    def capturando(self) -> bool:
        return self._dados_pendentes is not None or (self.sessao is not None and not self.sessao.encerrada)

    # ------------------------------------------------------------------ ciclo de vida
    def ativar(self) -> None:
        self._ativo = True
        if self.capturando:
            self._definir("pausada", False)
            self._ligar_camera()

    def desativar(self) -> None:
        self._ativo = False
        if self.capturando:
            self._definir("pausada", True)     # a sessão continua; a câmera volta ao reabrir a tela
        self.app.camera.parar()

    def ao_pipeline_pronto(self) -> None:
        self._iniciar_sessao_se_pronto()

    # ------------------------------------------------------------------ formulário
    @Slot(str, result=str)
    def matriculaEmUso(self, matricula: str) -> str:
        """Nome de quem já usa a matrícula ('' se livre). Usado na validação ao digitar."""
        matricula = (matricula or "").strip()
        if not matricula:
            return ""
        try:
            u = self.app.banco.obter_por_matricula(matricula)
        except Exception:  # noqa: BLE001
            return ""
        return u.nome if u is not None else ""

    def _validar(self, nome: str, matricula: str, cargo: str, nivel: int) -> DadosCadastro | None:
        nome, matricula, cargo = (nome or "").strip(), (matricula or "").strip(), (cargo or "").strip()
        if not nome:
            return self._erro("nome", "Informe o nome do usuário.")
        if not matricula:
            return self._erro("matricula", "Informe a matrícula.")
        if int(nivel) not in config.NIVEIS:
            return self._erro("nivel", "Escolha um nível de acesso válido.")
        try:
            existente = self.app.banco.obter_por_matricula(matricula)
        except Exception as e:  # noqa: BLE001
            return self._erro("", f"Não foi possível consultar o banco: {e}")
        if existente is not None:
            return self._erro("matricula", f"Matrícula {matricula} já cadastrada para {existente.nome}.")
        self._definir("erro", "")
        self._definir("erroCampo", "")
        return DadosCadastro(nome, matricula, cargo, int(nivel))

    def _erro(self, campo: str, texto: str) -> None:
        self._definir("erroCampo", campo)
        self._definir("erro", texto)
        return None

    @Slot()
    def limparErro(self) -> None:
        self._definir("erro", "")
        self._definir("erroCampo", "")

    @Slot()
    def fecharSucesso(self) -> None:
        self._definir("sucesso", {})

    # ------------------------------------------------------------------ captura pela câmera
    @Slot(str, str, str, int, result=bool)
    def iniciarCaptura(self, nome: str, matricula: str, cargo: str, nivel: int) -> bool:
        if self.capturando or self._v["fase"] == "importando":
            return False
        dados = self._validar(nome, matricula, cargo, nivel)
        if dados is None:
            return False
        self._dados_pendentes = dados
        self._definir("sucesso", {})
        self._definir("nome", dados.nome)
        self._definir("nivelCadastro", dados.nivel)
        self._definir("fase", "preparando")
        self._definir("pausada", False)
        self._zerar_progresso(config.AMOSTRAS_POR_CADASTRO)
        self._definir("status", "Carregando os modelos…" if self.app.pipeline is None else "Ligando a câmera…")
        self._iniciar_sessao_se_pronto()
        return True

    def _zerar_progresso(self, total: int) -> None:
        self.app.imagens.remover_prefixo("cadastro/")
        self._definir("revisao", self._v["revisao"] + 1)
        self._definir("miniaturas", 0)
        self._definir("capturadas", 0)
        self._definir("total", int(total))
        self._definir("statusTipo", "neutro")
        self._definir("pose", POSES[0])
        self._definir("poseIndice", 0)
        self._definir("nitidez", 0.0)
        self._definir("brilho", 0.0)
        self._definir("qualidadeOk", False)
        self._definir("nRostos", 0)
        self.video.limpar()

    def _iniciar_sessao_se_pronto(self) -> None:
        if self._dados_pendentes is None or self.app.pipeline is None:
            return
        dados, self._dados_pendentes = self._dados_pendentes, None
        try:
            # quantidade explícita: o padrão do construtor é fixado na importação do módulo
            self.sessao = SessaoCadastro(self.app.banco, self.app.pipeline, dados,
                                         amostras=int(config.AMOSTRAS_POR_CADASTRO))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.sessao = None
            self._definir("fase", "formulario")
            self._erro("", f"Não foi possível iniciar o cadastro: {e}")
            return
        self._zerar_progresso(self.sessao.amostras)
        self._definir("fase", "capturando")
        self._definir("status", "Posicione o rosto na câmera")
        if self._ativo:
            self._ligar_camera()

    def _ligar_camera(self) -> None:
        if self.sessao is None or self.sessao.encerrada or self.app.pipeline is None:
            return
        self._seq_visto = -1
        self.app.camera.iniciar(self._processar)

    def _processar(self, frame):
        """Thread da câmera: só o pipeline e a conversão (sem banco, sem QML)."""
        res = self.app.pipeline.processar(frame, extrair_embedding=False)
        return res, bgr_para_qimage(frame)

    @Slot()
    def tentarCamera(self) -> None:
        self._ligar_camera()

    @Slot()
    def _quadro(self) -> None:
        sessao = self.sessao
        if not self._ativo or sessao is None or sessao.encerrada:
            return
        pacote = self.app.camera.ultimo()
        if pacote is None or pacote.seq == self._seq_visto or pacote.saida is None:
            return
        self._seq_visto = pacote.seq
        res, qimg = pacote.saida
        try:
            sessao.passo(pacote.frame, res)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._definir("status", f"Erro ao gravar a amostra: {e}")
            self._definir("statusTipo", "erro")
            return
        tipo = _TIPO_COR.get(tuple(sessao.cor), "neutro")
        self._definir("status", _sem_acento_para_texto(sessao.status))
        self._definir("statusTipo", tipo)
        pose = sessao.pose if sessao.pose in INSTRUCOES_POSE else INSTRUCOES_POSE[0]
        self._definir("poseIndice", INSTRUCOES_POSE.index(pose))
        self._definir("pose", POSES[INSTRUCOES_POSE.index(pose)])
        self._definir("nRostos", len(res.rostos))
        p = res.principal
        if p is not None and len(res.rostos) == 1:
            self._definir("nitidez", round(float(p.qualidade.nitidez), 1))
            self._definir("brilho", round(float(p.qualidade.brilho), 1))
            self._definir("qualidadeOk", bool(p.qualidade.aprovada))
        else:
            self._definir("qualidadeOk", False)
        self.video.definir(qimg, self._caixas(res, tipo))
        self.app.camera.atualizar_fps(pacote.fps)
        self._sincronizar_miniaturas()
        self._definir("capturadas", sessao.capturadas)
        if sessao.capturou_agora:
            self.amostraCapturada.emit(sessao.capturadas)

    def _caixas(self, res, tipo: str) -> list[dict]:
        caixas = []
        if len(res.rostos) > 1:
            for rp in res.rostos:
                r = rp.rosto
                caixas.append({"x": r.x, "y": r.y, "w": r.w, "h": r.h, "cor": tema.VERMELHO, "rotulo": "", "pontos": []})
        elif res.rostos:
            rp = res.principal
            r = rp.rosto
            ok = rp.qualidade.aprovada
            caixas.append({"x": r.x, "y": r.y, "w": r.w, "h": r.h, "cor": _COR_TIPO.get(tipo, tema.ACENTO),
                           "rotulo": "Qualidade OK" if ok else "",
                           "pontos": [r.olho_dir, r.olho_esq, r.nariz, r.boca_dir, r.boca_esq] if ok else []})
        return caixas

    def _sincronizar_miniaturas(self) -> None:
        sessao = self.sessao
        n = self._v["miniaturas"]
        novas = sessao.miniaturas[n:]
        if not novas:
            return
        for i, recorte in enumerate(novas, start=n):
            try:
                self.app.imagens.guardar(f"cadastro/{i}", _miniatura(recorte))
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        self._definir("miniaturas", len(sessao.miniaturas))

    @Slot()
    def cancelar(self) -> None:
        """Desfaz o cadastro em andamento (usuário e amostras já gravadas) e desliga a câmera."""
        sessao, self.sessao = self.sessao, None
        self._dados_pendentes = None
        if sessao is not None and not sessao.encerrada:
            try:
                sessao.cancelar()
            except Exception as e:  # noqa: BLE001
                self._erro("", f"Falha ao desfazer o cadastro: {e}")
        self._encerrar()
        self._zerar_progresso(config.AMOSTRAS_POR_CADASTRO)
        self.app.notificar("info", "Cadastro cancelado. Nada foi gravado.")

    @Slot()
    def concluir(self) -> None:
        sessao = self.sessao
        if sessao is None:
            return
        self.sessao = None
        try:
            usuario = sessao.concluir()
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            usuario = None
            self._erro("", f"Falha ao concluir o cadastro: {e}")
        self._encerrar()
        if usuario is None:
            self.app.notificar("aviso", "Nenhuma amostra capturada: o cadastro foi desfeito.")
            return
        self._anunciar_sucesso(usuario, sessao.capturadas, [])

    def _encerrar(self) -> None:
        self.app.camera.parar()
        self._definir("fase", "formulario")
        self._definir("pausada", False)
        self.video.limpar()

    def _anunciar_sucesso(self, usuario, n: int, avisos: list[str]) -> None:
        resumidos = []
        for a in avisos[:MAX_AVISOS]:
            caminho, sep, resto = a.partition(": ")
            resumidos.append(f"{Path(caminho).name}: {resto}" if sep and Path(caminho).suffix else a)
        if len(avisos) > MAX_AVISOS:
            resumidos.append(f"… e mais {len(avisos) - MAX_AVISOS} aviso(s)")
        self._definir("sucesso", {
            "nome": usuario.nome, "matricula": usuario.matricula, "cargo": usuario.cargo or "",
            "nivel": int(usuario.nivel), "nivelDescricao": config.NIVEIS.get(usuario.nivel, ""),
            "area": config.AREAS.get(usuario.nivel, ""), "amostras": int(n), "avisos": resumidos,
        })
        self.app.notificar("ok", f"{usuario.nome} cadastrado com {n} amostra(s).")
        self.app.banco_alterado()

    # ------------------------------------------------------------------ cadastro por fotos
    @Slot(str, str, str, int, "QVariantList", result=bool)
    def cadastrarPorFotos(self, nome: str, matricula: str, cargo: str, nivel: int, urls: list) -> bool:
        if self.capturando or self._v["fase"] == "importando":
            return False
        caminhos = [_caminho_local(str(u)) for u in (urls or []) if str(u)]
        if not caminhos:
            self._erro("", "Nenhuma foto escolhida.")
            return False
        dados = self._validar(nome, matricula, cargo, nivel)
        if dados is None:
            return False
        if self.app.pipeline is None:
            self._erro("", "Os modelos ainda estão carregando. Tente novamente em instantes.")
            return False
        self._definir("sucesso", {})
        self._definir("fase", "importando")
        self._definir("status", f"Processando {len(caminhos)} foto(s)…")
        caminho_db, pipeline = self.app.banco.caminho, self.app.pipeline
        em_memoria = str(caminho_db) == ":memory:"
        banco_principal = self.app.banco

        def trabalho():
            banco = banco_principal if em_memoria else Banco(caminho_db)
            try:
                return cadastrar_de_imagens(banco, pipeline, dados, caminhos)
            finally:
                if banco is not banco_principal:
                    banco.fechar()

        def terminou(resultado, erro: str) -> None:
            self._definir("fase", "formulario")
            if erro:
                self._erro("", f"Cadastro por fotos falhou: {erro}")
                return
            usuario, n, avisos = resultado
            usuario = self.app.banco.obter_usuario(usuario.id) or usuario   # relê pela conexão principal
            self._anunciar_sucesso(usuario, n, avisos)

        if em_memoria:      # banco em memória (testes): a conexão não pode mudar de thread
            try:
                terminou(trabalho(), "")
            except Exception as e:  # noqa: BLE001
                terminou(None, str(e))
        else:
            self.app.tarefas.executar(trabalho, terminou)
        return True
