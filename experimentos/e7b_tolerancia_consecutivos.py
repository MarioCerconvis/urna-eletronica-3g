"""E7b — Vazão com 3 e 4 validadores CONSECUTIVOS na ordem de rodízio parados (12 validadores, quórum 8).

Complementa o E7, que sorteou os conjuntos de nós parados: aqui os conjuntos são fixos e consecutivos na ordem de
rodízio do proponente (.101 → .113), como pede o protocolo da Tabela de falhas do manuscrito
(medicoes-pendentes.md §2): 3 fora = .111 .112 .113; 4 fora = .110 .111 .112 .113. É o pior caso para a vazão,
porque cada volta do rodízio acumula 3 ou 4 trocas de rodada seguidas, com a espera dobrando a cada uma.
5 repetições por conjunto, janela de 120 s, rede saudável antes de cada repetição (mesmo procedimento do E7).
Grava todos os intervalos entre blocos da janela, a partir dos timestamps dos blocos.
"""

from __future__ import annotations

import json
import time

import cluster as C
from comum import RESULTADOS, gravar, resumo

REPS, JANELA = 5, 120
# os últimos k nós da lista são consecutivos no rodízio (nodeK segue a ordem dos endereços, que é a do rodízio);
# no cluster: 3 fora = .111 .112 .113 e 4 fora = .110 .111 .112 .113
CONJUNTOS = {3: C.IPS[-3:], 4: C.IPS[-4:]}
METODO = (f"{REPS} repetições por conjunto, janela {JANELA} s, nós consecutivos na ordem de rodízio "
          "(3 fora = .111–.113; 4 fora = .110–.113), rede saudável antes de cada repetição")


def main() -> None:
    anterior = RESULTADOS / "e7b-tolerancia-consecutivos.json"
    execs = json.loads(anterior.read_text()).get("execucoes", []) if anterior.is_file() else []
    feitas = {(e["k_fora"], e["rep"]) for e in execs}
    with C.Tunel():
        C.esperar_saudavel()
        for k, fora in CONJUNTOS.items():
            for rep in range(1, REPS + 1):
                if (k, rep) in feitas:
                    continue
                C.parar(fora)
                time.sleep(5)
                h0, t0 = C.altura_max(), time.time()
                time.sleep(JANELA)
                h1, t1 = C.altura_max(), time.time()
                ts = C.timestamps(h0, h1) if h1 > h0 else []
                inter = [b - a for a, b in zip(ts, ts[1:], strict=False)]
                r = {"k_fora": k, "rep": rep, "fora": [C.ROT[ip] for ip in fora], "blocos": h1 - h0,
                     "janela_s": round(t1 - t0, 1), "blocos_por_120s": round((h1 - h0) * 120 / (t1 - t0), 2),
                     "blocos_por_min": round((h1 - h0) * 60 / (t1 - t0), 2),
                     "maior_intervalo_s": max(inter) if inter else None, "intervalos_s": inter}
                C.ligar(fora)
                r["tempo_ate_saudavel_s"] = round(C.esperar_saudavel(), 1)
                execs.append(r)
                print(json.dumps(r, ensure_ascii=False), flush=True)
                gravar("e7b-tolerancia-consecutivos", {"metodo": METODO, "parcial": True, "execucoes": execs})
    por_k = {}
    for k in CONJUNTOS:
        rs = [e for e in execs if e["k_fora"] == k]
        por_k[str(k)] = {"fora": rs[0]["fora"] if rs else [],
                         "blocos": resumo([e["blocos"] for e in rs], 2),
                         "blocos_por_120s": resumo([e["blocos_por_120s"] for e in rs], 2),
                         "maior_intervalo_s": resumo([e["maior_intervalo_s"] for e in rs if e["maior_intervalo_s"]], 1),
                         "produziu_em_todas": all(e["blocos"] > 0 for e in rs)}
    print("->", gravar("e7b-tolerancia-consecutivos", {"metodo": METODO, "validadores": C.N, "quorum": C.QUORUM,
                                                       "por_k": por_k, "execucoes": execs}))


if __name__ == "__main__":
    main()
