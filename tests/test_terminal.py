"""Máquina de estados do terminal de autenticação, alimentada com imagens (sem webcam)."""
import numpy as np

from cofre import config
from cofre.autenticacao import Estado, TerminalAutenticacao
from cofre.cadastro import DadosCadastro, cadastrar_de_imagens
from cofre.fase1_aquisicao import carregar_imagem
from cofre.fase5_reconhecimento import Resultado


def _terminal(banco, pipeline, fotos, nivel, liveness, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EVIDENCIAS_DIR", tmp_path / "ev")
    cadastrar_de_imagens(banco, pipeline, DadosCadastro("Obama", "001", "Ministro", 3), [fotos["obama"][0]])
    cadastrar_de_imagens(banco, pipeline, DadosCadastro("Biden", "002", "Diretor", 2), [fotos["biden"][0]])
    return TerminalAutenticacao(banco, pipeline, nivel_exigido=nivel, liveness=liveness)


def _alimentar(term, pipeline, frame, n):
    for _ in range(n):
        res = pipeline.processar(frame)
        term.passo(frame, res.principal, len(res.rostos))
        term.desenhar(frame, res, 30.0)  # HUD não pode quebrar em nenhum estado
    return res


def test_concede_apos_frames_de_confirmacao_sem_liveness(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 3, False, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO - 1)
    assert t.estado is Estado.CONFIRMANDO
    _alimentar(t, pipeline, frame, 1)
    assert t.estado is Estado.RESULTADO and t._decisao.concedido
    assert banco.listar_acessos()[0].resultado == "CONCEDIDO"


def test_nega_nivel_e_bloqueia_apos_tres_falhas(banco, pipeline, fotos, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TEMPO_EXIBIR_RESULTADO_SEG", 0.0)
    t = _terminal(banco, pipeline, fotos, 3, False, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["biden"][1])
    for i in range(3):
        _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO)
        assert t._decisao.resultado is Resultado.NEGADO_NIVEL
        _alimentar(t, pipeline, frame, 1)  # sai do estado RESULTADO
    assert t.estado is Estado.BLOQUEADO
    resultados = [a.resultado for a in banco.listar_acessos()]
    assert resultados[0] == "BLOQUEADO" and resultados.count("NEGADO_NIVEL") == 3
    assert any(a.evidencia for a in banco.listar_acessos())


def test_desconhecido_negado(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 1, False, tmp_path, monkeypatch)
    banco.remover_usuario(1); t.reconhecedor.recarregar()  # Obama deixa de existir
    _alimentar(t, pipeline, carregar_imagem(fotos["obama"][1]), config.FRAMES_CONFIRMACAO)
    assert t._decisao.resultado is Resultado.NEGADO_DESCONHECIDO


def test_liveness_exige_movimento(banco, pipeline, fotos, tmp_path, monkeypatch):
    from cofre.fase3_segmentacao import Rosto
    t = _terminal(banco, pipeline, fotos, 3, True, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO)
    assert t.estado is Estado.LIVENESS
    # foto parada: nunca passa
    _alimentar(t, pipeline, frame, 5)
    assert t.estado is Estado.LIVENESS
    # simula a cabeça virando: esquerda, direita, centro
    for yaw in (-0.4, 0.4, 0.0):
        monkeypatch.setattr(Rosto, "yaw", lambda self, y=yaw: y)
        _alimentar(t, pipeline, frame, 1)
    assert t.estado is Estado.RESULTADO and t._decisao.concedido


def test_sem_rosto_volta_a_aguardar(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 1, False, tmp_path, monkeypatch)
    _alimentar(t, pipeline, carregar_imagem(fotos["obama"][1]), 2)
    assert t.estado is Estado.CONFIRMANDO
    _alimentar(t, pipeline, np.zeros((480, 640, 3), np.uint8), 1)
    assert t.estado is Estado.AGUARDANDO and t.confirmador.progresso == 0


def test_prova_de_vida_exige_a_identidade_confirmada(banco, pipeline, fotos, tmp_path, monkeypatch):
    t = _terminal(banco, pipeline, fotos, 3, True, tmp_path, monkeypatch)
    frame = carregar_imagem(fotos["obama"][1])
    _alimentar(t, pipeline, frame, config.FRAMES_CONFIRMACAO)
    assert t.estado is Estado.LIVENESS

    outro_rosto = carregar_imagem(fotos["biden"][1])
    _alimentar(t, pipeline, outro_rosto, 1)

    assert t.estado is Estado.RESULTADO
    assert t.decisao_atual.resultado is Resultado.NEGADO_LIVENESS
    assert t.decisao_atual.identificacao is None
    assert [acesso.resultado for acesso in banco.listar_acessos()] == ["NEGADO_LIVENESS"]
