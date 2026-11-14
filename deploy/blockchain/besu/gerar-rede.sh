#!/usr/bin/env bash
# Gera genesis.json (QBFT) e as chaves de N validadores com o próprio Besu (via Docker).
#
#   ./gerar-rede.sh            # 4 validadores (tolera 1 falha)
#   ./gerar-rede.sh 13         # 13 validadores (tolera 4 falhas) — experimento no cluster
#
# Saída em ./rede/:
#   genesis.json               igual para TODOS os nós (copie para cada máquina)
#   nodeK/key, nodeK/key.pub   chave do validador K (entregue só a quem opera o nó K)
#   validadores.txt            nó → endereço (conta) do validador
# Contas de teste: cada endereço de validador recebe saldo no genesis, para poder ser usado como
# "autoridade" ou "apurador" nos ensaios (em produção as contas de apuração são outras; ver README).
set -euo pipefail
cd "$(dirname "$0")"
N="${1:-4}"
IMG="${BESU_IMAGE:-hyperledger/besu:26.11.0}"
[ "$N" -ge 1 ] || { echo "N inválido"; exit 1; }
if [ -d rede ]; then
  echo "erro: ./rede já existe. Apague (rm -rf rede) se quiser gerar uma rede NOVA — os dados antigos ficam inválidos." >&2
  exit 1
fi
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
sed "s/\"count\": [0-9]*/\"count\": $N/" qbftConfigFile.json > "$TMP/config.json"
docker run --rm -u "$(id -u):$(id -g)" -v "$TMP:/data" "$IMG" operator generate-blockchain-config \
  --config-file=/data/config.json --to=/data/saida --private-key-file-name=key >/dev/null
mkdir -p rede
: > rede/validadores.txt
k=1
for d in "$TMP"/saida/keys/*/; do
  addr=$(basename "$d")
  mkdir -p "rede/node$k/data"
  cp "$d/key" "$d/key.pub" "rede/node$k/"
  chmod 600 "rede/node$k/key"
  echo "node$k $addr" >> rede/validadores.txt
  k=$((k+1))
done
# saldo de teste para as contas dos validadores (gasPrice é 0 nesta rede, mas carteiras/ferramentas
# costumam exigir saldo > 0 para estimar transações)
python3 - "$TMP/saida/genesis.json" rede/genesis.json rede/validadores.txt <<'PY'
import json, sys
g = json.load(open(sys.argv[1]))
for linha in open(sys.argv[3]):
    _, addr = linha.split()
    g["alloc"][addr.lower().removeprefix("0x")] = {"balance": "0x56bc75e2d63100000"}  # 100 ETH de teste
json.dump(g, open(sys.argv[2], "w"), indent=2)
PY
echo "rede gerada com $N validador(es) em $(pwd)/rede"
cat rede/validadores.txt
