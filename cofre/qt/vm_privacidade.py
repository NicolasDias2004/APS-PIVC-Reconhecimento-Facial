"""Privacidade das telas de análise (v2): a chave "Mostrar nomes" e os rótulos de pessoa.

As telas novas abrem anônimas ("Pessoa A", "Pessoa B"...). O nome só aparece com a chave ligada,
que vale até fechar o aplicativo e nunca é gravada. Os rótulos são lidos do banco por
`rotulos_para`, sempre dentro do `Trabalho` de quem vai mostrar (nunca na thread da interface),
e viram texto com `rotulo_de`. Não há cache: cada recálculo lê de novo.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from .. import leitura_ro
from .base import ViewModel, prop

SEM_IDENTIDADE = "Sem identidade"
PESSOA_REMOVIDA = "Pessoa removida"


def rotulos_para(caminho_db, com_nomes: bool) -> dict[int, str]:
    """Rótulo de cada usuário do banco (ativos e inativos, para o rótulo não mudar com filtros).
    Lê o banco: chamar só dentro de um `Trabalho`."""
    if com_nomes:
        return leitura_ro.nomes(caminho_db)
    return leitura_ro.rotulos_anonimos(leitura_ro.ids_usuarios(caminho_db))


def rotulo_de(mapa: dict[int, str], usuario_id: int | None) -> str:
    if usuario_id is None:
        return SEM_IDENTIDADE
    return mapa.get(int(usuario_id), PESSOA_REMOVIDA)


class PrivacidadeVM(ViewModel):
    mostrarNomesMudou = Signal()

    mostrarNomes = prop(bool, "mostrarNomes", mostrarNomesMudou)      # False ao abrir; nunca gravado

    def __init__(self, aplicacao, parent=None):
        super().__init__(aplicacao, parent)
        self._iniciar(mostrarNomes=False)

    @Slot(bool)
    def definirMostrarNomes(self, ligado: bool) -> None:
        """Só troca a chave: quem mostra pessoas liga `mostrarNomesMudou` a `pedir_recarga`."""
        self._definir("mostrarNomes", bool(ligado))
