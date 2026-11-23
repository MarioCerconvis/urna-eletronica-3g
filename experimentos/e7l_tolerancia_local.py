"""E7L — Vazão da rede LOCAL de 4 validadores (ambiente B, quórum 3) com 0, 1 e 2 validadores parados.

Mesmo procedimento do E7, na rede Docker local de `deploy/blockchain/besu/rede-local.sh` (contêineres besu-node1..4,
RPC em 127.0.0.1:8545..8548): 5 repetições por cenário, janela de 120 s, rede saudável antes de cada repetição.
Nós parados fixos, como no simular.sh: 1 fora = node4; 2 fora = node3 e node4. Com 2 fora a rede para (sem quórum);
depois de cada janela desse cenário a rede é reiniciada por inteiro (os 4 nós parados e religados juntos), para não
esperar a troca de rodada com espera dobrada, que é medida à parte no E8.

Antes de rodar: deploy/blockchain/besu/rede-local.sh subir
"""

from __future__ import annotations

import json
import subprocess
import time

import httpx
from comum import gravar, resumo

N, REPS, JANELA = 4, 5, 120
CENARIOS = {0: [], 1: [4], 2: [3, 4]}
METODO = (f"rede local de {N} validadores (Docker, um contêiner por nó); {REPS} repetições por cenário, janela "
          f"{JANELA} s; 1 fora = node4, 2 fora = node3 e node4; reinício completo da rede depois de cada janela sem "
          "quórum; rede saudável (4 nós sincronizados, 3 pares cada, produzindo) antes de cada repetição")
_cli = httpx.Client(timeout=2.5)


def rpc(k: int, metodo: str, params: list | None = None):  # noqa: ANN201
    r = _cli.post(f"http://127.0.0.1:{8544 + k}",
                  json={"jsonrpc": "2.0", "method": metodo, "params": params or [], "id": 1}).json()
    if "error" in r:
        raise RuntimeError(r["error"].get("message"))
    return r["result"]


def altura(k: int) -> int | None:
    try:
        return int(rpc(k, "eth_blockNumber"), 16)
    except Exception:  # noqa: BLE001
        return None


def altura_max() -> int:
    return max((h for k in range(1, N + 1) if (h := altura(k)) is not None), default=-1)


def timestamps(de: int, ate: int) -> list[int]:
    saida = []
    for n in range(de, ate + 1):
        for k in range(1, N + 1):
            try:
                b = rpc(k, "eth_getBlockByNumber", [hex(n), False])
                if b:
                    saida.append(int(b["timestamp"], 16))
                    break
            except Exception:  # noqa: BLE001, S112
                continue
    return saida


def docker(acao: str, nos: list[int]) -> None:
    if nos:
        args = ["docker", "stop", "-t", "2"] if acao == "parar" else ["docker", "start"]
        subprocess.run([*args, *[f"besu-node{k}" for k in nos]], capture_output=True, check=False, timeout=120)


def saudavel() -> bool:
    hs = [altura(k) for k in range(1, N + 1)]
    if any(h is None for h in hs) or max(hs) - min(hs) > 2:  # type: ignore[type-var]
        return False
    try:
        return all(len(rpc(k, "admin_peers")) >= N - 1 for k in range(1, N + 1))
    except Exception:  # noqa: BLE001
        return False


def esperar_saudavel(timeout: float = 900) -> float:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if saudavel():
            h0 = altura_max()
            time.sleep(6)
            if altura_max() > h0:
                return time.time() - t0
        time.sleep(3)
    raise TimeoutError("rede local não ficou saudável a tempo")


def main() -> None:
    execs = []
    esperar_saudavel()
    for k, fora in CENARIOS.items():
        for rep in range(1, REPS + 1):
            docker("parar", fora)
            time.sleep(5)
            h0, t0 = altura_max(), time.time()
            time.sleep(JANELA)
            h1, t1 = altura_max(), time.time()
            ts = timestamps(h0, h1) if h1 > h0 else []
            inter = [b - a for a, b in zip(ts, ts[1:], strict=False)]
            r = {"k_fora": k, "rep": rep, "fora": [f"node{n}" for n in fora], "blocos": h1 - h0,
                 "janela_s": round(t1 - t0, 1), "blocos_por_120s": round((h1 - h0) * 120 / (t1 - t0), 2),
                 "maior_intervalo_s": max(inter) if inter else None, "intervalos_s": inter}
            if k >= N - (2 * N + 2) // 3 + 1:  # sem quórum: reinício completo
                docker("parar", [n for n in range(1, N + 1) if n not in fora])
                docker("ligar", list(range(1, N + 1)))
            else:
                docker("ligar", fora)
            r["tempo_ate_saudavel_s"] = round(esperar_saudavel(), 1)
            execs.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            gravar("e7l-tolerancia-local", {"metodo": METODO, "parcial": True, "execucoes": execs})
    por_k = {str(k): {"fora": [f"node{n}" for n in fora],
                      "blocos": resumo([e["blocos"] for e in execs if e["k_fora"] == k], 2),
                      "blocos_por_120s": resumo([e["blocos_por_120s"] for e in execs if e["k_fora"] == k], 2),
                      "maior_intervalo_s": resumo([e["maior_intervalo_s"] for e in execs
                                                   if e["k_fora"] == k and e["maior_intervalo_s"]], 1)}
             for k, fora in CENARIOS.items()}
    print("->", gravar("e7l-tolerancia-local", {"metodo": METODO, "validadores": N, "quorum": (2 * N + 2) // 3,
                                                "por_k": por_k, "execucoes": execs}))


if __name__ == "__main__":
    main()
