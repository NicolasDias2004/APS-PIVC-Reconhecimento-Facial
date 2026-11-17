import QtQuick

// Linha de abas com sublinhado que desliza. `opcoes`: lista de { valor, texto, contador?, erro? }.
// Não guarda estado: quem usa devolve `atual` ao receber `escolhida`.
Item {
    id: abas
    property var opcoes: []
    property var atual
    signal escolhida(var valor)
    property Item itemAtivo: null
    property bool pronto: false
    readonly property int indiceAtual: {
        var lista = opcoes || []
        for (var i = 0; i < lista.length; i++)
            if (lista[i].valor === atual) return i
        return -1
    }
    function mover(passo) {
        var lista = opcoes || []
        if (lista.length === 0) return
        var i = indiceAtual < 0 ? 0 : (indiceAtual + passo + lista.length) % lista.length
        escolhida(lista[i].valor)
    }
    implicitHeight: 38
    implicitWidth: linha.implicitWidth
    activeFocusOnTab: true
    Accessible.role: Accessible.PageTabList
    Accessible.name: "Abas"
    Keys.onLeftPressed: mover(-1)
    Keys.onRightPressed: mover(1)
    Component.onCompleted: pronto = true

    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 1
        color: Theme.borda
    }
    Row {
        id: linha
        height: parent.height
        spacing: 22
        Repeater {
            model: abas.opcoes || []
            delegate: Item {
                id: aba
                required property var modelData
                readonly property bool ativa: abas.atual === modelData.valor
                readonly property string contador: modelData.contador !== undefined && modelData.contador !== null ? String(modelData.contador) : ""
                width: conteudo.width
                height: linha.height
                Accessible.role: Accessible.PageTab
                Accessible.name: modelData.texto || ""
                Binding { target: abas; property: "itemAtivo"; value: aba; when: aba.ativa }
                TextMetrics { id: medida; text: aba.modelData.texto || ""; font.pixelSize: Theme.tCorpo; font.weight: Font.DemiBold }
                Row {
                    id: conteudo
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    Text {
                        width: Math.ceil(medida.advanceWidth) + 1      // a largura do negrito: a aba não muda de tamanho ao ser escolhida
                        anchors.verticalCenter: parent.verticalCenter
                        text: aba.modelData.texto || ""
                        color: aba.ativa || toque.containsMouse ? Theme.texto : Theme.texto2
                        font.pixelSize: Theme.tCorpo
                        font.weight: aba.ativa ? Font.DemiBold : Font.Normal
                        Behavior on color { ColorAnimation { duration: Theme.rapido } }
                    }
                    Text {
                        visible: aba.contador !== ""
                        anchors.verticalCenter: parent.verticalCenter
                        text: aba.contador
                        color: Theme.texto3
                        font.pixelSize: Theme.tLegenda
                        font.features: { "tnum": 1 }
                    }
                    Rectangle {
                        visible: !!aba.modelData.erro
                        anchors.verticalCenter: parent.verticalCenter
                        width: 6; height: 6; radius: 3
                        color: Theme.aviso
                    }
                }
                MouseArea {
                    id: toque
                    anchors.fill: parent
                    anchors.margins: -8
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: abas.escolhida(aba.modelData.valor)
                }
            }
        }
    }
    Rectangle {
        visible: abas.itemAtivo !== null
        x: abas.itemAtivo ? abas.itemAtivo.x : 0
        width: abas.itemAtivo ? abas.itemAtivo.width : 0
        anchors.bottom: parent.bottom
        height: 2
        radius: 1
        color: Theme.acento
        Behavior on x { enabled: abas.pronto; NumberAnimation { duration: Theme.rapido; easing.type: Easing.OutCubic } }
        Behavior on width { enabled: abas.pronto; NumberAnimation { duration: Theme.rapido; easing.type: Easing.OutCubic } }
    }
    Rectangle {        // anel de foco do teclado
        anchors.fill: parent
        anchors.margins: -3
        radius: Theme.raioPequeno
        color: "transparent"
        border.width: 2
        border.color: Theme.acento
        opacity: abas.activeFocus ? 0.7 : 0
    }
}
