#!/usr/bin/env bash
# Fila dos experimentos no cluster (um de cada vez; cada um grava parciais). Log em resultados/log-cluster.txt
cd "$(dirname "$0")"
PY=../.venv/bin/python
LOG=../resultados/log-cluster.txt
for e in e5_intervalo_blocos.py e7_tolerancia.py e6 e9_capacidade.py e10_ensaio_com_falhas.py e8_recuperacao.py e11_reinicio.py; do
  echo "=== $(date '+%F %T') início $e" >> "$LOG"
  if [ "$e" = e6 ]; then ./e6_ensaios_nominais.sh >> "$LOG" 2>&1; else $PY "$e" >> "$LOG" 2>&1; fi
  echo "=== $(date '+%F %T') fim $e (código $?)" >> "$LOG"
done
echo "=== $(date '+%F %T') FILA CONCLUÍDA" >> "$LOG"
