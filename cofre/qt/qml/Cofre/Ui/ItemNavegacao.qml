import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Item da navegação lateral.
AbstractButton {
    id: it
    property string icone: ""
    property bool ativo: false
    property string atalho: ""
    implicitHeight: 36
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    background: Rectangle {
        radius: Theme.raioPequeno
        color: it.ativo ? Theme.realce : (it.hovered ? Qt.rgba(1, 1, 1, 0.035) : "transparent")
        border.width: it.visualFocus ? 2 : 0
        border.color: Theme.acento
        Behavior on color { ColorAnimation { duration: Theme.rapido } }
        Rectangle {
            visible: it.ativo
            width: 3; height: 16; radius: 2
            color: Theme.acento
            anchors { left: parent.left; leftMargin: -10; verticalCenter: parent.verticalCenter }
        }
    }
    contentItem: RowLayout {
        spacing: 11
        Item { implicitWidth: 2 }
        Icone { nome: it.icone; tamanho: 17; cor: it.ativo ? Theme.acento : (it.hovered ? Theme.texto : Theme.texto2) }
        Text {
            text: it.text
            color: it.ativo ? Theme.texto : (it.hovered ? Theme.texto : Theme.texto2)
            font.pixelSize: Theme.tCorpo
            font.weight: it.ativo ? Font.DemiBold : Font.Normal
            Layout.fillWidth: true
        }
        Text { visible: it.atalho !== ""; text: it.atalho; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
    }
}
