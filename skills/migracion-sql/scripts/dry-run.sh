#!/usr/bin/env bash
# Aplica la migración y su reversión sobre una base de datos desechable.
set -euo pipefail
MIGRACION="${1:?uso: dry-run.sh migracion.sql [reversion.sql]}"
REVERSION="${2:-${MIGRACION%.sql}.down.sql}"
DB="dryrun_$(date +%s)"

createdb "$DB"
trap 'dropdb --if-exists "$DB"' EXIT

echo "== Aplicando $MIGRACION =="
time psql -v ON_ERROR_STOP=1 -d "$DB" -f "$MIGRACION"

if [ -f "$REVERSION" ]; then
  echo "== Revirtiendo con $REVERSION =="
  time psql -v ON_ERROR_STOP=1 -d "$DB" -f "$REVERSION"
else
  echo "AVISO: no existe $REVERSION — la migración no tiene reversión probada." >&2
  exit 1
fi

echo "Ensayo correcto."
