#!/usr/bin/env bash
# Arranca Skills Book (macOS / Linux).  Uso: ./skillsbook.sh [--port 8777] [--dir ruta]
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Necesitas Python 3.9 o superior instalado." >&2
  exit 1
fi

exec "$PY" -m skillsbook "$@"
