"""Aplicativo desktop (customtkinter) do sistema de autenticação biométrica.

Estrutura:
  app.py            janela principal, barra lateral e troca de telas
  camera.py         serviço de câmera em thread (captura + pipeline)
  widgets.py        VideoWidget, cartões, tabela escura, barra de status
  tema.py           cores, fontes e conversão de imagens
  base.py           classe base das telas
  tela_*.py         uma tela por funcionalidade
"""
