import QtQuick
import QtQuick.Layouts

// Postura dos controles do terminal (só leitura dos valores em vigor no backend) e o diagnóstico do
// ambiente. "ok" é turquesa, nunca verde: é uma leitura consultiva, não uma decisão de acesso.
Painel {
    id: postura
    property var linhas: []
    property var diagnostico: []
    property bool diagnosticando: false
    signal diagnosticar()
    signal abrirConfiguracoes()
    signal verSeparacao()
    signal verSaudeCadastro()

    function corSituacao(s) {
        if (s === "ok") return Theme.acento
        if (s === "aviso" || s === "atencao") return Theme.aviso
        if (s === "falha") return Theme.perigo
        return Theme.texto3
    }

    titulo: "Postura dos controles"
    subtitulo: "Valores em vigor no terminal"
    espacamento: 8

    Repeater {
        model: postura.linhas || []
        delegate: ColumnLayout {
            required property var modelData
            Layout.fillWidth: true
            spacing: 1
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Rectangle {
                    Layout.alignment: Qt.AlignVCenter
                    width: 7; height: 7; radius: 3.5
                    color: postura.corSituacao(modelData.situacao)
                }
                Text {
                    Layout.fillWidth: true
                    text: modelData.rotulo || ""
                    color: Theme.texto2
                    font.pixelSize: Theme.tPequeno
                    elide: Text.ElideRight
                }
                Text {
                    visible: (modelData.fabrica || "") !== ""
                    text: "padrão " + (modelData.fabrica || "")
                    color: Theme.texto3
                    font.pixelSize: Theme.tLegenda
                    font.features: { "tnum": 1 }
                }
                Text {
                    Layout.maximumWidth: postura.width * 0.5
                    text: modelData.valor || "–"
                    color: modelData.situacao === "aviso" ? Theme.aviso : Theme.texto
                    font.pixelSize: Theme.tCorpo
                    font.features: { "tnum": 1 }
                    elide: Text.ElideMiddle
                }
            }
            Botao {
                objectName: "botaoVerSeparacao"
                visible: modelData.chave === "limiar"
                Layout.leftMargin: 9
                text: "Ver a separação medida"
                icone: "resultados"
                variante: "fantasma"
                compacto: true
                onClicked: postura.verSeparacao()
            }
            Text {
                visible: (modelData.texto || "") !== ""
                Layout.fillWidth: true
                Layout.leftMargin: 15
                text: modelData.texto || ""
                color: Theme.texto3
                font.pixelSize: Theme.tLegenda
                wrapMode: Text.Wrap
            }
            Accessible.role: Accessible.StaticText
            Accessible.name: (modelData.rotulo || "") + ": " + (modelData.valor || "")
        }
    }

    Flow {
        Layout.fillWidth: true
        Layout.topMargin: 6
        spacing: 8
        Botao {
            objectName: "botaoDiagnostico"
            text: "Executar diagnóstico"
            icone: "pulso"
            compacto: true
            carregando: postura.diagnosticando
            enabled: !postura.diagnosticando
            onClicked: postura.diagnosticar()
        }
        Botao {
            text: "Abrir Configurações"
            icone: "config"
            variante: "fantasma"
            compacto: true
            onClicked: postura.abrirConfiguracoes()
        }
        Botao {
            objectName: "botaoVerSaudeCadastro"
            text: "Ver saúde do cadastro"
            icone: "usuarios"
            variante: "fantasma"
            compacto: true
            onClicked: postura.verSaudeCadastro()
        }
    }

    Text {
        visible: (postura.diagnostico || []).length > 0
        Layout.topMargin: 4
        text: "Diagnóstico"
        color: Theme.texto
        font.pixelSize: Theme.tCorpo
        font.weight: Font.DemiBold
    }
    Repeater {
        model: postura.diagnostico || []
        delegate: RowLayout {
            required property var modelData
            Layout.fillWidth: true
            spacing: 8
            Rectangle {
                Layout.alignment: Qt.AlignVCenter
                width: 7; height: 7; radius: 3.5
                color: postura.corSituacao(modelData.situacao)
            }
            Text {
                Layout.fillWidth: true
                text: modelData.item || ""
                color: Theme.texto2
                font.pixelSize: Theme.tPequeno
                elide: Text.ElideRight
            }
            Text {
                Layout.maximumWidth: postura.width * 0.55
                text: modelData.valor || "–"
                color: Theme.texto
                font.pixelSize: Theme.tPequeno
                font.features: { "tnum": 1 }
                elide: Text.ElideMiddle
            }
            Accessible.role: Accessible.StaticText
            Accessible.name: (modelData.item || "") + ": " + (modelData.valor || "")
        }
    }
}
