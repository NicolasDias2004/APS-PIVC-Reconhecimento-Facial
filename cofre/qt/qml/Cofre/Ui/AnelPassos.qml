import QtQuick
import QtQuick.Shapes

// Três arcos da prova de vida (esquerda, direita, piscar): feito, atual e por fazer.
Item {
    id: ap
    property int feitos: 0
    property int atual: 0
    property color cor: Theme.acento
    property real espessura: 3
    readonly property real r: Math.min(width, height) / 2 - espessura - 1
    implicitWidth: 120
    implicitHeight: 120
    Accessible.role: Accessible.ProgressBar
    Accessible.name: "Prova de vida: passo " + (atual + 1) + " de 3"
    function corDe(i) { return i < feitos ? cor : (i === atual ? Qt.rgba(cor.r, cor.g, cor.b, 0.45) : Theme.trilho) }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath { strokeColor: ap.corDe(0); strokeWidth: ap.espessura; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: ap.width / 2; centerY: ap.height / 2; radiusX: ap.r; radiusY: ap.r; startAngle: 126; sweepAngle: 108 } }
        ShapePath { strokeColor: ap.corDe(1); strokeWidth: ap.espessura; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: ap.width / 2; centerY: ap.height / 2; radiusX: ap.r; radiusY: ap.r; startAngle: -54; sweepAngle: 108 } }
        ShapePath { strokeColor: ap.corDe(2); strokeWidth: ap.espessura; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: ap.width / 2; centerY: ap.height / 2; radiusX: ap.r; radiusY: ap.r; startAngle: 246; sweepAngle: 48 } }
    }
}
