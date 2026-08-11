# Lista de comprobación

## Corrección
- [ ] ¿Los casos límite (lista vacía, `None`, cero, negativos) están cubiertos?
- [ ] ¿Los errores se propagan o se tragan silenciosamente?
- [ ] ¿Hay condiciones de carrera en el código concurrente?
- [ ] ¿Los índices y rangos son correctos en los bucles?

## Recursos
- [ ] Ficheros, sockets y conexiones se cierran (`with` / `defer` / `try-finally`).
- [ ] No hay consultas dentro de bucles que puedan agruparse.

## Seguridad
- [ ] La entrada del usuario se valida antes de tocar disco, SQL o el shell.
- [ ] No hay credenciales ni tokens escritos en el código.
- [ ] Las rutas de fichero se normalizan para evitar `../`.

## Mantenimiento
- [ ] Los nombres describen la intención, no la implementación.
- [ ] El cambio sigue las convenciones del código de alrededor.
- [ ] Las pruebas cubren el comportamiento nuevo, no solo la línea nueva.
