"""E11 — Convergência após reinício completo dos 12 nós: 5 reinícios escalonados (um por vez, como na implantação)
e 5 simultâneos. Mede: tempo até todos responderem, até o primeiro bloco novo e até a malha completa (11 pares)."""

from __future__ import annotations

import json
import time

import cluster as C
from comum import RESULTADOS, gravar, resumo

REPS = 5


def uma(modo: str, rep: int) -> dict:
    C.esperar_saudavel()
    C.parar(C.IPS)
    time.sleep(3)
    h_antes = max((h for h in C.alturas().values() if h is not None), default=None)
    if modo == "escalonado":
        tempos = C.ligar_sequencial(C.IPS)
        t0, espalhamento = tempos[-1], tempos[-1] - tempos[0]
    else:
        a = time.time()
        C.ligar(C.IPS)
        t0, espalhamento = time.time(), time.time() - a
    h_ref = None
    t_todos = t_bloco = t_malha = None
    while time.time() - t0 < 900:
        hs = C.alturas()
        if t_todos is None and all(h is not None for h in hs.values()):
            t_todos = time.time() - t0
            h_ref = max(hs.values())  # type: ignore[type-var]
        if h_ref is not None and t_bloco is None and max(h for h in hs.values() if h is not None) > h_ref:
            t_bloco = time.time() - t0
        if t_todos is not None and t_malha is None and all((C.pares(k) or 0) >= C.N - 1 for k in range(1, C.N + 1)):
            t_malha = time.time() - t0
        if t_bloco is not None and t_malha is not None:
            break
        time.sleep(2)
    return {"modo": modo, "rep": rep, "espalhamento_starts_s": round(espalhamento, 1), "altura_antes": h_antes,
            "todos_respondem_s": round(t_todos, 1) if t_todos else None,
            "primeiro_bloco_s": round(t_bloco, 1) if t_bloco else None,
            "malha_completa_s": round(t_malha, 1) if t_malha else None}


def main() -> None:
    am = C.Amostrador(RESULTADOS / "e12-recursos.jsonl")
    am.start()
    execs = []
    try:
        with C.Tunel():
            for modo in ("escalonado", "simultaneo"):
                for rep in range(1, REPS + 1):
                    am.rotulo = f"e11_{modo}_r{rep}"
                    r = uma(modo, rep)
                    execs.append(r)
                    print(json.dumps(r, ensure_ascii=False), flush=True)
                    gravar("e11-reinicio", {"parcial": True, "execucoes": execs})
            C.esperar_saudavel()
    finally:
        am.parar()
    por_modo = {m: {c: resumo([e[c] for e in execs if e["modo"] == m and e[c] is not None], 1)
                    for c in ("todos_respondem_s", "primeiro_bloco_s", "malha_completa_s", "espalhamento_starts_s")}
                for m in ("escalonado", "simultaneo")}
    print("->", gravar("e11-reinicio", {"metodo": f"{REPS} reinícios por modo; tempos contados a partir do último start", "por_modo": por_modo, "execucoes": execs}))


if __name__ == "__main__":
    main()
