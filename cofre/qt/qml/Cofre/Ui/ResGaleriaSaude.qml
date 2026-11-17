import QtQuick
import QtQuick.Layouts

// Saúde do cadastro de cada pessoa da galeria (aba Galeria de Resultados). A tabela é a do kit;
// abaixo dela, cada achado em selo com a recomendação inteira. Tudo consultivo.
Painel {
    id: saude
    property var linhas: []
    readonly property var lista: linhas || []
    signal abrirUsuarios()
    titulo: "Saúde do cadastro"
    subtitulo: "Alertas consultivos: esta tela não desativa, não remove e não bloqueia ninguém."
    cabecalhoDireita: Botao {
        text: "Abrir Usuários"
        icone: "usuarios"
        compacto: true
        onClicked: saude.abrirUsuarios()
    }

    Tabela {
        Layout.fillWidth: true
        colunas: [{ chave: "rotulo", titulo: "Pessoa", largura: 0, alinhamento: "esq" },
                  { chave: "nivel", titulo: "Nível", largura: 44, alinhamento: "dir" },
                  { chave: "amostras", titulo: "Amostras", largura: 66, alinhamento: "dir" },
                  { chave: "coesao", titulo: "Coesão", largura: 58, alinhamento: "dir" },
                  { chave: "maisFraca", titulo: "Amostra mais fraca", largura: 128, alinhamento: "dir" },
                  { chave: "vizinho", titulo: "Vizinho mais próximo", largura: 0, alinhamento: "esq" },
                  { chave: "folga", titulo: "Folga até o limiar", largura: 118, alinhamento: "dir" },
                  { chave: "situacaoTexto", titulo: "Situação", largura: 150, alinhamento: "esq" },
                  { chave: "recomendacao", titulo: "Recomendação", largura: 0, alinhamento: "esq" }]
        linhas: saude.lista
        vazio: "Nenhuma pessoa ativa na galeria."
    }

    Repeater {
        model: saude.lista
        delegate: RowLayout {
            required property var modelData
            Layout.fillWidth: true
            spacing: 10
            Selo {
                texto: modelData.situacaoTexto || ""
                cor: modelData.situacao === "boa" ? Theme.acento : Theme.aviso
                icone: modelData.situacao === "boa" ? "ok" : "alerta"
            }
            Text {
                Layout.fillWidth: true
                text: (modelData.rotulo || "") + " · " + (modelData.recomendacao || "")
                color: Theme.texto2
                font.pixelSize: Theme.tPequeno
                wrapMode: Text.Wrap
            }
        }
    }
}
