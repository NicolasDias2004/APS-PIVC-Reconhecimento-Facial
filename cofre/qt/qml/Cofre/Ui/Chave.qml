import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Interruptor com título e descrição.
Switch {
    id: ch
    property string descricao: ""
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    padding: 0
    rightPadding: 48
    spacing: 12
    indicator: Rectangle {
        x: ch.width - width
        anchors.verticalCenter: parent.verticalCenter
        implicitWidth: 36
        implicitHeight: 20
        radius: 10
        color: ch.checked ? Theme.acento : Theme.realce
        border.color: ch.checked ? Theme.acento : Theme.bordaForte
        opacity: ch.enabled ? 1 : 0.45
        Behavior on color { ColorAnimation { duration: Theme.medio } }
        Rectangle {
            x: ch.checked ? parent.width - width - 3 : 3
            anchors.verticalCenter: parent.verticalCenter
            width: 14; height: 14; radius: 7
            color: ch.checked ? Theme.sobreCor : Theme.texto2
            Behavior on x { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
        }
        Rectangle {
            anchors.fill: parent; anchors.margins: -3; radius: 13
            color: "transparent"; border.width: 2; border.color: Theme.acento
            opacity: ch.visualFocus ? 0.7 : 0
        }
    }
    contentItem: ColumnLayout {
        spacing: 1
        Text { text: ch.text; color: ch.enabled ? Theme.texto : Theme.texto3; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium }
        Text {
            visible: ch.descricao !== ""
            text: ch.descricao
            color: Theme.texto3
            font.pixelSize: Theme.tPequeno
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
    }
}
