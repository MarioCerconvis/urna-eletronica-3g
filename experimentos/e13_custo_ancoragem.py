"""E13 — Gás e latência de inclusão de cada transação de ancoragem, uma de cada vez (sem concorrência).

10 eleições no cluster de 12 validadores. Em cada uma: implanta um contrato novo (conta e nó 1), cria a eleição com
as 12 contas de validador como apuradoras (como nos ensaios), registra o boletim de cada uma das 12 seções pela conta
e pelo nó da própria seção e encerra a eleição (conta e nó 1). Cada transação só é enviada depois do recibo da
anterior, então a latência medida não sofre disputa por espaço no bloco (a capacidade sob rajada é o E9). Antes de
cada envio há uma espera aleatória uniforme de 0 a 2 s (um período de bloco, semente 1313): sem ela, cada envio
sairia logo depois do bloco que trouxe o recibo anterior e a latência ficaria presa perto de 2 s.

Latência de inclusão = tempo entre o envio da transação assinada e o recibo disponível no nó que a recebeu
(consulta a cada 0,1 s). Também se grava o timestamp do bloco de inclusão menos o instante do envio, que tem a
resolução de 1 s dos timestamps de bloco.
"""

from __future__ import annotations

import json
import os
import random
import time

import cluster as C
from comum import RAIZ, gravar, resumo
from eth_account import Account
from web3 import Web3

ELEICOES = 10
CEDULAS = 250
rng = random.Random(1313)
ART = json.loads((RAIZ / "deploy/blockchain/contracts/RegistroEleitoral.json").read_text())
METODO = (f"{ELEICOES} eleições; em cada uma: implantar (nó 1), criarEleicao com as 12 contas de validador, "
          "registrarBoletim das seções 001–012 cada uma pela conta e pelo nó da própria seção, encerrar (nó 1); "
          "uma transação por vez, após espera aleatória U(0, 2 s); latência = envio → recibo (consulta a cada 0,1 s)")


def w3_no(k: int) -> Web3:
    return Web3(Web3.HTTPProvider(C.url(k), request_kwargs={"timeout": 30}))


def conta(k: int):  # noqa: ANN201
    return Account.from_key((C.REDE / f"node{k}" / "key").read_text().strip())


def enviar(w3: Web3, ac, fn) -> tuple:  # noqa: ANN001
    tx = fn.build_transaction({"from": ac.address, "nonce": w3.eth.get_transaction_count(ac.address, "pending"),
                               "gasPrice": w3.eth.gas_price, "chainId": w3.eth.chain_id})
    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)
    bruto = ac.sign_transaction(tx).raw_transaction
    time.sleep(rng.uniform(0, 2))  # fase do envio independente da produção de blocos
    t_envio = time.time()
    t0 = time.perf_counter()
    h = w3.eth.send_raw_transaction(bruto)
    rec = w3.eth.wait_for_transaction_receipt(h, timeout=300, poll_latency=0.1)
    lat = time.perf_counter() - t0
    ts_bloco = int(C.bloco(rec.blockNumber)["timestamp"], 16)  # RPC cru: o extraData do QBFT barra o get_block
    return rec, lat, t_envio, ts_bloco


def main() -> None:
    linhas: list[dict] = []
    with C.Tunel():
        C.esperar_saudavel()
        contas = {k: conta(k) for k in range(1, C.N + 1)}
        w3s = {k: w3_no(k) for k in range(1, C.N + 1)}

        def registrar(eleicao: int, funcao: str, secao: str, k: int, resultado: tuple) -> None:
            rec, lat, t_envio, ts_bloco = resultado
            r = {"eleicao": eleicao, "funcao": funcao, "secao": secao, "no": C.ROT[C.IPS[k - 1]],
                 "gas_usado": rec.gasUsed, "status": rec.status, "bloco": rec.blockNumber,
                 "latencia_recibo_s": round(lat, 3), "latencia_timestamp_s": round(ts_bloco - t_envio, 3),
                 "tx": rec.transactionHash.hex()}
            linhas.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)

        for e in range(1, ELEICOES + 1):
            w1, a1 = w3s[1], contas[1]
            fab = w1.eth.contract(abi=ART["abi"], bytecode=ART["bytecode"])
            res = enviar(w1, a1, fab.constructor())
            registrar(e, "implantar", "", 1, res)
            endereco = res[0].contractAddress
            eid = os.urandom(32)
            c1 = w1.eth.contract(address=endereco, abi=ART["abi"])
            apuradores = [contas[k].address for k in range(1, C.N + 1)]
            registrar(e, "criarEleicao", "", 1, enviar(w1, a1, c1.functions.criarEleicao(eid, apuradores)))
            for k in range(1, C.N + 1):
                ck = w3s[k].eth.contract(address=endereco, abi=ART["abi"])
                fn = ck.functions.registrarBoletim(eid, f"{k:03d}", os.urandom(32), os.urandom(32), CEDULAS)
                registrar(e, "registrarBoletim", f"{k:03d}", k, enviar(w3s[k], contas[k], fn))
            registrar(e, "encerrar", "", 1, enviar(w1, a1, c1.functions.encerrar(eid, os.urandom(32))))
            gravar("e13-custo-ancoragem", {"metodo": METODO, "parcial": True, "transacoes": linhas})

    def stats(rs: list[dict]) -> dict:
        return {"gas": resumo([r["gas_usado"] for r in rs], 1),
                "latencia_recibo_s": resumo([r["latencia_recibo_s"] for r in rs], 3),
                "latencia_timestamp_s": resumo([r["latencia_timestamp_s"] for r in rs], 3)}

    por_funcao = {f: stats([r for r in linhas if r["funcao"] == f])
                  for f in ("implantar", "criarEleicao", "registrarBoletim", "encerrar")}
    reg = [r for r in linhas if r["funcao"] == "registrarBoletim"]
    primeiras = [r for r in reg if r["secao"] == "001"]
    demais = [r for r in reg if r["secao"] != "001"]
    print("->", gravar("e13-custo-ancoragem", {
        "metodo": METODO, "validadores": C.N, "eleicoes": ELEICOES, "por_funcao": por_funcao,
        "registrar_primeira_secao": stats(primeiras), "registrar_demais_secoes": stats(demais),
        "todas_com_sucesso": all(r["status"] == 1 for r in linhas), "transacoes": linhas}))


if __name__ == "__main__":
    main()
