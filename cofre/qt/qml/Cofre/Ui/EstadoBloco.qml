import QtQuick
import QtQuick.Layouts

// Estado de um bloco de análise: vazio, carregando, erro ou indisponível. Em "pronto" e "poucos" some.
// Uso: EstadoBloco { anchors.fill: parent; estado: vm.estado; erro: vm.erro; ... } por cima do conteúdo.
Item {
    id: bloco
    property string estado: "pronto"      // vazio | carregando | pronto | poucos | erro | indisponivel
    property string erro: ""
    property string vazioIcone: "caixa"
    property string vazioTitulo: ""
    property string vazioTexto: ""
    property string vazioAcao: ""
    property real progresso: -1           // 0..1; -1 = indeterminado
    property bool cancelavel: false
    signal acionado()
    signal tentarNovamente()
    signal cancelar()
    visible: estado === "vazio" || estado === "carregando" || estado === "erro" || estado === "indisponivel"
    implicitWidth: 320
    implicitHeight: coluna.implicitHeight + 32

    ColumnLayout {
        id: coluna
        anchors.centerIn: parent
        width: Math.min(parent.width - 32, 440)
        spacing: 10

        // vazio: o mesmo desenho do `Vazio`, que não cabe aqui porque tem largura mínima de 380 px
        Rectangle {
            visible: bloco.estado === "vazio"
            Layout.alignment: Qt.AlignHCenter
            width: 48; height: 48; radius: 14
            color: Theme.elevada
            border.color: Theme.borda
            Icone { anchors.centerIn: parent; nome: bloco.vazioIcone; tamanho: 22; cor: Theme.texto2 }
        }
        Text {
            visible: bloco.estado === "vazio" && text !== ""
            Layout.fillWidth: true
            text: bloco.vazioTitulo
            color: Theme.texto
            font.pixelSize: Theme.tDestaque
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
        }
        Text {
            visible: bloco.estado === "vazio" && text !== ""
            Layout.fillWidth: true
            Layout.maximumWidth: 380
            Layout.alignment: Qt.AlignHCenter
            text: bloco.vazioTexto
            color: Theme.texto2
            font.pixelSize: Theme.tCorpo
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
        }
        Botao {
            visible: bloco.estado === "vazio" && bloco.vazioAcao !== ""
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 4
            variante: "primario"
            text: bloco.vazioAcao
            onClicked: bloco.acionado()
        }

        Carregando { visible: bloco.estado === "carregando"; Layout.alignment: Qt.AlignHCenter; tamanho: 22 }
        Text {
            visible: bloco.estado === "carregando"
            Layout.alignment: Qt.AlignHCenter
            text: "Calculando…"
            color: Theme.texto2
            font.pixelSize: Theme.tCorpo
        }
        BarraSimilaridade {
            visible: bloco.estado === "carregando" && bloco.progresso >= 0
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Math.min(200, coluna.width)
            altura: 4
            valor: bloco.progresso
            descricao: "Progresso " + Math.round(Math.max(0, Math.min(1, bloco.progresso)) * 100) + " %"
        }
        Botao {
            visible: bloco.estado === "carregando" && bloco.cancelavel
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 2
            variante: "fantasma"
            compacto: true
            text: "Cancelar"
            onClicked: bloco.cancelar()
        }

        Rectangle {
            visible: bloco.estado === "erro"
            Layout.alignment: Qt.AlignHCenter
            width: 48; height: 48; radius: 14
            color: Theme.perigoSuave
            border.color: Qt.rgba(Theme.perigo.r, Theme.perigo.g, Theme.perigo.b, 0.26)
            Icone { anchors.centerIn: parent; nome: "alerta"; tamanho: 22; cor: Theme.perigo }
        }
        Text {
            visible: bloco.estado === "erro"
            Layout.alignment: Qt.AlignHCenter
            text: "Não foi possível calcular"
            color: Theme.texto
            font.pixelSize: Theme.tDestaque
            font.weight: Font.DemiBold
            Accessible.role: Accessible.AlertMessage
            Accessible.name: text + ". " + bloco.erro
        }
        Text {
            visible: (bloco.estado === "erro" || bloco.estado === "indisponivel") && bloco.erro !== ""
            Layout.fillWidth: true
            text: bloco.erro
            color: Theme.texto2
            font.pixelSize: Theme.tCorpo
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
        }
        Botao {
            visible: bloco.estado === "erro"
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 4
            text: "Tentar novamente"
            icone: "recarregar"
            onClicked: bloco.tentarNovamente()
        }
    }
}
