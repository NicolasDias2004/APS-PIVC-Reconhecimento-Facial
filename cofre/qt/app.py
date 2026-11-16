"""Inicialização do aplicativo Qt Quick: QGuiApplication, estilo, tipos nativos e QML."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuickControls2 import QQuickStyle

from .. import config
from .aplicacao import Aplicacao
from .video import VisorVideo

DIR_QML = Path(__file__).resolve().parent / "qml"
ARQUIVO_MAIN = DIR_QML / "Cofre" / "Ui" / "Main.qml"

_registrado = False


def registrar_tipos() -> None:
    global _registrado
    if not _registrado:
        qmlRegisterType(VisorVideo, "Cofre.Nativo", 1, 0, "VisorVideo")
        _registrado = True


def preparar_qt(argv: list[str] | None = None) -> QGuiApplication:
    """Cria (ou reaproveita) a QGuiApplication com o estilo e a fonte do aplicativo."""
    QQuickStyle.setStyle("Basic")            # estilo neutro, totalmente personalizado pelo Theme.qml
    app = QGuiApplication.instance() or QGuiApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Cofre MMA")
    app.setOrganizationName("APS PIVC")
    app.setApplicationDisplayName("Cofre MMA")
    fonte = QFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))
    fonte.setPixelSize(13)
    fonte.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(fonte)
    registrar_tipos()
    return app


def criar_motor(aplicacao: Aplicacao, avisos: list[str] | None = None) -> QQmlApplicationEngine:
    """Carrega o Main.qml. Avisos do QML vão para `avisos` (os testes falham se houver algum)."""
    motor = QQmlApplicationEngine()
    motor.addImageProvider("cofre", aplicacao.imagens)
    motor.addImportPath(str(DIR_QML))
    motor.rootContext().setContextProperty("app", aplicacao)
    if avisos is not None:
        motor.warnings.connect(lambda lista: avisos.extend(w.toString() for w in lista))
    motor.load(QUrl.fromLocalFile(str(ARQUIVO_MAIN)))
    return motor


def destruir_motor(motor: QQmlApplicationEngine) -> None:
    """Destrói a janela antes do motor: assim nenhum vínculo do QML é reavaliado com `app` nulo."""
    for obj in motor.rootObjects():
        obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    motor.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def executar(caminho_db=config.DB_PATH, fonte_camera: Callable[[], Any] | None = None) -> int:
    app = preparar_qt()
    icone = config.BASE_DIR / "docs" / "icone.png"
    if icone.exists():
        app.setWindowIcon(QIcon(str(icone)))
    aplicacao = Aplicacao(caminho_db, fonte_camera)
    motor = criar_motor(aplicacao)
    if not motor.rootObjects():
        print("Falha ao carregar a interface QML (veja as mensagens acima).", file=sys.stderr)
        aplicacao.fechar()
        return 1
    app.aboutToQuit.connect(aplicacao.fechar)
    aplicacao.navegar("terminal")
    codigo = app.exec()
    destruir_motor(motor)
    return codigo
