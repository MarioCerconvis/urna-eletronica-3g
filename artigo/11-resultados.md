# 11 — Resultados [todos MEDIDOS]

Dados brutos em `anexos/dados-medicoes.json` e `anexos/dados-falhas-cluster.csv`.

## 11.1 Correção funcional

* 59/59 testes automatizados passando; CI verde em Python 3.10 e 3.12.
* Demonstração (P2): 40 cédulas aceitas; releitura → "duplicada"; cédula forjada → "inválida"; boletim assinado e
  verificado; ledger íntegro com 42 registros (abertura + 40 cédulas + encerramento).
* Testes de adulteração: alterar o conteúdo de um registro do ledger, ou remover um registro, é detectado pela
  verificação da cadeia; boletim com um campo alterado ou assinado por outra chave é rejeitado (inclusive pelo
  mural, HTTP 400); segundo boletim diferente para a mesma seção → HTTP 409.

## 11.2 Cédula e QR

| Métrica | Valor |
|---|---|
| carga binária (3 cargos, seção "001") | 106 bytes |
| texto do QR | 147 caracteres |
| versão do QR (correção M) | 8 |
| tempo para assinar uma cédula | ≈ 0,17 ms (i7-4770) |

| Detector (40 cédulas distintas) | Acertos |
|---|---|
| `QRCodeDetector`, escala 5, borda 3 | 37/40 |
| `QRCodeDetector`, escalas 5–10, borda 4 | 36–37/40 (as falhas foram de **detecção**, não de decodificação) |
| `QRCodeDetectorAruco`, escalas 4, 5, 6, 8 | 40/40 |
| `QRCodeDetectorAruco`, rotação 7° + escala 0,9 + desfoque 3×3 | 40/40 |

Consequência de projeto: o leitor por câmera usa o detector ArUco, com o clássico como segunda tentativa.

## 11.3 Rede local simulada (4 validadores, ambiente B)

| Cenário | Resultado |
|---|---|
| 4/4 no ar | 1 bloco a cada 2 s (6 blocos em 12 s; ~15 por 30 s) |
| 3/4 (1 fora) | continua, mais lento: 3 blocos/12 s; 18 blocos/60 s; 9 blocos/30 s em outra execução |
| 2/4 (2 fora) | para: 0 blocos |
| recuperação após 10 s parada | 34 s |
| recuperação após ~30 s parada | 66 s |
| recuperação após 60 s parada | 131 s |
| integridade após todas as quedas | 4 nós na mesma altura; boletim ancorado presente |
| ancoragem e recusas | boletim gravado pelo nó 2, consultado no nó 4, "confere: SIM"; conta não autorizada e seção repetida recusadas |
| simulação completa (`simular.sh`, sem falhas) | ≈ 1 min |

**Observação central:** o tempo de recuperação cresce com a duração da parada, porque o QBFT dobra o tempo de espera
a cada rodada sem quórum (4, 8, 16, 32 s…). Regra operacional derivada: **evitar perder o quórum**.

## 11.4 Cluster do LAOB

### Preparação

| Etapa | Resultado |
|---|---|
| verificação das 13 máquinas | 12 aptas; 1 sem SSH por chave (excluída) |
| download da imagem do Besu nas 12 máquinas, em paralelo | 94 s |
| memória por nó Besu | ≈ 287–290 MiB (rede de 4); 331–375 MiB (rede de 12) |

### 4 validadores (.101–.104)

* Produzindo após ~1 min; diferença momentânea de 1 bloco entre nós (propagação).
* Contrato implantado (bloco 29), eleição criada (bloco 30), boletim ancorado (bloco 31) pelo apurador; consulta pelo
  .104 confere com o arquivo.

### 12 validadores (.101–.106, .108–.113)

| Cenário | Resultado |
|---|---|
| subida escalonada dos 12 (≈ 56 s entre o 1º e o 12º) | todos no bloco 0 por ~30 s após o último subir; depois todos no bloco 7 juntos (rodadas se alinhando) |
| topologia | malha completa: cada nó com 11 pares (66 conexões) após a descoberta; no início, 3 a 11 pares por nó |
| 12/12 no ar | 15 blocos em 30 s; 3 blocos em 5 s |
| 3 fora (9/12) | continua: 23 blocos em 121 s |
| 4 fora (8/12, limite teórico) | continua aos solavancos: 16 blocos em 182 s; alturas a cada 15 s: 96 96 96 101 104 104 104 104 109 112 112 112 (pausas de 30–45 s) |
| 4 fora, janela de 30 s | 0 blocos (janela inteira dentro de uma pausa) |
| 5 fora (7/12) | para |
| religar 1 nó após a parada | voltou a produzir em 131 s |
| ancoragem | contrato (bloco 27), eleição (28), boletim (29); conta não autorizada recusada; consulta pelo .113 confere |

### Ensaios de eleição (P7)

| Ensaio | Seções | Cédulas | Blocos de ancoragem | Encerramento | Observações |
|---|---|---|---|---|---|
| rede local, com falha injetada | 4 | 36 | 4583 (todas) | bloco 4584 | 2 de 4 nós parados durante a apuração: seções aguardaram ("rede sem quórum" / "nó fora do ar"); rede ficou 115 s sem blocos (60 s após o quórum voltar); depois as 4 seções ancoraram no mesmo bloco |
| cluster | 12 | 137 | 1072–1079 | bloco 1080 | releituras e cédulas forjadas rejeitadas; nenhum falso alarme de queda |
| cluster (iniciado pelo operador) | 12 | 50 | 1433–1438 | encerrada | registros lidos diretamente do contrato via nó .113 batem com o painel, seção a seção |

Resultado do ensaio do operador (50 cédulas; candidatos fictícios do conjunto de demonstração): Presidente — 23 × 21,
5 brancos, 1 nulo; Senador — 17 × 15 × 14, 1 branco, 3 nulos; Deputado — 23 × 18, 5 brancos, 4 nulos.

## 11.5 Defeitos revelados pelos experimentos (e corrigidos)

| Defeito | Onde apareceu | Causa | Correção |
|---|---|---|---|
| "Invalid opcode: 0x5f" ao implantar o contrato | rede local | solc ≥ 0.8.20 emite `PUSH0` (Shanghai); a rede usa regras London | compilar para EVM London |
| script de ancoragem só funcionava com preço de gás zero | EVM de teste | `gasPrice` fixo em 0 | usar o preço informado pela rede |
| nós não se conectavam no script original | revisão para a simulação | Besu não aceita nome de host no enode sem DNS habilitado | bootnode por IP fixo |
| deriva de relógio falsa (4 s → 23 s, crescente) | verificação do cluster | comparação com a hora do início do laço | comparar no meio de cada conexão SSH |
| status "produzindo" com a rede parada | cluster (subida dos 12) | status baseado só no nº de nós vivos | exigir avanço da altura entre duas leituras |
| falso "nó fora do ar" no painel | ensaio local | apuração com fsync no laço de eventos atrasou as consultas | apuração em thread própria; queda só após 2 falhas seguidas |
| erro de thread do SQLite no ensaio | ensaio local | ledger aberto numa thread e usado em outra | ledger aberto e usado na mesma thread |

Valor para o artigo: três dos defeitos (PUSH0, preço de gás, bootnode) só aparecem ao executar contra uma rede
real — reforça o argumento de testar a camada de blockchain fora de simuladores.
