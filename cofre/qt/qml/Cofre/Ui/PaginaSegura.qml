import QtQuick

// Página nova da lateral: o QML dela só é carregado na primeira visita (como a `Pagina` do Main.qml),
// por URL em texto, e um ViewModel indisponível ou um arquivo com erro viram um `ErroCarga` no lugar.
// Toda vez que a página fica atual, o conteúdo entra em fade (só nas páginas novas).
Item {
    id: pagina
    property string fonte: ""
    property string id_: ""
    property bool encerrando: false
    property string erroVm: ""
    readonly property bool atual: app.pagina === id_
    property bool carregado: false
    readonly property bool comErro: carregado && (erroVm !== "" || carga.status === Loader.Error)

    onAtualChanged: if (atual) { carregado = true; entrada.restart() }
    Component.onCompleted: if (atual) carregado = true

    Loader {
        id: carga
        anchors.fill: parent
        asynchronous: false
        source: pagina.carregado && !pagina.encerrando && pagina.erroVm === "" ? pagina.fonte : ""
    }
    NumberAnimation { id: entrada; target: carga; property: "opacity"; from: 0; to: 1; duration: 160; easing.type: Easing.OutCubic }

    ErroCarga {
        anchors.fill: parent
        visible: pagina.comErro
        detalhe: pagina.erroVm !== "" ? pagina.erroVm : "O arquivo " + pagina.fonte + " tem um erro."
    }
}
