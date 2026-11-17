import QtQuick
import QtQuick.Layouts

// Uma regra do registro: id, título, selo "Consultiva" quando for, e a marca da contagem.
// "confere" em turquesa (leitura consultiva, nunca verde); violação em vermelho; consultiva em âmbar.
Rectangle {
    id: regra
    property string ident: ""
    property string titulo: ""
    property bool consultiva: false
    property string situacao: "confere"     // confere | viola | observar
    property string marca: "confere"
    property string garantia: ""
    property string observacao: ""
    property string exemplos: ""
    readonly property color corMarca: situacao === "viola" ? Theme.perigo : (situacao === "observar" ? Theme.aviso : Theme.acento)

    implicitWidth: 520
    implicitHeight: Theme.linhaTabela
    color: sobre.hovered ? Theme.hover : "transparent"
    radius: Theme.raioPequeno
    Accessible.role: Accessible.StaticText
    Accessible.name: ident + ", " + titulo + (consultiva ? ", consultiva" : "") + ": " + marca

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        spacing: 12
        Text {
            Layout.preferredWidth: 34
            text: regra.ident
            color: Theme.texto3
            font.pixelSize: Theme.tPequeno
            font.family: Theme.familiaMono
        }
        Text {
            Layout.fillWidth: true
            text: regra.titulo
            color: Theme.texto
            font.pixelSize: Theme.tCorpo
            elide: Text.ElideRight
        }
        Selo { visible: regra.consultiva; texto: "Consultiva"; cor: Theme.texto2 }
        RowLayout {
            spacing: 6
            Rectangle { width: 7; height: 7; radius: 3.5; color: regra.corMarca; Layout.alignment: Qt.AlignVCenter }
            Text {
                text: regra.marca
                color: regra.corMarca
                font.pixelSize: Theme.tPequeno
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
            }
        }
    }
    Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 1; color: Theme.borda }
    HoverHandler { id: sobre }
    Dica {
        visible: sobre.hovered
        text: "Garantia: " + regra.garantia + (regra.observacao !== "" ? "\n" + regra.observacao : "")
              + (regra.exemplos !== "" ? "\nExemplos: " + regra.exemplos : "")
    }
}
