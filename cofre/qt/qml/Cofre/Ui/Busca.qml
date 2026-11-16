import QtQuick
import QtQuick.Controls.Basic

// Campo de busca com ícone e botão de limpar.
TextField {
    id: b
    implicitHeight: 34
    implicitWidth: 260
    color: Theme.texto
    placeholderTextColor: Theme.texto3
    selectionColor: Theme.acentoForte
    selectedTextColor: Theme.sobreCor
    font.pixelSize: Theme.tCorpo
    leftPadding: 34
    rightPadding: b.text !== "" ? 32 : 12
    background: Rectangle {
        radius: Theme.raioPequeno
        color: Theme.campo
        border.width: b.activeFocus ? 1.5 : 1
        border.color: b.activeFocus ? Theme.acento : (b.hovered ? Theme.bordaForte : Theme.borda)
        Icone { anchors.verticalCenter: parent.verticalCenter; x: 11; nome: "busca"; tamanho: 15; cor: Theme.texto3 }
    }
    BotaoIcone {
        visible: b.text !== ""
        anchors.right: parent.right
        anchors.rightMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        tamanho: 24
        icone: "fechar"
        dica: "Limpar busca"
        onClicked: { b.clear(); b.forceActiveFocus() }
    }
}
