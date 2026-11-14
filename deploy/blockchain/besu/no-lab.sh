#!/usr/bin/env bash
# Sobe o nó K da rede QBFT em UMA máquina do laboratório (cada máquina roda um nó).
#
#   ./no-lab.sh K IP_DESTA_MAQUINA IP_DO_NODE1          # validador K (precisa de rede/nodeK/key)
#   ./no-lab.sh obs IP_DESTA_MAQUINA IP_DO_NODE1        # observador (sem chave de validador)
#   ./no-lab.sh parar
#
# Copie para a máquina: este script, rede/genesis.json, rede/node1/key.pub (para o bootnode) e,
# se for validador, rede/nodeK/key. Portas: 30303/tcp+udp (P2P, liberar entre as máquinas) e
# 8545/tcp (RPC; por padrão só localhost — use RPC_PUBLICO=1 para servir aos fiscais na LAN).
# Memória: BESU_HEAP limita o heap da JVM (padrão 1g; o nó usa ~1,5 GB no total). Máquinas com 4 GB: deixe 1g.
set -euo pipefail
cd "$(dirname "$0")"
IMG="${BESU_IMAGE:-hyperledger/besu:26.11.0}"
if [ "${1:-}" = "parar" ]; then docker rm -f besu >/dev/null 2>&1 && echo "nó parado"; exit 0; fi
K="${1:?K (número do validador) ou 'obs'}"; IP="${2:?IP desta máquina}"; IP1="${3:?IP do node1}"
[ -f rede/genesis.json ] || { echo "falta rede/genesis.json" >&2; exit 1; }
BIND="127.0.0.1:"; [ "${RPC_PUBLICO:-0}" = "1" ] && BIND=""
ARGS=(--genesis-file=/config/genesis.json --data-path=/data --min-gas-price=0
      --p2p-host="$IP" --p2p-port=30303 --rpc-http-enabled --rpc-http-host=0.0.0.0
      --rpc-http-api=ETH,NET,WEB3,QBFT,ADMIN --host-allowlist="*" --logging=WARN)
VOLS=(-v "$PWD/rede/genesis.json:/config/genesis.json:ro" -v "$PWD/dados:/data")
mkdir -p dados
if [ "$K" != "obs" ]; then
  [ -f "rede/node$K/key" ] || { echo "falta rede/node$K/key" >&2; exit 1; }
  VOLS+=(-v "$PWD/rede/node$K/key:/config/key:ro"); ARGS+=(--node-private-key-file=/config/key)
fi
if [ "$K" != "1" ]; then
  ARGS+=(--bootnodes="enode://$(sed 's/^0x//' rede/node1/key.pub)@$IP1:30303")
fi
docker rm -f besu >/dev/null 2>&1 || true
docker run -d --name besu --restart unless-stopped -u "$(id -u):$(id -g)" -e BESU_OPTS="-Xmx${BESU_HEAP:-1g}" \
  -p 30303:30303/tcp -p 30303:30303/udp -p "${BIND}8545:8545" "${VOLS[@]}" "$IMG" "${ARGS[@]}" >/dev/null
echo "nó $K no ar em $IP (P2P 30303, RPC ${BIND:-0.0.0.0:}8545)"
