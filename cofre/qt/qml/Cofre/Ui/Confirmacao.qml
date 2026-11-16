import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Diálogo modal de confirmação (ações destrutivas usam perigo: true).
Popup {
    id: d
    property string titulo: ""
    property string texto: ""
    property string textoConfirmar: "Confirmar"
    property bool perigo: false
    property string icone: perigo ? "alerta" : "info"
    signal confirmado()
    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(440, parent ? parent.width - 48 : 440)
    padding: 22
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.55) }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.medio }
            NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.medio; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.rapido } }
    background: Rectangle { radius: Theme.raioGrande; color: Theme.elevada; border.color: Theme.bordaForte }
    contentItem: ColumnLayout {
        spacing: 14
        RowLayout {
            spacing: 12
            Rectangle {
                width: 36; height: 36; radius: 10
                color: d.perigo ? Theme.perigoSuave : Theme.acentoSuave
                Icone { anchors.centerIn: parent; nome: d.icone; tamanho: 18; cor: d.perigo ? Theme.perigo : Theme.acento }
            }
            Text { text: d.titulo; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
        Text { text: d.texto; color: Theme.texto2; font.pixelSize: Theme.tCorpo; wrapMode: Text.Wrap; Layout.fillWidth: true; lineHeight: 1.15 }
        RowLayout {
            Layout.topMargin: 6
            spacing: 8
            Item { Layout.fillWidth: true }
            Botao { text: "Cancelar"; onClicked: d.close() }
            Botao {
                id: confirmar
                text: d.textoConfirmar
                variante: d.perigo ? "perigo" : "primario"
                onClicked: { d.close(); d.confirmado() }
            }
        }
    }
    onOpened: confirmar.forceActiveFocus()
}
