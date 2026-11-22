"""Infraestrutura dos experimentos no cluster: túnel RPC, ligar/desligar nós, espera de saúde e amostrador de recursos.

Roda neste computador; alcança os nós por SSH através da máquina-ponte (computador principal do cluster).
Portas locais 19300+K (separadas das do painel, 19100+K).
"""

from __future__ import annotations

import json
import random
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx

import os

CFG_PATH = Path(os.environ.get("URNA3G_PAINEL_CFG", Path.home() / "Desktop/UFABC/cluster-rede-12/painel.json"))
CFG = json.loads(CFG_PATH.read_text())
DIRETO = not CFG.get("ponte")  # rodando no computador principal: fala direto com os nós
PONTE = CFG.get("ponte")
USUARIO = CFG.get("usuario_nos", "laob")
IPS: list[str] = CFG["ips"]
REDE = Path(CFG["rede_dir"]).expanduser()
VALIDADORES = [ln.split() for ln in (REDE / "validadores.txt").read_text().splitlines() if ln.strip()]
N = len(IPS)
QUORUM = (2 * N + 2) // 3
PORTA = int(__import__("os").environ.get("URNA3G_PORTA", "19300"))
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=10"]
ROT = {ip: "." + ip.rsplit(".", 1)[1] for ip in IPS}


def url(k: int) -> str:  # k = 1..N
    return f"http://{IPS[k - 1]}:8545" if DIRETO else f"http://127.0.0.1:{PORTA + k}"


class Tunel:
    def __enter__(self) -> "Tunel":
        if DIRETO:
            self.p = None
            return self
        args = [*SSH, "-N", "-o", "ExitOnForwardFailure=yes"]
        for k, ip in enumerate(IPS, start=1):
            args += ["-L", f"127.0.0.1:{PORTA + k}:{ip}:8545"]
        self.p = subprocess.Popen([*args, PONTE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        if self.p.poll() is not None:
            raise RuntimeError("túnel SSH não subiu")
        return self

    def __exit__(self, *a: object) -> None:
        if self.p:
            self.p.terminate()


_cli = httpx.Client(timeout=2.5)


def rpc(k: int, metodo: str, params: list | None = None) -> Any:
    r = _cli.post(url(k), json={"jsonrpc": "2.0", "method": metodo, "params": params or [], "id": 1}).json()
    if "error" in r:
        raise RuntimeError(r["error"].get("message"))
    return r["result"]


def altura(k: int) -> int | None:
    try:
        return int(rpc(k, "eth_blockNumber"), 16)
    except Exception:  # noqa: BLE001
        return None


def alturas() -> dict[int, int | None]:
    return {k: altura(k) for k in range(1, N + 1)}


def altura_max() -> int:
    return max((h for h in alturas().values() if h is not None), default=-1)


def bloco(num: int) -> dict:
    for k in range(1, N + 1):
        try:
            b = rpc(k, "eth_getBlockByNumber", [hex(num), False])
            if b:
                return b
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError(f"bloco {num} indisponível")


def timestamps(de: int, ate: int) -> list[int]:
    return [int(bloco(n)["timestamp"], 16) for n in range(de, ate + 1)]


def ssh_ponte(cmd: str, timeout: float = 120) -> str:
    """Executa `cmd` na ponte (ou localmente, no modo direto)."""
    argv = ["bash", "-c", cmd] if DIRETO else [*SSH, PONTE, cmd]
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    return r.stdout


def _docker_em(ips: list[str], acao: str) -> None:
    cmd = "docker stop -t 2 besu" if acao == "parar" else "docker start besu"
    laco = " ".join(f"( ssh -o BatchMode=yes -o ConnectTimeout=5 {USUARIO}@{ip} '{cmd}' >/dev/null 2>&1 ) &" for ip in ips)
    ssh_ponte(f"{laco} wait")


def parar(ips: list[str]) -> None:
    _docker_em(ips, "parar")


def ligar(ips: list[str]) -> None:
    _docker_em(ips, "ligar")


def ligar_sequencial(ips: list[str]) -> list[float]:
    """Liga um por vez (como o implantar-cluster.sh); devolve o instante de cada start."""
    t = []
    for ip in ips:
        ssh_ponte(f"ssh -o BatchMode=yes {USUARIO}@{ip} 'docker start besu' >/dev/null 2>&1")
        t.append(time.time())
    return t


def pares(k: int) -> int | None:
    try:
        return len(rpc(k, "admin_peers"))
    except Exception:  # noqa: BLE001
        return None


def saudavel(min_pares: int = 1) -> bool:
    hs = alturas()
    if any(h is None for h in hs.values()):
        return False
    if max(hs.values()) - min(hs.values()) > 2:  # type: ignore[type-var]
        return False
    return all((pares(k) or 0) >= min_pares for k in range(1, N + 1))


def esperar_saudavel(timeout: float = 900, produzindo: bool = True) -> float:
    """Espera todos responderem, sincronizados e (opcional) produzindo. Devolve o tempo gasto."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if saudavel():
            if not produzindo:
                return time.time() - t0
            h0 = altura_max()
            time.sleep(6)
            if altura_max() > h0:
                return time.time() - t0
        time.sleep(3)
    raise TimeoutError("rede não ficou saudável a tempo")


def sorteio(rng: random.Random, k: int) -> list[str]:
    return rng.sample(IPS, k)


class Amostrador(threading.Thread):
    """A cada `intervalo` s grava memória e CPU do contêiner Besu de cada nó (docker stats)."""

    def __init__(self, destino: Path, intervalo: float = 60):
        super().__init__(daemon=True)
        self.destino, self.intervalo, self.rotulo, self._parar = destino, intervalo, "inicio", threading.Event()

    def run(self) -> None:
        laco = " ".join(
            f"( echo \"{ip}|$(ssh -o BatchMode=yes -o ConnectTimeout=5 {USUARIO}@{ip} "
            f"'docker stats --no-stream --format \"{{{{.MemUsage}}}}|{{{{.CPUPerc}}}}\" besu 2>/dev/null')\" ) &"
            for ip in IPS)
        while not self._parar.is_set():
            try:
                saida = ssh_ponte(f"{laco} wait", timeout=60)
                ts = time.time()
                with self.destino.open("a") as f:
                    for ln in saida.splitlines():
                        partes = ln.split("|")
                        if len(partes) >= 3 and partes[1]:
                            f.write(json.dumps({"ts": ts, "rotulo": self.rotulo, "ip": partes[0],
                                                "mem": partes[1].split("/")[0].strip(), "cpu": partes[2].strip()}) + "\n")
            except Exception:  # noqa: BLE001
                pass
            self._parar.wait(self.intervalo)

    def parar(self) -> None:
        self._parar.set()
