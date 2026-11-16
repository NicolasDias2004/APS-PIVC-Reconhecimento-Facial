# Sistema de Identificação e Autenticação Biométrica Facial

APS 2026/2 - Ciência da Computação (5º/6º) - disciplina de Processamento de Imagem e Visão Computacional (PIVC).

Controle de acesso ao cofre do Ministério do Meio Ambiente por reconhecimento facial em tempo real,
com três níveis de permissão (1 geral, 2 diretores, 3 ministro), prova de vida, bloqueio por tentativas,
log de auditoria e relatórios. O código é organizado nas cinco fases do processamento de imagens digitais.

## Requisitos

- Python 3.10 ou superior (testado no 3.14)
- Webcam (ou imagens de arquivo para cadastro/autenticação offline)
- Pacotes: `opencv-contrib-python`, `numpy`, `PySide6-Essentials` (aplicativo desktop Qt Quick),
  `customtkinter` e `pillow` (interface anterior) e `pytest` (testes)

## Instalação

```bash
cd APS-PIVC-Reconhecimento-Facial
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Os modelos `models/face_detection_yunet_2023mar.onnx` (detecção, YuNet) e
`models/face_recognition_sface_2021dec.onnx` (reconhecimento, SFace) já estão na pasta.
Se precisar baixar de novo: <https://github.com/opencv/opencv_zoo>.

No macOS, a primeira vez que a câmera abre o sistema pede permissão para o aplicativo que
iniciou o programa (Terminal, VS Code etc.). Se recusar sem querer, libere em
Ajustes > Privacidade e Segurança > Câmera e abra o programa de novo.

## Como usar

### Aplicativo desktop

```bash
python app_qt.py                 # aplicativo principal (PySide6 + Qt Quick), usa data/cofre.db
python app_qt.py --db outro.db   # usa outro banco
python app.py                    # interface anterior (customtkinter), mantida para comparação
```

No macOS, abra pelo aplicativo Terminal: é ele que recebe a permissão da câmera. Processos
abertos por outras ferramentas (editores, assistentes) podem não conseguir o pedido de permissão.

Seis telas na barra lateral (atalhos ⌘1 a ⌘6):

| tela | o que faz |
|---|---|
| Terminal de acesso | câmera ao vivo, escolha da área (níveis 1-3), prova de vida, painel didático, veredito e últimos acessos; filtro de pose (rosto virado, inclinado ou cabeça baixa não é avaliado) e leitura do rosto (pose pelos 5 pontos e o vetor de 128 dimensões) |
| Cadastro biométrico | formulário (nome, matrícula, cargo, nível) e captura de 18 amostras em 9 poses pela câmera (frente, giro, inclinação, queixo, sorriso), ou cadastro por fotos |
| Usuários | lista com busca, alterar nível, ativar/desativar, ver as fotos de cadastro e remover |
| Auditoria de acessos | indicadores, log filtrável (pessoa, resultado, área, período), resumos por pessoa e por dia, detalhe com a evidência, exportação CSV/HTML |
| Avaliação e demo | painel das 5 fases para uma imagem, autenticação por imagem e avaliação TAR/FAR/FRR/EER de uma pasta com curva |
| Configurações | ajusta limiares, pose aceita no terminal, cadastro e câmera; cada campo diz quando passa a valer; salva em `data/config_usuario.json` |

No Terminal de acesso valem as mesmas teclas da versão OpenCV: `1` `2` `3`, `l`, `d` e `r`. Durante o
bloqueio, área e prova de vida ficam travadas (botões e teclas).

Depois de um acesso **concedido**, abre a **área liberada**: uma tela por nível, com dados fictícios de
demonstração. Nível 1 vê a área comum (comunicados, agenda, indicadores), nível 2 vê também a sala dos
diretores (orçamento, metas, aprovações) e nível 3 vê ainda o cofre de toxinas (inventário, sensores,
retiradas). A tela abre só a partir da decisão do backend, fecha por inatividade (`SESSAO_LIBERADA_SEG`,
2 min) ou pelo botão Encerrar sessão, e enquanto está aberta a câmera fica desligada e a navegação travada.
As configurações salvas são aplicadas quando o aplicativo abre. A linha de comando continua usando os valores de `cofre/config.py`.

Na tela de Configurações do aplicativo Qt, frames de confirmação, giro e tempo da prova de vida, máximo de
falhas e duração do bloqueio aparecem como somente leitura: o backend fixa esses valores quando o programa
é carregado, então mudá-los em tempo de execução não teria efeito (ver `docs/DETALHES-PARA-DOCUMENTACAO.md`, seção 8).

### Linha de comando

```bash
python main.py                                   # menu interativo
python main.py cadastrar                         # cadastro pela webcam (18 fotos em 9 poses, com controle de qualidade)
python main.py cadastrar --imagens a.jpg b.jpg   # cadastro a partir de fotos
python main.py autenticar --nivel 3              # terminal do cofre (nível 3 = só o ministro)
python main.py autenticar --nivel 2 --didatico   # mostra também o painel das 5 fases
python main.py autenticar --imagem foto.jpg --nivel 1
python main.py usuarios                          # lista cadastrados
python main.py nivel 2 3 | ativar 2 | desativar 2 | remover 2
python main.py relatorio --html --csv            # estatísticas + log, exporta em data/relatorios/
python main.py avaliar tests/fixtures/pessoas    # TAR/FAR/EER em pasta rotulada (pasta/pessoa/*.jpg)
python main.py demo foto.jpg                     # painel didático das 5 fases para uma imagem
```

Teclas na janela de autenticação: `1` `2` `3` troca a área/nível exigido, `l` liga/desliga prova de vida,
`d` painel didático, `r` recarrega a galeria, `q` sai. No cadastro, `ESC` cancela.

## Testes

```bash
python -m pytest -q
```

96 testes cobrem as fases 2-5, o banco, o esquema de permissões, a prova de vida, o bloqueio,
a máquina de estados do terminal, o filtro de pose, a área liberada, os relatórios, a avaliação, as seis
telas da interface customtkinter e o aplicativo Qt Quick (`tests/test_qt_app.py`, sem janela visível). Usam as fotos em `tests/fixtures`
e uma câmera falsa, sem webcam. A suíte leva cerca de 50 s.

## Estrutura

```
main.py                      CLI e menu
app_qt.py                    aplicativo desktop (PySide6 + Qt Quick)
app.py                       interface anterior (customtkinter)
cofre/
  config.py                  limiares, níveis, áreas, caminhos
  parametros.py              campos ajustáveis e arquivo config_usuario.json (usado pelas duas interfaces)
  areas.py                   conteúdo fictício das áreas liberadas (nível N enxerga 1..N)
  fase1_aquisicao.py         webcam / arquivos
  fase2_preprocessamento.py  redução, cinza, Gauss, CLAHE, métricas de qualidade
  fase3_segmentacao.py       detecção YuNet, pontos faciais, recorte, alinhamento, yaw
  fase4_representacao.py     embedding SFace 128-d, LBP didático, similaridade do cosseno
  fase5_reconhecimento.py    identificação 1:N, limiar, decisão por nível
  pipeline.py                encadeia as fases 2-4
  banco.py                   SQLite (usuarios, amostras, acessos)
  liveness.py                desafio de movimento, bloqueio por tentativas
  autenticacao.py            terminal em tempo real (máquina de estados)
  cadastro.py                enrollment pela webcam ou por imagens
  relatorios.py              tabelas, CSV, HTML
  avaliacao.py               métricas TAR/FAR/EER
  demo.py / hud.py           painel didático e desenho na tela
  qt/                        aplicativo Qt Quick (camadas: serviços, ViewModels, QML)
    aplicacao.py             raiz: banco, câmera, tarefas, navegação e os seis ViewModels
    camera.py                captura + pipeline em QThread, entrega só o quadro mais recente
    tarefas.py               trabalhos em segundo plano (cadastro por fotos, exportação, avaliação)
    video.py                 VisorVideo: desenha o quadro e as caixas dos rostos (QQuickPaintedItem)
    vm_*.py                  um ViewModel por tela; o QML só lê propriedades e chama slots
    vm_sessao.py             área liberada: abre só pela decisão do backend, fecha por tempo ou botão
    qml/Cofre/Ui/            páginas, componentes, tema (Theme.qml) e ícones vetoriais
  interface/                 interface anterior (customtkinter)
    app.py                   janela, barra lateral, troca de telas e ciclo de atualização
    camera.py                câmera em thread separada (captura + pipeline)
    tela_*.py                uma tela por funcionalidade
    widgets.py / tema.py     vídeo, cartões, tabelas, cores e fontes
models/                      redes ONNX (YuNet, SFace)
data/                        cofre.db, fotos/, evidencias/, relatorios/ (gerados em uso)
tests/                       pytest + fotos de teste
docs/                        material para a dissertação e listagem de código
ferramentas/listar_codigo.py gera docs/LISTAGEM-CODIGO.md
```

Material para a dissertação: [docs/DETALHES-PARA-DOCUMENTACAO.md](docs/DETALHES-PARA-DOCUMENTACAO.md).
