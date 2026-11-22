"""E7 — Vazão com k validadores fora (k = 0..4 de 12; quórum 8), 5 repetições por k, nós sorteados, janela de 120 s.

A vazão no limite depende de QUAIS nós caem (ordem de rodízio do proponente), por isso cada repetição sorteia um
conjunto diferente. Os intervalos entre blocos vêm dos timestamps dos blocos produzidos na janela.
"""

from __future__ import annotations

import json
import random
import time

import cluster as C
from comum import RESULTADOS, gravar, resumo

REPS, JANELA = 5, 120
rng = random.Random(77)


def main() -> None:
    amostras = RESULTADOS / "e12-recursos.jsonl"
    am = C.Amostrador(amostras)
    am.start()
    anterior = RESULTADOS / "e7-tolerancia.json"
    execs = json.loads(anterior.read_text()).get("execucoes", []) if anterior.is_file() else []
    feitas = {(e["k_fora"], e["rep"]) for e in execs}
    if feitas:
        print(f"retomando: {len(feitas)} repetições já concluídas", flush=True)
    try:
        with C.Tunel():
            C.esperar_saudavel()
            for k in range(0, 5):
                for rep in range(1, REPS + 1):
                    fora = C.sorteio(rng, k)  # sorteia sempre, para manter a mesma sequência ao retomar
                    if (k, rep) in feitas:
                        continue
                    am.rotulo = f"e7_k{k}_r{rep}"
                    if fora:
                        C.parar(fora)
                    time.sleep(5)
                    h0, t0 = C.altura_max(), time.time()
                    time.sleep(JANELA)
                    h1, t1 = C.altura_max(), time.time()
                    ts = C.timestamps(h0, h1) if h1 > h0 else []
                    inter = [b - a for a, b in zip(ts, ts[1:], strict=False)]
                    r = {"k_fora": k, "rep": rep, "fora": [C.ROT[i] for i in fora], "blocos": h1 - h0,
                         "janela_s": round(t1 - t0, 1), "blocos_por_min": round((h1 - h0) * 60 / (t1 - t0), 2),
                         "maior_intervalo_s": max(inter) if inter else None,
                         "intervalo_medio_s": round(sum(inter) / len(inter), 2) if inter else None}
                    if fora:
                        C.ligar(fora)
                    r["tempo_ate_saudavel_s"] = round(C.esperar_saudavel(), 1)
                    execs.append(r)
                    print(json.dumps(r, ensure_ascii=False), flush=True)
                    gravar("e7-tolerancia", {"metodo": f"{REPS} repetições por k, janela {JANELA} s, nós sorteados (semente 77), rede saudável antes de cada repetição", "parcial": True, "execucoes": execs})
    finally:
        am.parar()
    por_k = {}
    for k in range(0, 5):
        rs = [e for e in execs if e["k_fora"] == k]
        por_k[str(k)] = {"blocos_por_min": resumo([e["blocos_por_min"] for e in rs], 2),
                         "maior_intervalo_s": resumo([e["maior_intervalo_s"] for e in rs if e["maior_intervalo_s"]], 1),
                         "produziu_em_todas": all(e["blocos"] > 0 for e in rs)}
    print("->", gravar("e7-tolerancia", {"metodo": f"{REPS} repetições por k, janela {JANELA} s, nós sorteados (semente 77), rede saudável antes de cada repetição",
                                          "validadores": C.N, "quorum": C.QUORUM, "por_k": por_k, "execucoes": execs}))


if __name__ == "__main__":
    main()
