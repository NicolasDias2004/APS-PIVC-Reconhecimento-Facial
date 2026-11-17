import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Aba Visão geral do Painel de segurança: o que o terminal decidiu, com que folga em relação ao
// limiar e em que estado estão os controles. Um traço por tentativa; nada aqui altera o acesso.
Item {
    id: aba
    objectName: "abaPainelGeral"
    readonly property var vm: app.v2.painelGeral
    readonly property string estado: vm && vm.estado !== undefined ? vm.estado : "vazio"
    readonly property bool temDado: estado === "pronto" || estado === "poucos"
    readonly property int nFaixas: vm && vm.fita && vm.fita.faixas ? vm.fita.faixas.length : 0
    readonly property bool estreita: width < 980

    function corSerie(nome) {
        if (nome === "concedido") return Theme.sucesso
        if (nome === "bloqueio") return Theme.texto3
        var alfas = { "negado": 1, "negado2": 0.78, "negado3": 0.58, "negado4": 0.40 }
        return Qt.rgba(Theme.perigo.r, Theme.perigo.g, Theme.perigo.b, alfas[nome] !== undefined ? alfas[nome] : 1)
    }
    function exportar(tipo, dados, nome) { app.v2.figuras.exportar(tipo, dados || ({}), nome) }

    ScrollView {
        id: rolagem
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
            width: rolagem.availableWidth
            spacing: Theme.espacoBloco

            Aviso {
                Layout.fillWidth: true
                visible: aba.estado === "poucos"
                tipo: "aviso"
                texto: "Poucos registros (N = " + (aba.vm.total || 0) + "): leia como tendência"
            }

            // A + B: manchete e composição
            GridLayout {
                Layout.fillWidth: true
                visible: aba.temDado
                columns: aba.estreita ? 1 : 2
                columnSpacing: Theme.espacoBloco
                rowSpacing: Theme.espacoBloco

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 58
                    Layout.alignment: Qt.AlignTop
                    spacing: 8
                    Text {
                        objectName: "mancheteGeral"
                        Layout.fillWidth: true
                        text: aba.vm.manchete || ""
                        color: Theme.texto
                        font.pixelSize: Theme.tGrande
                        font.weight: Font.DemiBold
                        font.features: { "tnum": 1 }
                        wrapMode: Text.Wrap
                    }
                    Repeater {
                        model: aba.vm.leituras || []
                        delegate: Text {
                            required property var modelData
                            Layout.fillWidth: true
                            text: String(modelData)
                            color: Theme.texto2
                            font.pixelSize: Theme.tCorpo
                            font.features: { "tnum": 1 }
                            wrapMode: Text.Wrap
                        }
                    }
                }
                CartaoGrafico {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 42
                    Layout.alignment: Qt.AlignTop
                    titulo: "Resultado das tentativas"
                    tipo: "barras"
                    altura: 96
                    dados: aba.vm.composicao || ({})
                    estado: aba.estado
                    nomeArquivo: "painel-composicao"
                    legenda: {
                        var s = (aba.vm.composicao && aba.vm.composicao.series) || [], itens = []
                        for (var i = 0; i < s.length; i++)
                            itens.push({ nome: s[i].nome + " " + ((s[i].valores || [0])[0] || 0), cor: aba.corSerie(s[i].cor) })
                        return itens
                    }
                    onExportar: aba.exportar(tipo, dados, nomeArquivo)
                }
            }

            // C: fita de eventos
            CartaoGrafico {
                Layout.fillWidth: true
                visible: aba.temDado
                titulo: "Tentativas no tempo"
                subtitulo: "Um traço por tentativa · faixa hachurada = terminal bloqueado"
                tipo: "fita"
                altura: 60 + 26 * Math.max(1, aba.nFaixas)
                dados: aba.vm.fita || ({})
                estado: aba.estado
                nomeArquivo: "painel-fita"
                onExportar: aba.exportar(tipo, dados, nomeArquivo)
            }

            // D + E: espectro e coluna direita
            GridLayout {
                Layout.fillWidth: true
                columns: aba.estreita ? 1 : 2
                columnSpacing: Theme.espacoBloco
                rowSpacing: Theme.espacoBloco

                Item {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    implicitHeight: aba.temDado ? espectro.implicitHeight : 340
                    CartaoGrafico {
                        id: espectro
                        anchors { left: parent.left; right: parent.right; top: parent.top }
                        visible: aba.temDado
                        titulo: "Similaridade registrada"
                        subtitulo: "Melhor candidato de cada tentativa: não é taxa de erro"
                        tipo: "histograma"
                        altura: 240
                        dados: aba.vm.espectro || ({})
                        estado: aba.estado
                        nomeArquivo: "painel-espectro"
                        onExportar: aba.exportar(tipo, dados, nomeArquivo)
                    }
                    Rectangle {
                        anchors.fill: parent
                        visible: !aba.temDado
                        radius: Theme.raioGrande
                        color: Theme.superficie
                        border.color: Theme.borda
                        EstadoBloco {
                            objectName: "estadoGeral"
                            anchors.fill: parent
                            estado: aba.estado
                            erro: aba.vm.erro || ""
                            vazioIcone: "painel"
                            vazioTitulo: "Ainda não há tentativas registradas"
                            vazioTexto: "Cada tentativa no terminal aparece aqui, com a folga em relação ao limiar."
                            vazioAcao: "Abrir terminal"
                            onAcionado: app.navegar("terminal")
                            onTentarNovamente: aba.vm.recarregar()
                        }
                    }
                }

                ColumnLayout {
                    Layout.preferredWidth: aba.estreita ? -1 : Theme.colunaLateral
                    Layout.maximumWidth: aba.estreita ? 100000 : Theme.colunaLateral
                    Layout.fillWidth: aba.estreita
                    Layout.alignment: Qt.AlignTop
                    spacing: Theme.espacoBloco

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Agora"
                        subtitulo: "Últimos 15 minutos"
                        espacamento: 8
                        Text {
                            visible: (aba.vm.agora || []).length === 0
                            Layout.fillWidth: true
                            text: "Nada nos últimos 15 minutos"
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                        }
                        Repeater {
                            model: (aba.vm.agora || []).slice(0, 8)
                            delegate: RowLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 8
                                Text {
                                    text: modelData.hora || "–"
                                    color: Theme.texto2
                                    font.pixelSize: Theme.tPequeno
                                    font.features: { "tnum": 1 }
                                }
                                Selo { texto: modelData.titulo || ""; cor: Theme.corResultado(modelData.concedido ? "CONCEDIDO" : "erro") }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: modelData.similaridade || "–"
                                    color: Theme.texto
                                    font.pixelSize: Theme.tPequeno
                                    font.features: { "tnum": 1 }
                                }
                                Accessible.role: Accessible.StaticText
                                Accessible.name: (modelData.hora || "") + ", " + (modelData.titulo || "") + ", " + (modelData.similaridade || "")
                            }
                        }
                        Botao {
                            text: "Ver na Auditoria"
                            icone: "acessos"
                            variante: "fantasma"
                            compacto: true
                            onClicked: aba.vm.abrirAuditoria()
                        }
                    }

                    PainelPostura {
                        objectName: "posturaGeral"
                        Layout.fillWidth: true
                        linhas: aba.vm.postura || []
                        diagnostico: aba.vm.diagnostico || []
                        diagnosticando: aba.vm.diagnosticando === true
                        onDiagnosticar: aba.vm.executarDiagnostico()
                        onAbrirConfiguracoes: aba.vm.abrirConfiguracoes()
                        onVerSeparacao: app.v2.irPara("resultados", "separacao")
                        onVerSaudeCadastro: app.v2.irPara("resultados", "galeria")
                    }
                }
            }

            Item { Layout.preferredHeight: 8 }
        }
    }
}
