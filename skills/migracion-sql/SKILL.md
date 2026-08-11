---
name: Migraciones SQL seguras
description: "Escribe y revisa migraciones de base de datos que no bloqueen tablas ni pierdan datos, con su plan de reversión. Úsala al añadir o cambiar columnas, índices o restricciones en producción."
agents: [claude, opencode]
tags: [base-de-datos, sql, produccion]
version: 0.9.0
allowed-tools: [Read, Bash, Edit]
updated: "2026-08-11T10:56:38"
---

# Migraciones SQL seguras

## Cuándo usarla

Cualquier cambio de esquema que vaya a ejecutarse contra una base de datos con tráfico real.

## Reglas duras

1. **Una migración, un cambio.** Nada de mezclar esquema y datos en el mismo fichero.
2. **Expandir, migrar, contraer.** Añade lo nuevo, copia los datos, borra lo viejo — en tres despliegues, nunca en uno.
3. **Nunca renombres ni borres una columna** que el código en producción todavía lee.
4. Toda migración necesita su reversión escrita y probada.

## Cómo funciona

1. Ejecuta `scripts/check-locks.sql` contra una copia para estimar el bloqueo.
2. Escribe la migración siguiendo los patrones de `references/patrones.md`.
3. Prueba ida y vuelta con `scripts/dry-run.sh`.
4. Anota en la cabecera del fichero: duración estimada, tablas bloqueadas y plan de reversión.

## Señales de alarma

| Señal | Por qué duele | Alternativa |
| --- | --- | --- |
| `ALTER TABLE … ADD COLUMN … NOT NULL DEFAULT` | Reescribe la tabla entera | Añadir nullable, rellenar por lotes, luego imponer `NOT NULL` |
| `CREATE INDEX` sin `CONCURRENTLY` | Bloquea escrituras | `CREATE INDEX CONCURRENTLY` |
| `UPDATE` sin `WHERE` acotado | Transacción enorme | Lotes de 1.000 filas |
