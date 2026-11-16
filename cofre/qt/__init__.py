"""Interface desktop em PySide6 + Qt Quick (QML).

Camadas:
  qml/Cofre/Ui/        telas e componentes visuais (só apresentação, nenhuma regra de negócio)
  vm_*.py              ViewModels: estado das telas exposto ao QML por propriedades e slots
  camera.py            captura em QThread; entrega só o último quadro (sem fila acumulando)
  video.py             componente de vídeo desenhado com QPainter (quadro + marcações do rosto)
  tarefas.py           trabalho pesado fora da thread da interface, com resultado via sinal
  modelos.py           modelos de lista genéricos para tabelas e listas do QML

A lógica (pipeline, máquina de estados do terminal, cadastro, banco, relatórios) continua
no pacote `cofre` e é a mesma usada pela linha de comando e pela interface customtkinter.
"""
