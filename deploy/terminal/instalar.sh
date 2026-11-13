#!/usr/bin/env bash
# Instala o urna3g em um terminal (Debian/Ubuntu x86_64) e configura o modo quiosque.
# Uso: sudo ./instalar.sh <papel> <secao> [impressora]
#   papel: votar | verificar | apurar
set -euo pipefail

PAPEL="${1:?papel: votar|verificar|apurar}"
SECAO="${2:?identificador da seção, ex.: 001}"
IMPRESSORA="${3:-}"
ORIGEM="${URNA3G_ORIGEM:-git+https://github.com/MarioCerconvis/urna-eletronica-3g.git}"
PREFIXO=/opt/urna3g
CONF=/etc/urna3g

apt-get update -q
apt-get install -y -q python3 python3-venv python3-pip cups cups-client \
  libegl1 libgl1 libxkbcommon0 libxcb-cursor0 libglib2.0-0 libdbus-1-3 libfontconfig1 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 pulseaudio-utils

id -u urna >/dev/null 2>&1 || useradd --create-home --shell /bin/bash urna
usermod -aG lp,lpadmin,video,audio urna

python3 -m venv "$PREFIXO"
"$PREFIXO/bin/pip" install --upgrade pip
"$PREFIXO/bin/pip" install "urna3g[gui,camera] @ $ORIGEM"

install -d -m 0750 -o urna -g urna "$CONF" "$CONF/chaves" /var/lib/urna3g
cat > "$CONF/terminal.conf" <<CONF
PAPEL=$PAPEL
SECAO=$SECAO
IMPRESSORA=$IMPRESSORA
ELEICAO=$CONF/eleicao/eleicao.json
CHAVES=$CONF/chaves
SAIDA=/var/lib/urna3g
CONF
install -m 0755 "$(dirname "$0")/urna3g-kiosk.sh" /usr/local/bin/urna3g-kiosk
install -d /etc/xdg/autostart
install -m 0644 "$(dirname "$0")/urna3g-kiosk.desktop" /etc/xdg/autostart/urna3g-kiosk.desktop

cat <<MSG

Instalado. Falta:
  1. copiar o pacote da eleição para $CONF/eleicao/ (eleicao.json, eleicao.sig, fotos/)
  2. copiar para $CONF/chaves/ SOMENTE as chaves deste papel:
       votar      -> secao-$SECAO.key  (+ autoridade.pub)
       verificar  -> secao-$SECAO.pub  (+ autoridade.pub)
       apurar     -> secao-$SECAO.pub, apuracao-$SECAO.key (+ autoridade.pub)
     e ajustar permissões: chown -R urna:urna $CONF; chmod 600 $CONF/chaves/*.key
  3. configurar a impressora no CUPS (lpadmin) e testar: lp -d "$IMPRESSORA" /usr/share/cups/data/testprint
  4. autologin do usuário 'urna' no gerenciador de sessão (ex.: LightDM: autologin-user=urna)
  5. para urna/verificação: DESCONECTAR a rede antes de abrir a seção.
MSG
