import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Sobreposição que abre depois de um acesso CONCEDIDO no terminal. Mostra as áreas que o nível
// da pessoa libera (nível N enxerga 1..N). O conteúdo vem de app.sessao.conteudo(n), que devolve
// vazio para qualquer área acima do nível: a tela nunca decide o que liberar.
Rectangle {
    id: area
    readonly property var s: app.sessao
    property int atual: s.areaSolicitada
    color: Theme.janela
    visible: opacity > 0
    opacity: s.ativa ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.lento; easing.type: Easing.OutCubic } }
    Connections {
        target: area.s
        function onAtivaChanged() { if (area.s.ativa) area.atual = area.s.areaSolicitada }
    }
    // clique em área vazia renova o tempo de inatividade
    MouseArea { anchors.fill: parent; onPressed: function(m) { m.accepted = false; s.renovar() } }

    readonly property color corArea: Theme.corNivel(atual)

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---------------------------------------------------------------- barra superior
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 64
            color: Theme.lateral
            Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 1; color: Theme.borda }
            RowLayout {
                anchors { fill: parent; leftMargin: 22; rightMargin: 22 }
                spacing: 14
                Rectangle {
                    width: 36; height: 36; radius: 11
                    color: Theme.sucessoSuave
                    Icone { anchors.centerIn: parent; nome: "escudoOk"; tamanho: 20; traco: 2; cor: Theme.sucesso }
                }
                ColumnLayout {
                    spacing: 1
                    Text { text: "Acesso liberado"; color: Theme.sucesso; font.pixelSize: Theme.tLegenda; font.weight: Font.DemiBold }
                    RowLayout {
                        spacing: 8
                        Text { text: s.nome; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                        Selo { texto: "Nível " + s.nivelUsuario + " · " + s.nivelDescricao; cor: Theme.corNivel(s.nivelUsuario) }
                        Text { visible: s.cargo !== ""; text: s.cargo; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                    }
                }
                Item { Layout.fillWidth: true }
                ColumnLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignVCenter
                    RowLayout {
                        spacing: 6
                        Icone { nome: "relogio"; tamanho: 13; cor: s.tempoRestante <= 15 ? Theme.aviso : Theme.texto3 }
                        Text {
                            text: "Fecha sozinha em " + s.tempoRestante + " s"
                            color: s.tempoRestante <= 15 ? Theme.aviso : Theme.texto3
                            font.pixelSize: Theme.tLegenda
                            font.features: { "tnum": 1 }
                        }
                    }
                    Rectangle {
                        implicitWidth: 150; implicitHeight: 3; radius: 1.5
                        color: Theme.realce
                        Rectangle {
                            width: s.tempoTotal > 0 ? parent.width * s.tempoRestante / s.tempoTotal : 0
                            height: parent.height; radius: 1.5
                            color: s.tempoRestante <= 15 ? Theme.aviso : Theme.acento
                            Behavior on width { NumberAnimation { duration: 900 } }
                        }
                    }
                }
                Botao { text: "Prolongar"; variante: "fantasma"; compacto: true; onClicked: s.renovar() }
                Botao { text: "Encerrar sessão"; icone: "cadeado"; variante: "perigo"; onClicked: s.encerrar() }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // ------------------------------------------------------------ trilho de áreas
            Rectangle {
                Layout.fillHeight: true
                Layout.preferredWidth: 250
                color: Theme.lateral
                Rectangle { anchors { right: parent.right; top: parent.top; bottom: parent.bottom } width: 1; color: Theme.borda }
                ColumnLayout {
                    anchors { fill: parent; margins: 14; topMargin: 18 }
                    spacing: 6
                    Text { Layout.leftMargin: 6; Layout.bottomMargin: 6; text: "Áreas do Ministério"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                    Repeater {
                        model: s.areas
                        delegate: Rectangle {
                            id: item
                            required property var modelData
                            readonly property bool escolhida: area.atual === modelData.nivel
                            readonly property color cor: Theme.corNivel(modelData.nivel)
                            Layout.fillWidth: true
                            implicitHeight: col.implicitHeight + 22
                            radius: Theme.raio
                            color: escolhida ? Theme.superficie : (hover.hovered && modelData.liberada ? Theme.realce : "transparent")
                            border.color: escolhida ? Qt.rgba(cor.r, cor.g, cor.b, 0.55) : "transparent"
                            opacity: modelData.liberada ? 1 : 0.55
                            HoverHandler { id: hover; cursorShape: item.modelData.liberada ? Qt.PointingHandCursor : Qt.ForbiddenCursor }
                            TapHandler { onTapped: { if (item.modelData.liberada) { area.atual = item.modelData.nivel; s.renovar() } } }
                            Dica { visible: hover.hovered && !item.modelData.liberada; text: "Exige nível " + item.modelData.nivel + ". Você tem nível " + s.nivelUsuario + "." }
                            RowLayout {
                                id: col
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                                spacing: 10
                                Rectangle {
                                    width: 30; height: 30; radius: 9
                                    Layout.alignment: Qt.AlignTop
                                    color: Qt.rgba(item.cor.r, item.cor.g, item.cor.b, item.modelData.liberada ? 0.16 : 0.06)
                                    Icone {
                                        anchors.centerIn: parent
                                        nome: item.modelData.liberada ? (item.modelData.nivel === 3 ? "alerta" : item.modelData.nivel === 2 ? "camadas" : "usuarios") : "cadeado"
                                        tamanho: 15; traco: 2
                                        cor: item.modelData.liberada ? item.cor : Theme.texto3
                                    }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text { text: "Nível " + item.modelData.nivel; color: item.cor; font.pixelSize: Theme.tLegenda; font.weight: Font.DemiBold }
                                    Text { Layout.fillWidth: true; text: item.modelData.titulo; color: item.modelData.liberada ? Theme.texto : Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; wrapMode: Text.WordWrap }
                                    Text { Layout.fillWidth: true; text: item.modelData.liberada ? item.modelData.descricao : "Bloqueada para o seu nível"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.WordWrap }
                                }
                            }
                        }
                    }
                    Item { Layout.fillHeight: true }
                    Rectangle {
                        Layout.fillWidth: true
                        radius: Theme.raio
                        color: Theme.superficie
                        border.color: Theme.borda
                        implicitHeight: rod.implicitHeight + 20
                        ColumnLayout {
                            id: rod
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                            spacing: 3
                            Text { text: "Autenticação facial"; color: Theme.texto2; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                            Text { text: "Liberada às " + s.abertaEm + " para a área de nível " + s.areaSolicitada; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            Text { visible: s.similaridade >= 0; text: "Similaridade " + s.similaridade.toFixed(3); color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.features: { "tnum": 1 } }
                            Text { text: "Dados de demonstração, fictícios."; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                        }
                    }
                }
            }

            // ------------------------------------------------------------ conteúdo
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                Loader {
                    id: conteudo
                    anchors.fill: parent
                    active: s.ativa
                    source: !s.ativa ? "" : area.atual === 3 ? "AreaCofre.qml" : area.atual === 2 ? "AreaDiretores.qml" : "AreaComum.qml"
                    onLoaded: { item.dados = s.conteudo(area.atual); entrada.restart() }
                    NumberAnimation { id: entrada; target: conteudo; property: "opacity"; from: 0; to: 1; duration: Theme.medio }
                }
            }
        }
    }
}
