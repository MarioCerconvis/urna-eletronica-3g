#!/usr/bin/env bash
# Simulação da rede QBFT NESTA máquina: um contêiner Besu por validador, numa rede Docker com IPs fixos.
#
#   ./rede-local.sh subir          sobe todos os nós de ./rede (gere antes com ./gerar-rede.sh)
#   ./rede-local.sh status         altura do bloco e nº de pares de cada nó
#   ./rede-local.sh derrubar K     para o nó K (simula máquina desligada)
#   ./rede-local.sh religar K      sobe o nó K de novo (ele sincroniza sozinho)
#   ./rede-local.sh parar          para todos (dados preservados em rede/nodeK/data)
#   ./rede-local.sh limpar         para tudo e APAGA a cadeia (mantém chaves e genesis)
#
# RPC do nó K: http://127.0.0.1:$((8544+K))   (só localhost)
set -euo pipefail
cd "$(dirname "$0")"
IMG="${BESU_IMAGE:-hyperledger/besu:26.11.0}"
REDE_DOCKER=urna3g-besu
SUBNET=172.28.0
nos() { ls -d rede/node* 2>/dev/null | sed 's#rede/node##' | sort -n; }
ip_no() { echo "$SUBNET.$((10+$1))"; }
porta_no() { echo $((8544+$1)); }

subir_no() {
  local k=$1 boot=""
  if [ "$k" -ne 1 ]; then
    boot="--bootnodes=enode://$(sed 's/^0x//' rede/node1/key.pub)@$(ip_no 1):30303"
  fi
  docker rm -f "besu-node$k" >/dev/null 2>&1 || true
  docker run -d --name "besu-node$k" --network "$REDE_DOCKER" --ip "$(ip_no "$k")" \
    -u "$(id -u):$(id -g)" \
    -p "127.0.0.1:$(porta_no "$k"):8545" \
    -v "$PWD/rede/genesis.json:/config/genesis.json:ro" \
    -v "$PWD/rede/node$k/key:/config/key:ro" \
    -v "$PWD/rede/node$k/data:/data" \
    "$IMG" \
    --genesis-file=/config/genesis.json --data-path=/data --node-private-key-file=/config/key \
    --min-gas-price=0 --p2p-host="$(ip_no "$k")" --p2p-port=30303 \
    --rpc-http-enabled --rpc-http-host=0.0.0.0 --rpc-http-api=ETH,NET,WEB3,QBFT,ADMIN,TXPOOL \
    --host-allowlist="*" --rpc-http-cors-origins="*" \
    --logging=WARN $boot >/dev/null
  echo "node$k  ip $(ip_no "$k")  rpc http://127.0.0.1:$(porta_no "$k")"
}

rpc() {  # rpc PORTA METODO [PARAMS_JSON]
  curl -s -m 3 -X POST -H 'Content-Type: application/json' \
    --data "{\"jsonrpc\":\"2.0\",\"method\":\"$2\",\"params\":${3:-[]},\"id\":1}" "http://127.0.0.1:$1" \
    | python3 -c 'import sys,json; r=json.load(sys.stdin).get("result"); print(int(r,16) if isinstance(r,str) and r.startswith("0x") else r)' 2>/dev/null || echo "-"
}

case "${1:-}" in
  subir)
    [ -f rede/genesis.json ] || { echo "rode ./gerar-rede.sh primeiro" >&2; exit 1; }
    docker network inspect "$REDE_DOCKER" >/dev/null 2>&1 || docker network create --subnet "$SUBNET.0/24" "$REDE_DOCKER" >/dev/null
    for k in $(nos); do subir_no "$k"; done ;;
  status)
    printf "%-7s %-8s %-7s %-6s\n" nó bloco pares estado
    for k in $(nos); do
      estado=$(docker inspect -f '{{.State.Status}}' "besu-node$k" 2>/dev/null || echo ausente)
      printf "%-7s %-8s %-7s %-6s\n" "node$k" "$(rpc "$(porta_no "$k")" eth_blockNumber)" "$(rpc "$(porta_no "$k")" net_peerCount)" "$estado"
    done ;;
  derrubar) docker stop "besu-node${2:?nó}" >/dev/null && echo "node$2 parado" ;;
  religar)  subir_no "${2:?nó}" ;;
  parar)    for k in $(nos); do docker rm -f "besu-node$k" >/dev/null 2>&1 || true; done; echo "nós parados" ;;
  limpar)
    for k in $(nos); do docker rm -f "besu-node$k" >/dev/null 2>&1 || true; rm -rf "rede/node$k/data"; mkdir -p "rede/node$k/data"; done
    docker network rm "$REDE_DOCKER" >/dev/null 2>&1 || true
    echo "cadeia apagada (chaves e genesis mantidos)" ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
