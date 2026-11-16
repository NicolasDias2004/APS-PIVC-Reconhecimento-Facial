import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Cofre.Nativo

// Terminal de acesso: câmera dominante à esquerda, painel compacto à direita.
// Toda decisão exibida vem do TerminalAutenticacao (app.terminal); esta tela só a apresenta.
Item {
    id: pagina
    readonly property var t: app.terminal
    readonly property var cam: app.cameraServico
    readonly property string estado: t.estado
    readonly property var poseLimites: t.limitesPose()
    readonly property bool emResultado: estado === "RESULTADO" && t.resultadoTipo !== ""
    readonly property bool bloqueado: estado === "BLOQUEADO"
    readonly property bool concedido: emResultado && t.resultadoConcedido === true
    readonly property color corEstado: {
        if (bloqueado) return Theme.perigo
        if (emResultado) return concedido ? Theme.sucesso : Theme.perigo
        if (estado === "CONFIRMANDO" || estado === "LIVENESS") return Theme.acento
        return Theme.bordaForte
    }

    // atalhos iguais aos da versão de linha de comando
    Shortcut { sequences: ["1"]; enabled: pagina.visible && !pagina.bloqueado; onActivated: t.definirNivel(1) }
    Shortcut { sequences: ["2"]; enabled: pagina.visible && !pagina.bloqueado; onActivated: t.definirNivel(2) }
    Shortcut { sequences: ["3"]; enabled: pagina.visible && !pagina.bloqueado; onActivated: t.definirNivel(3) }
    Shortcut { sequences: ["L"]; enabled: pagina.visible && !pagina.bloqueado; onActivated: t.definirLiveness(!t.liveness) }
    Shortcut { sequences: ["D"]; enabled: pagina.visible; onActivated: t.definirDidatico(!t.didatico) }
    Shortcut { sequences: ["R"]; enabled: pagina.visible; onActivated: t.recarregarGaleria() }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 18

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Terminal de acesso"
            descricao: "Nível " + t.nivel + " exigido: " + t.area
            Selo {
                texto: cam.estado === "ativa" ? Math.round(cam.fps) + " fps" : (cam.estado === "abrindo" ? "abrindo câmera" : (cam.estado === "erro" ? "câmera indisponível" : "câmera desligada"))
                cor: cam.estado === "ativa" ? Theme.sucesso : (cam.estado === "erro" ? Theme.perigo : Theme.texto2)
                icone: cam.estado === "erro" ? "cameraOff" : "camera"
            }
            Selo { texto: t.galeria + " amostras na galeria"; cor: Theme.texto2; icone: "banco" }
            BotaoIcone { icone: "recarregar"; dica: "Recarregar galeria (R)"; onClicked: t.recarregarGaleria() }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 18

            // -------------------------------------------------------- vídeo
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                Rectangle {
                    id: moldura
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 300
                    radius: Theme.raioGrande + 2
                    color: Theme.lateral
                    border.width: 2
                    border.color: pagina.corEstado
                    Behavior on border.color { ColorAnimation { duration: Theme.lento } }

                    // brilho breve quando a decisão chega
                    Rectangle {
                        id: brilho
                        anchors.fill: parent
                        anchors.margins: -5
                        radius: parent.radius + 5
                        color: "transparent"
                        border.width: 5
                        border.color: pagina.corEstado
                        opacity: 0
                        SequentialAnimation {
                            id: pulso
                            NumberAnimation { target: brilho; property: "opacity"; to: 0.35; duration: 140 }
                            NumberAnimation { target: brilho; property: "opacity"; to: 0; duration: 650; easing.type: Easing.OutCubic }
                        }
                    }
                    Connections { target: t; function onDecisaoTomada(c, r) { pulso.restart() } }

                    VisorVideo {
                        id: visor
                        anchors.fill: parent
                        anchors.margins: 2
                        fonte: t.fonteVideo
                        raio: Theme.raioGrande
                        corFundo: Theme.lateral
                        preencher: false
                        // linha de varredura enquanto a identidade é confirmada quadro a quadro
                        varredura: -1
                        NumberAnimation on varredura {
                            running: pagina.estado === "CONFIRMANDO"
                            from: 0; to: 1; duration: 1100; loops: Animation.Infinite
                            onRunningChanged: if (!running) visor.varredura = -1
                        }
                    }

                    // área exigida (canto superior esquerdo)
                    Rectangle {
                        visible: cam.estado === "ativa"
                        anchors { left: parent.left; top: parent.top; margins: 16 }
                        height: 30
                        width: linhaArea.implicitWidth + 22
                        radius: 15
                        color: Qt.rgba(0.06, 0.07, 0.08, 0.78)
                        border.color: Theme.borda
                        RowLayout {
                            id: linhaArea
                            anchors.centerIn: parent
                            spacing: 7
                            Icone { nome: "cadeado"; tamanho: 13; cor: Theme.corNivel(t.nivel); traco: 2 }
                            Text { text: "Nível " + t.nivel; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold }
                            Text { text: t.area; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                        }
                    }

                    // instrução de base (aguardando / confirmando)
                    Rectangle {
                        id: instrucao
                        readonly property bool mostrar: cam.estado === "ativa" && (pagina.estado === "AGUARDANDO" || pagina.estado === "CONFIRMANDO")
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 22 }
                        width: Math.min(parent.width - 48, 420)
                        height: colInstrucao.implicitHeight + 24
                        radius: Theme.raio
                        color: Qt.rgba(0.06, 0.07, 0.08, 0.84)
                        border.color: Theme.borda
                        opacity: mostrar ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity { NumberAnimation { duration: Theme.medio } }
                        ColumnLayout {
                            id: colInstrucao
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }
                            spacing: 8
                            RowLayout {
                                spacing: 8
                                Icone {
                                    nome: t.nRostos > 1 || t.orientacao !== "" ? "alerta" : pagina.estado === "CONFIRMANDO" ? "foco" : "rosto"
                                    tamanho: 16
                                    cor: t.nRostos > 1 || t.orientacao !== "" ? Theme.aviso : pagina.estado === "CONFIRMANDO" ? Theme.acento : Theme.texto2
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: t.nRostos > 1 ? "Mais de uma pessoa diante do terminal"
                                          : t.orientacao !== "" ? t.orientacao
                                          : pagina.estado === "CONFIRMANDO" ? "Confirmando identidade, mantenha o rosto parado"
                                          : "Posicione o rosto de frente para a câmera"
                                    color: t.nRostos > 1 || t.orientacao !== "" ? Theme.aviso : Theme.texto
                                    font.pixelSize: Theme.tCorpo
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                }
                            }
                            Medidor {
                                visible: pagina.estado === "CONFIRMANDO"
                                Layout.fillWidth: true
                                valor: t.progresso
                                cor: Theme.acento
                                altura: 4
                            }
                        }
                    }

                    // prova de vida
                    Rectangle {
                        id: cartaoLiveness
                        readonly property bool mostrar: pagina.estado === "LIVENESS"
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 22 }
                        width: Math.min(parent.width - 48, 460)
                        height: colLiveness.implicitHeight + 32
                        radius: Theme.raioGrande
                        color: Qt.rgba(0.06, 0.07, 0.08, 0.88)
                        border.color: Qt.rgba(0.208, 0.816, 0.753, 0.4)
                        opacity: mostrar ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity { NumberAnimation { duration: Theme.medio } }
                        ColumnLayout {
                            id: colLiveness
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 20 }
                            spacing: 12
                            RowLayout {
                                spacing: 8
                                Icone { nome: "pulso"; tamanho: 16; cor: Theme.acento }
                                Text { text: "Prova de vida"; color: Theme.acento; font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: Math.ceil(t.livenessRestante) + " s"
                                    color: t.livenessRestante <= 3 ? Theme.aviso : Theme.texto2
                                    font.pixelSize: Theme.tPequeno
                                    font.features: { "tnum": 1 }
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: ({ 0: "Vire o rosto para a esquerda", 1: "Agora vire para a direita", 2: "Olhe de novo para a câmera", 3: "Prova de vida concluída" })[t.livenessPasso]
                                color: Theme.texto
                                font.pixelSize: 22
                                font.weight: Font.DemiBold
                                wrapMode: Text.Wrap
                            }
                            RowLayout {
                                spacing: 6
                                Repeater {
                                    model: ["Esquerda", "Direita", "Centro"]
                                    delegate: RowLayout {
                                        required property string modelData
                                        required property int index
                                        spacing: 6
                                        Rectangle {
                                            width: 18; height: 18; radius: 9
                                            color: index < t.livenessPasso ? Theme.acento : "transparent"
                                            border.width: 1.5
                                            border.color: index <= t.livenessPasso ? Theme.acento : Theme.bordaForte
                                            Icone { anchors.centerIn: parent; visible: index < t.livenessPasso; nome: "ok"; tamanho: 11; traco: 3; cor: Theme.sobreCor }
                                        }
                                        Text { text: modelData; color: index === t.livenessPasso ? Theme.texto : Theme.texto3; font.pixelSize: Theme.tPequeno }
                                        Rectangle { visible: index < 2; width: 22; height: 1; color: Theme.bordaForte }
                                    }
                                }
                            }
                            Medidor {
                                Layout.fillWidth: true
                                valor: t.livenessTotal > 0 ? t.livenessRestante / t.livenessTotal : 0
                                cor: t.livenessRestante <= 3 ? Theme.aviso : Theme.acento
                                altura: 3
                            }
                        }
                    }

                    // veredito
                    Rectangle {
                        id: veredito
                        readonly property bool mostrar: pagina.emResultado
                        // o veredito some com um fade; o texto fica congelado durante a saída
                        property var congelado: ({ concedido: false, nome: "", nivel: 0, mensagem: "" })
                        readonly property bool vConcedido: mostrar ? pagina.concedido : congelado.concedido
                        readonly property string vNome: mostrar ? t.resultadoNome : congelado.nome
                        readonly property int vNivel: mostrar ? t.resultadoNivel : congelado.nivel
                        readonly property string vMensagem: mostrar ? t.resultadoMensagem : congelado.mensagem
                        onMostrarChanged: if (!mostrar) congelado = { concedido: pagina.concedido, nome: t.resultadoNome, nivel: t.resultadoNivel, mensagem: t.resultadoMensagem }
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: mostrar ? 22 : 8 }
                        width: Math.min(parent.width - 48, 520)
                        height: colVeredito.implicitHeight + 36
                        radius: Theme.raioGrande
                        color: Qt.rgba(0.07, 0.08, 0.10, 0.93)
                        border.width: 1
                        readonly property color corV: vConcedido ? Theme.sucesso : Theme.perigo
                        border.color: Qt.rgba(corV.r, corV.g, corV.b, 0.55)
                        opacity: mostrar ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity { NumberAnimation { duration: Theme.medio } }
                        Behavior on anchors.bottomMargin { NumberAnimation { duration: Theme.lento; easing.type: Easing.OutCubic } }
                        RowLayout {
                            id: colVeredito
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 20 }
                            spacing: 16
                            Rectangle {
                                Layout.alignment: Qt.AlignTop
                                width: 52; height: 52; radius: 16
                                color: veredito.vConcedido ? Theme.sucessoSuave : Theme.perigoSuave
                                Icone { anchors.centerIn: parent; nome: veredito.vConcedido ? "escudoOk" : "escudoX"; tamanho: 26; traco: 2; cor: veredito.corV }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 5
                                Text {
                                    text: veredito.vConcedido ? "Acesso autorizado" : "Acesso negado"
                                    color: veredito.corV
                                    font.pixelSize: 22
                                    font.weight: Font.Bold
                                }
                                RowLayout {
                                    spacing: 8
                                    visible: veredito.vNome !== ""
                                    Text { text: veredito.vNome; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.maximumWidth: 260 }
                                    Selo { visible: veredito.vNivel > 0; texto: "Nível " + veredito.vNivel; cor: Theme.corNivel(veredito.vNivel) }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: veredito.vMensagem
                                    color: Theme.texto2
                                    font.pixelSize: Theme.tCorpo
                                    wrapMode: Text.Wrap
                                    maximumLineCount: 3
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }

                    // bloqueio
                    Rectangle {
                        anchors.fill: visor
                        radius: Theme.raioGrande
                        color: Qt.rgba(0.05, 0.06, 0.07, 0.82)
                        opacity: pagina.bloqueado ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity { NumberAnimation { duration: Theme.lento } }
                        ColumnLayout {
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 60, 380)
                            spacing: 12
                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                width: 64; height: 64; radius: 20
                                color: Theme.perigoSuave
                                border.color: Qt.rgba(0.941, 0.416, 0.416, 0.35)
                                Icone { anchors.centerIn: parent; nome: "cadeado"; tamanho: 30; traco: 2; cor: Theme.perigo }
                            }
                            Text { Layout.alignment: Qt.AlignHCenter; text: "Terminal bloqueado"; color: Theme.texto; font.pixelSize: 22; font.weight: Font.Bold }
                            Text {
                                Layout.alignment: Qt.AlignHCenter
                                text: "Liberação em " + Math.ceil(t.bloqueadoRestante) + " s"
                                color: Theme.perigo
                                font.pixelSize: Theme.tDestaque
                                font.weight: Font.DemiBold
                                font.features: { "tnum": 1 }
                            }
                            Medidor {
                                Layout.fillWidth: true
                                valor: t.bloqueioTotal > 0 ? t.bloqueadoRestante / t.bloqueioTotal : 0
                                cor: Theme.perigo
                                altura: 4
                            }
                            Text {
                                Layout.fillWidth: true
                                horizontalAlignment: Text.AlignHCenter
                                text: "Várias tentativas negadas em sequência. Nenhuma autenticação é feita até o fim do bloqueio."
                                color: Theme.texto2
                                font.pixelSize: Theme.tPequeno
                                wrapMode: Text.Wrap
                            }
                        }
                    }

                    // câmera não disponível / carregando
                    ColumnLayout {
                        anchors.centerIn: parent
                        width: Math.min(parent.width - 80, 420)
                        visible: cam.estado !== "ativa"
                        spacing: 12
                        Carregando {
                            Layout.alignment: Qt.AlignHCenter
                            visible: cam.estado === "abrindo" || (!app.modelosProntos && app.erroModelos === "")
                            tamanho: 30
                        }
                        Rectangle {
                            Layout.alignment: Qt.AlignHCenter
                            visible: cam.estado === "erro" || app.erroModelos !== ""
                            width: 56; height: 56; radius: 18
                            color: Theme.perigoSuave
                            Icone { anchors.centerIn: parent; nome: "cameraOff"; tamanho: 26; cor: Theme.perigo }
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: app.erroModelos !== "" ? "Modelos não carregados"
                                  : !app.modelosProntos ? "Carregando os modelos de reconhecimento"
                                  : cam.estado === "abrindo" ? "Abrindo a câmera"
                                  : cam.estado === "erro" ? "Câmera indisponível" : "Câmera desligada"
                            color: Theme.texto
                            font.pixelSize: Theme.tDestaque
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: text !== ""
                            horizontalAlignment: Text.AlignHCenter
                            text: app.erroModelos !== "" ? app.erroModelos
                                  : cam.estado === "erro" ? cam.erro + "\n\nNo macOS, permita o acesso em Ajustes do Sistema › Privacidade e Segurança › Câmera."
                                  : ""
                            color: Theme.texto2
                            font.pixelSize: Theme.tPequeno
                            wrapMode: Text.Wrap
                        }
                        Botao {
                            Layout.alignment: Qt.AlignHCenter
                            visible: cam.estado === "erro" || cam.estado === "desligada" && app.modelosProntos
                            text: "Tentar novamente"
                            icone: "recarregar"
                            variante: "primario"
                            onClicked: t.tentarCamera()
                        }
                    }
                }

                // painel didático: as fases do pipeline em tempo real
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: t.didatico ? 168 : 0
                    visible: Layout.preferredHeight > 0
                    clip: true
                    radius: Theme.raioGrande
                    color: Theme.superficie
                    border.color: Theme.borda
                    Behavior on Layout.preferredHeight { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
                    ListView {
                        anchors.fill: parent
                        anchors.margins: 12
                        orientation: ListView.Horizontal
                        spacing: 10
                        model: t.etapas
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded; height: 6 }
                        delegate: ColumnLayout {
                            required property var modelData
                            width: 150
                            height: ListView.view.height - 8
                            spacing: 6
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: Theme.raioPequeno
                                color: Theme.lateral
                                border.color: Theme.borda
                                VisorVideo { anchors.fill: parent; anchors.margins: 1; fonte: modelData; raio: Theme.raioPequeno; corFundo: Theme.lateral; mostrarPontos: false }
                                Text { anchors.centerIn: parent; visible: !modelData.temImagem; text: "sem rosto"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                            }
                            Text { text: modelData.nome; color: Theme.texto2; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: parent.count === 0
                            text: "As imagens de cada fase aparecem aqui enquanto a câmera estiver ativa."
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                        }
                    }
                }
            }

            // -------------------------------------------------------- painel lateral
            ScrollView {
                id: rolagem
                Layout.preferredWidth: 360
                Layout.minimumWidth: 320
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: rolagem.availableWidth
                    spacing: 12

                    // área exigida
                    Painel {
                        Layout.fillWidth: true
                        titulo: "Área protegida"
                        subtitulo: "Nível mínimo exigido para liberar a porta"
                        Segmentado {
                            Layout.fillWidth: true
                            habilitado: !pagina.bloqueado
                            atual: t.nivel
                            opcoes: [
                                { valor: 1, texto: "Nível 1", dica: "Área comum do Ministério (atalho 1)" },
                                { valor: 2, texto: "Nível 2", dica: "Sala dos diretores de divisão (atalho 2)" },
                                { valor: 3, texto: "Nível 3", dica: "Cofre de toxinas, exclusivo do Ministro (atalho 3)" }
                            ]
                            onEscolhido: function(v) { t.definirNivel(v) }
                        }
                        RowLayout {
                            spacing: 8
                            Rectangle { width: 8; height: 8; radius: 4; color: Theme.corNivel(t.nivel) }
                            Text { text: t.area; color: Theme.texto2; font.pixelSize: Theme.tPequeno; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        }
                    }

                    // estado e leitura
                    Painel {
                        Layout.fillWidth: true
                        espacamento: 14
                        RowLayout {
                            spacing: 12
                            Rectangle {
                                width: 40; height: 40; radius: 12
                                color: Qt.rgba(pagina.corEstado.r, pagina.corEstado.g, pagina.corEstado.b, 0.14)
                                Behavior on color { ColorAnimation { duration: Theme.medio } }
                                Icone {
                                    anchors.centerIn: parent
                                    tamanho: 20
                                    traco: 2
                                    cor: pagina.estado === "AGUARDANDO" ? Theme.texto2 : pagina.corEstado
                                    nome: pagina.bloqueado ? "cadeado" : pagina.emResultado ? (pagina.concedido ? "escudoOk" : "escudoX")
                                          : pagina.estado === "LIVENESS" ? "pulso" : pagina.estado === "CONFIRMANDO" ? "foco" : "rosto"
                                }
                            }
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Text {
                                    text: pagina.bloqueado ? "Bloqueado" : pagina.emResultado ? (pagina.concedido ? "Autorizado" : "Negado")
                                          : pagina.estado === "LIVENESS" ? "Prova de vida" : pagina.estado === "CONFIRMANDO" ? "Confirmando" : "Aguardando"
                                    color: pagina.estado === "AGUARDANDO" ? Theme.texto : pagina.corEstado
                                    font.pixelSize: Theme.tDestaque
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: pagina.bloqueado ? "Aguarde " + Math.ceil(t.bloqueadoRestante) + " s para nova tentativa"
                                          : pagina.emResultado ? t.resultadoTitulo
                                          : pagina.estado === "LIVENESS" ? t.livenessInstrucao.charAt(0) + t.livenessInstrucao.slice(1).toLowerCase()
                                          : pagina.estado === "CONFIRMANDO" ? "Mesma identidade em " + Math.round(t.progresso * 100) + "% dos quadros"
                                          : (t.nRostos > 1 ? "Mais de uma pessoa no quadro" : t.orientacao !== "" ? "Pose fora do aceitável, sem tentativa" : "Nenhum rosto em análise")
                                    color: Theme.texto2
                                    font.pixelSize: Theme.tPequeno
                                    elide: Text.ElideRight
                                }
                            }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda }
                        ColumnLayout {
                            spacing: 8
                            RowLayout {
                                Text { text: "Similaridade"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true }
                                Text {
                                    text: t.similaridade < 0 ? "sem leitura" : t.similaridade.toFixed(3)
                                    // verde fica reservado para "autorizado": aqui só se indica se o rosto bate com alguém da galeria
                                    color: t.similaridade < 0 || pagina.estado === "BLOQUEADO" ? Theme.texto3 : (t.similaridade >= t.limiar ? Theme.acento : Theme.texto2)
                                    font.pixelSize: Theme.tCorpo
                                    font.weight: Font.DemiBold
                                    font.features: { "tnum": 1 }
                                }
                            }
                            Medidor {
                                Layout.fillWidth: true
                                valor: t.similaridade
                                limiar: t.limiar
                                cor: pagina.estado === "BLOQUEADO" ? Theme.texto3 : (t.similaridade >= t.limiar ? Theme.acento : Theme.texto2)
                            }
                            Text { text: "Limiar " + t.limiar.toFixed(3) + ". Acima dele o rosto é considerado da mesma pessoa."; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        }
                        GridLayout {
                            columns: 3
                            columnSpacing: 8
                            rowSpacing: 8
                            Layout.fillWidth: true
                            Metrica { rotulo: "Rostos"; valor: String(t.nRostos); cor: t.nRostos > 1 ? Theme.aviso : Theme.texto }
                            Metrica { rotulo: "FPS"; valor: cam.estado === "ativa" ? String(Math.round(cam.fps)) : "–" }
                            Metrica { rotulo: "Usuários ativos"; valor: String(t.usuariosAtivos) }
                        }
                    }

                    // geometria do rosto e assinatura biométrica (só exibição; a decisão é do backend)
                    Painel {
                        Layout.fillWidth: true
                        titulo: "Leitura do rosto"
                        subtitulo: "Pose pelos 5 pontos do detector e o vetor de 128 dimensões do SFace"
                        espacamento: 10
                        readonly property bool semRosto: t.poseYaw <= -90
                        readonly property bool poseRuim: t.orientacao !== ""
                        GridLayout {
                            columns: 3
                            columnSpacing: 8
                            rowSpacing: 8
                            Layout.fillWidth: true
                            Metrica {
                                rotulo: "Giro (yaw)"
                                valor: parent.parent.semRosto ? "–" : (t.poseYaw >= 0 ? "+" : "") + t.poseYaw.toFixed(2)
                                cor: parent.parent.poseRuim ? Theme.aviso : Theme.texto
                                Dica { visible: hoverYaw.hovered; text: "Nariz em relação ao meio dos olhos. 0 = de frente. Aceito até ±" + pagina.poseLimites.yaw }
                                HoverHandler { id: hoverYaw }
                            }
                            Metrica {
                                rotulo: "Inclinação"
                                valor: parent.parent.semRosto ? "–" : (t.poseRoll >= 0 ? "+" : "") + t.poseRoll.toFixed(0) + "°"
                                cor: parent.parent.poseRuim ? Theme.aviso : Theme.texto
                                Dica { visible: hoverRoll.hovered; text: "Ângulo da linha dos olhos. Aceito até ±" + pagina.poseLimites.roll + "°" }
                                HoverHandler { id: hoverRoll }
                            }
                            Metrica {
                                rotulo: "Nariz (pitch)"
                                valor: parent.parent.semRosto ? "–" : t.poseRazao.toFixed(2)
                                cor: parent.parent.poseRuim ? Theme.aviso : Theme.texto
                                Dica { visible: hoverPitch.hovered; text: "Posição do nariz entre os olhos (0) e a boca (1). Aceito entre " + pagina.poseLimites.razaoMin + " e " + pagina.poseLimites.razaoMax }
                                HoverHandler { id: hoverPitch }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: "Assinatura biométrica"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true }
                            Text {
                                text: t.assinatura.length > 0 ? t.assinatura.length + " dimensões" : "sem rosto"
                                color: Theme.texto3
                                font.pixelSize: Theme.tLegenda
                                font.features: { "tnum": 1 }
                            }
                        }
                        Canvas {
                            id: assinatura
                            Layout.fillWidth: true
                            implicitHeight: 64
                            readonly property var viva: t.assinatura
                            readonly property var ref: t.assinaturaReferencia
                            readonly property color corViva: pagina.bloqueado ? Theme.texto3 : (t.similaridade >= t.limiar ? Theme.acento : Theme.texto2)
                            onVivaChanged: requestPaint()
                            onCorVivaChanged: requestPaint()
                            onWidthChanged: requestPaint()
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.reset()
                                var n = viva.length, w = width, h = height, meio = h / 2
                                ctx.strokeStyle = String(Theme.borda)
                                ctx.lineWidth = 1
                                ctx.beginPath(); ctx.moveTo(0, meio); ctx.lineTo(w, meio); ctx.stroke()
                                if (n === 0) return
                                var passo = w / n, amp = meio - 3
                                // referência da galeria (amostra mais parecida), atrás, apagada
                                if (ref.length === n) {
                                    ctx.fillStyle = Qt.rgba(Theme.texto3.r, Theme.texto3.g, Theme.texto3.b, 0.45)
                                    for (var i = 0; i < n; ++i) {
                                        var rv = ref[i] * amp
                                        ctx.fillRect(i * passo, rv < 0 ? meio : meio - rv, Math.max(1, passo - 0.6), Math.abs(rv))
                                    }
                                }
                                ctx.fillStyle = String(corViva)
                                for (var j = 0; j < n; ++j) {
                                    var v = viva[j] * amp
                                    ctx.fillRect(j * passo + passo * 0.25, v < 0 ? meio : meio - v, Math.max(1, passo * 0.5), Math.abs(v))
                                }
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: t.assinatura.length === 0 ? "Cada rosto alinhado vira um vetor de 128 números; a similaridade é o cosseno entre dois vetores."
                                  : t.assinaturaReferencia.length > 0 ? "Barras claras: rosto ao vivo. Barras apagadas: amostra mais parecida da galeria."
                                  : "Galeria vazia: não há amostra para comparar."
                            color: Theme.texto3
                            font.pixelSize: Theme.tLegenda
                            wrapMode: Text.WordWrap
                        }
                    }

                    // aviso de galeria vazia (amarelo: é um aviso)
                    Rectangle {
                        Layout.fillWidth: true
                        visible: t.aviso !== "" || t.erro !== ""
                        implicitHeight: linhaAviso.implicitHeight + 24
                        radius: Theme.raio
                        color: t.erro !== "" ? Theme.perigoSuave : Theme.avisoSuave
                        border.color: Qt.rgba(1, 1, 1, 0.04)
                        RowLayout {
                            id: linhaAviso
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                            spacing: 10
                            Icone { Layout.alignment: Qt.AlignTop; nome: "alerta"; tamanho: 16; cor: t.erro !== "" ? Theme.perigo : Theme.aviso }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                Text { text: t.erro !== "" ? t.erro : t.aviso; color: Theme.texto; font.pixelSize: Theme.tPequeno; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                Botao {
                                    visible: t.erro === "" && t.usuariosAtivos === 0
                                    compacto: true
                                    text: "Cadastrar usuário"
                                    icone: "cadastro"
                                    onClicked: app.navegar("cadastro")
                                }
                            }
                        }
                    }

                    // controles
                    Painel {
                        Layout.fillWidth: true
                        espacamento: 14
                        Chave {
                            Layout.fillWidth: true
                            text: "Prova de vida"
                            descricao: "Pede que a pessoa vire o rosto antes de liberar (atalho L)"
                            checked: t.liveness
                            enabled: !pagina.bloqueado
                            onToggled: t.definirLiveness(checked)
                        }
                        Chave {
                            Layout.fillWidth: true
                            text: "Painel didático"
                            descricao: "Mostra cada fase do pipeline abaixo do vídeo (atalho D)"
                            checked: t.didatico
                            onToggled: t.definirDidatico(checked)
                        }
                    }

                    // últimos acessos
                    Painel {
                        Layout.fillWidth: true
                        titulo: "Últimos acessos"
                        espacamento: 4
                        cabecalhoDireita: Botao { text: "Ver auditoria"; variante: "fantasma"; compacto: true; onClicked: app.navegar("acessos") }
                        Text {
                            visible: t.ultimosAcessos.contagem === 0
                            text: "Nenhuma tentativa registrada ainda."
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                            Layout.topMargin: 4
                        }
                        Repeater {
                            model: t.ultimosAcessos
                            delegate: RowLayout {
                                required property string hora
                                required property string nome
                                required property string titulo
                                required property bool concedido
                                required property int nivelExigido
                                required property string similaridade
                                Layout.fillWidth: true
                                Layout.topMargin: 4
                                Layout.bottomMargin: 4
                                spacing: 10
                                Rectangle {
                                    width: 6; height: 6; radius: 3
                                    color: concedido ? Theme.sucesso : Theme.perigo
                                }
                                ColumnLayout {
                                    spacing: 1
                                    Layout.fillWidth: true
                                    Text { text: nome; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: titulo + ", nível " + nivelExigido; color: concedido ? Theme.sucesso : Theme.texto3; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                                }
                                Text { text: hora; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.features: { "tnum": 1 } }
                            }
                        }
                    }
                }
            }
        }
    }

    component Metrica: Rectangle {
        property string rotulo
        property string valor
        property color cor: Theme.texto
        Layout.fillWidth: true
        implicitHeight: 54
        radius: Theme.raioPequeno
        color: Theme.campo
        border.color: Theme.borda
        ColumnLayout {
            anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 10 }
            spacing: 1
            Text { text: parent.parent.valor; color: parent.parent.cor; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
            Text { text: parent.parent.rotulo; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
        }
    }
}
