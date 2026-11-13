"""Manifesto da eleição: cargos, partidos (ou chapas) e candidatos.

No protótipo original o cadastro ficava em um SQLite mutável (``eleicoesdb.db``) copiado
para cada máquina. Aqui a eleição é um **arquivo JSON imutável** cujo SHA-256 canônico
é o *identificador da eleição*: ele vai embutido em cada cédula, no ledger e no boletim,
garantindo que todas as 13 máquinas (urnas, verificadores, apuradores) e o servidor
falam da *mesma* eleição. O manifesto é assinado pela chave da autoridade eleitoral e
as fotos têm seu hash registrado, para que uma troca de foto/candidato em uma máquina
seja detectável.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from urna3g import BRANCO, NULO, crypto

FORMATO = 1
CONTEXTO_ASSINATURA = b"urna3g/eleicao/v1"
_RE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_RE_SECAO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,15}$")
MAX_VOTOS_POR_ELEITOR = 20
MAX_DIGITOS = 6


class ErroManifesto(ValueError):
    """Manifesto estruturalmente inválido ou inconsistente."""


@dataclass(frozen=True)
class Cargo:
    id: str
    nome: str
    votos_por_eleitor: int = 1
    digitos: int | None = None  # se None, derivado dos números dos candidatos


@dataclass(frozen=True)
class Partido:
    numero: int
    nome: str
    sigla: str
    presidente: str = ""
    foto: str | None = None
    foto_sha256: str | None = None


@dataclass(frozen=True)
class Candidato:
    numero: int
    nome: str
    cargo: str
    partido: int
    titulo: str | None = None
    foto: str | None = None
    foto_sha256: str | None = None


@dataclass(frozen=True)
class Slot:
    """Uma posição de voto na cédula (um cargo pode ter várias, ex.: 2 senadores)."""

    cargo_id: str
    indice: int  # 0-based dentro do cargo
    posicao: int  # 0-based na cédula


def _limpar(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


@dataclass
class Eleicao:
    nome: str
    data: str = ""
    cargos: list[Cargo] = field(default_factory=list)
    partidos: list[Partido] = field(default_factory=list)
    candidatos: list[Candidato] = field(default_factory=list)
    secoes: list[str] = field(default_factory=list)
    formato: int = FORMATO
    base_dir: Path | None = field(default=None, compare=False, repr=False)

    # ------------------------------------------------------------------ (de)serialização
    def to_dict(self) -> dict[str, Any]:
        return {
            "formato": self.formato,
            "nome": self.nome,
            "data": self.data,
            "secoes": list(self.secoes),
            "cargos": [_limpar(asdict(c)) for c in self.cargos],
            "partidos": [_limpar(asdict(p)) for p in self.partidos],
            "candidatos": [_limpar(asdict(c)) for c in self.candidatos],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], base_dir: Path | None = None) -> Eleicao:
        try:
            return cls(
                nome=str(d["nome"]),
                data=str(d.get("data", "")),
                cargos=[Cargo(**c) for c in d.get("cargos", [])],
                partidos=[Partido(**p) for p in d.get("partidos", [])],
                candidatos=[Candidato(**c) for c in d.get("candidatos", [])],
                secoes=[str(s) for s in d.get("secoes", [])],
                formato=int(d.get("formato", FORMATO)),
                base_dir=base_dir,
            )
        except (KeyError, TypeError) as e:
            raise ErroManifesto(f"manifesto malformado: {e}") from e

    def canonico(self) -> bytes:
        """JSON canônico (chaves ordenadas, sem espaços) — base do identificador."""
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def id(self) -> str:
        """SHA-256 hex do manifesto canônico."""
        return hashlib.sha256(self.canonico()).hexdigest()

    @property
    def id_curto(self) -> bytes:
        """Primeiros 8 bytes do id — o que cabe no QR da cédula."""
        return bytes.fromhex(self.id[:16])

    def salvar(self, caminho: Path | str) -> Path:
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self.base_dir = caminho.parent
        return caminho

    @classmethod
    def carregar(cls, caminho: Path | str) -> Eleicao:
        caminho = Path(caminho)
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except FileNotFoundError as e:
            raise ErroManifesto(f"manifesto não encontrado: {caminho}") from e
        except json.JSONDecodeError as e:
            raise ErroManifesto(f"JSON inválido em {caminho}: {e}") from e
        return cls.from_dict(dados, base_dir=caminho.parent)

    # ------------------------------------------------------------------ consultas
    def cargo(self, cargo_id: str) -> Cargo:
        for c in self.cargos:
            if c.id == cargo_id:
                return c
        raise KeyError(cargo_id)

    def candidatos_do_cargo(self, cargo_id: str) -> list[Candidato]:
        return sorted((c for c in self.candidatos if c.cargo == cargo_id), key=lambda c: c.numero)

    def candidato(self, cargo_id: str, numero: int) -> Candidato | None:
        for c in self.candidatos:
            if c.cargo == cargo_id and c.numero == numero:
                return c
        return None

    def partido(self, numero: int) -> Partido | None:
        for p in self.partidos:
            if p.numero == numero:
                return p
        return None

    def digitos(self, cargo_id: str) -> int:
        cargo = self.cargo(cargo_id)
        if cargo.digitos:
            return cargo.digitos
        numeros = [len(str(c.numero)) for c in self.candidatos_do_cargo(cargo_id)]
        return max(numeros) if numeros else 2

    def slots(self) -> list[Slot]:
        slots: list[Slot] = []
        for cargo in self.cargos:
            for i in range(cargo.votos_por_eleitor):
                slots.append(Slot(cargo.id, i, len(slots)))
        return slots

    def descrever_voto(self, cargo_id: str, valor: int) -> str:
        if valor == BRANCO:
            return "Branco"
        if valor == NULO:
            return "Nulo"
        cand = self.candidato(cargo_id, valor)
        if cand is None:
            return f"{valor} (número inexistente)"
        partido = self.partido(cand.partido)
        sigla = f" ({partido.sigla})" if partido else ""
        return f"{cand.numero} - {cand.nome}{sigla}"

    def caminho(self, relativo: str) -> Path:
        if self.base_dir is None:
            raise ErroManifesto("manifesto sem diretório base; use Eleicao.carregar()")
        return (self.base_dir / relativo).resolve()

    # ------------------------------------------------------------------ validação
    def validar(self, verificar_fotos: bool = False) -> None:
        erros: list[str] = []
        if self.formato != FORMATO:
            erros.append(f"formato {self.formato} não suportado (esperado {FORMATO})")
        if not self.nome.strip():
            erros.append("nome da eleição vazio")
        if not self.cargos:
            erros.append("eleição sem cargos")

        ids = set()
        for c in self.cargos:
            if not _RE_ID.match(c.id):
                erros.append(f"id de cargo inválido: {c.id!r} (use [a-z0-9_-], até 32 chars)")
            if c.id in ids:
                erros.append(f"cargo duplicado: {c.id}")
            ids.add(c.id)
            if not c.nome.strip():
                erros.append(f"cargo {c.id} sem nome")
            if not 1 <= int(c.votos_por_eleitor) <= MAX_VOTOS_POR_ELEITOR:
                erros.append(f"cargo {c.id}: votos_por_eleitor fora de 1..{MAX_VOTOS_POR_ELEITOR}")
            if c.digitos is not None and not 1 <= int(c.digitos) <= MAX_DIGITOS:
                erros.append(f"cargo {c.id}: digitos fora de 1..{MAX_DIGITOS}")

        secoes = set()
        for s in self.secoes:
            if not _RE_SECAO.match(s):
                erros.append(f"identificador de seção inválido: {s!r}")
            if s in secoes:
                erros.append(f"seção duplicada: {s}")
            secoes.add(s)

        numeros_partidos = set()
        for p in self.partidos:
            if not isinstance(p.numero, int) or p.numero < 1:
                erros.append(f"partido com número inválido: {p.numero!r}")
            if p.numero in numeros_partidos:
                erros.append(f"partido duplicado: {p.numero}")
            numeros_partidos.add(p.numero)
            if not p.nome.strip() or not p.sigla.strip():
                erros.append(f"partido {p.numero} sem nome/sigla")

        chaves = set()
        titulos = set()
        for c in self.candidatos:
            if not isinstance(c.numero, int) or c.numero < 1:
                erros.append(f"candidato {c.nome!r} com número inválido: {c.numero!r}")
                continue
            if c.cargo not in ids:
                erros.append(f"candidato {c.numero} refere cargo inexistente {c.cargo!r}")
            if c.partido not in numeros_partidos:
                erros.append(f"candidato {c.numero} refere partido inexistente {c.partido!r}")
            if not c.nome.strip():
                erros.append(f"candidato {c.numero} sem nome")
            if (c.cargo, c.numero) in chaves:
                erros.append(f"número {c.numero} repetido no cargo {c.cargo}")
            chaves.add((c.cargo, c.numero))
            if c.titulo:
                if c.titulo in titulos:
                    erros.append(f"título de eleitor repetido: {c.titulo}")
                titulos.add(c.titulo)
            if c.cargo in ids and len(str(c.numero)) > self.digitos(c.cargo):
                erros.append(
                    f"candidato {c.numero} excede os {self.digitos(c.cargo)} dígitos do cargo {c.cargo}"
                )

        if verificar_fotos:
            for obj in [*self.partidos, *self.candidatos]:
                if obj.foto is None:
                    continue
                try:
                    p = self.caminho(obj.foto)
                except ErroManifesto as e:
                    erros.append(str(e))
                    break
                if not p.is_file():
                    erros.append(f"foto não encontrada: {obj.foto}")
                elif obj.foto_sha256 and _sha256_arquivo(p) != obj.foto_sha256:
                    erros.append(f"foto alterada (hash difere): {obj.foto}")

        if erros:
            raise ErroManifesto("; ".join(erros))

    def preencher_hashes_fotos(self) -> Eleicao:
        """Retorna uma cópia com ``foto_sha256`` preenchido para cada foto existente."""
        partidos = [
            replace(p, foto_sha256=_sha256_arquivo(self.caminho(p.foto))) if p.foto else p
            for p in self.partidos
        ]
        candidatos = [
            replace(c, foto_sha256=_sha256_arquivo(self.caminho(c.foto))) if c.foto else c
            for c in self.candidatos
        ]
        return replace(self, partidos=partidos, candidatos=candidatos)


# ---------------------------------------------------------------------- assinatura

def assinar_manifesto(eleicao: Eleicao, privada: crypto.ChavePrivada) -> bytes:
    return crypto.assinar(privada, CONTEXTO_ASSINATURA + eleicao.canonico())


def verificar_manifesto(eleicao: Eleicao, publica: crypto.ChavePublica, assinatura: bytes) -> bool:
    return crypto.verificar(publica, CONTEXTO_ASSINATURA + eleicao.canonico(), assinatura)


def salvar_assinatura(caminho: Path | str, assinatura: bytes) -> Path:
    caminho = Path(caminho)
    caminho.write_text(base64.b64encode(assinatura).decode("ascii") + "\n", encoding="ascii")
    return caminho


def carregar_assinatura(caminho: Path | str) -> bytes:
    try:
        return base64.b64decode(Path(caminho).read_text(encoding="ascii").strip(), validate=True)
    except (OSError, ValueError) as e:
        raise ErroManifesto(f"assinatura do manifesto ilegível: {caminho}") from e
