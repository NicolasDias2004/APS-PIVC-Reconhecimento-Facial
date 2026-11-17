import QtQuick
import QtQuick.Layouts

// Ficha do protocolo da aba Separação: quantas pessoas, imagens e pares entraram na conta.
// `ficha` chega do ViewModel em texto pronto; sem ficha, os valores ficam em "–".
ColumnLayout {
    id: ficha
    property var dados: ({})
    readonly property var d: dados || ({})
    function ler(chave) { return d[chave] !== undefined && d[chave] !== null ? String(d[chave]) : "–" }
    spacing: 2
    implicitWidth: 260

    ParRotuloValor { Layout.fillWidth: true; rotulo: "Pessoas"; valor: ficha.ler("pessoas") }
    ParRotuloValor { Layout.fillWidth: true; rotulo: "Imagens"; valor: ficha.ler("imagens") }
    ParRotuloValor { Layout.fillWidth: true; rotulo: "Sem rosto"; valor: ficha.ler("semRosto") }
    ParRotuloValor { Layout.fillWidth: true; rotulo: "Pares genuínos"; valor: ficha.ler("paresGenuinos") }
    ParRotuloValor { Layout.fillWidth: true; rotulo: "Pares impostores"; valor: ficha.ler("paresImpostores") }
    ParRotuloValor { Layout.fillWidth: true; rotulo: "Amostras por pessoa"; valor: ficha.ler("amostrasPorPessoa") }
}
