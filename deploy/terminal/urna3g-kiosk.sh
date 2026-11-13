#!/usr/bin/env bash
# Lançador do modo quiosque: lê /etc/urna3g/terminal.conf e abre o módulo em tela cheia.
# Reabre automaticamente se a janela fechar (Ctrl+Shift+Q só deve ser usado pelo mesário).
set -u
. /etc/urna3g/terminal.conf
export URNA3G_SEM_SOM="${URNA3G_SEM_SOM:-}"
ARGS=(--eleicao "$ELEICAO" --secao "$SECAO" --chaves "$CHAVES" --saida "$SAIDA")
[ -n "${IMPRESSORA:-}" ] && ARGS+=(--impressora "$IMPRESSORA")
[ -n "${CAMERA:-}" ] && ARGS+=(--camera "$CAMERA")
while true; do
  /opt/urna3g/bin/urna3g gui "$PAPEL" "${ARGS[@]}"
  codigo=$?
  [ "$codigo" -eq 0 ] && exit 0      # fechamento intencional pelo mesário
  sleep 2                            # falha: registra e reabre
done
