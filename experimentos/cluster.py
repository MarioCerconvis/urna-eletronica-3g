"""Infraestrutura dos experimentos no cluster: túnel RPC, ligar/desligar nós, espera de saúde e amostrador de recursos.

Três modos, escolhidos pelo arquivo de configuração (variável URNA3G_PAINEL_CFG):
- cluster via ponte ("ponte": "usuario@host"): roda na estação do operador e alcança os nós por SSH através da
  máquina-ponte, com túnel nas portas locais 19300+K (separadas das do painel, 19100+K);
- cluster direto ("ponte": null): roda numa máquina da mesma rede dos nós (ex.: o computador principal do cluster);
- local ("modo": "local"): rede de contêineres Besu nesta máquina, criada por deploy/blockchain/besu/gerar-rede.sh N e
  rede-local.sh subir (contêineres besu-nodeK, RPC em 127.0.0.1:8544+K). Permite replicar os experimentos do cluster
  num único computador (ver exemplos/experimentos-local.json).
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx

CFG_PATH = Path(os.environ.get("URNA3G_PAINEL_CFG", Path.home() / "Desktop/UFABC/cluster-rede-12/painel.json"))
CFG = json.loads(CFG_PATH.read_text())
LOCAL = CFG.get("modo") == "local"  # contêineres nesta máquina (rede-local.sh)
DIRETO = not CFG.get("ponte")  # rodando no computador principal (ou local): fala direto com os nós
PONTE = CFG.get("ponte")
USUARIO = CFG.get("usuario_nos", "laob")
REDE = Path(CFG["rede_dir"]).expanduser()
if not REDE.is_absolute():
    REDE = (CFG_PATH.parent / REDE).resolve()
VALIDADORES = [ln.split() for ln in (REDE / "validadores.txt").read_text().splitlines() if ln.strip()]
# no modo local, os "IPs" são os da rede Docker de rede-local.sh (só servem de rótulo e para o sorteio)
IPS: list[str] = CFG.get("ips") or [f"172.28.0.{10 + k}" for k in range(1, len(VALIDADORES) + 1)]
N = len(IPS)
QUORUM = (2 * N + 2) // 3
PORTA = int(__import__("os").environ.get("URNA3G_PORTA", "19300"))
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=10"]
ROT = {ip: "." + ip.rsplit(".", 1)[1] for ip in IPS}


def url(k: int) -> str:  # k = 1..N
    if LOCAL:
        return f"http://127.0.0.1:{8544 + k}"
    return f"http://{IPS[k - 1]}:8545" if DIRETO else f"http://127.0.0.1:{PORTA + k}"


def conteiner(ip: str) -> str:  # modo local: nome do contêiner do nó
    return f"besu-node{IPS.index(ip) + 1}"


class Tunel:
    def __enter__(self) -> Tunel:
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
    if LOCAL:
        args = ["docker", "stop", "-t", "2"] if acao == "parar" else ["docker", "start"]
        subprocess.run([*args, *[conteiner(ip) for ip in ips]], capture_output=True, check=False, timeout=180)
        return
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
        if LOCAL:
            subprocess.run(["docker", "start", conteiner(ip)], capture_output=True, check=False, timeout=120)
        else:
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
        if LOCAL:
            self._run_local()
            return
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

    def _run_local(self) -> None:
        nomes = {conteiner(ip): ip for ip in IPS}
        while not self._parar.is_set():
            try:
                saida = subprocess.run(["docker", "stats", "--no-stream", "--format",
                                        "{{.Name}}|{{.MemUsage}}|{{.CPUPerc}}", *nomes],
                                       capture_output=True, text=True, timeout=60, check=False).stdout
                ts = time.time()
                with self.destino.open("a") as f:
                    for ln in saida.splitlines():
                        partes = ln.split("|")
                        if len(partes) >= 3 and partes[0] in nomes:
                            f.write(json.dumps({"ts": ts, "rotulo": self.rotulo, "ip": nomes[partes[0]],
                                                "mem": partes[1].split("/")[0].strip(), "cpu": partes[2].strip()}) + "\n")
            except Exception:  # noqa: BLE001
                pass
            self._parar.wait(self.intervalo)

    def parar(self) -> None:
        self._parar.set()
