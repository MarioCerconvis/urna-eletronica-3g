# Data S1 — Raw measurement data (data dictionary)

Measurements taken on 13–14 November 2026 (see Section 5 of the article). The files are provided
exactly as recorded; keys and comments are in Portuguese, and this dictionary translates them.
Times are in seconds (s), memory in mebibytes (MiB), block numbers are block heights of the test chain.

## `dados-falhas-cluster.csv` — block-height series (Figure 5a,b)

| Column | Meaning |
|---|---|
| `cenario` | scenario: `4_fora_8_de_12` = 4 validators stopped, 8 of 12 online (cluster); `3_fora_9_de_12` = 3 stopped, 9 of 12 online (cluster, after one validator was restarted); `1_fora_3_de_4_local` = 1 stopped, 3 of 4 online (local Docker network) |
| `t_segundos` | time since the start of the observation window (s); cluster samples every 15 s, local samples every 3 s |
| `altura_bloco` | block height read from a node at that time |
| `observacao` | free-text note (`inicio da janela` = start of window; `fim: N blocos em T s` = end: N blocks in T s; `1 validador religado` = one validator restarted) |

## `dados-medicoes.json` — all measurements

| Key | Meaning |
|---|---|
| `data_medicoes` | measurement dates |
| `ambiente_desenvolvimento` | development workstation (environment A): CPU, RAM (GB), OS, Docker and Python versions |
| `cluster` | laboratory cluster (environment C): `maquinas_total` machines in the lab, `maquinas_usadas` machines used, `excluida` excluded machine and reason (`sem SSH por chave` = no key-based SSH), `ips_usados` IP addresses used, `so` OS, `arquitetura` architecture, `ram_total_gb` total RAM, `ram_livre_gb` free RAM, `disco_livre_gb` free disk, `ponte` bridge computer (IP, RAM, access method), `besu` Besu version, `heap_jvm` Java heap limit, `pull_imagem_12_maquinas_s` time to download the Besu image on the 12 machines in parallel (s) |
| `cedula` | signed ballot: `bytes` payload size, `caracteres_qr` QR text length, `versao_qr` QR version, `correcao` error-correction level, `assinatura_ms` mean signing time (ms, 200 signatures, i7-4770) |
| `leitura_qr_40_cedulas` | optical decoding of 40 distinct ballots, successes/total per detector and condition (`escala` = pixels per module, `borda` = quiet zone in modules, `rotacao7` = 7° rotation, `escala0.9` = 0.9 scale, `desfoque3x3` = 3×3 Gaussian blur) |
| `testes` | automated tests: `casos` cases, `passando` passing, `ci` Python versions in continuous integration |
| `demo_40_eleitores` | demonstration with 40 voters: `aceitas` accepted ballots, `releitura` result for a re-read ballot (`duplicada` = duplicate), `forjada` result for a forged ballot (`invalida` = invalid), `registros_ledger` ledger records |
| `rede_local_4_validadores` | local network with 4 validators: `vazao_4_de_4`, `vazao_3_de_4`, `vazao_2_de_4` throughput with 4, 3 and 2 validators online (`blocos em N s` = blocks in N s); `recuperacao_s` list of {`parada_s` outage duration, `recuperacao_s` time to next block after restart}; `ancoragem` blocks of contract deployment, election creation and report anchoring, and cross-node check (`confere` = matches) |
| `cluster_4_validadores` | cluster with 4 validators: memory per node (MiB) and anchoring blocks |
| `cluster_12_validadores` | cluster with 12 validators: `subida_escalonada_s` staggered start-up duration, `tempo_ate_alinhar_apos_ultimo_s` time at block 0 after the last node started, `pares_por_no_final` peers per node, `conexoes_total` total peer connections, `vazao_12_de_12` / `vazao_9_de_12` / `vazao_8_de_12` / `vazao_7_de_12` throughput with 12/9/8/7 online (`pausas` = pauses; `parada` = halted), `recuperacao_apos_parada_s` time to resume after restarting one node (the duration of the preceding halt was not recorded), `memoria_no_mib` min/max memory per node, `ancoragem` anchoring blocks and cross-node check |
| `ensaios` | election rehearsals with simulated voters: `onde` where (`rede local` = local network; `cluster (operador)` = started by the human operator), `secoes` polling stations, `cedulas` ballots, `falha_injetada` injected fault, `rede_sem_blocos_s` time without blocks, `ancoragem_bloco(s)` anchoring block(s), `encerramento_bloco` closing block, `falsos_alarmes` false node-down alarms, `eleicao_id` election identifier, `resultado` aggregated result per contest (`presidente`, `senador`, `deputado`; candidate numbers, `branco` = blank, `nulo` = null) |
| `prototipo_2016` | 2016 prototype: files, lines of Python, RSA key size in the code, anti-duplicate identifier |

Rehearsal artifacts (ballots, ledgers, tally reports) were not preserved; only their hashes were recorded on the test chain.
