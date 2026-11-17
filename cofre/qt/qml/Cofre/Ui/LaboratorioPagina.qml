import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import Cofre.Nativo

// Laboratório PIVC: uma imagem atravessando as cinco fases, com medida em cada uma.
// A barra de fonte escolhe a amostra e a referência, que as abas leem do LaboratorioVM. A câmera
// aqui só mostra o quadro para congelá-lo: nada é comparado com a galeria ao vivo.
Item {
    id: pagina
    objectName: "paginaLaboratorio"
    readonly property var l: app.v2.laboratorio
    readonly property var cam: app.cameraServico
    readonly property var abas: l && typeof l.abas === "function" ? l.abas() : []
    readonly property int indiceAba: {
        for (var i = 0; i < abas.length; ++i) if (abas[i].valor === l.aba) return i
        return 0
    }
    readonly property var opcoesFotos: {
        var fotos = l.fotosTeste || []
        var lista = []
        for (var i = 0; i < fotos.length; ++i) lista.push({ valor: fotos[i].indice, texto: fotos[i].rotulo })
        return lista
    }
    readonly property bool emPrevia: l.previa === true
    // a barra de fonte encolhe com a janela: abaixo de 1300 px os botões ficam só com o ícone (a dica diz
    // o que fazem) e abaixo de 1000 px o seletor de fotos encurta; os rótulos quebram em até duas linhas
    readonly property bool estreita: width < 1300
    readonly property bool apertada: width < 1000
    readonly property var filtroImagens: ["Imagens (*.jpg *.jpeg *.png *.bmp *.webp)", "Todos os arquivos (*)"]

    FileDialog {
        id: dialogoAmostra
        title: "Imagem para a amostra"
        nameFilters: pagina.filtroImagens
        onAccepted: pagina.l.abrirArquivo(selectedFile)
    }
    FileDialog {
        id: dialogoReferencia
        title: "Imagem de referência"
        nameFilters: pagina.filtroImagens
        onAccepted: pagina.l.abrirReferencia(selectedFile)
    }

    Shortcut {
        sequences: ["Space"]
        enabled: pagina.visible && pagina.emPrevia && !app.v2.sobreposicaoAberta
        onActivated: pagina.l.congelar()
    }
    Shortcut {
        sequences: ["Escape"]
        enabled: pagina.visible && pagina.emPrevia && !app.v2.sobreposicaoAberta
        onActivated: pagina.l.cancelarPrevia()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: Theme.espacoBloco

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Laboratório PIVC"
            descricao: "Uma imagem atravessando as cinco fases, com medida em cada uma"
            SeloDemo { compacto: true }
            SeloConsultivo {}
        }

        // ------------------------------------------------------------ barra de fonte
        Rectangle {
            id: barra
            objectName: "barraFonte"
            Layout.fillWidth: true
            implicitHeight: 64
            radius: Theme.raioGrande
            color: Theme.superficie
            border.color: Theme.borda

            RowLayout {
                anchors { fill: parent; leftMargin: 10; rightMargin: 12 }
                spacing: 8

                // amostra
                Rectangle {
                    Layout.preferredWidth: 44
                    Layout.preferredHeight: 44
                    radius: 8
                    color: Theme.campo
                    border.color: Theme.borda
                    clip: true
                    VisorVideo {
                        anchors.fill: parent
                        anchors.margins: 1
                        visible: pagina.l.fonteVideo.temImagem
                        fonte: pagina.l.fonteVideo
                        preencher: true
                        raio: 8
                        corFundo: Theme.campo
                        mostrarPontos: false
                    }
                    Icone { anchors.centerIn: parent; visible: !pagina.l.fonteVideo.temImagem; nome: "imagem"; tamanho: 18; cor: Theme.texto3 }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 60
                    spacing: 1
                    Text { text: "Amostra"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text {
                            Layout.fillWidth: true
                            text: pagina.l.temAmostra ? (pagina.l.amostraRotulo || "") : "Nenhuma imagem"
                            color: pagina.l.temAmostra ? Theme.texto : Theme.texto2
                            font.pixelSize: Theme.tCorpo
                            font.weight: pagina.l.temAmostra ? Font.Medium : Font.Normal
                            wrapMode: Text.Wrap
                            maximumLineCount: 2
                            lineHeight: 0.95
                            elide: Text.ElideRight
                        }
                        Carregando { visible: pagina.l.processando === true; tamanho: 13 }
                    }
                }
                Selo { visible: pagina.l.nRostos > 1; texto: pagina.l.nRostos + " rostos"; cor: Theme.aviso; icone: "alerta" }
                Seletor {
                    Layout.preferredWidth: pagina.apertada ? 100 : 150
                    implicitHeight: 30
                    displayText: pagina.apertada ? "Fotos" : "Fotos de teste"
                    opcoes: pagina.opcoesFotos
                    enabled: pagina.opcoesFotos.length > 0
                    Accessible.name: "Fotos de teste para a amostra"
                    onEscolhido: function(valor) { pagina.l.usarFotoTeste(valor) }
                }
                Botao {
                    compacto: true
                    icone: "arquivo"
                    text: pagina.estreita ? "" : "Arquivo…"
                    dica: pagina.estreita ? "Abrir uma imagem como amostra" : ""
                    Accessible.name: "Arquivo para a amostra"
                    onClicked: dialogoAmostra.open()
                }
                Botao {
                    compacto: true
                    icone: "camera"
                    text: pagina.estreita ? "" : "Câmera"
                    dica: pagina.estreita ? "Congelar um quadro da câmera como amostra" : ""
                    enabled: !app.sessao.ativa
                    Accessible.name: "Câmera para a amostra"
                    onClicked: pagina.l.iniciarPrevia("amostra")
                }

                Rectangle { Layout.fillHeight: true; Layout.topMargin: 12; Layout.bottomMargin: 12; Layout.leftMargin: 4; Layout.rightMargin: 4; implicitWidth: 1; color: Theme.borda }

                // referência
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 60
                    spacing: 1
                    Text { text: "Referência"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                    Text {
                        Layout.fillWidth: true
                        text: pagina.l.temReferencia ? (pagina.l.referenciaRotulo || "") : "Sem referência"
                        color: pagina.l.temReferencia ? Theme.texto : Theme.texto2
                        font.pixelSize: Theme.tCorpo
                        font.weight: pagina.l.temReferencia ? Font.Medium : Font.Normal
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        lineHeight: 0.95
                        elide: Text.ElideRight
                    }
                }
                Seletor {
                    Layout.preferredWidth: pagina.apertada ? 100 : 150
                    implicitHeight: 30
                    displayText: pagina.apertada ? "Fotos" : "Fotos de teste"
                    opcoes: pagina.opcoesFotos
                    enabled: pagina.opcoesFotos.length > 0
                    Accessible.name: "Fotos de teste para a referência"
                    onEscolhido: function(valor) { pagina.l.usarFotoTesteComoReferencia(valor) }
                }
                Botao {
                    compacto: true
                    icone: "arquivo"
                    text: pagina.estreita ? "" : "Arquivo…"
                    dica: pagina.estreita ? "Abrir uma imagem como referência" : ""
                    Accessible.name: "Arquivo para a referência"
                    onClicked: dialogoReferencia.open()
                }
                Botao {
                    compacto: true
                    icone: "camera"
                    text: pagina.estreita ? "" : "Câmera"
                    dica: pagina.estreita ? "Congelar um quadro da câmera como referência" : ""
                    enabled: !app.sessao.ativa
                    Accessible.name: "Câmera para a referência"
                    onClicked: pagina.l.iniciarPrevia("referencia")
                }
                BotaoIcone {
                    icone: "fechar"
                    dica: "Remover referência"
                    enabled: pagina.l.temReferencia === true
                    onClicked: pagina.l.limparReferencia()
                }
            }
        }

        Aviso {
            Layout.fillWidth: true
            visible: (pagina.l.erro || "") !== ""
            tipo: "erro"
            texto: pagina.l.erro || ""
        }

        Abas {
            Layout.fillWidth: true
            opcoes: pagina.abas
            atual: pagina.l.aba
            onEscolhida: function(valor) { pagina.l.definirAba(valor) }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            StackLayout {
                anchors.fill: parent
                currentIndex: pagina.indiceAba
                Repeater {
                    model: pagina.abas
                    delegate: Carregador {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        fonte: modelData.fonte || ""
                        erroVm: modelData.erro || ""
                        ativo: pagina.l.aba === modelData.valor
                    }
                }
            }

            // ---------------------------------------------------- pré-visualização da câmera
            Rectangle {
                id: previa
                objectName: "previaCamera"
                anchors.fill: parent
                visible: pagina.emPrevia
                radius: Theme.raioGrande
                color: Theme.superficie
                border.color: Theme.borda
                MouseArea { anchors.fill: parent; hoverEnabled: true }      // as abas por baixo não recebem o clique

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 14

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: Theme.raio
                        color: Theme.lateral
                        border.color: Theme.borda
                        clip: true
                        VisorVideo {
                            anchors.fill: parent
                            anchors.margins: 1
                            fonte: pagina.l.fonteVideo
                            preencher: false
                            raio: Theme.raio
                            corFundo: Theme.lateral
                            mostrarPontos: false
                        }
                        ColumnLayout {
                            anchors.centerIn: parent
                            visible: pagina.cam.estado === "abrindo"
                            spacing: 8
                            Carregando { Layout.alignment: Qt.AlignHCenter; tamanho: 22 }
                            Text { text: "Abrindo a câmera"; color: Theme.texto2; font.pixelSize: Theme.tCorpo }
                        }
                        Aviso {
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 48, 520)
                            visible: pagina.cam.estado === "erro"
                            tipo: "erro"
                            texto: pagina.cam.erro || "A câmera não está disponível."
                            acao: pagina.opcoesFotos.length > 0 ? "Usar foto de teste" : ""
                            iconeAcao: "imagem"
                            onAcionado: {
                                pagina.l.cancelarPrevia()
                                pagina.l.usarFotoTeste(pagina.opcoesFotos[0].valor)
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: "Posicione o rosto e congele o quadro"
                                color: Theme.texto
                                font.pixelSize: Theme.tCorpo
                                font.weight: Font.Medium
                            }
                            Text {
                                Layout.fillWidth: true
                                text: (pagina.l.alvoPrevia === "referencia" ? "O quadro vira a referência." : "O quadro vira a amostra.")
                                      + " Ele fica só na memória e some ao sair desta página."
                                color: Theme.texto3
                                font.pixelSize: Theme.tPequeno
                                wrapMode: Text.Wrap
                            }
                        }
                        Botao {
                            text: "Cancelar"
                            onClicked: pagina.l.cancelarPrevia()
                        }
                        Botao {
                            variante: "primario"
                            icone: "congelar"
                            text: "Congelar quadro"
                            enabled: pagina.cam.estado === "ativa"
                            onClicked: pagina.l.congelar()
                        }
                        Tecla { texto: "espaço" }
                    }
                }
            }
        }
    }
}
