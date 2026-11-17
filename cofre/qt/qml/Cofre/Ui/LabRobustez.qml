import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Aba Robustez do Laboratório PIVC: medidor ao vivo de uma degradação sintética, curvas das oito
// famílias com o ponto de quebra e a ablação. O medidor é turquesa ou cinza, nunca verde.
Item {
    id: aba
    objectName: "abaLabRobustez"
    readonly property var vm: app.v2.labRobustez
    readonly property bool comDado: vm.estado === "pronto" || vm.estado === "poucos"
    readonly property bool acima: vm.similaridade >= 0 && vm.similaridade >= vm.limiar
    readonly property int colunasCurvas: rolagem.availableWidth > 900 ? 4 : 2

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
                visible: vm.semReferencia === true
                tipo: "aviso"
                texto: "Sem referência: o medidor compara a imagem com ela mesma. Escolha uma referência na barra de fonte."
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 16

                // A. prova
                ColumnLayout {
                    Layout.preferredWidth: 240
                    Layout.alignment: Qt.AlignTop
                    spacing: 8
                    Rectangle {
                        Layout.preferredWidth: 240
                        Layout.preferredHeight: 240
                        radius: Theme.raio
                        color: Theme.campo
                        border.color: Theme.borda
                        clip: true
                        Image {
                            anchors.fill: parent
                            anchors.margins: 1
                            source: (vm.revisao || 0) > 0 ? "image://cofre/lab/robustez/previa?r=" + vm.revisao : ""
                            fillMode: Image.PreserveAspectFit
                            smooth: false
                            cache: false
                        }
                        Selo {
                            anchors { left: parent.left; top: parent.top; margins: 8 }
                            texto: "Sintético"
                            cor: Theme.aviso
                        }
                    }
                    ParRotuloValor {
                        Layout.fillWidth: true
                        rotulo: "Referência"
                        valor: vm.referenciaRotulo || "–"
                    }
                }

                // B. medidor
                ColumnLayout {
                    Layout.preferredWidth: 300
                    Layout.alignment: Qt.AlignTop
                    spacing: 10
                    Item {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 180
                        Layout.preferredHeight: 180
                        Anel {
                            anchors.fill: parent
                            valor: Math.max(0, vm.similaridade)
                            marca: vm.limiar
                            cor: aba.acima ? Theme.acento : Theme.texto2
                            espessura: 6
                            descricao: "Similaridade com a referência"
                        }
                        Text {
                            anchors.centerIn: parent
                            text: vm.similaridade >= 0 ? vm.similaridade.toFixed(3).replace(".", ",") : "–"
                            color: Theme.texto
                            font.pixelSize: 28
                            font.weight: Font.DemiBold
                            font.features: { "tnum": 1 }
                        }
                    }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: vm.similaridade < 0 ? "sem leitura" : (aba.acima ? "acima do limiar em vigor" : "abaixo do limiar em vigor")
                        color: aba.acima ? Theme.acento : Theme.texto2
                        font.pixelSize: Theme.tPequeno
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        Repeater {
                            model: vm.familias || []
                            delegate: Rectangle {
                                id: pilula
                                required property var modelData
                                readonly property bool ativa: vm.familia === modelData.chave
                                width: rot.implicitWidth + 18
                                height: 26
                                radius: 13
                                color: ativa ? Theme.realce : (areaP.containsMouse ? Theme.hover : "transparent")
                                border.color: ativa ? Theme.acento : Theme.borda
                                activeFocusOnTab: true
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: modelData.nome
                                Keys.onReturnPressed: vm.definirFamilia(modelData.chave)
                                Keys.onSpacePressed: vm.definirFamilia(modelData.chave)
                                Text {
                                    id: rot
                                    anchors.centerIn: parent
                                    text: pilula.modelData.nome
                                    color: pilula.ativa ? Theme.texto : Theme.texto2
                                    font.pixelSize: Theme.tLegenda
                                }
                                MouseArea {
                                    id: areaP
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: vm.definirFamilia(pilula.modelData.chave)
                                }
                            }
                        }
                    }
                    Deslizante {
                        objectName: "deslizanteIntensidade"
                        Layout.fillWidth: true
                        rotulo: "Intensidade · " + (vm.rotuloIntensidade || "")
                        valor: vm.intensidade || 0
                        minimo: 0; maximo: 1; passo: 1 / 11; casas: 2
                        padrao: 0
                        onMovido: function(v) { vm.definirIntensidade(v) }
                    }
                }

                // C. curvas
                ColumnLayout {
                    id: curvasCol
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Botao {
                            objectName: "botaoVarrer"
                            variante: "primario"
                            icone: "play"
                            text: "Varrer"
                            carregando: vm.varrendo === true
                            enabled: vm.varrendo !== true
                            onClicked: vm.varrer()
                        }
                        Botao {
                            visible: vm.varrendo === true
                            variante: "fantasma"
                            text: "Cancelar"
                            onClicked: vm.cancelar()
                        }
                        BarraSimilaridade {
                            visible: vm.varrendo === true
                            Layout.fillWidth: true
                            valor: vm.progresso
                            descricao: "Progresso da varredura"
                        }
                        Item { visible: vm.varrendo !== true; Layout.fillWidth: true }
                        Botao {
                            compacto: true
                            icone: "baixar"
                            text: "Exportar CSV"
                            enabled: (vm.curvas || []).length > 0
                            onClicked: vm.exportarCsv()
                        }
                    }
                    Text {
                        visible: (vm.curvas || []).length === 0
                        Layout.fillWidth: true
                        text: "“Varrer” mede as oito famílias em doze intensidades e marca onde cada curva cruza o limiar em vigor."
                        color: Theme.texto2
                        font.pixelSize: Theme.tCorpo
                        wrapMode: Text.Wrap
                    }
                    Painel {
                        visible: (vm.quebras || []).length > 0
                        Layout.fillWidth: true
                        titulo: "Ponto de quebra"
                        Repeater {
                            model: vm.quebras || []
                            delegate: ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 2
                                ParRotuloValor {
                                    Layout.fillWidth: true
                                    rotulo: modelData.nome
                                    valor: modelData.texto
                                }
                                Botao {
                                    objectName: "botaoVerOndeOlha"
                                    visible: modelData.familia === "oclusao_olhos"
                                    text: "Ver onde o descritor olha"
                                    icone: "alvo"
                                    variante: "fantasma"
                                    compacto: true
                                    onClicked: app.v2.laboratorio.definirAba("explicabilidade")
                                }
                            }
                        }
                    }
                    Aviso {
                        visible: (vm.nota || "") !== ""
                        Layout.fillWidth: true
                        tipo: "info"
                        texto: vm.nota || ""
                    }
                }
            }

            GridLayout {
                visible: (vm.curvas || []).length > 0
                Layout.fillWidth: true
                columns: aba.colunasCurvas
                columnSpacing: 10
                rowSpacing: 10
                Repeater {
                    model: vm.curvas || []
                    delegate: CartaoGrafico {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        Layout.preferredWidth: 10
                        titulo: modelData.titulo || ""
                        tipo: "xy"
                        dados: modelData
                        altura: 130
                        nomeArquivo: "robustez-" + ((vm.familias || [])[index] || {}).chave
                        onExportar: app.v2.figuras.exportar("xy", modelData, nomeArquivo)
                    }
                }
            }

            // D. ablação
            LabRobustezAblacao {
                Layout.fillWidth: true
                linhas: vm.ablacao || []
                estado: vm.ablacaoEstado || "nao_pedida"
                onMedir: vm.executarAblacao()
            }
        }
    }

    EstadoBloco {
        anchors.fill: parent
        estado: vm.estado || "vazio"
        erro: vm.erro || ""
        vazioIcone: "laboratorio"
        vazioTitulo: "Nenhum rosto para degradar"
        vazioTexto: "Escolha uma imagem com rosto na barra de fonte"
        vazioAcao: "Usar foto de teste"
        onAcionado: app.v2.laboratorio.usarFotoTeste(0)
        onTentarNovamente: vm.recarregar()
    }
}
