import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Aba Explicabilidade do Laboratório PIVC: o mapa de oclusão sobre o rosto alinhado, calculado só
// pelo botão. Análise consultiva: uma imagem mostra tendência, não estatística.
Item {
    id: aba
    objectName: "abaLabExplicabilidade"
    readonly property var vm: app.v2.labExplicabilidade
    readonly property bool comDado: vm.estado === "pronto" || vm.estado === "poucos"
    readonly property string versao: "?r=" + (vm.revisao || 0)
    property string modo: "ambos"           // rosto | mapa | ambos

    ScrollView {
        id: rolagem
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true
        visible: aba.comDado

        ColumnLayout {
            width: rolagem.availableWidth
            spacing: Theme.espacoBloco

            Aviso {
                Layout.fillWidth: true
                visible: vm.semReferencia === true
                tipo: "aviso"
                texto: "O mapa precisa de uma referência: outra imagem da mesma pessoa. Escolha na barra de fonte."
            }
            Aviso {
                Layout.fillWidth: true
                visible: vm.mesmaImagem === true
                tipo: "aviso"
                texto: "A referência parece ser a mesma imagem (similaridade " + (vm.base || 0).toFixed(2).replace(".", ",")
                       + "): o mapa não diz nada assim."
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 20

                // A. rosto e mapa
                ColumnLayout {
                    Layout.alignment: Qt.AlignTop
                    spacing: 10
                    Rectangle {
                        objectName: "palcoOclusao"
                        Layout.preferredWidth: 448
                        Layout.preferredHeight: 448
                        radius: Theme.raio
                        color: Theme.campo
                        border.color: Theme.borda
                        clip: true
                        Image {
                            anchors.fill: parent
                            anchors.margins: 1
                            visible: aba.modo !== "mapa"
                            source: (vm.revisao || 0) > 0 ? "image://cofre/lab/oclusao/rosto" + aba.versao : ""
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            cache: false
                        }
                        Image {
                            objectName: "calorOclusao"
                            anchors.fill: parent
                            anchors.margins: 1
                            visible: vm.temMapa === true && aba.modo !== "rosto"
                            opacity: aba.modo === "mapa" ? 1 : vm.opacidade
                            source: vm.temMapa ? "image://cofre/lab/oclusao/calor" + aba.versao : ""
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            cache: false
                        }
                    }
                    RowLayout {
                        Layout.preferredWidth: 448
                        spacing: 8
                        Segmentado {
                            opcoes: [{ valor: "rosto", texto: "Rosto" }, { valor: "mapa", texto: "Mapa" }, { valor: "ambos", texto: "Os dois" }]
                            atual: aba.modo
                            onEscolhido: function(v) { aba.modo = v }
                        }
                        Item { Layout.fillWidth: true }
                        Text { text: "menos"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                        Row {
                            spacing: 0
                            Repeater {
                                model: Theme.calor
                                delegate: Rectangle {
                                    required property var modelData
                                    width: 16; height: 8
                                    color: modelData
                                }
                            }
                        }
                        Text { text: "mais"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                    }
                    Deslizante {
                        Layout.preferredWidth: 448
                        rotulo: "Opacidade do mapa"
                        valor: vm.opacidade
                        minimo: 0; maximo: 1; passo: 0.05; casas: 2
                        padrao: 0.65
                        habilitado: vm.temMapa === true
                        onMovido: function(v) { vm.definirOpacidade(v) }
                    }
                }

                // B. leitura
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Botao {
                            objectName: "botaoCalcularMapa"
                            variante: "primario"
                            icone: "alvo"
                            text: "Calcular mapa"
                            enabled: vm.semReferencia !== true
                            onClicked: vm.calcular()
                        }
                        Text { text: (vm.variacoes || 49) + " variações"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                        Item { Layout.fillWidth: true }
                        Segmentado {
                            opcoes: [{ valor: 28, texto: "7 × 7 (rápido)" }, { valor: 24, texto: "12 × 12 (fino)" }]
                            atual: vm.janela
                            onEscolhido: function(v) { vm.definirJanela(v) }
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: vm.temMapa ? (vm.frase || "") : "O mapa cobre partes do rosto, uma de cada vez, e mede quanto a similaridade com a referência cai."
                        color: vm.temMapa ? Theme.texto : Theme.texto2
                        font.pixelSize: 15
                        wrapMode: Text.Wrap
                    }
                    Botao {
                        objectName: "botaoVerCurvasOclusao"
                        text: "Ver as curvas de oclusão"
                        icone: "resultados"
                        variante: "fantasma"
                        compacto: true
                        onClicked: app.v2.laboratorio.definirAba("robustez")
                    }
                    CartaoGrafico {
                        visible: vm.temMapa === true
                        Layout.fillWidth: true
                        titulo: "Queda de similaridade ao cobrir cada região"
                        tipo: "barras"
                        dados: vm.barras || ({})
                        altura: 260
                        nomeArquivo: "oclusao-regioes"
                        onExportar: app.v2.figuras.exportar("barras", vm.barras, "oclusao-regioes")
                    }
                    Text {
                        visible: vm.temMapa === true && (vm.aumentos || 0) > 0
                        Layout.fillWidth: true
                        text: "Em " + (vm.aumentos || 0) + " posições, cobrir aumentou a similaridade (tratadas como zero)."
                        color: Theme.texto2
                        font.pixelSize: Theme.tPequeno
                        wrapMode: Text.Wrap
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Análise consultiva. Uma imagem mostra tendência, não estatística."
                        color: Theme.texto3
                        font.pixelSize: Theme.tPequeno
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }

    EstadoBloco {
        anchors.fill: parent
        estado: vm.estado || "vazio"
        erro: vm.erro || ""
        progresso: vm.progresso !== undefined ? vm.progresso : -1
        vazioIcone: "rosto"
        vazioTitulo: "Nenhum rosto para examinar"
        vazioTexto: "Escolha uma imagem com rosto na barra de fonte"
        vazioAcao: "Usar foto de teste"
        onAcionado: app.v2.laboratorio.usarFotoTeste(0)
        onTentarNovamente: vm.recarregar()
    }
}
