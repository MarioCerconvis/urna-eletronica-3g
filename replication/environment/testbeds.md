# Testbeds

| Environment | Hardware and software | Used for |
|---|---|---|
| A: operator's workstation | Dell OptiPlex 9020, Intel Core i7-4770 (4 cores, 8 threads, 3.4 GHz), 27 GB RAM, root file system on a 5,400 rpm hard disk, Ubuntu 24.04.5, Docker 29.1.3, Python 3.12.3 | Automated tests, demonstration, E1–E4, host of environment B, single-run cluster measurements through an SSH tunnel (13–14 Nov 2026) |
| B: local network | Four Besu 26.11.0 containers on a Docker network with fixed addresses (172.28.0.11–14), running on A; RPC on 127.0.0.1:8545–8548 | Procedure P4, local rehearsal, E7L |
| C: laboratory cluster | 12 x86-64 desktops (192.168.0.101–106 and 192.168.0.108–113; 192.168.0.107 excluded for lack of key-based SSH), Ubuntu 26.04, 3.3–3.4 GB RAM (one with 5.1 GB), 61–86 GB of free disk, one Besu 26.11.0 container per machine with `BESU_OPTS=-Xmx1g`, RPC open on the LAN, Docker restart policy `unless-stopped` | 12-validator network |
| D: bridge computer | Intel Core i7-4790, 15 GB RAM, Ubuntu 24.04.4, Python 3.12.3, in the cluster LAN (192.168.0.100), reached from A through Tailscale | Ran the cluster experiments of the battery (E5–E13, 22–23 Nov 2026) in direct mode, inside tmux |

Network parameters (both networks): QBFT, block period 2 s, round-change timeout (`requesttimeoutseconds`) 4 s,
London rules from block 0, zero base fee, `--min-gas-price=0`, chain identifier 20261113. Clocks synchronized by NTP
(checked by `verificar-cluster.sh`).
