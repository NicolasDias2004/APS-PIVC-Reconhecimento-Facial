import QtQuick
import QtQuick.Layouts

// Estado vazio com orientação para a próxima ação.
ColumnLayout {
    id: v
    property string icone: "caixa"
    property string titulo: ""
    property string texto: ""
    property string acao: ""
    property string iconeAcao: ""
    signal acionado()
    spacing: 10
    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        width: 48; height: 48; radius: 14
        color: Theme.elevada
        border.color: Theme.borda
        Icone { anchors.centerIn: parent; nome: v.icone; tamanho: 22; cor: Theme.texto2 }
    }
    Text { Layout.alignment: Qt.AlignHCenter; text: v.titulo; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
    Text {
        Layout.alignment: Qt.AlignHCenter
        Layout.maximumWidth: 380
        text: v.texto
        visible: text !== ""
        color: Theme.texto2
        font.pixelSize: Theme.tCorpo
        wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignHCenter
    }
    Botao {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 4
        visible: v.acao !== ""
        text: v.acao
        icone: v.iconeAcao
        variante: "primario"
        onClicked: v.acionado()
    }
}
