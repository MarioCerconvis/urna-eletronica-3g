#!/usr/bin/env bash
# Builds the Zenodo replication package from the current commit.
#
#   replication/build_package.sh [VERSION] [OUTPUT_DIR]      # defaults: 1.0.0, ./dist
#
# The package is a snapshot of the committed repository (git archive HEAD), without the research dossier (artigo/),
# plus the English replication guide, data dictionary, preliminary data, network files and environment description
# kept in replication/. Validator keys are never part of git, hence never part of the package.
set -euo pipefail
RAIZ=$(cd "$(dirname "$0")/.." && pwd)
VERSAO="${1:-1.0.0}"
SAIDA="${2:-$RAIZ/dist}"
NOME="urna3g-replication-v$VERSAO"
cd "$RAIZ"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "error: commit your changes first (the package is built from HEAD)" >&2
  exit 1
fi
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive --format=tar --prefix="$NOME/" HEAD -- . ':(exclude)artigo' | tar -x -C "$TMP"
P="$TMP/$NOME"
mv "$P/README.md" "$P/README.pt-BR.md"
mv "$P/replication/README.md" "$P/README.md"
mv "$P/replication/REPLICATION.md" "$P/replication/DATA_DICTIONARY.md" "$P/"
mv "$P/replication/data-preliminary" "$P/replication/network" "$P/replication/environment" "$P/"
mv "$P/replication/docs/format-specification.md" "$P/docs/"
rm -rf "$P/replication"
echo "commit $(git rev-parse HEAD)" > "$P/environment/source-commit.txt"
# absolute home paths in the run logs -> ~/ (no local user names in the public package)
find "$P/resultados" -maxdepth 1 -type f \( -name '*.txt' -o -name '*.md' \) -exec sed -i -E 's#/home/[^/ ]+/#~/#g' {} +
# sanity checks: no private keys or local configuration in the package
if grep -rIl -E "BEGIN (EC |OPENSSH |RSA )?PRIVATE KEY" "$P" >/dev/null; then echo "error: private key found" >&2; exit 1; fi
if find "$P" -path '*/rede/node*/key' | grep -q .; then echo "error: validator key found" >&2; exit 1; fi
(cd "$P" && find . -type f ! -name CHECKSUMS.sha256 -print0 | sort -z | xargs -0 sha256sum > CHECKSUMS.sha256)
mkdir -p "$SAIDA"
rm -f "$SAIDA/$NOME.zip"
(cd "$TMP" && zip -qr -X "$SAIDA/$NOME.zip" "$NOME")
echo "-> $SAIDA/$NOME.zip ($(du -h "$SAIDA/$NOME.zip" | cut -f1)), sha256 $(sha256sum "$SAIDA/$NOME.zip" | cut -d' ' -f1)"
