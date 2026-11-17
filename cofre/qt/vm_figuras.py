"""Exportação das figuras das telas de análise (v2) e o único ponto do código novo que abre algo no sistema.

"Exportar figura" grava, em `config.RELATORIOS_DIR / "figuras"`, o PNG (2x) e o SVG na paleta papel e o
CSV dos dados, pela mesma função de desenho da tela (`graficos.exportar`, que recusa dados com vetor
biométrico). Na base de demonstração os três arquivos levam o carimbo "Base de demonstração".

`abrir_no_sistema` é chamada sempre pelo módulo (`vm_figuras.abrir_no_sistema(...)`), para os testes
poderem trocá-la por um registrador: nenhum teste abre o Finder.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from PySide6.QtCore import QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from .. import config
from . import graficos
from .base import ViewModel, prop
from .formatos import carimbo_arquivo
from .trabalhos import Trabalho

CARIMBO_DEMO = "Base de demonstração"
NOME_PADRAO = "figura"


def abrir_no_sistema(caminho: Path) -> bool:
    """Abre a pasta ou o arquivo no programa padrão do sistema. Devolve se o sistema aceitou o pedido."""
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho)))


def pasta_figuras() -> Path:
    """Pasta das figuras exportadas, lida na hora (os testes redirecionam `config.RELATORIOS_DIR`)."""
    return Path(config.RELATORIOS_DIR) / "figuras"


def sanear_nome(nome: str) -> str:
    """Nome de arquivo só com [a-z0-9_-]: tira acentos, passa a minúsculas e troca o resto por "_"."""
    sem_acento = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode("ascii")
    saneado = re.sub(r"[^a-z0-9_-]+", "_", sem_acento.lower()).strip("_-")
    return saneado or NOME_PADRAO


class FigurasVM(ViewModel):
    ultimaPastaMudou = Signal()

    ultimaPasta = prop(str, "ultimaPasta", ultimaPastaMudou)      # pasta da última figura salva ("" = nenhuma)

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(ultimaPasta="")
        self.trabalho = Trabalho(aplicacao.extensoes.trabalhos, self)

    @Slot(str, "QVariantMap", str)
    def exportar(self, tipo: str, dados: dict, nome: str) -> None:
        """Grava a figura fora da thread da interface e avisa o resultado por notificação."""
        destino = pasta_figuras() / f"{sanear_nome(nome)}_{carimbo_arquivo()}"
        carimbo = CARIMBO_DEMO if self.app.extensoes.baseDemonstracao else ""
        dados = dict(dados or {})

        def gravar(sinal) -> list[Path]:
            sinal.conferir()
            return graficos.exportar(tipo, dados, destino, carimbo=carimbo)

        self.trabalho.executar(gravar, self._ao_exportar)

    def _ao_exportar(self, caminhos, erro: str) -> None:
        if erro:
            self.app.notificar("erro", f"Não foi possível exportar a figura: {erro}")
            return
        self._definir("ultimaPasta", str(caminhos[0].parent))
        self.app.notificar("info", f"Figura salva em figuras/{caminhos[0].name} (com SVG e CSV)")

    @Slot()
    def abrirPasta(self) -> None:
        """Abre a pasta das figuras no sistema (criada vazia se ainda não existir)."""
        pasta = pasta_figuras()
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.app.notificar("erro", f"Não foi possível criar a pasta de figuras: {e}")
            return
        if not abrir_no_sistema(pasta):
            self.app.notificar("erro", "O sistema não abriu a pasta de figuras.")
