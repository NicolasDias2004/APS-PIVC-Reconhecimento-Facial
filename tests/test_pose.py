"""Filtro de pose do terminal (pelos 5 pontos do detector) e as 9 poses do cadastro.

Regra: entrada que não serve (rosto virado, inclinado, cabeça baixa/erguida, borrado) é ignorada
pelo terminal: nada é decidido, nada entra no log e nada conta para o bloqueio. A prova de vida,
que pede o giro da cabeça, não passa pelo filtro."""
import numpy as np

from cofre import config
from cofre.autenticacao import Estado, TerminalAutenticacao
from cofre.cadastro import INSTRUCOES_POSE, DadosCadastro, SessaoCadastro, cadastrar_de_imagens
from cofre.fase1_aquisicao import carregar_imagem
from cofre.fase3_segmentacao import Rosto, rosto_de_linha


def _rosto(olho_dir=(40, 40), olho_esq=(80, 40), nariz=(60, 62), boca_dir=(45, 85), boca_esq=(75, 85)) -> Rosto:
    linha = np.array([20, 10, 80, 100, *olho_dir, *olho_esq, *nariz, *boca_dir, *boca_esq, 0.95], np.float32)
    return rosto_de_linha(linha)


def test_medidas_de_pose_e_limites():
    frontal = _rosto()
    assert abs(frontal.yaw()) < 0.01 and abs(frontal.roll()) < 0.01 and 0.45 < frontal.razao_nariz() < 0.55
    assert frontal.problema_pose() == ""
    assert "Vire o rosto" in _rosto(nariz=(100, 62)).problema_pose()            # yaw 1,0
    assert "Endireite" in _rosto(olho_esq=(80, 70)).problema_pose()             # roll ~37°
    assert "Levante a cabeça" in _rosto(nariz=(60, 80)).problema_pose()          # nariz perto da boca
    assert "Abaixe o queixo" in _rosto(nariz=(60, 50)).problema_pose()           # nariz perto dos olhos
    # os limites são lidos de config na hora (ajustáveis na tela de configurações)
    assert _rosto(nariz=(72, 62)).problema_pose() == ""                           # yaw 0,3
    antes = config.POSE_MAX_YAW
    try:
        config.POSE_MAX_YAW = 0.2
        assert "Vire o rosto" in _rosto(nariz=(72, 62)).problema_pose()
    finally:
        config.POSE_MAX_YAW = antes


def _terminal(banco, pipeline, fotos, nivel, liveness, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EVIDENCIAS_DIR", tmp_path / "ev")
    cadastrar_de_imagens(banco, pipeline, DadosCadastro("Obama", "001", "Ministro", 3), [fotos["obama"][0]])
    return TerminalAutenticacao(banco, pipeline, nivel_exigido=nivel, liveness=liveness)


def _alimentar(term, pipeline, frame, n):
    for _ in range(n):
        res = pipeline.processar(frame)
        term.passo(frame, res.principal, len(res.rostos))
        term.desenhar(frame, res, 30.0)
    return res


def test_pose_ruim_nao_tenta_nem_conta_falha(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 3, False, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    monkeypatch.setattr(Rosto, "problema_pose", lambda self: "Vire o rosto para a câmera")
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO + 3)
    assert t.estado is Estado.AGUARDANDO and t.confirmador.progresso == 0
    assert t.status()["orientacao"] == "Vire o rosto para a câmera"
    assert banco.listar_acessos() == [] and not t.tentativas.bloqueado and t.tentativas._falhas == []
    # pose corrigida: volta a funcionar normalmente
    monkeypatch.undo()
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO)
    assert t.estado is Estado.RESULTADO and t._decisao.concedido and t.status()["orientacao"] == ""


def test_imagem_borrada_nao_tenta(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 3, False, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    monkeypatch.setattr(config, "MIN_NITIDEZ", 1e9)
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO + 1)
    assert t.estado is Estado.AGUARDANDO and "borrada" in t.status()["orientacao"]
    assert banco.listar_acessos() == []


def test_prova_de_vida_nao_passa_pelo_filtro(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 3, True, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO)
    assert t.estado is Estado.LIVENESS
    # girar a cabeça para o desafio deixa o rosto "fora da pose": o desafio continua mesmo assim
    monkeypatch.setattr(Rosto, "problema_pose", lambda self: "Vire o rosto para a câmera")
    for yaw in (-0.9, 0.9, 0.0):
        monkeypatch.setattr(Rosto, "yaw", lambda self, y=yaw: y)
        _alimentar(t, pipeline, frame, 1)
        assert t.status()["orientacao"] == ""
    assert t.estado is Estado.RESULTADO and t._decisao.concedido


def test_cadastro_percorre_as_nove_poses(banco, pipeline, fotos, monkeypatch):
    assert len(INSTRUCOES_POSE) == 9 and config.AMOSTRAS_POR_CADASTRO == 18
    monkeypatch.setattr(config, "INTERVALO_AMOSTRAS_SEG", 0.0)
    s = SessaoCadastro(banco, pipeline, DadosCadastro("Obama", "001", "", 3), amostras=18)
    frame = carregar_imagem(fotos["obama"][1])
    vistas = []
    while not s.concluida:
        res = pipeline.processar(frame)
        s.passo(frame, res)
        vistas.append(s.pose)
    assert s.capturadas == 18 and [vistas.count(p) for p in INSTRUCOES_POSE] == [2] * 9
    assert vistas == [p for p in INSTRUCOES_POSE for _ in (0, 1)]
    s.cancelar()
