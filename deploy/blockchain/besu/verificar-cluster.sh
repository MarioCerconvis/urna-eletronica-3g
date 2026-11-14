#!/usr/bin/env bash
# Passo 1: confere se as máquinas do cluster estão prontas para rodar um nó Besu.
#
#   ./verificar-cluster.sh aluno 10.0.0.1 10.0.0.2 ... 10.0.0.13
#   ./verificar-cluster.sh aluno $(cat maquinas.txt)          # um IP/hostname por linha
#   ./verificar-cluster.sh - local                             # testa ESTA máquina, sem SSH
#
# Requer acesso SSH por chave (sem senha) do computador onde roda para cada máquina.
# Não altera nada nas máquinas: só lê informações.
set -uo pipefail
USUARIO="${1:?usuário SSH (ou - para local)}"; shift
[ $# -ge 1 ] || { echo "informe ao menos uma máquina" >&2; exit 1; }
IMG="${BESU_IMAGE:-hyperledger/besu:26.11.0}"

# Roda em cada máquina e imprime "chave=valor" (uma linha por item).
read -r -d '' CHECAGEM <<'REMOTO'
echo "so=$(. /etc/os-release 2>/dev/null && echo "$ID-$VERSION_ID" || uname -s)"
echo "arq=$(uname -m)"
echo "ram_total=$(awk '/MemTotal/{printf "%.1f", $2/1048576}' /proc/meminfo)"
echo "ram_livre=$(awk '/MemAvailable/{printf "%.1f", $2/1048576}' /proc/meminfo)"
echo "disco_livre=$(df -BG --output=avail "$HOME" 2>/dev/null | tail -1 | tr -dc 0-9)"
if command -v docker >/dev/null; then
  if docker info >/dev/null 2>&1; then echo "docker=ok"; else echo "docker=sem_permissao"; fi
  if docker image inspect "IMAGEM" >/dev/null 2>&1; then echo "imagem=ok"; else echo "imagem=ausente"; fi
else echo "docker=ausente"; echo "imagem=-"; fi
if command -v timedatectl >/dev/null; then
  s=$(timedatectl show -p NTPSynchronized --value 2>/dev/null); echo "relogio=${s:-?}"
else echo "relogio=?"; fi
echo "hora=$(date -u +%s)"
if command -v curl >/dev/null && curl -s -m 5 -o /dev/null https://registry-1.docker.io/v2/; then echo "internet=ok"
elif timeout 5 bash -c '</dev/tcp/registry-1.docker.io/443' 2>/dev/null; then echo "internet=ok"
else echo "internet=nao"; fi
if command -v ss >/dev/null && ss -ltnu 2>/dev/null | grep -q ':30303 '; then echo "porta30303=ocupada"; else echo "porta30303=livre"; fi
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then echo "firewall=ufw_ativo"
elif command -v firewall-cmd >/dev/null && firewall-cmd --state 2>/dev/null | grep -q running; then echo "firewall=firewalld_ativo"
else echo "firewall=nao_detectado"; fi
REMOTO
CHECAGEM="${CHECAGEM//IMAGEM/$IMG}"

printf "%-16s %-14s %-7s %-10s %-8s %-14s %-8s %-8s %-9s %-10s %s\n" \
  máquina sistema arq "RAM livre" disco docker imagem relógio internet "porta" firewall
problemas=()
agora=$(date -u +%s)
for m in "$@"; do
  if [ "$m" = "local" ]; then saida=$(bash -c "$CHECAGEM" 2>/dev/null)
  else saida=$(ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new "$USUARIO@$m" bash -s <<<"$CHECAGEM" 2>/dev/null); fi
  if [ -z "$saida" ]; then
    printf "%-16s %s\n" "$m" "SEM ACESSO SSH (confira IP, usuário e chave: ssh-copy-id $USUARIO@$m)"
    problemas+=("$m: sem acesso SSH"); continue
  fi
  v() { echo "$saida" | sed -n "s/^$1=//p"; }
  deriva=$(( $(v hora) - agora )); deriva=${deriva#-}
  printf "%-16s %-14s %-7s %-10s %-8s %-14s %-8s %-8s %-9s %-10s %s\n" "$m" "$(v so)" "$(v arq)" \
    "$(v ram_livre)/$(v ram_total)G" "$(v disco_livre)G" "$(v docker)" "$(v imagem)" "$(v relogio)" "$(v internet)" \
    "$(v porta30303)" "$(v firewall)"
  [ "$(v arq)" = "x86_64" ] || [ "$(v arq)" = "aarch64" ] || problemas+=("$m: arquitetura $(v arq) não suportada pela imagem do Besu")
  awk -v r="$(v ram_livre)" 'BEGIN{exit !(r<2)}' && problemas+=("$m: menos de 2 GB de RAM livre")
  [ "$(v disco_livre)" -ge 5 ] 2>/dev/null || problemas+=("$m: menos de 5 GB livres no disco")
  case "$(v docker)" in
    ausente) problemas+=("$m: Docker não instalado → sudo apt install docker.io") ;;
    sem_permissao) problemas+=("$m: usuário fora do grupo docker → sudo usermod -aG docker $USUARIO (e entrar de novo)") ;;
  esac
  [ "$(v imagem)" = "ok" ] || [ "$(v docker)" != "ok" ] || problemas+=("$m: imagem do Besu ausente (passo 3)")
  [ "$(v relogio)" = "yes" ] || problemas+=("$m: relógio não sincronizado → sudo timedatectl set-ntp true (ou instalar chrony)")
  [ "$deriva" -le 2 ] || problemas+=("$m: relógio difere ${deriva}s deste computador")
  [ "$(v porta30303)" = "livre" ] || problemas+=("$m: porta 30303 já em uso")
  case "$(v firewall)" in
    ufw_ativo) problemas+=("$m: firewall ativo → sudo ufw allow 30303 (TCP e UDP)") ;;
    firewalld_ativo) problemas+=("$m: firewall ativo → sudo firewall-cmd --permanent --add-port=30303/tcp --add-port=30303/udp && sudo firewall-cmd --reload") ;;
  esac
done
echo
if [ ${#problemas[@]} -eq 0 ]; then echo "Tudo pronto para o passo 2."
else echo "Pendências (${#problemas[@]}):"; printf '  - %s\n' "${problemas[@]}"
  echo "Sem internet nas máquinas não é problema: a imagem pode ir por 'docker save | ssh ... docker load' (passo 3)."; fi
