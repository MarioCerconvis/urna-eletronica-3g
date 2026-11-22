#!/usr/bin/env bash
# E6 — 10 ensaios nominais no cluster (12 seções cada = 120 ancoragens), com o coletor corrigido.
cd "$(dirname "$0")/.." && .venv/bin/urna3g ensaio-lote --config "${URNA3G_PAINEL_CFG:-$HOME/Desktop/UFABC/cluster-rede-12/painel.json}" \
  --n 10 --eleitores 25 --duracao 30 --pausa 10 --saida resultados/e6-ensaios-nominais
