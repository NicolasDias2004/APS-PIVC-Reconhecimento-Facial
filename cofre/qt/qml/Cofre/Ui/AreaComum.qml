import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Nível 1: o dia a dia de quem trabalha no Ministério.
ScrollView {
    id: pagina
    property var dados: ({})
    readonly property color cor: Theme.corNivel(1)
    readonly property var comunicados: dados.comunicados || []
    readonly property var agenda: dados.agenda || []
    readonly property var indicadores: dados.indicadores || []
    readonly property var ar: dados.qualidadeAr || []
    readonly property var ramais: dados.ramais || []
    contentWidth: availableWidth
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

    ColumnLayout {
        width: pagina.availableWidth
        spacing: 18

        ColumnLayout {
            Layout.margins: 28
            Layout.bottomMargin: 0
            spacing: 4
            Text {
                readonly property int hora: new Date().getHours()
                text: (hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite") + ", " + app.sessao.nome.split(" ")[0]
                color: Theme.texto; font.pixelSize: Theme.tTitulo; font.weight: Font.DemiBold
            }
            Text { text: dados.titulo || ""; color: Theme.texto2; font.pixelSize: Theme.tCorpo }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            spacing: 12
            Repeater {
                model: pagina.indicadores
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: 84
                    radius: Theme.raio
                    color: Theme.superficie
                    border.color: Theme.borda
                    ColumnLayout {
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                        spacing: 4
                        Text { text: modelData.nome; color: Theme.texto2; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                        RowLayout {
                            spacing: 8
                            Text { text: modelData.valor; color: Theme.texto; font.pixelSize: 24; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                            Text { text: modelData.unidade; color: Theme.texto3; font.pixelSize: Theme.tLegenda; Layout.alignment: Qt.AlignBottom; Layout.bottomMargin: 5 }
                            Item { Layout.fillWidth: true }
                            Selo {
                                texto: (modelData.variacao > 0 ? "+" : "") + modelData.variacao + (modelData.nome.indexOf("Qualidade") === 0 ? "" : "%")
                                cor: modelData.variacao <= 0 ? Theme.sucesso : Theme.aviso
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            Layout.bottomMargin: 28
            spacing: 16

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 16
                Painel {
                    Layout.fillWidth: true
                    titulo: "Comunicados internos"
                    subtitulo: pagina.comunicados.length + " avisos desta semana"
                    espacamento: 8
                    Repeater {
                        model: pagina.comunicados
                        delegate: Rectangle {
                            required property var modelData
                            readonly property color tom: modelData.tipo === "aviso" ? Theme.aviso : modelData.tipo === "ok" ? Theme.sucesso : pagina.cor
                            Layout.fillWidth: true
                            implicitHeight: linha.implicitHeight + 22
                            radius: Theme.raioPequeno + 1
                            color: Theme.campo
                            border.color: Theme.borda
                            Rectangle { anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 1 } width: 3; radius: 2; color: tom }
                            RowLayout {
                                id: linha
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 16; rightMargin: 12 }
                                spacing: 12
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3
                                    Text { text: modelData.titulo; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    Text { text: modelData.texto; color: Theme.texto2; font.pixelSize: Theme.tPequeno; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                }
                                Text { text: modelData.data; color: Theme.texto3; font.pixelSize: Theme.tLegenda; Layout.alignment: Qt.AlignTop; font.features: { "tnum": 1 } }
                            }
                        }
                    }
                }
                Painel {
                    Layout.fillWidth: true
                    titulo: "Qualidade do ar em Brasília"
                    subtitulo: "Índice IQAr dos últimos 7 dias, menor é melhor"
                    Item {
                        Layout.fillWidth: true
                        implicitHeight: 110
                        Row {
                            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: 18 }
                            height: 80
                            spacing: 8
                            Repeater {
                                model: pagina.ar
                                delegate: Item {
                                    required property var modelData
                                    width: (parent.width - 8 * Math.max(0, pagina.ar.length - 1)) / Math.max(1, pagina.ar.length)
                                    height: parent.height
                                    Rectangle {
                                        anchors.bottom: parent.bottom
                                        width: parent.width
                                        height: Math.max(4, parent.height * modelData.valor / 100)
                                        radius: 4
                                        color: modelData.valor <= 40 ? Theme.sucesso : modelData.valor <= 80 ? Theme.aviso : Theme.perigo
                                        opacity: 0.85
                                    }
                                    Text {
                                        anchors { top: parent.bottom; topMargin: 4; horizontalCenter: parent.horizontalCenter }
                                        text: modelData.dia; color: Theme.texto3; font.pixelSize: Theme.tLegenda
                                    }
                                }
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.preferredWidth: 330
                Layout.maximumWidth: 330
                Layout.alignment: Qt.AlignTop
                spacing: 16
                Painel {
                    Layout.fillWidth: true
                    titulo: "Agenda de hoje"
                    espacamento: 0
                    Repeater {
                        model: pagina.agenda
                        delegate: RowLayout {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            spacing: 12
                            Text { text: modelData.hora; color: pagina.cor; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold; font.features: { "tnum": 1 }; Layout.preferredWidth: 42; Layout.alignment: Qt.AlignTop; Layout.topMargin: 10 }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda; visible: index > 0 }
                                ColumnLayout {
                                    Layout.topMargin: 10
                                    Layout.bottomMargin: 10
                                    spacing: 2
                                    Text { text: modelData.titulo; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    Text { text: modelData.local; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                                }
                            }
                        }
                    }
                }
                Painel {
                    Layout.fillWidth: true
                    titulo: "Ramais úteis"
                    espacamento: 6
                    GridLayout {
                        columns: 2
                        columnSpacing: 10
                        rowSpacing: 6
                        Layout.fillWidth: true
                        Repeater {
                            model: pagina.ramais
                            delegate: Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                implicitHeight: 40
                                radius: Theme.raioPequeno
                                color: Theme.campo
                                border.color: Theme.borda
                                RowLayout {
                                    anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                                    Text { text: modelData.setor; color: Theme.texto2; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: modelData.ramal; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
