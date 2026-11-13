# Blockchain permissionada (opcional): ancoragem de boletins

Por que e o quê: `docs/04-blockchain.md`. Resumo: **nenhum voto vai para a cadeia** — só o id da eleição, o hash de
cada boletim assinado + hash do ledger da seção, e o hash do mural no encerramento.

## Componentes

* `contracts/RegistroEleitoral.sol` — contrato (Solidity 0.8). `compilar.py` gera `contracts/RegistroEleitoral.json`
  (ABI + bytecode) com `py-solc-x`.
* `ancorar.py` — implanta o contrato, cria a eleição (lista de apuradores autorizados), registra boletins, encerra e
  consulta. Recalcula o hash do boletim com `urna3g.boletim`.
* `besu/` — rede QBFT de 4 validadores (Hyperledger Besu) para ensaio em uma máquina (`gerar-rede.sh`, Docker) e
  base para o cluster.
* `../../tests/test_blockchain.py` — testa o contrato em uma EVM em memória (`web3[tester]`); pulado se o extra não
  estiver instalado ou se o contrato não tiver sido compilado.

## Ensaio em uma máquina

```bash
pip install 'urna3g[blockchain]'
python deploy/blockchain/compilar.py
deploy/blockchain/besu/gerar-rede.sh && (cd deploy/blockchain/besu && docker compose up -d)
export URNA3G_ETH_KEY=0x$(cat deploy/blockchain/besu/node1/key)      # conta do validador 1 como "autoridade" de teste
python deploy/blockchain/ancorar.py --rpc http://localhost:8545 implantar
python deploy/blockchain/ancorar.py --rpc http://localhost:8545 --contrato 0x... criar \
    --eleicao minha-eleicao/eleicao/eleicao.json --apuradores 0xEnderecoApurador001
python deploy/blockchain/ancorar.py --rpc http://localhost:8545 --contrato 0x... registrar --boletim saida/boletim-001.json
```

## No cluster (13 máquinas)

1. Rode `gerar-rede.sh` **uma vez** na máquina da comissão; entregue `nodeN/key` a cada parte validadora
   (comissão, chapas, DCE, auditor) — cada uma leva o seu diretório para a sua máquina.
2. Em cada validador: `docker run -d --name besu -p 30303:30303 -p 8545:8545 -v $PWD/genesis.json:/config/genesis.json
   -v $PWD/key:/config/key -v besu-data:/data hyperledger/besu:latest --genesis-file=/config/genesis.json
   --node-private-key-file=/config/key --data-path=/data --min-gas-price=0 --rpc-http-enabled --rpc-http-host=0.0.0.0
   --p2p-host=<IP da máquina> --bootnodes=enode://<key.pub do node1 sem 0x>@<IP do node1>:30303`
3. Observadores (demais máquinas): mesmo comando **sem** `--node-private-key-file` (gera chave própria; não valida,
   só replica e serve RPC aos fiscais).
4. Cada apurador precisa de uma conta Ethereum (endereço) autorizada em `criarEleicao`; com `--min-gas-price=0` e
   `zeroBaseFee` não há custo. A chave privada dessa conta fica na máquina de apuração, ao lado de `apuracao-ID.key`.

> Estado: `tests/test_blockchain.py` testa o contrato em EVM local, mas exige o artefato compilado (`compilar.py`
> baixa o solc); nesta primeira versão ele **ainda não foi executado**. A rede Besu é um roteiro de implantação
> **não exercitado pela CI**.
