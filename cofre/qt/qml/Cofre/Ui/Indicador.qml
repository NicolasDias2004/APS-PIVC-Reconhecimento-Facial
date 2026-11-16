import QtQuick
import QtQuick.Layouts

// Número com legenda (indicadores de resumo).
Rectangle {
    id: i
    property string rotulo: ""
    property string valor: "0"
    property string detalhe: ""
    property string icone: ""
    property color cor: Theme.texto
    color: Theme.superficie
    radius: Theme.raio
    border.color: Theme.borda
    implicitHeight: col.implicitHeight + 28
    implicitWidth: 150
    ColumnLayout {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
        spacing: 4
        RowLayout {
            spacing: 6
            Icone { visible: i.icone !== ""; nome: i.icone; tamanho: 14; cor: Theme.texto3 }
            Text { text: i.rotulo; color: Theme.texto2; font.pixelSize: Theme.tPequeno; elide: Text.ElideRight; Layout.fillWidth: true }
        }
        Text {
            text: i.valor
            color: i.cor
            font.pixelSize: 24
            font.weight: Font.DemiBold
            font.features: { "tnum": 1 }
        }
        Text { visible: i.detalhe !== ""; text: i.detalhe; color: Theme.texto3; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
    }
}
