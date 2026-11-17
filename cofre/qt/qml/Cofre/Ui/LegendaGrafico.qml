import QtQuick
import QtQuick.Shapes

// Legenda de gráfico: uma linha de itens { nome, cor, forma?, tracejada?, hachura? }. A amostra é um
// traço (quando o item diz `tracejada`), o marcador (`forma` de 0 a 3) ou um quadrado. `cor` aceita
// o nome usado nos dados ("serie0".."serie3", "neutro", "concedido", "negado".."negado4", "bloqueio",
// "aviso", "texto"), o índice da série ou uma cor pronta.
Flow {
    id: legenda
    property var itens: []
    spacing: 14
    Accessible.role: Accessible.StaticText
    Accessible.name: (itens || []).map(function(item) { return item.nome || "" }).join(", ")

    function corDe(c) {
        if (typeof c === "number") return Theme.corSerie(c)
        if (c === undefined || c === null || c === "") return Theme.neutroDado
        if (c === "concedido") return Theme.sucesso
        if (c === "neutro") return Theme.neutroDado
        if (c === "texto") return Theme.texto
        if (c === "bloqueio") return Theme.texto3
        if (c === "aviso") return Theme.aviso
        if (typeof c === "string" && c.indexOf("negado") === 0) {
            var alfa = [1, 1, 0.78, 0.58, 0.40][Math.max(1, Math.min(4, parseInt(c.slice(6)) || 1))]
            return Qt.rgba(Theme.perigo.r, Theme.perigo.g, Theme.perigo.b, alfa)
        }
        if (typeof c === "string" && c.indexOf("serie") === 0) return Theme.corSerie(parseInt(c.slice(5)) || 0)
        return c
    }

    Repeater {
        model: legenda.itens || []
        delegate: Row {
            id: item
            required property var modelData
            readonly property color cor: legenda.corDe(modelData.cor)
            readonly property bool traco: modelData.tracejada !== undefined
            readonly property int forma: modelData.forma !== undefined && !traco ? modelData.forma % 4 : -1
            spacing: 6
            Item {
                width: 14; height: 14
                anchors.verticalCenter: parent.verticalCenter
                Row {                                   // traço: cheio ou em três pedaços
                    visible: item.traco
                    anchors.centerIn: parent
                    spacing: item.modelData.tracejada === true ? 2 : 0
                    Repeater {
                        model: item.modelData.tracejada === true ? 3 : 1
                        delegate: Rectangle { width: item.modelData.tracejada === true ? 3.4 : 14; height: 2; color: item.cor }
                    }
                }
                Rectangle {                             // quadrado (padrão), círculo, losango ou hachura
                    visible: !item.traco && item.forma !== 2
                    anchors.centerIn: parent
                    width: item.forma === 3 ? 6.5 : 8
                    height: width
                    radius: item.forma === 0 ? 4 : (item.forma === -1 ? 2 : 0)
                    rotation: item.forma === 3 ? 45 : 0
                    color: item.modelData.hachura === true ? Qt.rgba(item.cor.r, item.cor.g, item.cor.b, 0.30) : item.cor
                    border.width: item.modelData.hachura === true ? 1 : 0
                    border.color: item.cor
                }
                Shape {                                 // triângulo
                    visible: !item.traco && item.forma === 2
                    anchors.centerIn: parent
                    width: 9; height: 8
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: "transparent"
                        fillColor: item.cor
                        PathSvg { path: "M4.5 0L9 8H0z" }
                    }
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: item.modelData.nome || ""
                color: Theme.texto2
                font.pixelSize: Theme.tLegenda
            }
        }
    }
}
