-- Bloqueos vivos y consultas que los mantienen (PostgreSQL).
SELECT
    locks.pid,
    locks.mode,
    locks.granted,
    relation.relname AS tabla,
    now() - activity.query_start AS duracion,
    left(activity.query, 120) AS consulta
FROM pg_locks AS locks
JOIN pg_stat_activity AS activity ON activity.pid = locks.pid
LEFT JOIN pg_class AS relation ON relation.oid = locks.relation
WHERE locks.pid <> pg_backend_pid()
ORDER BY duracion DESC NULLS LAST;
