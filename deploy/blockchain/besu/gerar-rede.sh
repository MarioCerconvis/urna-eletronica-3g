#!/usr/bin/env bash
# Gera genesis.json + chaves de 4 validadores QBFT com o Besu (via Docker) e um docker-compose.yml
# para ensaio em uma única máquina. Para o cluster real, copie cada diretório nodeN/ para uma máquina
# diferente e troque os hostnames node1..node4 pelos IPs (ver README.md).
set -euo pipefail
cd "$(dirname "$0")"
IMG="${BESU_IMAGE:-hyperledger/besu:latest}"
rm -rf rede && mkdir -p rede
docker run --rm -u "$(id -u)" -v "$PWD:/data" "$IMG" operator generate-blockchain-config \
  --config-file=/data/qbftConfigFile.json --to=/data/rede --private-key-file-name=key
i=1
for d in rede/keys/*/; do
  mkdir -p "node$i/data"
  cp "$d/key" "$d/key.pub" "node$i/"
  i=$((i+1))
done
cp rede/genesis.json genesis.json
PUB1=$(sed 's/^0x//' node1/key.pub)
{
  echo "services:"
  for n in 1 2 3 4; do
    cat <<YAML
  node$n:
    image: $IMG
    volumes: ["./genesis.json:/config/genesis.json:ro", "./node$n/key:/config/key:ro", "./node$n/data:/data"]
    command: >
      --genesis-file=/config/genesis.json --data-path=/data --node-private-key-file=/config/key
      --min-gas-price=0 --rpc-http-enabled --rpc-http-host=0.0.0.0 --rpc-http-api=ETH,NET,WEB3,QBFT
      --host-allowlist=* --rpc-http-cors-origins=all --p2p-port=30303
      $( [ "$n" -ne 1 ] && echo "--bootnodes=enode://$PUB1@node1:30303" )
    ports: ["$((8544+n)):8545"]
YAML
  done
} > docker-compose.yml
echo "pronto: docker compose up -d   (RPC dos nós em http://localhost:8545..8548)"
echo "contas dos validadores (use uma delas como autoridade/apurador para testes):"
for n in 1 2 3 4; do echo "  node$n: $(basename "$(dirname "$(ls rede/keys/*/key | sed -n ${n}p)")")"; done
