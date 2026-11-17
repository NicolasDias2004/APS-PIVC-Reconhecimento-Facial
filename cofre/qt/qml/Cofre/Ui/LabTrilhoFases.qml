import QtQuick
import QtQuick.Layouts

// Trilho das cinco estações (fases de Gonzalez e Woods): número, nome, arquivo, tempo e barra
// proporcional. Clique ou ← → (com foco) escolhem a estação.
Rectangle {
    id: trilho
    property var tempos: []
    property int atual: 2
    property real orcamento: 0
    signal escolhida(int estacao)
    implicitHeight: 84
    implicitWidth: 900
    radius: Theme.raioGrande
    color: Theme.superficie
    border.color: activeFocus ? Theme.bordaForte : Theme.borda
    activeFocusOnTab: true
    Accessible.role: Accessible.PageTabList
    Accessible.name: "Estações do pipeline"
    Keys.onLeftPressed: if (atual > 1) trilho.escolhida(atual - 1)
    Keys.onRightPressed: if (atual < 5) trilho.escolhida(atual + 1)

    Rectangle {        // fio do topo
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 12; rightMargin: 12 }
        height: 1
        color: Theme.luzTopo
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 6

        Repeater {
            model: trilho.tempos || []
            delegate: Rectangle {
                id: est
                required property var modelData
                required property int index
                readonly property bool ativa: (modelData.fase || 0) === trilho.atual
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.raio
                color: ativa ? Theme.realce : (area.containsMouse ? Theme.hover : "transparent")
                border.width: ativa ? 1 : 0
                border.color: Theme.bordaForte
                Accessible.role: Accessible.PageTab
                Accessible.name: "Fase " + (modelData.fase || "") + ": " + (modelData.nome || "") + ", " + (modelData.texto || "")

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 8
                    Rectangle {
                        Layout.alignment: Qt.AlignTop
                        implicitWidth: 22; implicitHeight: 22; radius: 11
                        color: est.ativa ? Theme.acento : Theme.elevada
                        border.color: est.ativa ? Theme.acento : Theme.bordaForte
                        Text {
                            anchors.centerIn: parent
                            text: est.modelData.fase || ""
                            color: est.ativa ? Theme.sobreCor : Theme.texto2
                            font.pixelSize: Theme.tLegenda
                            font.weight: Font.DemiBold
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: est.modelData.nome || ""
                            color: est.ativa ? Theme.texto : Theme.texto2
                            font.pixelSize: Theme.tPequeno
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            text: est.modelData.arquivo || ""
                            color: Theme.texto3
                            font.pixelSize: Theme.tLegenda
                            elide: Text.ElideRight
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 3
                                radius: 1.5
                                color: Theme.trilho
                                Rectangle {
                                    width: parent.width * Math.max(0, Math.min(1, est.modelData.fracao || 0))
                                    height: parent.height
                                    radius: 1.5
                                    color: est.ativa ? Theme.acento : Theme.texto3
                                }
                            }
                            Text {
                                text: est.modelData.texto || "–"
                                color: Theme.texto2
                                font.pixelSize: Theme.tLegenda
                                font.features: { "tnum": 1 }
                            }
                        }
                    }
                }
                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { trilho.forceActiveFocus(); trilho.escolhida(est.modelData.fase || 1) }
                }
            }
        }

        ColumnLayout {
            Layout.preferredWidth: 150
            Layout.alignment: Qt.AlignVCenter
            spacing: 2
            Text { text: "Orçamento do quadro"; color: Theme.texto3; font.pixelSize: Theme.tLegenda }
            Text {
                text: trilho.orcamento > 0 ? trilho.orcamento.toFixed(1).replace(".", ",") + " ms" : "–"
                color: Theme.texto
                font.pixelSize: Theme.tDestaque
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
            }
        }
    }
}
