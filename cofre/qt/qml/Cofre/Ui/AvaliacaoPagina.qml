import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import Cofre.Nativo

// Avaliação e demo: as 5 fases em uma imagem, autenticação por imagem (registrada no log)
// e avaliação quantitativa do reconhecedor (TAR, FAR, FRR e EER).
Item {
    id: pagina
    objectName: "paginaAvaliacao"
    readonly property var v: app.avaliacao
    property string aba: "demo"
    readonly property var filtroImagens: ["Imagens (*.jpg *.jpeg *.png *.bmp *.webp)", "Todos os arquivos (*)"]

    FileDialog {
        id: dialogoDemo
        title: "Imagem para a demonstração"
        nameFilters: pagina.filtroImagens
        onAccepted: v.demonstrar(selectedFile)
    }
    FileDialog {
        id: dialogoAuth
        title: "Imagem para autenticar"
        nameFilters: pagina.filtroImagens
        onAccepted: v.autenticar(selectedFile)
    }
    FolderDialog {
        id: dialogoPasta
        title: "Pasta com uma subpasta por pessoa"
        onAccepted: v.definirPasta(selectedFolder)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 18

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Avaliação e demonstração"
            descricao: "Veja o pipeline fase a fase e meça a precisão do reconhecedor"
            Segmentado {
                atual: pagina.aba
                opcoes: [
                    { valor: "demo", texto: "Fases do pipeline", dica: "Mostra o que cada fase produz em uma imagem" },
                    { valor: "auth", texto: "Autenticar imagem", dica: "Decide o acesso a partir de uma foto" },
                    { valor: "aval", texto: "Avaliar reconhecedor", dica: "TAR, FAR, FRR e EER em uma pasta de fotos" }
                ]
                onEscolhido: function(x) { pagina.aba = x }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: ["demo", "auth", "aval"].indexOf(pagina.aba)

            // ===================================================== demonstração das fases
            RowLayout {
                spacing: 16

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 16

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 240
                        radius: Theme.raioGrande
                        color: Theme.superficie
                        border.color: Theme.borda

                        VisorVideo {
                            anchors.fill: parent
                            anchors.margins: 1
                            fonte: v.fonteDemo
                            raio: Theme.raioGrande
                            corFundo: Theme.lateral
                            preencher: false
                            visible: v.fonteDemo.temImagem
                        }
                        Vazio {
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 40, 400)
                            visible: !v.fonteDemo.temImagem && !v.demoProcessando
                            icone: "camadas"
                            titulo: "Escolha uma foto com um rosto"
                            texto: "A imagem passa pelas 5 fases (aquisição, pré-processamento, segmentação, representação e reconhecimento). Nada é gravado no log."
                            acao: "Escolher imagem"
                            iconeAcao: "imagem"
                            onAcionado: dialogoDemo.open()
                        }
                        Carregando { anchors.centerIn: parent; visible: v.demoProcessando }

                        // resultado sobre a imagem
                        Rectangle {
                            visible: v.fonteDemo.temImagem && v.demoResultado.titulo !== undefined
                            anchors { left: parent.left; bottom: parent.bottom; margins: 14 }
                            radius: Theme.raio
                            color: Qt.rgba(0.06, 0.07, 0.09, 0.92)
                            border.color: v.demoResultado.tipo === "ok" ? Theme.sucesso : (v.demoResultado.tipo === "aviso" ? Theme.aviso : Theme.perigo)
                            implicitWidth: Math.min(parent.width - 28, resDemo.implicitWidth + 28)
                            implicitHeight: resDemo.implicitHeight + 20
                            ColumnLayout {
                                id: resDemo
                                anchors { fill: parent; margins: 10; leftMargin: 14; rightMargin: 14 }
                                spacing: 2
                                Text { text: v.demoResultado.titulo || ""; color: parent.parent.border.color; font.pixelSize: Theme.tCorpo; font.weight: Font.DemiBold }
                                Text { text: v.demoResultado.mensagem || ""; color: Theme.texto2; font.pixelSize: Theme.tPequeno; wrapMode: Text.WordWrap; Layout.maximumWidth: 460 }
                            }
                        }
                    }

                    // imagens intermediárias
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 150
                        visible: v.demoEtapas.length > 0
                        radius: Theme.raioGrande
                        color: Theme.superficie
                        border.color: Theme.borda
                        ListView {
                            anchors { fill: parent; margins: 12 }
                            orientation: ListView.Horizontal
                            spacing: 10
                            clip: true
                            model: v.demoEtapas
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
                            delegate: ColumnLayout {
                                required property var modelData
                                width: 108
                                spacing: 5
                                Rectangle {
                                    Layout.preferredWidth: 108
                                    Layout.preferredHeight: 100
                                    radius: Theme.raioPequeno
                                    color: Theme.lateral
                                    border.color: Theme.borda
                                    VisorVideo { anchors.fill: parent; anchors.margins: 1; fonte: modelData; raio: Theme.raioPequeno; corFundo: Theme.lateral; mostrarPontos: false }
                                }
                                Text { text: modelData.nome; color: Theme.texto2; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                            }
                        }
                    }
                }

                // painel lateral: controles e fases
                ScrollView {
                    Layout.preferredWidth: 340
                    Layout.fillHeight: true
                    contentWidth: availableWidth
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ColumnLayout {
                        width: parent.width
                        spacing: 16
                        Painel {
                            Layout.fillWidth: true
                            titulo: "Imagem"
                            subtitulo: v.demoArquivo !== "" ? v.demoArquivo : "Nenhuma imagem escolhida"
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Botao { Layout.fillWidth: true; text: v.demoArquivo !== "" ? "Trocar imagem" : "Escolher imagem"; icone: "imagem"; variante: "primario"; carregando: v.demoProcessando; enabled: !v.demoProcessando && app.modelosProntos; onClicked: dialogoDemo.open() }
                                Botao { text: "Salvar painel"; icone: "salvar"; enabled: v.demoEtapas.length > 0; dica: "Grava o mosaico das fases na pasta de relatórios"; onClicked: v.salvarPainel() }
                            }
                            Text { text: "Área usada na fase 5"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.topMargin: 4 }
                            Segmentado {
                                Layout.fillWidth: true
                                atual: v.demoNivel
                                opcoes: [{ valor: 1, texto: "Nível 1" }, { valor: 2, texto: "Nível 2" }, { valor: 3, texto: "Nível 3" }]
                                onEscolhido: function(x) { v.definirNivelDemo(x) }
                            }
                        }
                        Repeater {
                            model: v.demoFases
                            delegate: Painel {
                                required property var modelData
                                Layout.fillWidth: true
                                titulo: "Fase " + modelData.fase + ": " + modelData.titulo
                                espacamento: 6
                                Repeater {
                                    model: modelData.linhas
                                    delegate: RowLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: 12
                                        Text { text: modelData[0]; color: Theme.texto3; font.pixelSize: Theme.tPequeno; Layout.preferredWidth: 118; Layout.alignment: Qt.AlignTop }
                                        Text { text: modelData[1]; color: Theme.texto; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.features: { "tnum": 1 } }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ===================================================== autenticar por imagem
            RowLayout {
                spacing: 16
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: Theme.raioGrande
                    color: Theme.superficie
                    border.color: v.authResultado.tipo === "ok" ? Theme.sucesso : (v.authResultado.tipo === "erro" ? Theme.perigo : Theme.borda)
                    Behavior on border.color { ColorAnimation { duration: Theme.medio } }
                    VisorVideo {
                        anchors.fill: parent
                        anchors.margins: 1
                        fonte: v.fonteAuth
                        raio: Theme.raioGrande
                        corFundo: Theme.lateral
                        preencher: false
                        visible: v.fonteAuth.temImagem
                    }
                    Vazio {
                        anchors.centerIn: parent
                        width: Math.min(parent.width - 40, 400)
                        visible: !v.fonteAuth.temImagem && !v.authProcessando
                        icone: "escudo"
                        titulo: "Autentique a partir de uma foto"
                        texto: "Mesma decisão do terminal, sem prova de vida. A tentativa fica registrada na auditoria de acessos."
                        acao: "Escolher imagem"
                        iconeAcao: "imagem"
                        onAcionado: dialogoAuth.open()
                    }
                    Carregando { anchors.centerIn: parent; visible: v.authProcessando }
                }
                ColumnLayout {
                    Layout.preferredWidth: 340
                    Layout.maximumWidth: 340
                    Layout.fillHeight: true
                    spacing: 16
                    Painel {
                        Layout.fillWidth: true
                        titulo: "Área protegida"
                        subtitulo: "Nível exigido para liberar o acesso"
                        Segmentado {
                            Layout.fillWidth: true
                            atual: v.authNivel
                            habilitado: !v.authProcessando
                            opcoes: [{ valor: 1, texto: "Nível 1" }, { valor: 2, texto: "Nível 2" }, { valor: 3, texto: "Nível 3" }]
                            onEscolhido: function(x) { v.definirNivelAuth(x) }
                        }
                        Botao {
                            Layout.fillWidth: true
                            text: v.authArquivo !== "" ? "Autenticar outra imagem" : "Escolher imagem"
                            icone: "imagem"
                            variante: "primario"
                            carregando: v.authProcessando
                            enabled: !v.authProcessando && app.modelosProntos
                            onClicked: dialogoAuth.open()
                        }
                        RowLayout {
                            spacing: 6
                            Icone { nome: "info"; tamanho: 14; cor: Theme.texto3 }
                            Text { Layout.fillWidth: true; text: "Cada autenticação entra no log de acessos."; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.WordWrap }
                        }
                    }
                    Painel {
                        Layout.fillWidth: true
                        visible: v.authResultado.titulo !== undefined
                        titulo: v.authResultado.titulo || ""
                        subtitulo: v.authArquivo
                        cabecalhoDireita: Icone {
                            nome: v.authResultado.concedido ? "escudoOk" : "escudoX"
                            tamanho: 22
                            cor: v.authResultado.concedido ? Theme.sucesso : Theme.perigo
                        }
                        Text { Layout.fillWidth: true; text: v.authResultado.mensagem || ""; color: Theme.texto2; font.pixelSize: Theme.tPequeno; wrapMode: Text.WordWrap }
                        GridLayout {
                            visible: v.authResultado.usuario !== undefined
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 12
                            rowSpacing: 8
                            Text { text: "Pessoa"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: v.authResultado.usuario || ""; color: Theme.texto; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true; elide: Text.ElideRight }
                            Text { text: "Nível da pessoa"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: v.authResultado.nivelUsuario ? String(v.authResultado.nivelUsuario) : "–"; color: Theme.corNivel(v.authResultado.nivelUsuario || 0); font.pixelSize: Theme.tPequeno }
                            Text { text: "Nível exigido"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: String(v.authResultado.nivelExigido || ""); color: Theme.texto; font.pixelSize: Theme.tPequeno }
                            Text { text: "Similaridade"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: (v.authResultado.similaridade || "–") + " (limiar " + (v.authResultado.limiar || "") + ")"; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.features: { "tnum": 1 } }
                            Text { text: "Rostos na imagem"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: String(v.authResultado.rostos !== undefined ? v.authResultado.rostos : ""); color: v.authResultado.rostos > 1 ? Theme.aviso : Theme.texto; font.pixelSize: Theme.tPequeno }
                        }
                        Botao { text: "Ver na auditoria"; icone: "acessos"; variante: "fantasma"; compacto: true; visible: v.authResultado.usuario !== undefined; onClicked: app.navegar("acessos") }
                    }
                    Item { Layout.fillHeight: true }
                }
            }

            // ===================================================== avaliação do reconhecedor
            ScrollView {
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ColumnLayout {
                    width: parent.width
                    spacing: 16

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Conjunto de teste"
                        subtitulo: "Uma subpasta por pessoa (pasta/pessoa/foto.jpg). Pares da mesma pessoa são genuínos, os demais são impostores."
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 34
                                radius: Theme.raioPequeno
                                color: Theme.campo
                                border.color: Theme.borda
                                RowLayout {
                                    anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                                    spacing: 8
                                    Icone { nome: "pasta"; tamanho: 15; cor: Theme.texto3 }
                                    Text {
                                        Layout.fillWidth: true
                                        text: v.avalPasta !== "" ? v.avalPasta : "Nenhuma pasta escolhida"
                                        color: v.avalPasta !== "" ? Theme.texto : Theme.texto3
                                        font.pixelSize: Theme.tPequeno
                                        elide: Text.ElideMiddle
                                    }
                                }
                            }
                            Botao { text: "Escolher pasta"; icone: "pasta"; enabled: !v.avalProcessando; onClicked: dialogoPasta.open() }
                            Botao { text: "Usar fotos de teste"; variante: "fantasma"; enabled: !v.avalProcessando; dica: "tests/fixtures/pessoas, incluídas no projeto"; onClicked: v.usarFotosTeste() }
                            Botao { text: "Avaliar"; icone: "play"; variante: "primario"; carregando: v.avalProcessando; enabled: !v.avalProcessando && v.avalPasta !== "" && app.modelosProntos; onClicked: v.avaliar() }
                        }
                    }

                    Vazio {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 40
                        Layout.preferredWidth: 420
                        visible: v.avalResultado.valido === undefined && !v.avalProcessando
                        icone: "pulso"
                        titulo: "Nenhuma avaliação ainda"
                        texto: "Escolha uma pasta e clique em Avaliar. O resultado mostra as taxas no limiar atual e uma varredura de limiares."
                    }
                    ColumnLayout {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 40
                        visible: v.avalProcessando
                        spacing: 10
                        Carregando { Layout.alignment: Qt.AlignHCenter }
                        Text { text: "Extraindo embeddings e comparando pares..."; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        visible: (v.avalResultado.aviso || "") !== ""
                        implicitHeight: textoAviso.implicitHeight + 20
                        radius: Theme.raio
                        color: Theme.avisoSuave
                        border.color: Qt.rgba(Theme.aviso.r, Theme.aviso.g, Theme.aviso.b, 0.35)
                        RowLayout {
                            anchors { fill: parent; margins: 10; leftMargin: 12 }
                            spacing: 8
                            Icone { nome: "alerta"; tamanho: 16; cor: Theme.aviso; Layout.alignment: Qt.AlignTop }
                            Text { id: textoAviso; Layout.fillWidth: true; text: v.avalResultado.aviso || ""; color: Theme.texto; font.pixelSize: Theme.tPequeno; wrapMode: Text.WordWrap }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: v.avalResultado.valido === true && !v.avalProcessando
                        Layout.fillHeight: false   // não herda o preenchimento dos indicadores
                        spacing: 12
                        Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "TAR (aceitação correta)"; valor: v.avalResultado.tar || "–"; cor: Theme.sucesso; detalhe: "limiar " + Number(v.avalResultado.limiar || 0).toFixed(3) }
                        Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "FAR (impostor aceito)"; valor: v.avalResultado.far || "–"; cor: Theme.perigo; detalhe: (v.avalResultado.impostores || 0) + " pares impostores" }
                        Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "FRR (genuíno rejeitado)"; valor: v.avalResultado.frr || "–"; cor: Theme.aviso; detalhe: (v.avalResultado.genuinos || 0) + " pares genuínos" }
                        Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "EER"; valor: v.avalResultado.eer || "–"; cor: Theme.acento; detalhe: "no limiar " + (v.avalResultado.eerLimiar || "–") }
                        Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Conjunto"; valor: (v.avalResultado.pessoas || 0) + " pessoas"; detalhe: (v.avalResultado.imagens || 0) + " imagens, " + (v.avalResultado.semRosto || 0) + " sem rosto" }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: v.avalResultado.valido === true && !v.avalProcessando
                        spacing: 16

                        Painel {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            titulo: "Curva de decisão"
                            subtitulo: "TAR e FAR conforme o limiar de similaridade"
                            cabecalhoDireita: RowLayout {
                                spacing: 12
                                Legenda { cor: Theme.sucesso; texto: "TAR" }
                                Legenda { cor: Theme.perigo; texto: "FAR" }
                                Legenda { cor: Theme.texto2; texto: "limiar atual"; tracejada: true }
                            }
                            Canvas {
                                id: curva
                                Layout.fillWidth: true
                                implicitHeight: 240
                                readonly property var pontos: v.avalResultado.curva || []
                                readonly property real limiar: v.avalResultado.limiar || 0
                                onPontosChanged: requestPaint()
                                onWidthChanged: requestPaint()
                                onPaint: {
                                    var ctx = getContext("2d")
                                    ctx.reset()
                                    var esq = 38, dir = 10, topo = 8, base = 26
                                    var w = width - esq - dir, h = height - topo - base
                                    if (pontos.length === 0 || w <= 0) return
                                    var min = pontos[0].limiar, max = pontos[pontos.length - 1].limiar
                                    function px(l) { return esq + (l - min) / Math.max(1e-6, max - min) * w }
                                    function py(f) { return topo + (1 - f) * h }
                                    ctx.font = "11px sans-serif"
                                    ctx.lineWidth = 1
                                    for (var i = 0; i <= 4; ++i) {
                                        var y = py(i / 4)
                                        ctx.strokeStyle = String(Theme.borda)
                                        ctx.beginPath(); ctx.moveTo(esq, y); ctx.lineTo(esq + w, y); ctx.stroke()
                                        ctx.fillStyle = String(Theme.texto3)
                                        ctx.fillText((i * 25) + "%", 2, y + 4)
                                    }
                                    for (var k = 0; k <= 4; ++k) {
                                        var l = min + (max - min) * k / 4
                                        ctx.fillText(l.toFixed(2), px(l) - 12, height - 6)
                                    }
                                    function serie(campo, cor) {
                                        ctx.strokeStyle = cor
                                        ctx.lineWidth = 2
                                        ctx.beginPath()
                                        var iniciou = false
                                        for (var j = 0; j < pontos.length; ++j) {
                                            var val = pontos[j][campo]
                                            if (val === null || val === undefined) { iniciou = false; continue }
                                            if (!iniciou) { ctx.moveTo(px(pontos[j].limiar), py(val)); iniciou = true }
                                            else ctx.lineTo(px(pontos[j].limiar), py(val))
                                        }
                                        ctx.stroke()
                                    }
                                    serie("tar", String(Theme.sucesso))
                                    serie("far", String(Theme.perigo))
                                    if (limiar >= min && limiar <= max) {
                                        ctx.strokeStyle = String(Theme.texto2)
                                        ctx.lineWidth = 1
                                        ctx.setLineDash([4, 4])
                                        ctx.beginPath(); ctx.moveTo(px(limiar), topo); ctx.lineTo(px(limiar), topo + h); ctx.stroke()
                                        ctx.setLineDash([])
                                    }
                                }
                            }
                        }

                        Painel {
                            Layout.preferredWidth: 340
                            Layout.alignment: Qt.AlignTop
                            titulo: "Varredura de limiares"
                            subtitulo: "Linha destacada: mais próxima do limiar em uso"
                            espacamento: 0
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.topMargin: 8
                                Layout.bottomMargin: 6
                                Layout.leftMargin: 6
                                Layout.rightMargin: 6
                                Text { Layout.preferredWidth: 64; text: "Limiar"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                                Text { Layout.fillWidth: true; text: "TAR"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                                Text { Layout.fillWidth: true; text: "FRR"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                                Text { Layout.fillWidth: true; text: "FAR"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium; horizontalAlignment: Text.AlignRight }
                            }
                            Repeater {
                                model: v.modeloVarredura
                                delegate: Rectangle {
                                    id: lv
                                    required property var model
                                    Layout.fillWidth: true
                                    implicitHeight: 26
                                    radius: 5
                                    color: model.atual ? Theme.acentoSuave : "transparent"
                                    RowLayout {
                                        anchors { fill: parent; leftMargin: 6; rightMargin: 6 }
                                        Text { Layout.preferredWidth: 64; text: lv.model.limiar; color: lv.model.atual ? Theme.acento : Theme.texto; font.pixelSize: Theme.tPequeno; font.features: { "tnum": 1 } }
                                        Text { Layout.fillWidth: true; text: lv.model.tar; color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                        Text { Layout.fillWidth: true; text: lv.model.frr; color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                        Text { Layout.fillWidth: true; text: lv.model.far; color: Theme.texto2; font.pixelSize: Theme.tPequeno; horizontalAlignment: Text.AlignRight; font.features: { "tnum": 1 } }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    component Legenda: RowLayout {
        property color cor
        property string texto
        property bool tracejada: false
        spacing: 5
        Rectangle { width: 14; height: 2; color: tracejada ? "transparent" : cor; border.width: tracejada ? 1 : 0; border.color: cor }
        Text { text: texto; color: Theme.texto2; font.pixelSize: Theme.tLegenda }
    }
}
