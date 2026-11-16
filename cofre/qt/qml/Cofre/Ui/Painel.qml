import QtQuick
import QtQuick.Layouts

// Superfície elevada com borda sutil. O conteúdo vai para uma ColumnLayout interna.
Rectangle {
    id: p
    default property alias conteudo: corpo.data
    property int preenchimento: 18
    property int espacamento: 12
    property string titulo: ""
    property string subtitulo: ""
    property alias cabecalhoDireita: direita.data
    color: Theme.superficie
    radius: Theme.raioGrande
    border.color: Theme.borda
    implicitHeight: corpo.implicitHeight + 2 * preenchimento + (cab.visible ? cab.implicitHeight + espacamento : 0)
    implicitWidth: Math.max(corpo.implicitWidth, cab.implicitWidth) + 2 * preenchimento

    RowLayout {
        id: cab
        visible: p.titulo !== ""
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: p.preenchimento }
        spacing: 8
        ColumnLayout {
            spacing: 2
            Layout.fillWidth: true
            Text { text: p.titulo; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
            Text { visible: p.subtitulo !== ""; text: p.subtitulo; color: Theme.texto3; font.pixelSize: Theme.tPequeno; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
        RowLayout { id: direita; spacing: 6 }
    }
    ColumnLayout {
        id: corpo
        spacing: p.espacamento
        anchors {
            left: parent.left; right: parent.right
            top: cab.visible ? cab.bottom : parent.top
            bottom: parent.bottom
            leftMargin: p.preenchimento; rightMargin: p.preenchimento
            topMargin: cab.visible ? p.espacamento : p.preenchimento
            bottomMargin: p.preenchimento
        }
    }
}
