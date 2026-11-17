import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
    id: janela
    width: 1360
    height: 860
    minimumWidth: 1080
    minimumHeight: 680
    visible: true
    color: Theme.janela
    title: "Cofre MMA · Autenticação biométrica"

    // Ao fechar, as páginas são descarregadas antes de o Python liberar os ViewModels.
    property bool encerrando: false
    Connections {
        target: app
        function onEncerrando() { janela.encerrando = true }
    }

    readonly property var paginas: [
        { id: "terminal", texto: "Terminal de acesso", icone: "terminal" },
        { id: "cadastro", texto: "Cadastro biométrico", icone: "cadastro" },
        { id: "usuarios", texto: "Usuários", icone: "usuarios" },
        { id: "acessos", texto: "Auditoria de acessos", icone: "acessos" },
        { id: "avaliacao", texto: "Avaliação e demo", icone: "avaliacao" },
        { id: "config", texto: "Configurações", icone: "config" },
        { id: "painel", texto: "Painel de segurança", icone: "painel", grupo: "Análise" },
        { id: "laboratorio", texto: "Laboratório PIVC", icone: "laboratorio" },
        { id: "resultados", texto: "Resultados", icone: "resultados" }
    ]
    function indicePagina(id) {
        for (var i = 0; i < paginas.length; ++i) if (paginas[i].id === id) return i
        return 0
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ------------------------------------------------------------ navegação lateral
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: 232
            color: Theme.lateral
            Rectangle { anchors { right: parent.right; top: parent.top; bottom: parent.bottom } width: 1; color: Theme.borda }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                anchors.topMargin: 20
                spacing: 2

                RowLayout {
                    Layout.leftMargin: 6
                    Layout.bottomMargin: 22
                    spacing: 10
                    Rectangle {
                        width: 32; height: 32; radius: 9
                        color: Theme.acentoSuave
                        border.color: Qt.rgba(0.208, 0.816, 0.753, 0.35)
                        Icone { anchors.centerIn: parent; nome: "escudo"; tamanho: 17; cor: Theme.acento; traco: 2 }
                    }
                    ColumnLayout {
                        spacing: 0
                        Text { text: "Cofre MMA"; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                        Text { text: "Autenticação facial"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
                    }
                }

                Repeater {
                    model: janela.paginas
                    delegate: ItemNavegacao {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        text: modelData.texto
                        icone: modelData.icone
                        atalho: "⌘" + (index + 1)
                        ativo: app.pagina === modelData.id
                        onClicked: app.navegar(modelData.id)
                        Layout.topMargin: modelData.grupo ? 30 : 0
                        Text { visible: !!modelData.grupo; text: modelData.grupo || ""; x: 8; y: -22
                               color: Theme.texto3; font.pixelSize: Theme.tLegenda; font.weight: Font.DemiBold }
                    }
                }
                Botao { Layout.fillWidth: true; Layout.topMargin: 14; variante: "fantasma"; compacto: true
                        icone: "porta"; text: "Modo porta"; dica: "Terminal em tela cheia (⌘⇧F)"
                        enabled: !app.sessao.ativa; onClicked: app.v2.entrarQuiosque() }

                Item { Layout.fillHeight: true }

                // estado do sistema
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: sistema.implicitHeight + 24
                    radius: Theme.raio
                    color: Theme.superficie
                    border.color: Theme.borda
                    ColumnLayout {
                        id: sistema
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                        spacing: 8
                        LinhaSistema {
                            rotulo: "Modelos"
                            valor: app.erroModelos !== "" ? "falha" : (app.modelosProntos ? "carregados" : "carregando")
                            cor: app.erroModelos !== "" ? Theme.perigo : (app.modelosProntos ? Theme.sucesso : Theme.aviso)
                        }
                        LinhaSistema {
                            rotulo: "Câmera"
                            valor: ({ "desligada": "desligada", "abrindo": "abrindo", "ativa": "ativa", "erro": "indisponível" })[app.cameraServico.estado]
                            cor: app.cameraServico.estado === "ativa" ? Theme.sucesso : (app.cameraServico.estado === "erro" ? Theme.perigo
                                 : (app.cameraServico.estado === "abrindo" ? Theme.aviso : Theme.texto3))
                        }
                        LinhaSistema { rotulo: "Banco"; valor: app.nomeBanco(); cor: Theme.texto3 }
                        SeloDemo { Layout.fillWidth: true; compacto: true }
                    }
                }
                Text {
                    Layout.topMargin: 10
                    Layout.leftMargin: 6
                    text: "Versão " + app.versao() + "  ·  APS PIVC"
                    color: Theme.texto3
                    font.pixelSize: Theme.tLegenda
                }
            }
        }

        // ------------------------------------------------------------ páginas
        StackLayout {
            id: pilha
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: janela.indicePagina(app.pagina)

            Pagina { fonte: "TerminalPagina.qml"; id_: "terminal" }
            Pagina { fonte: "CadastroPagina.qml"; id_: "cadastro" }
            Pagina { fonte: "UsuariosPagina.qml"; id_: "usuarios" }
            Pagina { fonte: "AcessosPagina.qml"; id_: "acessos" }
            Pagina { fonte: "AvaliacaoPagina.qml"; id_: "avaliacao" }
            Pagina { fonte: "ConfigPagina.qml"; id_: "config" }
            PaginaSegura { fonte: "PainelPagina.qml"; id_: "painel"; encerrando: janela.encerrando; erroVm: app.v2.erroDe("painel") }
            PaginaSegura { fonte: "LaboratorioPagina.qml"; id_: "laboratorio"; encerrando: janela.encerrando; erroVm: app.v2.erroDe("laboratorio") }
            PaginaSegura { fonte: "ResultadosPagina.qml"; id_: "resultados"; encerrando: janela.encerrando; erroVm: app.v2.erroDe("resultados") }
        }
    }

    component LinhaSistema: RowLayout {
        property string rotulo
        property string valor
        property color cor
        spacing: 8
        Rectangle { width: 6; height: 6; radius: 3; color: parent.cor }
        Text { text: parent.rotulo; color: Theme.texto2; font.pixelSize: Theme.tPequeno; Layout.fillWidth: true }
        Text { text: parent.valor; color: Theme.texto3; font.pixelSize: Theme.tPequeno; elide: Text.ElideMiddle; Layout.maximumWidth: 110 }
    }

    // Cada página só é criada na primeira visita (abre mais rápido).
    component Pagina: Loader {
        property string fonte
        property string id_
        active: false
        asynchronous: false
        source: active && !janela.encerrando ? fonte : ""
        readonly property bool atual: app.pagina === id_
        onAtualChanged: if (atual) active = true
        Component.onCompleted: if (atual) active = true
    }

    // área liberada depois de um acesso concedido: cobre a janela inteira até a sessão encerrar
    Loader {
        anchors.fill: parent
        z: 50
        active: !janela.encerrando
        sourceComponent: AreaLiberada {}
    }

    // ---- v2: guarda de teclas das sobreposições, modo porta e cena de abertura
    // Com uma sobreposição aberta (modo porta, paleta), cada tecla do terminal ganha um segundo Shortcut: a ativação
    // fica ambígua e o onActivated de TerminalPagina.qml não dispara, mesmo com o foco fora da sobreposição.
    Repeater {
        model: ["1", "2", "3", "L", "D", "R"]
        delegate: Item {
            required property string modelData
            Shortcut { sequences: [modelData]; enabled: app.v2.sobreposicaoAberta }
        }
    }
    property bool cenaPronta: false
    Connections { target: app.sessao; function onAtivaChanged() { if (app.sessao.ativa) janela.cenaPronta = true } }
    Carregador { anchors.fill: parent; z: 40; sobreposicao: true; encerrando: janela.encerrando
                 fonte: "Quiosque.qml"; ativo: app.v2.quiosqueUsado; erroVm: app.v2.erroDe("quiosque")
                 onFalhou: { app.notificar("erro", "O modo porta não pôde ser carregado."); app.v2.sairQuiosque() } }
    Carregador { anchors.fill: parent; z: 60; sobreposicao: true; encerrando: janela.encerrando
                 fonte: "CenaAbertura.qml"; ativo: janela.cenaPronta; erroVm: "" }
    Connections { target: app.v2; function onQuiosqueTelaCheiaChanged() { janela.visibility = app.v2.quiosqueTelaCheia ? Window.FullScreen : Window.Windowed } }
    Shortcut { sequence: "Ctrl+Shift+F"; context: Qt.ApplicationShortcut
               enabled: !app.sessao.ativa && !app.v2.sobreposicaoAberta; onActivated: app.v2.entrarQuiosque() }

    Notificacoes {
        anchors { right: parent.right; bottom: parent.bottom; margins: 20 }
        height: parent.height - 40
        z: 100
    }

    Repeater {
        model: janela.paginas
        delegate: Item {
            required property var modelData
            required property int index
            Shortcut {
                sequence: "Ctrl+" + (index + 1)
                context: Qt.ApplicationShortcut
                enabled: !app.sessao.ativa
                onActivated: app.navegar(modelData.id)
            }
        }
    }
}
