"""
Conteúdo das áreas protegidas, liberado depois de uma autenticação CONCEDIDA no terminal.

Os dados são fictícios e determinísticos (mesma semente → mesmo conteúdo), só para a
demonstração: nada aqui consulta sistemas reais. A regra de herança é a dos níveis do
sistema: quem tem nível N enxerga as áreas de nível 1 até N (`areas_liberadas`).

Este módulo não decide acesso. Quem decide é `fase5_reconhecimento.decidir_acesso`, no
terminal; aqui só se monta o que mostrar DEPOIS que o backend concedeu.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from . import config

DESCRICAO_AREA = {
    1: "Comunicados, agenda e indicadores públicos do Ministério.",
    2: "Orçamento, metas e aprovações das divisões.",
    3: "Inventário, sensores e registro de retiradas do cofre de toxinas.",
}


def areas_liberadas(nivel_usuario: int) -> list[int]:
    """Níveis de área que um usuário com `nivel_usuario` pode abrir (herança: N libera 1..N)."""
    return [n for n in sorted(config.NIVEIS) if n <= int(nivel_usuario)]


def resumo_areas(nivel_usuario: int) -> list[dict]:
    liberadas = set(areas_liberadas(nivel_usuario))
    return [{"nivel": n, "titulo": config.AREAS[n], "descricao": DESCRICAO_AREA.get(n, ""),
             "liberada": n in liberadas} for n in sorted(config.NIVEIS)]


def conteudo(nivel: int, hoje: date | None = None) -> dict:
    """Conteúdo fictício da área de nível `nivel`. Levanta ValueError para nível inexistente."""
    nivel = int(nivel)
    if nivel not in config.NIVEIS:
        raise ValueError(f"Área inexistente: {nivel}")
    hoje = hoje or date.today()
    return {1: _area_comum, 2: _area_diretores, 3: _area_cofre}[nivel](hoje)


# --------------------------------------------------------------------------- nível 1
def _area_comum(hoje: date) -> dict:
    r = random.Random(101)
    dias = [hoje - timedelta(days=6 - i) for i in range(7)]
    base = 38
    qualidade = []
    for d in dias:
        base = max(18, min(95, base + r.randint(-9, 9)))
        qualidade.append({"dia": d.strftime("%d/%m"), "valor": base})
    return {
        "titulo": config.AREAS[1],
        "comunicados": [
            {"tipo": "aviso", "data": (hoje - timedelta(days=0)).strftime("%d/%m"),
             "titulo": "Manutenção do sistema de climatização no bloco B",
             "texto": "Entre 13h e 15h o 3º andar ficará sem climatização. Reuniões podem usar as salas do bloco A."},
            {"tipo": "info", "data": (hoje - timedelta(days=1)).strftime("%d/%m"),
             "titulo": "Semana do Meio Ambiente: inscrições abertas",
             "texto": "Oficinas de compostagem e de coleta seletiva no auditório. Vagas limitadas por setor."},
            {"tipo": "info", "data": (hoje - timedelta(days=2)).strftime("%d/%m"),
             "titulo": "Novo cardápio do restaurante",
             "texto": "Opção vegetariana diária a partir de segunda. Sugestões pelo ramal 4120."},
            {"tipo": "ok", "data": (hoje - timedelta(days=4)).strftime("%d/%m"),
             "titulo": "Credenciais do estacionamento renovadas",
             "texto": "As credenciais de 2026 já valem nas cancelas. As antigas expiram no fim do mês."},
        ],
        "agenda": [
            {"hora": "09:00", "titulo": "Café com a Secretaria de Biodiversidade", "local": "Sala 204"},
            {"hora": "10:30", "titulo": "Treinamento: SEI para iniciantes", "local": "Laboratório 1"},
            {"hora": "14:00", "titulo": "Reunião geral do Departamento de Florestas", "local": "Auditório"},
            {"hora": "16:30", "titulo": "Plantão de dúvidas de RH", "local": "Sala 110"},
        ],
        "indicadores": [
            {"nome": "Focos de queimada (24 h)", "valor": "1.284", "variacao": -12, "unidade": "focos"},
            {"nome": "Unidades de conservação", "valor": "335", "variacao": 2, "unidade": "federais"},
            {"nome": "Alertas de desmatamento", "valor": "412", "variacao": -8, "unidade": "km² no mês"},
            {"nome": "Qualidade do ar (DF)", "valor": str(qualidade[-1]["valor"]), "variacao": qualidade[-1]["valor"] - qualidade[-2]["valor"], "unidade": "IQAr"},
        ],
        "qualidadeAr": qualidade,
        "ramais": [
            {"setor": "Recepção", "ramal": "4000"}, {"setor": "Protocolo", "ramal": "4015"},
            {"setor": "Recursos Humanos", "ramal": "4100"}, {"setor": "Suporte de TI", "ramal": "4200"},
            {"setor": "Segurança", "ramal": "4300"}, {"setor": "Restaurante", "ramal": "4120"},
        ],
    }


# --------------------------------------------------------------------------- nível 2
def _area_diretores(hoje: date) -> dict:
    r = random.Random(202)
    divisoes = []
    for nome, orcamento in (("Florestas", 48.2), ("Biodiversidade", 36.9), ("Recursos Hídricos", 29.4),
                            ("Qualidade Ambiental", 22.7), ("Educação Ambiental", 11.3)):
        exec_ = round(orcamento * r.uniform(0.42, 0.88), 1)
        divisoes.append({"nome": nome, "orcamento": orcamento, "executado": exec_,
                         "fracao": round(exec_ / orcamento, 3), "meta": r.randint(68, 94),
                         "servidores": r.randint(38, 160)})
    prioridades = ["alta", "média", "baixa"]
    aprovacoes = []
    assuntos = [("Licença de operação: hidrelétrica do Rio Claro", "Divisão de Recursos Hídricos"),
                ("Plano de manejo da Floresta Nacional de Ipanema", "Divisão de Florestas"),
                ("Convênio com universidades para monitoramento de fauna", "Divisão de Biodiversidade"),
                ("Compra de sensores de qualidade do ar", "Divisão de Qualidade Ambiental"),
                ("Edital de educação ambiental nas escolas", "Divisão de Educação Ambiental"),
                ("Contratação de brigadistas para a estação seca", "Divisão de Florestas")]
    for i, (assunto, origem) in enumerate(assuntos):
        aprovacoes.append({"id": f"SEI-{2026}-{10400 + i * 37}", "assunto": assunto, "origem": origem,
                           "prazo": (hoje + timedelta(days=r.randint(1, 20))).strftime("%d/%m"),
                           "prioridade": prioridades[i % 3], "valor": f"R$ {r.uniform(0.3, 9.8):.1f} mi"})
    total_orc = sum(d["orcamento"] for d in divisoes)
    total_exec = sum(d["executado"] for d in divisoes)
    return {
        "titulo": config.AREAS[2],
        "resumo": {"orcamento": f"R$ {total_orc:.1f} mi", "executado": f"R$ {total_exec:.1f} mi",
                   "fracao": round(total_exec / total_orc, 3), "aprovacoesPendentes": len(aprovacoes),
                   "divisoes": len(divisoes)},
        "divisoes": divisoes,
        "aprovacoes": aprovacoes,
        "metas": [{"nome": "Área reflorestada", "atual": 1.84, "alvo": 2.5, "unidade": "mil ha"},
                  {"nome": "Licenças analisadas no prazo", "atual": 81, "alvo": 90, "unidade": "%"},
                  {"nome": "Municípios com coleta seletiva", "atual": 1372, "alvo": 1600, "unidade": ""},
                  {"nome": "Unidades com plano de manejo", "atual": 212, "alvo": 335, "unidade": ""}],
    }


# --------------------------------------------------------------------------- nível 3
def _area_cofre(hoje: date) -> dict:
    r = random.Random(303)
    agentes = [("Tetrodotoxina", "Marinha", "crítico"), ("Batracotoxina", "Anfíbios", "crítico"),
               ("Ricina", "Vegetal", "alto"), ("Crotoxina", "Serpentes", "alto"),
               ("Microcistina-LR", "Cianobactérias", "moderado"), ("Palitoxina", "Corais", "crítico"),
               ("Abrina", "Vegetal", "alto"), ("Saxitoxina", "Dinoflagelados", "alto")]
    lotes = []
    for i, (agente, origem, risco) in enumerate(agentes):
        lotes.append({"codigo": f"TX-{2600 + i * 13:04d}", "agente": agente, "origem": origem, "risco": risco,
                      "quantidade": f"{r.uniform(0.2, 12.0):.1f}", "unidade": "mg",
                      "validade": (hoje + timedelta(days=r.randint(40, 700))).strftime("%d/%m/%Y"),
                      "prateleira": f"{'ABCD'[i % 4]}{i // 4 + 1}"})
    temperatura, t = [], -78.0
    for h in range(24):
        t = max(-82.0, min(-74.0, t + r.uniform(-0.6, 0.6)))
        temperatura.append({"hora": f"{(datetime.now().hour - 23 + h) % 24:02d}h", "valor": round(t, 1)})
    retiradas = [
        {"data": (hoje - timedelta(days=d)).strftime("%d/%m"), "lote": lotes[i]["codigo"], "agente": lotes[i]["agente"],
         "responsavel": nome, "finalidade": fim, "quantidade": f"{q:.1f} mg"}
        for d, i, nome, fim, q in ((2, 0, "Lab. de Toxinologia", "Antiveneno experimental", 0.4),
                                   (9, 3, "Instituto Butantan", "Padrão de referência", 1.0),
                                   (17, 4, "Lab. de Qualidade da Água", "Calibração de ensaio", 0.2),
                                   (31, 2, "Perícia Federal", "Contraprova", 0.5))]
    return {
        "titulo": config.AREAS[3],
        "sensores": [
            {"nome": "Temperatura", "valor": f"{temperatura[-1]['valor']:.1f}", "unidade": "°C", "faixa": "-82 a -74", "ok": True},
            {"nome": "Umidade", "valor": "31", "unidade": "%", "faixa": "20 a 40", "ok": True},
            {"nome": "Pressão interna", "valor": "-12", "unidade": "Pa", "faixa": "-20 a -5", "ok": True},
            {"nome": "Filtro HEPA", "valor": "94", "unidade": "%", "faixa": "≥ 85", "ok": True},
        ],
        "temperatura": temperatura,
        "lotes": lotes,
        "retiradas": retiradas,
        "portas": [{"nome": "Antecâmara", "estado": "fechada"}, {"nome": "Câmara fria", "estado": "fechada"},
                   {"nome": "Armário de contenção", "estado": "lacrado"}, {"nome": "Exaustão", "estado": "ativa"}],
        "totais": {"lotes": len(lotes), "criticos": sum(1 for l in lotes if l["risco"] == "crítico"),
                   "retiradas30d": sum(1 for x in retiradas if True), "vencendo": sum(1 for l in lotes if int(l["validade"][6:]) == hoje.year)},
    }
