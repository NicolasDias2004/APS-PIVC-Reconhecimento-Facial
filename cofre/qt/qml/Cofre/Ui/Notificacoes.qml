import QtQuick
import QtQuick.Layouts

// Pilha de notificações temporárias (canto inferior direito), alimentada por app.notificacao.
Item {
    id: n
    width: 380
    ListModel { id: fila }
    Connections {
        target: app
        function onNotificacao(tipo, texto) {
            fila.append({ tipo: tipo, texto: texto })
            if (fila.count > 4) fila.remove(0)
        }
    }
    Column {
        anchors { right: parent.right; bottom: parent.bottom }
        spacing: 8
        Repeater {
            model: fila
            delegate: Rectangle {
                id: t
                required property string tipo
                required property string texto
                required property int index
                width: n.width
                height: linha.implicitHeight + 22
                radius: Theme.raio
                color: Theme.elevada
                border.color: Theme.bordaForte
                opacity: 0
                Component.onCompleted: opacity = 1
                Behavior on opacity { NumberAnimation { duration: Theme.medio } }
                readonly property color cor: tipo === "ok" ? Theme.sucesso : tipo === "erro" ? Theme.perigo
                                            : tipo === "aviso" ? Theme.aviso : Theme.acento
                Rectangle { width: 3; radius: 2; color: t.cor; anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 8 } }
                RowLayout {
                    id: linha
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 20; rightMargin: 8 }
                    spacing: 10
                    Icone { nome: t.tipo === "ok" ? "ok" : t.tipo === "erro" ? "erro" : t.tipo === "aviso" ? "alerta" : "info"; cor: t.cor; tamanho: 16 }
                    Text { text: t.texto; color: Theme.texto; font.pixelSize: Theme.tCorpo; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    BotaoIcone { icone: "fechar"; dica: "Fechar"; tamanho: 24; onClicked: fila.remove(t.index) }
                }
                Timer { interval: t.tipo === "erro" ? 7000 : 4200; running: true; onTriggered: if (t.index >= 0 && t.index < fila.count) fila.remove(t.index) }
            }
        }
    }
}
