import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Resultados: números com N e teto de erro (separação, qualidade e galeria). Análise consultiva:
// nada aqui altera o acesso nem os parâmetros. Cada aba entra por um Carregador, na primeira vez
// em que é escolhida.
Item {
    id: pagina
    objectName: "paginaResultados"
    readonly property var r: app.v2.resultados
    readonly property var priv: app.v2.privacidade
    readonly property var abas: r && typeof r.abas === "function" ? r.abas() : []
    readonly property int indiceAba: {
        for (var i = 0; i < abas.length; ++i) if (abas[i].valor === r.aba) return i
        return 0
    }

    Confirmacao {
        id: confirmarNomes
        titulo: "Mostrar nomes?"
        texto: "Os nomes ficarão visíveis nas telas de análise até fechar o aplicativo."
        textoConfirmar: "Mostrar nomes"
        icone: "olho"
        onConfirmado: pagina.priv.definirMostrarNomes(true)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: Theme.espacoBloco

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Resultados"
            descricao: "Números com N e teto de erro: separação, qualidade e galeria"
            SeloDemo { compacto: true }
            SeloConsultivo {}
            Chave {
                text: "Mostrar nomes"
                checked: pagina.priv.mostrarNomes === true
                onToggled: {
                    var ligar = checked
                    checked = Qt.binding(function() { return pagina.priv.mostrarNomes === true })
                    if (ligar) confirmarNomes.open()
                    else pagina.priv.definirMostrarNomes(false)
                }
            }
        }

        Abas {
            Layout.fillWidth: true
            opcoes: pagina.abas
            atual: pagina.r.aba
            onEscolhida: function(valor) { pagina.r.definirAba(valor) }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: pagina.indiceAba
            Repeater {
                model: pagina.abas
                delegate: Carregador {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    fonte: modelData.fonte || ""
                    erroVm: modelData.erro || ""
                    ativo: pagina.r.aba === modelData.valor
                }
            }
        }
    }
}
