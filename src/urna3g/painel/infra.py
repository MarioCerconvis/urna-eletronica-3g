"""Acesso à infraestrutura: túneis SSH, estatísticas das máquinas e ligar/desligar nós."""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass

from urna3g.painel.config import NoCfg, PainelCfg

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=10",
            "-o", "ServerAliveCountMax=3"]


@dataclass
class StatsMaquina:
    carga: float | None = None        # load average 1 min
    nucleos: int | None = None
    mem_usada: float | None = None    # GB
    mem_total: float | None = None    # GB
    besu_mem: str | None = None       # "290MiB"
    besu_estado: str | None = None    # running/exited/ausente


async def _rodar(*cmd: str, timeout: float = 30) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "tempo esgotado"
    return proc.returncode or 0, out.decode(errors="replace")


class Tunel:
    """Um único processo ssh -N com um -L por nó; reinicia sozinho se cair."""

    def __init__(self, cfg: PainelCfg):
        self.cfg = cfg
        self.proc: asyncio.subprocess.Process | None = None
        self.ativo = False
        self.ultimo_erro = ""

    def _args(self) -> list[str]:
        args = ["ssh", "-N", *SSH_OPTS, "-o", "ExitOnForwardFailure=yes"]
        for no in self.cfg.nos:
            porta = no.rpc.rsplit(":", 1)[-1]
            args += ["-L", f"127.0.0.1:{porta}:{no.ip}:8545"]
        args.append(self.cfg.ponte or "")
        return args

    async def manter(self, ao_mudar) -> None:  # noqa: ANN001
        while True:
            self.proc = await asyncio.create_subprocess_exec(
                *self._args(), stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
            )
            await asyncio.sleep(2)
            if self.proc.returncode is None:
                self.ativo = True
                await ao_mudar(True, "")
                await self.proc.wait()
            err = (await self.proc.stderr.read()).decode(errors="replace").strip() if self.proc.stderr else ""
            self.ativo = False
            self.ultimo_erro = err.splitlines()[-1] if err else f"ssh saiu com código {self.proc.returncode}"
            await ao_mudar(False, self.ultimo_erro)
            await asyncio.sleep(5)

    def encerrar(self) -> None:
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()


_SCRIPT_STATS = r"""
for ip in {ips}; do
  ( s=$(ssh -o BatchMode=yes -o ConnectTimeout=4 {usuario}@$ip '
      read l1 _ < /proc/loadavg; n=$(nproc)
      mt=$(awk "/MemTotal/{{print \$2}}" /proc/meminfo); ma=$(awk "/MemAvailable/{{print \$2}}" /proc/meminfo)
      st=$(docker inspect -f "{{{{.State.Status}}}}" besu 2>/dev/null || echo ausente)
      bm=$(docker stats --no-stream --format "{{{{.MemUsage}}}}" besu 2>/dev/null | cut -d/ -f1 | tr -d " ")
      echo "$l1|$n|$mt|$ma|$st|$bm"' 2>/dev/null) && echo "$ip|$s" || echo "$ip|ERRO" ) &
done; wait
"""


def _parse_stats(linha: str) -> tuple[str, StatsMaquina]:
    partes = linha.strip().split("|")
    ip = partes[0]
    if len(partes) < 7:
        return ip, StatsMaquina(besu_estado="sem acesso")
    l1, n, mt, ma, st, bm = partes[1:7]
    try:
        return ip, StatsMaquina(
            carga=float(l1), nucleos=int(n), mem_total=int(mt) / 1048576, mem_usada=(int(mt) - int(ma)) / 1048576,
            besu_estado=st, besu_mem=bm or None,
        )
    except ValueError:
        return ip, StatsMaquina(besu_estado=st or "?")


async def coletar_stats(cfg: PainelCfg) -> dict[str, StatsMaquina]:
    if cfg.modo == "cluster":
        script = _SCRIPT_STATS.format(ips=" ".join(n.ip for n in cfg.nos), usuario=cfg.usuario_nos)
        if cfg.ponte:
            rc, out = await _rodar("ssh", *SSH_OPTS, cfg.ponte, script, timeout=40)
        else:
            rc, out = await _rodar("bash", "-c", script, timeout=40)
        por_ip = dict(_parse_stats(ln) for ln in out.splitlines() if ln.count("|") >= 1)
        return {n.id: por_ip.get(n.ip, StatsMaquina(besu_estado="sem resposta")) for n in cfg.nos}
    # local: os "nós" são contêineres nesta máquina
    rc, out = await _rodar("docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.MemUsage}}", timeout=20)
    mem = {ln.split("|")[0]: ln.split("|")[1].split("/")[0].strip() for ln in out.splitlines() if "|" in ln}
    rc2, st = await _rodar("docker", "ps", "-a", "--format", "{{.Names}}|{{.State}}", timeout=10)
    estados = {ln.split("|")[0]: ln.split("|")[1] for ln in st.splitlines() if "|" in ln}
    with open("/proc/loadavg") as f:
        carga = float(f.read().split()[0])
    import os

    return {
        n.id: StatsMaquina(carga=carga, nucleos=os.cpu_count(), besu_mem=mem.get(f"besu-{n.id}"),
                           besu_estado=estados.get(f"besu-{n.id}", "ausente"))
        for n in cfg.nos
    }


async def acao_no(cfg: PainelCfg, no: NoCfg, acao: str) -> tuple[bool, str]:
    """acao ∈ {derrubar, religar}: para/inicia o contêiner Besu da máquina (reversível)."""
    docker = "docker stop -t 2 besu" if acao == "derrubar" else "docker start besu"
    if cfg.modo == "cluster":
        remoto = f"ssh -o BatchMode=yes -o ConnectTimeout=5 {cfg.usuario_nos}@{no.ip} {shlex.quote(docker)}"
        if cfg.ponte:
            rc, out = await _rodar("ssh", *SSH_OPTS, cfg.ponte, remoto, timeout=40)
        else:
            rc, out = await _rodar("bash", "-c", remoto, timeout=40)
    else:
        nome = f"besu-{no.id}"
        rc, out = await _rodar("docker", "stop" if acao == "derrubar" else "start", nome, timeout=40)
    return rc == 0, out.strip()[-300:]
