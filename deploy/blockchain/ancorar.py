#!/usr/bin/env python3
"""Ancora boletins do urna3g no contrato RegistroEleitoral (web3.py).

    pip install 'urna3g[blockchain]'
    export URNA3G_ETH_KEY=0x...           # chave da conta (autoridade ou apurador) na rede permissionada

    python ancorar.py --rpc http://10.10.0.31:8545 implantar
    python ancorar.py --rpc ... --contrato 0x... criar --eleicao eleicao.json --apuradores 0xA 0xB
    python ancorar.py --rpc ... --contrato 0x... registrar --boletim saida/boletim-001.json
    python ancorar.py --rpc ... --contrato 0x... encerrar --mural-hash <hash_cadeia do /api/mural>
    python ancorar.py --rpc ... --contrato 0x... consultar --eleicao eleicao.json [--secao 001]

O hash do boletim é recalculado aqui com ``urna3g.boletim.hash_boletim`` — o mesmo que qualquer fiscal obtém
localmente — de modo que a cadeia nunca contém nada além do que já é público e verificável.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from urna3g import boletim as bmod
from urna3g.manifest import Eleicao

AQUI = Path(__file__).resolve().parent
ARTEFATO = AQUI / "contracts" / "RegistroEleitoral.json"  # {"abi": [...], "bytecode": "0x..."} gerado por compilar.py


def _web3(rpc: str):
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc))
    if not w3.is_connected():
        sys.exit(f"erro: não foi possível conectar a {rpc}")
    return w3


def _conta(w3):
    chave = os.environ.get("URNA3G_ETH_KEY")
    if not chave:
        sys.exit("erro: defina URNA3G_ETH_KEY com a chave privada da conta (nunca em linha de comando)")
    return w3.eth.account.from_key(chave)


def _artefato() -> dict:
    if not ARTEFATO.is_file():
        sys.exit(f"erro: {ARTEFATO} não existe; rode compilar.py (requer py-solc-x)")
    return json.loads(ARTEFATO.read_text())


def _enviar(w3, conta, fn):
    tx = fn.build_transaction(
        {"from": conta.address, "nonce": w3.eth.get_transaction_count(conta.address), "gasPrice": 0,
         "chainId": w3.eth.chain_id}
    )
    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)
    assinada = conta.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(assinada.raw_transaction)
    rec = w3.eth.wait_for_transaction_receipt(h, timeout=120)
    if rec.status != 1:
        sys.exit(f"erro: transação revertida ({h.hex()})")
    return rec


def _contrato(w3, endereco: str):
    return w3.eth.contract(address=w3.to_checksum_address(endereco), abi=_artefato()["abi"])


def _id(eleicao_json: str) -> bytes:
    return bytes.fromhex(Eleicao.carregar(eleicao_json).id)


def cmd_implantar(args, w3, conta):
    art = _artefato()
    fab = w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"])
    rec = _enviar(w3, conta, fab.constructor())
    print(f"contrato implantado em {rec.contractAddress} (bloco {rec.blockNumber})")


def cmd_criar(args, w3, conta):
    c = _contrato(w3, args.contrato)
    apuradores = [w3.to_checksum_address(a) for a in args.apuradores]
    rec = _enviar(w3, conta, c.functions.criarEleicao(_id(args.eleicao), apuradores))
    print(f"eleição criada: tx {rec.transactionHash.hex()} bloco {rec.blockNumber}")


def cmd_registrar(args, w3, conta):
    b = bmod.carregar(args.boletim)
    c = _contrato(w3, args.contrato)
    rec = _enviar(
        w3, conta,
        c.functions.registrarBoletim(
            bytes.fromhex(b["eleicao_id"]), b["secao"], bytes.fromhex(bmod.hash_boletim(b)),
            bytes.fromhex(b["ledger"]["hash_final"]), int(b["total_cedulas"]),
        ),
    )
    print(f"boletim da seção {b['secao']} ancorado: hash {bmod.hash_boletim(b)} tx {rec.transactionHash.hex()} "
          f"bloco {rec.blockNumber}")


def cmd_encerrar(args, w3, conta):
    c = _contrato(w3, args.contrato)
    rec = _enviar(w3, conta, c.functions.encerrar(_id(args.eleicao), bytes.fromhex(args.mural_hash)))
    print(f"eleição encerrada na cadeia: tx {rec.transactionHash.hex()} bloco {rec.blockNumber}")


def cmd_consultar(args, w3, conta=None):
    c = _contrato(w3, args.contrato)
    eid = _id(args.eleicao)
    autoridade, existe, encerrada, mural, n = c.functions.eleicao(eid).call()
    print(f"eleição {eid.hex()}\n  existe={existe} encerrada={encerrada} autoridade={autoridade} seções={n}")
    if encerrada:
        print(f"  hash do mural: {mural.hex()}")
    secoes = [args.secao] if args.secao else c.functions.secoes(eid).call()
    for s in secoes:
        hb, hl, total, bloco, quem = c.functions.boletim(eid, s).call()
        print(f"  seção {s}: boletim {hb.hex()} ledger {hl.hex()} cédulas {total} bloco {bloco} por {quem}")
        if args.boletim:
            b = bmod.carregar(args.boletim)
            ok = bmod.hash_boletim(b) == hb.hex() and b["secao"] == s
            print(f"    confere com {args.boletim}: {'SIM' if ok else 'NÃO'}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rpc", default="http://127.0.0.1:8545")
    p.add_argument("--contrato", help="endereço do RegistroEleitoral")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("implantar").set_defaults(func=cmd_implantar)
    c = sub.add_parser("criar")
    c.add_argument("--eleicao", required=True)
    c.add_argument("--apuradores", nargs="+", required=True)
    c.set_defaults(func=cmd_criar)
    r = sub.add_parser("registrar")
    r.add_argument("--boletim", required=True)
    r.set_defaults(func=cmd_registrar)
    e = sub.add_parser("encerrar")
    e.add_argument("--eleicao", required=True)
    e.add_argument("--mural-hash", required=True)
    e.set_defaults(func=cmd_encerrar)
    q = sub.add_parser("consultar")
    q.add_argument("--eleicao", required=True)
    q.add_argument("--secao")
    q.add_argument("--boletim")
    q.set_defaults(func=cmd_consultar)
    args = p.parse_args(argv)
    w3 = _web3(args.rpc)
    if args.cmd == "consultar":
        cmd_consultar(args, w3)
        return 0
    if args.cmd != "implantar" and not args.contrato:
        sys.exit("erro: informe --contrato")
    args.func(args, w3, _conta(w3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
