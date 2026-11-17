import QtQuick
import QtQuick.Layouts

// Cena de abertura da sessão. Só existe enquanto app.sessao.ativa (a sessão que o backend já abriu e gravou).
// Não atrasa nem condiciona nada: a área liberada já está aberta por baixo. Não recebe clique nem tecla.
Item {
    id: cena
    objectName: "cenaAbertura"
    anchors.fill: parent
    enabled: false
    readonly property var s: app.sessao
    property real fase: 1                                                  // 0..1; 1 = terminada
    visible: s.ativa && fase < 1
    readonly property real abrir: Math.max(0, (fase - 0.70) / 0.30)       // 0..1 nas folhas
    // Easing.InOutCubic aplicada à fase das folhas
    readonly property real folhas: abrir < 0.5 ? 4 * abrir * abrir * abrir : 1 - Math.pow(-2 * abrir + 2, 3) / 2

    NumberAnimation { id: anim; target: cena; property: "fase"; from: 0; to: 1; duration: Theme.cenaLonga }
    Connections { target: cena.s; function onAtivaChanged() { if (cena.s.ativa) anim.restart(); else { anim.stop(); cena.fase = 1 } } }
    Component.onCompleted: if (s.ativa) anim.restart()                   // o arquivo é carregado na primeira sessão

    Rectangle {
        width: Math.ceil(parent.width / 2); height: parent.height
        color: Theme.lateral
        x: -width * cena.folhas
        Rectangle { anchors { right: parent.right; top: parent.top; bottom: parent.bottom } width: 1; color: Theme.borda }
    }
    Rectangle {
        width: Math.ceil(parent.width / 2); height: parent.height
        color: Theme.lateral
        x: parent.width / 2 + width * cena.folhas
        Rectangle { anchors { left: parent.left; top: parent.top; bottom: parent.bottom } width: 1; color: Theme.borda }
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 18
        opacity: Math.max(0, 1 - cena.abrir * 1.6)
        Item {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 132; Layout.preferredHeight: 132
            Anel { anchors.fill: parent; espessura: 4; valor: Math.min(1, cena.fase / 0.32); cor: cena.s.ativa ? Theme.sucesso : Theme.texto2 }
            Icone {
                anchors.centerIn: parent
                nome: "ok"; tamanho: 54; traco: 2.4
                cor: cena.s.ativa ? Theme.sucesso : Theme.texto2
                opacity: Math.max(0, Math.min(1, (cena.fase - 0.22) / 0.12))
            }
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "Acesso autorizado"
            color: cena.s.ativa ? Theme.sucesso : Theme.texto2
            font.pixelSize: 13; font.weight: Font.DemiBold; font.letterSpacing: 1.6; font.capitalization: Font.AllUppercase
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: cena.s.nome
            color: Theme.texto
            font.pixelSize: Theme.tCena; font.weight: Font.DemiBold; font.letterSpacing: -0.6
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 8
            Rectangle { Layout.preferredWidth: 7; Layout.preferredHeight: 7; radius: 4; color: Theme.corNivel(cena.s.nivelUsuario) }
            Text { text: cena.s.nivelDescricao; color: Theme.texto2; font.pixelSize: 14 }
        }
    }
}
