"""E8 — Tempo de recuperação após perda de quórum, em função da duração da parada.

Para cada duração d ∈ {10, 30, 60, 120} s: derruba 5 de 12 (sorteados; sobram 7 < quórum 8), espera d, religa UM
deles (volta a 8) e mede (a) quando o RPC do nó religado responde e (b) quando sai o próximo bloco.
Repetições: 5, 5, 5, 3 (a de 120 s é a mais longa).
"""

from __future__ import annotations

import json
import random
import time

import cluster as C
from comum import RESULTADOS, gravar, resumo

PLANO = [(10, 5), (30, 5), (60, 5), (120, 3)]
rng = random.Random(88)


def main() -> None:
    am = C.Amostrador(RESULTADOS / "e12-recursos.jsonl")
    am.start()
    execs = []
    try:
        with C.Tunel():
            C.esperar_saudavel()
            for d, reps in PLANO:
                for rep in range(1, reps + 1):
                    am.rotulo = f"e8_d{d}_r{rep}"
                    fora = C.sorteio(rng, 5)
                    C.parar(fora)
                    h_parada = C.altura_max()
                    time.sleep(d)
                    volta = fora[0]
                    k_volta = C.IPS.index(volta) + 1
                    t0 = time.time()
                    C.ligar([volta])
                    t_rpc = t_bloco = None
                    while time.time() - t0 < 900:
                        if t_rpc is None and C.altura(k_volta) is not None:
                            t_rpc = time.time() - t0
                        if C.altura_max() > h_parada + 0 and _novo_bloco(h_parada):
                            t_bloco = time.time() - t0
                            break
                        time.sleep(1)
                    C.ligar(fora[1:])
                    saude = C.esperar_saudavel()
                    r = {"parada_s": d, "rep": rep, "fora": [C.ROT[i] for i in fora], "religado": C.ROT[volta],
                         "rpc_religado_s": round(t_rpc, 1) if t_rpc else None,
                         "proximo_bloco_s": round(t_bloco, 1) if t_bloco else None,
                         "ate_saudavel_s": round(saude, 1)}
                    execs.append(r)
                    print(json.dumps(r, ensure_ascii=False), flush=True)
                    gravar("e8-recuperacao", {"parcial": True, "execucoes": execs})
    finally:
        am.parar()
    por_d = {str(d): {"proximo_bloco_s": resumo([e["proximo_bloco_s"] for e in execs if e["parada_s"] == d], 1),
                      "rpc_religado_s": resumo([e["rpc_religado_s"] for e in execs if e["parada_s"] == d], 1)}
             for d, _ in PLANO}
    print("->", gravar("e8-recuperacao", {"metodo": "5 de 12 parados (sem quórum) por d segundos; religar 1; medir RPC do religado e o próximo bloco; nós sorteados (semente 88)",
                                           "plano": PLANO, "por_duracao": por_d, "execucoes": execs}))


def _novo_bloco(h_parada: int) -> bool:
    return C.altura_max() > h_parada


if __name__ == "__main__":
    main()
