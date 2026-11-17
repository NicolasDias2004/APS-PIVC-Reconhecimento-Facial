import QtQuick
import QtQuick.Layouts

// Cartão de número: rótulo, valor e detalhe (N, intervalo, teto). Altura fixa, para alinhar em fila.
Rectangle {
    id: m
    property string rotulo: ""
    property string valor: "–"
    property string detalhe: ""
    property color cor: Theme.texto
    property string dica: ""
    implicitHeight: 76
    implicitWidth: 150
    radius: Theme.raio
    color: Theme.superficie
    border.color: Theme.borda
    Accessible.role: Accessible.StaticText
    Accessible.name: rotulo + ": " + valor + ". " + detalhe

    ColumnLayout {
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 14; rightMargin: 14 }
        spacing: 1
        Text { text: m.rotulo; color: Theme.texto2; font.pixelSize: Theme.tPequeno; elide: Text.ElideRight; Layout.fillWidth: true }
        Text {
            text: m.valor
            color: m.cor
            font.pixelSize: 22
            font.weight: Font.DemiBold
            font.features: { "tnum": 1 }
            fontSizeMode: Text.HorizontalFit      // valor comprido ("0 de 2 236") encolhe antes de ser cortado
            minimumPixelSize: 15
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
        Text {
            text: m.detalhe
            color: Theme.texto3
            font.pixelSize: Theme.tLegenda
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
    }
    HoverHandler { id: cursor }
    Dica { visible: m.dica !== "" && cursor.hovered; text: m.dica }
}
