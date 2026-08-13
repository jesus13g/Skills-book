#!/usr/bin/env bash
# Copia de seguridad de la biblioteca: un .tar.gz con fecha.
#
#   ./deploy/copia-seguridad.sh                      # usa ./data/skills
#   ./deploy/copia-seguridad.sh /var/lib/skillsbook/skills /mnt/backups
#
# Las skills son archivos normales: esto es un tar de una carpeta, y se
# restaura descomprimiendolo encima. No hace falta parar el servidor.
set -euo pipefail

ORIGEN="${1:-${SKILLSBOOK_HOME:-$(cd "$(dirname "$0")/.." && pwd)/data/skills}}"
DESTINO="${2:-$(cd "$(dirname "$0")/.." && pwd)/backups}"
CUANTAS="${SKILLSBOOK_BACKUPS_A_GUARDAR:-14}"

if [[ ! -d "$ORIGEN" ]]; then
  echo "No existe la biblioteca: $ORIGEN" >&2
  exit 1
fi

mkdir -p "$DESTINO"
ARCHIVO="$DESTINO/skillsbook-$(date +%Y%m%d-%H%M%S).tar.gz"
tar -czf "$ARCHIVO" -C "$(dirname "$ORIGEN")" "$(basename "$ORIGEN")"
echo "Copia creada: $ARCHIVO  ($(du -h "$ARCHIVO" | cut -f1))"

# Rotacion: deja solo las ultimas CUANTAS copias.
ls -1t "$DESTINO"/skillsbook-*.tar.gz 2>/dev/null | tail -n +$((CUANTAS + 1)) | while read -r viejo; do
  rm -f "$viejo"
  echo "Borrada copia antigua: $(basename "$viejo")"
done
