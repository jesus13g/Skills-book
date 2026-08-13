#!/usr/bin/env bash
# Skills Book como servidor de la LAN (Linux / macOS), sin Docker.
# Configuracion: servidor.env al lado de este script.
# Uso: ./skillsbook-servidor.sh [--port 8777] [--dir /ruta/skills]
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f servidor.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source servidor.env
  set +a
fi

export SKILLSBOOK_HOST="${SKILLSBOOK_HOST:-0.0.0.0}"
export SKILLSBOOK_PORT="${SKILLSBOOK_PORT:-8777}"
export SKILLSBOOK_HOME="${SKILLSBOOK_HOME:-$PWD/data/skills}"
export SKILLSBOOK_ALLOW_PATH_IMPORT="${SKILLSBOOK_ALLOW_PATH_IMPORT:-0}"
export SKILLSBOOK_NO_BROWSER=1
export SKILLSBOOK_STRICT_PORT=1

mkdir -p "$SKILLSBOOK_HOME"

# Primera vez: sembrar con las skills de ejemplo del repositorio.
if [[ -d skills && -z "$(ls -A "$SKILLSBOOK_HOME" 2>/dev/null)" ]]; then
  echo "  Biblioteca vacia: copiando las skills de ejemplo."
  cp -R skills/. "$SKILLSBOOK_HOME"/
fi

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Necesitas Python 3.9 o superior instalado." >&2
  exit 1
fi

if [[ -z "${SKILLSBOOK_TOKEN:-}" ]]; then
  echo "  [AVISO] Sin SKILLSBOOK_TOKEN: cualquiera en la red puede editar y borrar." >&2
fi

exec "$PY" -m skillsbook "$@"
