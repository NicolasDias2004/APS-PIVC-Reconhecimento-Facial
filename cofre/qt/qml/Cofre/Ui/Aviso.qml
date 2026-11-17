import QtQuick
import QtQuick.Layouts

// Faixa de aviso dentro da página. `tipo`: "info", "aviso", "erro" ou "consultivo".
Rectangle {
    id: aviso
    property string tipo: "info"
    property string texto: ""
    property string acao: ""
    property string iconeAcao: ""
    signal acionado()
    readonly property color cor: tipo === "aviso" ? Theme.aviso : (tipo === "erro" ? Theme.perigo : (tipo === "consultivo" ? Theme.texto2 : Theme.acento))
    implicitHeight: linha.implicitHeight + 20
    implicitWidth: 360
    radius: Theme.raio
    color: tipo === "aviso" ? Theme.avisoSuave : (tipo === "erro" ? Theme.perigoSuave : (tipo === "consultivo" ? Theme.elevada : Theme.acentoSuave))
    border.color: tipo === "consultivo" ? Theme.borda : Qt.rgba(cor.r, cor.g, cor.b, 0.26)
    Accessible.role: tipo === "aviso" || tipo === "erro" ? Accessible.AlertMessage : Accessible.StaticText
    Accessible.name: texto

    RowLayout {
        id: linha
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 12; rightMargin: aviso.acao !== "" ? 8 : 12 }
        spacing: 10
        Icone {
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: 1
            nome: aviso.tipo === "aviso" ? "alerta" : (aviso.tipo === "erro" ? "erro" : (aviso.tipo === "consultivo" ? "escudo" : "info"))
            tamanho: 16
            traco: 2
            cor: aviso.cor
        }
        Text {
            Layout.fillWidth: true
            text: aviso.texto
            color: Theme.texto
            font.pixelSize: Theme.tPequeno
            lineHeight: 1.25
            wrapMode: Text.Wrap
        }
        Botao {
            visible: aviso.acao !== ""
            Layout.alignment: Qt.AlignVCenter
            variante: "fantasma"
            compacto: true
            text: aviso.acao
            icone: aviso.iconeAcao
            onClicked: aviso.acionado()
        }
    }
}
