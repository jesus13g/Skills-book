#!/usr/bin/env bash
# Copia de seguridad de la biblioteca: un .tar.gz con fecha.
#
#   ./deploy/copia-seguridad.sh                      # usa ./data/skills
#   ./deploy/copia-seguridad.sh /var/lib/skillsbook/skills /mnt/backups
#
# Las skills y los prompts son archivos normales: esto es un tar de sus dos
# carpetas, y se restaura descomprimiendolo encima. No hace falta parar el
# servidor.
set -euo pipefail

ORIGEN="${1:-${SKILLSBOOK_HOME:-$(cd "$(dirname "$0")/.." && pwd)/data/skills}}"
DESTINO="${2:-$(cd "$(dirname "$0")/.." && pwd)/backups}"
CUANTAS="${SKILLSBOOK_BACKUPS_A_GUARDAR:-14}"
# Los prompts viven al lado de las skills, salvo que digas otra cosa.
PROMPTS="${SKILLSBOOK_PROMPTS:-$(dirname "$ORIGEN")/prompts}"

if [[ ! -d "$ORIGEN" ]]; then
  echo "No existe la biblioteca: $ORIGEN" >&2
  exit 1
fi

mkdir -p "$DESTINO"
ARCHIVO="$DESTINO/skillsbook-$(date +%Y%m%d-%H%M%S).tar.gz"
CARPETAS=("$(basename "$ORIGEN")")
if [[ -d "$PROMPTS" && "$(dirname "$PROMPTS")" == "$(dirname "$ORIGEN")" ]]; then
  CARPETAS+=("$(basename "$PROMPTS")")
elif [[ -d "$PROMPTS" ]]; then
  # Carpeta de prompts fuera de sitio: se guarda en su propio tar.
  PROMPTS_TAR="$DESTINO/skillsbook-prompts-$(date +%Y%m%d-%H%M%S).tar.gz"
  tar -czf "$PROMPTS_TAR" -C "$(dirname "$PROMPTS")" "$(basename "$PROMPTS")"
  echo "Copia de los prompts: $PROMPTS_TAR"
fi
tar -czf "$ARCHIVO" -C "$(dirname "$ORIGEN")" "${CARPETAS[@]}"
echo "Copia creada: $ARCHIVO  ($(du -h "$ARCHIVO" | cut -f1))"

# Rotacion: deja solo las ultimas CUANTAS copias de cada serie. El sello de
# fecha empieza por un digito, asi que [0-9]* no pisa las de los prompts.
rotar() {
  # El patron llega sin comillas a proposito: es el shell quien lo expande.
  # shellcheck disable=SC2086
  ls -1t $1 2>/dev/null | tail -n +$((CUANTAS + 1)) | while read -r viejo; do
    rm -f "$viejo"
    echo "Borrada copia antigua: $(basename "$viejo")"
  done || true
}
rotar "$DESTINO/skillsbook-[0-9]*.tar.gz"
rotar "$DESTINO/skillsbook-prompts-*.tar.gz"
