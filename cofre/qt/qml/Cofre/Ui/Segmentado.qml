import QtQuick
import QtQuick.Layouts

// Controle segmentado. `opcoes`: lista de { valor, texto, dica? }.
Rectangle {
    id: seg
    property var opcoes: []
    property var atual
    property bool habilitado: true
    signal escolhido(var valor)
    implicitHeight: 32
    implicitWidth: linha.implicitWidth + 6
    radius: Theme.raioPequeno + 2
    color: Theme.campo
    border.color: Theme.borda
    opacity: habilitado ? 1 : 0.5

    RowLayout {
        id: linha
        anchors.fill: parent
        anchors.margins: 3
        spacing: 2
        Repeater {
            model: seg.opcoes
            delegate: Rectangle {
                id: item
                required property var modelData
                required property int index
                readonly property bool ativo: seg.atual === modelData.valor
                Layout.fillWidth: true
                Layout.fillHeight: true
                implicitWidth: rotulo.implicitWidth + 22
                radius: Theme.raioPequeno
                color: ativo ? Theme.realce : (area.containsMouse && seg.habilitado ? Qt.rgba(1, 1, 1, 0.03) : "transparent")
                border.width: ativo ? 1 : 0
                border.color: Theme.bordaForte
                Behavior on color { ColorAnimation { duration: Theme.rapido } }
                Text {
                    id: rotulo
                    anchors.centerIn: parent
                    text: item.modelData.texto
                    color: item.ativo ? Theme.texto : Theme.texto2
                    font.pixelSize: Theme.tPequeno
                    font.weight: item.ativo ? Font.DemiBold : Font.Normal
                }
                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: seg.habilitado
                    cursorShape: Qt.PointingHandCursor
                    onClicked: seg.escolhido(item.modelData.valor)
                }
                Dica { visible: area.containsMouse && (item.modelData.dica || "") !== ""; text: item.modelData.dica || "" }
            }
        }
    }
}
