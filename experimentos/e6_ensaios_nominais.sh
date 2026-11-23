#!/usr/bin/env bash
# E6 — 10 ensaios nominais no cluster (12 seções cada = 120 ancoragens), com o coletor corrigido.
#    Com uma configuração de modo local (exemplos/experimentos-local.json), roda na rede de contêineres desta máquina.
cd "$(dirname "$0")/.." || exit 1
CFG="${URNA3G_PAINEL_CFG:-$HOME/Desktop/UFABC/cluster-rede-12/painel.json}"
if grep -q '"modo": *"local"' "$CFG"; then ALVO=(--local); else ALVO=(--config "$CFG"); fi
.venv/bin/urna3g ensaio-lote "${ALVO[@]}" --n 10 --eleitores 25 --duracao 30 --pausa 10 --saida resultados/e6-ensaios-nominais
