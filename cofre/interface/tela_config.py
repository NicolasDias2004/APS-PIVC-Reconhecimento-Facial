"""
Tela "Configurações": formulário que lê e grava, em tempo de execução, os valores
do módulo `cofre.config` (via `setattr`), com persistência opcional em JSON
(`config.DATA_DIR / "config_usuario.json"`) e uma seção informativa (caminhos,
versões, modelos, níveis e áreas).

Observação importante sobre o efeito das alterações: os objetos do sistema leem
`config` de duas formas. Alguns leem no momento do uso (ex.: `Identificacao.reconhecido`
lê `config.LIMIAR_COSSENO` a cada frame) e por isso mudam na hora. Outros leem ao serem
construídos (`Confirmador`, `DesafioMovimento`, `ControleTentativas`, `FonteCamera`,
`SessaoCadastro`) e só enxergam o valor novo quando a tela de câmera cria um objeto
novo, ou seja, na próxima sessão de câmera.
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk
import cv2

from .. import __version__, config
from ..fase1_aquisicao import FonteCamera
from . import tema
from .base import Tela
from .widgets import Faixa, Tabela, botao, botao_secundario, titulo

from ..parametros import ARQUIVO_CONFIG_NOME, CAMPOS, CAMPOS_POR_CHAVE, MENSAGEM_APLICADO, Campo  # noqa: F401



class _LinhaCampo(ctk.CTkFrame):
    """Uma linha do formulário: rótulo + explicação à esquerda, controle + valor à direita."""

    def __init__(self, master, campo: Campo, ao_mudar: Callable[[str, Any], None]):
        super().__init__(master, fg_color=tema.CARTAO, corner_radius=10)
        self.campo = campo
        self._ao_mudar = ao_mudar
        self._silencio = False
        self.grid_columnconfigure(0, weight=1)
        textos = ctk.CTkFrame(self, fg_color="transparent")
        textos.grid(row=0, column=0, sticky="nsew", padx=(16, 12), pady=12)
        ctk.CTkLabel(textos, text=campo.rotulo, font=tema.SUBTITULO, text_color=tema.TEXTO, anchor="w").pack(fill="x")
        ctk.CTkLabel(textos, text=campo.explicacao, font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w",
                     justify="left", wraplength=520).pack(fill="x", pady=(2, 0))
        controle = ctk.CTkFrame(self, fg_color="transparent", width=300)
        controle.grid(row=0, column=1, sticky="e", padx=(0, 16), pady=12)
        self.valor_lbl = ctk.CTkLabel(controle, text="", font=tema.MONO, text_color=tema.ACENTO, width=70,
                                      anchor="e")
        if campo.tipo == "bool":
            self.switch = ctk.CTkSwitch(controle, text="", width=60, command=self._mudou,
                                        progress_color=tema.ACENTO, button_color=tema.TEXTO)
            self.switch.pack(side="right")
            self.valor_lbl.pack(side="right", padx=(0, 8))
            self.slider = None
        else:
            self.switch = None
            passos = int(round((campo.maximo - campo.minimo) / campo.passo))
            self.slider = ctk.CTkSlider(controle, from_=campo.minimo, to=campo.maximo, number_of_steps=max(1, passos),
                                        width=220, command=self._mudou, progress_color=tema.ACENTO,
                                        button_color=tema.ACENTO, button_hover_color=tema.ACENTO_HOVER)
            self.valor_lbl.pack(side="right", padx=(8, 0))
            self.slider.pack(side="right")
            ctk.CTkLabel(controle, text=f"{campo.formatar(campo.minimo)} a {campo.formatar(campo.maximo)}",
                         font=tema.PEQUENO, text_color=tema.TEXTO_2).pack(side="right", padx=(0, 8))

    def definir(self, valor: Any) -> None:
        """Atualiza o controle sem disparar o callback."""
        self._silencio = True
        try:
            if self.switch is not None:
                (self.switch.select if valor else self.switch.deselect)()
            else:
                self.slider.set(float(valor))
            self.valor_lbl.configure(text=self.campo.formatar(valor))
        finally:
            self._silencio = False

    def _mudou(self, *_: Any) -> None:
        if self._silencio:
            return
        if self.switch is not None:
            valor = bool(self.switch.get())
        else:
            valor = self.campo.normalizar(self.slider.get())
        self.valor_lbl.configure(text=self.campo.formatar(valor))
        self._ao_mudar(self.campo.chave, valor)


class TelaConfig(Tela):
    """Formulário de configurações em tempo de execução + informações do sistema."""

    TITULO = "Configurações"

    # ------------------------------------------------------------------ construção
    def construir(self) -> None:
        # Valores originais do módulo, capturados ANTES de qualquer carregamento de arquivo.
        self.padroes: dict[str, Any] = {c.chave: getattr(config, c.chave) for c in CAMPOS}
        self._valores: dict[str, Any] = dict(self.padroes)
        self._linhas: dict[str, _LinhaCampo] = {}
        self._pendente_msg: tuple[str, str] | None = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        titulo(self, self.TITULO, "Ajuste os parâmetros do sistema sem reiniciar. Aplicar grava no módulo "
               "cofre.config; Salvar guarda em arquivo para as próximas execuções.").grid(
            row=0, column=0, sticky="ew", padx=24, pady=(24, 12))

        self.corpo = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.corpo.grid(row=1, column=0, sticky="nsew", padx=(24, 12))
        self.corpo.grid_columnconfigure(0, weight=1)
        self._construir_formulario(self.corpo)
        self._construir_informacoes(self.corpo)

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.grid(row=2, column=0, sticky="ew", padx=24, pady=(12, 24))
        rodape.grid_columnconfigure(0, weight=1)
        self.mensagem = Faixa(rodape)
        self.mensagem.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        botoes = ctk.CTkFrame(rodape, fg_color="transparent")
        botoes.grid(row=1, column=0, sticky="ew")
        self.btn_aplicar = botao(botoes, "Aplicar", self.aplicar, width=140)
        self.btn_aplicar.pack(side="left")
        self.btn_restaurar = botao_secundario(botoes, "Restaurar padrões", self.restaurar_padroes, width=160)
        self.btn_restaurar.pack(side="left", padx=(12, 0))
        self.btn_carregar = botao_secundario(botoes, "Carregar de arquivo", self.carregar_arquivo, width=170)
        self.btn_carregar.pack(side="right")
        self.btn_salvar = botao_secundario(botoes, "Salvar em arquivo", self.salvar_arquivo, width=160)
        self.btn_salvar.pack(side="right", padx=(0, 12))

        self._ligar_camera_na_config()
        self._carregar_inicial()
        self._atualizar_controles()

    def _construir_formulario(self, pai) -> None:
        secao_atual = None
        linha = 0
        for campo in CAMPOS:
            if campo.secao != secao_atual:
                secao_atual = campo.secao
                ctk.CTkLabel(pai, text=campo.secao, font=tema.SUBTITULO, text_color=tema.ACENTO, anchor="w").grid(
                    row=linha, column=0, sticky="ew", pady=(12 if linha else 0, 6))
                linha += 1
            w = _LinhaCampo(pai, campo, self._campo_mudou)
            w.grid(row=linha, column=0, sticky="ew", pady=(0, 8))
            self._linhas[campo.chave] = w
            linha += 1
        self._proxima_linha = linha

    def _construir_informacoes(self, pai) -> None:
        linha = self._proxima_linha
        ctk.CTkLabel(pai, text="Informações do sistema", font=tema.SUBTITULO, text_color=tema.ACENTO, anchor="w").grid(
            row=linha, column=0, sticky="ew", pady=(24, 6))
        linha += 1
        cartao = ctk.CTkFrame(pai, fg_color=tema.CARTAO, corner_radius=10)
        cartao.grid(row=linha, column=0, sticky="ew", pady=(0, 8))
        cartao.grid_columnconfigure(1, weight=1)
        infos = self.informacoes()
        for i, (nome, valor) in enumerate(infos):
            pady = (12 if i == 0 else 2, 12 if i == len(infos) - 1 else 2)
            ctk.CTkLabel(cartao, text=nome, font=tema.PEQUENO, text_color=tema.TEXTO_2, anchor="w", width=190).grid(
                row=i, column=0, sticky="nw", padx=(16, 8), pady=pady)
            ctk.CTkLabel(cartao, text=valor, font=tema.MONO, text_color=tema.TEXTO, anchor="w", justify="left",
                         wraplength=760).grid(row=i, column=1, sticky="w", padx=(0, 16), pady=pady)
        linha += 1
        ctk.CTkLabel(pai, text="Níveis de acesso e áreas protegidas", font=tema.SUBTITULO, text_color=tema.ACENTO,
                     anchor="w").grid(row=linha, column=0, sticky="ew", pady=(16, 6))
        linha += 1
        self.tabela_niveis = Tabela(pai, [("nivel", "Nível", 70), ("nome", "Permissão", 260),
                                          ("area", "Área liberada (nível mínimo)", 420)], altura=max(1, len(config.NIVEIS)))
        self.tabela_niveis.grid(row=linha, column=0, sticky="ew", pady=(0, 8))
        for n in sorted(config.NIVEIS):
            self.tabela_niveis.adicionar(str(n), (n, config.NIVEIS[n], config.AREAS.get(n, "-")))

    # ------------------------------------------------------------------ informações
    def informacoes(self) -> list[tuple[str, str]]:
        """Pares (nome, valor) exibidos na seção informativa."""
        def arquivo(p: Path) -> str:
            try:
                return f"{p}  ({p.stat().st_size / 1024:.0f} KB)" if p.exists() else f"{p}  (NÃO ENCONTRADO)"
            except OSError:
                return str(p)
        banco = getattr(self.app, "banco", None)
        caminho_db = getattr(banco, "caminho", config.DB_PATH)
        return [
            ("Banco de dados", str(caminho_db)),
            ("Pasta de dados", str(config.DATA_DIR)),
            ("Fotos / evidências / relatórios", f"{config.FOTOS_DIR}\n{config.EVIDENCIAS_DIR}\n{config.RELATORIOS_DIR}"),
            ("Arquivo de configuração", str(self.caminho_arquivo)),
            ("Modelo de detecção (YuNet)", arquivo(config.MODELO_DETECCAO)),
            ("Modelo de reconhecimento (SFace)", arquivo(config.MODELO_RECONHECIMENTO)),
            ("Dimensões dos modelos", f"YuNet: entrada ajustada ao frame reduzido ({config.LARGURA_PROCESSAMENTO} px de largura), "
                                     f"padrão 320x320\nSFace: rosto alinhado 112x112 -> embedding de 128 dimensões"),
            ("Captura", f"{config.CAMERA_LARGURA}x{config.CAMERA_ALTURA}, processamento em {config.LARGURA_PROCESSAMENTO} px"),
            ("OpenCV", cv2.__version__),
            ("customtkinter / Python", f"{ctk.__version__} / {platform.python_version()} ({sys.platform})"),
            ("Versão do aplicativo", __version__),
        ]

    # ------------------------------------------------------------------ valores
    @property
    def caminho_arquivo(self) -> Path:
        return Path(config.DATA_DIR) / ARQUIVO_CONFIG_NOME

    def valores(self) -> dict[str, Any]:
        """Valores atualmente no formulário (ainda não necessariamente aplicados)."""
        return dict(self._valores)

    def definir(self, chave: str, valor: Any) -> None:
        """Define um campo do formulário (valida e limita ao intervalo). Não aplica no módulo."""
        campo = CAMPOS_POR_CHAVE[chave]
        self._valores[chave] = campo.normalizar(valor)
        if chave in self._linhas:
            self._linhas[chave].definir(self._valores[chave])

    def _campo_mudou(self, chave: str, valor: Any) -> None:
        self._valores[chave] = valor
        self.mensagem.definir("Alterações pendentes: clique em Aplicar", tema.CARTAO, tema.LARANJA)

    def _atualizar_controles(self) -> None:
        for chave, w in self._linhas.items():
            w.definir(self._valores[chave])

    # ------------------------------------------------------------------ ações
    def aplicar(self) -> bool:
        """Valida e grava os valores do formulário no módulo `cofre.config`."""
        try:
            novos = {c.chave: c.normalizar(self._valores[c.chave]) for c in CAMPOS}
        except (ValueError, KeyError) as e:
            self._erro(f"Valor inválido: {e}")
            return False
        for chave, valor in novos.items():
            setattr(config, chave, valor)
        self._valores = novos
        self._atualizar_controles()
        self._ligar_camera_na_config()
        self.mensagem.definir(MENSAGEM_APLICADO, tema.CARTAO, tema.VERDE)
        self.app.status.definir("Configurações aplicadas", None)
        return True

    def restaurar_padroes(self) -> None:
        """Volta o formulário aos valores originais do módulo (não aplica; clique em Aplicar)."""
        self._valores = dict(self.padroes)
        self._atualizar_controles()
        self.mensagem.definir("Padrões restaurados no formulário. Clique em Aplicar para valer.", tema.CARTAO,
                              tema.LARANJA)

    def salvar_arquivo(self) -> bool:
        """Grava os valores do formulário em `config.DATA_DIR/config_usuario.json`."""
        try:
            novos = {c.chave: c.normalizar(self._valores[c.chave]) for c in CAMPOS}
            caminho = self.caminho_arquivo
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(json.dumps(novos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except (OSError, ValueError, KeyError) as e:
            self._erro(f"Não foi possível salvar o arquivo: {e}")
            return False
        self.mensagem.definir(f"Salvo em {caminho}. Será carregado automaticamente ao abrir esta tela.",
                              tema.CARTAO, tema.VERDE)
        return True

    def carregar_arquivo(self) -> bool:
        """Lê o JSON de `config.DATA_DIR/config_usuario.json`, preenche o formulário e aplica."""
        caminho = self.caminho_arquivo
        if not caminho.exists():
            self._erro(f"Arquivo não encontrado: {caminho}")
            return False
        try:
            self._ler_arquivo(caminho)
        except (OSError, ValueError, TypeError) as e:
            self._erro(f"Arquivo inválido ({caminho.name}): {e}")
            return False
        if self.aplicar():
            self.mensagem.definir(f"Carregado de {caminho.name} e aplicado. {MENSAGEM_APLICADO}", tema.CARTAO, tema.VERDE)
            return True
        return False

    # ------------------------------------------------------------------ internos
    def _ler_arquivo(self, caminho: Path) -> None:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(dados, dict):
            raise ValueError("o conteúdo precisa ser um objeto JSON com os nomes dos parâmetros")
        reconhecidos = {k: v for k, v in dados.items() if k in CAMPOS_POR_CHAVE}
        if not reconhecidos:
            raise ValueError("nenhum parâmetro conhecido no arquivo")
        normalizados = {k: CAMPOS_POR_CHAVE[k].normalizar(v) for k, v in reconhecidos.items()}
        self._valores.update(normalizados)
        self._atualizar_controles()

    def _carregar_inicial(self) -> None:
        """Ao abrir a tela: se o arquivo do usuário existir, carrega e aplica (sem estourar exceção)."""
        caminho = self.caminho_arquivo
        try:
            if not caminho.exists():
                self.mensagem.definir("Valores atuais do módulo cofre.config (nenhum arquivo de usuário salvo).",
                                      tema.CARTAO, tema.TEXTO_2)
                return
            self._ler_arquivo(caminho)
            novos = {c.chave: c.normalizar(self._valores[c.chave]) for c in CAMPOS}
            for chave, valor in novos.items():
                setattr(config, chave, valor)
            self._valores = novos
            self.mensagem.definir(f"Configuração carregada de {caminho.name} e aplicada.", tema.CARTAO, tema.VERDE)
        except (OSError, ValueError, TypeError, KeyError) as e:
            self._erro(f"Arquivo {caminho.name} ignorado: {e}")

    def _ligar_camera_na_config(self) -> None:
        """`FonteCamera()` fixa índice/espelho nos defaults de importação; a fábrica passa a ler `config`
        a cada abertura. Só mexe quando a fábrica é a padrão (os testes usam uma câmera falsa)."""
        cam = getattr(self.app, "camera", None)
        if cam is not None and getattr(cam, "fonte_fabrica", None) is FonteCamera:
            cam.fonte_fabrica = lambda: FonteCamera(config.CAMERA_INDEX, config.ESPELHAR_CAMERA)

    def _erro(self, texto: str) -> None:
        self.mensagem.definir(texto, tema.CARTAO, tema.VERMELHO)

    # ------------------------------------------------------------------ ciclo
    def ao_mostrar(self) -> None:
        self.app.status.definir(None, f"arquivo: {self.caminho_arquivo.name}"
                                      f"{'' if self.caminho_arquivo.exists() else ' (não existe)'}")
