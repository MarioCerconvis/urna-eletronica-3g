"""Configuração do painel (arquivo JSON) e descoberta dos nós."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[3]
ARTEFATO_PADRAO = RAIZ_REPO / "deploy" / "blockchain" / "contracts" / "RegistroEleitoral.json"
REDE_LOCAL_PADRAO = RAIZ_REPO / "deploy" / "blockchain" / "besu" / "rede"
PORTA_TUNEL_BASE = 19100


@dataclass
class NoCfg:
    id: str          # "node1"
    indice: int      # 1..N  (= seção do ensaio)
    ip: str          # IP real da máquina (cluster) ou 127.0.0.1 (local)
    rpc: str         # URL RPC vista DESTE computador
    endereco: str    # conta do validador (minúsculas, 0x...)
    chave: Path      # arquivo da chave do validador (usada pelo ensaio para ancorar pela máquina)

    @property
    def rotulo(self) -> str:
        if self.ip.count(".") == 3 and not self.ip.startswith("127."):
            return "." + self.ip.rsplit(".", 1)[-1]
        return self.id


@dataclass
class PainelCfg:
    modo: str                         # "cluster" | "local"
    nome: str
    rede_dir: Path
    nos: list[NoCfg]
    ponte: str | None = None          # usuario@host da máquina-ponte (modo cluster)
    usuario_nos: str = "laob"
    ip_ponte: str | None = None       # IP interno da ponte (só exibição)
    contrato: str | None = None
    artefato: Path = ARTEFATO_PADRAO
    periodo_bloco: float = 2.0
    extra: dict = field(default_factory=dict)


def _validadores(rede_dir: Path) -> list[tuple[str, str]]:
    arq = rede_dir / "validadores.txt"
    if not arq.is_file():
        raise SystemExit(f"não encontrei {arq} (gere a rede com gerar-rede.sh)")
    return [tuple(linha.split()[:2]) for linha in arq.read_text().splitlines() if linha.strip()]  # type: ignore[misc]


def carregar(caminho: Path | None, local: bool) -> PainelCfg:
    if local:
        rede = REDE_LOCAL_PADRAO
        nos = [
            NoCfg(nid, k, "127.0.0.1", f"http://127.0.0.1:{8544 + k}", addr.lower(), rede / nid / "key")
            for k, (nid, addr) in enumerate(_validadores(rede), start=1)
        ]
        return PainelCfg("local", "Simulação local (Docker)", rede, nos)
    if caminho is None:
        raise SystemExit("informe --config painel.json ou use --local")
    d = json.loads(Path(caminho).read_text())
    rede = Path(d["rede_dir"]).expanduser()
    vals = _validadores(rede)
    ips = d["ips"]
    if len(ips) != len(vals):
        raise SystemExit(f"{len(ips)} IPs no config, mas a rede tem {len(vals)} validadores")
    direto = not d.get("ponte")  # sem ponte = este computador está na rede dos nós (ex.: o computador principal)
    nos = [
        NoCfg(nid, k, ip, f"http://{ip}:8545" if direto else f"http://127.0.0.1:{PORTA_TUNEL_BASE + k}",
              addr.lower(), rede / nid / "key")
        for k, ((nid, addr), ip) in enumerate(zip(vals, ips, strict=True), start=1)
    ]
    return PainelCfg(
        modo="cluster",
        nome=d.get("nome", "Cluster"),
        rede_dir=rede,
        nos=nos,
        ponte=d.get("ponte"),
        usuario_nos=d.get("usuario_nos", "laob"),
        ip_ponte=d.get("ip_ponte"),
        contrato=d.get("contrato"),
        artefato=Path(d.get("artefato", ARTEFATO_PADRAO)).expanduser(),
    )
