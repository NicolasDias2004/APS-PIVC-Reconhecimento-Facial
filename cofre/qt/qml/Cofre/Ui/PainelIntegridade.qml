import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Aba Integridade do Painel: as regras do dono contadas no registro e o selo encadeado que detecta
// alteração e remoção de registros antigos. Só conta e confere; não corrige nada.
Item {
    id: aba
    objectName: "abaPainelIntegridade"
    readonly property var vm: app.v2.painelIntegridade
    readonly property string estado: vm && vm.estado !== undefined ? vm.estado : "vazio"
    readonly property bool temDado: estado === "pronto" || estado === "poucos" || estado === "vazio"
    readonly property var selo: vm && vm.selo ? vm.selo : ({})
    readonly property var selos: vm && vm.selos ? vm.selos : ({})
    readonly property var estrutura: vm && vm.estrutura ? vm.estrutura : ({})

    ScrollView {
        id: rolagem
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true
        visible: aba.temDado

        ColumnLayout {
            width: rolagem.availableWidth
            spacing: Theme.espacoBloco

            Aviso {
                Layout.fillWidth: true
                visible: aba.vm.demonstracao === true
                tipo: "aviso"
                texto: "Base de demonstração: as regras de evidência (I5, I13) não se aplicam às linhas fictícias."
            }
            Aviso {
                Layout.fillWidth: true
                visible: aba.estado === "vazio"
                tipo: "info"
                texto: "O registro ainda está vazio: as regras conferem, mas não há o que contar."
            }

            // A. regras do registro
            Painel {
                Layout.fillWidth: true
                titulo: "Regras do registro"
                subtitulo: aba.vm.resumo || ""
                espacamento: 0
                Repeater {
                    model: aba.vm.regras || []
                    delegate: PainelLinhaRegra {
                        required property var modelData
                        Layout.fillWidth: true
                        ident: modelData.id || ""
                        titulo: modelData.titulo || ""
                        consultiva: modelData.consultiva === true
                        situacao: modelData.situacao || "confere"
                        marca: modelData.marca || ""
                        garantia: modelData.garantia || ""
                        observacao: modelData.observacao || ""
                        exemplos: modelData.exemplos || ""
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: aba.width < 900 ? 1 : 2
                columnSpacing: Theme.espacoBloco
                rowSpacing: Theme.espacoBloco

                // B. selo do registro
                Painel {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    titulo: "Selo do registro"
                    subtitulo: aba.selo.texto || ""
                    espacamento: 10
                    Flow {
                        objectName: "seloSha256"
                        Layout.fillWidth: true
                        spacing: 6
                        Repeater {
                            model: aba.selo.grupos || []
                            delegate: Text {
                                required property var modelData
                                text: String(modelData)
                                color: Theme.texto
                                font.pixelSize: Theme.tPequeno
                                font.family: Theme.familiaMono
                            }
                        }
                        Accessible.role: Accessible.StaticText
                        Accessible.name: "SHA-256 " + (aba.selo.sha256 || "")
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Rectangle {
                            Layout.alignment: Qt.AlignVCenter
                            width: 7; height: 7; radius: 3.5
                            color: (aba.selos.total || 0) === 0 ? Theme.texto3
                                   : (aba.selos.ultimoConfere ? Theme.acento : Theme.perigo)
                        }
                        Text {
                            objectName: "textoUltimoSelo"
                            Layout.fillWidth: true
                            text: aba.selos.ultimoTexto || ""
                            color: (aba.selos.total || 0) === 0 || aba.selos.ultimoConfere ? Theme.texto2 : Theme.perigo
                            font.pixelSize: Theme.tPequeno
                            wrapMode: Text.Wrap
                        }
                    }
                    Text {
                        visible: (aba.selos.total || 0) > 1
                        Layout.fillWidth: true
                        text: (aba.selos.conferem || 0) + " de " + (aba.selos.total || 0) + " selos gravados conferem"
                        color: Theme.texto3
                        font.pixelSize: Theme.tLegenda
                        font.features: { "tnum": 1 }
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 8
                        Botao {
                            objectName: "botaoSelarAgora"
                            text: "Selar agora"
                            icone: "selo"
                            variante: "primario"
                            compacto: true
                            carregando: aba.vm.selando === true
                            enabled: aba.vm.selando !== true
                            onClicked: aba.vm.selarAgora()
                        }
                        Botao {
                            text: "Abrir pasta dos selos"
                            icone: "pasta"
                            variante: "fantasma"
                            compacto: true
                            onClicked: aba.vm.abrirPastaSelos()
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "O selo detecta alteração e remoção de registros antigos. Quem tem acesso ao disco pode refazer banco e selos: guarde uma cópia do selo fora desta máquina. A remoção de um usuário desvincula os registros dele; o selo não cobre esse vínculo."
                        color: Theme.texto3
                        font.pixelSize: Theme.tLegenda
                        wrapMode: Text.Wrap
                    }
                }

                // C. estrutura
                Painel {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    titulo: "Estrutura"
                    subtitulo: "Numeração e diário do banco"
                    espacamento: 4
                    Repeater {
                        model: aba.estrutura.linhas || []
                        delegate: ParRotuloValor {
                            required property var modelData
                            Layout.fillWidth: true
                            rotulo: modelData.rotulo || ""
                            valor: modelData.valor || "–"
                            cor: modelData.ok === false ? Theme.perigo : Theme.texto
                        }
                    }
                }
            }
            Item { Layout.preferredHeight: 8 }
        }
    }

    EstadoBloco {
        objectName: "estadoIntegridade"
        anchors.fill: parent
        visible: !aba.temDado
        estado: aba.estado
        erro: aba.vm.erro || ""
        vazioIcone: "selo"
        onTentarNovamente: aba.vm.recarregar()
    }
}
