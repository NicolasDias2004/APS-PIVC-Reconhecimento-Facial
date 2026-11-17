import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Cofre.Nativo

// Aba Fases do Laboratório PIVC: as cinco fases como cinco estações, com imagem, medida e tempo.
// Leitura de laboratório: esta tela não decide acesso.
Item {
    id: aba
    objectName: "abaLabFases"
    readonly property var vm: app.v2.labFases
    readonly property bool comDado: vm.estado === "pronto" || vm.estado === "poucos"
    readonly property int estacao: vm.estacao || 2
    readonly property string versao: "?r=" + (vm.revisao || 0)
    readonly property var par: vm.parametros || ({})
    readonly property var pad: vm.padroes || ({})
    property string ladoDireito: "clahe"
    function img(chave) { return "image://cofre/lab/fases/" + chave + versao }
    function leiturasDe(e) { var l = vm.leituras || ({}); return l[String(e)] || [] }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        visible: aba.comDado

        Aviso {
            Layout.fillWidth: true
            visible: vm.foraDoPadrao === true
            tipo: "aviso"
            texto: "Prévia com parâmetros de estudo. O sistema continua usando os valores de Configurações."
            acao: "Voltar aos valores do sistema"
            onAcionado: vm.restaurarPadroes()
        }
        Aviso {
            Layout.fillWidth: true
            visible: (vm.nRostos || 0) > 1
            tipo: "info"
            texto: (vm.nRostos || 0) + " rostos: a análise usa o maior, como o pipeline"
        }

        LabTrilhoFases {
            objectName: "trilhoFases"
            Layout.fillWidth: true
            Layout.preferredHeight: 84
            tempos: vm.tempos || []
            atual: aba.estacao
            orcamento: vm.orcamento || 0
            onEscolhida: function(e) { vm.definirEstacao(e) }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            // ------------------------------------------------------------ palco
            ScrollView {
                id: palco
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true

                ColumnLayout {
                    width: palco.availableWidth
                    spacing: 12

                    Text {
                        visible: aba.estacao >= 3 && vm.temRosto !== true
                        Layout.fillWidth: true
                        Layout.topMargin: 40
                        horizontalAlignment: Text.AlignHCenter
                        text: "Nenhum rosto detectado nesta imagem"
                        color: Theme.texto2
                        font.pixelSize: Theme.tDestaque
                    }

                    // estação 1: aquisição
                    Rectangle {
                        visible: aba.estacao === 1
                        Layout.fillWidth: true
                        Layout.preferredHeight: 420
                        radius: Theme.raio
                        color: Theme.campo
                        border.color: Theme.borda
                        Image {
                            anchors.fill: parent; anchors.margins: 1
                            source: aba.estacao === 1 ? aba.img("original") : ""
                            fillMode: Image.PreserveAspectFit
                            cache: false
                        }
                    }

                    // estação 2: pré-processamento
                    ColumnLayout {
                        visible: aba.estacao === 2
                        Layout.fillWidth: true
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: "Arraste a alça para comparar"; color: Theme.texto3; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true }
                            Segmentado {
                                opcoes: [{ valor: "clahe", texto: "CLAHE" }, { valor: "global", texto: "Equalização global" }]
                                atual: aba.ladoDireito
                                onEscolhido: function(v) { aba.ladoDireito = v }
                            }
                        }
                        LabCortina {
                            objectName: "cortinaFases"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 300
                            esquerda: aba.estacao === 2 ? aba.img("original") : ""
                            direita: aba.estacao === 2 ? aba.img(aba.ladoDireito) : ""
                            rotuloDireita: aba.ladoDireito === "clahe" ? "CLAHE" : "Equalização global"
                        }
                        CartaoGrafico {
                            Layout.fillWidth: true
                            titulo: "Histograma de luminância"
                            subtitulo: "Original, equalização global e CLAHE"
                            tipo: "xy"
                            dados: vm.histograma || ({})
                            altura: 200
                            nomeArquivo: "lab-histograma"
                            onExportar: app.v2.figuras.exportar("xy", vm.histograma, "lab-histograma")
                        }
                    }

                    // estação 3: segmentação e alinhamento
                    ColumnLayout {
                        visible: aba.estacao === 3 && vm.temRosto === true
                        Layout.fillWidth: true
                        spacing: 12
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 300
                                radius: Theme.raio
                                color: Theme.campo
                                border.color: Theme.borda
                                VisorVideo {
                                    anchors.fill: parent
                                    anchors.margins: 1
                                    fonte: vm.fonteDeteccao
                                    preencher: false
                                    raio: 8
                                    corFundo: Theme.campo
                                    mostrarPontos: true
                                }
                            }
                            ColumnLayout {
                                spacing: 6
                                Text { text: "Recorte"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                                Image {
                                    Layout.preferredWidth: 140; Layout.preferredHeight: 140
                                    source: aba.estacao === 3 && vm.temRosto ? aba.img("recorte") : ""
                                    fillMode: Image.PreserveAspectFit
                                    cache: false
                                }
                            }
                            ColumnLayout {
                                spacing: 6
                                Text { text: "Rosto alinhado 112 × 112"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                                Image {
                                    Layout.preferredWidth: 224; Layout.preferredHeight: 224
                                    source: aba.estacao === 3 && vm.temRosto ? aba.img("alinhado") : ""
                                    fillMode: Image.PreserveAspectFit
                                    smooth: false
                                    cache: false
                                }
                            }
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: colMatriz.implicitHeight + 24
                            radius: Theme.raio
                            color: Theme.superficie
                            border.color: Theme.borda
                            ColumnLayout {
                                id: colMatriz
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 6
                                Text { text: "Matriz afim 2 × 3 do alinhamento"; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                                Repeater {
                                    model: vm.matriz || []
                                    delegate: Text {
                                        required property var modelData
                                        text: "[ " + (modelData || []).map(function(v) { return ("          " + v).slice(-10) }).join("  ") + " ]"
                                        color: Theme.texto
                                        font.family: Theme.familiaMono
                                        font.pixelSize: Theme.tCorpo
                                    }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: (vm.matrizDetalhe || ({})).texto || ""
                                    color: Theme.texto2
                                    font.pixelSize: Theme.tPequeno
                                    wrapMode: Text.Wrap
                                }
                            }
                        }
                    }

                    // estação 4: representação
                    RowLayout {
                        visible: aba.estacao === 4 && vm.temRosto === true
                        Layout.fillWidth: true
                        spacing: 12
                        ColumnLayout {
                            spacing: 6
                            Text { text: "Mapa LBP do rosto alinhado"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                            Image {
                                Layout.preferredWidth: 220; Layout.preferredHeight: 220
                                source: aba.estacao === 4 && vm.temRosto ? aba.img("lbp") : ""
                                fillMode: Image.PreserveAspectFit
                                smooth: false
                                cache: false
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            LabAssinatura {
                                objectName: "assinaturaFases"
                                Layout.fillWidth: true
                                Layout.preferredHeight: 150
                                fonte: aba.estacao === 4 && vm.temRosto ? aba.img("assinatura") : ""
                            }
                            Repeater {
                                model: aba.leiturasDe(4)
                                delegate: ParRotuloValor {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    rotulo: modelData[0]
                                    valor: modelData[1]
                                }
                            }
                        }
                    }

                    // estação 5: reconhecimento
                    ColumnLayout {
                        visible: aba.estacao === 5 && vm.temRosto === true
                        Layout.fillWidth: true
                        spacing: 12
                        RowLayout {
                            visible: vm.similaridadeReferencia >= 0
                            Layout.fillWidth: true
                            spacing: 10
                            Text { text: "Referência do laboratório"; color: Theme.texto2; font.pixelSize: Theme.tCorpo; Layout.preferredWidth: 190 }
                            BarraSimilaridade {
                                Layout.fillWidth: true
                                valor: vm.similaridadeReferencia
                                marca: vm.limiar || -1
                                descricao: "Similaridade com a referência"
                            }
                            Text {
                                text: (vm.similaridadeReferencia || 0).toFixed(3).replace(".", ",")
                                color: Theme.texto
                                font.pixelSize: Theme.tCorpo
                                font.features: { "tnum": 1 }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Botao {
                                objectName: "botaoCompararGaleria"
                                visible: vm.comparacaoPermitida === true
                                variante: "primario"
                                icone: "alvo"
                                text: "Comparar com a galeria"
                                carregando: vm.rankingEstado === "calculando"
                                onClicked: vm.compararComGaleria()
                            }
                            Selo { visible: vm.foraDoPadrao === true; texto: "Hipotética"; cor: Theme.aviso }
                            Item { Layout.fillWidth: true }
                            Botao {
                                objectName: "botaoTestarRobustez"
                                text: "Testar a robustez desta imagem"
                                icone: "pulso"
                                variante: "fantasma"
                                compacto: true
                                onClicked: app.v2.laboratorio.definirAba("robustez")
                            }
                        }
                        Text {
                            visible: vm.rankingEstado === "indisponivel" || vm.comparacaoPermitida !== true
                            Layout.fillWidth: true
                            text: vm.rankingMotivo || ""
                            color: Theme.texto2
                            font.pixelSize: Theme.tCorpo
                            wrapMode: Text.Wrap
                        }
                        Text {
                            visible: vm.rankingEstado === "galeria_vazia"
                            text: "A galeria está vazia: cadastre alguém para comparar."
                            color: Theme.texto2
                            font.pixelSize: Theme.tCorpo
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "Leitura de laboratório: esta tela não decide acesso; a decisão é do Terminal."
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                            wrapMode: Text.Wrap
                        }
                        Repeater {
                            model: vm.rankingEstado === "pronto" ? (vm.ranking || []) : []
                            delegate: RowLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 10
                                Text { text: modelData.rotulo; color: Theme.texto; font.pixelSize: Theme.tCorpo; Layout.preferredWidth: 140; elide: Text.ElideRight }
                                BarraSimilaridade { Layout.fillWidth: true; valor: modelData.similaridade; marca: vm.limiar; descricao: modelData.rotulo }
                                Text { text: modelData.texto; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.features: { "tnum": 1 } }
                                Text {
                                    text: modelData.leitura
                                    color: modelData.acima ? Theme.acento : Theme.texto2
                                    font.pixelSize: Theme.tPequeno
                                    Layout.preferredWidth: 170
                                }
                            }
                        }
                        ColumnLayout {
                            visible: vm.foraDoPadrao === true && vm.rankingEstado === "pronto" && (vm.rankingPadrao || []).length > 0
                            Layout.fillWidth: true
                            spacing: 4
                            Text { text: "Com os parâmetros do sistema"; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                            Repeater {
                                model: vm.rankingPadrao || []
                                delegate: ParRotuloValor {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    rotulo: modelData.rotulo
                                    valor: modelData.texto + " · " + modelData.leitura
                                }
                            }
                        }
                    }
                }
            }

            // ------------------------------------------------------------ coluna direita
            ScrollView {
                id: coluna
                Layout.preferredWidth: Theme.colunaLateral
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true

                ColumnLayout {
                    width: coluna.availableWidth
                    spacing: Theme.espacoBloco

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Leituras da estação"
                        Repeater {
                            model: aba.leiturasDe(aba.estacao)
                            delegate: ParRotuloValor {
                                required property var modelData
                                Layout.fillWidth: true
                                rotulo: modelData[0]
                                valor: modelData[1]
                            }
                        }
                        Text {
                            visible: aba.leiturasDe(aba.estacao).length === 0
                            text: aba.estacao === 5 ? "Preenchida depois de “Comparar com a galeria”." : "Sem leitura nesta estação."
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                    }

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Parâmetros de estudo"
                        subtitulo: "Valem só para esta prévia"
                        Deslizante {
                            objectName: "deslizanteLargura"
                            Layout.fillWidth: true
                            rotulo: "Largura de trabalho"
                            valor: aba.par.largura || 640; minimo: 320; maximo: 960; passo: 40; casas: 0; sufixo: " px"
                            padrao: aba.pad.largura || NaN
                            onMovido: function(v) { vm.definirParametro("largura", v) }
                        }
                        Deslizante {
                            Layout.fillWidth: true
                            rotulo: "Núcleo do Gauss"
                            valor: aba.par.kernel || 3; minimo: 1; maximo: 15; passo: 2; casas: 0
                            padrao: aba.pad.kernel || NaN
                            onMovido: function(v) { vm.definirParametro("kernel", v) }
                        }
                        Deslizante {
                            Layout.fillWidth: true
                            rotulo: "Clip do CLAHE"
                            valor: aba.par.clip || 2; minimo: 0.5; maximo: 8; passo: 0.1; casas: 1
                            padrao: aba.pad.clip || NaN
                            onMovido: function(v) { vm.definirParametro("clip", v) }
                        }
                        Deslizante {
                            Layout.fillWidth: true
                            rotulo: "Grade do CLAHE"
                            valor: aba.par.grade || 8; minimo: 4; maximo: 16; passo: 4; casas: 0
                            padrao: aba.pad.grade || NaN
                            onMovido: function(v) { vm.definirParametro("grade", v) }
                        }
                    }

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Qualidade do rosto"
                        Selo { texto: "Leitura informativa"; icone: "info" }
                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: "Índice"; color: Theme.texto2; font.pixelSize: Theme.tCorpo; Layout.fillWidth: true }
                            Text {
                                text: vm.indiceQualidade >= 0 ? vm.indiceQualidade + " de 100" : "–"
                                color: Theme.texto
                                font.pixelSize: Theme.tDestaque
                                font.weight: Font.DemiBold
                                font.features: { "tnum": 1 }
                            }
                        }
                        Repeater {
                            model: vm.qualidade || []
                            delegate: ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 3
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { text: modelData.rotulo; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true }
                                    Text { text: modelData.bruto; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.features: { "tnum": 1 } }
                                }
                                BarraSimilaridade {
                                    Layout.fillWidth: true
                                    valor: modelData.nota
                                    altura: 4
                                    descricao: modelData.rotulo
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    EstadoBloco {
        anchors.fill: parent
        estado: vm.estado || "vazio"
        erro: vm.erro || ""
        progresso: vm.progresso !== undefined ? vm.progresso : -1
        vazioIcone: "laboratorio"
        vazioTitulo: "Nenhuma amostra"
        vazioTexto: "Escolha uma imagem na barra de fonte"
        vazioAcao: "Usar foto de teste"
        onAcionado: app.v2.laboratorio.usarFotoTeste(0)
        onTentarNovamente: vm.recarregar()
    }
}
