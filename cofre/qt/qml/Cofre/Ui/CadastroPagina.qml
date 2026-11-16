import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import Cofre.Nativo

// Cadastro biométrico: formulário à direita, prévia da câmera e amostras à esquerda.
Item {
    id: pagina
    readonly property var c: app.cadastro
    readonly property var cam: app.cameraServico
    readonly property var lim: c.limites()
    readonly property bool ocupado: c.fase !== "formulario"
    property int nivelEscolhido: 1
    property string avisoMatricula: ""

    function iniciar() {
        if (c.iniciarCaptura(nome.texto, matricula.texto, cargo.texto, nivelEscolhido)) limparFormulario()
    }
    function limparFormulario() { nome.texto = ""; matricula.texto = ""; cargo.texto = ""; nivelEscolhido = 1; avisoMatricula = "" }

    FileDialog {
        id: dialogoFotos
        title: "Escolha as fotos do rosto"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Imagens (*.jpg *.jpeg *.png *.bmp *.webp)", "Todos os arquivos (*)"]
        onAccepted: {
            if (c.cadastrarPorFotos(nome.texto, matricula.texto, cargo.texto, pagina.nivelEscolhido, selectedFiles))
                pagina.limparFormulario()
        }
    }
    Confirmacao {
        id: confirmarCancelar
        titulo: "Cancelar o cadastro?"
        texto: "As " + c.capturadas + " amostras já capturadas de " + c.nome + " serão descartadas e o usuário não será criado."
        textoConfirmar: "Descartar cadastro"
        perigo: true
        onConfirmado: c.cancelar()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 18

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Cadastro biométrico"
            descricao: "Registre um rosto autorizado pela câmera ou a partir de fotos"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 18

            // ---------------------------------------------------- câmera e amostras
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                Rectangle {
                    id: moldura
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 280
                    radius: Theme.raioGrande + 2
                    color: Theme.lateral
                    border.width: c.fase === "capturando" ? 2 : 1
                    border.color: c.fase !== "capturando" ? Theme.borda
                                  : c.statusTipo === "ok" ? Theme.sucesso : c.statusTipo === "erro" ? Theme.perigo
                                  : c.statusTipo === "aviso" ? Theme.aviso : Theme.acento
                    Behavior on border.color { ColorAnimation { duration: Theme.medio } }

                    VisorVideo {
                        id: visor
                        anchors.fill: parent
                        anchors.margins: 2
                        fonte: c.fonteVideo
                        raio: Theme.raioGrande
                        corFundo: Theme.lateral
                    }
                    Rectangle {      // clarão a cada amostra capturada
                        id: clarao
                        anchors.fill: visor
                        radius: Theme.raioGrande
                        color: "white"
                        opacity: 0
                        NumberAnimation on opacity { id: animClarao; running: false; from: 0.28; to: 0; duration: 380; easing.type: Easing.OutCubic }
                    }
                    Connections { target: c; function onAmostraCapturada(n) { animClarao.restart() } }

                    // instrução de pose
                    Rectangle {
                        visible: c.fase === "capturando" && cam.estado === "ativa"
                        anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: 18 }
                        width: Math.min(parent.width - 40, 460)
                        height: colPose.implicitHeight + 26
                        radius: Theme.raio
                        color: Qt.rgba(0.06, 0.07, 0.08, 0.86)
                        border.color: Theme.borda
                        ColumnLayout {
                            id: colPose
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }
                            spacing: 8
                            RowLayout {
                                Text { text: "Pose " + (c.poseIndice + 1) + " de " + pagina.lim.poses.length; color: Theme.texto3; font.pixelSize: Theme.tLegenda; Layout.fillWidth: true }
                                Repeater {
                                    model: pagina.lim.poses.length
                                    delegate: Rectangle {
                                        required property int index
                                        width: index === c.poseIndice ? 18 : 6
                                        height: 6
                                        radius: 3
                                        color: index < c.poseIndice ? Theme.acento : index === c.poseIndice ? Theme.texto : Theme.bordaForte
                                        Behavior on width { NumberAnimation { duration: Theme.medio } }
                                    }
                                }
                            }
                            Text { text: c.pose; color: Theme.texto; font.pixelSize: 18; font.weight: Font.DemiBold; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        }
                    }

                    // estado da captura
                    Rectangle {
                        visible: c.fase === "capturando" && cam.estado === "ativa" && c.status !== ""
                        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 18 }
                        height: 34
                        width: linhaStatus.implicitWidth + 28
                        radius: 17
                        color: Qt.rgba(0.06, 0.07, 0.08, 0.86)
                        border.color: Qt.rgba(corStatus.r, corStatus.g, corStatus.b, 0.5)
                        readonly property color corStatus: Theme.corResultado(c.statusTipo)
                        RowLayout {
                            id: linhaStatus
                            anchors.centerIn: parent
                            spacing: 8
                            Rectangle { width: 8; height: 8; radius: 4; color: parent.parent.corStatus }
                            Text { text: c.status; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium }
                        }
                    }

                    // vazio, carregando, erro ou pausa
                    ColumnLayout {
                        anchors.centerIn: parent
                        width: Math.min(parent.width - 80, 420)
                        visible: c.fase === "formulario" || c.fase === "importando" || c.fase === "preparando" || cam.estado !== "ativa"
                        spacing: 12
                        Carregando {
                            Layout.alignment: Qt.AlignHCenter
                            visible: c.fase === "importando" || c.fase === "preparando" || (c.fase === "capturando" && cam.estado === "abrindo")
                            tamanho: 30
                        }
                        Rectangle {
                            Layout.alignment: Qt.AlignHCenter
                            visible: c.fase === "formulario" || (c.fase === "capturando" && cam.estado === "erro")
                            width: 56; height: 56; radius: 18
                            color: cam.estado === "erro" && c.fase === "capturando" ? Theme.perigoSuave : Theme.elevada
                            border.color: Theme.borda
                            Icone {
                                anchors.centerIn: parent
                                nome: cam.estado === "erro" && c.fase === "capturando" ? "cameraOff" : "camera"
                                tamanho: 24
                                cor: cam.estado === "erro" && c.fase === "capturando" ? Theme.perigo : Theme.texto2
                            }
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: c.fase === "importando" ? "Processando as fotos"
                                  : c.fase === "preparando" ? c.status
                                  : c.fase === "formulario" ? "A câmera liga quando a captura começar"
                                  : c.pausada ? "Captura pausada"
                                  : cam.estado === "erro" ? "Câmera indisponível" : "Abrindo a câmera"
                            color: Theme.texto
                            font.pixelSize: Theme.tDestaque
                            font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            text: c.fase === "formulario" ? "Preencha os dados ao lado e clique em Iniciar captura. Serão gravadas " + c.total + " amostras, uma a cada " + pagina.lim.intervalo.toFixed(1).replace(".", ",") + " s, seguindo as instruções de pose."
                                  : c.fase === "importando" ? c.status
                                  : cam.estado === "erro" ? cam.erro : ""
                            visible: text !== ""
                            color: Theme.texto2
                            font.pixelSize: Theme.tPequeno
                            wrapMode: Text.Wrap
                        }
                        Botao {
                            Layout.alignment: Qt.AlignHCenter
                            visible: c.fase === "capturando" && (cam.estado === "erro" || cam.estado === "desligada")
                            text: "Tentar novamente"
                            icone: "recarregar"
                            variante: "primario"
                            onClicked: c.tentarCamera()
                        }
                    }
                }

                // amostras capturadas
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 104
                    radius: Theme.raioGrande
                    color: Theme.superficie
                    border.color: Theme.borda
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8
                        RowLayout {
                            Text { text: "Amostras"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium }
                            Text { text: c.capturadas + " de " + c.total; color: Theme.texto3; font.pixelSize: Theme.tPequeno; font.features: { "tnum": 1 } }
                            Item { Layout.fillWidth: true }
                        }
                        ListView {
                            id: faixa
                            // cabem todas as amostras sem rolagem; só encolhem até 34 px
                            readonly property real lado: Math.max(34, Math.min(52, (width - spacing * (c.total - 1)) / Math.max(1, c.total)))
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            orientation: ListView.Horizontal
                            spacing: 8
                            clip: true
                            model: c.total
                            boundsBehavior: Flickable.StopAtBounds
                            delegate: Rectangle {
                                required property int index
                                readonly property bool cheia: index < c.miniaturas
                                width: faixa.lado; height: faixa.lado
                                anchors.verticalCenter: parent ? parent.verticalCenter : undefined
                                radius: Theme.raioPequeno
                                color: Theme.campo
                                border.color: cheia ? Theme.bordaForte : Theme.borda
                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 1
                                    visible: parent.cheia
                                    source: parent.cheia ? "image://cofre/cadastro/" + index + "?r=" + c.revisao : ""
                                    sourceSize: Qt.size(104, 104)
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: false
                                }
                                Text { anchors.centerIn: parent; visible: !parent.cheia; text: index + 1; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                            }
                        }
                    }
                }
            }

            // ---------------------------------------------------- formulário / progresso
            ScrollView {
                id: rolagem
                Layout.preferredWidth: 380
                Layout.minimumWidth: 330
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: rolagem.availableWidth
                    spacing: 12

                    // sucesso
                    Painel {
                        Layout.fillWidth: true
                        visible: c.sucesso.nome !== undefined
                        border.color: Qt.rgba(0.239, 0.839, 0.549, 0.4)
                        RowLayout {
                            spacing: 12
                            Rectangle {
                                width: 40; height: 40; radius: 12
                                color: Theme.sucessoSuave
                                Icone { anchors.centerIn: parent; nome: "usuarioOk"; tamanho: 20; cor: Theme.sucesso }
                            }
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Text { text: "Cadastro concluído"; color: Theme.sucesso; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                                Text { text: (c.sucesso.amostras || 0) + " amostras gravadas"; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                            }
                        }
                        GridLayout {
                            columns: 2
                            columnSpacing: 14
                            rowSpacing: 6
                            Text { text: "Nome"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: c.sucesso.nome || ""; color: Theme.texto; font.pixelSize: Theme.tCorpo; elide: Text.ElideRight; Layout.fillWidth: true }
                            Text { text: "Matrícula"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Text { text: c.sucesso.matricula || ""; color: Theme.texto; font.pixelSize: Theme.tCorpo }
                            Text { text: "Nível"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Selo { texto: (c.sucesso.nivel || "") + " · " + (c.sucesso.nivelDescricao || ""); cor: Theme.corNivel(c.sucesso.nivel || 0) }
                        }
                        Repeater {
                            model: c.sucesso.avisos || []
                            delegate: RowLayout {
                                required property string modelData
                                Layout.fillWidth: true
                                spacing: 6
                                Icone { nome: "alerta"; tamanho: 13; cor: Theme.aviso }
                                Text { text: modelData; color: Theme.texto2; font.pixelSize: Theme.tLegenda; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            }
                        }
                        RowLayout {
                            spacing: 8
                            Botao { text: "Ir para o terminal"; icone: "terminal"; onClicked: { c.fecharSucesso(); app.navegar("terminal") } }
                            Botao { text: "Fechar"; variante: "fantasma"; onClicked: c.fecharSucesso() }
                        }
                    }

                    // progresso da captura
                    Painel {
                        Layout.fillWidth: true
                        visible: c.fase === "capturando" || c.fase === "preparando"
                        titulo: "Capturando " + c.nome
                        subtitulo: "Nível " + c.nivelCadastro + ". Siga as instruções sobre o vídeo."
                        ColumnLayout {
                            spacing: 6
                            RowLayout {
                                Text { text: "Progresso"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true }
                                Text { text: c.capturadas + " / " + c.total; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                            }
                            Medidor { Layout.fillWidth: true; valor: c.total > 0 ? c.capturadas / c.total : 0; cor: c.capturadas >= c.total ? Theme.sucesso : Theme.acento }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borda }
                        Text { text: "Qualidade da amostra"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium }
                        BarraQualidade {
                            Layout.fillWidth: true
                            rotulo: "Nitidez"
                            valor: c.nitidez
                            maximo: pagina.lim.minNitidez * 4
                            minimo: pagina.lim.minNitidez
                            limite: -1
                            ativo: c.nRostos === 1
                        }
                        BarraQualidade {
                            Layout.fillWidth: true
                            rotulo: "Brilho"
                            valor: c.brilho
                            maximo: 255
                            minimo: pagina.lim.minBrilho
                            limite: pagina.lim.maxBrilho
                            ativo: c.nRostos === 1
                        }
                        Text {
                            Layout.fillWidth: true
                            text: c.nRostos === 0 ? "Nenhum rosto no quadro." : c.nRostos > 1 ? "Mais de um rosto: só uma pessoa pode aparecer."
                                  : c.qualidadeOk ? "Amostra aprovada: o rosto está nítido e bem iluminado." : "Ajuste a posição ou a luz até as barras ficarem dentro da faixa."
                            color: c.nRostos > 1 ? Theme.aviso : (c.qualidadeOk ? Theme.sucesso : Theme.texto3)
                            font.pixelSize: Theme.tLegenda
                            wrapMode: Text.Wrap
                        }
                        RowLayout {
                            spacing: 8
                            Botao {
                                Layout.fillWidth: true
                                text: c.capturadas >= c.total ? "Concluir cadastro" : "Aguardando amostras"
                                icone: "ok"
                                variante: "primario"
                                enabled: c.fase === "capturando" && c.capturadas >= c.total
                                onClicked: c.concluir()
                            }
                            Botao {
                                text: "Cancelar"
                                onClicked: c.capturadas > 0 ? confirmarCancelar.open() : c.cancelar()
                            }
                        }
                        Text {
                            visible: c.pausada
                            text: "A câmera foi desligada ao sair da tela. A captura continua quando você voltar."
                            color: Theme.aviso
                            font.pixelSize: Theme.tLegenda
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                    }

                    // formulário
                    Painel {
                        Layout.fillWidth: true
                        titulo: "Dados do usuário"
                        subtitulo: "A matrícula identifica a pessoa e não pode se repetir"
                        visible: c.fase === "formulario" || c.fase === "importando"
                        enabled: !pagina.ocupado
                        opacity: enabled ? 1 : 0.5
                        espacamento: 14
                        Campo {
                            id: nome
                            Layout.fillWidth: true
                            rotulo: "Nome completo"
                            obrigatorio: true
                            placeholder: "Ex.: Ana Souza"
                            erro: c.erroCampo === "nome" ? c.erro : ""
                            entrada.onTextChanged: if (c.erroCampo === "nome") c.limparErro()
                            onConfirmado: matricula.entrada.forceActiveFocus()
                        }
                        Campo {
                            id: matricula
                            Layout.fillWidth: true
                            rotulo: "Matrícula"
                            obrigatorio: true
                            placeholder: "Ex.: M0042"
                            erro: c.erroCampo === "matricula" ? c.erro : pagina.avisoMatricula
                            entrada.onTextChanged: {
                                if (c.erroCampo === "matricula") c.limparErro()
                                var dono = c.matriculaEmUso(texto)
                                pagina.avisoMatricula = dono !== "" ? "Matrícula já cadastrada para " + dono + "." : ""
                            }
                            onConfirmado: cargo.entrada.forceActiveFocus()
                        }
                        Campo {
                            id: cargo
                            Layout.fillWidth: true
                            rotulo: "Cargo"
                            placeholder: "Opcional"
                            onConfirmado: pagina.iniciar()
                        }
                        ColumnLayout {
                            spacing: 6
                            Text { text: "Nível de acesso"; color: Theme.texto2; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium }
                            Repeater {
                                model: app.niveis()
                                delegate: Rectangle {
                                    id: opcaoNivel
                                    required property var modelData
                                    readonly property bool ativo: pagina.nivelEscolhido === modelData.nivel
                                    Layout.fillWidth: true
                                    implicitHeight: linhaNivel.implicitHeight + 18
                                    radius: Theme.raioPequeno + 1
                                    color: ativo ? Theme.realce : (areaNivel.containsMouse ? Theme.elevada : Theme.campo)
                                    border.color: ativo ? Theme.corNivel(modelData.nivel) : Theme.borda
                                    border.width: ativo ? 1.5 : 1
                                    Behavior on color { ColorAnimation { duration: Theme.rapido } }
                                    RowLayout {
                                        id: linhaNivel
                                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                                        spacing: 10
                                        Rectangle {
                                            width: 16; height: 16; radius: 8
                                            color: "transparent"
                                            border.width: 1.5
                                            border.color: opcaoNivel.ativo ? Theme.corNivel(opcaoNivel.modelData.nivel) : Theme.bordaForte
                                            Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: 4; visible: opcaoNivel.ativo; color: Theme.corNivel(opcaoNivel.modelData.nivel) }
                                        }
                                        ColumnLayout {
                                            spacing: 1
                                            Layout.fillWidth: true
                                            Text { text: "Nível " + opcaoNivel.modelData.nivel + ": " + opcaoNivel.modelData.descricao; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium }
                                            Text { text: "Libera até: " + opcaoNivel.modelData.area; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                        }
                                    }
                                    MouseArea { id: areaNivel; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pagina.nivelEscolhido = opcaoNivel.modelData.nivel }
                                }
                            }
                        }
                        Text {
                            visible: c.erro !== "" && c.erroCampo === ""
                            text: c.erro
                            color: Theme.perigo
                            font.pixelSize: Theme.tPequeno
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                        RowLayout {
                            spacing: 8
                            Botao {
                                Layout.fillWidth: true
                                text: "Iniciar captura"
                                icone: "camera"
                                variante: "primario"
                                enabled: pagina.avisoMatricula === ""
                                onClicked: pagina.iniciar()
                            }
                            Botao {
                                text: "Importar fotos"
                                icone: "imagem"
                                dica: "Cadastrar a partir de arquivos de imagem (scanner ou câmera externa)"
                                enabled: pagina.avisoMatricula === ""
                                carregando: c.fase === "importando"
                                onClicked: dialogoFotos.open()
                            }
                        }
                    }
                }
            }
        }
    }

    component BarraQualidade: ColumnLayout {
        id: bq
        property string rotulo
        property real valor
        property real maximo: 1
        property real minimo: 0
        property real limite: -1
        property bool ativo: true
        readonly property bool dentro: valor >= minimo && (limite < 0 || valor <= limite)
        spacing: 4
        RowLayout {
            Text { text: bq.rotulo; color: Theme.texto3; font.pixelSize: Theme.tLegenda; Layout.fillWidth: true }
            Text {
                text: bq.ativo ? Math.round(bq.valor) : "–"
                color: !bq.ativo ? Theme.texto3 : bq.dentro ? Theme.sucesso : Theme.aviso
                font.pixelSize: Theme.tPequeno
                font.features: { "tnum": 1 }
            }
        }
        Item {
            Layout.fillWidth: true
            implicitHeight: 10
            Rectangle {
                id: trilhoQ
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                height: 5; radius: 3; color: Theme.realce
                Rectangle {     // faixa aceita
                    x: parent.width * Math.min(1, bq.minimo / bq.maximo)
                    width: parent.width * Math.min(1, (bq.limite < 0 ? bq.maximo : bq.limite) / bq.maximo) - x
                    height: parent.height; radius: 3
                    color: Theme.sucessoSuave
                }
            }
            Rectangle {
                visible: bq.ativo
                width: 10; height: 10; radius: 5
                anchors.verticalCenter: parent.verticalCenter
                x: Math.max(0, Math.min(trilhoQ.width - width, trilhoQ.width * bq.valor / bq.maximo - 5))
                color: bq.dentro ? Theme.sucesso : Theme.aviso
                border.color: Theme.janela
                border.width: 2
                Behavior on x { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
            }
        }
    }
}
