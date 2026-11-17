import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

// Aba Separação de Resultados: genuínos × impostores com N, teto de erro e um limiar de estudo.
// O limiar de estudo é só simulação: não existe botão de aplicar e o limiar do sistema não muda.
Item {
    id: aba
    objectName: "abaResSeparacao"
    readonly property var vm: app.v2.resSeparacao
    readonly property string estado: vm ? (vm.estado || "vazio") : "vazio"
    readonly property bool temDado: estado === "pronto" || estado === "poucos"
    readonly property var cartoes: vm ? (vm.cartoes || []) : []
    readonly property var selos: vm ? (vm.selos || []) : []
    readonly property var noEstudo: vm ? (vm.noEstudo || ({})) : ({})
    readonly property var descritores: vm ? (vm.descritores || []) : []

    FolderDialog {
        id: dialogoPasta
        title: "Pasta com uma subpasta por pessoa"
        onAccepted: aba.vm.definirPasta(selectedFolder)
    }

    ScrollView {
        id: rolagem
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: rolagem.availableWidth
            spacing: Theme.espacoBloco

            // A. Fonte dos pares
            Painel {
                Layout.fillWidth: true
                titulo: "Fonte dos pares"
                subtitulo: "Cada par de imagens vira um escore: genuíno (mesma pessoa) ou impostor (pessoas diferentes)."
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 24
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        spacing: 10
                        Segmentado {
                            opcoes: [{ valor: "fotos_teste", texto: "Fotos de teste" },
                                     { valor: "pasta", texto: "Pasta rotulada…" },
                                     { valor: "galeria", texto: "Galeria cadastrada" }]
                            atual: aba.vm ? aba.vm.protocolo : ""
                            habilitado: aba.estado !== "carregando"
                            onEscolhido: function(valor) {
                                if (valor === "pasta") dialogoPasta.open()
                                else aba.vm.definirProtocolo(valor)
                            }
                        }
                        Text {
                            visible: aba.vm && aba.vm.protocolo === "pasta" && aba.vm.pasta !== ""
                            Layout.fillWidth: true
                            text: aba.vm ? (aba.vm.pasta || "") : ""
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                            elide: Text.ElideMiddle
                        }
                        Flow {
                            visible: aba.selos.length > 0
                            Layout.fillWidth: true
                            spacing: 8
                            Repeater {
                                model: aba.selos
                                delegate: Selo { required property var modelData; texto: String(modelData); cor: Theme.aviso; icone: "alerta" }
                            }
                        }
                        RowLayout {
                            spacing: 8
                            Botao {
                                text: "Calcular"
                                icone: "play"
                                variante: "primario"
                                enabled: aba.vm && aba.vm.protocolo !== "" && aba.estado !== "carregando"
                                onClicked: aba.vm.calcular()
                            }
                            Botao {
                                visible: aba.vm && aba.vm.protocolo === "pasta"
                                text: "Trocar pasta"
                                icone: "pasta"
                                onClicked: dialogoPasta.open()
                            }
                        }
                    }
                    ResFichaProtocolo {
                        Layout.preferredWidth: 280
                        Layout.alignment: Qt.AlignTop
                        dados: aba.vm ? aba.vm.ficha : ({})
                    }
                }
            }

            Aviso {
                visible: aba.estado === "poucos" && aba.vm.avisoPoucos !== ""
                Layout.fillWidth: true
                tipo: "aviso"
                texto: aba.vm ? (aba.vm.avisoPoucos || "") : ""
            }

            // Vazio, carregando, erro e indisponível ocupam o lugar do conteúdo.
            Item {
                visible: !aba.temDado
                Layout.fillWidth: true
                Layout.preferredHeight: 300
                EstadoBloco {
                    anchors.fill: parent
                    estado: aba.estado
                    erro: aba.vm ? (aba.vm.erro || "") : ""
                    progresso: aba.vm ? aba.vm.progresso : -1
                    cancelavel: true
                    vazioIcone: "resultados"
                    vazioTitulo: "Separação entre genuínos e impostores"
                    vazioTexto: aba.vm ? (aba.vm.vazioTexto || "") : ""
                    vazioAcao: aba.vm && aba.vm.protocolo === "" ? "Usar fotos de teste" : ""
                    onAcionado: { aba.vm.definirProtocolo("fotos_teste"); aba.vm.calcular() }
                    onTentarNovamente: aba.vm.calcular()
                    onCancelar: aba.vm.cancelar()
                }
            }

            // B e C. Histograma com o limiar de estudo, e os cartões
            RowLayout {
                visible: aba.temDado
                Layout.fillWidth: true
                spacing: Theme.espacoBloco
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: 12
                    CartaoGrafico {
                        Layout.fillWidth: true
                        titulo: "Genuínos × impostores"
                        subtitulo: "Similaridade (cosseno do SFace) por par"
                        tipo: "histograma"
                        dados: aba.vm ? aba.vm.histograma : ({})
                        altura: 300
                        nomeArquivo: "separacao-histograma"
                        estado: aba.estado
                        onExportar: app.v2.figuras.exportar(tipo, dados, nomeArquivo)
                    }
                    Deslizante {
                        Layout.fillWidth: true
                        rotulo: "Limiar de estudo"
                        valor: aba.vm ? aba.vm.limiarEstudo : 0
                        minimo: 0
                        maximo: 1
                        passo: 0.005
                        casas: 3
                        padrao: aba.vm ? aba.vm.limiarVigor : NaN
                        onMovido: function(valor) { aba.vm.definirLimiarEstudo(valor) }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Simulação. O limiar do sistema continua " + (aba.vm ? aba.vm.limiarVigorTexto : "–") + "."
                        color: Theme.texto2
                        font.pixelSize: Theme.tPequeno
                        wrapMode: Text.Wrap
                    }
                    Text {
                        Layout.fillWidth: true
                        text: aba.noEstudo.frase || ""
                        color: Theme.texto
                        font.pixelSize: Theme.tCorpo
                        font.features: { "tnum": 1 }
                        wrapMode: Text.Wrap
                    }
                }
                GridLayout {
                    Layout.preferredWidth: 380
                    Layout.alignment: Qt.AlignTop
                    columns: 2
                    columnSpacing: 10
                    rowSpacing: 10
                    Repeater {
                        model: aba.cartoes
                        delegate: Metrica {
                            required property var modelData
                            Layout.fillWidth: true
                            rotulo: modelData.rotulo || ""
                            valor: modelData.valor || "–"
                            detalhe: modelData.detalhe || ""
                        }
                    }
                }
            }

            // D. Curva ROC (ou o teto quando não há erro observado)
            CartaoGrafico {
                visible: aba.temDado && !(aba.vm && aba.vm.semErro)
                Layout.fillWidth: true
                titulo: "Curva ROC"
                subtitulo: "Genuínos aceitos contra falso casamento, com FMR em escala log"
                tipo: "xy"
                dados: aba.vm ? aba.vm.roc : ({})
                altura: 240
                nomeArquivo: "separacao-roc"
                estado: aba.estado
                onExportar: app.v2.figuras.exportar(tipo, dados, nomeArquivo)
            }
            Painel {
                visible: aba.temDado && aba.vm && aba.vm.semErro
                Layout.fillWidth: true
                titulo: "Curva ROC"
                Text {
                    Layout.fillWidth: true
                    text: aba.vm ? (aba.vm.textoSemErro || "") : ""
                    color: Theme.texto2
                    font.pixelSize: Theme.tCorpo
                    wrapMode: Text.Wrap
                }
            }

            // E. Pontos de operação
            Painel {
                visible: aba.temDado
                Layout.fillWidth: true
                titulo: "Pontos de operação"
                subtitulo: "Taxas em cada limiar, com o teto de erro (Wilson, ou regra de três quando nada foi observado)"
                cabecalhoDireita: Botao {
                    text: "Exportar CSV"
                    icone: "baixar"
                    compacto: true
                    onClicked: aba.vm.exportarCsv()
                }
                Tabela {
                    Layout.fillWidth: true
                    colunas: [{ chave: "limiar", titulo: "Limiar", largura: 150, alinhamento: "esq" },
                              { chave: "fmr", titulo: "FMR", largura: 0, alinhamento: "dir" },
                              { chave: "fnmr", titulo: "FNMR", largura: 0, alinhamento: "dir" },
                              { chave: "tetoFmr", titulo: "Teto FMR", largura: 100, alinhamento: "dir" },
                              { chave: "tetoFnmr", titulo: "Teto FNMR", largura: 100, alinhamento: "dir" }]
                    linhas: aba.vm ? (aba.vm.pontosLinhas || []) : []
                }
            }

            // F. Clássico × profundo (some na galeria, onde não há imagem para o LBP)
            Painel {
                visible: aba.temDado && aba.descritores.length > 0
                Layout.fillWidth: true
                titulo: "O mesmo protocolo com outros descritores"
                subtitulo: "SFace (rede profunda) contra o histograma LBP, nos mesmos pares"
                Tabela {
                    Layout.fillWidth: true
                    colunas: [{ chave: "nome", titulo: "Descritor", largura: 0, alinhamento: "esq" },
                              { chave: "auc", titulo: "AUC", largura: 90, alinhamento: "dir" },
                              { chave: "eer", titulo: "EER", largura: 90, alinhamento: "dir" },
                              { chave: "dprime", titulo: "d′", largura: 90, alinhamento: "dir" }]
                    linhas: aba.descritores
                }
                Text {
                    visible: text !== ""
                    Layout.fillWidth: true
                    text: aba.vm ? (aba.vm.fraseDescritores || "") : ""
                    color: Theme.texto2
                    font.pixelSize: Theme.tPequeno
                    wrapMode: Text.Wrap
                }
                Botao {
                    objectName: "botaoVerOndeOlhaSeparacao"
                    text: "Ver o que o descritor olha"
                    icone: "alvo"
                    variante: "fantasma"
                    compacto: true
                    onClicked: app.v2.irPara("laboratorio", "explicabilidade")
                }
            }

            Item { Layout.preferredHeight: 8 }
        }
    }
}
