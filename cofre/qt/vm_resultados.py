"""Página Resultados (v2): só a troca entre as abas Separação, Qualidade e Galeria."""

from __future__ import annotations

from .base_v2 import PaginaAbasVM


class ResultadosVM(PaginaAbasVM):
    CHAVE = "resultados"
