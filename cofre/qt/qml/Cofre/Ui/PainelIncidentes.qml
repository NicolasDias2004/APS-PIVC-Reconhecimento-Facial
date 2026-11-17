import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Aba Incidentes do Painel: o registro transformado em fatos com nome. Consultivo: descreve padrões,
// não acusa pessoas. Nada aqui altera o acesso nem grava no registro.
Item {
    id: aba
    objectName: "abaPainelIncidentes"
    readonly property var vm: app.v2.painelIncidentes
    readonly property string estado: vm && vm.estado !== undefined ? vm.estado : "vazio"
    readonly property bool temDado: estado === "pronto" || estado === "poucos"
    readonly property var contagens: vm && vm.contagens ? vm.contagens : ({})
    readonly property var lista: vm ? vm.incidentes : null
    property bool regrasAbertas: false

    function rotulo(texto, chave) { return texto + " " + (contagens[chave] || 0) }
    function selecionadoAtual() {
        if (!lista) return ({})
        for (var i = 0; i < lista.contagem; ++i) {
            var it = lista.item(i)
            if (it.id === vm.selecionado) return it
        }
        return ({})
    }
    function mover(passo) {
        if (!lista || lista.contagem === 0) return
        var atual = -1
        for (var i = 0; i < lista.contagem; ++i) if (lista.item(i).id === vm.selecionado) atual = i
        var novo = Math.max(0, Math.min(lista.contagem - 1, atual + passo))
        vm.selecionar(lista.item(novo).id)
        cartoes.positionViewAtIndex(novo, ListView.Contain)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 14

        // A. filtros
        Flow {
            Layout.fillWidth: true
            spacing: 12
            Segmentado {
                objectName: "filtroIncidentes"
                atual: aba.vm.filtroTipo || ""
                opcoes: [
                    { valor: "", texto: aba.rotulo("Todos", "todos") },
                    { valor: "bloqueio", texto: aba.rotulo("Bloqueio", "bloqueio") },
                    { valor: "acima_do_nivel", texto: aba.rotulo("Acima do nível", "acima_do_nivel") },
                    { valor: "prova_de_vida", texto: aba.rotulo("Prova de vida", "prova_de_vida") },
                    { valor: "multiplos", texto: aba.rotulo("Mais de uma pessoa", "multiplos") }
                ]
                onEscolhido: function(valor) { aba.vm.definirFiltroTipo(valor) }
            }
            SeloConsultivo { texto: "Consultivo: descreve padrões, não acusa pessoas" }
        }

        // B + C. lista e linha do tempo
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 300

            RowLayout {
                anchors.fill: parent
                visible: aba.temDado
                spacing: Theme.espacoBloco

                ListView {
                    id: cartoes
                    objectName: "listaIncidentes"
                    Layout.preferredWidth: Math.min(420, aba.width * 0.45)
                    Layout.fillHeight: true
                    clip: true
                    spacing: 8
                    boundsBehavior: Flickable.StopAtBounds
                    activeFocusOnTab: true
                    model: aba.lista
                    Accessible.role: Accessible.List
                    Accessible.name: "Incidentes"
                    Keys.onUpPressed: aba.mover(-1)
                    Keys.onDownPressed: aba.mover(1)
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: Rectangle {
                        id: cartao
                        required property var model
                        required property int index
                        readonly property bool escolhido: cartao.model.id === aba.vm.selecionado
                        width: cartoes.width - 8
                        height: coluna.implicitHeight + 24
                        radius: Theme.raio
                        color: escolhido ? Theme.elevada : (sobre.hovered ? Theme.hover : Theme.superficie)
                        border.color: escolhido ? Theme.bordaForte : Theme.borda
                        Accessible.role: Accessible.ListItem
                        Accessible.name: (cartao.model.titulo || "") + ", " + (cartao.model.inicio || "") + ", "
                                         + (cartao.model.resumo || "")
                        Rectangle {
                            visible: cartao.escolhido
                            width: 3; radius: 1.5
                            anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 8 }
                            color: Theme.acento
                        }
                        ColumnLayout {
                            id: coluna
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12; leftMargin: 18 }
                            spacing: 4
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Icone { nome: "incidente"; tamanho: 16; cor: cartao.model.gravidade === "alta" ? Theme.perigo : Theme.aviso }
                                Text {
                                    Layout.fillWidth: true
                                    text: cartao.model.titulo || ""
                                    color: Theme.texto
                                    font.pixelSize: Theme.tCorpo
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Selo {
                                    texto: cartao.model.gravidade === "alta" ? "alta" : "média"
                                    cor: cartao.model.gravidade === "alta" ? Theme.perigo : Theme.aviso
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: (cartao.model.inicio || "") + " a " + (cartao.model.fim || "")
                                      + " · " + (cartao.model.tentativas || 0) + (cartao.model.tentativas === 1 ? " tentativa" : " tentativas")
                                      + " · nível " + (cartao.model.nivelExigido || "")
                                color: Theme.texto2
                                font.pixelSize: Theme.tPequeno
                                font.features: { "tnum": 1 }
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: cartao.model.resumo || ""
                                color: Theme.texto3
                                font.pixelSize: Theme.tPequeno
                                wrapMode: Text.Wrap
                            }
                            Text {
                                visible: (cartao.model.pessoa || "") !== ""
                                text: cartao.model.pessoa || ""
                                color: Theme.texto2
                                font.pixelSize: Theme.tLegenda
                            }
                        }
                        HoverHandler { id: sobre }
                        TapHandler { onTapped: { aba.vm.selecionar(cartao.model.id); cartoes.forceActiveFocus() } }
                    }
                }

                PainelLinhaTempo {
                    objectName: "linhaTempoIncidente"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    readonly property var atual: aba.vm.selecionado !== "" ? aba.selecionadoAtual() : ({})
                    linhas: aba.vm.linhaTempo || []
                    limiar: aba.vm.limiar !== undefined ? aba.vm.limiar : -1
                    titulo: atual.titulo || "Linha do tempo"
                    subtitulo: atual.inicio ? atual.inicio + " a " + atual.fim + " · tentativas do incidente em destaque" : ""
                    pessoa: atual.pessoa || ""
                    onAbrirAuditoria: aba.vm.abrirNaAuditoria()
                }
            }

            Rectangle {
                anchors.fill: parent
                visible: !aba.temDado
                radius: Theme.raioGrande
                color: Theme.superficie
                border.color: Theme.borda
                EstadoBloco {
                    objectName: "estadoIncidentes"
                    anchors.fill: parent
                    estado: aba.estado
                    erro: aba.vm.erro || ""
                    vazioIcone: "incidente"
                    vazioTitulo: "Nenhum incidente no período"
                    vazioTexto: "As regras aplicadas estão em Como o painel classifica"
                    onTentarNovamente: aba.vm.recarregar()
                }
            }
        }

        // D. regras de classificação (recolhível)
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: colunaRegras.implicitHeight + 20
            radius: Theme.raio
            color: Theme.superficie
            border.color: Theme.borda
            ColumnLayout {
                id: colunaRegras
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10; leftMargin: 14; rightMargin: 14 }
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Icone { nome: aba.regrasAbertas ? "baixo" : "direita"; tamanho: 14; cor: Theme.texto2 }
                    Text {
                        Layout.fillWidth: true
                        text: "Como o painel classifica"
                        color: Theme.texto
                        font.pixelSize: Theme.tCorpo
                        font.weight: Font.DemiBold
                    }
                    TapHandler { onTapped: aba.regrasAbertas = !aba.regrasAbertas }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Como o painel classifica"
                }
                Repeater {
                    model: aba.regrasAbertas ? (aba.vm.regras || []) : []
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 2
                        Text { text: modelData.titulo || ""; color: Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold }
                        Text {
                            Layout.fillWidth: true
                            text: modelData.regra || ""
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }
    }
}
