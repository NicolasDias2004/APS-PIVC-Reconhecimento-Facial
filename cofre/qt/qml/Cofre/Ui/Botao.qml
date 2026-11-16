import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Botão com variantes: "primario" (acento), "secundario", "fantasma" e "perigo".
Button {
    id: b
    property string variante: "secundario"
    property string icone: ""
    property bool compacto: false
    property string dica: ""
    property bool carregando: false

    readonly property color _fundo: {
        if (!enabled) return variante === "fantasma" ? "transparent" : Theme.elevada
        if (variante === "primario") return down ? Theme.acentoForte : (hovered ? Qt.lighter(Theme.acento, 1.08) : Theme.acento)
        if (variante === "perigo") return down ? Qt.darker(Theme.perigo, 1.15) : (hovered ? Qt.lighter(Theme.perigo, 1.06) : Theme.perigo)
        if (variante === "fantasma") return down ? Theme.realce : (hovered ? Theme.elevada : "transparent")
        return down ? Theme.bordaForte : (hovered ? Theme.realce : Theme.elevada)
    }
    readonly property color _texto: {
        if (!enabled) return Theme.texto3
        if (variante === "primario" || variante === "perigo") return Theme.sobreCor
        return variante === "fantasma" && !hovered ? Theme.texto2 : Theme.texto
    }

    implicitHeight: compacto ? 28 : 34
    leftPadding: compacto ? 10 : 14
    rightPadding: compacto ? 10 : 14
    font.pixelSize: compacto ? Theme.tPequeno : Theme.tCorpo
    font.weight: Font.Medium
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus

    contentItem: RowLayout {
        spacing: 7
        Item {
            visible: b.icone !== "" || b.carregando
            implicitWidth: b.compacto ? 14 : 16
            implicitHeight: implicitWidth
            Icone { anchors.centerIn: parent; visible: !b.carregando; nome: b.icone; cor: b._texto; tamanho: parent.width; traco: 2 }
            Carregando { anchors.centerIn: parent; visible: b.carregando; tamanho: parent.width; cor: b._texto }
        }
        Text {
            visible: b.text !== ""
            text: b.text
            color: b._texto
            font: b.font
            elide: Text.ElideRight
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
        }
    }
    background: Rectangle {
        radius: Theme.raioPequeno
        color: b._fundo
        border.width: b.variante === "secundario" ? 1 : 0
        border.color: b.hovered ? Theme.bordaForte : Theme.borda
        Behavior on color { ColorAnimation { duration: Theme.rapido } }
        Rectangle {        // anel de foco do teclado
            anchors.fill: parent
            anchors.margins: -3
            radius: parent.radius + 3
            color: "transparent"
            border.width: 2
            border.color: Theme.acento
            opacity: b.visualFocus ? 0.7 : 0
        }
    }
    Dica { visible: b.dica !== "" && b.hovered; text: b.dica }
}
