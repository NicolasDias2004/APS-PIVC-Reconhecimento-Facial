import QtQuick
import QtQuick.Shapes

// Indicador de carregamento (arco girando).
Item {
    id: c
    property real tamanho: 20
    property color cor: Theme.acento
    implicitWidth: tamanho
    implicitHeight: tamanho
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        RotationAnimator on rotation { from: 0; to: 360; duration: 900; loops: Animation.Infinite; running: c.visible }
        ShapePath {
            strokeColor: c.cor
            strokeWidth: Math.max(1.5, c.tamanho / 9)
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: c.tamanho / 2; centerY: c.tamanho / 2
                radiusX: c.tamanho / 2 - 2; radiusY: c.tamanho / 2 - 2
                startAngle: 0; sweepAngle: 270
            }
        }
    }
}
