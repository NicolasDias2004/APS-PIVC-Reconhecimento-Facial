import QtQuick
import QtQuick.Layouts

// Ablação: o que cada fase segura (alinhamento com a cabeça inclinada; fase 2 com a cena escura).
Rectangle {
    id: abl
    property var linhas: []
    property string estado: "nao_pedida"      // nao_pedida | calculando | pronta | sem_fotos
    signal medir()
    implicitHeight: col.implicitHeight + 36
    implicitWidth: 600
    radius: Theme.raioGrande
    color: Theme.superficie
    border.color: Theme.borda

    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 12; rightMargin: 12 }
        height: 1
        color: Theme.luzTopo
    }

    ColumnLayout {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text { text: "O que cada fase segura"; color: Theme.texto; font.pixelSize: Theme.tDestaque; font.weight: Font.DemiBold }
                Text {
                    Layout.fillWidth: true
                    text: "Resultado de estudo: não muda o pipeline."
                    color: Theme.texto3
                    font.pixelSize: Theme.tPequeno
                    wrapMode: Text.Wrap
                }
            }
            Selo { texto: "Sintético"; cor: Theme.aviso }
            Botao {
                objectName: "botaoAblacao"
                compacto: true
                icone: "camadas"
                text: "Medir nas fotos de teste"
                carregando: abl.estado === "calculando"
                enabled: abl.estado !== "calculando"
                onClicked: abl.medir()
            }
        }

        Text {
            visible: abl.estado === "nao_pedida" || abl.estado === "sem_fotos"
            Layout.fillWidth: true
            text: abl.estado === "sem_fotos" ? "Não há fotos de teste nesta instalação."
                                             : "Gira a cabeça 20° e escurece a cena nas fotos de teste, com e sem a fase em estudo."
            color: Theme.texto2
            font.pixelSize: Theme.tCorpo
            wrapMode: Text.Wrap
        }

        Tabela {
            visible: abl.estado === "pronta"
            Layout.fillWidth: true
            colunas: [{ chave: "cenario", titulo: "Cenário", largura: 0, alinhamento: "esq" },
                      { chave: "variante", titulo: "Variante", largura: 160, alinhamento: "esq" },
                      { chave: "valor", titulo: "Resultado", largura: 170, alinhamento: "dir" },
                      { chave: "leitura", titulo: "Leitura", largura: 200, alinhamento: "esq" }]
            linhas: abl.linhas || []
            vazio: "Sem resultado"
        }
    }
}
