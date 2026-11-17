import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Painel de segurança: o que o terminal decidiu, com que folga, e se o registro confere.
// Só lê o registro: nada aqui participa da decisão de acesso. Cada aba entra por um Carregador,
// na primeira vez em que é escolhida.
Item {
    id: pagina
    objectName: "paginaPainel"
    readonly property var p: app.v2.painel
    readonly property var priv: app.v2.privacidade
    readonly property var abas: p && typeof p.abas === "function" ? p.abas() : []
    readonly property int indiceAba: {
        for (var i = 0; i < abas.length; ++i) if (abas[i].valor === p.aba) return i
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
            titulo: "Painel de segurança"
            descricao: "O que o terminal decidiu, com que folga, e se o registro confere"
            SeloDemo { compacto: true }
            Segmentado {
                atual: pagina.p.periodo || "tudo"
                opcoes: [
                    { valor: "24h", texto: "24 h", dica: "Últimas 24 horas" },
                    { valor: "7d", texto: "7 dias" },
                    { valor: "30d", texto: "30 dias" },
                    { valor: "tudo", texto: "Tudo", dica: "Todo o registro" }
                ]
                onEscolhido: function(valor) { pagina.p.definirPeriodo(valor) }
            }
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
            BotaoIcone { icone: "recarregar"; dica: "Atualizar"; onClicked: pagina.p.atualizar() }
        }

        SeloConsultivo { texto: "Leitura do registro · não altera o acesso" }

        Abas {
            Layout.fillWidth: true
            opcoes: pagina.abas
            atual: pagina.p.aba
            onEscolhida: function(valor) { pagina.p.definirAba(valor) }
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
                    ativo: pagina.p.aba === modelData.valor
                }
            }
        }
    }
}
