import QtQuick
import QtQuick.Layouts

// Cabeçalho de página: título, descrição e ações à direita.
RowLayout {
    id: c
    property string titulo: ""
    property string descricao: ""
    default property alias acoes: acoes.data
    spacing: 16
    ColumnLayout {
        spacing: 3
        Layout.fillWidth: true
        Text { text: c.titulo; color: Theme.texto; font.pixelSize: Theme.tTitulo; font.weight: Font.DemiBold }
        Text { visible: c.descricao !== ""; text: c.descricao; color: Theme.texto2; font.pixelSize: Theme.tCorpo; elide: Text.ElideRight; Layout.fillWidth: true }
    }
    RowLayout { id: acoes; spacing: 8 }
}
