"""Cédula: o registro digital impresso no código QR.

Formato binário v1 (big-endian), codificado em base64url sem padding e prefixado por
``U3G1:`` para que leitores de QR do tipo "teclado" (keyboard wedge) digitem uma
linha reconhecível::

    1 B  versão (=1)
    8 B  id curto da eleição (SHA-256 do manifesto, 8 primeiros bytes)
    1 B  tamanho da seção  +  N B  seção (UTF-8, até 16 bytes)
    1 B  nº de slots       +  4 B por slot (int32: >0 candidato, 0 branco, -1 nulo)
   16 B  nonce aleatório (identificador único da cédula; evita dupla contagem)
   64 B  assinatura Ed25519 sobre b"urna3g/cedula/v1" + tudo acima

Com 3 cargos: ~107 bytes → ~143 caracteres → QR versão 7/8, legível por webcams
de 640×480 (menor que o RSA-1024 em base64 do protótipo original).

O nonce de 128 bits elimina na prática a colisão discutida na seção 4 do artigo de
2017 (o original usava ``randint(0, 1e9)``: ~30 bits).
"""

from __future__ import annotations

import base64
import binascii
import secrets
import struct
from dataclasses import dataclass

from urna3g import BRANCO, NULO, crypto
from urna3g.manifest import Eleicao

PREFIXO = "U3G1:"
VERSAO = 1
CONTEXTO = b"urna3g/cedula/v1"
TAM_ID = 8
TAM_NONCE = 16
TAM_ASSINATURA = 64
MAX_SECAO = 16
MAX_SLOTS = 40


class ErroCedula(ValueError):
    """Cédula malformada, de outra eleição/seção ou com assinatura inválida."""


def _b64e(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _b64d(texto: str) -> bytes:
    texto = texto.strip()
    texto += "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto.encode("ascii"))


@dataclass(frozen=True)
class Cedula:
    eleicao_id_curto: bytes
    secao: str
    votos: tuple[int, ...]
    nonce: bytes
    assinatura: bytes | None = None

    def cabecalho(self) -> bytes:
        sec = self.secao.encode("utf-8")
        partes = [
            struct.pack(">B", VERSAO),
            self.eleicao_id_curto,
            struct.pack(">B", len(sec)),
            sec,
            struct.pack(">B", len(self.votos)),
            *(struct.pack(">i", v) for v in self.votos),
            self.nonce,
        ]
        return b"".join(partes)

    def mensagem(self) -> bytes:
        """Bytes efetivamente assinados (com separação de domínio)."""
        return CONTEXTO + self.cabecalho()

    def texto(self) -> str:
        """Conteúdo do QR."""
        if self.assinatura is None:
            raise ErroCedula("cédula não assinada")
        return PREFIXO + _b64e(self.cabecalho() + self.assinatura)

    @property
    def nonce_hex(self) -> str:
        return self.nonce.hex()


def emitir(
    eleicao: Eleicao,
    secao: str,
    votos: list[int] | tuple[int, ...],
    privada: crypto.ChavePrivada,
    nonce: bytes | None = None,
) -> Cedula:
    """Monta, valida e assina uma cédula (executado na urna de votação)."""
    slots = eleicao.slots()
    valores = tuple(int(v) for v in votos)
    if len(valores) != len(slots):
        raise ErroCedula(f"esperados {len(slots)} votos, recebidos {len(valores)}")
    for slot, v in zip(slots, valores, strict=True):
        if v in (BRANCO, NULO):
            continue
        if v < 1 or eleicao.candidato(slot.cargo_id, v) is None:
            raise ErroCedula(f"candidato {v} inexistente para o cargo {slot.cargo_id!r}")
    if not 1 <= len(secao.encode("utf-8")) <= MAX_SECAO:
        raise ErroCedula("identificador de seção deve ter de 1 a 16 bytes")
    if len(slots) > MAX_SLOTS:
        raise ErroCedula(f"a cédula suporta no máximo {MAX_SLOTS} votos")
    nonce = nonce if nonce is not None else secrets.token_bytes(TAM_NONCE)
    if len(nonce) != TAM_NONCE:
        raise ErroCedula("nonce deve ter 16 bytes")
    base = Cedula(eleicao.id_curto, secao, valores, nonce)
    return Cedula(base.eleicao_id_curto, base.secao, base.votos, base.nonce,
                  crypto.assinar(privada, base.mensagem()))


def decodificar(texto: str) -> Cedula:
    """Decodifica o texto do QR *sem* verificar a assinatura (use ``verificar``)."""
    texto = texto.strip()
    if not texto.startswith(PREFIXO):
        raise ErroCedula("código não é uma cédula urna3g (prefixo desconhecido)")
    try:
        dados = _b64d(texto[len(PREFIXO):])
    except (ValueError, binascii.Error) as e:
        raise ErroCedula("codificação base64 inválida") from e

    pos = 0

    def pegar(n: int) -> bytes:
        nonlocal pos
        if pos + n > len(dados):
            raise ErroCedula("cédula truncada")
        bloco = dados[pos : pos + n]
        pos += n
        return bloco

    versao = pegar(1)[0]
    if versao != VERSAO:
        raise ErroCedula(f"versão de cédula {versao} não suportada")
    id_curto = pegar(TAM_ID)
    n_sec = pegar(1)[0]
    if not 1 <= n_sec <= MAX_SECAO:
        raise ErroCedula("tamanho de seção inválido")
    try:
        secao = pegar(n_sec).decode("utf-8")
    except UnicodeDecodeError as e:
        raise ErroCedula("seção com codificação inválida") from e
    n_votos = pegar(1)[0]
    if n_votos > MAX_SLOTS:
        raise ErroCedula("número de votos inválido")
    votos = tuple(struct.unpack(">i", pegar(4))[0] for _ in range(n_votos))
    nonce = pegar(TAM_NONCE)
    assinatura = pegar(TAM_ASSINATURA)
    if pos != len(dados):
        raise ErroCedula("dados excedentes após a assinatura")
    return Cedula(id_curto, secao, votos, nonce, assinatura)


def verificar(
    cedula: Cedula,
    eleicao: Eleicao,
    publica: crypto.ChavePublica,
    secao_esperada: str | None = None,
) -> None:
    """Confere eleição, seção e assinatura. Levanta ``ErroCedula`` se algo falhar."""
    if cedula.eleicao_id_curto != eleicao.id_curto:
        raise ErroCedula("cédula pertence a outra eleição")
    if secao_esperada is not None and cedula.secao != secao_esperada:
        raise ErroCedula(f"cédula da seção {cedula.secao}, esperada {secao_esperada}")
    if cedula.assinatura is None or not crypto.verificar(publica, cedula.mensagem(), cedula.assinatura):
        raise ErroCedula("assinatura inválida: cédula não pertence a esta seção")
    if len(cedula.votos) != len(eleicao.slots()):
        raise ErroCedula("número de votos incompatível com a eleição")


def ler(
    texto: str,
    eleicao: Eleicao,
    publica: crypto.ChavePublica,
    secao_esperada: str | None = None,
) -> Cedula:
    """Decodifica e verifica em um passo (o que verificação e apuração fazem)."""
    cedula = decodificar(texto)
    verificar(cedula, eleicao, publica, secao_esperada)
    return cedula


def descrever(cedula: Cedula, eleicao: Eleicao) -> list[tuple[str, str]]:
    """Lista (título do slot, descrição do voto) para exibir/imprimir."""
    linhas: list[tuple[str, str]] = []
    for slot, valor in zip(eleicao.slots(), cedula.votos, strict=False):
        cargo = eleicao.cargo(slot.cargo_id)
        titulo = cargo.nome
        if cargo.votos_por_eleitor > 1:
            titulo = f"{cargo.nome} ({slot.indice + 1}º voto)"
        linhas.append((titulo, eleicao.descrever_voto(slot.cargo_id, valor)))
    return linhas
