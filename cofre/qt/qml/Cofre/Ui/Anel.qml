import QtQuick
import QtQuick.Shapes

// Anel de leitura de 0 a 1 com a marca do limiar. É o gesto forte das telas novas: usa-se um por bloco.
Item {
    id: anel
    property real valor: 0            // 0..1
    property real marca: -1           // 0..1; < 0 = sem marca
    property color cor: Theme.acento
    property color trilho: Theme.trilho
    property real espessura: 3
    property real inicio: -90         // ângulo de partida em graus (-90 = no alto)
    property string descricao: ""
    readonly property real r: Math.min(width, height) / 2 - espessura - 1
    implicitWidth: 120
    implicitHeight: 120
    Accessible.role: Accessible.ProgressBar
    Accessible.name: descricao
    Behavior on valor { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: anel.trilho; strokeWidth: 1.5; fillColor: "transparent"
            PathAngleArc { centerX: anel.width / 2; centerY: anel.height / 2; radiusX: anel.r; radiusY: anel.r; startAngle: 0; sweepAngle: 360 }
        }
        ShapePath {
            strokeColor: anel.valor > 0 ? anel.cor : "transparent"; strokeWidth: anel.espessura; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: anel.width / 2; centerY: anel.height / 2; radiusX: anel.r; radiusY: anel.r
                startAngle: anel.inicio; sweepAngle: 360 * Math.max(0, Math.min(1, anel.valor)) }
        }
    }
    Rectangle {                        // marca do limiar: traço radial curto
        visible: anel.marca >= 0
        width: 2; height: anel.espessura + 9; radius: 1; color: Theme.texto
        x: anel.width / 2 - 1; y: anel.height / 2 - anel.r - height / 2
        transform: Rotation { origin.x: 1; origin.y: anel.r + (anel.espessura + 9) / 2; angle: 360 * anel.marca + anel.inicio + 90 }
    }
}
