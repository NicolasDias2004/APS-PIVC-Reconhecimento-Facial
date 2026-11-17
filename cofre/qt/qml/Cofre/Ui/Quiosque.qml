import QtQuick
import QtQuick.Layouts
import Cofre.Nativo

// Modo porta: a tela que a pessoa na porta vê. Só reflete o TerminalVM e o SessaoVM; não decide nada.
// O verde vem só de app.sessao.ativa (a sessão que o backend abriu), nunca da decisão sozinha.
FocusScope {
    id: quiosque
    objectName: "quiosque"
    anchors.fill: parent
    readonly property var t: app.terminal
    readonly property var q: app.v2.quiosque
    readonly property bool aberto: q.ativo && app.pagina === "terminal"

    // os três estados de resultado: única fonte de cor e de texto do resultado
    readonly property bool emResultado: t.estado === "RESULTADO" && t.resultadoTipo !== ""
    readonly property bool concedido: emResultado && t.resultadoConcedido === true && app.sessao.ativa === true
    readonly property bool negado: emResultado && t.resultadoConcedido === false
    readonly property bool pendente: emResultado && !concedido && !negado      // decisão concedida, sessão não aberta
    readonly property bool bloqueado: t.estado === "BLOQUEADO"
    readonly property bool comErro: t.erro !== "" || app.cameraServico.estado === "erro"

    readonly property color corEstado: concedido ? Theme.sucesso : (negado || bloqueado ? Theme.perigo : (pendente ? Theme.texto2 : Theme.acento))
    readonly property string rotulo: bloqueado ? "Terminal bloqueado"
                                     : concedido ? "Acesso autorizado"
                                     : negado ? "Acesso negado"
                                     : pendente ? "Decisão registrada"
                                     : t.estado === "LIVENESS" ? "Prova de vida"
                                     : t.estado === "CONFIRMANDO" ? "Identificando" : "Pronto"
    readonly property string frase: bloqueado ? ("Aguarde " + Math.ceil(t.bloqueadoRestante) + " s")
                                    : (concedido || negado) ? t.resultadoTitulo
                                    : pendente ? "Aguarde"
                                    : t.estado === "LIVENESS" ? t.livenessInstrucao
                                    : t.orientacao !== "" ? t.orientacao
                                    : t.estado === "CONFIRMANDO" ? "Mantenha o rosto na câmera" : "Aproxime-se e olhe para a câmera"

    visible: opacity > 0
    opacity: aberto ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.lento; easing.type: Easing.OutCubic } }
    focus: aberto
    onVisibleChanged: if (visible) forceActiveFocus()
    Component.onCompleted: if (aberto) forceActiveFocus()             // o arquivo é carregado na primeira entrada

    // (1) engole os atalhos enquanto tem o foco: 1 2 3 L D R do terminal e Ctrl+N
    Keys.onShortcutOverride: function(e) { e.accepted = quiosque.aberto }
    // (2) prende o foco: Tab não sai, e o foco volta se algo o tirar com a sessão fechada
    Keys.onTabPressed: function(e) { e.accepted = true }
    Keys.onBacktabPressed: function(e) { e.accepted = true }
    onActiveFocusChanged: if (!activeFocus && aberto && !app.sessao.ativa) Qt.callLater(forceActiveFocus)
    Connections { target: app.sessao; function onAtivaChanged() { if (!app.sessao.ativa && quiosque.aberto) quiosque.forceActiveFocus() } }
    // (3) é o guarda de teclas do Main.qml, ligado por app.v2.sobreposicaoAberta enquanto q.ativo.

    // Esc segurado 600 ms sai; soltar antes cancela. F alterna a preferência de tela cheia.
    property real saida: 0
    NumberAnimation { id: segurar; target: quiosque; property: "saida"; from: 0; to: 1; duration: 600
                      onFinished: if (quiosque.saida >= 1) { quiosque.saida = 0; quiosque.q.sair() } }
    Keys.onPressed: function(e) {
        if (e.key === Qt.Key_Escape) {
            if (!e.isAutoRepeat && !segurar.running) segurar.restart()
        } else if (e.key === Qt.Key_F && !e.isAutoRepeat) {
            quiosque.q.definirTelaCheia(!quiosque.q.telaCheia)
        }
        e.accepted = true                                                  // no quiosque nenhuma tecla desce
    }
    Keys.onReleased: function(e) {
        if (e.key === Qt.Key_Escape && !e.isAutoRepeat) { segurar.stop(); quiosque.saida = 0 }
        e.accepted = true
    }

    MouseArea { anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.AllButtons }     // consome os cliques

    Rectangle { anchors.fill: parent; color: Theme.lateral }
    VisorVideo { anchors.fill: parent; fonte: quiosque.q.fonteVideo; preencher: true; corFundo: Theme.lateral; mostrarPontos: false; varredura: -1 }
    Rectangle { anchors.fill: parent; color: Theme.lateral; opacity: quiosque.bloqueado ? 0.45 : 0 }
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 200
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.rgba(0.047, 0.055, 0.067, 0.92) }
            GradientStop { position: 1; color: "transparent" }
        }
    }
    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 340
        gradient: Gradient {
            GradientStop { position: 0; color: "transparent" }
            GradientStop { position: 0.7; color: Qt.rgba(0.047, 0.055, 0.067, 0.90) }
            GradientStop { position: 1; color: Qt.rgba(0.047, 0.055, 0.067, 0.97) }
        }
    }

    // ---- anel sobre o rosto (escala do modo cobrir do VisorVideo)
    readonly property real qw: Math.max(1, q.quadroLargura)
    readonly property real qh: Math.max(1, q.quadroAltura)
    readonly property real escala: Math.max(width / qw, height / qh)
    readonly property var r: q.rosto
    Item {
        id: alvo
        visible: quiosque.q.temRosto
        width: Math.max(quiosque.r.w * quiosque.qw, quiosque.r.h * quiosque.qh) * quiosque.escala * 1.30
        height: width
        x: (quiosque.width - quiosque.qw * quiosque.escala) / 2 + (quiosque.r.x + quiosque.r.w / 2) * quiosque.qw * quiosque.escala - width / 2
        y: (quiosque.height - quiosque.qh * quiosque.escala) / 2 + (quiosque.r.y + quiosque.r.h / 2) * quiosque.qh * quiosque.escala - height / 2
        Behavior on x { SmoothedAnimation { duration: 160 } }
        Behavior on y { SmoothedAnimation { duration: 160 } }
        Behavior on width { SmoothedAnimation { duration: 220 } }

        Item {
            anchors.fill: parent
            transform: Translate { id: tremor; x: 0 }
            Anel {
                anchors.fill: parent
                visible: quiosque.t.estado !== "LIVENESS"
                espessura: 4
                cor: quiosque.emResultado ? (quiosque.concedido ? Theme.sucesso : (quiosque.negado ? Theme.perigo : Theme.texto2))
                                          : (quiosque.bloqueado ? Theme.perigo : Theme.acento)
                valor: quiosque.t.estado === "CONFIRMANDO" ? quiosque.t.progresso
                       : quiosque.emResultado ? 1
                       : (quiosque.bloqueado && quiosque.t.bloqueioTotal > 0 ? quiosque.t.bloqueadoRestante / quiosque.t.bloqueioTotal : 0)
                descricao: quiosque.rotulo
            }
            AnelPassos {
                anchors.fill: parent
                visible: quiosque.t.estado === "LIVENESS"
                feitos: quiosque.t.livenessPasso
                atual: quiosque.t.livenessPasso
                espessura: 4
            }
        }
    }
    SequentialAnimation {
        id: tremer
        NumberAnimation { target: tremor; property: "x"; to: 10; duration: 35 }
        NumberAnimation { target: tremor; property: "x"; to: -10; duration: 70 }
        NumberAnimation { target: tremor; property: "x"; to: 10; duration: 70 }
        NumberAnimation { target: tremor; property: "x"; to: -10; duration: 70 }
        NumberAnimation { target: tremor; property: "x"; to: 0; duration: 35 }
    }
    onNegadoChanged: if (negado && visible) tremer.restart()

    // ---- topo: marca e chips
    RowLayout {
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 28 }
        spacing: 12
        Rectangle {
            Layout.preferredWidth: 34; Layout.preferredHeight: 34
            radius: 10; color: Theme.acentoSuave; border.color: Qt.rgba(0.208, 0.816, 0.753, 0.35)
            Icone { anchors.centerIn: parent; nome: "escudo"; tamanho: 18; cor: Theme.acento; traco: 2 }
        }
        ColumnLayout {
            spacing: 0
            Text { text: "Cofre MMA"; color: Theme.texto; font.pixelSize: 15; font.weight: Font.DemiBold }
            Text { text: "Terminal de acesso"; color: Theme.texto2; font.pixelSize: 11 }
        }
        Item { Layout.fillWidth: true }
        Rectangle {
            visible: quiosque.t.liveness === false
            Layout.preferredHeight: 30; Layout.preferredWidth: avisoVida.implicitWidth + 24
            radius: 15; color: Theme.avisoSuave; border.color: Theme.aviso
            RowLayout {
                id: avisoVida
                anchors.centerIn: parent
                spacing: 8
                Icone { nome: "alerta"; tamanho: 14; cor: Theme.aviso; traco: 2 }
                Text { text: "Prova de vida desligada"; color: Theme.aviso; font.pixelSize: 12; font.weight: Font.DemiBold }
            }
        }
        Rectangle {
            Layout.preferredHeight: 30; Layout.preferredWidth: chip.implicitWidth + 24
            radius: 15; color: Theme.vidro; border.color: Theme.borda
            RowLayout {
                id: chip
                anchors.centerIn: parent
                spacing: 8
                Rectangle { Layout.preferredWidth: 7; Layout.preferredHeight: 7; radius: 4; color: Theme.corNivel(quiosque.t.nivel) }
                Text { text: "Nível " + quiosque.t.nivel + " · " + quiosque.t.area; color: Theme.texto; font.pixelSize: 12; font.weight: Font.DemiBold }
            }
        }
    }

    // ---- base: estado e frase do backend
    ColumnLayout {
        visible: !quiosque.comErro && app.modelosProntos
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 76 }
        width: Math.min(parent.width - 80, 900)
        spacing: 10
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: quiosque.rotulo
            color: quiosque.corEstado
            font.pixelSize: 13; font.weight: Font.DemiBold; font.letterSpacing: 1.6; font.capitalization: Font.AllUppercase
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: parent.width
            text: quiosque.frase
            color: Theme.texto
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            font.pixelSize: Theme.tCena; font.weight: Font.DemiBold; font.letterSpacing: -0.6
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            visible: quiosque.t.nRostos > 1 && !quiosque.emResultado
            text: quiosque.t.aviso !== "" ? quiosque.t.aviso : "Mais de uma pessoa na imagem"
            color: Theme.aviso
            font.pixelSize: 14; font.weight: Font.Medium
        }
    }

    // ---- erros e carregamento
    Rectangle {
        visible: quiosque.comErro
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 460); height: colErro.implicitHeight + 48
        radius: Theme.raioGrande; color: Theme.vidro; border.color: Theme.borda
        ColumnLayout {
            id: colErro
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 24 }
            spacing: 14
            Icone { Layout.alignment: Qt.AlignHCenter; nome: "cameraOff"; tamanho: 28; cor: Theme.texto2; traco: 1.8 }
            Text {
                Layout.fillWidth: true
                text: quiosque.t.erro !== "" ? quiosque.t.erro : app.cameraServico.erro
                color: Theme.texto; font.pixelSize: 14
                horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
            }
            Botao { Layout.alignment: Qt.AlignHCenter; text: "Tentar novamente"; icone: "recarregar"; onClicked: quiosque.t.tentarCamera() }
        }
    }
    ColumnLayout {
        visible: !app.modelosProntos && !quiosque.comErro
        anchors.centerIn: parent
        spacing: 12
        Carregando { Layout.alignment: Qt.AlignHCenter; tamanho: 26 }
        Text { Layout.alignment: Qt.AlignHCenter; text: "Carregando modelos"; color: Theme.texto2; font.pixelSize: 14 }
    }

    // ---- rodapé
    RowLayout {
        anchors { left: parent.left; bottom: parent.bottom; margins: 26 }
        spacing: 8
        Text { text: "Segure"; color: Theme.texto3; font.pixelSize: 11 }
        Tecla { texto: "esc" }
        Text { text: "para sair"; color: Theme.texto3; font.pixelSize: 11 }
        Anel { Layout.preferredWidth: 18; Layout.preferredHeight: 18; espessura: 2; valor: quiosque.saida; cor: Theme.acento; descricao: "Saindo do modo porta" }
    }
    RowLayout {
        anchors { right: parent.right; bottom: parent.bottom; margins: 26 }
        spacing: 8
        Tecla { texto: "F" }
        Text { text: "tela cheia"; color: Theme.texto3; font.pixelSize: 11 }
    }
}
