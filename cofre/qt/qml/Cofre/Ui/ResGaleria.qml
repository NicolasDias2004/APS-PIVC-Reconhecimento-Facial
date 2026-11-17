import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Aba Galeria de Resultados: a fase 4 como geometria (cada pessoa vira um agrupamento) e a saúde do
// cadastro. Anônima por padrão; os alertas são só texto.
Item {
    id: aba
    objectName: "abaResGaleria"
    readonly property var vm: app.v2.resGaleria
    readonly property string estado: vm ? (vm.estado || "vazio") : "vazio"
    readonly property bool temDado: estado === "pronto" || estado === "poucos"
    readonly property var resumo: vm ? (vm.resumo || ({})) : ({})
    function ler(chave) { return resumo[chave] !== undefined ? String(resumo[chave]) : "–" }

    ScrollView {
        id: rolagem
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: rolagem.availableWidth
            spacing: Theme.espacoBloco

            Aviso {
                visible: aba.estado === "poucos"
                Layout.fillWidth: true
                tipo: "aviso"
                texto: "Só " + aba.ler("pessoas") + " pessoas na galeria: o mapa e a matriz servem de exemplo, não de retrato do cadastro."
            }

            Item {
                visible: !aba.temDado
                Layout.fillWidth: true
                Layout.preferredHeight: 320
                EstadoBloco {
                    anchors.fill: parent
                    estado: aba.estado
                    erro: aba.vm ? (aba.vm.erro || "") : ""
                    progresso: aba.vm ? aba.vm.progresso : -1
                    vazioIcone: "usuarios"
                    vazioTitulo: "Cadastre ao menos duas pessoas para comparar"
                    vazioTexto: "O mapa mostra como as amostras de cada pessoa se agrupam e quem está perto demais de outra."
                    vazioAcao: "Novo cadastro"
                    onAcionado: aba.vm.abrirCadastro()
                    onTentarNovamente: aba.vm.recarregar()
                    onCancelar: aba.vm.cancelar()
                }
            }

            // A. Números da galeria
            RowLayout {
                visible: aba.temDado
                Layout.fillWidth: true
                spacing: 10
                Metrica { Layout.fillWidth: true; rotulo: "Pessoas ativas"; valor: aba.ler("pessoas"); detalhe: aba.vm ? (aba.vm.notaInativos !== "" ? aba.ler("inativos") + " inativas fora" : "galeria do terminal") : "" }
                Metrica { Layout.fillWidth: true; rotulo: "Amostras"; valor: aba.ler("amostras"); detalhe: "vetores gravados no cadastro" }
                Metrica { Layout.fillWidth: true; rotulo: "Pessoas com achado"; valor: aba.ler("comAchado"); detalhe: "situação diferente de boa" }
                Metrica { Layout.fillWidth: true; rotulo: "Pares com risco de confusão"; valor: aba.ler("paresDeRisco"); detalhe: "a menos de 0,10 do limiar " + (aba.vm ? aba.vm.limiarTexto : "–") }
            }

            Text {
                visible: aba.temDado && aba.vm && aba.vm.notaInativos !== ""
                Layout.fillWidth: true
                text: aba.vm ? (aba.vm.notaInativos || "") : ""
                color: Theme.texto3
                font.pixelSize: Theme.tPequeno
                wrapMode: Text.Wrap
            }

            // B e C. Mapa de identidades e matriz
            RowLayout {
                visible: aba.temDado
                Layout.fillWidth: true
                spacing: Theme.espacoBloco
                CartaoGrafico {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 6
                    Layout.alignment: Qt.AlignTop
                    titulo: "Mapa de identidades"
                    subtitulo: "Projeção em duas dimensões das amostras gravadas (PCA) · cada marca é uma amostra"
                    tipo: "dispersao"
                    dados: aba.vm ? aba.vm.dispersao : ({})
                    altura: 360
                    nomeArquivo: "galeria-mapa"
                    estado: aba.estado
                    onExportar: app.v2.figuras.exportar(tipo, dados, nomeArquivo)
                }
                CartaoGrafico {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 4
                    Layout.alignment: Qt.AlignTop
                    titulo: "Similaridade entre pessoas"
                    subtitulo: "Diagonal = coesão da própria pessoa · fora = par mais parecido"
                    tipo: "calor"
                    dados: aba.vm ? aba.vm.matriz : ({})
                    altura: 360
                    nomeArquivo: "galeria-matriz"
                    estado: aba.estado
                    onExportar: app.v2.figuras.exportar(tipo, dados, nomeArquivo)
                }
            }

            // D. Saúde do cadastro
            ResGaleriaSaude {
                visible: aba.temDado
                Layout.fillWidth: true
                linhas: aba.vm ? (aba.vm.saudeLinhas || []) : []
                onAbrirUsuarios: aba.vm.abrirUsuarios()
            }

            Item { Layout.preferredHeight: 8 }
        }
    }
}
