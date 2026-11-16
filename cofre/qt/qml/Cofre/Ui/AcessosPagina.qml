import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Auditoria: indicadores, filtros, tabela de tentativas, resumos e detalhe com evidência.
// Somente leitura: nada aqui altera o log de acessos.
Item {
    id: pagina
    readonly property var a: app.acessos
    readonly property bool filtrando: a.busca !== "" || a.filtroResultado !== "" || a.filtroNivel !== 0 || a.periodo !== "tudo"
    readonly property bool compacta: width < 1180

    function porcentagem(x) { return x < 0 ? "–" : (x * 100).toFixed(x === 1 ? 0 : 1).replace(".", ",") + "%" }

    // ------------------------------------------------------------- detalhe da tentativa
    Popup {
        id: detalhe
        property var d: ({})
        function abrir(ident) { d = a.detalhe(ident); open() }
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(pagina.width - 60, 760)
        padding: 22
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.6) }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.medio } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.rapido } }
        background: Rectangle { radius: Theme.raioGrande; color: Theme.elevada; border.color: Theme.bordaForte }
        contentItem: ColumnLayout {
            spacing: 16
            RowLayout {
                spacing: 12
                Rectangle {
                    width: 36; height: 36; radius: 10
                    color: Theme.suaveResultado(detalhe.d.resultado || "")
                    Icone { anchors.centerIn: parent; nome: detalhe.d.concedido ? "escudoOk" : "escudoX"; tamanho: 20; cor: Theme.corResultado(detalhe.d.resultado || "") }
                }
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Text { text: detalhe.d.titulo || ""; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                    Text { text: "Tentativa nº " + (detalhe.d.id || "") + ", " + (detalhe.d.data || "") + " às " + (detalhe.d.hora || ""); color: Theme.texto2; font.pixelSize: Theme.tPequeno }
                }
                BotaoIcone { icone: "fechar"; dica: "Fechar"; onClicked: detalhe.close() }
            }
            RowLayout {
                spacing: 18
                Layout.fillWidth: true
                Rectangle {
                    Layout.preferredWidth: 260
                    Layout.preferredHeight: 260
                    Layout.alignment: Qt.AlignTop
                    radius: Theme.raio
                    color: Theme.campo
                    border.color: Theme.borda
                    clip: true
                    Image {
                        anchors.fill: parent
                        anchors.margins: 1
                        visible: detalhe.d.evidenciaExiste === true
                        source: detalhe.d.evidenciaExiste ? detalhe.d.evidenciaUrl : ""
                        sourceSize: Qt.size(520, 520)
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                    }
                    ColumnLayout {
                        anchors.centerIn: parent
                        width: parent.width - 40
                        visible: detalhe.d.evidenciaExiste !== true
                        spacing: 6
                        Icone { Layout.alignment: Qt.AlignHCenter; nome: "imagem"; tamanho: 22; cor: Theme.texto3 }
                        Text {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: detalhe.d.evidencia ? "O arquivo de evidência não está mais na pasta." : "Esta tentativa não gerou imagem de evidência."
                            color: Theme.texto3
                            font.pixelSize: Theme.tPequeno
                        }
                    }
                }
                GridLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    columns: 2
                    columnSpacing: 16
                    rowSpacing: 10
                    component Rotulo: Text { color: Theme.texto3; font.pixelSize: Theme.tPequeno; Layout.alignment: Qt.AlignTop }
                    component Valor: Text { color: Theme.texto; font.pixelSize: Theme.tCorpo; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Rotulo { text: "Pessoa" }
                    Valor { text: detalhe.d.nome || "" }
                    Rotulo { text: "Nível da pessoa" }
                    Valor { text: detalhe.d.nivelUsuario ? detalhe.d.nivelUsuario + ": " + detalhe.d.nivelUsuarioDescricao : "Sem nível (não reconhecida)"; color: detalhe.d.nivelUsuario ? Theme.corNivel(detalhe.d.nivelUsuario) : Theme.texto2 }
                    Rotulo { text: "Área solicitada" }
                    Valor { text: "Nível " + (detalhe.d.nivelExigido || "") + ": " + (detalhe.d.area || "") }
                    Rotulo { text: "Similaridade" }
                    Valor { text: (detalhe.d.similaridade || "–") + "   (limiar " + (detalhe.d.limiar || "") + ")"; font.features: { "tnum": 1 } }
                    Rotulo { text: "Registro" }
                    Valor { text: detalhe.d.mensagem || "–"; color: Theme.texto2 }
                    Rotulo { text: "Evidência"; visible: (detalhe.d.evidencia || "") !== "" }
                    Valor { visible: (detalhe.d.evidencia || "") !== ""; text: detalhe.d.evidencia || ""; color: Theme.texto3; font.pixelSize: Theme.tLegenda; wrapMode: Text.WrapAnywhere }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Botao { text: "Pasta de evidências"; icone: "pasta"; onClicked: a.abrirPastaEvidencias() }
                Botao { text: "Fechar"; variante: "primario"; onClicked: detalhe.close() }
            }
        }
    }

    // ------------------------------------------------------------- página
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.margemPagina
        anchors.topMargin: 22
        spacing: 18

        Cabecalho {
            Layout.fillWidth: true
            titulo: "Auditoria de acessos"
            descricao: "Cada tentativa no terminal fica registrada com resultado, similaridade e evidência"
            Botao {
                visible: a.ultimoExportado !== ""
                text: "Abrir relatório"
                icone: "externo"
                variante: "fantasma"
                dica: a.ultimoExportado
                onClicked: a.abrirExportado()
            }
            Botao { text: "Exportar CSV"; icone: "baixar"; carregando: a.exportando; enabled: !a.exportando; onClicked: a.exportar("csv") }
            Botao { text: "Exportar HTML"; icone: "arquivo"; enabled: !a.exportando; onClicked: a.exportar("html") }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: false   // não herda o preenchimento dos indicadores
            spacing: 12
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Tentativas"; valor: a.total; icone: "pulso" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Autorizadas"; valor: a.concedidos; cor: Theme.sucesso; icone: "escudoOk" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Negadas ou bloqueadas"; valor: a.negados; cor: a.negados > 0 ? Theme.perigo : Theme.texto; icone: "escudoX" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Taxa de autorização"; valor: pagina.porcentagem(a.taxa); icone: "camadas" }
            Indicador { Layout.fillWidth: true; Layout.fillHeight: true; rotulo: "Usuários cadastrados"; valor: a.usuarios; detalhe: a.amostras + " amostras biométricas"; icone: "usuarios" }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            // ------------------------------------------------- tabela
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.raioGrande
                color: Theme.superficie
                border.color: Theme.borda

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    Item {
                        Layout.fillWidth: true
                        implicitHeight: filtros.implicitHeight + 28
                    Flow {
                        id: filtros
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                        spacing: 10
                        Busca {
                            width: 180
                            placeholderText: "Buscar pessoa"
                            text: a.busca
                            onTextChanged: if (text !== a.busca) a.definirBusca(text)
                        }
                        Seletor {
                            width: 172
                            atual: a.filtroResultado
                            opcoes: a.opcoesResultado().map(function(o) { return { valor: o.chave, texto: o.titulo } })
                            onEscolhido: function(v) { a.definirFiltroResultado(v) }
                        }
                        Seletor {
                            width: 136
                            atual: a.filtroNivel
                            opcoes: [{ valor: 0, texto: "Todas as áreas" }, { valor: 1, texto: "Área nível 1" }, { valor: 2, texto: "Área nível 2" }, { valor: 3, texto: "Área nível 3" }]
                            onEscolhido: function(v) { a.definirFiltroNivel(v) }
                        }
                        Segmentado {
                            atual: a.periodo
                            opcoes: [{ valor: "tudo", texto: "Tudo" }, { valor: "hoje", texto: "Hoje" }, { valor: "7d", texto: "7 dias" }, { valor: "30d", texto: "30 dias" }]
                            onEscolhido: function(v) { a.definirPeriodo(v) }
                        }
                        Botao { visible: pagina.filtrando; text: "Limpar filtros"; icone: "fechar"; variante: "fantasma"; compacto: true; onClicked: a.limparFiltros() }
                    }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 34
                        color: Theme.campo
                        Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top } height: 1; color: Theme.borda }
                        Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 1; color: Theme.borda }
                        Colunas {
                            anchors.fill: parent
                            Cab { Layout.preferredWidth: pagina.cData; text: "Data e hora" }
                            Cab { Layout.fillWidth: true; Layout.minimumWidth: 140; text: "Pessoa" }
                            Cab { Layout.preferredWidth: pagina.cResultado; text: "Resultado" }
                            Cab { Layout.preferredWidth: pagina.cArea; text: "Área" }
                            Cab { Layout.preferredWidth: pagina.cSim; text: "Similaridade"; horizontalAlignment: Text.AlignRight }
                            Item { Layout.preferredWidth: 28 }
                        }
                    }

                    ListView {
                        id: tabela
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: a.modelo
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        delegate: Rectangle {
                            id: linha
                            required property var model
                            width: tabela.width
                            height: 46
                            color: areaLinha.containsMouse ? Qt.rgba(1, 1, 1, 0.03) : "transparent"
                            Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 14; rightMargin: 14 } height: 1; color: Theme.borda; opacity: 0.55 }
                            MouseArea {
                                id: areaLinha
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: detalhe.abrir(linha.model.id)
                            }
                            Colunas {
                                anchors.fill: parent
                                ColumnLayout {
                                    Layout.preferredWidth: pagina.cData
                                    spacing: 0
                                    Text { text: linha.model.hora; color: Theme.texto; font.pixelSize: Theme.tCorpo; font.features: { "tnum": 1 } }
                                    Text { text: linha.model.data; color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.features: { "tnum": 1 } }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 140
                                    spacing: 8
                                    Rectangle { width: 6; height: 6; radius: 3; color: Theme.corNivel(linha.model.nivelUsuario); visible: linha.model.nivelUsuario > 0 }
                                    Text {
                                        Layout.fillWidth: true
                                        text: linha.model.nome
                                        color: linha.model.nivelUsuario > 0 ? Theme.texto : Theme.texto2
                                        font.pixelSize: Theme.tCorpo
                                        font.italic: linha.model.nivelUsuario === 0
                                        elide: Text.ElideRight
                                    }
                                }
                                Item {
                                    Layout.preferredWidth: pagina.cResultado
                                    implicitHeight: 22
                                    Selo { anchors.verticalCenter: parent.verticalCenter; texto: linha.model.titulo; cor: Theme.corResultado(linha.model.resultado) }
                                }
                                Text {
                                    Layout.preferredWidth: pagina.cArea
                                    text: "Nível " + linha.model.nivelExigido
                                    color: Theme.texto2
                                    font.pixelSize: Theme.tPequeno
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.preferredWidth: pagina.cSim
                                    horizontalAlignment: Text.AlignRight
                                    text: linha.model.similaridade
                                    color: Theme.texto2
                                    font.pixelSize: Theme.tCorpo
                                    font.features: { "tnum": 1 }
                                }
                                Item {
                                    Layout.preferredWidth: 28
                                    implicitHeight: 16
                                    Icone { anchors.centerIn: parent; visible: linha.model.temEvidencia; nome: "imagem"; tamanho: 15; cor: Theme.texto3 }
                                }
                            }
                        }

                        Vazio {
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 40, 380)
                            visible: tabela.count === 0
                            icone: pagina.filtrando ? "filtro" : "relogio"
                            titulo: pagina.filtrando ? "Nenhuma tentativa com esses filtros" : "Nenhuma tentativa registrada"
                            texto: pagina.filtrando ? "Amplie o período ou limpe a busca para ver mais registros."
                                                    : "As tentativas do terminal aparecem aqui assim que alguém se posicionar diante da câmera."
                            acao: pagina.filtrando ? "Limpar filtros" : "Abrir terminal"
                            iconeAcao: pagina.filtrando ? "fechar" : "terminal"
                            onAcionado: pagina.filtrando ? a.limparFiltros() : app.navegar("terminal")
                        }
                    }

                    // rodapé: quantidade e limite
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 40
                        color: "transparent"
                        Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top } height: 1; color: Theme.borda }
                        RowLayout {
                            anchors { fill: parent; leftMargin: 16; rightMargin: 12 }
                            Text {
                                text: a.listados + (a.listados >= a.limite ? " registros mais recentes" : " registro(s)") + (pagina.filtrando ? " com os filtros" : "")
                                color: Theme.texto3
                                font.pixelSize: Theme.tPequeno
                            }
                            Item { Layout.fillWidth: true }
                            Text { text: "Mostrar"; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                            Segmentado {
                                atual: a.limite
                                opcoes: [{ valor: 50, texto: "50" }, { valor: 200, texto: "200" }, { valor: 1000, texto: "1000" }]
                                onEscolhido: function(v) { a.definirLimite(v) }
                            }
                        }
                    }
                }
            }

            // ------------------------------------------------- resumos
            ScrollView {
                Layout.preferredWidth: pagina.compacta ? 270 : 310
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    width: parent.width
                    spacing: 16

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Motivos de negação"
                        subtitulo: "Todas as tentativas registradas"
                        Repeater {
                            model: a.negacoes
                            delegate: ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 5
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { text: modelData.titulo; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true; elide: Text.ElideRight }
                                    Text { text: modelData.n; color: modelData.n > 0 ? Theme.texto : Theme.texto3; font.pixelSize: Theme.tPequeno; font.weight: Font.Medium; font.features: { "tnum": 1 } }
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: 4
                                    radius: 2
                                    color: Theme.realce
                                    Rectangle {
                                        height: parent.height
                                        radius: 2
                                        width: a.negados > 0 ? parent.width * modelData.n / a.negados : 0
                                        color: Theme.corResultado(modelData.chave)
                                        Behavior on width { NumberAnimation { duration: Theme.medio } }
                                    }
                                }
                            }
                        }
                    }

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Últimos dias"
                        subtitulo: a.dias.length > 0 ? "Autorizadas em verde" : ""
                        Item {
                            Layout.fillWidth: true
                            implicitHeight: 96
                            visible: a.dias.length > 0
                            Row {
                                id: barras
                                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: 18 }
                                height: 74
                                spacing: 4
                                readonly property real largura: (width - spacing * Math.max(0, a.dias.length - 1)) / Math.max(1, a.dias.length)
                                Repeater {
                                    model: a.dias
                                    delegate: Item {
                                        required property var modelData
                                        width: Math.min(22, barras.largura)
                                        height: barras.height
                                        Rectangle {
                                            id: total
                                            anchors.bottom: parent.bottom
                                            width: parent.width
                                            height: Math.max(2, parent.height * modelData.fracao)
                                            radius: 3
                                            color: Theme.perigoSuave
                                            border.color: Qt.rgba(Theme.perigo.r, Theme.perigo.g, Theme.perigo.b, 0.35)
                                            Rectangle {
                                                anchors.bottom: parent.bottom
                                                width: parent.width
                                                height: modelData.total > 0 ? parent.height * modelData.concedidos / modelData.total : 0
                                                radius: 3
                                                color: Theme.sucesso
                                                opacity: 0.85
                                            }
                                        }
                                        Dica { visible: hoverBarra.hovered; text: modelData.dia + ": " + modelData.total + " tentativa(s), " + modelData.concedidos + " autorizada(s)" }
                                        HoverHandler { id: hoverBarra }
                                    }
                                }
                            }
                            Text { anchors { left: parent.left; bottom: parent.bottom } text: a.dias.length > 0 ? a.dias[0].dia : ""; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                            Text { anchors { right: parent.right; bottom: parent.bottom } text: a.dias.length > 0 ? a.dias[a.dias.length - 1].dia : ""; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                        }
                        Text { visible: a.dias.length === 0; text: "Sem tentativas registradas."; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                    }

                    Painel {
                        Layout.fillWidth: true
                        titulo: "Por pessoa"
                        subtitulo: a.modeloPessoas.contagem > 0 ? "Clique para filtrar a tabela" : ""
                        espacamento: 2
                        Repeater {
                            model: a.modeloPessoas
                            delegate: Rectangle {
                                id: pessoa
                                required property var model
                                readonly property bool desconhecido: model.nome === "DESCONHECIDO"
                                Layout.fillWidth: true
                                implicitHeight: 34
                                radius: Theme.raioPequeno
                                color: areaPessoa.containsMouse ? Theme.realce : "transparent"
                                MouseArea {
                                    id: areaPessoa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: a.filtrarPessoa(pessoa.model.nome)
                                }
                                RowLayout {
                                    anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                                    spacing: 8
                                    Text {
                                        Layout.fillWidth: true
                                        text: pessoa.desconhecido ? "Não identificados" : pessoa.model.nome
                                        color: pessoa.desconhecido ? Theme.texto2 : Theme.texto
                                        font.italic: pessoa.desconhecido
                                        font.pixelSize: Theme.tPequeno
                                        elide: Text.ElideRight
                                    }
                                    Text { text: pessoa.model.concedidos; color: Theme.sucesso; font.pixelSize: Theme.tPequeno; font.features: { "tnum": 1 } }
                                    Text { text: pessoa.model.negados; color: pessoa.model.negados > 0 ? Theme.perigo : Theme.texto3; font.pixelSize: Theme.tPequeno; font.features: { "tnum": 1 }; Layout.preferredWidth: 22; horizontalAlignment: Text.AlignRight }
                                }
                            }
                        }
                        Text { visible: a.modeloPessoas.contagem === 0; text: "Ninguém tentou acessar ainda."; color: Theme.texto3; font.pixelSize: Theme.tPequeno }
                    }
                }
            }
        }
    }

    readonly property int cData: 92
    readonly property int cResultado: 150
    readonly property int cArea: 74
    readonly property int cSim: 86

    component Colunas: RowLayout {
        anchors.leftMargin: 18
        anchors.rightMargin: 12
        spacing: 12
    }
    component Cab: Text { color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.Medium }
}
