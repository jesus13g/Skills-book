# Patrones de migración

## Añadir una columna obligatoria

```sql
-- Paso 1 (despliegue A): nullable, sin reescritura de tabla
ALTER TABLE pedidos ADD COLUMN canal text;

-- Paso 2 (despliegue A, por lotes): rellenar
UPDATE pedidos SET canal = 'web'
WHERE canal IS NULL AND id IN (
  SELECT id FROM pedidos WHERE canal IS NULL LIMIT 1000
);

-- Paso 3 (despliegue B): imponer la restricción ya validada
ALTER TABLE pedidos ADD CONSTRAINT pedidos_canal_no_nulo
  CHECK (canal IS NOT NULL) NOT VALID;
ALTER TABLE pedidos VALIDATE CONSTRAINT pedidos_canal_no_nulo;
```

## Renombrar una columna sin parada

1. Añade la columna nueva y escribe en las dos desde el código.
2. Copia los datos históricos por lotes.
3. Cambia las lecturas a la columna nueva y despliega.
4. Deja de escribir en la vieja y despliega.
5. Borra la columna vieja en un despliegue posterior.

## Índices

```sql
CREATE INDEX CONCURRENTLY idx_pedidos_canal ON pedidos (canal);
DROP INDEX CONCURRENTLY IF EXISTS idx_pedidos_antiguo;
```
