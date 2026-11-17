import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

// Aba Qualidade de Resultados: que medida de qualidade prevê o erro (curva erro × descarte).
// Protocolo sintético e leitura informativa.
Item {
    id: aba
    objectName: "abaResQualidade"
    readonly property var vm: app.v2.resQualidade
    readonly property bool comDado: vm.estado === "pronto" || vm.estado === "poucos"
    readonly property var ficha: vm.ficha || ({})

    FolderDialog {
        id: dialogoPasta
        title: "Pasta rotulada (uma subpasta por pessoa)"
        onAccepted: aba.vm.definirPasta(selectedFolder)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.espacoBloco

        // A. fonte
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Segmentado {
                opcoes: [{ valor: "fotos_teste", texto: "Fotos de teste" }, { valor: "pasta", texto: "Pasta rotulada…" }]
                atual: vm.fonte
                onEscolhido: function(v) { if (v === "pasta") dialogoPasta.open(); else vm.usarFotosTeste() }
            }
            Text {
                visible: vm.fonte === "pasta" && (vm.pasta || "") !== ""
                Layout.maximumWidth: 260
                text: vm.pasta || ""
                color: Theme.texto3
                font.pixelSize: Theme.tLegenda
                elide: Text.ElideMiddle
            }
            Botao {
                objectName: "botaoCalcularQualidade"
                variante: "primario"
                icone: "play"
                text: "Calcular"
                enabled: vm.estado !== "carregando"
                onClicked: vm.calcular()
            }
            Item { Layout.fillWidth: true }
            Selo { texto: "Sintético"; cor: Theme.aviso }
            Repeater {
                model: [["Pessoas", "pessoas"], ["Imagens", "imagens"], ["Amostras", "amostras"], ["Pares", "pares"]]
                delegate: ColumnLayout {
                    required property var modelData
                    visible: aba.comDado
                    spacing: 0
                    Text { text: modelData[0]; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                    Text {
                        text: aba.ficha[modelData[1]] || "–"
                        color: Theme.texto
                        font.pixelSize: Theme.tCorpo
                        font.weight: Font.DemiBold
                        font.features: { "tnum": 1 }
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ScrollView {
                id: rolagem
                anchors.fill: parent
                contentWidth: availableWidth
                clip: true
                visible: aba.comDado

                ColumnLayout {
                    width: rolagem.availableWidth
                    spacing: Theme.espacoBloco

                    Aviso {
                        Layout.fillWidth: true
                        visible: vm.estado === "poucos"
                        tipo: "aviso"
                        texto: (aba.ficha.pares || "0") + " pares genuínos: leia como exemplo, não como taxa."
                    }

                    // B. curva
                    CartaoGrafico {
                        visible: vm.semErro !== true
                        Layout.fillWidth: true
                        titulo: "Erro × descarte"
                        subtitulo: (vm.curvas || ({})).subtitulo || ""
                        tipo: "xy"
                        dados: vm.curvas || ({})
                        altura: 280
                        nomeArquivo: "qualidade-erc"
                        onExportar: app.v2.figuras.exportar("xy", vm.curvas, "qualidade-erc")
                    }
                    Painel {
                        visible: vm.semErro === true
                        Layout.fillWidth: true
                        titulo: "Nenhum erro observado neste protocolo: não há o que descartar."
                    }

                    // C. componentes
                    Tabela {
                        Layout.fillWidth: true
                        colunas: [{ chave: "componente", titulo: "Medida", largura: 0, alinhamento: "esq" },
                                  { chave: "spearman", titulo: "ρ de Spearman", largura: 120, alinhamento: "dir" },
                                  { chave: "fnmr0", titulo: "FNMR sem descarte", largura: 140, alinhamento: "dir" },
                                  { chave: "fnmr10", titulo: "com 10 %", largura: 110, alinhamento: "dir" },
                                  { chave: "fnmr20", titulo: "com 20 %", largura: 110, alinhamento: "dir" }]
                        linhas: vm.tabela || []
                        vazio: "Sem resultado"
                    }

                    // D. leitura
                    Text {
                        Layout.fillWidth: true
                        text: vm.leitura || ""
                        color: Theme.texto
                        font.pixelSize: 15
                        wrapMode: Text.Wrap
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Leitura informativa. Nenhuma destas medidas é usada no cadastro nem na autenticação; usá-las como critério depende de aprovação."
                        color: Theme.texto3
                        font.pixelSize: Theme.tPequeno
                        wrapMode: Text.Wrap
                    }
                }
            }

            EstadoBloco {
                anchors.fill: parent
                estado: vm.estado || "vazio"
                erro: vm.erro || ""
                progresso: vm.progresso !== undefined ? vm.progresso : -1
                cancelavel: true
                vazioIcone: "resultados"
                vazioTitulo: "Escolha a fonte e calcule"
                vazioTexto: "O protocolo degrada imagens rotuladas e mede que medida de qualidade prevê o erro"
                vazioAcao: "Usar fotos de teste"
                onAcionado: { vm.usarFotosTeste(); vm.calcular() }
                onTentarNovamente: vm.calcular()
                onCancelar: vm.cancelar()
            }
        }
    }
}
