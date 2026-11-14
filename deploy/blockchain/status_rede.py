#!/usr/bin/env python3
"""Estado da rede Besu como grafo: quem está conectado a quem, altura de bloco e validadores.

    python status_rede.py                        # rede local (./besu/rede, portas 8545..)
    python status_rede.py --dot > rede.dot       # Graphviz:  dot -Tsvg rede.dot -o rede.svg
    python status_rede.py --rpc http://10.10.0.31:8545 http://10.10.0.32:8545 ...   # cluster

Usa só a biblioteca padrão (urllib) e a API ADMIN/QBFT do Besu.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REDE = AQUI / "besu" / "rede"


def rpc(url: str, metodo: str, params: list | None = None):
    if not url.startswith(("http://", "https://")):
        raise SystemExit(f"URL RPC inválida: {url}")
    corpo = json.dumps({"jsonrpc": "2.0", "method": metodo, "params": params or [], "id": 1}).encode()
    req = urllib.request.Request(url, corpo, {"Content-Type": "application/json"})  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=3) as r:  # noqa: S310 — esquema validado acima
            return json.load(r).get("result")
    except (OSError, ValueError):
        return None


def nomes_locais() -> dict[str, str]:
    """enode id (chave pública sem 0x) → nodeK, a partir de ./besu/rede/nodeK/key.pub."""
    out = {}
    for d in sorted(REDE.glob("node*")):
        pub = d / "key.pub"
        if pub.is_file():
            out[pub.read_text().strip().removeprefix("0x").lower()] = d.name
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rpc", nargs="*", help="URLs RPC dos nós (padrão: nós locais em 127.0.0.1:8545..)")
    p.add_argument("--dot", action="store_true", help="imprime o grafo em formato Graphviz")
    args = p.parse_args()
    nomes = nomes_locais()
    urls = args.rpc or [f"http://127.0.0.1:{8544 + k}" for k in range(1, len(nomes) + 1)]

    nos = []
    for url in urls:
        info = rpc(url, "admin_nodeInfo") or {}
        enode_id = (info.get("id") or "").lower()
        nome = nomes.get(enode_id) or (info.get("ip") or url)
        bloco = rpc(url, "eth_blockNumber")
        pares = rpc(url, "admin_peers") or []
        ids_pares = [(pp.get("id") or "").removeprefix("0x").lower() for pp in pares]
        nos.append({"url": url, "id": enode_id, "nome": nome, "no_ar": bool(info),
                    "bloco": int(bloco, 16) if bloco else None, "pares": ids_pares})
    validadores = []
    for n in nos:
        if n["no_ar"]:
            validadores = rpc(n["url"], "qbft_getValidatorsByBlockNumber", ["latest"]) or []
            break
    por_id = {n["id"]: n["nome"] for n in nos if n["id"]}
    nome_de = lambda i: por_id.get(i) or nomes.get(i) or i[:10] + "…"  # noqa: E731

    if args.dot:
        print("graph rede_besu {\n  layout=circo; node [shape=circle, style=filled, fontname=Helvetica];")
        for n in nos:
            cor = "#9be29b" if n["no_ar"] else "#f4a3a3"
            rot = f'{n["nome"]}\\nbloco {n["bloco"] if n["bloco"] is not None else "-"}'
            print(f'  "{n["nome"]}" [label="{rot}", fillcolor="{cor}"];')
        arestas = {tuple(sorted((n["nome"], nome_de(i)))) for n in nos for i in n["pares"]}
        for a, b in sorted(arestas):
            print(f'  "{a}" -- "{b}";')
        print("}")
        return 0

    print(f"{'nó':<10}{'estado':<9}{'bloco':>7}  pares")
    for n in nos:
        estado = "no ar" if n["no_ar"] else "FORA"
        bloco = n["bloco"] if n["bloco"] is not None else "-"
        print(f"{n['nome']:<10}{estado:<9}{bloco:>7}  {', '.join(sorted(nome_de(i) for i in n['pares'])) or '-'}")
    vivos = sum(n["no_ar"] for n in nos)
    total_val = len(validadores) or len(nos)
    quorum = (2 * total_val + 2) // 3  # ⌈2n/3⌉, regra do QBFT
    blocos = {n["bloco"] for n in nos if n["bloco"] is not None}
    print(f"\nvalidadores no genesis/atual: {total_val}  ·  QBFT precisa de {quorum} para produzir blocos  ·  "
          f"no ar: {vivos}  ·  tolera {total_val - quorum} falha(s)")
    print("situação:", "PRODUZINDO" if vivos >= quorum else "PARADA (sem quórum)",
          "· nós sincronizados" if len(blocos) <= 1 else f"· alturas diferentes {sorted(blocos)} (sincronizando)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
