import QtQuick
import QtQuick.Layouts

// Uma linha "rótulo à esquerda · valor à direita" (leituras das estações, postura, ficha de protocolo).
Item {
    id: par
    property string rotulo: ""
    property string valor: "–"
    property bool mono: false
    property color cor: Theme.texto
    property string dica: ""
    implicitHeight: 24
    implicitWidth: 240
    Accessible.role: Accessible.StaticText
    Accessible.name: rotulo + ": " + valor

    RowLayout {
        anchors.fill: parent
        spacing: 12
        Text {
            text: par.rotulo
            color: Theme.texto2
            font.pixelSize: Theme.tPequeno
            elide: Text.ElideRight
            Layout.fillWidth: true
            Layout.minimumWidth: Math.min(implicitWidth, par.width * 0.3)
        }
        Text {
            text: par.valor
            color: par.cor
            font.pixelSize: par.mono ? Theme.tPequeno : Theme.tCorpo
            font.family: par.mono ? Theme.familiaMono : Theme.familia
            font.features: { "tnum": 1 }
            elide: Text.ElideMiddle
            horizontalAlignment: Text.AlignRight
            Layout.maximumWidth: par.width * 0.7
        }
    }
    HoverHandler { id: cursor }
    Dica { visible: par.dica !== "" && cursor.hovered; text: par.dica }
}
