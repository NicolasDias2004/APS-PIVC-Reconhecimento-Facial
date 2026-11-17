import QtQuick
import QtQuick.Layouts
import Cofre.Nativo

// Cartão de gráfico: cabeçalho (título, subtítulo, selos, N e "Exportar figura"), o gráfico nativo e o
// rodapé com a legenda e a linha de leitura. O cartão só emite `exportar()`: quem grava é a página, que
// chama o `exportar(tipo, dados, nomeArquivo)` do ViewModel de figuras. Sem `legenda`, usa a que o
// próprio dado pede (duas séries ou mais).
Rectangle {
    id: cartao
    property string titulo: ""
    property string subtitulo: ""
    property string tipo: "xy"
    property var dados: ({})
    property int altura: 220
    property bool exportavel: true
    property string nomeArquivo: ""
    property var legenda
    property string estado: "pronto"
    property string erro: ""
    signal exportar()

    property var leitura: ({})            // o que valorEm ou valorIndice devolveu por último
    property int indice: -1               // ponto sob o teclado
    readonly property var dadosSeguros: dados !== undefined && dados !== null ? dados : ({})
    readonly property bool temDado: estado === "pronto" || estado === "poucos"
    readonly property var selos: dadosSeguros.selos || []
    readonly property string textoN: dadosSeguros.n !== undefined && dadosSeguros.n !== null ? String(dadosSeguros.n) : ""
    // o N fica à direita do título quando os dois cabem na mesma linha; senão desce para a linha dos selos
    readonly property bool nNoTitulo: medidaTitulo.advanceWidth + medidaN.advanceWidth + (exportavel ? 62 : 24) <= coluna.width
    function ler(resultado) { leitura = resultado && resultado.texto !== undefined ? resultado : ({}) }
    function andar(passo) {
        var total = grafico.totalIndices()
        if (!temDado || total === 0) return
        indice = indice < 0 ? (passo > 0 ? 0 : total - 1) : (indice + passo + total) % total
        ler(grafico.valorIndice(indice))
    }
    function soltar() { indice = -1; leitura = ({}) }

    implicitWidth: 420
    implicitHeight: coluna.implicitHeight + 36
    radius: Theme.raioGrande
    color: Theme.superficie
    border.color: Theme.borda
    activeFocusOnTab: true
    Accessible.role: Accessible.Chart
    Accessible.name: titulo
    Accessible.description: dadosSeguros.resumo || ""
    Keys.onLeftPressed: andar(-1)
    Keys.onRightPressed: andar(1)
    Keys.onReturnPressed: if (exportavel && temDado) exportar()
    Keys.onEnterPressed: if (exportavel && temDado) exportar()
    onActiveFocusChanged: if (!activeFocus) soltar()
    onDadosChanged: soltar()
    onTipoChanged: soltar()

    TextMetrics { id: medidaTitulo; text: cartao.titulo; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
    TextMetrics { id: medidaN; text: cartao.textoN; font.pixelSize: Theme.tLegenda }
    ColumnLayout {
        id: coluna
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Text {
                Layout.fillWidth: true
                text: cartao.titulo
                color: Theme.texto
                font.pixelSize: Theme.tDestaque
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Text {
                visible: cartao.textoN !== "" && cartao.nNoTitulo
                text: cartao.textoN
                color: Theme.texto2
                font.pixelSize: Theme.tLegenda
                font.features: { "tnum": 1 }
            }
            BotaoIcone {
                visible: cartao.exportavel
                enabled: cartao.temDado
                Layout.topMargin: -5
                Layout.bottomMargin: -5
                Layout.rightMargin: -6
                tamanho: 28
                icone: "baixar"
                dica: "Exportar figura"
                onClicked: cartao.exportar()
            }
        }
        Text {
            visible: cartao.subtitulo !== ""
            Layout.fillWidth: true
            Layout.topMargin: 2
            text: cartao.subtitulo
            color: Theme.texto3
            font.pixelSize: Theme.tPequeno
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        Flow {
            visible: cartao.selos.length > 0 || (cartao.textoN !== "" && !cartao.nNoTitulo)
            Layout.fillWidth: true
            Layout.topMargin: 8
            spacing: 8
            Text {
                visible: cartao.textoN !== "" && !cartao.nNoTitulo
                width: Math.min(implicitWidth, coluna.width)
                height: 22
                verticalAlignment: Text.AlignVCenter
                text: cartao.textoN
                color: Theme.texto2
                font.pixelSize: Theme.tLegenda
                font.features: { "tnum": 1 }
                elide: Text.ElideRight
            }
            Repeater {
                model: cartao.selos
                delegate: Selo { required property var modelData; texto: String(modelData); cor: Theme.aviso }
            }
        }
        Item {
            id: corpo
            Layout.fillWidth: true
            Layout.topMargin: 14
            implicitHeight: cartao.altura
            Grafico {
                id: grafico
                anchors.fill: parent
                visible: cartao.temDado
                tipo: cartao.tipo
                dados: cartao.dadosSeguros
                // realce da leitura: fio no xy, no histograma e na fita; anel na dispersão; contorno na célula e na barra
                Rectangle {
                    visible: cartao.leitura.forma === "fio"
                    x: Math.round(cartao.leitura.px || 0)
                    y: cartao.leitura.ry || 0
                    width: 1
                    height: cartao.leitura.ra || 0
                    color: Theme.texto
                    opacity: 0.38
                }
                Rectangle {
                    visible: cartao.leitura.forma === "fio" || cartao.leitura.forma === "anel"
                    x: (cartao.leitura.px || 0) - width / 2
                    y: (cartao.leitura.py || 0) - height / 2
                    width: cartao.leitura.forma === "anel" ? 14 : 8
                    height: width
                    radius: width / 2
                    color: "transparent"
                    border.width: 1.5
                    border.color: Theme.texto
                }
                Rectangle {
                    visible: cartao.leitura.forma === "caixa"
                    x: (cartao.leitura.rx || 0) - 1.5
                    y: (cartao.leitura.ry || 0) - 1.5
                    width: (cartao.leitura.rl || 0) + 3
                    height: (cartao.leitura.ra || 0) + 3
                    radius: 3
                    color: "transparent"
                    border.width: 1.5
                    border.color: Theme.texto
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                    onPositionChanged: function(mouse) { cartao.indice = -1; cartao.ler(grafico.valorEm(mouse.x, mouse.y)) }
                    onExited: cartao.soltar()
                }
            }
            EstadoBloco {
                anchors.fill: parent
                estado: cartao.estado
                erro: cartao.erro
                vazioIcone: "avaliacao"
                vazioTitulo: "Sem dados para mostrar"
                vazioTexto: cartao.dadosSeguros.vazio || ""
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 10
            Layout.minimumHeight: 16
            spacing: 14
            LegendaGrafico {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                visible: cartao.temDado
                itens: cartao.legenda !== undefined && cartao.legenda !== null ? cartao.legenda : grafico.legenda
            }
            Text {
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                Layout.maximumWidth: cartao.width * 0.62
                text: cartao.leitura.texto || ""
                color: Theme.texto
                font.pixelSize: Theme.tLegenda
                font.features: { "tnum": 1 }
                elide: Text.ElideRight
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }
        }
    }
    Rectangle {        // anel de foco do teclado
        anchors.fill: parent
        anchors.margins: -3
        radius: parent.radius + 3
        color: "transparent"
        border.width: 2
        border.color: Theme.acento
        opacity: cartao.activeFocus ? 0.7 : 0
    }
}
