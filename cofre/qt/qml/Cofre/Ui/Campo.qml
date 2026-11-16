import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Campo de texto com rótulo, dica e mensagem de erro.
ColumnLayout {
    id: c
    property string rotulo: ""
    property string ajuda: ""
    property string erro: ""
    property alias texto: entrada.text
    property alias placeholder: entrada.placeholderText
    property alias entrada: entrada
    property bool obrigatorio: false
    signal confirmado()
    spacing: 6

    RowLayout {
        visible: c.rotulo !== ""
        spacing: 4
        Text { text: c.rotulo; color: Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium }
        Text { visible: c.obrigatorio; text: "obrigatório"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
    }
    TextField {
        id: entrada
        Layout.fillWidth: true
        implicitHeight: 36
        color: Theme.texto
        placeholderTextColor: Theme.texto3
        selectionColor: Theme.acentoForte
        selectedTextColor: Theme.sobreCor
        font.pixelSize: Theme.tCorpo
        leftPadding: 12
        rightPadding: 12
        onAccepted: c.confirmado()
        background: Rectangle {
            radius: Theme.raioPequeno
            color: entrada.enabled ? Theme.campo : Theme.superficie
            border.width: entrada.activeFocus || c.erro !== "" ? 1.5 : 1
            border.color: c.erro !== "" ? Theme.perigo : (entrada.activeFocus ? Theme.acento : (entrada.hovered ? Theme.bordaForte : Theme.borda))
            Behavior on border.color { ColorAnimation { duration: Theme.rapido } }
        }
    }
    Text {
        visible: c.erro !== "" || c.ajuda !== ""
        text: c.erro !== "" ? c.erro : c.ajuda
        color: c.erro !== "" ? Theme.perigo : Theme.texto3
        font.pixelSize: Theme.tLegenda
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }
}
