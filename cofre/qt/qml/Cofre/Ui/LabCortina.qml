import QtQuick

// Duas imagens sobrepostas e uma alça vertical arrastável: à esquerda a original, à direita a
// equalizada. ← → movem a alça com foco.
Rectangle {
    id: cortina
    property url esquerda
    property url direita
    property string rotuloEsquerda: "Original"
    property string rotuloDireita: "CLAHE"
    property real posicao: 0.5
    implicitWidth: 480
    implicitHeight: 300
    radius: Theme.raio
    color: Theme.campo
    border.color: activeFocus ? Theme.bordaForte : Theme.borda
    clip: true
    activeFocusOnTab: true
    Accessible.role: Accessible.Slider
    Accessible.name: "Comparação " + rotuloEsquerda + " e " + rotuloDireita
    Keys.onLeftPressed: posicao = Math.max(0, posicao - 0.05)
    Keys.onRightPressed: posicao = Math.min(1, posicao + 0.05)

    Image {
        id: imgEsq
        anchors.fill: parent
        anchors.margins: 1
        source: cortina.esquerda
        fillMode: Image.PreserveAspectFit
        asynchronous: false
        cache: false
        smooth: true
    }
    Item {
        id: recorte
        x: 1 + (cortina.width - 2) * cortina.posicao
        y: 1
        width: cortina.width - 1 - x
        height: cortina.height - 2
        clip: true
        Image {
            x: -recorte.x + 1
            width: cortina.width - 2
            height: recorte.height
            source: cortina.direita
            fillMode: Image.PreserveAspectFit
            cache: false
            smooth: true
        }
    }
    Rectangle {
        id: alca
        x: recorte.x - 1
        width: 2
        height: parent.height
        color: Theme.texto
        opacity: 0.85
        Rectangle {
            anchors.centerIn: parent
            width: 18; height: 34; radius: 9
            color: Theme.elevada
            border.color: cortina.activeFocus ? Theme.acento : Theme.bordaForte
            border.width: cortina.activeFocus ? 2 : 1
        }
    }
    Rectangle {
        anchors { left: parent.left; top: parent.top; margins: 10 }
        width: t1.implicitWidth + 14; height: 22; radius: 6
        color: Theme.vidro
        Text { id: t1; anchors.centerIn: parent; text: cortina.rotuloEsquerda; color: Theme.texto; font.pixelSize: Theme.tLegenda }
    }
    Rectangle {
        anchors { right: parent.right; top: parent.top; margins: 10 }
        width: t2.implicitWidth + 14; height: 22; radius: 6
        color: Theme.vidro
        Text { id: t2; anchors.centerIn: parent; text: cortina.rotuloDireita; color: Theme.texto; font.pixelSize: Theme.tLegenda }
    }
    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.SplitHCursor
        function mover(mx) { cortina.posicao = Math.max(0, Math.min(1, mx / Math.max(1, cortina.width))) }
        onPressed: function(ev) { cortina.forceActiveFocus(); mover(ev.x) }
        onPositionChanged: function(ev) { if (pressed) mover(ev.x) }
    }
}
