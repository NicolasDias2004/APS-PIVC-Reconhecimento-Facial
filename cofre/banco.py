"""
Camada de persistência (SQLite, biblioteca padrão do Python).

Tabelas:
  usuarios  : pessoas autorizadas (nome, matrícula, cargo, nível 1-3, ativo)
  amostras  : embeddings (BLOB float32[128]) + foto de referência de cada usuário
  acessos   : log de auditoria de toda tentativa de autenticação

Para usar MySQL (também permitido no enunciado) bastaria trocar o driver e os
placeholders `?` por `%s`; o restante do sistema não conhece o banco.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT    NOT NULL,
    matricula  TEXT    NOT NULL UNIQUE,
    cargo      TEXT    NOT NULL DEFAULT '',
    nivel      INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 3),
    ativo      INTEGER NOT NULL DEFAULT 1,
    criado_em  TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS amostras (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    embedding   BLOB    NOT NULL,
    caminho_foto TEXT,
    nitidez     REAL,
    brilho      REAL,
    criado_em   TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS acessos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora      TEXT    NOT NULL,
    usuario_id     INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    nome_detectado TEXT,
    nivel_usuario  INTEGER,
    nivel_exigido  INTEGER NOT NULL,
    area           TEXT    NOT NULL,
    similaridade   REAL,
    resultado      TEXT    NOT NULL,
    mensagem       TEXT,
    evidencia      TEXT
);
CREATE INDEX IF NOT EXISTS idx_amostras_usuario ON amostras(usuario_id);
CREATE INDEX IF NOT EXISTS idx_acessos_data ON acessos(data_hora);
"""


@dataclass
class Usuario:
    id: int
    nome: str
    matricula: str
    cargo: str
    nivel: int
    ativo: bool
    criado_em: str

    @property
    def nivel_descricao(self) -> str:
        return config.NIVEIS.get(self.nivel, "?")


@dataclass
class Acesso:
    id: int
    data_hora: str
    usuario_id: int | None
    nome_detectado: str | None
    nivel_usuario: int | None
    nivel_exigido: int
    area: str
    similaridade: float | None
    resultado: str
    mensagem: str | None
    evidencia: str | None


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Banco:
    def __init__(self, caminho: str | Path = config.DB_PATH):
        self.caminho = Path(caminho)
        if str(self.caminho) != ":memory:":
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(self.caminho))
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.executescript(SCHEMA)

    # ------------------------------------------------------------------ usuários
    def criar_usuario(self, nome: str, matricula: str, cargo: str, nivel: int) -> Usuario:
        if nivel not in config.NIVEIS:
            raise ValueError(f"Nível inválido: {nivel}")
        nome, matricula, cargo = nome.strip(), matricula.strip(), cargo.strip()
        if not nome or not matricula:
            raise ValueError("Nome e matrícula são obrigatórios.")
        cur = self._con.execute(
            "INSERT INTO usuarios (nome, matricula, cargo, nivel, ativo, criado_em) VALUES (?,?,?,?,1,?)",
            (nome, matricula, cargo, nivel, _agora()),
        )
        self._con.commit()
        return self.obter_usuario(cur.lastrowid)

    def obter_usuario(self, usuario_id: int) -> Usuario | None:
        row = self._con.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        return self._usuario(row) if row else None

    def obter_por_matricula(self, matricula: str) -> Usuario | None:
        row = self._con.execute("SELECT * FROM usuarios WHERE matricula = ?", (matricula.strip(),)).fetchone()
        return self._usuario(row) if row else None

    def listar_usuarios(self, apenas_ativos: bool = False) -> list[Usuario]:
        sql = "SELECT * FROM usuarios" + (" WHERE ativo = 1" if apenas_ativos else "") + " ORDER BY nivel DESC, nome"
        return [self._usuario(r) for r in self._con.execute(sql)]

    def alterar_nivel(self, usuario_id: int, nivel: int) -> None:
        if nivel not in config.NIVEIS:
            raise ValueError(f"Nível inválido: {nivel}")
        self._con.execute("UPDATE usuarios SET nivel = ? WHERE id = ?", (nivel, usuario_id))
        self._con.commit()

    def definir_ativo(self, usuario_id: int, ativo: bool) -> None:
        self._con.execute("UPDATE usuarios SET ativo = ? WHERE id = ?", (1 if ativo else 0, usuario_id))
        self._con.commit()

    def remover_usuario(self, usuario_id: int) -> None:
        self._con.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
        self._con.commit()

    # ------------------------------------------------------------------ amostras
    def adicionar_amostra(self, usuario_id: int, embedding: np.ndarray, caminho_foto: str | None = None,
                          nitidez: float | None = None, brilho: float | None = None) -> int:
        emb = np.asarray(embedding, dtype=np.float32).reshape(-1)
        cur = self._con.execute(
            "INSERT INTO amostras (usuario_id, embedding, caminho_foto, nitidez, brilho, criado_em) VALUES (?,?,?,?,?,?)",
            (usuario_id, emb.tobytes(), caminho_foto, nitidez, brilho, _agora()),
        )
        self._con.commit()
        return cur.lastrowid

    def versao_dados(self) -> int:
        """Muda sempre que OUTRA conexão grava no banco (outra janela do aplicativo, a linha de
        comando). Gravações desta mesma conexão não alteram o valor (`PRAGMA data_version`)."""
        return int(self._con.execute("PRAGMA data_version").fetchone()[0])

    def embeddings_do_usuario(self, usuario_id: int) -> list[np.ndarray]:
        rows = self._con.execute("SELECT embedding FROM amostras WHERE usuario_id = ?", (usuario_id,))
        return [np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]

    def contar_amostras(self, usuario_id: int) -> int:
        return self._con.execute("SELECT COUNT(*) FROM amostras WHERE usuario_id = ?", (usuario_id,)).fetchone()[0]

    def fotos_do_usuario(self, usuario_id: int) -> list[str]:
        rows = self._con.execute(
            "SELECT caminho_foto FROM amostras WHERE usuario_id = ? AND caminho_foto IS NOT NULL", (usuario_id,))
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ acessos
    def registrar_acesso(self, *, usuario_id: int | None, nome_detectado: str | None, nivel_usuario: int | None,
                         nivel_exigido: int, similaridade: float | None, resultado: str,
                         mensagem: str | None = None, evidencia: str | None = None) -> int:
        cur = self._con.execute(
            """INSERT INTO acessos (data_hora, usuario_id, nome_detectado, nivel_usuario, nivel_exigido, area,
                                    similaridade, resultado, mensagem, evidencia)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (_agora(), usuario_id, nome_detectado, nivel_usuario, nivel_exigido,
             config.AREAS.get(nivel_exigido, str(nivel_exigido)), similaridade, resultado, mensagem, evidencia),
        )
        self._con.commit()
        return cur.lastrowid

    def listar_acessos(self, limite: int | None = None, resultado: str | None = None) -> list[Acesso]:
        sql, params = "SELECT * FROM acessos", []
        if resultado:
            sql += " WHERE resultado = ?"
            params.append(resultado)
        sql += " ORDER BY data_hora DESC, id DESC"
        if limite:
            sql += " LIMIT ?"
            params.append(limite)
        return [Acesso(**dict(r)) for r in self._con.execute(sql, params)]

    def filtrar_acessos(self, *, limite: int | None = None, resultado: str | None = None,
                        nivel_exigido: int | None = None, desde: str | None = None,
                        termo: str | None = None) -> list[Acesso]:
        """Consulta só de leitura com filtros combinados (usada pela interface Qt).

        `desde`: data/hora ISO mínima (inclusive); `termo`: parte do nome detectado,
        sem diferenciar maiúsculas. O limite vale depois de aplicar os filtros."""
        sql, filtros, params = "SELECT * FROM acessos", [], []
        if resultado:
            filtros.append("resultado = ?")
            params.append(resultado)
        if nivel_exigido:
            filtros.append("nivel_exigido = ?")
            params.append(int(nivel_exigido))
        if desde:
            filtros.append("data_hora >= ?")
            params.append(desde)
        if termo:
            filtros.append("LOWER(COALESCE(nome_detectado, '')) LIKE ?")
            params.append(f"%{termo.lower()}%")
        if filtros:
            sql += " WHERE " + " AND ".join(filtros)
        sql += " ORDER BY data_hora DESC, id DESC"
        if limite:
            sql += " LIMIT ?"
            params.append(int(limite))
        return [Acesso(**dict(r)) for r in self._con.execute(sql, params)]

    def estatisticas(self) -> dict:
        por_resultado = {r[0]: r[1] for r in self._con.execute(
            "SELECT resultado, COUNT(*) FROM acessos GROUP BY resultado")}
        por_usuario = [dict(r) for r in self._con.execute(
            """SELECT COALESCE(u.nome, a.nome_detectado, 'DESCONHECIDO') AS nome,
                      SUM(a.resultado = 'CONCEDIDO') AS concedidos,
                      SUM(a.resultado != 'CONCEDIDO') AS negados
               FROM acessos a LEFT JOIN usuarios u ON u.id = a.usuario_id
               GROUP BY nome ORDER BY concedidos + negados DESC""")]
        por_dia = [dict(r) for r in self._con.execute(
            """SELECT substr(data_hora, 1, 10) AS dia, COUNT(*) AS total,
                      SUM(resultado = 'CONCEDIDO') AS concedidos
               FROM acessos GROUP BY dia ORDER BY dia DESC LIMIT 30""")]
        por_area = {r[0]: r[1] for r in self._con.execute(
            "SELECT area, COUNT(*) FROM acessos GROUP BY area")}
        return {
            "total": sum(por_resultado.values()),
            "por_resultado": por_resultado,
            "por_usuario": por_usuario,
            "por_dia": por_dia,
            "por_area": por_area,
            "usuarios": len(self.listar_usuarios()),
            "amostras": self._con.execute("SELECT COUNT(*) FROM amostras").fetchone()[0],
        }

    # ------------------------------------------------------------------ util
    @staticmethod
    def _usuario(row: sqlite3.Row) -> Usuario:
        d = dict(row)
        d["ativo"] = bool(d["ativo"])
        return Usuario(**d)

    def fechar(self) -> None:
        self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.fechar()
