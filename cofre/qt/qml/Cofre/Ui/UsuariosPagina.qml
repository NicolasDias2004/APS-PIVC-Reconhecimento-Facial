import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Administração de usuários: busca, filtros, nível, ativação, remoção e fotos.
Item {
    id: pagina
    readonly property var u: app.usuarios
    // cópia dos campos da linha escolhida: a referência ao item do modelo some quando a linha é removida
    property var selecionado: ({ id: 0, nome: "", matricula: "", nivel: 0, amostras: 0, ativo: false })
    function escolher(m) {
        selecionado = { id: m.id, nome: m.nome, matricula: m.matricula, nivel: m.nivel, amostras: m.amostras, ativo: m.ativo }
    }

    Confirmacao {
        id: confirmarRemocao
        titulo: "Remover " + (pagina.selecionado.nome || "") + "?"
        texto: "O cadastro (matrícula " + (pagina.selecionado.matricula || "") + ") e as " + (pagina.selecionado.amostras || 0)
               + " amostras biométricas serão apagados do banco. O histórico de acessos é mantido. Esta ação não pode ser desfeita."
        textoConfirmar: "Remover usuário"
        perigo: true
        onConfirmado: u.remover(pagina.selecionado.id)
    }
    Confirmacao {
        id: confirmarAtivo
        readonly property bool desativar: pagina.selecionado.ativo === true
        titulo: (desativar ? "Desativar " : "Reativar ") + (pagina.selecionado.nome || "") + "?"
        texto: desativar ? "A pessoa deixa de ser reconhecida pelo terminal até ser reativada. Os dados biométricos são mantidos."
                         : "A pessoa volta a ser reconhecida pelo terminal com o nível " + (pagina.selecionado.nivel || "") + "."
        textoConfirmar: desativar ? "Desativar" : "Reativar"
        icone: desativar ? "usuarioX" : "usuarioOk"
        onConfirmado: u.alternarAtivo(pagina.selecionado.id)
    }

    // escolha do nível
    Popup {
        id: escolhaNivel
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: 420
        padding: 20
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.55) }
        background: Rectangle { radius: Theme.raioGrande; color: Theme.elevada; border.color: Theme.bordaForte }
        contentItem: ColumnLayout {
            spacing: 10
            Text { text: "Nível de acesso"; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
            Text { text: (pagina.selecionado.nome || "") + " está no nível " + (pagina.selecionado.nivel || "") + "."; color: Theme.texto2; font.pixelSize: Theme.tCorpo }
            Repeater {
                model: app.niveis()
                delegate: Rectangle {
                    id: opc
                    required property var modelData
                    readonly property bool atual: pagina.selecionado.nivel === modelData.nivel
                    Layout.fillWidth: true
                    implicitHeight: lin.implicitHeight + 18
                    radius: Theme.raioPequeno + 1
                    color: area.containsMouse && !atual ? Theme.realce : Theme.campo
                    border.color: atual ? Theme.corNivel(modelData.nivel) : Theme.borda
                    RowLayout {
                        id: lin
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                        spacing: 10
                        Rectangle { width: 8; height: 8; radius: 4; color: Theme.corNivel(opc.modelData.nivel) }
                        ColumnLayout {
                            spacing: 1
                            Layout.fillWidth: true
                            Text { text: "Nível " + opc.modelData.nivel + ": " + opc.modelData.descricao; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium }
                            Text { text: opc.modelData.area; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                        }
                        Text { visible: opc.atual; text: "atual"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                    }
                    MouseArea {
                        id: area
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: !opc.atual
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { escolhaNivel.close(); u.alterarNivel(pagina.selecionado.id, opc.modelData.nivel) }
                    }
                }
            }
            Botao { Layout.alignment: Qt.AlignRight; text: "Cancelar"; onClicked: escolhaNivel.close() }
        }
    }

    // fotos de referência
    Popup {
        id: galeriaFotos
        property var fotos: []
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(pagina.width - 80, 760)
        height: Math.min(pagina.height - 80, 600)
        padding: 20
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.6) }
        background: Rectangle { radius: Theme.raioGrande; color: Theme.elevada; border.color: Theme.bordaForte }
        contentItem: ColumnLayout {
            spacing: 14
            RowLayout {
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Text { text: "Fotos de referência"; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                    Text { text: (pagina.selecionado.nome || "") + ", " + galeriaFotos.fotos.length + " foto(s)"; color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                }
                BotaoIcone { icone: "fechar"; dica: "Fechar"; onClicked: galeriaFotos.close() }
            }
            GridView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                cellWidth: 132
                cellHeight: 132
                model: galeriaFotos.fotos
                delegate: Item {
                    required property var modelData
                    width: 132; height: 132
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 6
                        radius: Theme.raio
                        color: Theme.campo
                        border.color: Theme.borda
                        clip: true
                        Image {
                            anchors.fill: parent
                            anchors.margins: 1
                            visible: modelData.existe
                            source: modelData.existe ? modelData.url : ""
                            sourceSize: Qt.size(240, 240)
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                        }
                        Text { anchors.centerIn: parent; visible: !modelData.existe; text: "arquivo ausente"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                    }
                }
                Vazio {
                    anchors.centerIn: parent
                    visible: galeriaFotos.fotos.length === 0
                    icone: "imagem"
                    titulo: "Sem fotos gravadas"
                    texto: "Este usuário não tem fotos de referência na pasta de dados."
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 18

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Usuários"
            descricao: "Pessoas cadastradas, níveis de acesso e situação no terminal"
            Botao { text: "Novo cadastro"; icone: "cadastro"; variante: "primario"; onClicked: app.navegar("cadastro") }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: false   // não herda o preenchimento dos indicadores
            spacing: 12
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Cadastrados"; valor: u.total; icone: "usuarios" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Ativos"; valor: u.ativos; detalhe: (u.total - u.ativos) + " inativo(s)"; icone: "usuarioOk" }
            Repeater {
                model: 3
                delegate: Indicador {
                    required property int index
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    rotulo: "Nível " + (index + 1)
                    valor: u.porNivel[index] !== undefined ? u.porNivel[index] : 0
                    cor: Theme.corNivel(index + 1)
                    icone: "escudo"
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.raioGrande
            color: Theme.superficie
            border.color: Theme.borda

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.margins: 14
                    spacing: 10
                    Busca {
                        id: busca
                        Layout.preferredWidth: 300
                        placeholderText: "Buscar por nome, matrícula ou cargo"
                        text: u.busca
                        onTextChanged: u.definirBusca(text)
                    }
                    Segmentado {
                        atual: u.filtroStatus
                        opcoes: [{ valor: "todos", texto: "Todos" }, { valor: "ativos", texto: "Ativos" }, { valor: "inativos", texto: "Inativos" }]
                        onEscolhido: function(v) { u.definirFiltroStatus(v) }
                    }
                    Seletor {
                        atual: u.filtroNivel
                        opcoes: [{ valor: 0, texto: "Todos os níveis" }, { valor: 1, texto: "Nível 1" }, { valor: 2, texto: "Nível 2" }, { valor: 3, texto: "Nível 3" }]
                        onEscolhido: function(v) { u.definirFiltroNivel(v) }
                    }
                    Item { Layout.fillWidth: true }
                    Text { text: lista.count + " de " + u.total; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                }

                // cabeçalho da tabela
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 34
                    color: Theme.campo
                    Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top } height: 1; color: Theme.borda }
                    Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 1; color: Theme.borda }
                    LinhaColunas {
                        anchors.fill: parent
                        Text { Layout.fillWidth: true; Layout.minimumWidth: 150; text: "Nome"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: colMatricula; text: "Matrícula"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: colNivel; text: "Nível"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { visible: !pagina.compacta; Layout.preferredWidth: colAmostras; text: "Amostras"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { Layout.preferredWidth: colSituacao; text: "Situação"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Text { visible: !pagina.compacta; Layout.preferredWidth: colData; text: "Cadastro"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
                        Item { Layout.preferredWidth: pagina.colAcoes }
                    }
                }

                ListView {
                    id: lista
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: u.modelo
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: Rectangle {
                        id: linha
                        required property var model
                        required property int index
                        width: lista.width
                        height: 58
                        color: areaLinha.containsMouse ? Qt.rgba(1, 1, 1, 0.025) : "transparent"
                        Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 14; rightMargin: 14 } height: 1; color: Theme.borda; opacity: 0.6 }
                        MouseArea { id: areaLinha; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
                        LinhaColunas {
                            anchors.fill: parent
                            opacity: linha.model.ativo ? 1 : 0.55
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 150
                                spacing: 10
                                Rectangle {
                                    width: 32; height: 32; radius: 16
                                    color: Qt.rgba(Theme.corNivel(linha.model.nivel).r, Theme.corNivel(linha.model.nivel).g, Theme.corNivel(linha.model.nivel).b, 0.16)
                                    Text { anchors.centerIn: parent; text: linha.model.iniciais; color: Theme.corNivel(linha.model.nivel); font.pixelSize: Theme.tPequeno; font.weight: Font.DemiBold }
                                }
                                ColumnLayout {
                                    spacing: 1
                                    Layout.fillWidth: true
                                    Text { text: linha.model.nome; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.weight: Font.Medium; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { text: linha.model.cargo !== "" ? linha.model.cargo : "Sem cargo informado"; color: Theme.texto3; font.pixelSize: Theme.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                                }
                            }
                            Text { Layout.preferredWidth: colMatricula; text: linha.model.matricula; color: Theme.texto2; font.pixelSize: Theme.tCorpo; elide: Text.ElideRight; font.features: { "tnum": 1 } }
                            Item {
                                Layout.preferredWidth: colNivel
                                implicitHeight: seloNivel.implicitHeight
                                Selo { id: seloNivel; texto: linha.model.nivel + " · " + linha.model.nivelDescricao; cor: Theme.corNivel(linha.model.nivel) }
                                Dica { visible: hover.hovered; text: "Libera até: " + linha.model.area }
                                HoverHandler { id: hover }
                            }
                            Text {
                                visible: !pagina.compacta
                                Layout.preferredWidth: colAmostras
                                text: linha.model.amostras
                                color: linha.model.amostras === 0 ? Theme.aviso : Theme.texto2
                                font.pixelSize: Theme.tCorpo
                                font.features: { "tnum": 1 }
                            }
                            Item {
                                Layout.preferredWidth: colSituacao
                                implicitHeight: 22
                                Selo {
                                    texto: linha.model.emCadastro ? "Em cadastro" : (linha.model.ativo ? "Ativo" : "Inativo")
                                    cor: linha.model.emCadastro ? Theme.aviso : (linha.model.ativo ? Theme.acento : Theme.texto3)
                                }
                            }
                            Text { visible: !pagina.compacta; Layout.preferredWidth: colData; text: linha.model.criadoEm; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            RowLayout {
                                Layout.preferredWidth: pagina.colAcoes
                                spacing: 2
                                Item { Layout.fillWidth: true }
                                opacity: areaLinha.containsMouse || hoverAcoes.hovered ? 1 : 0.55
                                HoverHandler { id: hoverAcoes }
                                BotaoIcone { icone: "imagem"; dica: "Ver fotos de referência"; onClicked: { pagina.escolher(linha.model); galeriaFotos.fotos = u.fotos(linha.model.id); galeriaFotos.open() } }
                                BotaoIcone { icone: "escudo"; dica: "Alterar nível de acesso"; onClicked: { pagina.escolher(linha.model); escolhaNivel.open() } }
                                BotaoIcone {
                                    visible: !linha.model.emCadastro
                                    icone: linha.model.ativo ? "usuarioX" : "usuarioOk"; dica: linha.model.ativo ? "Desativar" : "Reativar"
                                    onClicked: { pagina.escolher(linha.model); confirmarAtivo.open() }
                                }
                                BotaoIcone {
                                    visible: !linha.model.emCadastro
                                    icone: "lixeira"; dica: "Remover usuário"; cor: Theme.perigo
                                    onClicked: { pagina.escolher(linha.model); confirmarRemocao.open() }
                                }
                                BotaoIcone {
                                    visible: linha.model.emCadastro
                                    icone: "direita"; dica: "Voltar ao cadastro em andamento"; cor: Theme.aviso
                                    onClicked: app.navegar("cadastro")
                                }
                            }
                        }
                    }

                    Vazio {
                        anchors.centerIn: parent
                        visible: lista.count === 0 && u.carregado
                        icone: u.total === 0 ? "usuarios" : "busca"
                        titulo: u.total === 0 ? "Nenhum usuário cadastrado" : "Nenhum usuário encontrado"
                        texto: u.total === 0 ? "Cadastre a primeira pessoa autorizada para o terminal começar a reconhecer rostos."
                                             : "Nenhum cadastro corresponde à busca e aos filtros escolhidos."
                        acao: u.total === 0 ? "Cadastrar usuário" : "Limpar filtros"
                        iconeAcao: u.total === 0 ? "cadastro" : "fechar"
                        onAcionado: u.total === 0 ? app.navegar("cadastro") : u.limparFiltros()
                    }
                }
            }
        }
    }

    readonly property bool compacta: width < 980
    readonly property int colAcoes: 128
    readonly property int colMatricula: compacta ? 90 : 110
    readonly property int colNivel: compacta ? 180 : 210
    readonly property int colAmostras: 80
    readonly property int colSituacao: 90
    readonly property int colData: 100

    component LinhaColunas: RowLayout {
        anchors.leftMargin: 18
        anchors.rightMargin: 14
        spacing: 12
    }
}
