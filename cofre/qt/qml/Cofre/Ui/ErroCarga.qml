import QtQuick
import QtQuick.Layouts

// Reserva de uma tela ou aba nova que não pôde ser carregada (ViewModel indisponível ou QML com erro).
// Ocupa o lugar dela, discreta, sem derrubar o resto do aplicativo.
Item {
    id: erroCarga
    property string titulo: "Esta tela não pôde ser carregada"
    property string detalhe: ""
    implicitWidth: 360
    implicitHeight: coluna.implicitHeight + 32
    Accessible.role: Accessible.AlertMessage
    Accessible.name: titulo + (detalhe !== "" ? ". " + detalhe : "")

    ColumnLayout {
        id: coluna
        anchors.centerIn: parent
        width: Math.min(parent.width - 32, 460)
        spacing: 10
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 48; height: 48; radius: 14
            color: Theme.elevada
            border.color: Theme.borda
            Icone { anchors.centerIn: parent; nome: "alerta"; tamanho: 22; cor: Theme.texto2 }
        }
        Text {
            Layout.fillWidth: true
            text: erroCarga.titulo
            color: Theme.texto
            font.pixelSize: Theme.tDestaque
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
        }
        Text {
            visible: erroCarga.detalhe !== ""
            Layout.fillWidth: true
            text: erroCarga.detalhe
            color: Theme.texto3
            font.pixelSize: Theme.tPequeno
            wrapMode: Text.Wrap
            maximumLineCount: 4
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
