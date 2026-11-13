#!/usr/bin/env python3
"""Compila RegistroEleitoral.sol → contracts/RegistroEleitoral.json (abi + bytecode). Requer py-solc-x."""

from __future__ import annotations

import json
from pathlib import Path

import solcx

AQUI = Path(__file__).resolve().parent
VERSAO = "0.8.26"


def compilar() -> dict:
    if VERSAO not in [str(v) for v in solcx.get_installed_solc_versions()]:
        solcx.install_solc(VERSAO)
    fonte = (AQUI / "contracts" / "RegistroEleitoral.sol").read_text()
    saida = solcx.compile_source(
        fonte, output_values=["abi", "bin"], solc_version=VERSAO, optimize=True, optimize_runs=200
    )
    (_, contrato), = saida.items()
    artefato = {"abi": contrato["abi"], "bytecode": "0x" + contrato["bin"], "solc": VERSAO}
    (AQUI / "contracts" / "RegistroEleitoral.json").write_text(json.dumps(artefato, indent=1))
    return artefato


if __name__ == "__main__":
    art = compilar()
    print(f"ok: {len(art['abi'])} entradas na ABI, {len(art['bytecode']) // 2} bytes de bytecode")
