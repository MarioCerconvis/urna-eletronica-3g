"""Boletim de urna: resultado da seção em JSON canônico, assinado pela máquina de apuração."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from urna3g import crypto

FORMATO = 1
CONTEXTO = b"urna3g/boletim/v1"
PREFIXO_QR = "BU1:"


class ErroBoletim(ValueError):
    """Boletim sem assinatura, com assinatura inválida ou malformado."""


def canonico(boletim: dict[str, Any]) -> bytes:
    corpo = {k: v for k, v in boletim.items() if k != "assinatura"}
    return json.dumps(corpo, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hash_boletim(boletim: dict[str, Any]) -> str:
    return hashlib.sha256(canonico(boletim)).hexdigest()


def assinar(boletim: dict[str, Any], privada: crypto.ChavePrivada) -> dict[str, Any]:
    novo = {k: v for k, v in boletim.items() if k != "assinatura"}
    novo["assinatura"] = base64.b64encode(crypto.assinar(privada, CONTEXTO + canonico(novo))).decode("ascii")
    return novo


def verificar(boletim: dict[str, Any], publica: crypto.ChavePublica) -> None:
    try:
        assinatura = base64.b64decode(boletim["assinatura"], validate=True)
    except (KeyError, TypeError, ValueError) as e:
        raise ErroBoletim("boletim sem assinatura válida") from e
    for campo in ("formato", "eleicao_id", "secao", "resultados", "ledger", "total_cedulas"):
        if campo not in boletim:
            raise ErroBoletim(f"boletim sem o campo obrigatório {campo!r}")
    if boletim["formato"] != FORMATO:
        raise ErroBoletim(f"formato de boletim {boletim['formato']} não suportado")
    if not crypto.verificar(publica, CONTEXTO + canonico(boletim), assinatura):
        raise ErroBoletim("assinatura do boletim inválida")


def texto_qr(boletim: dict[str, Any]) -> str:
    """Conteúdo do QR impresso no boletim: seção + hash, para fiscais fotografarem."""
    return f"{PREFIXO_QR}{boletim['secao']}:{hash_boletim(boletim)}"


def salvar(boletim: dict[str, Any], caminho: Path | str) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(boletim, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return caminho


def carregar(caminho: Path | str) -> dict[str, Any]:
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ErroBoletim(f"não foi possível ler o boletim {caminho}: {e}") from e
    if not isinstance(dados, dict):
        raise ErroBoletim("boletim deve ser um objeto JSON")
    return dados
