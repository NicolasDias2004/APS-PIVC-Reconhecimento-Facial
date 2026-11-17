import QtQuick
import QtQuick.Layouts

// Selo "Base de demonstração". É o único componente do kit que lê `app`: só aparece quando o banco
// aberto tem o marcador de demonstração (e fica invisível, sem aviso, se `app` ou `app.v2` não existirem).
Rectangle {
    id: selo
    property bool compacto: false
    readonly property bool ativo: typeof app !== "undefined" && app !== null && app.v2 !== undefined && app.v2 !== null
                                  && app.v2.baseDemonstracao === true
    visible: ativo
    implicitHeight: compacto ? 22 : 26
    implicitWidth: linha.implicitWidth + (compacto ? 16 : 22)
    radius: height / 2
    color: Theme.avisoSuave
    border.color: Qt.rgba(Theme.aviso.r, Theme.aviso.g, Theme.aviso.b, 0.30)
    Accessible.role: Accessible.StaticText
    Accessible.name: "Base de demonstração"

    RowLayout {
        id: linha
        anchors.centerIn: parent
        spacing: 6
        Icone { visible: !selo.compacto; nome: "banco"; tamanho: 13; traco: 2; cor: Theme.aviso }
        Text {
            text: "Base de demonstração"
            color: Theme.aviso
            font.pixelSize: Theme.tLegenda
            font.weight: Font.DemiBold
        }
    }
}
