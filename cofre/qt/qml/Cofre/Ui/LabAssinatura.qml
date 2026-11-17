import QtQuick
import QtQuick.Layouts

// Assinatura do descritor: as 128 barras já vêm desenhadas do Python como imagem
// (image://cofre/lab/fases/assinatura). Nenhum número do vetor passa pelo QML.
Rectangle {
    id: ass
    property url fonte
    implicitWidth: 420
    implicitHeight: 130
    radius: Theme.raio
    color: Theme.superficie
    border.color: Theme.borda
    Accessible.role: Accessible.Graphic
    Accessible.name: "Assinatura do descritor: 128 barras"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 6
        Text { text: "Assinatura do descritor · 128 dimensões"; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
        Image {
            Layout.fillWidth: true
            Layout.fillHeight: true
            source: ass.fonte
            fillMode: Image.Stretch
            cache: false
            smooth: false
        }
    }
}
