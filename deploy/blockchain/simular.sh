#!/usr/bin/env bash
# Simulação completa NESTA máquina: rede Besu QBFT em Docker + eleição urna3g + ancoragem do boletim.
#
#   deploy/blockchain/simular.sh                 # 4 validadores
#   deploy/blockchain/simular.sh 7               # 7 validadores (tolera 2 falhas)
#   deploy/blockchain/simular.sh 4 --falhas      # também mede parada/recuperação derrubando nós
#
# Pré-requisitos: Docker (usuário no grupo docker) e o venv do projeto com o extra "blockchain".
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
BESU="$RAIZ/deploy/blockchain/besu"
PY="${PYTHON:-$RAIZ/.venv/bin/python}"
URNA="${URNA3G:-$RAIZ/.venv/bin/urna3g}"
N="${1:-4}"
FALHAS="${2:-}"
TRAB="$(mktemp -d /tmp/urna3g-sim.XXXX)"
A() { "$PY" "$RAIZ/deploy/blockchain/ancorar.py" "$@"; }
bloco() { curl -s -m 2 -X POST -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' "http://127.0.0.1:$1" \
  | "$PY" -c 'import sys,json;print(int(json.load(sys.stdin)["result"],16))' 2>/dev/null || echo -1; }

echo "== 1. rede com $N validador(es)"
if [ -d "$BESU/rede" ] && [ "$(ls -d "$BESU"/rede/node* | wc -l)" -ne "$N" ]; then
  echo "   ./rede existe com outro nº de nós; recriando"; "$BESU/rede-local.sh" parar >/dev/null; rm -rf "$BESU/rede"
fi
[ -d "$BESU/rede" ] || "$BESU/gerar-rede.sh" "$N" >/dev/null
"$BESU/rede-local.sh" subir >/dev/null
printf "   aguardando blocos"
for _ in $(seq 60); do [ "$(bloco 8545)" -ge 2 ] && break; printf "."; sleep 1; done; echo
"$PY" "$RAIZ/deploy/blockchain/status_rede.py" | sed 's/^/   /'

echo "== 2. contrato"
[ -f "$RAIZ/deploy/blockchain/contracts/RegistroEleitoral.json" ] || "$PY" "$RAIZ/deploy/blockchain/compilar.py"
SAIDA=$(A --rpc http://127.0.0.1:8545 --chave-arquivo "$BESU/rede/node1/key" implantar)
echo "$SAIDA"
END=$(echo "$SAIDA" | grep -o '0x[0-9a-fA-F]\{40\}')

echo "== 3. eleição simulada (urna3g demo, seção 001, 30 eleitores)"
"$URNA" demo --saida "$TRAB/s1" --eleitores 30 --pdfs 0 >/dev/null
ELEICAO="$TRAB/s1/eleicao/eleicao.json"
echo "   id da eleição: $("$URNA" eleicao id "$ELEICAO")"
APUR=$(sed -n 2p "$BESU/rede/validadores.txt" | cut -d' ' -f2)
A --rpc http://127.0.0.1:8545 --chave-arquivo "$BESU/rede/node1/key" --contrato "$END" criar --eleicao "$ELEICAO" --apuradores "$APUR"

echo "== 4. ancoragem do boletim (apurador = conta do node2, enviado ao node2)"
A --rpc http://127.0.0.1:8546 --chave-arquivo "$BESU/rede/node2/key" --contrato "$END" registrar --boletim "$TRAB/s1/boletim-001.json"
echo "   tentativas que DEVEM falhar:"
A --rpc http://127.0.0.1:8545 --chave-arquivo "$BESU/rede/node1/key" --contrato "$END" registrar --boletim "$TRAB/s1/boletim-001.json" 2>&1 | sed 's/^/     não autorizado → /' || true
A --rpc http://127.0.0.1:8546 --chave-arquivo "$BESU/rede/node2/key" --contrato "$END" registrar --boletim "$TRAB/s1/boletim-001.json" 2>&1 | sed 's/^/     repetido       → /' || true

echo "== 5. consulta em OUTRO nó (node$N) e conferência com o arquivo"
A --rpc "http://127.0.0.1:$((8544+N))" --contrato "$END" consultar --eleicao "$ELEICAO" --boletim "$TRAB/s1/boletim-001.json" | sed 's/^/   /'

if [ "$FALHAS" = "--falhas" ]; then
  quorum=$(( (2*N + 2)/3 )); toler=$(( N - quorum ))   # quórum QBFT = ⌈2N/3⌉
  echo "== 6. tolerância a falhas: quórum $quorum de $N, tolera $toler"
  for k in $(seq "$N" -1 $((N-toler+1))); do "$BESU/rede-local.sh" derrubar "$k" >/dev/null; done
  a=$(bloco 8545); sleep 30; b=$(bloco 8545); echo "   com $toler nó(s) fora: $((b-a)) blocos em 30 s (deve continuar, mais devagar; com todos: ~15)"
  k=$((N-toler)); "$BESU/rede-local.sh" derrubar "$k" >/dev/null
  a=$(bloco 8545); sleep 30; b=$(bloco 8545); echo "   com $((toler+1)) nó(s) fora: $((b-a)) blocos em 30 s (deve PARAR)"
  "$BESU/rede-local.sh" religar "$k" >/dev/null; t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt 300 ] && [ "$(bloco 8545)" -le "$b" ]; do sleep 1; done
  echo "   religando 1 nó: voltou a produzir em $(( $(date +%s) - t0 )) s"
  for k in $(seq "$N" -1 $((N-toler+1))); do "$BESU/rede-local.sh" religar "$k" >/dev/null; done
  sleep 15; "$PY" "$RAIZ/deploy/blockchain/status_rede.py" | tail -2 | sed 's/^/   /'
fi

echo "== pronto. contrato $END · arquivos da eleição em $TRAB"
echo "   parar a rede: $BESU/rede-local.sh parar   ·   grafo: python $RAIZ/deploy/blockchain/status_rede.py --dot"
