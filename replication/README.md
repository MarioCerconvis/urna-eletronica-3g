# Urna3G: replication package

Code, network configuration and raw data for the article

> G. J. M. Hassegawa, M. G. Cerconvis, V. V. Colombo, D. M. Dourado, L. F. C. Monteiro, J. P. Carmo and M. Gazziro,
> *Anchoring, Not Voting, On-Chain: A Third-Generation Paper Ballot System Evaluated on a 12-Node Permissioned
> Blockchain*. Manuscript submitted to *Future Internet* (MDPI), 2026.

Urna3G prints each ballot with a human-readable record and an Ed25519-signed QR code. It records the public tally of
each polling station in a hash-chained ledger closed by a signed report, and it anchors only the hash of each report in
a permissioned Hyperledger Besu network with QBFT consensus. This package holds everything needed to rerun the
evaluation: the system, the anchoring contract, the scripts that create and operate the blockchain network, the
measurement scripts, and the raw data of every run.

## Contents

| Path | Content |
|---|---|
| `src/urna3g/` | The system: ballot, manifest, ledger, tally and report formats; command line; graphical screens; bulletin-board server; live dashboard; rehearsal runner |
| `tests/` | Automated tests (pytest; 61 cases in this version) |
| `deploy/blockchain/` | `RegistroEleitoral` contract (Solidity source and compiled artifact for the London EVM), network generation and start-up scripts for a local Docker network and for a physical cluster, anchoring command line, network status tool |
| `experimentos/` | Measurement scripts E1–E13 and the report generator |
| `exemplos/` | Example election and configuration files |
| `resultados/` | Raw results of the measurement battery of 22–23 November 2026 (E1–E13), run logs, and the consolidated report in Portuguese |
| `data-preliminary/` | Single-run measurements of 13–14 November 2026 reported in the article, with a data dictionary |
| `network/` | Genesis files and validator addresses of the 12-validator cluster and of the 4-validator local network (no private keys) |
| `environment/` | Exact Python package versions, Besu image digest, description of the testbeds |
| `docs/` | Design notes (Portuguese) and the data-format specification (`docs/format-specification.md`, English) |
| `REPLICATION.md` | Step-by-step replication guide |
| `DATA_DICTIONARY.md` | Fields of every result file |
| `README.pt-BR.md` | Original repository README (Portuguese) |

## Where each number in the article comes from

| Article item | Data | Script |
|---|---|---|
| Single-run results: throughput and outages on the local and cluster networks, recovery on the local network, start-up, memory, anchoring blocks, election rehearsals | `data-preliminary/` | Procedures P1–P7 (REPLICATION.md, Section 7) |
| Table "Block production with stopped validators", last column, cluster 12/12 | `resultados/e7-tolerancia.json` (k = 0) | `experimentos/e7_tolerancia.py` |
| Same table, cluster 9/12 and 8/12 | `resultados/e7b-tolerancia-consecutivos.json` | `experimentos/e7b_tolerancia_consecutivos.py` |
| Same table, cluster 7/12 | `resultados/e8-recuperacao.json` (no block in any of the 18 outages) | `experimentos/e8_recuperacao.py` |
| Same table, local network rows | `resultados/e7l-tolerancia-local.json` | `experimentos/e7l_tolerancia_local.py` |
| Recovery times on the cluster after outages of 10, 30, 60 and 120 s | `resultados/e8-recuperacao.json` | `experimentos/e8_recuperacao.py` |
| Table "Gas used and inclusion latency of the anchoring transactions" | `resultados/e13-custo-ancoragem.json` | `experimentos/e13_custo_ancoragem.py` |

The other experiments of the battery (E1–E6 and E9–E12) are not discussed in the article. They are included for
completeness and summarized in `resultados/RELATORIO-EXPERIMENTOS.md`. `resultados/e7-tolerancia.json` also
contains runs with randomly drawn stopped validators, which show that the longest pause depends on whether stopped
validators are adjacent in the proposer rotation.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[gui,camera,servidor,blockchain,painel,dev]"
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q          # automated tests
.venv/bin/urna3g demo --saida /tmp/urna3g-demo --eleitores 40   # complete election on disk
deploy/blockchain/simular.sh                            # 4-validator QBFT network in Docker, end to end
```

REPLICATION.md describes four levels of replication: offline measurements, the 4-validator local network, all
cluster experiments on a single computer with 12 Besu containers, and the physical cluster used in the article.

## License and citation

The code is released under the MIT license (`LICENSE`). Cite the article and this package as described in
`CITATION.cff`. The source code of the 2016 prototype reviewed in the article is not part of this package; it is
available at <https://github.com/mariogazziro/urna_eletronica>.

Generative AI was used to write most of the code base, the tests and the measurement scripts (Claude models from
Anthropic, through the Claude Code tool). The authors reviewed the code and ran every measurement; see the article for
the full statement.
