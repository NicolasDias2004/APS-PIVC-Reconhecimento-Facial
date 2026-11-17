import QtQuick

// Barra de 0 a 1 para similaridade e progresso nas telas novas. A cor é a do chamador (turquesa por
// padrão): quem diz se passou do limiar é o texto ao lado, nunca a cor da barra.
Item {
    id: barra
    property real valor: 0            // < 0 = sem leitura
    property real marca: -1           // limiar em vigor; < 0 = sem marca
    property real marcaEstudo: -1     // limiar de estudo; < 0 = sem marca
    property color cor: Theme.acento
    property real altura: 6
    property string descricao: ""
    readonly property bool temMarca: marca >= 0 || marcaEstudo >= 0
    implicitHeight: altura + (temMarca ? 8 : 0)
    implicitWidth: 200
    Accessible.role: Accessible.ProgressBar
    Accessible.name: descricao !== "" ? descricao : (valor < 0 ? "Sem leitura" : Math.round(Math.min(1, valor) * 100) + " %")

    Rectangle {
        id: trilho
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
        height: barra.altura
        radius: height / 2
        color: Theme.realce
        Rectangle {
            visible: barra.valor >= 0
            width: barra.valor < 0 ? 0 : Math.max(height, parent.width * Math.min(1, barra.valor))
            height: parent.height
            radius: parent.radius
            color: barra.cor
            Behavior on width { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
        }
    }
    Column {                           // limiar de estudo: traço pontilhado
        visible: barra.marcaEstudo >= 0
        x: Math.round(trilho.width * Math.min(1, barra.marcaEstudo)) - 1
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Repeater {
            model: Math.max(1, Math.floor((barra.altura + 10) / 4))
            delegate: Rectangle { width: 2; height: 2; radius: 1; color: Theme.texto2 }
        }
    }
    Rectangle {                        // limiar em vigor: traço cheio
        visible: barra.marca >= 0
        x: Math.round(trilho.width * Math.min(1, barra.marca)) - 1
        anchors.verticalCenter: parent.verticalCenter
        width: 2
        height: barra.altura + 8
        radius: 1
        color: Theme.texto
    }
}
