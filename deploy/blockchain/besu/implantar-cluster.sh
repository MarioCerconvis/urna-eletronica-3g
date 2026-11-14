#!/usr/bin/env bash
# Distribui e liga a rede QBFT no cluster, a partir da máquina de controle (acesso SSH por chave).
#
#   ./implantar-cluster.sh subir  <dir_rede> <usuario> IP1 IP2 ... IPN   # nodeK → IPK; N = nº de nós em dir_rede
#   ./implantar-cluster.sh parar  <usuario> IP1 IP2 ...                  # para o contêiner besu nas máquinas
#   ./implantar-cluster.sh apagar <usuario> IP1 IP2 ...                  # para e APAGA ~/besu (dados e chaves)
#
# Cada máquina recebe em ~/besu: no-lab.sh, rede/genesis.json, rede/node1/key.pub e SÓ a sua chave rede/nodeK/key.
# Os nós sobem com RPC_PUBLICO=1 (RPC na porta 8545 da LAN do cluster) para o status_rede.py funcionar daqui.
set -euo pipefail
cd "$(dirname "$0")"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=10)
acao="${1:?subir|parar|apagar}"; shift
case "$acao" in
  subir)
    rede="${1:?dir da rede (com genesis.json e nodeK/)}"; usuario="${2:?usuário}"; shift 2
    n=$(ls -d "$rede"/node* | wc -l)
    [ $# -eq "$n" ] || { echo "a rede tem $n nós; informe exatamente $n IPs (recebidos $#)" >&2; exit 1; }
    ips=("$@"); ip1="${ips[0]}"
    for k in $(seq 1 "$n"); do
      ip="${ips[$((k-1))]}"
      "${SSH[@]}" "$usuario@$ip" "mkdir -p besu/rede/node1 besu/rede/node$k && chmod 700 besu/rede/node$k"
      scp -q no-lab.sh "$usuario@$ip:besu/"
      scp -q "$rede/genesis.json" "$usuario@$ip:besu/rede/"
      scp -q "$rede/node1/key.pub" "$usuario@$ip:besu/rede/node1/"
      scp -q "$rede/node$k/key" "$rede/node$k/key.pub" "$usuario@$ip:besu/rede/node$k/"
      "${SSH[@]}" "$usuario@$ip" "chmod 600 besu/rede/node$k/key && cd besu && RPC_PUBLICO=1 ./no-lab.sh $k $ip $ip1"
      [ "$k" -eq 1 ] && sleep 5   # dá tempo ao bootnode antes dos outros
    done
    echo "rede de $n nós distribuída. Status: python3 status_rede.py --rpc $(printf 'http://%s:8545 ' "${ips[@]}")" ;;
  parar|apagar)
    usuario="${1:?usuário}"; shift
    for ip in "$@"; do
      if [ "$acao" = parar ]; then cmd="docker rm -f besu >/dev/null 2>&1; echo parado"
      else cmd="docker rm -f besu >/dev/null 2>&1; rm -rf besu; echo apagado"; fi
      echo "$ip: $("${SSH[@]}" "$usuario@$ip" "$cmd" 2>&1)"
    done ;;
  *) sed -n '2,9p' "$0"; exit 1 ;;
esac
