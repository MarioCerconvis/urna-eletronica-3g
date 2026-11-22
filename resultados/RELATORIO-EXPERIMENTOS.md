# Relatório consolidado dos experimentos

Gerado por `experimentos/relatorio.py` a partir de `resultados/*.json`. Cada seção indica método e tamanho de amostra. Os scripts de cada experimento estão em `experimentos/` e podem ser reexecutados.

## E1 — Tamanho da cédula e do QR

uma medição por configuração (determinístico); votos brancos têm o mesmo tamanho que qualquer outro (int32)

| Votos por cédula | Bytes (seção de 3 B) | Caracteres no QR | Versão do QR (M) | Bytes (seção de 16 B) | Versão (M) |
|---|---|---|---|---|---|
| 1 | 98 | 136 | 8 (49×49) | 111 | 9 |
| 2 | 102 | 141 | 8 (49×49) | 115 | 9 |
| 3 | 106 | 147 | 8 (49×49) | 119 | 9 |
| 5 | 114 | 157 | 8 (49×49) | 127 | 9 |
| 10 | 134 | 184 | 9 (53×53) | 147 | 10 |
| 20 | 174 | 237 | 10 (57×57) | 187 | 11 |
| 40 | 254 | 344 | 12 (65×65) | 267 | 13 |

Protótipo de 2016 (RSA-1024-OAEP em base64): 128 bytes cifrados, 175 caracteres, QR versão 8 com correção L (versão 9 se fosse M). A cédula nova com 3 votos ocupa a mesma versão 8, mas com correção M (≈15% de recuperação, contra ≈7% da L) e com autenticidade.

## E2 — Desempenho criptográfico

n=10000 por operação, aquecimento 500, perf_counter_ns, um núcleo; Intel(R) Core(TM) i7-4770 CPU @ 3.40GHz.

| Operação | Média ± desvio (ms) | Mediana | p99 | Operações/s |
|---|---|---|---|---|
| Ed25519 — assinar (106 B) | 0,0349 ± 0,0053 | 0,0338 | 0,0620 | 28629 |
| Ed25519 — verificar | 0,1107 ± 0,0055 | 0,1096 | 0,1393 | 9033 |
| Emitir cédula completa (montar + assinar) | 0,1173 ± 0,0067 | 0,1158 | 0,1478 | 8522 |
| Ler cédula (decodificar + verificar) | 0,1974 ± 0,0082 | 0,1953 | 0,2357 | 5065 |
| Protótipo: RSA-1024 OAEP cifrar | 0,0229 ± 0,0016 | 0,0227 | 0,0284 | 43687 |
| Protótipo: RSA-1024 OAEP decifrar | 0,1184 ± 0,0265 | 0,1126 | 0,2592 | 8444 |
| Referência: RSA-2048 PSS assinar | 0,5463 ± 0,0764 | 0,5285 | 0,9351 | 1830 |
| Referência: RSA-2048 PSS verificar | 0,0453 ± 0,0039 | 0,0446 | 0,0583 | 22070 |

## E3 — Leitura óptica do QR

1000 cédulas distintas (3 cargos, votos sorteados), mesmas cédulas em todas as condições; sucesso = texto decodificado idêntico; IC de Wilson 95%; semente 2026

| Condição | QRCodeDetector (IC 95%) | QRCodeDetectorAruco (IC 95%) | Tempo mediano Aruco (ms) |
|---|---|---|---|
| limpo 4px modulo | 980/1000 (96,9–98,7%) | 1000/1000 (99,6–100,0%) | 6,3 |
| resolucao minima 2px modulo | 997/1000 (99,1–99,9%) | 1000/1000 (99,6–100,0%) | 4,4 |
| rotacao 7graus desfoque | 908/1000 (88,8–92,4%) | 1000/1000 (99,6–100,0%) | 7,2 |
| perspectiva e rotacao ate 25graus | 935/1000 (91,8–94,9%) | 1000/1000 (99,6–100,0%) | 11,6 |
| webcam 640x480 ruido jpeg70 | 826/1000 (80,1–84,8%) | 1000/1000 (99,6–100,0%) | 15,1 |
| termica desbotada 35pct contraste | 982/1000 (97,2–98,9%) | 1000/1000 (99,6–100,0%) | 6,2 |

Exemplos de cada condição: `resultados/e3-exemplo-*.png`.

## E4 — Custo computacional da apuração

ledger com synchronous=FULL (fsync por cédula); emissão das cédulas fora da medição; HD mecânico vs RAM

| Meio | Seção | Repetições | Processar 1 cédula (ms, média ± desvio, p95) | Verificar ledger (ms) | Gerar boletim (ms) | Tempo de máquina por seção (s) |
|---|---|---|---|---|---|---|
| hd mecanico (/dev/sdb2 ext4) | 400 cédulas | 10 | 112,972 ± 83,886 (p95 249,268) | 5,1 | 168,7 | 45,19 |
| ram tmpfs (tmpfs  tmpfs) | 400 cédulas | 10 | 0,282 ± 0,030 (p95 0,315) | 1,6 | 13,2 | 0,11 |
| ram tmpfs (tmpfs  tmpfs) | 5000 cédulas | 3 | 0,292 ± 0,047 (p95 0,366) | 20,4 | 171,7 | 1,46 |

Referência: em 2016 a leitura humana levou ≈ 15 s por cédula; o custo de máquina é desprezível frente a isso, mesmo com HD mecânico.

## E5 — Intervalo entre blocos (12/12 no ar)

timestamps (resolução 1 s) dos blocos 17815–19315: 12/12 no ar, antes dos testes de falha; uma lacuna de desligamento do cluster (> 60 s) excluída e contada à parte

* 1499 intervalos (blocos 17815..19315), 30,00 blocos/min.
* Intervalo: média 2 s, desvio 0,000 s, p99 2,0 s, máximo 2 s.
* Fração de intervalos de exatamente 2 s: 100,00%. Distribuição: {'2': 1499}.

## E6 — Ensaios nominais (12 seções cada)

Relatório detalhado: `resultados/e6-ensaios-nominais.md`.

| Indicador | Valor |
|---|---|
| Execuções com sucesso | 10 de 10 |
| Seções ancoradas / boletins que conferem na cadeia | 120 / 120 de 120 |
| Cédulas | 2750 (relidas rejeitadas 56, forjadas rejeitadas 31) |
| Duração por execução (s) | média 49,4, desvio 1,8, mín 47,6, máx 52,6 |
| Do boletim assinado à ancoragem (s) | média 2,5, mín 0,7, máx 4,7 |
| Nós que saíram do ar / quórum perdido | 0 / 0 |

Latência de ancoragem por seção (n = 120): média 2,53 s, mediana 2,55 s, p95 3,80 s, IC95 da média 2,38–2,68 s.

## E7 — Vazão com validadores fora (12 validadores, quórum 8)

5 repetições por k, janela 120 s, nós sorteados (semente 77), rede saudável antes de cada repetição

| Nós fora | No ar | Blocos/min (média ± desvio, mín–máx) | Maior intervalo entre blocos (s, média; máx) | Produziu em todas as repetições |
|---|---|---|---|---|
| 0 | 12 | 30,0 ± 0,0 (29,9–30,0) | 2; 2 | sim |
| 1 | 11 | 25,4 ± 0,5 (25,0–26,0) | 6; 6 | sim |
| 2 | 10 | 20,4 ± 1,8 (18,0–22,0) | 9,2; 14 | sim |
| 3 | 9 | 18,0 ± 0,0 (18,0–18,0) | 6; 6 | sim |
| 4 | 8 | 14,2 ± 1,4 (12,0–15,5) | 9,2; 14 | sim |

Por repetição (ordem de rodízio do proponente = .101 → .102 → .103 → .104 → .105 → .106 → .108 → .109 → .110 → .111 → .112 → .113):

| Nós fora | Rep. | Quais | Vizinhos no rodízio | Blocos/min | Maior pausa (s) |
|---|---|---|---|---|---|
| 2 | 1 | .102, .105 | não | 22,0 | 6 |
| 2 | 2 | .109, .110 | sim | 18,0 | 14 |
| 2 | 3 | .111, .104 | não | 21,0 | 6 |
| 2 | 4 | .103, .110 | não | 22,0 | 6 |
| 2 | 5 | .112, .113 | sim | 19,0 | 14 |
| 3 | 1 | .110, .101, .105 | não | 18,0 | 6 |
| 3 | 2 | .101, .109, .103 | não | 18,0 | 6 |
| 3 | 3 | .104, .110, .108 | não | 18,0 | 6 |
| 3 | 4 | .103, .106, .112 | não | 18,0 | 6 |
| 3 | 5 | .102, .113, .110 | não | 18,0 | 6 |
| 4 | 1 | .105, .110, .109, .104 | sim | 12,0 | 14 |
| 4 | 2 | .104, .113, .102, .111 | não | 15,0 | 6 |
| 4 | 3 | .104, .110, .109, .112 | sim | 13,5 | 14 |
| 4 | 4 | .102, .113, .104, .106 | não | 15,5 | 6 |
| 4 | 5 | .102, .113, .111, .109 | não | 15,0 | 6 |

## E8 — Recuperação após perda de quórum

5 de 12 parados (sem quórum) por d segundos; religar 1; medir RPC do religado e o próximo bloco; nós sorteados (semente 88)

| Parada (s) | n | Próximo bloco após religar (s): média ± desvio (mín–máx) | RPC do nó religado (s, média) |
|---|---|---|---|
| 10 | 5 | 51,5 ± 17,8 (38,4–71,1) | 8,8 |
| 30 | 5 | 83,5 ± 28,7 (70,2–134,8) | 9,0 |
| 60 | 5 | 288,5 ± 210,2 (134,7–518,8) | 8,9 |
| 120 | 3 | 433,3 ± 147,1 (263,5–518,5) | 8,9 |

Valores individuais (s): 10 s → 71,1 · 70,9 · 38,5 · 38,8 · 38,4; 30 s → 134,8 · 70,2 · 71,5 · 70,4 · 70,6; 60 s → 135,2 · 135,0 · 518,7 · 518,8 · 134,7; 120 s → 518,0 · 263,5 · 518,5.
Os tempos formam degraus (≈ 38, 70, 135, 263, 518 s) com diferenças de 4 s × 2ʳ: o temporizador de rodada do QBFT.

## E9 — Custo em gás e capacidade de ancoragem

12 contas × 100 registros por repetição, cada conta pelo próprio nó, sem pausa, gás estimado uma vez por conta; latência = timestamp do bloco − envio; 3 repetições; contrato novo implantado no início

| Operação do contrato | Gás |
|---|---|
| Implantar | 834064 |
| Criar eleição (12 apuradores) | 321814 |
| Registrar boletim | média 126590 (mín 126543, máx 143679; n = 3600) |
| Encerrar | 51445 |

| Repetição | Enviadas / incluídas | Taxa oferecida (tx/s) | Envio (s) | Vazão na cadeia (tx/s) | Blocos (vazios no meio) | Tx por bloco (média; máx) | Latência de inclusão (s: mediana; p95; máx) |
|---|---|---|---|---|---|---|---|
| 1 | 1200 / 1200 | 28,2 | 42,6 | 27,3 | 22 (0) | 54,5; 70 | 1,0; 1,9; 2,0 |
| 2 | 1200 / 1200 | 28,4 | 42,3 | 27,3 | 22 (0) | 54,5; 67 | 1,0; 1,9; 2,1 |
| 3 | 1200 / 1200 | 28,5 | 42,2 | 27,3 | 22 (0) | 54,5; 64 | 1,0; 1,9; 2,0 |

## E10 — Ensaios com queda transitória de 3 validadores

5 ensaios (25 eleitores/seção, votação 30 s); ao iniciar a apuração, 3 validadores sorteados param por 60 s (semente 1010)

* Execuções com sucesso: 5 de 5; duração média 114,1 s.
* Do boletim à ancoragem — seções cujo nó caiu: média 71,6 s (máx 75,8, n = 15); seções não afetadas: média 6,3 s (máx 16,4, n = 45).

## E11 — Convergência após reinício completo dos 12 nós

5 reinícios por modo; tempos contados a partir do último start

| Modo | Espalhamento dos starts (s) | Todos respondem (s) | Primeiro bloco (s) | Malha completa, 11 pares (s) |
|---|---|---|---|---|
| escalonado | 11,7 | 8,0 ± 0,4 | 12,7 ± 3,9 (máx 19,0) | 62,8 ± 3,3 |
| simultaneo | 1,3 | 11,0 ± 0,1 | 13,2 ± 0,1 (máx 13,3) | 68,2 ± 0,2 |

## E12 — Recursos por nó Besu durante os testes

Amostras de `docker stats` a cada 60 s em todos os nós durante E6–E11: 1611 amostras de memória.

* Memória por nó: média 389 MiB, p95 551 MiB, máximo 692 MiB (máquinas de 3,3–3,4 GB; heap da JVM limitado a 1 GB).
* CPU por nó: média 13,4%, p95 48,0%, máximo 379,5% (percentual de um núcleo, como reporta o Docker).

