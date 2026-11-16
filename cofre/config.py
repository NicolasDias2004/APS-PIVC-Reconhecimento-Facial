"""Configurações centrais do sistema (caminhos, limiares e níveis de acesso)."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cofre.db"
FOTOS_DIR = DATA_DIR / "fotos"            # fotos de referência dos cadastrados
EVIDENCIAS_DIR = DATA_DIR / "evidencias"  # capturas de tentativas negadas
RELATORIOS_DIR = DATA_DIR / "relatorios"  # CSV/HTML gerados

MODELO_DETECCAO = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
MODELO_RECONHECIMENTO = MODELS_DIR / "face_recognition_sface_2021dec.onnx"

# ---------------------------------------------------------------------------
# Níveis de segurança (enunciado da APS)
# ---------------------------------------------------------------------------
NIVEIS = {
    1: "Permissão geral",
    2: "Diretor de divisão",
    3: "Ministro do Meio Ambiente",
}

# Áreas protegidas e o nível mínimo exigido para cada uma
AREAS = {
    1: "Área comum do Ministério",
    2: "Sala dos diretores de divisão",
    3: "Cofre de toxinas (exclusivo do Ministro)",
}

# ---------------------------------------------------------------------------
# Fase 1 - Aquisição
# ---------------------------------------------------------------------------
CAMERA_INDEX = 0
CAMERA_LARGURA = 1280
CAMERA_ALTURA = 720
ESPELHAR_CAMERA = True  # exibe como um espelho, mais natural para o usuário

# ---------------------------------------------------------------------------
# Fase 2 - Pré-processamento
# ---------------------------------------------------------------------------
CLAHE_CLIP = 2.0
CLAHE_GRADE = (8, 8)
GAUSS_KERNEL = (3, 3)
LARGURA_PROCESSAMENTO = 640   # frame reduzido para acelerar a detecção
MIN_NITIDEZ = 60.0            # variância do Laplaciano abaixo disso = borrado
MIN_BRILHO = 40.0             # média de intensidade abaixo disso = muito escuro
MAX_BRILHO = 220.0            # acima disso = estourado

# ---------------------------------------------------------------------------
# Fase 3 - Segmentação (detecção)
# ---------------------------------------------------------------------------
DETECCAO_SCORE_MIN = 0.85
DETECCAO_NMS = 0.3
DETECCAO_TOP_K = 50
TAMANHO_MIN_ROSTO = 80        # lado mínimo (px) do rosto no frame reduzido
# Pose aceitável para AUTENTICAR, medida pelos 5 pontos do YuNet. Fora disso o terminal pede
# "olhe para a câmera" e não tenta reconhecer: a tentativa não entra no log nem conta como
# falha para o bloqueio. Calibrado com 69 quadros reais: rostos de frente ficam com |yaw| < 0,45,
# |roll| < 20° e razão do nariz entre 0,45 e 0,70. Não se aplica à prova de vida (que pede o giro)
# nem ao cadastro (que pede as poses).
POSE_MAX_YAW = 0.60           # |nariz - meio dos olhos| / distância entre os olhos
POSE_MAX_ROLL_GRAUS = 25.0    # inclinação da linha dos olhos
POSE_RAZAO_NARIZ_MIN = 0.35   # (nariz - olhos) / (boca - olhos): abaixo = cabeça muito erguida
POSE_RAZAO_NARIZ_MAX = 0.80   # acima = cabeça muito baixa

# ---------------------------------------------------------------------------
# Fase 5 - Reconhecimento
# ---------------------------------------------------------------------------
# Limiar oficial recomendado pelo OpenCV para o modelo SFace (similaridade do cosseno).
# Acima do limiar = mesma pessoa.
LIMIAR_COSSENO = 0.363
# Margem extra para considerar "reconhecimento forte" (usada no HUD).
LIMIAR_COSSENO_FORTE = 0.50
# Quantidade de frames consecutivos com a MESMA identidade antes de decidir.
FRAMES_CONFIRMACAO = 6

# ---------------------------------------------------------------------------
# Cadastro
# ---------------------------------------------------------------------------
AMOSTRAS_POR_CADASTRO = 18
# Intervalo entre amostras. As 9 instruções de pose ocupam 2 amostras cada, então cada
# instrução fica 3 s na tela (1,5 s para reagir antes de cada captura); o cadastro leva ~27 s.
# Com 0,4 s a pose mudava a cada 0,8 s, rápido demais para acompanhar, e o cadastro saía
# quase todo de frente, reconhecendo pior com a cabeça virada.
INTERVALO_AMOSTRAS_SEG = 1.5

# ---------------------------------------------------------------------------
# Segurança / anti-fraude
# ---------------------------------------------------------------------------
LIVENESS_ATIVO = True
LIVENESS_LIMIAR_YAW = 0.22      # razão nariz/olhos para considerar a cabeça virada
LIVENESS_TIMEOUT_SEG = 12.0
MAX_TENTATIVAS_FALHAS = 3       # negações seguidas antes de bloquear
JANELA_FALHAS_SEG = 60.0
BLOQUEIO_SEG = 30.0
TEMPO_EXIBIR_RESULTADO_SEG = 3.0
# Área liberada (aplicativo Qt): tempo de inatividade até a sessão aberta pelo terminal fechar sozinha.
SESSAO_LIBERADA_SEG = 120
BLOQUEAR_MULTIPLOS_ROSTOS = True  # "carona" (tailgating): mais de um rosto = não autentica
