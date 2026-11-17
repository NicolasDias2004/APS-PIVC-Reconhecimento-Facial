import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Deslizante com rótulo, valor e a marca do valor do sistema. Não guarda estado: emite `movido` e
// mostra o `valor` que o ViewModel devolver. Fora do padrão, o número fica âmbar.
ColumnLayout {
    id: d
    property string rotulo: ""
    property real valor: 0
    property real minimo: 0
    property real maximo: 1
    property real passo: 0.01
    property real padrao: NaN         // valor do sistema; NaN = sem marca
    property int casas: 2
    property string sufixo: ""
    property bool habilitado: true
    signal movido(real valor)
    readonly property bool temPadrao: !isNaN(padrao)
    readonly property bool foraDoPadrao: temPadrao && Math.abs(valor - padrao) > Math.max(passo / 2, 1e-9)
    function escrever(v) { return Number(v).toLocaleString(Qt.locale("pt_BR"), "f", casas) + sufixo }
    function fracao(v) { return maximo > minimo ? Math.max(0, Math.min(1, (v - minimo) / (maximo - minimo))) : 0 }
    spacing: 4
    implicitWidth: 240

    RowLayout {
        spacing: 8
        Text { text: d.rotulo; color: d.habilitado ? Theme.texto2 : Theme.texto3; font.pixelSize: Theme.tPequeno; elide: Text.ElideRight; Layout.fillWidth: true }
        Text {
            text: d.escrever(d.valor)
            color: !d.habilitado ? Theme.texto3 : (d.foraDoPadrao ? Theme.aviso : Theme.texto)
            font.pixelSize: Theme.tPequeno
            font.weight: Font.DemiBold
            font.features: { "tnum": 1 }
        }
    }
    Slider {
        id: s
        Layout.fillWidth: true
        implicitHeight: 22
        padding: 0
        from: d.minimo
        to: d.maximo
        stepSize: d.passo
        snapMode: Slider.SnapAlways
        value: d.valor
        enabled: d.habilitado
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        readonly property real curso: availableWidth - 14          // caminho do centro da alça
        Accessible.name: d.rotulo
        Accessible.description: "Valor " + d.escrever(d.valor) + (d.temPadrao ? ", padrão do sistema " + d.escrever(d.padrao) : "")
        onMoved: {
            d.movido(value)
            value = Qt.binding(function() { return d.valor })      // volta a mostrar o que o ViewModel devolveu
        }
        Keys.onPressed: function(evento) {
            if (evento.key === Qt.Key_Backspace && d.temPadrao) {
                d.movido(d.padrao)
                evento.accepted = true
            }
        }
        background: Item {
            x: s.leftPadding
            y: s.topPadding + s.availableHeight / 2 - height / 2
            width: s.availableWidth
            height: 14
            Rectangle {
                id: trilho
                width: parent.width; height: 4; radius: 2
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.realce
                Rectangle {
                    width: 7 + s.visualPosition * s.curso
                    height: parent.height
                    radius: 2
                    color: s.enabled ? Theme.acento : Theme.texto3
                }
            }
            Rectangle {            // tique do valor do sistema
                visible: d.temPadrao
                x: 7 + d.fracao(d.padrao) * s.curso - 1
                anchors.verticalCenter: parent.verticalCenter
                width: 2; height: 12; radius: 1
                color: Theme.texto2
            }
        }
        handle: Rectangle {
            x: s.leftPadding + s.visualPosition * s.curso
            y: s.topPadding + s.availableHeight / 2 - height / 2
            width: 14; height: 14; radius: 7
            color: s.enabled ? (s.pressed ? Theme.acento : Theme.texto) : Theme.texto3
            border.width: 2
            border.color: Theme.superficie
            Rectangle {        // anel de foco do teclado
                anchors.fill: parent
                anchors.margins: -3
                radius: 10
                color: "transparent"
                border.width: 2
                border.color: Theme.acento
                opacity: s.visualFocus ? 0.7 : 0
            }
        }
    }
}
