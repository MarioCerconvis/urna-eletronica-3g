"""Estado ao vivo do painel: nós, rede, blocos, eventos do contrato e linha do tempo."""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx
from eth_abi import decode as abi_decode
from eth_utils import keccak

from urna3g.painel import infra
from urna3g.painel.config import NoCfg, PainelCfg

SIG = {
    "EleicaoCriada": "EleicaoCriada(bytes32,address,uint256)",
    "BoletimRegistrado": "BoletimRegistrado(bytes32,string,bytes32,bytes32,uint32,address)",
    "EleicaoEncerrada": "EleicaoEncerrada(bytes32,bytes32)",
}
TOPICOS = {"0x" + keccak(text=s).hex(): nome for nome, s in SIG.items()}


@dataclass
class EstadoNo:
    id: str
    indice: int
    rotulo: str
    ip: str
    endereco: str
    estado: str = "desconhecido"      # no_ar | fora | desconhecido
    bloco: int | None = None
    pares: list[str] = field(default_factory=list)
    propostos: int = 0
    ultimo_proposto: int | None = None
    carga: float | None = None
    nucleos: int | None = None
    mem_usada: float | None = None
    mem_total: float | None = None
    besu_mem: str | None = None
    besu_estado: str | None = None
    enode: str | None = None
    falhas: int = 0                   # consultas seguidas sem resposta (2 = fora)


class Painel:
    def __init__(self, cfg: PainelCfg):
        self.cfg = cfg
        self.nos: dict[str, EstadoNo] = {
            n.id: EstadoNo(n.id, n.indice, n.rotulo, n.ip, n.endereco) for n in cfg.nos
        }
        self.cfg_por_id: dict[str, NoCfg] = {n.id: n for n in cfg.nos}
        self.por_endereco = {n.endereco: n.id for n in cfg.nos}
        self.eventos: deque[dict[str, Any]] = deque(maxlen=1000)
        self._seq = 0
        self.assinantes: set[asyncio.Queue] = set()
        self.http = httpx.AsyncClient(timeout=2.5)
        # rede
        self.altura = 0
        self.ultimo_bloco_em: float | None = None
        self.parada_desde: float | None = None
        self.blocos: deque[dict[str, Any]] = deque(maxlen=40)
        self.historico_ritmo: deque[tuple[float, int]] = deque(maxlen=400)  # (t, altura) a cada ~1 s
        self.validadores: list[str] = [n.endereco for n in cfg.nos]
        self.quorum_ok: bool | None = None
        self.tunel_ativo = cfg.modo == "local" or not cfg.ponte
        self.tunel_msg = ""
        # eleição
        self.contrato: str | None = cfg.contrato.lower() if cfg.contrato else None
        self.ultimo_bloco_logs = 0
        self.eleicao: dict[str, Any] = {"fase": "sem_eleicao", "id": None, "nome": None, "secoes": {},
                                        "resultados": {}, "total_secoes": 0, "encerrada": False}
        self.ensaio_ativo = False

    # ------------------------------------------------------------------ eventos
    def evento(self, categoria: str, texto: str, nivel: str = "info", nos: list[str] | None = None,
               dados: dict[str, Any] | None = None) -> None:
        self._seq += 1
        ev = {"t": "evento", "seq": self._seq, "ts": time.time(), "categoria": categoria, "nivel": nivel,
              "texto": texto, "nos": nos or [], "dados": dados or {}}
        self.eventos.append(ev)
        self._publicar(ev)

    def _publicar(self, msg: dict[str, Any]) -> None:
        for q in list(self.assinantes):
            if q.qsize() < 500:
                q.put_nowait(msg)

    @property
    def quorum(self) -> int:
        n = len(self.validadores) or len(self.nos)
        return (2 * n + 2) // 3

    def vivos(self) -> int:
        return sum(1 for n in self.nos.values() if n.estado == "no_ar")

    def ritmo(self, janela: float = 60) -> float | None:
        """Blocos por minuto na última janela (60 s para o indicador; 20 s para o estado da rede)."""
        if len(self.historico_ritmo) < 2:
            return None
        agora = self.historico_ritmo[-1]
        ref = next((p for p in self.historico_ritmo if agora[0] - p[0] <= janela), self.historico_ritmo[0])
        dt = agora[0] - ref[0]
        return (agora[1] - ref[1]) * 60 / dt if dt >= 5 else None

    def situacao(self) -> str:
        if not self.tunel_ativo:
            return "sem_conexao"
        if self.vivos() < self.quorum:
            return "parada"
        if self.parada_desde is not None:
            return "travada"
        r = self.ritmo(20)
        esperado = 60 / self.cfg.periodo_bloco
        if r is not None and r < 0.6 * esperado:
            return "lenta"
        return "produzindo"

    def snapshot(self) -> dict[str, Any]:
        agora = time.time()
        serie = [(round(t - agora, 1), h) for t, h in list(self.historico_ritmo)[-300:]]
        return {
            "t": "estado",
            "agora": agora,
            "modo": self.cfg.modo,
            "nome": self.cfg.nome,
            "ponte": {"host": self.cfg.ponte, "ip": self.cfg.ip_ponte, "ativo": self.tunel_ativo,
                      "msg": self.tunel_msg},
            "nos": [asdict(n) for n in self.nos.values()],
            "rede": {"altura": self.altura, "vivos": self.vivos(), "total": len(self.nos),
                     "validadores": len(self.validadores), "quorum": self.quorum, "situacao": self.situacao(),
                     "ritmo": self.ritmo(), "esperado": 60 / self.cfg.periodo_bloco,
                     "parada_ha": (agora - self.parada_desde) if self.parada_desde else None,
                     "blocos": list(self.blocos)[-28:], "serie": serie},
            "contrato": self.contrato,
            "eleicao": self.eleicao,
            "ensaio_ativo": self.ensaio_ativo,
        }

    # ------------------------------------------------------------------ RPC
    async def rpc(self, no_id: str, metodo: str, params: list | None = None) -> Any:
        url = self.cfg_por_id[no_id].rpc
        r = await self.http.post(url, json={"jsonrpc": "2.0", "method": metodo, "params": params or [], "id": 1})
        dados = r.json()
        if "error" in dados:
            raise RuntimeError(dados["error"].get("message", "erro RPC"))
        return dados.get("result")

    def no_vivo(self) -> str | None:
        vivos = [n for n in self.nos.values() if n.estado == "no_ar" and n.bloco is not None]
        return max(vivos, key=lambda n: n.bloco or 0).id if vivos else None

    # ------------------------------------------------------------------ laços
    async def laco_alturas(self) -> None:
        while True:
            await asyncio.gather(*(self._altura(nid) for nid in self.nos), return_exceptions=True)
            maior = max((n.bloco or 0 for n in self.nos.values() if n.estado == "no_ar"), default=0)
            agora = time.time()
            if maior > self.altura:
                await self._novos_blocos(self.altura, maior)
                if self.parada_desde is not None and self.altura:
                    parada = agora - self.parada_desde
                    self.evento("rede", f"A rede voltou a produzir blocos após {parada:.0f} s parada", "good")
                self.parada_desde = None
                self.altura = maior
                self.ultimo_bloco_em = agora
            elif self.ultimo_bloco_em and agora - self.ultimo_bloco_em > 3 * self.cfg.periodo_bloco + 1:
                if self.parada_desde is None:
                    self.parada_desde = self.ultimo_bloco_em
                    self.evento("rede", f"Nenhum bloco novo há {agora - self.ultimo_bloco_em:.0f} s", "warning")
            if self.altura:
                self.historico_ritmo.append((agora, self.altura))
            quorum_ok = self.vivos() >= self.quorum
            if self.quorum_ok is not None and quorum_ok != self.quorum_ok and self.tunel_ativo:
                if quorum_ok:
                    self.evento("rede", f"Quórum restabelecido: {self.vivos()} de {len(self.nos)} validadores no ar",
                                "good")
                else:
                    self.evento("rede", f"Quórum perdido: {self.vivos()} de {len(self.nos)} no ar, "
                                        f"o consenso exige {self.quorum}", "critical")
            self.quorum_ok = quorum_ok
            self._publicar(self.snapshot())
            await asyncio.sleep(1)

    async def _altura(self, nid: str) -> None:
        no = self.nos[nid]
        try:
            no.bloco = int(await self.rpc(nid, "eth_blockNumber"), 16)
            no.falhas = 0
            novo = "no_ar"
        except Exception:  # noqa: BLE001 — falha de rede; só marca fora após 2 seguidas (evita falso alarme)
            no.falhas += 1
            novo = "fora" if no.falhas >= 2 or no.estado != "no_ar" else no.estado
        if novo != no.estado:
            anterior, no.estado = no.estado, novo
            if self.tunel_ativo and anterior != "desconhecido":
                if novo == "fora":
                    self.evento("maquina", f"Nó {no.rotulo} saiu do ar", "critical", [nid])
                else:
                    self.evento("maquina", f"Nó {no.rotulo} voltou ao ar", "good", [nid])
            elif anterior == "desconhecido" and novo == "no_ar":
                pass

    async def _novos_blocos(self, de: int, ate: int) -> None:
        fonte = self.no_vivo()
        if fonte is None:
            return
        inicio = max(de + 1, ate - 15)
        for num in range(inicio, ate + 1):
            try:
                b = await self.rpc(fonte, "eth_getBlockByNumber", [hex(num), False])
            except Exception:  # noqa: BLE001
                continue
            if not b:
                continue
            prop = self.por_endereco.get(b["miner"].lower())
            ntx = len(b["transactions"])
            if prop:
                self.nos[prop].propostos += 1
                self.nos[prop].ultimo_proposto = num
            bloco = {"num": num, "proponente": prop, "txs": ntx, "ts": int(b["timestamp"], 16)}
            self.blocos.append(bloco)
            self._publicar({"t": "bloco", **bloco, "pares": self.nos[prop].pares if prop else []})
            if ntx and de:
                rot = self.nos[prop].rotulo if prop else "?"
                self.evento("blockchain", f"Bloco #{num} gravado com {ntx} transação(ões), proposto por {rot}",
                            "info", [prop] if prop else [], {"bloco": num})

    async def laco_pares(self) -> None:
        while True:
            for nid, no in self.nos.items():
                if no.estado != "no_ar":
                    no.pares = []
                    continue
                try:
                    if not no.enode:
                        info = await self.rpc(nid, "admin_nodeInfo")
                        no.enode = (info.get("id") or "").lower()
                    peers = await self.rpc(nid, "admin_peers") or []
                    ids = {(p.get("id") or "").removeprefix("0x").lower() for p in peers}
                    no.pares = sorted(o.id for o in self.nos.values() if o.enode and o.enode in ids)
                except Exception:  # noqa: BLE001
                    pass
            fonte = self.no_vivo()
            if fonte:
                try:
                    vals = await self.rpc(fonte, "qbft_getValidatorsByBlockNumber", ["latest"])
                    if vals:
                        self.validadores = [v.lower() for v in vals]
                except Exception:  # noqa: BLE001
                    pass
            await asyncio.sleep(4)

    async def laco_maquinas(self) -> None:
        intervalo = 8 if self.cfg.modo == "cluster" else 5
        while True:
            if self.tunel_ativo:
                try:
                    stats = await infra.coletar_stats(self.cfg)
                    for nid, s in stats.items():
                        no = self.nos[nid]
                        no.carga, no.nucleos, no.mem_usada, no.mem_total = s.carga, s.nucleos, s.mem_usada, s.mem_total
                        no.besu_mem, no.besu_estado = s.besu_mem, s.besu_estado
                except Exception as e:  # noqa: BLE001
                    self.evento("sistema", f"Falha ao coletar estatísticas das máquinas: {e}", "warning")
            await asyncio.sleep(intervalo)

    async def laco_contrato(self) -> None:
        while True:
            await asyncio.sleep(2)
            if not self.contrato:
                continue
            fonte = self.no_vivo()
            if fonte is None or not self.altura:
                continue
            # fixa o limite ANTES da consulta: a altura avança durante o await e não pode pular blocos
            ate = self.altura
            de = self.ultimo_bloco_logs + 1 if self.ultimo_bloco_logs else max(0, ate - 5000)
            if de > ate:
                continue
            try:
                logs = await self.rpc(fonte, "eth_getLogs", [{"address": self.contrato, "fromBlock": hex(de),
                                                              "toBlock": hex(ate)}])
            except Exception:  # noqa: BLE001
                continue
            for lg in logs or []:
                self._log_contrato(lg)
            self.ultimo_bloco_logs = ate

    def _log_contrato(self, lg: dict[str, Any]) -> None:
        nome = TOPICOS.get(lg["topics"][0])
        if not nome:
            return
        eid = lg["topics"][1][2:]
        dados = bytes.fromhex(lg["data"][2:])
        bloco = int(lg["blockNumber"], 16)
        el = self.eleicao
        if el.get("id") and el["id"] != eid and nome != "EleicaoCriada":
            return
        if nome == "EleicaoCriada":
            autoridade, n_ap = abi_decode(["address", "uint256"], dados)
            if el.get("id") != eid:
                el.update({"id": eid, "fase": "votacao", "encerrada": False, "secoes": el.get("secoes") if
                           el.get("id_pendente") == eid else {}, "resultados": el.get("resultados", {})})
            el["bloco_criacao"] = bloco
            no = self.por_endereco.get(autoridade.lower())
            self.evento("eleicao", f"Eleição registrada na blockchain (bloco #{bloco}) — {n_ap} apuradores autorizados",
                        "good", [no] if no else [], {"bloco": bloco, "eleicao": eid})
        elif nome == "BoletimRegistrado":
            secao, hb, hl, total, quem = abi_decode(["string", "bytes32", "bytes32", "uint32", "address"], dados)
            no = self.por_endereco.get(quem.lower())
            s = el["secoes"].setdefault(secao, {"secao": secao, "no": no, "fase": "ancorado", "cedulas": total})
            s.update({"fase": "ancorado", "hash": hb.hex(), "ledger": hl.hex(), "bloco": bloco,
                      "cedulas_apuradas": total, "no": s.get("no") or no})
            s.setdefault("tempos", {})["ancorado"] = time.time()
            rot = self.nos[no].rotulo if no else quem[:10]
            self.evento("eleicao", f"Seção {secao}: boletim ancorado no bloco #{bloco} por {rot} — {total} cédulas",
                        "good", [no] if no else [], {"bloco": bloco, "secao": secao, "hash": hb.hex()})
        elif nome == "EleicaoEncerrada":
            (hm,) = abi_decode(["bytes32"], dados)
            el.update({"fase": "encerrada", "encerrada": True, "hash_mural": hm.hex(), "bloco_encerramento": bloco})
            self.evento("eleicao", f"Eleição encerrada na blockchain (bloco #{bloco}). Hash do mural {hm.hex()[:16]}…",
                        "good", [], {"bloco": bloco})

    async def ao_mudar_tunel(self, ativo: bool, msg: str) -> None:
        if ativo != self.tunel_ativo:
            self.tunel_ativo = ativo
            self.tunel_msg = msg
            if ativo:
                self.evento("sistema", f"Conectado ao cluster pela ponte {self.cfg.ponte}", "good")
            else:
                self.evento("sistema", f"Conexão com o cluster perdida: {msg}. Tentando de novo…", "critical")

    async def iniciar(self) -> list[asyncio.Task]:
        tarefas = []
        if self.cfg.modo == "cluster" and self.cfg.ponte:
            self.tunel = infra.Tunel(self.cfg)
            tarefas.append(asyncio.create_task(self.tunel.manter(self.ao_mudar_tunel)))
        elif self.cfg.modo == "cluster":
            self.evento("sistema", "Painel rodando dentro da rede do cluster (acesso direto aos nós)", "good")
        else:
            self.evento("sistema", "Painel conectado à simulação local (contêineres Docker)", "good")
        for laco in (self.laco_alturas, self.laco_pares, self.laco_maquinas, self.laco_contrato):
            tarefas.append(asyncio.create_task(laco()))
        return tarefas

    def json_sse(self, msg: dict[str, Any]) -> str:
        return f"data: {json.dumps(msg, ensure_ascii=False, default=str)}\n\n"
