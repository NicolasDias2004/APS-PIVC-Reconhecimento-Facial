import QtQuick
import QtQuick.Shapes
import "Icones.js" as Icones

// Ícone vetorial em traço. `nome` vem de Icones.js.
Item {
    id: raiz
    property string nome: ""
    property color cor: Theme.texto2
    property real tamanho: 18
    property real traco: 1.8
    implicitWidth: tamanho
    implicitHeight: tamanho

    Shape {
        width: 24; height: 24
        scale: raiz.tamanho / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        visible: raiz.nome !== ""
        ShapePath {
            strokeColor: raiz.cor
            strokeWidth: raiz.traco
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: Icones.caminho(raiz.nome) }
        }
    }
}
