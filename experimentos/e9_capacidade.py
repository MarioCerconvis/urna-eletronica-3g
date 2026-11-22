"""E9 — Custo (gás) e capacidade da ancoragem.

(a) Gás de cada operação do contrato (implantar, criar, registrar, encerrar), a partir dos recibos.
(b) Rajada: cada um dos 12 validadores (como apurador) envia 100 registros de boletim pelo SEU nó, sem pausa e com
    o gás estimado uma vez por conta — 1 200 transações por repetição, 3 repetições. Mede a taxa oferecida, a vazão
    na cadeia, transações por bloco e a latência de inclusão (timestamp do bloco − instante do envio). Uma eleição
    nova (id aleatório) por repetição. (Uma primeira versão estimava o gás a cada envio — o que limitava a taxa
    oferecida — e media a latência só depois de terminar todos os envios; foi descartada.)
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter

import cluster as C
from comum import RAIZ, RESULTADOS, gravar, resumo
from eth_account import Account
from web3 import Web3

POR_CONTA, REPS = 100, 3
ART = json.loads((RAIZ / "deploy/blockchain/contracts/RegistroEleitoral.json").read_text())


def w3_no(k: int) -> Web3:
    return Web3(Web3.HTTPProvider(C.url(k), request_kwargs={"timeout": 30}))


def conta(k: int):  # noqa: ANN201
    return Account.from_key((C.REDE / f"node{k}" / "key").read_text().strip())


def enviar(w3: Web3, ac, fn, nonce: int | None = None, gas: int | None = None):  # noqa: ANN001, ANN201
    tx = fn.build_transaction({"from": ac.address, "nonce": w3.eth.get_transaction_count(ac.address, "pending") if nonce is None else nonce,
                               "gasPrice": w3.eth.gas_price, "chainId": w3.eth.chain_id, **({"gas": gas} if gas else {})})
    if not gas:
        tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)
    return w3.eth.send_raw_transaction(ac.sign_transaction(tx).raw_transaction)


def main() -> None:
    am = C.Amostrador(RESULTADOS / "e12-recursos.jsonl")
    am.start()
    try:
        with C.Tunel():
            C.esperar_saudavel()
            w3 = w3_no(1)
            ac1 = conta(1)
            fab = w3.eth.contract(abi=ART["abi"], bytecode=ART["bytecode"])
            rec_dep = w3.eth.wait_for_transaction_receipt(enviar(w3, ac1, fab.constructor()), timeout=180)
            end = rec_dep.contractAddress
            gas = {"implantar": rec_dep.gasUsed, "criar": [], "registrar": [], "encerrar": []}
            reps = []
            for rep in range(1, REPS + 1):
                am.rotulo = f"e9_r{rep}"
                eid = os.urandom(32)
                c1 = w3.eth.contract(address=end, abi=ART["abi"])
                apuradores = [Web3.to_checksum_address(v[1]) for v in C.VALIDADORES]
                rc = w3.eth.wait_for_transaction_receipt(enviar(w3, ac1, c1.functions.criarEleicao(eid, apuradores)), timeout=180)
                gas["criar"].append(rc.gasUsed)
                h_ini = C.altura_max()
                envios: dict[str, tuple[int, float]] = {}  # hash -> (conta, instante do envio)
                erros: Counter = Counter()
                trava = threading.Lock()

                def rajada(k: int) -> None:
                    """Envia POR_CONTA registros sem pausa; gás estimado uma única vez por conta."""
                    wk, ack = w3_no(k), conta(k)
                    ck = wk.eth.contract(address=end, abi=ART["abi"])
                    n0 = wk.eth.get_transaction_count(ack.address, "pending")
                    preco, cadeia = wk.eth.gas_price, wk.eth.chain_id
                    gas_fixo = None
                    for i in range(POR_CONTA):
                        fn = ck.functions.registrarBoletim(eid, f"k{k:02d}-{i:03d}", os.urandom(32), os.urandom(32), 250)
                        tx = fn.build_transaction({"from": ack.address, "nonce": n0 + i, "gasPrice": preco, "chainId": cadeia,
                                                   "gas": gas_fixo or 300_000})
                        if gas_fixo is None:
                            gas_fixo = int(wk.eth.estimate_gas({k_: v for k_, v in tx.items() if k_ != "gas"}) * 1.3)
                            tx["gas"] = gas_fixo
                        bruto = ack.sign_transaction(tx).raw_transaction
                        for _ in range(30):
                            try:
                                h = wk.eth.send_raw_transaction(bruto)
                                with trava:
                                    envios[h.hex()] = (k, time.time())
                                break
                            except Exception as e:  # noqa: BLE001
                                with trava:
                                    erros[str(e)[:60]] += 1
                                time.sleep(0.2)

                t0 = time.time()
                th = [threading.Thread(target=rajada, args=(k,)) for k in range(1, C.N + 1)]
                for t in th:
                    t.start()
                for t in th:
                    t.join()
                t_envio = time.time() - t0
                # inclusão: bloco de cada transação; latência = timestamp do bloco − instante do envio (relógios NTP)
                incl: dict[str, int] = {}
                pendentes = set(envios)
                limite = time.time() + 600
                while pendentes and time.time() < limite:
                    for hx in list(pendentes):
                        try:
                            r = w3.eth.get_transaction_receipt(hx)
                        except Exception:  # noqa: BLE001
                            continue
                        if r:
                            incl[hx] = r.blockNumber
                            gas["registrar"].append(r.gasUsed)
                            pendentes.discard(hx)
                    time.sleep(1)
                blocos = Counter(incl.values())
                ts_blocos = {b: int(C.bloco(b)["timestamp"], 16) for b in blocos}
                lat = [ts_blocos[incl[h]] - envios[h][1] for h in incl]
                ultimo_ts = max(ts_blocos.values()) if ts_blocos else None
                dur_cadeia = (max(ts_blocos.values()) - min(ts_blocos.values()) + 2) if ts_blocos else None
                vazios = sum(1 for b in range(min(blocos), max(blocos) + 1) if b not in blocos) if blocos else 0
                r = {"rep": rep, "transacoes_enviadas": len(envios), "incluidas": len(incl), "nao_incluidas": len(pendentes),
                     "tempo_envio_s": round(t_envio, 1), "taxa_oferecida_tx_s": round(len(envios) / t_envio, 1),
                     "tempo_ate_ultimo_bloco_s": round(ultimo_ts - t0, 1) if ultimo_ts else None,
                     "tx_por_s_fim_a_fim": round(len(incl) / (ultimo_ts - t0), 1) if ultimo_ts else None,
                     "blocos_usados": len(blocos), "blocos_vazios_no_intervalo": vazios,
                     "tx_por_bloco": resumo(list(blocos.values()), 1),
                     "tx_por_s_na_cadeia": round(len(incl) / dur_cadeia, 1) if dur_cadeia else None,
                     "latencia_inclusao_s": resumo(lat, 2), "altura_inicio": h_ini, "erros_envio": dict(erros)}
                ok = w3.eth.contract(address=end, abi=ART["abi"]).functions.eleicao(eid).call()
                r["secoes_registradas_no_contrato"] = ok[4]
                rr = w3.eth.wait_for_transaction_receipt(enviar(w3, ac1, c1.functions.encerrar(eid, os.urandom(32))), timeout=180)
                gas["encerrar"].append(rr.gasUsed)
                reps.append(r)
                print(json.dumps(r, ensure_ascii=False), flush=True)
                gravar("e9-capacidade", {"parcial": True, "repeticoes": reps})
                C.esperar_saudavel()
    finally:
        am.parar()
    gas_res = {"implantar": gas["implantar"], "criar_eleicao_12_apuradores": resumo(gas["criar"], 0),
               "registrar_boletim": resumo(gas["registrar"], 0), "encerrar": resumo(gas["encerrar"], 0)}
    print("->", gravar("e9-capacidade", {"metodo": f"12 contas × {POR_CONTA} registros por repetição, cada conta pelo próprio nó, sem pausa, gás estimado uma vez por conta; latência = timestamp do bloco − envio; {REPS} repetições; contrato novo implantado no início",
                                          "contrato": end, "gas": gas_res, "repeticoes": reps}))


if __name__ == "__main__":
    main()
