pragma Singleton
import QtQuick

// Tokens visuais do Cofre MMA. Grafite em camadas, acento turquesa;
// verde e vermelho são reservados às decisões de acesso e amarelo só a avisos.
QtObject {
    // superfícies (da mais funda para a mais elevada)
    readonly property color janela: "#0f1215"
    readonly property color lateral: "#0c0e11"
    readonly property color superficie: "#151a1f"
    readonly property color elevada: "#1b2026"
    readonly property color realce: "#232931"
    readonly property color campo: "#12161a"
    readonly property color borda: "#252b33"
    readonly property color bordaForte: "#333b45"

    // texto
    readonly property color texto: "#e7ebef"
    readonly property color texto2: "#9aa3ae"
    readonly property color texto3: "#68717d"

    // acento e estados
    readonly property color acento: "#35d0c0"
    readonly property color acentoForte: "#22b8a8"
    readonly property color acentoSuave: Qt.rgba(0.208, 0.816, 0.753, 0.12)
    readonly property color sucesso: "#3dd68c"
    readonly property color sucessoSuave: Qt.rgba(0.239, 0.839, 0.549, 0.13)
    readonly property color perigo: "#f06a6a"
    readonly property color perigoSuave: Qt.rgba(0.941, 0.416, 0.416, 0.13)
    readonly property color aviso: "#f2b544"
    readonly property color avisoSuave: Qt.rgba(0.949, 0.710, 0.267, 0.13)
    readonly property color sobreCor: "#0b0e11"     // texto sobre fundos coloridos

    // níveis de acesso (sem vermelho/verde/amarelo, que têm significado próprio)
    readonly property var coresNivel: ["#8b97a6", "#6ea8fe", "#b197fc"]
    function corNivel(n) { return n >= 1 && n <= 3 ? coresNivel[n - 1] : texto3 }

    function corResultado(tipo) {
        if (tipo === "CONCEDIDO" || tipo === "ok") return sucesso
        if (tipo === "aviso") return aviso
        if (tipo === "" || tipo === undefined || tipo === "info" || tipo === "neutro") return acento
        return perigo
    }
    function suaveResultado(tipo) {
        if (tipo === "CONCEDIDO" || tipo === "ok") return sucessoSuave
        if (tipo === "aviso") return avisoSuave
        if (tipo === "" || tipo === undefined || tipo === "info" || tipo === "neutro") return acentoSuave
        return perigoSuave
    }

    // tipografia (fonte do sistema: SF Pro no macOS)
    readonly property string familia: Qt.application.font.family
    readonly property int tLegenda: 11
    readonly property int tPequeno: 12
    readonly property int tCorpo: 13
    readonly property int tDestaque: 15
    readonly property int tTitulo: 20
    readonly property int tGrande: 28

    // geometria
    readonly property int raio: 10
    readonly property int raioPequeno: 7
    readonly property int raioGrande: 14
    readonly property int espaco: 16
    readonly property int margemPagina: 28

    // movimento
    readonly property int rapido: 120
    readonly property int medio: 200
    readonly property int lento: 320
}
