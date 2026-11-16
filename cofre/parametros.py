"""
Parâmetros ajustáveis do sistema, sem depender de nenhuma interface gráfica.

Cada `Campo` descreve um atributo de `cofre.config` (tipo, intervalo, seção e explicação).
As duas interfaces (customtkinter e Qt/QML) usam estas definições, e as funções do fim
do arquivo leem, aplicam e gravam o arquivo `config_usuario.json`.

Alguns objetos leem `config` no momento do uso (ex.: o limiar de similaridade, a cada frame)
e outros ao serem criados (`Confirmador`, `DesafioMovimento`, `ControleTentativas`,
`SessaoCadastro`). Estes só enxergam o valor novo na próxima sessão de câmera.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config

ARQUIVO_CONFIG_NOME = "config_usuario.json"

MENSAGEM_APLICADO = (
    "Aplicado: vale para a próxima sessão de câmera. Limiar de similaridade, nitidez mínima, "
    "múltiplos rostos e tempo do resultado valem imediatamente; frames de confirmação, prova de vida, "
    "tentativas/bloqueio, amostras e câmera são lidos quando o terminal ou o cadastro é criado."
)


@dataclass(frozen=True)
class Campo:
    """Descreve um campo do formulário ligado a um atributo de `cofre.config`."""

    chave: str
    rotulo: str
    explicacao: str
    tipo: str                      # "float" | "int" | "bool"
    minimo: float = 0.0
    maximo: float = 1.0
    passo: float = 1.0
    casas: int = 0                 # casas decimais exibidas (float)
    secao: str = ""

    def normalizar(self, valor: Any) -> Any:
        """Converte e limita o valor ao tipo e ao intervalo do campo. Levanta ValueError se inválido."""
        if self.tipo == "bool":
            if isinstance(valor, bool):
                return valor
            if isinstance(valor, (int, float)) and valor in (0, 1):
                return bool(valor)
            raise ValueError(f"{self.chave}: esperado verdadeiro/falso, recebido {valor!r}")
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError(f"{self.chave}: esperado número, recebido {valor!r}")
        v = float(valor)
        if v != v:  # NaN
            raise ValueError(f"{self.chave}: valor inválido")
        v = min(self.maximo, max(self.minimo, v))
        if self.tipo == "int":
            return int(round(v))
        return round(v, max(self.casas, 3))

    def formatar(self, valor: Any) -> str:
        if self.tipo == "bool":
            return "ligado" if valor else "desligado"
        if self.tipo == "int":
            return str(int(valor))
        return f"{float(valor):.{self.casas}f}"


CAMPOS: tuple[Campo, ...] = (
    Campo("LIMIAR_COSSENO", "Limiar de similaridade (cosseno)",
          "Acima deste valor o rosto é considerado a mesma pessoa. Maior = mais rígido, mais rejeições de "
          "cadastrados; menor = mais aceitações indevidas. O OpenCV recomenda 0,363 para o SFace.",
          "float", 0.20, 0.80, 0.005, 3, "Reconhecimento"),
    Campo("FRAMES_CONFIRMACAO", "Frames de confirmação",
          "Quantos frames seguidos precisam apontar a mesma identidade antes de decidir. Evita decisão em "
          "um frame ruim; valores altos deixam a resposta mais lenta.",
          "int", 2, 15, 1, 0, "Reconhecimento"),
    Campo("LIVENESS_ATIVO", "Prova de vida (liveness)",
          "Exige que a pessoa vire a cabeça (esquerda, direita, centro) antes de liberar. Dificulta fraude "
          "com foto ou vídeo na frente da câmera.",
          "bool", secao="Prova de vida"),
    Campo("LIVENESS_LIMIAR_YAW", "Limiar de giro da cabeça (yaw)",
          "Razão nariz/olhos a partir da qual a cabeça conta como virada. Menor = basta um giro leve; maior "
          "= precisa virar mais, o que reduz falsos positivos do desafio.",
          "float", 0.10, 0.40, 0.01, 2, "Prova de vida"),
    Campo("LIVENESS_TIMEOUT_SEG", "Tempo limite do desafio (s)",
          "Segundos para completar o movimento. Se estourar, a tentativa é negada por prova de vida.",
          "int", 5, 30, 1, 0, "Prova de vida"),
    Campo("MAX_TENTATIVAS_FALHAS", "Máximo de falhas seguidas",
          "Negações consecutivas (na janela de tempo) antes de bloquear o terminal. Protege contra "
          "tentativa e erro.",
          "int", 1, 10, 1, 0, "Anti-fraude"),
    Campo("BLOQUEIO_SEG", "Duração do bloqueio (s)",
          "Por quanto tempo o terminal fica bloqueado depois de atingir o máximo de falhas.",
          "int", 5, 300, 1, 0, "Anti-fraude"),
    Campo("BLOQUEAR_MULTIPLOS_ROSTOS", "Bloquear mais de um rosto",
          "Com mais de uma pessoa no quadro a autenticação é negada (evita 'carona' / tailgating).",
          "bool", secao="Anti-fraude"),
    Campo("AMOSTRAS_POR_CADASTRO", "Amostras por cadastro",
          "Quantidade de embeddings capturados ao cadastrar alguém. Mais amostras = cadastro mais robusto "
          "a pose e iluminação, porém mais demorado.",
          "int", 5, 30, 1, 0, "Cadastro e qualidade"),
    Campo("INTERVALO_AMOSTRAS_SEG", "Intervalo entre amostras (s)",
          "Tempo entre duas capturas do cadastro. Precisa dar tempo de seguir a instrução de pose; "
          "intervalos curtos geram amostras quase iguais, todas de frente.",
          "float", 0.2, 3.0, 0.1, 1, "Cadastro e qualidade"),
    Campo("POSE_MAX_YAW", "Giro máximo do rosto (yaw)",
          "Razão nariz/olhos acima da qual o terminal pede para olhar para a câmera em vez de tentar "
          "reconhecer. Rostos de frente ficam abaixo de 0,45. Menor = mais exigente com a pose.",
          "float", 0.30, 1.20, 0.05, 2, "Pose para autenticar"),
    Campo("POSE_MAX_ROLL_GRAUS", "Inclinação máxima da cabeça (graus)",
          "Ângulo da linha dos olhos acima do qual o terminal pede para endireitar a cabeça. "
          "Rostos retos ficam abaixo de 20°.",
          "float", 10, 45, 1, 0, "Pose para autenticar"),
    Campo("POSE_RAZAO_NARIZ_MAX", "Cabeça baixa: razão máxima do nariz",
          "Posição do nariz entre os olhos (0) e a boca (1). Acima disso a cabeça está baixa demais e o "
          "terminal pede para levantar. De frente fica em 0,5 a 0,7.",
          "float", 0.65, 0.95, 0.01, 2, "Pose para autenticar"),
    Campo("POSE_RAZAO_NARIZ_MIN", "Cabeça erguida: razão mínima do nariz",
          "Abaixo disso a cabeça está erguida demais e o terminal pede para abaixar o queixo.",
          "float", 0.20, 0.50, 0.01, 2, "Pose para autenticar"),
    Campo("MIN_NITIDEZ", "Nitidez mínima",
          "Variância do Laplaciano abaixo da qual o rosto é tratado como borrado e descartado. Suba se "
          "estiver aceitando imagens ruins; desça se a câmera for de baixa qualidade.",
          "float", 10, 200, 1, 0, "Cadastro e qualidade"),
    Campo("CAMERA_INDEX", "Índice da câmera",
          "Qual dispositivo de vídeo abrir (0 = padrão do sistema). Mude se houver mais de uma câmera.",
          "int", 0, 5, 1, 0, "Câmera"),
    Campo("ESPELHAR_CAMERA", "Espelhar a imagem",
          "Exibe o vídeo como um espelho, mais natural para quem está na frente da câmera.",
          "bool", secao="Câmera"),
    Campo("SESSAO_LIBERADA_SEG", "Tempo da área liberada (s)",
          "Depois de um acesso concedido, a área fica aberta por este tempo sem interação antes de fechar "
          "sozinha e o terminal voltar a aguardar.",
          "int", 15, 600, 5, 0, "Câmera"),
    Campo("TEMPO_EXIBIR_RESULTADO_SEG", "Tempo do resultado na tela (s)",
          "Quanto tempo a decisão (concedido/negado) fica visível antes de o terminal voltar a aguardar.",
          "int", 1, 10, 1, 0, "Câmera"),
)

CAMPOS_POR_CHAVE: dict[str, Campo] = {c.chave: c for c in CAMPOS}


def caminho_arquivo() -> Path:
    """Arquivo de configuração do usuário (fica na pasta de dados, ignorado pelo Git)."""
    return Path(config.DATA_DIR) / ARQUIVO_CONFIG_NOME


def valores_atuais() -> dict[str, Any]:
    """Valores em vigor no módulo `cofre.config` para todos os campos."""
    return {c.chave: getattr(config, c.chave) for c in CAMPOS}


def normalizar_todos(valores: dict[str, Any]) -> dict[str, Any]:
    """Valida e limita todos os campos. Levanta ValueError/KeyError se faltar ou for inválido."""
    return {c.chave: c.normalizar(valores[c.chave]) for c in CAMPOS}


def aplicar(valores: dict[str, Any]) -> dict[str, Any]:
    """Valida tudo antes e só então grava em `cofre.config` (nada é aplicado pela metade)."""
    novos = normalizar_todos(valores)
    for chave, valor in novos.items():
        setattr(config, chave, valor)
    return novos


def ler_arquivo(caminho: Path | None = None) -> dict[str, Any]:
    """Lê o JSON e devolve só os parâmetros conhecidos, já normalizados."""
    caminho = caminho or caminho_arquivo()
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ValueError("o conteúdo precisa ser um objeto JSON com os nomes dos parâmetros")
    reconhecidos = {k: v for k, v in dados.items() if k in CAMPOS_POR_CHAVE}
    if not reconhecidos:
        raise ValueError("nenhum parâmetro conhecido no arquivo")
    return {k: CAMPOS_POR_CHAVE[k].normalizar(v) for k, v in reconhecidos.items()}


def salvar_arquivo(valores: dict[str, Any], caminho: Path | None = None) -> Path:
    caminho = Path(caminho or caminho_arquivo())
    novos = normalizar_todos(valores)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(novos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return caminho
