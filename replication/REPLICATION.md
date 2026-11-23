# Replication guide

This guide reruns the evaluation of the article at four levels. Each level adds requirements:

| Level | What it reproduces | Requirements | Time |
|---|---|---|---|
| 1. Offline | Tests, demonstration, ballot size, cryptographic cost, QR decoding, tally cost (E1–E4) | Python 3.10 or later | about 30 min |
| 2. Local network | 4-validator QBFT network in Docker (procedure P4), throughput with stopped validators (E7L), dashboard and election rehearsals | Linux and Docker | about 1 h |
| 3. Single-computer cluster | All cluster experiments (E5–E13) on 12 Besu containers in one computer | Linux, Docker, about 10 GB of free RAM, 4 or more cores | about 4 h |
| 4. Physical cluster | The 12-desktop deployment of the article | 12 Linux machines with Docker on one LAN, plus a bridge computer | about 5 h of measurements |

Commands are given from the root of the package unless stated otherwise. Comments and identifiers in the code are in
Portuguese; DATA_DICTIONARY.md translates the result fields.

> **Before rerunning any experiment, move the published results aside.** The scripts write to `resultados/`, and
> E7 and E7b resume from an existing result file, so they would skip every run if the published file is present:
>
> ```bash
> mv resultados resultados-published && mkdir resultados
> ```

## 1. Software environment

Tested versions: Ubuntu 24.04 (workstation and bridge) and Ubuntu 26.04 (cluster nodes), Python 3.12.3, Docker 29.1.3,
Hyperledger Besu 26.11.0. `environment/requirements-lock.txt` lists the exact Python packages and
`environment/besu-image.txt` the digest of the Besu image.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[gui,camera,servidor,blockchain,painel,dev]"
# exact versions used in the article (optional):
.venv/bin/pip install -r environment/requirements-lock.txt
docker pull hyperledger/besu:26.11.0
```

The Docker user must belong to the `docker` group. The compiled contract
(`deploy/blockchain/contracts/RegistroEleitoral.json`) is included. To rebuild it, run
`.venv/bin/python deploy/blockchain/compilar.py`; py-solc-x downloads solc 0.8.26, and the target is the London EVM,
because the network does not activate the Shanghai rules (Section "Integration defects" of the article).

## 2. Level 1: offline measurements

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q                   # procedure P1
.venv/bin/urna3g demo --saida /tmp/urna3g-demo --eleitores 40   # procedure P2
cd experimentos
../.venv/bin/python e1_tamanho_cedula.py      # E1: ballot size and QR version vs. number of votes (seconds)
../.venv/bin/python e2_desempenho_cripto.py   # E2: Ed25519, ballot issue/read, RSA references, 10,000 runs each (minutes)
../.venv/bin/python e3_leitura_qr.py          # E3: 1,000 ballots x 6 image conditions x 2 OpenCV detectors (about 5 min)
../.venv/bin/python e4_apuracao.py            # E4: tally cost per ballot on the home-directory disk and in /dev/shm (about 10 min)
```

E4 measures the durable ledger (SQLite in WAL mode with full synchronization). Its cost depends on the disk: in the
article environment, the home directory was on a 5,400 rpm hard disk.

## 3. Level 2: the 4-validator local network (environment B)

```bash
deploy/blockchain/simular.sh 4 --falhas
```

`simular.sh` generates a QBFT network with four validators if `deploy/blockchain/besu/rede/` does not exist. It
starts one Besu container per validator on a Docker network with fixed addresses, deploys the contract, creates an
election, and anchors a report with an authorized account. It then tries an unauthorized account and a second record
for the same polling station, which must both be refused. With `--falhas`, it also stops one and then two validators
and measures the restart (procedure P4). RPC endpoints are `http://127.0.0.1:8545` to `:8548`.

Throughput with 0, 1 and 2 of the 4 validators stopped, with 5 runs of 120 s each (E7L, used in the article):

```bash
deploy/blockchain/besu/rede-local.sh subir                       # if the network is not running
.venv/bin/python deploy/blockchain/status_rede.py                # wait for "PRODUZINDO" and 3 peers per node
cd experimentos && ../.venv/bin/python e7l_tolerancia_local.py   # about 40 min
```

Dashboard and election rehearsals with simulated voters (procedure P7):

```bash
.venv/bin/urna3g painel --local --abrir                          # http://127.0.0.1:8787
.venv/bin/urna3g ensaio-lote --local --n 10 --eleitores 25 --duracao 30 --saida resultados/ensaios-locais
```

`deploy/blockchain/besu/rede-local.sh parar` stops the network and keeps the chain data.
`rede-local.sh limpar` erases the chain and keeps the keys.

## 4. Level 3: the cluster experiments on a single computer

The cluster scripts also accept a network of containers on the same computer (`"modo": "local"` in the configuration
file). This level reproduces the protocol behavior measured on the cluster: the quorum rule, the pauses caused by
stopped proposers, the recovery steps set by the doubling round-change timeout, and the gas costs. Absolute times that
depend on hardware and network, such as start-up and peer discovery, will differ, because all validators share one
host and there is no network latency between them.

```bash
cd deploy/blockchain/besu
./rede-local.sh parar 2>/dev/null; rm -rf rede      # discards any previous local network
./gerar-rede.sh 12                                  # genesis and 12 validator keys, generated by Besu itself
./rede-local.sh subir                               # 12 containers, RPC on 127.0.0.1:8545..8556
cd ../../..
.venv/bin/python deploy/blockchain/status_rede.py   # wait for "PRODUZINDO" and 11 peers per node
export URNA3G_PAINEL_CFG=$PWD/exemplos/experimentos-local.json
```

Then run the experiments from `experimentos/`, in the order of the article battery (Section 5):

| Script | Measures | Time |
|---|---|---|
| `e7_tolerancia.py` | Blocks per 120 s with k = 0–4 validators stopped, drawn at random (seed 77), 5 runs per k | 45 min |
| `e7b_tolerancia_consecutivos.py` | The same with the last 3 and the last 4 validators stopped, which are consecutive in the proposer rotation, 5 runs each | 30 min |
| `e6_ensaios_nominais.sh` | 10 election rehearsals, one polling station per validator | 10 min |
| `e9_capacidade.py` | Gas of each contract function; 3 bursts of 1,200 report records sent by 12 accounts | 6 min |
| `e13_custo_ancoragem.py` | Gas and inclusion latency of each anchoring transaction sent one at a time, in 10 elections of 12 polling stations | 6 min |
| `e10_ensaio_com_falhas.py` | 5 rehearsals with 3 validators stopped for 60 s when the tally starts | 12 min |
| `e8_recuperacao.py` | 5 of 12 validators stopped for 10, 30, 60 and 120 s (5, 5, 5 and 3 runs), then one restarted: time to the next block | 80 min |
| `e11_reinicio.py` | Full restart of the network, staggered and simultaneous, 5 runs each | 15 min |
| `e5_intervalo_blocos.py FIRST LAST` | Distribution of block intervals over a block range of your own chain with all validators online | seconds |

E7–E11 append memory and CPU samples of every container to `resultados/e12-recursos.jsonl` (E12). The consolidated
report is regenerated with `../.venv/bin/python relatorio.py`, which writes `resultados/RELATORIO-EXPERIMENTOS.md`.
The scripts that stop validators restore the network and wait for it to be healthy before the next run: all nodes
answer, are within two blocks of each other, have peers, and are producing blocks.

## 5. Level 4: a physical cluster (environment C)

Requirements: Linux machines with Docker on one LAN. The computer that controls them (the bridge, or the operator's
workstation) needs key-based SSH access to each machine, and the clocks must be synchronized by NTP. In the article,
12 desktops (Ubuntu 26.04, 3.3–3.4 GB of RAM) ran one Besu container each, with the Java heap limited to 1 GB.

```bash
IPS="192.168.0.101 192.168.0.102 ..."                         # one address per machine; node K -> K-th address
cd deploy/blockchain/besu
./verificar-cluster.sh USER $IPS                              # read-only check: SSH, Docker, RAM, disk, clock
./gerar-rede.sh 12                                            # keys and genesis, on the control computer
./implantar-cluster.sh subir rede USER $IPS                   # each machine receives only its own validator key
../../../.venv/bin/python ../status_rede.py --rpc $(for ip in $IPS; do printf 'http://%s:8545 ' $ip; done)
```

Copy `exemplos/painel-cluster.json` and fill in the node addresses, the user on the nodes, and `rede_dir`. Set
`"ponte": null` to run the scripts on a computer of the cluster LAN. That is how the article battery ran, on the
bridge computer, inside `tmux`. Set `"ponte": "user@bridge"` to run them from a remote workstation; the scripts then
open an SSH tunnel through the bridge. Export `URNA3G_PAINEL_CFG` with the path of this file and run the scripts of
Section 4. The live dashboard uses the same file: `urna3g painel --config painel.json --abrir`.

## 6. Network parameters

`network/` contains the genesis files and the validator addresses actually used: `cluster-12-validators` (chain
identifier 20261113, 12 validators) and `local-4-validators`. Both use QBFT with `blockperiodseconds` 2,
`requesttimeoutseconds` 4, the London rules from block 0, and zero base fee (`deploy/blockchain/besu/qbftConfigFile.json`).
The validator keys are not distributed. A replication generates its own keys with `gerar-rede.sh`, which gives a new
network with the same parameters. Validator K is the K-th address in `validadores.txt`. Addresses are in ascending
order, which is also the order in which QBFT rotates the proposer role, so the last validators of the list are
consecutive in the rotation.

## 7. Single-run measurements of 13–14 November 2026

`data-preliminary/` holds the single runs reported in the article. They were made with procedures P1–P7 of the
article: `simular.sh --falhas` and `rede-local.sh` on the local network, and `implantar-cluster.sh`, `status_rede.py`
and `docker stats` on the cluster. The rehearsals used the dashboard. The block-height series behind the fault figure
are in `dados-falhas-cluster.csv`. The stopped validators of these runs were not recorded, and the duration of the
halt that preceded the 131 s recovery on the cluster was not recorded either.

## 8. Expected results

The result files of the article are in `resultados-published/` (after the `mv` above) or in the original
`resultados/`. Protocol-determined quantities should reproduce on any hardware:

- 30 blocks per minute with every validator online.
- A pause of 6 s for each round whose proposer is stopped. The pause is 14 s when two consecutive proposers are stopped, 30 s for three, and 62 s for four, so the throughput depends on which validators stop as well as on how many.
- A halt when fewer than ⌈2n/3⌉ validators are online.
- Recovery times on discrete steps whose spacing doubles from one step to the next.
- Identical gas per function.

Hardware-dependent quantities are tally cost, start-up and recovery offsets, and memory.
