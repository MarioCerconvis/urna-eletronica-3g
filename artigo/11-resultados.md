# 11 — Resultados [todos MEDIDOS]

Fonte principal: a **bateria de experimentos E1–E12 de 22/11/2026** (scripts em `experimentos/`, dados brutos em
`anexos/dados/`, relatório consolidado em `anexos/RELATORIO-EXPERIMENTOS.md`). As medições de 13–14/11 (rede local
e primeiros testes no cluster, §11.10) são preliminares, com uma execução por condição; quando há conflito, valem
os números da bateria.

Ambientes (detalhes em `10`): **PC-A** (i7-4770, 27 GB, HD mecânico WD10SPZX 5 400 rpm, Ubuntu 24.04) executou
E1–E5 e o início de E7; o **computador principal do cluster** (i7-4790, 15 GB, Ubuntu 24.04) executou o restante de
E7 e E6, E8–E11; os **12 nós** (Ubuntu 26.04, 3,3–3,4 GB de RAM) rodaram os validadores Besu 26.11.0.

## 11.1 Correção funcional

* 61 testes automatizados passando (inclui teste de regressão do coletor e do gerador de relatório), integração contínua verde em Python 3.10
  e 3.12.
* **E6 — 10 ensaios nominais no cluster** (12 seções cada; 25 eleitores-alvo por seção; votação de 30 s):
  * 10/10 execuções bem-sucedidas; **120/120 seções ancoradas e 120/120 boletins idênticos ao registrado na
    blockchain** (conferência lendo o contrato por um nó diferente do que gravou);
  * 2 750 cédulas apuradas; **56 releituras e 31 cédulas forjadas, todas rejeitadas** (as falhas são injetadas de
    propósito pelo ensaio: releitura em ~50% das seções, cédula assinada com outra chave em ~25%);
  * duração por execução: 49,4 ± 1,8 s (47,6–52,6); apuração por seção 4,3 ± 0,6 s;
  * **do boletim assinado à ancoragem confirmada: média 2,53 s, mediana 2,55 s, p95 3,80 s (n = 120;
    IC95 da média 2,38–2,68 s)** — pouco mais de um bloco;
  * nenhum nó saiu do ar e nenhum falso alarme.

## 11.2 Cédula e QR (E1, determinístico)

| Votos por cédula | Bytes (seção "001") | Caracteres no QR | Versão do QR (correção M) | Versão com seção de 16 bytes |
|---|---|---|---|---|
| 1 | 98 | 136 | 8 (49×49 módulos) | 9 |
| 2 | 102 | 141 | 8 | 9 |
| **3** | **106** | **147** | **8** | 9 |
| 5 | 114 | 157 | 8 | 9 |
| 10 | 134 | 184 | 9 (53×53) | 10 |
| 20 | 174 | 237 | 10 (57×57) | 11 |
| 40 (máximo) | 254 | 344 | 12 (65×65) | 13 |

* **Comparação com o protótipo de 2016:** o QR carregava 128 bytes de RSA-1024 em base64 (175 caracteres) com
  correção **L** → versão 8. A cédula nova com 3 votos também é **versão 8**, mas com correção **M** (≈15% de área
  recuperável contra ≈7%) e **autenticada**. Ou seja: mesmo tamanho físico, mais robustez e autenticidade — não um
  QR "menor", como afirmava uma versão anterior deste dossiê.

## 11.3 Desempenho criptográfico (E2; n = 10 000 por operação; PC-A, um núcleo)

| Operação | Média ± desvio (ms) | p99 (ms) | Operações/s |
|---|---|---|---|
| Ed25519 — assinar 106 B | 0,035 ± 0,005 | 0,062 | 28 629 |
| Ed25519 — verificar | 0,111 ± 0,006 | 0,139 | 9 033 |
| **Emitir cédula completa** (montar + assinar) | **0,117 ± 0,007** | 0,148 | 8 522 |
| **Ler cédula** (decodificar + verificar) | **0,197 ± 0,008** | 0,236 | 5 065 |
| Protótipo: RSA-1024 OAEP cifrar / decifrar | 0,023 / 0,118 | 0,028 / 0,259 | 43 687 / 8 444 |
| Referência: RSA-2048 PSS assinar / verificar | 0,546 / 0,045 | 0,935 / 0,058 | 1 830 / 22 070 |

Leitura: a criptografia é irrelevante para o tempo de votação e de apuração (frações de milissegundo). Assinar com
Ed25519 é ~15× mais rápido que assinar com RSA-2048.

## 11.4 Leitura óptica do QR (E3; 1 000 cédulas distintas × 6 condições; IC de Wilson 95%)

| Condição simulada | `QRCodeDetector` (clássico) | `QRCodeDetectorAruco` |
|---|---|---|
| limpo, 4 px por módulo | 980/1000 (96,9–98,7%) | **1000/1000 (99,6–100%)** |
| resolução mínima, 2 px por módulo | 997/1000 (99,1–99,9%) | **1000/1000** |
| rotação 7° + escala 0,9 + desfoque 3×3 | 908/1000 (88,9–92,4%) | **1000/1000** |
| perspectiva leve + rotação até ±25° | 935/1000 (91,8–94,9%) | **1000/1000** |
| webcam 640×480, ruído σ = 8, JPEG q = 70 | 826/1000 (80,1–84,8%) | **1000/1000** |
| impressão térmica desbotada (35% de contraste) + ruído | 982/1000 (97,2–98,9%) | **1000/1000** |

* Com o detector ArUco: **6 000/6 000** leituras corretas; tempo mediano 4–15 ms por imagem.
* O detector clássico do OpenCV falha sobretudo em **detectar** o código (não em decodificá-lo), com pior caso na
  condição de webcam (82,6%). O sistema usa o ArUco com o clássico como segunda tentativa.
* Imagens de exemplo de cada condição: `anexos/dados/e3-exemplo-*.png`.
* Limitação: imagens sintéticas (geradas e degradadas por software), não fotos de papel térmico real.

## 11.5 Custo computacional da apuração (E4)

| Armazenamento do ledger | Seção | Repetições | Processar 1 cédula (ms) | Tempo de máquina por seção |
|---|---|---|---|---|
| HD mecânico 5 400 rpm (fsync real) | 400 cédulas | 10 | 113 ± 84 (p95 249) | **45 s** |
| RAM (tmpfs; fsync sem custo) | 400 cédulas | 10 | 0,28 ± 0,03 (p95 0,32) | 0,11 s |
| RAM (tmpfs) | 5 000 cédulas | 3 | 0,29 ± 0,05 (p95 0,37) | 1,5 s |

* O custo de CPU é ~0,3 ms por cédula e escala linearmente; no HD mecânico, ~99,7% do tempo é espera pela
  gravação durável (uma confirmação física por cédula, para resistir a queda de energia).
* Verificar a cadeia do ledger: 5 ms (400 cédulas, HD) e 20 ms (5 000, RAM); gerar o boletim: 13–170 ms.
* **Comparação com 2016:** a leitura humana levou ≈ 15 s por cédula (≈ 1h40 para 400); o custo de máquina, mesmo
  no HD lento, é 45 s por seção — **< 1% do tempo da apuração pública**.

## 11.6 Rede QBFT em operação normal (E5)

* 1 499 intervalos entre blocos consecutivos (blocos 17 815–19 315, 12/12 validadores no ar): **100% exatamente
  2 s** (média 2,000 s, desvio 0) — 30,0 blocos/min, sem nenhum atraso, inclusive durante os ensaios.
* Nesse trecho há uma lacuna de 8,2 dias em que o cluster esteve desligado; foi excluída (intervalos > 60 s).

## 11.7 Tolerância a falhas (E7; 12 validadores, quórum 8; 5 sorteios por nível; janela de 120 s)

| Nós fora | No ar | Blocos/min: média ± desvio (mín–máx) | Maior pausa entre blocos | Produziu em todas |
|---|---|---|---|---|
| 0 | 12 | 30,0 ± 0,0 | 2 s | sim |
| 1 | 11 | 25,4 ± 0,5 (25,0–26,0) | 6 s | sim |
| 2 | 10 | 20,4 ± 1,8 (18,0–22,0) | 6 ou 14 s | sim |
| 3 | 9 | 18,0 ± 0,0 | 6 s | sim |
| 4 (limite) | 8 | 14,2 ± 1,4 (12,0–15,5) | 6 ou 14 s | sim |
| 5 | 7 | **0** (sem quórum; ver E8) | — | — |

* **Achado mecanístico (15/15 casos):** a pausa máxima é de **14 s exatamente quando dois validadores desligados são
  vizinhos na ordem de rodízio do proponente** (duas trocas de rodada seguidas: 4 s + 8 s de espera + 2 s), e de
  6 s quando nenhum par é vizinho (uma troca: 4 s + 2 s). Por acaso, nenhum dos 5 sorteios com 3 fora tinha
  vizinhos — daí a variância zero nesse nível. Consequência: a vazão sob falhas depende menos de quantos nós caem e
  mais de caírem nós consecutivos no rodízio.
* Mesmo no limite teórico (4 de 12 fora) a rede produziu em todas as repetições, com ~47% da vazão nominal.
* Tempo para a rede voltar a ficar saudável depois de religar: 16–26 s.

## 11.8 Recuperação após perda de quórum (E8; 5 de 12 fora → religar 1)

| Parada (s) | n | Próximo bloco após religar (s), cada repetição | Mediana |
|---|---|---|---|
| 10 | 5 | 71,1 · 70,9 · 38,5 · 38,8 · 38,4 | 38,8 |
| 30 | 5 | 134,8 · 70,2 · 71,5 · 70,4 · 70,6 | 70,6 |
| 60 | 5 | 135,2 · 135,0 · 518,7 · 518,8 · 134,7 | 135,2 |
| 120 | 3 | 518,0 · 263,5 · 518,5 | 518,0 |

* O nó religado responde ao RPC em 8,5–9,2 s (subida do contêiner/JVM) em todos os casos.
* **Os tempos não se espalham: caem em degraus de ≈ 38, 70, 135, 263 e 518 s**, cujas diferenças (32, 65, 128,
  255 s) são 4 s × 2³…2⁶ — exatamente o temporizador de rodada do QBFT, que dobra a cada rodada sem quórum
  (`requesttimeoutseconds` = 4). A rede só retoma quando a rodada em curso expira; quanto mais longa a parada, maior a
  rodada em que os nós estão. Por isso a média (51 / 84 / 289 / 433 s) é enganosa; reportar os degraus e a mediana.
* Implicação operacional: perder o quórum por um minuto pode custar **quase 9 minutos** sem blocos depois que ele
  volta. Reduzir `requesttimeoutseconds` ou limitar o crescimento do temporizador encurta isso (trabalho futuro).

## 11.9 Ensaios com queda transitória (E10; 5 execuções; 3 validadores sorteados param 60 s ao iniciar a apuração)

* 5/5 execuções bem-sucedidas (todas as seções ancoradas e conferidas; quórum mantido: 9 de 12); duração
  114,1 s em média (contra 49,4 s sem falha).
* Do boletim à ancoragem: **seções cujo nó caiu 71,6 s em média (66–76 s, n = 15)** — os 60 s da queda mais a
  subida e sincronização do nó; **seções não afetadas 6,3 s (máx 16,4 s, n = 45)**, um pouco acima do nominal
  (2,5 s) por causa das trocas de rodada provocadas pelos nós fora.
* Comportamento correto do projeto: cada seção ancora pelo próprio nó e espera por ele, sem perder o boletim.

## 11.10 Reinício completo dos 12 nós (E11; 5 repetições por modo)

| Modo | Espalhamento dos starts | Todos respondem | Primeiro bloco novo | Malha completa (11 pares) |
|---|---|---|---|---|
| escalonado (um por vez) | 11,7 s | 8,0 ± 0,4 s | 12,7 ± 3,9 s (9,7–19,0) | 62,8 ± 3,3 s |
| simultâneo | 1,3 s | 11,0 ± 0,1 s | 13,2 ± 0,1 s | 68,2 ± 0,2 s |

* A cadeia volta a produzir ~13 s depois do último nó ligar, nos dois modos; a descoberta completa de pares leva
  ~1 min, mas não é necessária para o consenso (basta o quórum se enxergar).

## 11.11 Recursos por nó Besu (E12; amostras a cada 60 s durante E6–E11; 1 563 amostras)

* Memória do contêiner: **média 389 MiB, p95 552 MiB, máximo 692 MiB** (máquinas de 3,3–3,4 GB; heap limitado a 1 GB).
* CPU: média 13,5% de um núcleo, p95 48%; picos de até 380% durante a subida da JVM nos reinícios (E11).

## 11.12 Custo em gás e capacidade de ancoragem (E9)

| Operação do contrato | Gás (custo monetário zero nesta rede) |
|---|---|
| implantar | 834 064 |
| criar eleição (12 apuradores) | 321 814 |
| **registrar boletim** | **126 590 em média** (126 543–143 679; n = 3 600) |
| encerrar | 51 445 |

Rajadas (3 repetições; 12 contas × 100 registros, cada conta pelo próprio nó, sem pausa):

| Rep. | Enviadas / incluídas | Taxa oferecida | Vazão na cadeia | Blocos usados | Tx por bloco (média; máx) | Latência de inclusão (mediana; p95; máx) |
|---|---|---|---|---|---|---|
| 1 | 1 200 / 1 200 | 28,2 tx/s | 27,3 tx/s | 22 (nenhum vazio) | 54,5; 70 | 1,0 s; 1,9 s; 2,0 s |
| 2 | 1 200 / 1 200 | 28,4 tx/s | 27,3 tx/s | 22 | 54,5; 67 | 1,0 s; 1,9 s; 2,1 s |
| 3 | 1 200 / 1 200 | 28,5 tx/s | 27,3 tx/s | 22 | 54,5; 64 | 1,0 s; 1,9 s; 2,0 s |

* Todas as 3 600 transações entraram **no bloco seguinte ao envio** (latência máxima 2,1 s ≈ um período de bloco;
  valores levemente negativos no mínimo vêm da resolução de 1 s do timestamp do bloco).
* A rede **não saturou**: absorveu tudo o que foi oferecido. O limite foi o cliente (assinatura em Python, um fluxo
  por conta). Portanto, **27 tx/s é um limite inferior** da capacidade — equivale a mais de 90 mil boletins por hora,
  ordens de grandeza acima do necessário para uma eleição universitária (dezenas de seções).
* Uma primeira versão deste experimento (gás estimado a cada envio, latência medida só após todos os envios) foi
  descartada; ver §11.14.

## 11.13 Medições preliminares de 13–14/11 (uma execução por condição)

* Rede local, 4 validadores em Docker no PC-A: 1 fora → continua (3 blocos/12 s; 18 blocos/57 s); 2 fora → para;
  recuperação 34 s (após 10 s), 66 s (após ~30 s), 131 s (após 60 s) — compatível com os degraus de E8.
* Cluster com 4 validadores (.101–.104): produzindo, ancoragem e consulta entre nós corretas.
* Cluster com 12 validadores, primeira subida escalonada (≈ 56 s entre o 1º e o 12º nó): ~30 s até as rodadas se
  alinharem.
* Ensaio local com 2 de 4 nós parados durante a apuração: seções aguardaram; rede 115 s sem blocos; todas ancoraram
  no mesmo bloco ao voltar.
* Ensaios únicos no cluster (12 seções): 137 cédulas (blocos 1072–1079) e 50 cédulas (blocos 1433–1438), ambos
  encerrados e conferidos na cadeia.

## 11.14 Defeitos encontrados pelos experimentos

### No sistema (corrigidos)

| Defeito | Onde apareceu | Causa | Correção |
|---|---|---|---|
| "Invalid opcode: 0x5f" ao implantar o contrato | rede local | solc ≥ 0.8.20 emite `PUSH0` (Shanghai); a rede usa regras London | compilar para EVM London |
| script de ancoragem só funcionava com gás a preço zero | EVM de teste | `gasPrice` fixo em 0 | usar o preço informado pela rede |
| nós não se conectavam | preparação da simulação | Besu não aceita nome de host no enode sem DNS habilitado | bootnode por IP fixo |
| painel marcava 3 de 12 seções como "ancorando" para sempre (ensaio no lote preliminar) | cluster | o coletor fixava o limite de blocos **depois** de consultar os eventos e pulava os blocos produzidos durante a consulta | limite fixado antes da consulta + teste de regressão |
| falso "nó fora do ar" no painel | ensaio local | apuração com fsync no laço de eventos atrasou as consultas | apuração em thread própria; queda só após 2 falhas seguidas |
| status "produzindo" com a rede parada | subida dos 12 nós | status baseado só no nº de nós vivos | exigir avanço da altura |

### No método experimental (detectados e refeitos — relatar com transparência)

| Erro de método | Sintoma | Correção |
|---|---|---|
| E3: rotação sem margem cortava os cantos do QR | 533/1000 na condição de 25° | diagnóstico por ângulo (cortes a partir de ~15°); margem branca antes de girar; refeito (1000/1000); execução descartada arquivada |
| E5: janela de blocos incluía 8,2 dias de cluster desligado | "0,13 blocos/min" | excluir intervalos > 60 s; refeito |
| E9: gás estimado a cada envio e latência medida só após todos os envios | vazão limitada pelo cliente; "latência" de 48 s | gás fixo por conta, envio sem pausa, latência pelo timestamp do bloco; refeito |
| verificação do cluster: deriva de relógio crescente (4 → 23 s) | falsa pendência de NTP | comparar no meio de cada conexão SSH |
