import QtQuick
import QtQuick.Layouts

// Barra 0..1 com marca do limiar (similaridade) ou progresso simples.
Item {
    id: m
    property real valor: 0           // < 0 = sem leitura
    property real limiar: -1         // < 0 = sem marca
    property color cor: valor >= limiar && limiar >= 0 ? Theme.sucesso : (limiar >= 0 ? Theme.perigo : Theme.acento)
    property real altura: 6
    implicitHeight: altura + (limiar >= 0 ? 6 : 0)
    implicitWidth: 200
    Rectangle {
        id: trilho
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
        height: m.altura
        radius: height / 2
        color: Theme.realce
        Rectangle {
            width: m.valor < 0 ? 0 : Math.max(height, parent.width * Math.min(1, m.valor))
            height: parent.height
            radius: parent.radius
            color: m.cor
            visible: m.valor >= 0
            Behavior on width { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: Theme.medio } }
        }
    }
    Rectangle {
        visible: m.limiar >= 0
        x: trilho.width * m.limiar - 1
        anchors.verticalCenter: parent.verticalCenter
        width: 2
        height: m.altura + 8
        radius: 1
        color: Theme.texto
        opacity: 0.85
    }
}
