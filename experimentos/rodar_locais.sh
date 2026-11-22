#!/usr/bin/env bash
cd "$(dirname "$0")"
LOG=../resultados/log-locais.txt
for e in e3_leitura_qr.py e4_apuracao.py; do
  echo "=== $(date '+%F %T') início $e" >> "$LOG"; ../.venv/bin/python "$e" >> "$LOG" 2>&1; echo "=== $(date '+%F %T') fim $e (código $?)" >> "$LOG"
done
echo "=== $(date '+%F %T') FILA CONCLUÍDA" >> "$LOG"
