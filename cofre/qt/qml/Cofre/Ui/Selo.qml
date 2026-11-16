import QtQuick
import QtQuick.Layouts

// Selo compacto (estado, nível, resultado).
Rectangle {
    id: s
    property string texto: ""
    property color cor: Theme.texto2
    property string icone: ""
    property bool solido: false
    implicitHeight: 22
    implicitWidth: linha.implicitWidth + 16
    radius: height / 2
    color: solido ? cor : Qt.rgba(cor.r, cor.g, cor.b, 0.13)
    border.width: solido ? 0 : 1
    border.color: Qt.rgba(cor.r, cor.g, cor.b, 0.28)
    RowLayout {
        id: linha
        anchors.centerIn: parent
        spacing: 5
        Icone { visible: s.icone !== ""; nome: s.icone; tamanho: 12; traco: 2.2; cor: s.solido ? Theme.sobreCor : s.cor }
        Text {
            text: s.texto
            color: s.solido ? Theme.sobreCor : s.cor
            font.pixelSize: Theme.tLegenda
            font.weight: Font.DemiBold
        }
    }
}
