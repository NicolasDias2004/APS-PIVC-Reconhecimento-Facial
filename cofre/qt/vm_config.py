"""ViewModel das configurações: formulário dos parâmetros de `cofre.parametros` com validação,
alterações pendentes, aplicar/descartar, padrões e arquivo `config_usuario.json`."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

import cv2
from PySide6.QtCore import Signal, Slot
from PySide6 import __version__ as versao_pyside

from .. import __version__, config, parametros
from .base import ViewModel, objeto, prop
from .modelos import ModeloLista

# Parâmetros que mudam o comportamento de segurança: a tela os destaca.
SEGURANCA = {"LIMIAR_COSSENO", "FRAMES_CONFIRMACAO", "LIVENESS_ATIVO", "LIVENESS_LIMIAR_YAW", "LIVENESS_TIMEOUT_SEG",
             "MAX_TENTATIVAS_FALHAS", "BLOQUEIO_SEG", "BLOQUEAR_MULTIPLOS_ROSTOS"}

# Quando cada parâmetro passa a valer NESTE aplicativo (conferido no código do backend).
# "importacao": Confirmador, DesafioMovimento e ControleTentativas recebem o valor como argumento
# padrão, avaliado quando o módulo é importado; mudar `config` depois não muda nada. Corrigir isso
# mexe em controles de segurança e depende de aprovação, então a tela não deixa editar esses campos.
EFEITO = {
    "LIMIAR_COSSENO": "imediato", "BLOQUEAR_MULTIPLOS_ROSTOS": "imediato", "MIN_NITIDEZ": "imediato",
    "INTERVALO_AMOSTRAS_SEG": "imediato", "TEMPO_EXIBIR_RESULTADO_SEG": "imediato",
    "SESSAO_LIBERADA_SEG": "imediato", "POSE_MAX_YAW": "imediato", "POSE_MAX_ROLL_GRAUS": "imediato",
    "POSE_RAZAO_NARIZ_MAX": "imediato", "POSE_RAZAO_NARIZ_MIN": "imediato",
    "AMOSTRAS_POR_CADASTRO": "cadastro", "CAMERA_INDEX": "camera", "ESPELHAR_CAMERA": "camera",
    "LIVENESS_ATIVO": "abertura",
    "FRAMES_CONFIRMACAO": "importacao", "LIVENESS_LIMIAR_YAW": "importacao", "LIVENESS_TIMEOUT_SEG": "importacao",
    "MAX_TENTATIVAS_FALHAS": "importacao", "BLOQUEIO_SEG": "importacao",
}
TEXTO_EFEITO = {
    "imediato": "Vale assim que aplicar",
    "cadastro": "Vale no próximo cadastro",
    "camera": "Vale na próxima vez que a câmera ligar",
    "abertura": "Define o estado inicial do terminal ao abrir o aplicativo; no terminal há um interruptor",
    "importacao": "Somente leitura: o backend fixa este valor quando o programa é carregado",
}
MENSAGEM_APLICADO = ("Aplicado. Cada campo indica quando passa a valer; os de somente leitura "
                     "não mudam nesta versão.")


class ConfigVM(ViewModel):
    pendentesMudou = Signal()
    mensagemMudou = Signal()
    mensagemTipoMudou = Signal()
    arquivoExisteMudou = Signal()
    configAplicada = Signal()

    pendentes = prop(int, "pendentes", pendentesMudou)
    mensagem = prop(str, "mensagem", mensagemMudou)
    mensagemTipo = prop(str, "mensagemTipo", mensagemTipoMudou)
    arquivoExiste = prop(bool, "arquivoExiste", arquivoExisteMudou)
    modeloCampos = objeto("campos")

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(pendentes=0, mensagem="", mensagemTipo="info", arquivoExiste=False)
        self.padroes = parametros.valores_atuais()          # valores do módulo ao abrir o aplicativo
        self._form = dict(self.padroes)
        self.campos = ModeloLista(["id", "chave", "rotulo", "explicacao", "tipo", "minimo", "maximo", "passo", "casas",
                                   "secao", "valor", "texto", "aplicado", "textoAplicado", "padrao", "alterado",
                                   "diferePadrao", "seguranca", "efeito", "textoEfeito", "editavel"], self)
        self._atualizar()

    # ------------------------------------------------------------------ carga inicial
    def carregar_inicial(self) -> None:
        """Na abertura do aplicativo: se o usuário salvou um arquivo, aplica (como a tela antiga fazia
        ao ser aberta). Arquivo inválido é ignorado com aviso, sem aplicar nada pela metade."""
        caminho = parametros.caminho_arquivo()
        if not caminho.exists():
            self._msg("Valores atuais do sistema. Nenhum arquivo de configuração salvo.", "info")
            return
        try:
            lidos = parametros.ler_arquivo(caminho)
            lidos = {k: v for k, v in lidos.items() if EFEITO.get(k) != "importacao"}
            parametros.aplicar({**parametros.valores_atuais(), **lidos})
        except (OSError, ValueError, TypeError, KeyError) as e:
            self._msg(f"Arquivo {caminho.name} ignorado: {e}", "erro")
            return
        self._form = parametros.valores_atuais()
        self._atualizar()
        self._msg(f"Configuração carregada de {caminho.name} e aplicada.", "ok")

    # ------------------------------------------------------------------ estado
    def _msg(self, texto: str, tipo: str) -> None:
        self._definir("mensagem", texto)
        self._definir("mensagemTipo", tipo)

    def _atualizar(self) -> None:
        atuais = parametros.valores_atuais()
        itens, pendentes = [], 0
        for i, c in enumerate(parametros.CAMPOS):
            valor, aplicado, padrao = self._form[c.chave], atuais[c.chave], self.padroes[c.chave]
            alterado = valor != aplicado
            pendentes += alterado
            itens.append({
                "id": i, "chave": c.chave, "rotulo": c.rotulo, "explicacao": c.explicacao, "tipo": c.tipo,
                "minimo": float(c.minimo), "maximo": float(c.maximo), "passo": float(c.passo), "casas": c.casas,
                "secao": c.secao, "valor": valor, "texto": c.formatar(valor), "aplicado": aplicado,
                "textoAplicado": c.formatar(aplicado), "padrao": padrao, "alterado": bool(alterado),
                "diferePadrao": aplicado != padrao, "seguranca": c.chave in SEGURANCA,
                "efeito": EFEITO.get(c.chave, "imediato"), "textoEfeito": TEXTO_EFEITO[EFEITO.get(c.chave, "imediato")],
                "editavel": EFEITO.get(c.chave) != "importacao",
            })
        self.campos.definir(itens)
        self._definir("pendentes", int(pendentes))
        self._definir("arquivoExiste", parametros.caminho_arquivo().exists())

    @Slot(result="QVariantList")
    def secoes(self) -> list:
        vistas: list[str] = []
        for c in parametros.CAMPOS:
            if c.secao not in vistas:
                vistas.append(c.secao)
        return vistas

    @Slot(result=str)
    def caminhoArquivo(self) -> str:
        return str(parametros.caminho_arquivo())

    # ------------------------------------------------------------------ edição
    @Slot(str, "QVariant", result=bool)
    def definir(self, chave: str, valor) -> bool:
        campo = parametros.CAMPOS_POR_CHAVE.get(chave)
        if campo is None:
            return False
        if EFEITO.get(chave) == "importacao":
            self._msg(f"\"{campo.rotulo}\" é somente leitura nesta versão.", "aviso")
            return False
        try:
            if campo.tipo != "bool" and isinstance(valor, str):
                valor = float(valor.replace(",", "."))
            self._form[chave] = campo.normalizar(valor)
        except (ValueError, TypeError) as e:
            self._msg(f"Valor inválido em \"{campo.rotulo}\": {e}", "erro")
            self._atualizar()
            return False
        self._atualizar()
        if self._v["pendentes"]:
            self._msg(f"{self._v['pendentes']} alteração(ões) pendente(s). Clique em Aplicar para valer.", "aviso")
        else:
            self._msg("Sem alterações pendentes.", "info")
        return True

    @Slot(result=bool)
    def aplicar(self) -> bool:
        try:
            self._form = parametros.aplicar(self._form)
        except (ValueError, KeyError) as e:
            self._msg(f"Valor inválido: {e}", "erro")
            return False
        self._atualizar()
        self._msg(MENSAGEM_APLICADO, "ok")
        self.app.notificar("ok", "Configurações aplicadas.")
        self.configAplicada.emit()
        return True

    @Slot()
    def descartar(self) -> None:
        self._form = parametros.valores_atuais()
        self._atualizar()
        self._msg("Alterações descartadas.", "info")

    @Slot()
    def restaurarPadroes(self) -> None:
        atuais = parametros.valores_atuais()
        self._form = {k: (atuais[k] if EFEITO.get(k) == "importacao" else v) for k, v in self.padroes.items()}
        self._atualizar()
        self._msg("Padrões restaurados no formulário. Clique em Aplicar para valer.", "aviso")

    @Slot(result=bool)
    def salvar(self) -> bool:
        try:
            caminho = parametros.salvar_arquivo(self._form)
        except (OSError, ValueError, KeyError) as e:
            self._msg(f"Não foi possível salvar o arquivo: {e}", "erro")
            return False
        self._atualizar()
        self._msg(f"Salvo em {caminho.name}. O arquivo é aplicado ao abrir o aplicativo.", "ok")
        self.app.notificar("ok", f"Configuração salva em {caminho.name}")
        return True

    @Slot(result=bool)
    def carregar(self) -> bool:
        caminho = parametros.caminho_arquivo()
        if not caminho.exists():
            self._msg(f"Arquivo não encontrado: {caminho}", "erro")
            return False
        try:
            lidos = parametros.ler_arquivo(caminho)
        except (OSError, ValueError, TypeError) as e:
            self._msg(f"Arquivo inválido ({caminho.name}): {e}", "erro")
            return False
        self._form.update({k: v for k, v in lidos.items() if EFEITO.get(k) != "importacao"})
        if self.aplicar():
            self._msg(f"Carregado de {caminho.name} e aplicado. {MENSAGEM_APLICADO}", "ok")
            return True
        return False

    # ------------------------------------------------------------------ informações
    @Slot(result="QVariantList")
    def informacoes(self) -> list:
        def arquivo(p: Path) -> str:
            try:
                return f"{p.name} ({p.stat().st_size / 1024:.0f} KB)" if p.exists() else f"{p.name} (não encontrado)"
            except OSError:
                return str(p)
        banco = getattr(self.app, "banco", None)
        return [
            {"nome": "Banco de dados", "valor": str(getattr(banco, "caminho", config.DB_PATH))},
            {"nome": "Pasta de dados", "valor": str(config.DATA_DIR)},
            {"nome": "Arquivo de configuração", "valor": str(parametros.caminho_arquivo())},
            {"nome": "Detecção (YuNet)", "valor": arquivo(Path(config.MODELO_DETECCAO))},
            {"nome": "Reconhecimento (SFace)", "valor": arquivo(Path(config.MODELO_RECONHECIMENTO))},
            {"nome": "Captura", "valor": f"{config.CAMERA_LARGURA}×{config.CAMERA_ALTURA}, processamento em "
                                         f"{config.LARGURA_PROCESSAMENTO} px"},
            {"nome": "Embedding", "valor": "rosto alinhado 112×112 → vetor de 128 dimensões"},
            {"nome": "OpenCV", "valor": cv2.__version__},
            {"nome": "Qt / PySide6", "valor": versao_pyside},
            {"nome": "Python", "valor": f"{platform.python_version()} ({sys.platform})"},
            {"nome": "Versão do aplicativo", "valor": __version__},
        ]

    @Slot(result="QVariantList")
    def niveis(self) -> list:
        return [{"nivel": n, "descricao": config.NIVEIS[n], "area": config.AREAS.get(n, "–")}
                for n in sorted(config.NIVEIS)]
