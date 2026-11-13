"""Primitivas criptográficas e gestão de chaves em arquivo.

Substitui o RSA-1024 + PKCS1-OAEP do protótipo original por **assinaturas Ed25519**.

Por que assinar em vez de cifrar?
---------------------------------
No protótipo de 2016 a urna *cifrava* o voto com a chave pública da seção e as
máquinas de verificação/apuração *decifravam* com a chave privada. Isso não dá
autenticidade: qualquer pessoa com a chave pública (que é pública) consegue forjar
uma cédula "válida". O que o protocolo precisa é o contrário: a **urna assina** com
a chave privada da seção (que nunca sai da urna) e verificação/apuração **conferem a
assinatura** com a chave pública, que pode ser distribuída livremente, inclusive para
fiscais que queiram construir seu próprio apurador. O conteúdo do voto já é impresso
em texto claro na cédula, portanto cifrar o QR não acrescentava sigilo real.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

ChavePrivada = Ed25519PrivateKey
ChavePublica = Ed25519PublicKey


class ErroChave(ValueError):
    """Chave ausente, corrompida, de tipo errado ou senha incorreta."""


def gerar_chave() -> ChavePrivada:
    """Gera uma nova chave privada Ed25519 (a pública deriva dela)."""
    return Ed25519PrivateKey.generate()


def assinar(privada: ChavePrivada, mensagem: bytes) -> bytes:
    return privada.sign(mensagem)


def verificar(publica: ChavePublica, mensagem: bytes, assinatura: bytes) -> bool:
    try:
        publica.verify(assinatura, mensagem)
    except InvalidSignature:
        return False
    return True


def publica_bytes(publica: ChavePublica) -> bytes:
    """Os 32 bytes crus da chave pública."""
    return publica.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )


def publica_de_bytes(dados: bytes) -> ChavePublica:
    if len(dados) != 32:
        raise ErroChave("chave pública Ed25519 deve ter 32 bytes")
    return Ed25519PublicKey.from_public_bytes(dados)


def impressao_digital(publica: ChavePublica) -> str:
    """SHA-256 (hex) da chave pública — o que fiscais comparam entre máquinas."""
    return hashlib.sha256(publica_bytes(publica)).hexdigest()


def formatar_impressao(hex_digest: str, grupos: int = 8) -> str:
    """Formata um hash hex em grupos legíveis (ex.: 'A1B2C3D4 E5F6...')."""
    h = hex_digest.upper()
    return " ".join(h[i : i + grupos] for i in range(0, len(h), grupos))


# --------------------------------------------------------------------------- arquivos

def serializar_privada(privada: ChavePrivada, senha: str | None = None) -> bytes:
    enc: serialization.KeySerializationEncryption
    if senha:
        enc = serialization.BestAvailableEncryption(senha.encode("utf-8"))
    else:
        enc = serialization.NoEncryption()
    return privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=enc,
    )


def serializar_publica(publica: ChavePublica) -> bytes:
    return publica.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def salvar_privada(caminho: Path | str, privada: ChavePrivada, senha: str | None = None) -> Path:
    """Grava a chave privada em PEM com permissão 0600 (somente o dono lê)."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = serializar_privada(privada, senha)
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(dados)
    os.chmod(caminho, 0o600)
    return caminho


def salvar_publica(caminho: Path | str, publica: ChavePublica) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(serializar_publica(publica))
    return caminho


def carregar_privada(caminho: Path | str, senha: str | None = None) -> ChavePrivada:
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroChave(f"chave privada não encontrada: {caminho}")
    try:
        chave = serialization.load_pem_private_key(
            caminho.read_bytes(), password=senha.encode("utf-8") if senha else None
        )
    except (ValueError, TypeError) as e:
        raise ErroChave(f"não foi possível carregar {caminho.name}: senha incorreta ou arquivo inválido") from e
    if not isinstance(chave, Ed25519PrivateKey):
        raise ErroChave(f"{caminho.name} não é uma chave Ed25519")
    return chave


def carregar_publica(caminho: Path | str) -> ChavePublica:
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroChave(f"chave pública não encontrada: {caminho}")
    return carregar_publica_pem(caminho.read_bytes())


def carregar_publica_pem(pem: bytes) -> ChavePublica:
    try:
        chave = serialization.load_pem_public_key(pem)
    except ValueError as e:
        raise ErroChave("chave pública PEM inválida") from e
    if not isinstance(chave, Ed25519PublicKey):
        raise ErroChave("chave pública não é Ed25519")
    return chave
