---
name: "Revisión de código"
description: "Revisa un diff o una pull request buscando errores de corrección, fugas de recursos y complejidad innecesaria. Úsala cuando te pidan revisar código, comentar un PR o validar cambios antes de mezclarlos."
agents: [claude, opencode, cursor]
tags: [git, calidad, review]
version: 1.2.0
author: Equipo de plataforma
license: MIT
allowed-tools: [Read, Grep, Bash]
updated: "2026-08-11T10:56:38"
---

# Revisión de código

## Cuándo usarla

- Te piden revisar un diff, una rama o una pull request.
- Antes de mezclar cambios en la rama principal.
- Cuando hay que decidir si un cambio es seguro de desplegar.

## Cómo funciona

1. Obtén el diff con `scripts/diff-stats.sh` para ver el tamaño y los archivos tocados.
2. Recorre la lista de `references/checklist.md` por cada archivo modificado.
3. Clasifica cada hallazgo en **bloqueante**, **importante** o **sugerencia**.
4. Escribe el informe: un párrafo de resumen y luego los hallazgos ordenados por gravedad.

## Reglas

- Nunca inventes un fallo: cada hallazgo necesita un escenario concreto que lo dispare.
- Un cambio de estilo no es un hallazgo bloqueante.
- Si el diff supera las 800 líneas, avisa de que la revisión será parcial y di qué has cubierto.

## Formato de salida

```markdown
**Resumen** — una o dos frases sobre el estado general del cambio.

### Bloqueantes
- `ruta/archivo.py:42` — qué falla y con qué entrada.

### Sugerencias
- `ruta/otro.py:10` — mejora opcional.
```

## Recursos

- `scripts/diff-stats.sh` — resumen rápido del tamaño del cambio.
- `references/checklist.md` — la lista completa de comprobaciones.
