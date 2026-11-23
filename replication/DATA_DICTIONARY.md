# Data dictionary

Result files are JSON written by `experimentos/comum.py`. Keys are in Portuguese; this dictionary translates them.
Times are in seconds (s) unless a key says otherwise (`_ms` = milliseconds). Block numbers are heights of the test
chain. Node labels such as `.110` are the last byte of the node's address in the cluster LAN (192.168.0.0/24). The
validators, in proposer-rotation order, are .101, .102, .103, .104, .105, .106, .108, .109, .110, .111, .112 and
.113 (.107 was excluded).

## Fields common to all files

| Key | Meaning |
|---|---|
| `experimento` | experiment name |
| `gerado_em` | time the file was written (local time, ISO 8601) |
| `ambiente` | `cpu`, `python` version, operating system (`so`) and git `commit` of the computer that ran the script |
| `metodo` | method in one sentence |
| `execucoes` / `repeticoes` | one object per run |
| `parcial` | present and true while the experiment was still running |

A summary object (`resumo`) has: `n`, `media` (mean), `mediana` (median), `desvio` (sample standard deviation, n − 1),
`min`, `p95`, `p99`, `max`, and `ic95_media` (95% interval of the mean, mean ± 1.96·SD/√n).

## Battery of 22–23 November 2026 (`resultados/`)

Unless noted, cluster experiments ran on the bridge computer, in the cluster LAN (direct mode), with 12 validators
and a quorum of 8. E1–E4 ran on the operator's workstation and E7L on the local Docker network of that workstation.

### `e1-tamanho-cedula.json` (E1): ballot size
`nova_versao[]`: one entry per number of votes in the ballot. `votos` = votes; `secao_bytes` = bytes of the
polling-station identifier; `bytes_binarios` = signed payload in bytes; `caracteres_qr` = QR text length;
`versao_qr_M` = QR version at error-correction level M; `modulos_lado` = modules per side. `prototipo_2016`: the
same quantities for the 2016 prototype (RSA-1024 ciphertext in base64): `bytes_cifrados`, `caracteres_qr`,
`versao_qr_L`, `versao_qr_M`.

### `e2-desempenho-cripto.json` (E2): cryptographic cost
`unidade` = unit (ms). `operacoes`: one summary per operation, with 10,000 timed runs after 500 warm-up runs.
`ed25519_assinar_106B` / `ed25519_verificar_106B` = sign / verify a 106-byte ballot header; `emitir_cedula_completa`
= build and sign a ballot; `ler_cedula_decodificar_e_verificar` = decode and verify a QR text;
`prototipo_rsa1024_oaep_cifrar` / `_decifrar` = the 2016 prototype's RSA-1024 OAEP encrypt / decrypt;
`referencia_rsa2048_pss_assinar` / `_verificar` = RSA-2048 PSS sign / verify, for reference.

### `e3-leitura-qr.json` (E3): optical decoding
`condicoes`: the six image conditions. `limpo_4px_modulo` = clean, 4 pixels per module;
`resolucao_minima_2px_modulo` = 2 pixels per module; `rotacao_7graus_desfoque` = 7° rotation and blur;
`perspectiva_e_rotacao_ate_25graus` = perspective and rotation up to 25°; `webcam_640x480_ruido_jpeg70` =
webcam-like 640 × 480 frame with noise and JPEG quality 70; `termica_desbotada_35pct_contraste` = faded thermal print
with 35% contrast. `resultados[condition][detector]`, for the OpenCV detectors `QRCodeDetector` and
`QRCodeDetectorAruco`: `acertos` = ballots decoded correctly out of `n` = 1,000; `taxa` = success rate; `ic95` =
Wilson 95% interval; `tempo_ms` = decoding time per image. The files `e3-exemplo-*.png` show one image per condition.

### `e4-apuracao.json` (E4): tally cost
`resultados.hd_mecanico` = ledger on the home-directory disk (a 5,400 rpm hard disk); `resultados.ram_tmpfs` = ledger
in `/dev/shm`. `montagem` = mount point. `secoes_de_400` / `secoes_de_5000` = sections of 400 or 5,000 ballots, with
`repeticoes` = sections; `cedulas_medidas` = ballots timed; `processar_cedula_ms` = time to process one ballot
(decoding, signature check, and durable ledger write); `verificar_ledger_ms` = time to verify the hash chain;
`gerar_boletim_ms` = time to generate the signed report; and the time per section.

### `e5-intervalo-blocos.json` (E5): block intervals in normal operation
`blocos` = block range. `intervalos` = intervals counted. `lacunas_acima_60s` = gaps above 60 s, which are cluster
shutdowns and are excluded. `intervalo_s` = summary. `distribuicao_s` = histogram (interval in s → count).
`fracao_exatamente_2s` = fraction of intervals of exactly 2 s. `blocos_por_min` = blocks per minute.

### `e6-ensaios-nominais.json` / `.md` (E6): 10 election rehearsals
Written by `urna3g ensaio-lote`. `meta` = network, number of nodes, runs, voters per station, voting time, contract.
`agregado` = totals and summaries over the runs. `secoes_ancoradas` = stations anchored; `boletins_conferem` =
reports whose on-chain hash matches the local report, read back through another node; `duplicadas_total` /
`invalidas_total` = re-read and forged ballots rejected; `duracao` / `apuracao` / `ancoragem` = durations; `nos_sairam`
/ `quorum_perdido` = node-down and quorum-lost events. Each object of `execucoes[]` has the same fields per run, plus
`secoes` (per station: ballots, report hash, anchoring block and time) and `conferencia_cadeia` (on-chain check).

### `e7-tolerancia.json` (E7): throughput with randomly drawn stopped validators
Each object of `execucoes[]` is one run. `k_fora` = validators stopped (0–4); `rep` = repetition (1–5); `fora` = stopped
validators, drawn with seed 77; `blocos` = blocks in the window; `janela_s` = window length (about 120 s);
`blocos_por_min` = blocks per minute; `maior_intervalo_s` / `intervalo_medio_s` = longest / mean interval between
blocks; `tempo_ate_saudavel_s` = time for the network to be healthy again after the restart. `por_k` = summaries per
`k_fora`.

### `e7b-tolerancia-consecutivos.json` (E7b): throughput with consecutive stopped validators
Same fields as E7, plus `blocos_por_120s` (blocks normalized to 120 s) and `intervalos_s` (every interval between
blocks in the window). Stopped sets: k = 3 → .111, .112, .113; k = 4 → .110, .111, .112, .113.

### `e7l-tolerancia-local.json` (E7L): throughput on the 4-validator local network
Same fields as E7b. `fora`: `node4` (k = 1) or `node3` and `node4` (k = 2). After each window without a quorum
(k = 2), the four containers were restarted together.

### `e8-recuperacao.json` (E8): recovery after a halt
`plano` = [outage duration in s, runs]. Each object of `execucoes[]` has: `parada_s` = outage duration with 5 of 12
validators stopped (no quorum); `fora` = stopped validators (seed 88); `religado` = the validator restarted to restore
the quorum; `rpc_religado_s` = time until its RPC answered; `proximo_bloco_s` = time from the restart command to the
next block (the recovery time of the article); `ate_saudavel_s` = time until all 12 were healthy after restarting the
other four. `por_duracao` = summaries per outage duration. No block was produced during any outage: the height read
right after stopping the validators was still the highest height until the recovery block.

### `e9-capacidade.json` (E9): gas and burst capacity
`gas`: gas of `implantar` (deployment), `criar_eleicao_12_apuradores` (election creation with 12 authorized accounts),
`registrar_boletim` (report record) and `encerrar` (closing). `repeticoes[]`: each burst of 1,200 records sent by 12
accounts, each through its own node. `taxa_oferecida_tx_s` = rate offered by the client; `tx_por_s_na_cadeia` = rate
carried by the chain; `tx_por_bloco` = transactions per block; `latencia_inclusao_s` = block timestamp minus send
time, at the 1 s resolution of block timestamps, which is why a few values are slightly negative;
`secoes_registradas_no_contrato` = records read back from the contract.

### `e10-ensaio-com-falhas.json` (E10): rehearsals with validators stopped during the tally
Same per-run fields as E6. In each run, 3 validators (seed 1010) stopped for 60 s when the tally started.
`ancoragem_secoes_afetadas_s` / `ancoragem_secoes_nao_afetadas_s` = anchoring time of the stations whose node was or
was not stopped.

### `e11-reinicio.json` (E11): full restart of the network
`modo`: `escalonado` = staggered (nodes started one by one) or `simultaneo` = simultaneous. `espalhamento_starts_s` =
spread of the start commands; `todos_respondem_s` = time until all RPCs answer; `primeiro_bloco_s` = time to the first
new block; `malha_completa_s` = time until every node has 11 peers.

### `e12-recursos.jsonl` (E12): memory and CPU of the Besu containers
One JSON object per line, sampled every 60 s during E7–E11 with `docker stats`. `ts` = Unix time; `rotulo` = experiment
and run; `ip` = node; `mem` = memory in use; `cpu` = CPU share of one core.

### `e13-custo-ancoragem.json` (E13): gas and latency of single anchoring transactions
`transacoes[]`: one object per transaction. `eleicao` = election (1–10); `funcao` = `implantar`, `criarEleicao`,
`registrarBoletim` or `encerrar`; `secao` = polling station (001–012, each recorded by its own account through its
own node); `no` = node that received it; `gas_usado` = gas used; `status` = 1 for success; `bloco` = inclusion block;
`latencia_recibo_s` = time from sending the signed transaction to the receipt being available (polled every 0.1 s),
which is the inclusion latency of the article; `latencia_timestamp_s` = block timestamp minus send time; `tx` =
transaction hash. Each transaction was sent after the previous receipt, following a random wait of 0–2 s, so that the
send time was independent of block production. `por_funcao` = summaries per function. `registrar_primeira_secao` /
`registrar_demais_secoes` = report records split into the first record of each election, which costs more because it
creates the election's list of stations, and the others.

### Logs, report and discarded runs
`log-locais.txt`, `log-cluster.txt`, `log-e7l.txt` and `log-e13-e7b.txt` are the console output of the runs.
`RELATORIO-EXPERIMENTOS.md` is the consolidated report, in Portuguese, generated by `experimentos/relatorio.py`. The
following files are kept for transparency and were not used:
- `e3-leitura-qr-descartado-corte-na-rotacao.json`: the rotation clipped the QR corners.
- `e9-capacidade-descartado-latencia-mal-medida.json`: latency was measured only after all sends, and the offered rate was limited by the client.
- `lote-preliminar-com-defeito-do-coletor.*`: a dashboard defect skipped blocks when reading contract events.

## Single runs of 13–14 November 2026 (`data-preliminary/`)

See `data-preliminary/DATA_DICTIONARY.md`.
