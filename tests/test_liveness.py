"""Anti-fraude: desafio de movimento, bloqueio por tentativas e confirmador de frames."""
from cofre.liveness import ControleTentativas, DesafioMovimento, EtapaLiveness


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_desafio_aprova_esquerda_direita_centro():
    rl = Relogio()
    d = DesafioMovimento(limiar=0.2, timeout=10, relogio=rl)
    d.iniciar()
    assert d.atualizar(0.0) is EtapaLiveness.VIRAR_ESQUERDA
    assert d.atualizar(-0.3) is EtapaLiveness.VIRAR_DIREITA
    assert d.atualizar(-0.3) is EtapaLiveness.VIRAR_DIREITA   # ainda virado p/ esquerda
    assert d.atualizar(0.35) is EtapaLiveness.VOLTAR_CENTRO
    assert d.atualizar(0.02) is EtapaLiveness.APROVADO
    assert not d.ativo


def test_desafio_falha_por_timeout_e_ignora_none():
    rl = Relogio()
    d = DesafioMovimento(limiar=0.2, timeout=5, relogio=rl)
    d.iniciar()
    assert d.atualizar(None) is EtapaLiveness.VIRAR_ESQUERDA
    rl.t = 6
    assert d.atualizar(-0.5) is EtapaLiveness.FALHOU


def test_foto_estatica_nao_passa():
    rl = Relogio()
    d = DesafioMovimento(limiar=0.2, timeout=5, relogio=rl)
    d.iniciar()
    for _ in range(50):
        d.atualizar(0.01)
    assert d.etapa is EtapaLiveness.VIRAR_ESQUERDA


def test_bloqueio_apos_tres_falhas_e_expira():
    rl = Relogio()
    c = ControleTentativas(max_falhas=3, janela=60, bloqueio=30, relogio=rl)
    assert not c.registrar_falha() and not c.registrar_falha()
    assert c.registrar_falha() and c.bloqueado
    rl.t = 31
    assert not c.bloqueado
    c.registrar_falha(); c.registrar_sucesso(); c.registrar_falha(); c.registrar_falha()
    assert not c.bloqueado  # sucesso zera a contagem


def test_falhas_fora_da_janela_nao_contam():
    rl = Relogio()
    c = ControleTentativas(max_falhas=3, janela=10, bloqueio=30, relogio=rl)
    c.registrar_falha(); rl.t = 20; c.registrar_falha(); rl.t = 21
    assert not c.registrar_falha()


def test_confirmador_exige_identidade_estavel():
    from cofre.autenticacao import Confirmador
    from cofre.banco import Usuario
    from cofre.fase5_reconhecimento import Identificacao
    u1 = Usuario(1, "A", "a", "", 1, True, ""); u2 = Usuario(2, "B", "b", "", 1, True, "")
    c = Confirmador(3)
    assert c.adicionar(Identificacao(u1, 0.8)) is None
    assert c.adicionar(Identificacao(u2, 0.8)) is None
    assert c.adicionar(Identificacao(u1, 0.8)) is None     # misturou identidades
    assert c.adicionar(Identificacao(u1, 0.6)) is None
    r = c.adicionar(Identificacao(u1, 0.7))
    assert r is not None and r.usuario.id == 1 and abs(r.similaridade - 0.7) < 1e-6
    c.limpar()
    for _ in range(3):
        r = c.adicionar(Identificacao(None, 0.1))
    assert r is not None and not r.reconhecido
