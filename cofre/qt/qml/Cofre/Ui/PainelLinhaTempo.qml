import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Linha do tempo de um incidente: uma linha por tentativa (hora, resultado, similaridade com a marca do
// limiar em vigor, nível exigido). As tentativas do incidente ficam em destaque; as de contexto, apagadas.
Rectangle {
    id: linhaTempo
    property var linhas: []
    property real limiar: -1
    property string titulo: ""
    property string subtitulo: ""
    property string pessoa: ""
    signal abrirAuditoria()

    implicitWidth: 420
    implicitHeight: 320
    radius: Theme.raioGrande
    color: Theme.superficie
    border.color: Theme.borda

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    Layout.fillWidth: true
                    text: linhaTempo.titulo
                    color: Theme.texto
                    font.pixelSize: Theme.tDestaque
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    visible: text !== ""
                    Layout.fillWidth: true
                    text: linhaTempo.subtitulo + (linhaTempo.pessoa !== "" ? " · " + linhaTempo.pessoa : "")
                    color: Theme.texto3
                    font.pixelSize: Theme.tPequeno
                    wrapMode: Text.Wrap
                }
            }
            Botao {
                objectName: "botaoAbrirNaAuditoria"
                text: "Abrir na Auditoria"
                icone: "acessos"
                compacto: true
                enabled: (linhaTempo.linhas || []).length > 0
                onClicked: linhaTempo.abrirAuditoria()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Text { Layout.preferredWidth: 64; text: "Hora"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
            Text { Layout.preferredWidth: 128; text: "Resultado"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
            Text { Layout.fillWidth: true; text: "Similaridade"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
            Text { Layout.preferredWidth: 52; text: "Nível"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; horizontalAlignment: Text.AlignRight }
        }

        ListView {
            id: lista
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 0
            boundsBehavior: Flickable.StopAtBounds
            model: linhaTempo.linhas || []
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Item {
                id: item
                required property var modelData
                width: lista.width
                height: 34
                readonly property bool destaque: modelData.doIncidente === true
                Accessible.role: Accessible.StaticText
                Accessible.name: (modelData.hora || "") + ", " + (modelData.titulo || "") + ", similaridade "
                                 + (modelData.similaridadeTexto || "–") + ", nível " + (modelData.nivelExigido || "")
                Rectangle {
                    anchors.fill: parent
                    radius: Theme.raioPequeno
                    color: item.destaque ? Theme.elevada : "transparent"
                }
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6
                    spacing: 12
                    Text {
                        Layout.preferredWidth: 58
                        text: item.modelData.hora || "–"
                        color: item.destaque ? Theme.texto : Theme.texto3
                        font.pixelSize: Theme.tPequeno
                        font.features: { "tnum": 1 }
                    }
                    Item {
                        Layout.preferredWidth: 128
                        Layout.fillHeight: true
                        Selo {
                            anchors.verticalCenter: parent.verticalCenter
                            visible: item.destaque
                            texto: item.modelData.titulo || ""
                            cor: Theme.corResultado(item.modelData.concedido ? "CONCEDIDO" : "erro")
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            visible: !item.destaque
                            text: item.modelData.titulo || ""
                            color: Theme.texto3
                            font.pixelSize: Theme.tLegenda
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        BarraSimilaridade {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignVCenter
                            valor: item.modelData.similaridade !== undefined ? item.modelData.similaridade : -1
                            marca: linhaTempo.limiar
                            cor: item.destaque ? Theme.acento : Theme.texto3
                            descricao: "Similaridade " + (item.modelData.similaridadeTexto || "–")
                        }
                        Text {
                            Layout.preferredWidth: 40
                            text: item.modelData.similaridadeTexto || "–"
                            color: item.destaque ? Theme.texto : Theme.texto3
                            font.pixelSize: Theme.tPequeno
                            font.features: { "tnum": 1 }
                            horizontalAlignment: Text.AlignRight
                        }
                    }
                    Text {
                        Layout.preferredWidth: 46
                        text: String(item.modelData.nivelExigido || "–")
                        color: item.destaque ? Theme.texto2 : Theme.texto3
                        font.pixelSize: Theme.tPequeno
                        font.features: { "tnum": 1 }
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
        }
    }
}
