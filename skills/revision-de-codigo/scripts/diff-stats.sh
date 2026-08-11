#!/usr/bin/env bash
# Resumen del diff frente a la rama base (por defecto, main).
set -euo pipefail
BASE="${1:-main}"

echo "== Archivos tocados =="
git diff --stat "$BASE"...HEAD

echo
echo "== Líneas por tipo de archivo =="
git diff --numstat "$BASE"...HEAD | awk '{
  n = split($3, parts, ".")
  ext = (n > 1 ? parts[n] : "sin-extension")
  add[ext] += $1; del[ext] += $2
} END {
  for (e in add) printf "  %-12s +%-6d -%d\n", e, add[e], del[e]
}' | sort

echo
echo "== Commits =="
git log --oneline "$BASE"...HEAD
