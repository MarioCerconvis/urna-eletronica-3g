"""Ledger local da apuração: registro *append-only* encadeado por hash (SQLite).

Cada cédula aceita vira um registro ``hash = SHA-256(hash_anterior ‖ seq ‖ tipo ‖ dados)``.
Qualquer alteração, remoção ou reordenação posterior quebra a cadeia e é detectada por
``verificar()``. O hash final entra no boletim de urna assinado — e é exatamente esse
valor que pode ser *ancorado* em uma blockchain permissionada (ver ``docs/04-blockchain.md``),
sem expor votos individuais nem a ordem de votação.

Não há timestamps por registro de propósito: a ordem de leitura das cédulas na apuração
não deve permitir reconstruir a ordem em que eleitores votaram (princípio da
inviolabilidade do voto, Brunazo & Gazziro 2014).
"""

from __future__ import annotations

import hashlib
import pathlib
import sqlite3
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

CONTEXTO = b"urna3g/ledger/v1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS registros (
    seq           INTEGER PRIMARY KEY,
    tipo          TEXT    NOT NULL,
    dados         TEXT    NOT NULL,
    hash_anterior BLOB    NOT NULL,
    hash          BLOB    NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS cedulas (
    nonce BLOB    PRIMARY KEY,
    seq   INTEGER NOT NULL UNIQUE REFERENCES registros(seq)
);
CREATE TABLE IF NOT EXISTS ocorrencias (
    id      INTEGER PRIMARY KEY,
    tipo    TEXT NOT NULL,
    detalhe TEXT NOT NULL DEFAULT ''
);
"""


class ErroLedger(RuntimeError):
    """Cadeia quebrada, nonce duplicado ou ledger de outra eleição/seção."""


@dataclass(frozen=True)
class Registro:
    seq: int
    tipo: str
    dados: str
    hash_anterior: bytes
    hash: bytes


class Ledger:
    def __init__(self, caminho: Path | str, eleicao_id: str, secao: str):
        self.caminho = str(caminho)
        pathlib.Path(self.caminho).parent.mkdir(parents=True, exist_ok=True)
        self.eleicao_id = eleicao_id
        self.secao = secao
        self.con = sqlite3.connect(self.caminho, isolation_level=None)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA synchronous=FULL")  # resistência a queda de energia
        self.con.execute("PRAGMA foreign_keys=ON")
        self.con.executescript(_SCHEMA)
        id_existente = self.meta("eleicao_id")
        if id_existente is None:
            self.set_meta("eleicao_id", eleicao_id)
            self.set_meta("secao", secao)
        elif id_existente != eleicao_id or self.meta("secao") != secao:
            raise ErroLedger(
                f"o arquivo {self.caminho} pertence à eleição {id_existente[:16]}… seção "
                f"{self.meta('secao')}, não a {eleicao_id[:16]}… seção {secao}"
            )

    # ------------------------------------------------------------------ hashing
    @property
    def genesis(self) -> bytes:
        return hashlib.sha256(
            CONTEXTO + self.eleicao_id.encode("ascii") + b"/" + self.secao.encode("utf-8")
        ).digest()

    @staticmethod
    def calcular_hash(hash_anterior: bytes, seq: int, tipo: str, dados: str) -> bytes:
        h = hashlib.sha256()
        h.update(hash_anterior)
        h.update(struct.pack(">Q", seq))
        h.update(tipo.encode("utf-8"))
        h.update(b"\x00")
        h.update(dados.encode("utf-8"))
        return h.digest()

    def ultimo(self) -> tuple[int, bytes]:
        row = self.con.execute("SELECT seq, hash FROM registros ORDER BY seq DESC LIMIT 1").fetchone()
        return (int(row[0]), bytes(row[1])) if row else (0, self.genesis)

    @property
    def hash_final(self) -> str:
        return self.ultimo()[1].hex()

    # ------------------------------------------------------------------ escrita
    def anexar(self, tipo: str, dados: str, nonce: bytes | None = None) -> Registro:
        """Anexa um registro de forma atômica (registro + nonce na mesma transação)."""
        self.con.execute("BEGIN IMMEDIATE")
        try:
            seq_ant, hash_ant = self.ultimo()
            seq = seq_ant + 1
            h = self.calcular_hash(hash_ant, seq, tipo, dados)
            self.con.execute(
                "INSERT INTO registros(seq, tipo, dados, hash_anterior, hash) VALUES (?,?,?,?,?)",
                (seq, tipo, dados, hash_ant, h),
            )
            if nonce is not None:
                try:
                    self.con.execute("INSERT INTO cedulas(nonce, seq) VALUES (?,?)", (nonce, seq))
                except sqlite3.IntegrityError as e:
                    raise ErroLedger("cédula já registrada (nonce duplicado)") from e
            self.con.execute("COMMIT")
        except BaseException:
            self.con.execute("ROLLBACK")
            raise
        return Registro(seq, tipo, dados, hash_ant, h)

    def contem_nonce(self, nonce: bytes) -> bool:
        return self.con.execute("SELECT 1 FROM cedulas WHERE nonce=?", (nonce,)).fetchone() is not None

    def ocorrencia(self, tipo: str, detalhe: str = "") -> None:
        """Eventos que NÃO entram na cadeia (leituras duplicadas, inválidas…) mas são auditáveis."""
        self.con.execute("INSERT INTO ocorrencias(tipo, detalhe) VALUES (?,?)", (tipo, detalhe[:500]))

    # ------------------------------------------------------------------ leitura
    def registros(self, tipo: str | None = None) -> list[Registro]:
        if tipo is None:
            cur = self.con.execute("SELECT seq,tipo,dados,hash_anterior,hash FROM registros ORDER BY seq")
        else:
            cur = self.con.execute(
                "SELECT seq,tipo,dados,hash_anterior,hash FROM registros WHERE tipo=? ORDER BY seq", (tipo,)
            )
        return [Registro(int(s), t, d, bytes(ha), bytes(h)) for s, t, d, ha, h in cur]

    def ocorrencias(self) -> Counter[str]:
        return Counter(t for (t,) in self.con.execute("SELECT tipo FROM ocorrencias"))

    def verificar(self) -> int:
        """Recalcula toda a cadeia. Retorna o nº de registros; levanta ErroLedger se houver quebra."""
        esperado = self.genesis
        seq_esperado = 1
        for r in self.registros():
            if r.seq != seq_esperado:
                raise ErroLedger(f"sequência interrompida: esperado {seq_esperado}, encontrado {r.seq}")
            if r.hash_anterior != esperado:
                raise ErroLedger(f"registro {r.seq}: hash_anterior não confere")
            if self.calcular_hash(r.hash_anterior, r.seq, r.tipo, r.dados) != r.hash:
                raise ErroLedger(f"registro {r.seq}: conteúdo alterado (hash não confere)")
            esperado = r.hash
            seq_esperado += 1
        n_cedulas = self.con.execute("SELECT COUNT(*) FROM cedulas").fetchone()[0]
        n_reg_cedula = self.con.execute("SELECT COUNT(*) FROM registros WHERE tipo='cedula'").fetchone()[0]
        if n_cedulas != n_reg_cedula:
            raise ErroLedger("tabela de nonces inconsistente com os registros de cédula")
        return seq_esperado - 1

    def meta(self, chave: str) -> str | None:
        row = self.con.execute("SELECT valor FROM meta WHERE chave=?", (chave,)).fetchone()
        return row[0] if row else None

    def set_meta(self, chave: str, valor: str) -> None:
        self.con.execute("INSERT OR REPLACE INTO meta(chave, valor) VALUES (?,?)", (chave, valor))

    def fechar(self) -> None:
        self.con.close()

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *exc: object) -> None:
        self.fechar()
