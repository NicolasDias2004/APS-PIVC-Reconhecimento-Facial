import QtQuick

// Selo das telas de análise: lembra que o que está ali não participa da decisão de acesso.
Selo {
    texto: "Análise consultiva · não altera o acesso"
    icone: "info"
    cor: Theme.texto2
    Accessible.name: texto
}
