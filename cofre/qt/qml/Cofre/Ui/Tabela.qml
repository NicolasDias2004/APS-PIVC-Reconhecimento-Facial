import QtQuick

// Tabela de colunas fixas das abas de análise. `colunas`: lista de { chave, titulo, largura (px; 0 =
// divide o que sobra), alinhamento ("esq", "dir" ou "centro"), mono }; `linhas`: lista de
// { <chave>: texto pronto }. Sem ordenação e sem edição; se passar da altura, quem usa põe num ScrollView.
Item {
    id: tabela
    property var colunas: []
    property var linhas: []
    property int destaque: -1             // linha realçada por quem usa; -1 = nenhuma
    property string vazio: ""
    signal linhaAcionada(int indice)
    property int cursor: -1               // linha sob o teclado, enquanto a tabela tem o foco
    readonly property int total: (linhas || []).length
    readonly property int realce: activeFocus && cursor >= 0 ? cursor : destaque
    readonly property real espacoColunas: 16
    readonly property real sobra: {
        var lista = colunas || [], fixas = 0, livres = 0
        for (var i = 0; i < lista.length; i++) {
            if (lista[i].largura > 0) fixas += lista[i].largura
            else livres += 1
        }
        return livres > 0 ? Math.max(40, (width - fixas - espacoColunas * Math.max(0, lista.length - 1)) / livres) : 0
    }
    function larguraDe(coluna) { return coluna.largura > 0 ? coluna.largura : sobra }
    function alinhar(coluna) {
        return coluna.alinhamento === "dir" ? Text.AlignRight : (coluna.alinhamento === "centro" ? Text.AlignHCenter : Text.AlignLeft)
    }
    function mover(passo) {
        if (total === 0) return
        var de = cursor >= 0 ? cursor : (destaque >= 0 ? destaque : (passo > 0 ? -1 : total))
        cursor = Math.max(0, Math.min(total - 1, de + passo))
    }
    implicitWidth: {
        var lista = colunas || [], soma = 0
        for (var i = 0; i < lista.length; i++) soma += lista[i].largura > 0 ? lista[i].largura : 120
        return soma + espacoColunas * Math.max(0, lista.length - 1)
    }
    implicitHeight: cabecalho.height + (total > 0 ? total * Theme.linhaTabela : (vazio !== "" ? 56 : 0))
    activeFocusOnTab: true
    Accessible.role: Accessible.Table
    Accessible.name: (colunas || []).map(function(c) { return c.titulo || "" }).join(", ")
    Keys.onUpPressed: mover(-1)
    Keys.onDownPressed: mover(1)
    Keys.onReturnPressed: if (realce >= 0) linhaAcionada(realce)
    Keys.onEnterPressed: if (realce >= 0) linhaAcionada(realce)
    onActiveFocusChanged: if (!activeFocus) cursor = -1
    onTotalChanged: if (cursor >= total) cursor = -1

    Item {
        id: cabecalho
        width: parent.width
        height: 30
        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: tabela.espacoColunas
            Repeater {
                model: tabela.colunas || []
                delegate: Text {
                    required property var modelData
                    width: tabela.larguraDe(modelData)
                    text: modelData.titulo || ""
                    color: Theme.texto3
                    font.pixelSize: Theme.tPequeno
                    horizontalAlignment: tabela.alinhar(modelData)
                    elide: Text.ElideRight
                }
            }
        }
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 1
            color: Theme.borda
        }
    }
    Column {
        anchors.top: cabecalho.bottom
        width: parent.width
        Repeater {
            model: tabela.linhas || []
            delegate: Item {
                id: linha
                required property var modelData
                required property int index
                width: tabela.width
                height: Theme.linhaTabela
                Accessible.role: Accessible.Row
                Accessible.name: (tabela.colunas || []).map(function(c) { var v = linha.modelData[c.chave]; return v === undefined || v === null ? "" : String(v) }).join(", ")
                Rectangle {
                    anchors { fill: parent; leftMargin: -8; rightMargin: -8; topMargin: 2; bottomMargin: 3 }
                    radius: Theme.raioPequeno
                    color: tabela.realce === linha.index ? Theme.acentoSuave : (toque.containsMouse ? Theme.hover : "transparent")
                }
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: tabela.espacoColunas
                    Repeater {
                        model: tabela.colunas || []
                        delegate: Text {
                            required property var modelData
                            readonly property var bruto: linha.modelData[modelData.chave]
                            width: tabela.larguraDe(modelData)
                            text: bruto === undefined || bruto === null ? "–" : String(bruto)
                            color: Theme.texto
                            font.pixelSize: modelData.mono === true ? Theme.tPequeno : Theme.tCorpo
                            font.family: modelData.mono === true ? Theme.familiaMono : Theme.familia
                            font.features: { "tnum": modelData.alinhamento === "dir" ? 1 : 0 }
                            horizontalAlignment: tabela.alinhar(modelData)
                            elide: modelData.mono === true ? Text.ElideMiddle : Text.ElideRight
                        }
                    }
                }
                Rectangle {
                    visible: linha.index < tabela.total - 1
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: 1
                    color: Theme.borda
                }
                MouseArea {
                    id: toque
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: tabela.linhaAcionada(linha.index)
                }
            }
        }
    }
    Text {
        visible: tabela.total === 0 && tabela.vazio !== ""
        anchors { top: cabecalho.bottom; left: parent.left; right: parent.right }
        height: 56
        text: tabela.vazio
        color: Theme.texto3
        font.pixelSize: Theme.tPequeno
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.Wrap
    }
    Rectangle {        // anel de foco do teclado
        anchors.fill: parent
        anchors.margins: -6
        radius: Theme.raio
        color: "transparent"
        border.width: 2
        border.color: Theme.acento
        opacity: tabela.activeFocus ? 0.7 : 0
    }
}
