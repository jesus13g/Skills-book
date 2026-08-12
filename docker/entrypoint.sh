#!/bin/sh
# Prepara el volumen de datos y arranca la app.
set -eu

LIB="${SKILLSBOOK_HOME:-/data/skills}"
SEED="${SKILLSBOOK_SEED_DIR:-/opt/skillsbook/skills-semilla}"

if ! mkdir -p "$LIB" 2>/dev/null || [ ! -w "$LIB" ]; then
  echo "ERROR: no puedo escribir en $LIB." >&2
  echo "  El contenedor corre como uid $(id -u). Si montas una carpeta del host:" >&2
  echo "    sudo chown -R 1000:1000 <carpeta>" >&2
  echo "  o arranca con  user: \"\$(id -u):\$(id -g)\"  en docker-compose.yml." >&2
  exit 1
fi

# Semilla solo la primera vez: si ya hay algo, no se toca nada.
if [ -d "$SEED" ] && [ -z "$(ls -A "$LIB" 2>/dev/null)" ]; then
  if [ "${SKILLSBOOK_SEED:-1}" = "1" ]; then
    echo "  Biblioteca vacia: copiando las skills de ejemplo."
    cp -R "$SEED"/. "$LIB"/ 2>/dev/null || true
  fi
fi

exec "$@"
