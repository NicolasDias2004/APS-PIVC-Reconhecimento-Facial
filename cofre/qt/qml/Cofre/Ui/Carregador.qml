import QtQuick

// Aba ou sobreposição nova: carrega o QML por URL em texto na primeira vez que `ativo` fica verdadeiro
// e não descarrega mais. Com o ViewModel indisponível ou o arquivo com erro, uma aba mostra o
// `ErroCarga` no lugar; uma sobreposição não desenha nada e só emite `falhou`.
Item {
    id: carregador
    property string fonte: ""
    property bool ativo: false
    property string erroVm: ""
    property bool encerrando: false
    property bool sobreposicao: false
    signal falhou(string detalhe)
    property bool carregado: false
    readonly property bool comErro: carregado && (erroVm !== "" || carga.status === Loader.Error)
    readonly property string detalhe: erroVm !== "" ? erroVm : "O arquivo " + fonte + " tem um erro."

    onAtivoChanged: if (ativo) carregado = true
    Component.onCompleted: if (ativo) carregado = true
    onComErroChanged: if (comErro) falhou(detalhe)

    Loader {
        id: carga
        anchors.fill: parent
        asynchronous: false
        source: carregador.carregado && !carregador.encerrando && carregador.erroVm === "" ? carregador.fonte : ""
    }

    ErroCarga {
        anchors.fill: parent
        visible: carregador.comErro && !carregador.sobreposicao
        detalhe: carregador.detalhe
    }
}
