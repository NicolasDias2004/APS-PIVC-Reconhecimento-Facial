import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Nível 3: o cofre de toxinas. Inventário, sensores e retiradas, tudo fictício.
ScrollView {
    id: pagina
    property var dados: ({})
    readonly property color cor: Theme.corNivel(3)
    readonly property var sensores: dados.sensores || []
    readonly property var temperatura: dados.temperatura || []
    readonly property var lotes: dados.lotes || []
    readonly property var retiradas: dados.retiradas || []
    readonly property var portas: dados.portas || []
    readonly property var totais: dados.totais || ({})
    contentWidth: availableWidth
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    function corRisco(r) { return r === "crítico" ? Theme.perigo : r === "alto" ? Theme.aviso : Theme.texto2 }
    function demo() { app.notificar("info", "Demonstração: nenhum comando é enviado ao cofre.") }

    ColumnLayout {
        width: pagina.availableWidth
        spacing: 18

        // faixa de acesso restrito
        Rectangle {
            Layout.fillWidth: true
            Layout.margins: 28
            Layout.bottomMargin: 0
            implicitHeight: faixa.implicitHeight + 36
            radius: Theme.raioGrande
            color: Qt.rgba(pagina.cor.r, pagina.cor.g, pagina.cor.b, 0.10)
            border.color: Qt.rgba(pagina.cor.r, pagina.cor.g, pagina.cor.b, 0.45)
            RowLayout {
                id: faixa
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 22; rightMargin: 22 }
                spacing: 16
                Rectangle {
                    width: 48; height: 48; radius: 14
                    color: Qt.rgba(pagina.cor.r, pagina.cor.g, pagina.cor.b, 0.2)
                    Icone { anchors.centerIn: parent; nome: "alerta"; tamanho: 24; traco: 2; cor: pagina.cor }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    RowLayout {
                        spacing: 8
                        Text { text: dados.titulo || ""; color: Theme.texto; font.pixelSize: Theme.tTitulo; font.weight: Font.DemiBold }
                        Selo { texto: "Acesso restrito · nível 3"; cor: pagina.cor; solido: true }
                    }
                    Text { Layout.fillWidth: true; text: "Material biológico de risco. Toda retirada exige dupla custódia e fica registrada."; color: Theme.texto2; font.pixelSize: Theme.tCorpo; wrapMode: Text.WordWrap }
                    Flow {
                        Layout.fillWidth: true
                        Layout.topMargin: 6
                        spacing: 18
                        Repeater {
                            model: pagina.portas
                            delegate: RowLayout {
                                required property var modelData
                                spacing: 5
                                Rectangle { width: 7; height: 7; radius: 3.5; color: modelData.estado === "aberta" ? Theme.perigo : Theme.sucesso }
                                Text { text: modelData.nome + ": "; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                                Text { text: modelData.estado; color: Theme.texto; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 28
            Layout.rightMargin: 28
            spacing: 12
            Repeater {
                model: pagina.sensores
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: 80
                    radius: Theme.raio
                    color: Theme.superficie
                    border.color: modelData.ok ? Theme.borda : Theme.perigo
                    ColumnLayout {
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                        spacing: 3
                        RowLayout {
                            Text { text: modelData.nome; color: Theme.texto2; font.pixelSize: Theme.tLegenda; Layout.fillWidth: true }
                            Rectangle { width: 7; height: 7; radius: 3.5; color: modelData.ok ? Theme.sucesso : Theme.perigo }
                        }
                        RowLayout {
                            spacing: 5
                            Text { text: modelData.valor; color: Theme.texto; font.pixelSize: 24; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                            Text { text: modelData.unidade; color: Theme.texto3; font.pixelSize: Theme.tPequeno; Layout.alignment: Qt.AlignBottom; Layout.bottomMargin: 5 }
                            Item { Layout.fillWidth: true }
                            Text { text: "faixa " + modelData.faixa; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                        }
                    }
                }
            }
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
                    titulo: "Inventário"
                    subtitulo: (totais.lotes || 0) + " lotes, " + (totais.criticos || 0) + " de risco crítico"
                    espacamento: 0
                    cabecalhoDireita: Botao { text: "Solicitar abertura"; icone: "cadeado"; compacto: true; onClicked: pagina.demo() }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.bottomMargin: 8
                        spacing: 12
                        Text { Layout.preferredWidth: 80; text: "Código"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.fillWidth: true; text: "Agente"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: 80; text: "Risco"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: 70; text: "Quant."; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                        Text { Layout.preferredWidth: 84; text: "Validade"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                        Text { Layout.preferredWidth: 40; text: "Prat."; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                    }
                    Repeater {
                        model: pagina.lotes
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 0
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda; opacity: 0.7 }
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.topMargin: 9
                                Layout.bottomMargin: 9
                                spacing: 12
                                Text { Layout.preferredWidth: 80; text: modelData.codigo; color: pagina.cor; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    // fillWidth também nos textos: senão o máximo da coluna vira o tamanho do texto e a linha não estica
                                    Text { Layout.fillWidth: true; text: modelData.agente; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium; elide: Text.ElideRight }
                                    Text { Layout.fillWidth: true; text: "Origem: " + modelData.origem; color: Theme.texto3; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight }
                                }
                                Item { Layout.preferredWidth: 80; implicitHeight: 20; Selo { texto: modelData.risco; cor: pagina.corRisco(modelData.risco) } }
                                Text { Layout.preferredWidth: 70; text: modelData.quantidade + " " + modelData.unidade; color: Theme.texto; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                Text { Layout.preferredWidth: 84; text: modelData.validade; color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                Text { Layout.preferredWidth: 40; text: modelData.prateleira; color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight }
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.preferredWidth: 340
                Layout.maximumWidth: 340
                Layout.alignment: Qt.AlignTop
                spacing: 16
                Painel {
                    Layout.fillWidth: true
                    titulo: "Temperatura da câmara"
                    subtitulo: "Últimas 24 h, faixa segura de -82 a -74 °C"
                    Canvas {
                        id: curva
                        Layout.fillWidth: true
                        implicitHeight: 96
                        readonly property var pontos: pagina.temperatura
                        onPontosChanged: requestPaint()
                        onWidthChanged: requestPaint()
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.reset()
                            var n = pontos.length
                            if (n < 2) return
                            var w = width, h = height, min = -83, max = -73
                            function py(v) { return h - 14 - (v - min) / (max - min) * (h - 22) }
                            ctx.fillStyle = Qt.rgba(Theme.sucesso.r, Theme.sucesso.g, Theme.sucesso.b, 0.08)
                            ctx.fillRect(0, py(-74), w, py(-82) - py(-74))
                            ctx.strokeStyle = String(Theme.borda); ctx.lineWidth = 1
                            ctx.beginPath(); ctx.moveTo(0, py(-74)); ctx.lineTo(w, py(-74)); ctx.moveTo(0, py(-82)); ctx.lineTo(w, py(-82)); ctx.stroke()
                            ctx.strokeStyle = String(pagina.cor); ctx.lineWidth = 2
                            ctx.beginPath()
                            for (var i = 0; i < n; ++i) {
                                var x = i / (n - 1) * w, y = py(pontos[i].valor)
                                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                            }
                            ctx.stroke()
                            ctx.fillStyle = String(Theme.texto3); ctx.font = "10px sans-serif"
                            ctx.fillText(pontos[0].hora, 0, h - 2)
                            ctx.fillText(pontos[n - 1].hora, w - 22, h - 2)
                        }
                    }
                }
                Painel {
                    Layout.fillWidth: true
                    titulo: "Retiradas registradas"
                    subtitulo: "Últimos 30 dias"
                    espacamento: 0
                    Repeater {
                        model: pagina.retiradas
                        delegate: ColumnLayout {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            spacing: 0
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda; visible: index > 0; opacity: 0.7 }
                            ColumnLayout {
                                Layout.topMargin: 9
                                Layout.bottomMargin: 9
                                spacing: 2
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { text: modelData.lote + " · " + modelData.agente; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; Layout.fillWidth: true; elide: Text.ElideRight }
                                    Text { text: modelData.quantidade; color: pagina.cor; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                                }
                                Text { text: modelData.data + " · " + modelData.responsavel + " · " + modelData.finalidade; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            }
                        }
                    }
                }
            }
        }
    }
}
