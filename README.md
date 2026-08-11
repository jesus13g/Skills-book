# 📚 Skills Book

Biblioteca **local** de skills para agentes — Claude, ChatGPT, opencode, Cursor, Copilot, Gemini
o cualquier otro. Guarda, revisa, crea, edita y borra skills desde el navegador, con sus
carpetas de scripts y documentos de apoyo.

Sin base de datos, sin cuenta, sin conexión a internet y **sin dependencias**: solo Python 3.9+.
Cada skill es una carpeta de verdad en tu disco, así que sigue siendo utilizable desde la
terminal, desde git y desde los propios agentes.

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
| `--port N` | Puerto HTTP (por defecto `8777`). |
| `--host H` | Interfaz de escucha (por defecto `127.0.0.1`). |
| `--no-browser` | No abrir el navegador al arrancar. |
| `--verbose` | Registrar cada petición en consola. |

También puedes fijar la biblioteca con la variable `SKILLSBOOK_HOME`:

```bash
SKILLSBOOK_HOME=~/.claude/skills python3 -m skillsbook
```

Eso te deja editar directamente las skills que ya usa tu agente.

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

## Qué puedes hacer

**Con las skills**
- Crear, editar y borrar, con el identificador (nombre de carpeta) renombrable.
- Duplicar una skill entera con sus archivos.
- Marcar con qué agentes es compatible y etiquetarlas.
- Filtrar por agente o etiqueta, buscar por nombre y descripción, o buscar texto **dentro** de
  todos los archivos de todas las skills.
- Ver el `SKILL.md` renderizado como markdown: títulos, listas, tablas, código y citas.

**Con los archivos de cada skill**
- Árbol de carpetas con cualquier profundidad.
- Crear archivos y carpetas, renombrar, mover y borrar.
- Editor de texto integrado con guardado por `Ctrl/Cmd + S`.
- Subir archivos binarios (imágenes, PDF, zip…) y previsualizar imágenes.
- Descargar cualquier archivo suelto.
- Los `.sh` se marcan como ejecutables automáticamente.

**Entrar y salir**
- Exportar una skill o la biblioteca entera como zip.
- Importar un zip (con una o varias skills) o copiar una carpeta local, p. ej. `~/.claude/skills`.

### Atajos

| Tecla | Acción |
| --- | --- |
| `/` | Ir al buscador |
| `Intro` en el buscador | Buscar dentro del contenido de los archivos |
| `Ctrl/Cmd + S` | Guardar el archivo o el formulario abierto |

---

## API

La interfaz es solo un cliente de esta API; puedes usarla desde `curl` o tus propios scripts.

| Método y ruta | Qué hace |
| --- | --- |
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
| `GET /api/export` | Zip de toda la biblioteca |
| `POST /api/import` | Importar `zip_base64` o `path` |
| `GET /api/search?q=…` | Buscar texto dentro de los archivos |
| `GET /api/stats` | Totales, agentes y etiquetas |

```bash
curl -s localhost:8777/api/skills | python3 -m json.tool

curl -s -X POST localhost:8777/api/skills \
  -H 'Content-Type: application/json' \
  -d '{"name":"Mi skill","description":"Qué hace y cuándo usarla","agents":["claude"]}'
```

---

## Seguridad

Es una app local, pero trata los datos con cuidado:

- Solo escucha en `127.0.0.1` salvo que cambies `--host`.
- Todas las rutas se resuelven dentro de la carpeta de la skill: `..`, rutas absolutas y
  enlaces simbólicos que apunten fuera se rechazan.
- Los zips que importas no pueden escribir fuera de la biblioteca (*zip slip*).
- El markdown se escapa antes de renderizar: el HTML dentro de una skill se muestra, no se ejecuta.

---

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

33 pruebas sobre el frontmatter, el almacén en disco (incluidos los intentos de fuga de ruta)
y la API HTTP completa. La interfaz se validó además con Playwright sobre Chromium:
listado, renderizado de markdown, árbol de archivos, edición con guardado, alta y baja de
skills, filtros y búsqueda.

---

## Estructura del proyecto

```
skillsbook/
├── __main__.py       # CLI: puertos, navegador, arranque
├── server.py         # servidor HTTP y rutas de la API
├── store.py          # skills en disco: CRUD, archivos, zip, búsqueda
├── frontmatter.py    # lectura/escritura del YAML de cabecera
└── static/
    ├── index.html
    ├── styles.css    # tema claro y oscuro automáticos
    ├── app.js        # interfaz
    └── markdown.js   # renderizador de markdown
skills/               # tu biblioteca (incluye 3 skills de ejemplo)
tests/
```
