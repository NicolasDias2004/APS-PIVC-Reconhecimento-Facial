import QtQuick
import QtQuick.Controls.Basic

// Lista suspensa. `opcoes`: lista de { valor, texto }.
ComboBox {
    id: cb
    property var opcoes: []
    property var atual
    signal escolhido(var valor)
    model: opcoes
    textRole: "texto"
    valueRole: "valor"
    implicitHeight: 34
    implicitWidth: 180
    font.pixelSize: Theme.tCorpo
    hoverEnabled: true
    currentIndex: {
        for (var i = 0; i < opcoes.length; ++i) if (opcoes[i].valor === atual) return i
        return 0
    }
    onActivated: function(indice) { cb.escolhido(opcoes[indice].valor) }

    contentItem: Text {
        leftPadding: 12
        rightPadding: 30
        text: cb.displayText
        color: Theme.texto
        font: cb.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Icone { x: cb.width - width - 10; anchors.verticalCenter: parent.verticalCenter; nome: "baixo"; tamanho: 14; cor: Theme.texto3 }
    background: Rectangle {
        radius: Theme.raioPequeno
        color: cb.hovered ? Theme.realce : Theme.elevada
        border.width: cb.visualFocus ? 1.5 : 1
        border.color: cb.visualFocus ? Theme.acento : Theme.borda
    }
    delegate: ItemDelegate {
        id: opc
        required property var modelData
        required property int index
        width: ListView.view ? ListView.view.width : 0
        height: 32
        hoverEnabled: true
        contentItem: Text {
            text: opc.modelData.texto
            color: cb.currentIndex === opc.index ? Theme.acento : Theme.texto
            font.pixelSize: Theme.tCorpo
            verticalAlignment: Text.AlignVCenter
            leftPadding: 4
        }
        background: Rectangle { radius: Theme.raioPequeno - 2; color: opc.hovered ? Theme.realce : "transparent" }
    }
    popup: Popup {
        y: cb.height + 4
        width: Math.max(cb.width, 200)
        padding: 4
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 320)
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: cb.popup.visible ? cb.delegateModel : null
            currentIndex: cb.highlightedIndex
        }
        background: Rectangle { radius: Theme.raio; color: Theme.elevada; border.color: Theme.bordaForte }
    }
}
