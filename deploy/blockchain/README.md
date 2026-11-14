# Blockchain permissionada: ancoragem de boletins

Por que e o quê: `docs/04-blockchain.md`. Resumo: **nenhum voto vai para a cadeia**. Vão só o id da eleição,
o hash de cada boletim assinado com o hash do ledger da seção, e o hash do mural no encerramento.

## Simulação nesta máquina (um comando)

Requisitos: Docker (usuário no grupo `docker`) e o venv do projeto com `pip install -e ".[blockchain,dev]"`.

```bash
deploy/blockchain/simular.sh              # 4 validadores
deploy/blockchain/simular.sh 7 --falhas   # 7 validadores + teste de queda e recuperação
```

O script gera a rede, sobe um contêiner Besu por validador, implanta o contrato, roda uma eleição de
demonstração com 30 eleitores, ancora o boletim, confirma que recusas funcionam e consulta o registro num
nó diferente do que gravou. Com `--falhas`, derruba nós até perder o quórum e mede a recuperação.

Ferramentas soltas:

| Comando | O que faz |
|---|---|
| `besu/gerar-rede.sh N` | genesis QBFT + chaves de N validadores em `besu/rede/` (não versionado) |
| `besu/rede-local.sh subir\|status\|derrubar K\|religar K\|parar\|limpar` | gerencia os contêineres locais |
| `python status_rede.py` | estado de cada nó, pares, quórum |
| `python status_rede.py --dot \| dot -Tsvg -o rede.svg` | a rede como **grafo** de conexões (Graphviz) |
| `python ancorar.py ...` | implantar, criar, registrar, encerrar, consultar (veja `--help`) |
| `python compilar.py` | recompila o contrato (alvo EVM *London*) |

## Resultados medidos (2026-11-14, Besu 26.11.0, 4 validadores em Docker num i7 de 8 núcleos)

| Cenário | Resultado |
|---|---|
| 4 de 4 no ar | 1 bloco a cada 2 s (≈ 15 por 30 s) |
| 3 de 4 (1 fora) | continua, mais lento: 9 a 18 blocos por 30 s, conforme a vez do nó caído propor |
| 2 de 4 (2 fora) | **para** — 0 blocos, como prevê o QBFT (quórum ⌈2N/3⌉ = 3) |
| Recuperação ao religar 1 nó | 34 s após 10 s de parada · 66 s após ~30 s · 131 s após 60 s |
| Integridade | após todas as quedas, os 4 nós na mesma altura e o boletim ancorado intacto em todos |
| Custo | zero (rede própria, `gasPrice` 0) · ancorar uma seção = 1 transação |

A recuperação cresce com o tempo de parada porque o QBFT **dobra o tempo de espera** a cada rodada sem quórum.
Na prática, a regra operacional é: **nunca deixe a rede perder o quórum.** Com 13 validadores ela tolera 4 máquinas
fora ao mesmo tempo.

Problemas encontrados e corrigidos na simulação: o contrato compilado com o padrão do solc 0.8.26 usava a
instrução `PUSH0`, que a rede (regras *London*) rejeita; o `ancorar.py` fixava `gasPrice` 0 (só funcionava na
Besu); endereços de bootnode com nome de host em vez de IP, que o Besu não aceita sem configuração extra.

## No laboratório

0. Confira as máquinas: `besu/verificar-cluster.sh <usuário> <IP1> <IP2> ...` lista RAM, disco, Docker,
   imagem do Besu, relógio, internet, porta 30303 e firewall de cada uma, com o comando que resolve cada pendência.
1. Na máquina da comissão: `besu/gerar-rede.sh 13` (ou 4). Copie `rede/genesis.json` e `rede/node1/key.pub` para
   **todas** as máquinas, e `rede/nodeK/key` **só** para a máquina K.
2. Em cada máquina: `besu/no-lab.sh K <IP desta máquina> <IP da máquina do node1>`. Libere a porta 30303 (TCP e
   UDP) entre as máquinas.
3. Confira de qualquer máquina: `python status_rede.py --rpc http://IP1:8545 http://IP2:8545 ...` (suba os nós com
   `RPC_PUBLICO=1` para o RPC ser acessível na LAN — só na rede do laboratório).
4. Cada nó Besu usa ~1–2 GB de RAM em repouso; confira as máquinas antigas antes.

Comece com 3 ou 4 máquinas, depois as 13. Em produção, os validadores devem ser operados por partes distintas
(comissão, chapas, entidade estudantil, auditor) e as contas de apuração não devem ser as chaves dos validadores
— aqui elas coincidem só para simplificar o ensaio.
