import QtQuick
import QtQuick.Controls.Basic

// Botão só com ícone; `dica` é obrigatória para acessibilidade.
AbstractButton {
    id: b
    property string icone: ""
    property string dica: ""
    property color cor: Theme.texto2
    property real tamanho: 30
    implicitWidth: tamanho
    implicitHeight: tamanho
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: dica
    background: Rectangle {
        radius: Theme.raioPequeno
        color: b.down ? Theme.bordaForte : (b.hovered ? Theme.realce : "transparent")
        border.width: b.visualFocus ? 2 : 0
        border.color: Theme.acento
        Behavior on color { ColorAnimation { duration: Theme.rapido } }
    }
    contentItem: Item {
        Icone { anchors.centerIn: parent; nome: b.icone; tamanho: Math.round(b.tamanho * 0.55); cor: b.enabled ? (b.hovered ? Theme.texto : b.cor) : Theme.texto3 }
    }
    Dica { visible: b.dica !== "" && b.hovered; text: b.dica }
}
