import QtQuick

// Pílula de tecla, para escrever um atalho no meio de um texto.
Rectangle {
    id: tecla
    property string texto: ""
    implicitWidth: Math.max(20, rotulo.implicitWidth + 10)
    implicitHeight: 20
    radius: 5
    color: Theme.elevada
    border.color: Theme.bordaForte
    Accessible.ignored: true
    Text { id: rotulo; anchors.centerIn: parent; text: tecla.texto; color: Theme.texto2; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
}
