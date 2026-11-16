"""
Pacote `cofre`: sistema de identificação e autenticação biométrica facial
para controle de acesso ao cofre do Ministério do Meio Ambiente (APS PIVC).

O código é organizado seguindo as cinco fases do processamento de imagens digitais:

    fase1_aquisicao        -> captura da imagem (webcam ou arquivo)
    fase2_preprocessamento -> correção de iluminação, ruído e tamanho
    fase3_segmentacao      -> detecção e recorte/alinhamento do rosto
    fase4_representacao    -> extração do vetor de características (embedding)
    fase5_reconhecimento   -> comparação com a base e decisão de acesso

Módulos de apoio: banco (SQLite), liveness (anti-fraude), hud (interface),
cadastro, autenticacao, relatorios e avaliacao.
"""

__version__ = "1.0.0"

# Silencia avisos internos do OpenCV 5 ("Targets are not supported by the new graph engine")
try:  # pragma: no cover
    import cv2 as _cv2
    _cv2.utils.logging.setLogLevel(_cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:  # noqa: BLE001
    pass
