import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Nível 2: gestão das divisões. Dados fictícios; os botões de aprovação não executam nada.
ScrollView {
    id: pagina
    property var dados: ({})
    readonly property color cor: Theme.corNivel(2)
    readonly property var resumo: dados.resumo || ({})
    readonly property var divisoes: dados.divisoes || []
    readonly property var aprovacoes: dados.aprovacoes || []
    readonly property var metas: dados.metas || []
    contentWidth: availableWidth
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    function moeda(v) { return "R$ " + v.toFixed(1).replace(".", ",") + " mi" }
    function demo() { app.notificar("info", "Demonstração: a aprovação não é executada.") }

    ColumnLayout {
        width: pagina.availableWidth
        spacing: 18

        RowLayout {
            Layout.margins: 28
            Layout.bottomMargin: 0
            spacing: 14
            Rectangle {
                width: 44; height: 44; radius: 13
                color: Qt.rgba(pagina.cor.r, pagina.cor.g, pagina.cor.b, 0.16)
                Icone { anchors.centerIn: parent; nome: "camadas"; tamanho: 22; traco: 2; cor: pagina.cor }
            }
            ColumnLayout {
                spacing: 2
                Text { text: dados.titulo || ""; color: Theme.texto; font.pixelSize: Theme.tTitulo; font.weight: Font.DemiBold }
                Text { text: "Exercício 2026 · " + (resumo.divisoes || 0) + " divisões sob a Secretaria Executiva"; color: Theme.texto2; font.pixelSize: Theme.tCorpo }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            spacing: 12
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Orçamento anual"; valor: resumo.orcamento || "–"; icone: "banco" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Executado"; valor: resumo.executado || "–"; detalhe: resumo.fracao !== undefined ? Math.round(resumo.fracao * 100) + "% do previsto" : ""; cor: pagina.cor; icone: "pulso" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Aprovações pendentes"; valor: String(resumo.aprovacoesPendentes || 0); cor: (resumo.aprovacoesPendentes || 0) > 4 ? Theme.aviso : Theme.texto; icone: "arquivo" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Metas no alvo"; valor: pagina.metas.filter(function(m) { return m.atual >= m.alvo * 0.9 }).length + " de " + pagina.metas.length; icone: "foco" }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            Layout.bottomMargin: 28
            spacing: 16

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 16

                Painel {
                    Layout.fillWidth: true
                    titulo: "Execução orçamentária por divisão"
                    subtitulo: "Valores em milhões de reais"
                    espacamento: 0
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.bottomMargin: 8
                        Text { Layout.fillWidth: true; text: "Divisão"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: 90; text: "Previsto"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                        Text { Layout.preferredWidth: 90; text: "Executado"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                        Text { Layout.preferredWidth: 150; text: "Andamento"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                    }
                    Repeater {
                        model: pagina.divisoes
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 0
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda; opacity: 0.7 }
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.topMargin: 10
                                Layout.bottomMargin: 10
                                spacing: 12
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text { Layout.fillWidth: true; text: modelData.nome; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium; elide: Text.ElideRight }
                                    Text { Layout.fillWidth: true; text: modelData.servidores + " servidores · meta " + modelData.meta + "%"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight }
                                }
                                Text { Layout.preferredWidth: 90; text: pagina.moeda(modelData.orcamento); color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                Text { Layout.preferredWidth: 90; text: pagina.moeda(modelData.executado); color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                RowLayout {
                                    Layout.preferredWidth: 150
                                    spacing: 8
                                    Medidor { Layout.fillWidth: true; valor: modelData.fracao; cor: modelData.fracao >= modelData.meta / 100 ? Theme.sucesso : pagina.cor; altura: 5 }
                                    Text { text: Math.round(modelData.fracao * 100) + "%"; color: Theme.texto2; font.pixelSize: Theme.tLegenda; Layout.preferredWidth: 32; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                }
                            }
                        }
                    }
                }

                Painel {
                    Layout.fillWidth: true
                    titulo: "Aprovações pendentes"
                    subtitulo: "Processos que aguardam a assinatura de um diretor"
                    espacamento: 8
                    Repeater {
                        model: pagina.aprovacoes
                        delegate: Rectangle {
                            required property var modelData
                            readonly property color tom: modelData.prioridade === "alta" ? Theme.perigo : modelData.prioridade === "média" ? Theme.aviso : Theme.texto3
                            Layout.fillWidth: true
                            implicitHeight: la.implicitHeight + 22
                            radius: Theme.raioPequeno + 1
                            color: Theme.campo
                            border.color: Theme.borda
                            RowLayout {
                                id: la
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                                spacing: 12
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3
                                    RowLayout {
                                        spacing: 8
                                        Text { text: modelData.id; color: pagina.cor; font.pixelSize: Theme.tLegenda; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                                        Selo { texto: "prioridade " + modelData.prioridade; cor: tom }
                                        Text { text: "prazo " + modelData.prazo; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                                    }
                                    Text { text: modelData.assunto; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    Text { text: modelData.origem + " · " + modelData.valor; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                                }
                                Botao { text: "Devolver"; variante: "fantasma"; compacto: true; onClicked: pagina.demo() }
                                Botao { text: "Aprovar"; variante: "primario"; compacto: true; icone: "ok"; onClicked: pagina.demo() }
                            }
                        }
                    }
                }
            }

            Painel {
                Layout.preferredWidth: 320
                Layout.maximumWidth: 320
                Layout.alignment: Qt.AlignTop
                titulo: "Metas do ano"
                espacamento: 14
                Repeater {
                    model: pagina.metas
                    delegate: ColumnLayout {
                        required property var modelData
                        readonly property real fracao: Math.min(1, modelData.atual / modelData.alvo)
                        Layout.fillWidth: true
                        spacing: 5
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: modelData.nome; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; elide: Text.ElideRight }
                            Text { text: Math.round(fracao * 100) + "%"; color: fracao >= 0.9 ? Theme.sucesso : Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                        }
                        Medidor { Layout.fillWidth: true; valor: fracao; cor: fracao >= 0.9 ? Theme.sucesso : pagina.cor; altura: 6 }
                        Text { text: modelData.atual + " de " + modelData.alvo + (modelData.unidade ? " " + modelData.unidade : ""); color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.features: { "tnum": 1 } }
                    }
                }
            }
        }
    }
}
