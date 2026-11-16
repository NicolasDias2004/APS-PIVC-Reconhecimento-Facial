"""Cores e rótulos usados pelo lado Python da interface Qt (o QML tem o seu Theme.qml,
com os mesmos valores)."""

ACENTO = "#2dd4bf"
VERDE = "#34d399"
VERMELHO = "#f87171"
AMARELO = "#fbbf24"
NEUTRO = "#94a3b8"

TITULO_RESULTADO = {
    "CONCEDIDO": "Acesso autorizado",
    "NEGADO_NIVEL": "Nível insuficiente",
    "NEGADO_DESCONHECIDO": "Rosto não reconhecido",
    "NEGADO_LIVENESS": "Prova de vida não concluída",
    "NEGADO_MULTIPLOS": "Mais de uma pessoa",
    "BLOQUEADO": "Terminal bloqueado",
}

ROTULO_CURTO_RESULTADO = {
    "CONCEDIDO": "Concedido",
    "NEGADO_NIVEL": "Nível insuficiente",
    "NEGADO_DESCONHECIDO": "Não cadastrado",
    "NEGADO_LIVENESS": "Prova de vida",
    "NEGADO_MULTIPLOS": "Mais de uma pessoa",
    "BLOQUEADO": "Bloqueio",
}

ETAPAS_DIDATICAS = {
    "1 original": ("Fase 1", "Aquisição"),
    "2 reduzida": ("Fase 2", "Redução"),
    "2 cinza": ("Fase 2", "Tons de cinza"),
    "2 suavizada": ("Fase 2", "Suavização"),
    "2 CLAHE": ("Fase 2", "Equalização CLAHE"),
    "3 deteccao+pontos": ("Fase 3", "Detecção e pontos"),
    "3 recorte": ("Fase 3", "Recorte"),
    "3 alinhado 112x112": ("Fase 3", "Alinhado 112×112"),
    "4 LBP (textura)": ("Fase 4", "Textura LBP"),
    "4 embedding 128-d": ("Fase 4", "Embedding 128-d"),
}


def rotulo_etapa(chave: str) -> tuple[str, str]:
    if chave in ETAPAS_DIDATICAS:
        return ETAPAS_DIDATICAS[chave]
    fase, _, nome = chave.partition(" ")
    return (f"Fase {fase}" if fase.isdigit() else "", nome or chave)
