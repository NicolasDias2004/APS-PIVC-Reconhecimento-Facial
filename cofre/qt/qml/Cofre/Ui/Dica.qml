import QtQuick
import QtQuick.Controls.Basic

// Dica (tooltip) no estilo do aplicativo. Uso: Dica { visible: alvo.hovered; text: "..." }
ToolTip {
    id: dica
    delay: 450
    timeout: 6000
    padding: 8
    contentItem: Text {
        text: dica.text
        color: Theme.texto
        font.pixelSize: Theme.tPequeno
        wrapMode: Text.Wrap
        width: Math.min(implicitWidth, 300)
    }
    background: Rectangle {
        color: Theme.realce
        radius: Theme.raioPequeno
        border.color: Theme.bordaForte
    }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.rapido } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.rapido } }
}
