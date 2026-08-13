# 📚 Skills Book

Biblioteca **local** de skills y prompts para agentes — Claude, ChatGPT, opencode, Cursor,
Copilot, Gemini o cualquier otro. Guarda, revisa, crea, edita y borra skills desde el
navegador, con sus carpetas de scripts y documentos de apoyo; y guarda al lado los prompts
que repites cada día, listos para copiar de un clic.

Sin base de datos, sin cuenta, sin conexión a internet y **sin dependencias**: solo Python 3.9+.
Cada skill es una carpeta de verdad en tu disco y cada prompt un archivo de verdad, así que
todo sigue siendo utilizable desde la terminal, desde git y desde los propios agentes.

---

## Arrancar

```bash
./skillsbook.sh              # macOS / Linux
skillsbook.bat               # Windows
python3 -m skillsbook        # cualquier sistema
```

Se abre en <http://127.0.0.1:8777/>. Solo escucha en `localhost`; si el puerto está ocupado,
salta automáticamente al siguiente libre.

### Opciones

| Opción | Qué hace |
| --- | --- |
| `--dir RUTA` | Usa otra carpeta como biblioteca (por defecto `./skills`). |
| `--prompts-dir RUTA` | Carpeta de prompts (por defecto, la hermana de la biblioteca). |
| `--port N` | Puerto HTTP (por defecto `8777`). |
| `--host H` | Interfaz de escucha (por defecto `127.0.0.1`). |
| `--no-browser` | No abrir el navegador al arrancar. |
| `--verbose` | Registrar cada petición en consola. |

También puedes fijar la biblioteca con la variable `SKILLSBOOK_HOME`:

```bash
SKILLSBOOK_HOME=~/.claude/skills python3 -m skillsbook
```

Eso te deja editar directamente las skills que ya usa tu agente. Los prompts se guardan en
la carpeta hermana (`~/.claude/prompts` en ese ejemplo), o donde diga `SKILLSBOOK_PROMPTS`.

---

## En un servidor de la organización

La misma app, compartida por todo el equipo en la red local:

```bash
docker compose up -d                # Docker
skillsbook-servidor.bat             # Windows
./skillsbook-servidor.sh            # Linux / macOS
```

Queda en `http://IP-DEL-SERVIDOR:8777/`. Al salir a la red, la app se pone sola en modo
servidor: no abre navegador, no salta de puerto y desactiva la importación por ruta.
Pon un `SKILLSBOOK_TOKEN` para que pida contraseña, o cualquiera en la red podrá borrar
skills.

**[DESPLIEGUE.md](DESPLIEGUE.md)** lo cuenta entero: instalación, arranque automático,
configuración, permisos, copias de seguridad y qué mirar cuando algo falla.

---

## Cómo se guarda una skill

```
skills/
└── revision-de-codigo/
    ├── SKILL.md              ← metadatos (frontmatter) + instrucciones en markdown
    ├── scripts/
    │   └── diff-stats.sh     ← utilidades ejecutables
    └── references/
        └── checklist.md      ← documentación que el agente lee bajo demanda
```

`SKILL.md` sigue el formato estándar de agent skills, así que la carpeta se puede copiar tal
cual a `~/.claude/skills/` o al directorio de skills de tu agente:

```markdown
---
name: Revisión de código
description: Revisa un diff o una pull request buscando errores de corrección…
agents: [claude, opencode, cursor]
tags: [git, calidad, review]
version: 1.2.0
allowed-tools: [Read, Grep, Bash]
updated: 2026-08-11T10:56:38
---

# Revisión de código

## Cuándo usarla
…
```

Las claves que no conoce la app (por ejemplo `model:` o `x-origen:`) **se conservan** al editar.

---

## Cómo se guarda un prompt

Un prompt es un bloque de texto que repites mucho pero que no da para una skill: no tiene
scripts ni documentos, así que es **un archivo suelto** en la carpeta hermana de la
biblioteca:

```
data/
├── skills/
│   └── revision-de-codigo/…
└── prompts/
    ├── resumen-ejecutivo.md
    └── mensaje-de-commit.md
```

Mismo formato que una skill, para que se siga leyendo desde la terminal y desde git:

```markdown
---
name: Resumen ejecutivo
tags: [redaccion, cliente]
updated: 2026-08-13T10:04:11
---

Resume el siguiente texto en cinco viñetas…
```

Con `--prompts-dir` o `SKILLSBOOK_PROMPTS` puedes ponerlos en otro sitio.

---

## Qué puedes hacer

**Con los prompts**
- Crear, editar, duplicar y borrar, con el identificador (nombre del archivo) renombrable.
- **Copiar el prompt entero de un clic**, desde su tarjeta en la lista o desde el detalle.
- Etiquetarlos y filtrarlos con las mismas etiquetas que las skills.
- Buscarlos por nombre y por contenido.

**Con las skills**
- Crear, editar y borrar, con el identificador (nombre de carpeta) renombrable.
- Duplicar una skill entera con sus archivos.
- Marcar con qué agentes es compatible y etiquetarlas.
- Filtrar por agente o etiqueta, buscar por nombre y descripción, o buscar texto **dentro** de
  todos los archivos de todas las skills.
- Ver el listado completo en el **explorador** (`Ctrl/Cmd + K`, o el botón de la rejilla en las
  cabeceras de Skills y de Prompts): un diálogo con las dos bibliotecas en rejilla, su propio
  buscador y un clic para abrir lo que elijas.
- Ver el `SKILL.md` renderizado como markdown: títulos, listas, tablas, código y citas.

**En todo lo que sea markdown** — el contenido de una skill, un prompt, un `.md` del árbol de
archivos y los formularios de edición — hay un interruptor **Texto / Código** para alternar
entre el markdown renderizado y el fuente tal cual. La elección se recuerda, y en el editor
puedes ver la vista previa sin perder lo que estabas escribiendo.

**Con los archivos de cada skill**
- Árbol de carpetas con cualquier profundidad.
- Crear archivos y carpetas, renombrar, mover y borrar.
- Editor de texto integrado con guardado por `Ctrl/Cmd + S`.
- Tema claro y oscuro, con la opción de seguir al sistema.
- Subir archivos binarios (imágenes, PDF, zip…) y previsualizar imágenes.
- Descargar cualquier archivo suelto.
- Los `.sh` se marcan como ejecutables automáticamente.

**Entrar y salir**
- Exportar una skill, o la biblioteca entera —skills y prompts— como zip.
- Importar un zip (con una o varias skills, con prompts o con las dos cosas) o copiar una
  carpeta local de skills, p. ej. `~/.claude/skills`.

### Atajos

| Tecla | Acción |
| --- | --- |
| `/` | Ir al buscador |
| `Ctrl/Cmd + K` | Abrir el explorador con el listado completo |
| `Intro` en el buscador | Buscar dentro del contenido de los archivos |
| `Ctrl/Cmd + S` | Guardar el archivo o el formulario abierto |
| `T` | Cambiar de tema: sistema → claro → oscuro |

---

## La interfaz

Brutalismo moderno, en claro y en oscuro. Las reglas del sistema, por si tocas el CSS:

- **Geometría a cero radios.** Todo es caja; el borde es estructura, no adorno. Las sombras
  son duras y desplazadas (`4px 4px 0`), nunca difuminadas.
- **Dos voces tipográficas.** La interfaz (etiquetas, botones, rutas, árbol) habla en
  monoespaciada, en versalitas y con tracking abierto; la prosa larga —descripciones y el
  markdown de la skill— va en grotesca. Ambas pilas resuelven contra fuentes ya instaladas:
  ni una petición a internet.
- **Un solo acento.** Naranja de alta energía para lo accionable y lo seleccionado; el resto
  del color se reserva para señales (guardado sin confirmar, error, correcto).
- **Simbología en SVG.** Todos los iconos salen de un sprite `<symbol>` incrustado en
  `index.html` y heredan el color del texto. No hay emojis en la interfaz.
- **Movimiento contenido.** Solo desplazamientos de 2 px con sombra dura al pasar por encima,
  y todo se desactiva con `prefers-reduced-motion`.

- **La barra lateral no se desborda.** Los filtros enseñan los agentes y las etiquetas más
  usadas; las demás viven en un desplegable con buscador (el chip `+N etiquetas` o el `#` de la
  cabecera), y las que tengas activas se quedan siempre a la vista. Debajo, Skills y Prompts se
  reparten el alto a partes iguales —ninguna lista pasa de la mitad ni le come el sitio a la
  otra— y cada cabecera lleva su recuento y el botón que abre el explorador. Si un filtro de
  agente aparta los prompts, las skills recuperan la barra entera.

- **Dos temas, una sola tabla de color.** El botón del pie de la barra lateral (o la tecla `T`)
  recorre sistema → claro → oscuro. «Sistema» sigue al ajuste del escritorio, incluso si cambia
  con la app abierta; la preferencia se guarda en `localStorage` (`sb-theme`) y se aplica antes
  de pintar, así que no hay fogonazo al recargar.

Los tokens (superficies, líneas, tinta, señal, veladuras, tipografía y geometría) están al
principio de `styles.css`: el bloque `:root` es el tema oscuro y `:root[data-theme="light"]` el
claro. Ninguna regla del resto del archivo lleva un color literal, así que cambiar esos dos
bloques cambia el tema entero; si añades un color nuevo, decláralo en los dos.

---

## API

La interfaz es solo un cliente de esta API; puedes usarla desde `curl` o tus propios scripts.

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/prompts` | Lista de prompts (con su texto) |
| `POST /api/prompts` | Crear prompt |
| `GET /api/prompts/{slug}` | Prompt completo |
| `PUT /api/prompts/{slug}` | Actualizar (incluye renombrar el archivo) |
| `DELETE /api/prompts/{slug}` | Borrar el prompt |
| `POST /api/prompts/{slug}/duplicate` | Duplicar |
| `GET /api/skills` | Lista de skills con sus metadatos |
| `POST /api/skills` | Crear skill |
| `GET /api/skills/{slug}` | Skill completa: metadatos, cuerpo y árbol de archivos |
| `PUT /api/skills/{slug}` | Actualizar (incluye renombrar la carpeta) |
| `DELETE /api/skills/{slug}` | Borrar la skill y todos sus archivos |
| `POST /api/skills/{slug}/duplicate` | Duplicar |
| `GET /api/skills/{slug}/tree` | Árbol de archivos |
| `GET /api/skills/{slug}/file?path=…` | Leer un archivo |
| `PUT /api/skills/{slug}/file` | Escribir (`content`) o subir (`base64`) |
| `DELETE /api/skills/{slug}/file?path=…` | Borrar archivo o carpeta |
| `POST /api/skills/{slug}/folder` | Crear carpeta |
| `POST /api/skills/{slug}/move` | Renombrar o mover (`path` → `to`) |
| `GET /api/skills/{slug}/raw?path=…` | Descargar el archivo tal cual |
| `GET /api/skills/{slug}/export` | Zip de la skill |
| `GET /api/export` | Zip de toda la biblioteca (skills y prompts) |
| `POST /api/import` | Importar `zip_base64` o `path` |
| `GET /api/search?q=…` | Buscar texto dentro de los archivos y de los prompts |
| `GET /api/stats` | Totales, agentes y etiquetas |
| `GET /healthz` | Sonda de vida (no pide token) |

```bash
curl -s localhost:8777/api/skills | python3 -m json.tool

curl -s -X POST localhost:8777/api/skills \
  -H 'Content-Type: application/json' \
  -d '{"name":"Mi skill","description":"Qué hace y cuándo usarla","agents":["claude"]}'

curl -s -X POST localhost:8777/api/prompts \
  -H 'Content-Type: application/json' \
  -d '{"name":"Resumen ejecutivo","text":"Resume el texto en cinco viñetas.","tags":["redaccion"]}'
```

---

## Seguridad

Es una app local, pero trata los datos con cuidado:

- Solo escucha en `127.0.0.1` salvo que cambies `--host`. Si la publicas en la red, pon
  un `SKILLSBOOK_TOKEN`: sin él, cualquiera que llegue al puerto puede editar y borrar
  ([DESPLIEGUE.md](DESPLIEGUE.md#quién-puede-entrar)).
- Todas las rutas se resuelven dentro de la carpeta de la skill: `..`, rutas absolutas y
  enlaces simbólicos que apunten fuera se rechazan.
- Los zips que importas no pueden escribir fuera de la biblioteca (*zip slip*).
- El markdown se escapa antes de renderizar: el HTML dentro de una skill se muestra, no se ejecuta.

---

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

73 pruebas sobre el frontmatter, el almacén en disco de skills y de prompts (incluidos los
intentos de fuga de ruta), la API HTTP completa y el modo servidor (token, sonda de vida,
candados del despliegue). La interfaz se validó además con Playwright sobre Chromium: listado,
renderizado de markdown, interruptor texto/código, copiar al portapapeles (también sobre
`http://` en la LAN, donde el navegador no da `navigator.clipboard`), árbol de archivos,
edición con guardado, alta y baja de skills y de prompts, filtros y búsqueda.

---

## Estructura del proyecto

```
skillsbook/
├── __main__.py       # CLI: puertos, navegador, modo local o servidor
├── server.py         # servidor HTTP, rutas de la API y token de acceso
├── store.py          # skills en disco: CRUD, archivos, zip, búsqueda
├── prompts.py        # prompts en disco: un .md por prompt
├── frontmatter.py    # lectura/escritura del YAML de cabecera
└── static/
    ├── index.html
    ├── styles.css    # sistema visual: brutalismo moderno, temas claro y oscuro
    ├── app.js        # interfaz
    └── markdown.js   # renderizador de markdown
skills/               # tu biblioteca (incluye 3 skills de ejemplo)
prompts/              # tus prompts, uno por archivo (se crea al arrancar)
tests/
deploy/               # arranque automático y copias de seguridad
├── linux/            #   unidad de systemd
└── windows/          #   tarea programada y backup
docker/               # entrypoint de la imagen
Dockerfile            # despliegue en servidor con Docker
docker-compose.yml
skillsbook-servidor.*  # arranque en modo servidor (.bat y .sh)
DESPLIEGUE.md          # guía completa de despliegue en la LAN
```
