import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Configurações: parâmetros de cofre.config agrupados por seção, com validação, alterações
// pendentes, aplicar/descartar e o arquivo config_usuario.json. Cada campo diz quando passa a valer.
Item {
    id: pagina
    readonly property var c: app.configuracoes

    Confirmacao {
        id: confirmarPadroes
        titulo: "Restaurar os valores padrão?"
        texto: "O formulário volta aos valores com que o aplicativo abriu. Nada muda até você clicar em Aplicar."
        textoConfirmar: "Restaurar no formulário"
        icone: "desfazer"
        onConfirmado: c.restaurarPadroes()
    }
    Confirmacao {
        id: confirmarCarregar
        titulo: "Carregar o arquivo salvo?"
        texto: "Os valores de " + c.caminhoArquivo() + " substituem o formulário e são aplicados na hora."
        textoConfirmar: "Carregar e aplicar"
        icone: "arquivo"
        onConfirmado: c.carregar()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 16

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Configurações"
            descricao: "Parâmetros do reconhecimento, da prova de vida, do cadastro e da câmera"
            Botao { visible: c.pendentes > 0; text: "Descartar"; icone: "desfazer"; variante: "fantasma"; onClicked: c.descartar() }
            Botao {
                text: c.pendentes > 0 ? (c.pendentes === 1 ? "Aplicar 1 alteração" : "Aplicar " + c.pendentes + " alterações") : "Aplicar"
                icone: "ok"
                variante: "primario"
                enabled: c.pendentes > 0
                onClicked: c.aplicar()
            }
        }

        // mensagem de estado
        Rectangle {
            Layout.fillWidth: true
            visible: c.mensagem !== ""
            implicitHeight: msg.implicitHeight + 18
            radius: Theme.raio
            readonly property color tom: c.mensagemTipo === "ok" ? Theme.sucesso : c.mensagemTipo === "erro" ? Theme.perigo
                                       : c.mensagemTipo === "aviso" ? Theme.aviso : Theme.acento
            color: Qt.rgba(tom.r, tom.g, tom.b, 0.09)
            border.color: Qt.rgba(tom.r, tom.g, tom.b, 0.3)
            RowLayout {
                anchors { fill: parent; margins: 9; leftMargin: 12; rightMargin: 12 }
                spacing: 10
                Icone {
                    nome: c.mensagemTipo === "ok" ? "ok" : c.mensagemTipo === "erro" ? "erro" : c.mensagemTipo === "aviso" ? "alerta" : "info"
                    tamanho: 16
                    cor: parent.parent.tom
                }
                Text { id: msg; Layout.fillWidth: true; text: c.mensagem; color: Theme.texto; font.pixelSize: Theme.tPequeno; wrapMode: Text.WordWrap }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            // ------------------------------------------------- campos por seção
            ScrollView {
                id: rolagem
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: rolagem.availableWidth
                    spacing: 16

                    Repeater {
                        model: c.secoes()
                        delegate: Painel {
                            id: secao
                            required property var modelData
                            Layout.fillWidth: true
                            titulo: modelData
                            espacamento: 0
                            Repeater {
                                model: c.modeloCampos
                                delegate: CampoConfig {
                                    Layout.fillWidth: true
                                    visible: model.secao === secao.modelData
                                }
                            }
                        }
                    }
                    Item { implicitHeight: 4 }
                }
            }

            // ------------------------------------------------- arquivo e sistema
            ScrollView {
                Layout.preferredWidth: pagina.width < 1150 ? 270 : 320
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ColumnLayout {
                    width: parent.width
                    spacing: 16

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Arquivo de configuração"
                        subtitulo: c.arquivoExiste ? "Aplicado automaticamente ao abrir o aplicativo" : "Nenhum arquivo salvo ainda"
                        Text {
                            Layout.fillWidth: true
                            text: c.caminhoArquivo()
                            color: Theme.texto3
                            font.pixelSize: Theme.tLegenda
                            wrapMode: Text.WrapAnywhere
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Botao { Layout.fillWidth: true; text: "Salvar"; icone: "salvar"; dica: "Grava o formulário no arquivo"; onClicked: c.salvar() }
                            Botao { Layout.fillWidth: true; text: "Carregar"; icone: "arquivo"; enabled: c.arquivoExiste; dica: "Lê o arquivo e aplica"; onClicked: confirmarCarregar.open() }
                        }
                        Botao { Layout.fillWidth: true; text: "Restaurar padrões"; icone: "desfazer"; variante: "fantasma"; onClicked: confirmarPadroes.open() }
                    }

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Níveis de acesso"
                        subtitulo: "Quem tem nível N acessa as áreas de nível N ou menor"
                        espacamento: 10
                        Repeater {
                            model: c.niveis()
                            delegate: RowLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 10
                                Rectangle {
                                    width: 24; height: 24; radius: 7
                                    Layout.alignment: Qt.AlignTop
                                    color: Qt.rgba(Theme.corNivel(modelData.nivel).r, Theme.corNivel(modelData.nivel).g, Theme.corNivel(modelData.nivel).b, 0.15)
                                    Text { anchors.centerIn: parent; text: modelData.nivel; color: Theme.corNivel(modelData.nivel); font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text { text: modelData.descricao; color: Theme.texto; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; Layout.fillWidth: true; elide: Text.ElideRight }
                                    Text { text: modelData.area; color: Theme.texto3; font.pixelSize: Theme.tLegenda; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                                }
                            }
                        }
                    }

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Sistema"
                        espacamento: 8
                        Repeater {
                            model: c.informacoes()
                            delegate: ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 1
                                Text { text: modelData.nome; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                                Text { text: modelData.valor; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                            }
                        }
                    }
                }
            }
        }
    }

    // Uma linha de parâmetro: rótulo, selos, explicação, quando vale e o controle.
    component CampoConfig: Item {
        id: cc
        required property var model
        required property int index
        readonly property bool numero: model.tipo !== "bool"
        implicitHeight: visible ? corpo.implicitHeight + 28 : 0

        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 1
            color: Theme.borda
            opacity: 0.7
        }
        Rectangle {
            visible: cc.model.alterado
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom; topMargin: 14; bottomMargin: 14; leftMargin: -18 }
            width: 2
            radius: 1
            color: Theme.aviso
        }

        RowLayout {
            id: corpo
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: pagina.width < 1150 ? 14 : 24

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                RowLayout {
                    spacing: 8
                    Text { text: cc.model.rotulo; color: cc.model.editavel ? Theme.texto : Theme.texto2; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium }
                    Selo { visible: cc.model.seguranca; texto: "Segurança"; icone: "escudo"; cor: Theme.acento }
                    Selo { visible: cc.model.alterado; texto: "Pendente"; cor: Theme.aviso }
                    Selo { visible: !cc.model.alterado && cc.model.diferePadrao; texto: "Alterado"; cor: Theme.texto2 }
                }
                Text {
                    Layout.fillWidth: true
                    text: cc.model.explicacao
                    color: Theme.texto2
                    font.pixelSize: Theme.tPequeno
                    wrapMode: Text.WordWrap
                    lineHeight: 1.15
                }
                RowLayout {
                    spacing: 6
                    Layout.topMargin: 2
                    Icone { nome: cc.model.editavel ? "relogio" : "cadeado"; tamanho: 13; cor: cc.model.editavel ? Theme.texto3 : Theme.aviso }
                    Text {
                        Layout.fillWidth: true
                        text: cc.model.textoEfeito + (cc.model.alterado ? ". Em uso: " + cc.model.textoAplicado : "")
                        color: cc.model.editavel ? Theme.texto3 : Theme.aviso
                        font.pixelSize: Theme.tLegenda
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // controle
            Item {
                Layout.preferredWidth: pagina.width < 1150 ? 180 : 250
                Layout.alignment: Qt.AlignVCenter
                implicitHeight: cc.numero ? 36 : 22

                Switch {
                    id: chave
                    visible: !cc.numero
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    enabled: cc.model.editavel
                    checked: cc.model.valor === true
                    hoverEnabled: true
                    padding: 0
                    implicitWidth: 36
                    implicitHeight: 20
                    onToggled: c.definir(cc.model.chave, checked)
                    indicator: Rectangle {
                        implicitWidth: 36
                        implicitHeight: 20
                        radius: 10
                        color: chave.checked ? Theme.acento : Theme.realce
                        border.color: chave.checked ? Theme.acento : Theme.bordaForte
                        opacity: chave.enabled ? 1 : 0.45
                        Behavior on color { ColorAnimation { duration: Theme.medio } }
                        Rectangle {
                            x: chave.checked ? parent.width - width - 3 : 3
                            anchors.verticalCenter: parent.verticalCenter
                            width: 14; height: 14; radius: 7
                            color: chave.checked ? Theme.sobreCor : Theme.texto2
                            Behavior on x { NumberAnimation { duration: Theme.medio; easing.type: Easing.OutCubic } }
                        }
                    }
                    contentItem: Item {}
                    Dica { visible: chave.hovered && !chave.enabled; text: "Somente leitura nesta versão" }
                }

                RowLayout {
                    visible: cc.numero
                    anchors.fill: parent
                    spacing: 10
                    Slider {
                        id: deslizador
                        Layout.fillWidth: true
                        enabled: cc.model.editavel
                        from: cc.model.minimo
                        to: cc.model.maximo
                        stepSize: cc.model.passo
                        snapMode: Slider.SnapAlways
                        value: cc.numero ? Number(cc.model.valor) : 0
                        onMoved: c.definir(cc.model.chave, value)
                        background: Rectangle {
                            x: deslizador.leftPadding
                            y: deslizador.topPadding + deslizador.availableHeight / 2 - height / 2
                            width: deslizador.availableWidth
                            height: 4
                            radius: 2
                            color: Theme.realce
                            opacity: deslizador.enabled ? 1 : 0.5
                            Rectangle { width: deslizador.visualPosition * parent.width; height: parent.height; radius: 2; color: cc.model.alterado ? Theme.aviso : Theme.acento }
                        }
                        handle: Rectangle {
                            x: deslizador.leftPadding + deslizador.visualPosition * (deslizador.availableWidth - width)
                            y: deslizador.topPadding + deslizador.availableHeight / 2 - height / 2
                            width: 14; height: 14; radius: 7
                            color: deslizador.enabled ? Theme.texto : Theme.texto3
                            border.color: deslizador.pressed ? Theme.acento : "transparent"
                            border.width: 2
                        }
                    }
                    TextField {
                        id: entrada
                        Layout.preferredWidth: 72
                        implicitHeight: 32
                        enabled: cc.model.editavel
                        horizontalAlignment: Text.AlignRight
                        text: cc.model.texto
                        color: acceptableInput || !activeFocus ? Theme.texto : Theme.perigo
                        font.pixelSize: Theme.tCorpo
                        font.features: { "tnum": 1 }
                        selectByMouse: true
                        validator: RegularExpressionValidator { regularExpression: cc.model.tipo === "int" ? /-?\d{0,4}/ : /-?\d{0,4}([.,]\d{0,3})?/ }
                        onEditingFinished: if (text !== cc.model.texto) c.definir(cc.model.chave, text)
                        background: Rectangle {
                            radius: Theme.raioPequeno
                            color: Theme.campo
                            opacity: entrada.enabled ? 1 : 0.5
                            border.width: entrada.activeFocus ? 1.5 : 1
                            border.color: entrada.activeFocus ? Theme.acento : (cc.model.alterado ? Qt.rgba(Theme.aviso.r, Theme.aviso.g, Theme.aviso.b, 0.6) : Theme.borda)
                        }
                        Dica { visible: entrada.hovered; text: "Entre " + cc.model.minimo + " e " + cc.model.maximo + (cc.model.editavel ? "" : ". Somente leitura nesta versão") }
                    }
                }
            }
        }
    }
}
