# Desplegar Skills Book en un servidor de la organización

Guía para dejar la biblioteca funcionando en una máquina de la red local, accesible
desde el navegador de cualquiera en la oficina: `http://IP-DEL-SERVIDOR:8777/`.

Dos caminos, el mismo resultado:

| | Cuándo |
| --- | --- |
| **[Docker](#opción-a--docker)** | La máquina ya tiene Docker. Es la opción recomendada: se actualiza y se reinicia sola. |
| **[.bat / servicio de Windows](#opción-b--windows-con-bat)** | Servidor Windows sin Docker. Solo necesita Python instalado. |

---

## Antes de nada: dónde viven los datos

La app **no tiene base de datos**. Todo el estado es una carpeta con una subcarpeta
por skill:

```
<biblioteca>/
├── revision-de-codigo/
│   ├── SKILL.md          ← frontmatter + instrucciones
│   ├── scripts/…
│   └── references/…
└── migracion-sql/
    └── SKILL.md
```

Eso tiene tres consecuencias para el despliegue:

1. **La copia de seguridad es copiar una carpeta.** No hay que exportar ni volcar nada.
2. **La biblioteca sobrevive a la app.** Puedes borrar el contenedor, reinstalar Python o
   cambiar de máquina: mientras conserves la carpeta, no pierdes nada.
3. **La carpeta se elige con `SKILLSBOOK_HOME`** (o `--dir`). En Docker es un volumen; en
   Windows, por defecto, `data\skills` junto al `.bat`.

Dónde acaba siendo, en cada modo:

| Despliegue | Carpeta de datos |
| --- | --- |
| Docker (compose de este repo) | `./data/skills` del host → `/data/skills` en el contenedor |
| Windows `.bat` | `data\skills` junto al `.bat`, o lo que pongas en `servidor.env` |
| systemd (Linux sin Docker) | `/var/lib/skillsbook/skills` |

> **Escrituras a la vez.** No hay bloqueo ni historial: si dos personas guardan el mismo
> archivo en el mismo momento, gana el último. Con un equipo pequeño no da problemas; si
> quieres red de seguridad, haz `git init` en la carpeta de la biblioteca y programa un
> commit diario — son archivos de texto, el diff se lee perfectamente.

---

## Opción A — Docker

### Instalar

```bash
git clone https://github.com/jesus13g/skills-book.git /opt/skillsbook
cd /opt/skillsbook

# 1. Un token de acceso (recomendado; ver "Quién puede entrar")
python3 -c "import secrets; print('SKILLSBOOK_TOKEN=' + secrets.token_urlsafe(24))" > .env

# 2. La carpeta de datos, propiedad del uid con el que corre el contenedor
mkdir -p data/skills && sudo chown -R 1000:1000 data

# 3. Arrancar
docker compose up -d
docker compose logs -f      # Ctrl+C para dejar de mirar; el servicio sigue
```

Queda escuchando en el puerto `8777` de la máquina. Al reiniciar el servidor, Docker lo
vuelve a levantar solo (`restart: unless-stopped`).

### El día a día

```bash
docker compose ps                       # ¿está vivo? (mira la columna de salud)
docker compose logs -f --tail 100       # registro
docker compose restart                  # reiniciar
docker compose down                     # parar (los datos se quedan)
git pull && docker compose up -d --build   # actualizar a la última versión
```

### Ajustes

Todo se toca en `docker-compose.yml`:

- **Otro puerto:** `ports: - "80:8777"` (el 80 hace que la URL sea solo `http://IP/`).
- **Publicar en una sola tarjeta de red:** `ports: - "192.168.1.50:8777:8777"`.
- **Otra carpeta de datos:** `volumes: - /srv/skills:/data/skills`.
- **Permisos:** si prefieres no hacer `chown`, descomenta `user: "1000:1000"` y pon ahí
  el uid:gid dueño de la carpeta (`id -u`, `id -g`).

---

## Opción B — Windows con `.bat`

### Requisito

Python 3.9 o superior, instalado **para todos los usuarios** y marcando *"Add python.exe
to PATH"*. Comprobación:

```bat
python --version
```

### Instalar

1. Copia el repositorio al servidor, por ejemplo `C:\SkillsBook`.
2. Copia `servidor.env.ejemplo` a `servidor.env` y edítalo — como mínimo pon un
   `SKILLSBOOK_TOKEN`.
3. Doble clic en `skillsbook-servidor.bat`. Se queda en primer plano; ciérralo con Ctrl+C.

Eso ya funciona, pero se cae si alguien cierra la sesión. Para dejarlo permanente:

```
Botón derecho en deploy\windows\instalar-servicio.bat → Ejecutar como administrador
```

Ese script hace dos cosas: abre el puerto en el firewall (solo perfiles *privado* y
*dominio*, nunca el público) y crea una tarea programada que lanza la app al encender la
máquina, como SYSTEM y sin que nadie tenga que iniciar sesión.

### El día a día

```bat
schtasks /query /tn "Skills Book"     :: ¿está registrada?
schtasks /run   /tn "Skills Book"     :: arrancar
schtasks /end   /tn "Skills Book"     :: parar
deploy\windows\desinstalar-servicio.bat   :: quitar tarea y regla de firewall
```

Para actualizar: `git pull` (o copiar los archivos nuevos encima), parar y volver a
arrancar la tarea. La carpeta `data\skills` no se toca nunca.

---

## Opción C — Linux sin Docker

```bash
sudo useradd --system --home /var/lib/skillsbook skillsbook
sudo git clone https://github.com/jesus13g/skills-book.git /opt/skillsbook
sudo cp /opt/skillsbook/deploy/linux/skillsbook.service /etc/systemd/system/
sudo nano /etc/systemd/system/skillsbook.service     # revisa rutas, puerto y token
sudo systemctl daemon-reload
sudo systemctl enable --now skillsbook
journalctl -u skillsbook -f
```

Para lanzarlo a mano sin systemd: `./skillsbook-servidor.sh`.

---

## Configuración

Las mismas variables valen para los tres modos (en `servidor.env`, en `.env` de Docker o
en el entorno). Hay un archivo comentado listo para copiar: `servidor.env.ejemplo`.

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `SKILLSBOOK_HOME` | `./skills` | Carpeta de la biblioteca. **Es todo el estado de la app.** |
| `SKILLSBOOK_HOST` | `127.0.0.1` | `0.0.0.0` publica en toda la LAN. |
| `SKILLSBOOK_PORT` | `8777` | Puerto HTTP. |
| `SKILLSBOOK_TOKEN` | *(vacío)* | Contraseña de acceso. Vacío = abierto a toda la red. |
| `SKILLSBOOK_TOKEN_FILE` | *(vacío)* | Lee el token de un archivo (secretos de Docker). |
| `SKILLSBOOK_ALLOW_PATH_IMPORT` | solo en local | Permite importar carpetas por ruta del servidor. |
| `SKILLSBOOK_STRICT_PORT` | activo en red | Falla si el puerto está ocupado en vez de saltar al siguiente. |
| `SKILLSBOOK_NO_BROWSER` | — | `1` para no abrir el navegador. |
| `SKILLSBOOK_VERBOSE` | `0` | `1` registra cada petición. |

Todas tienen su equivalente en la línea de órdenes (`--dir`, `--host`, `--port`,
`--token`, `--strict-port`, `--no-path-import`, `--verbose`), que manda sobre el entorno.

### Lo que cambia solo al salir a la red

Cuando `--host` no es `localhost`, la app entra en modo servidor sin que tengas que
pedirlo:

- **No abre el navegador** (en un servidor no hay nadie mirando la pantalla).
- **No salta de puerto.** En local, si el 8777 está ocupado, prueba el 8778; en un
  servidor eso sería una trampa —el firewall, los marcadores y el proxy apuntan a un
  puerto fijo—, así que falla diciendo qué pasa.
- **Desactiva la importación por ruta**, porque leería el disco del servidor. La
  importación por zip sigue funcionando y el campo desaparece de la interfaz.

---

## Quién puede entrar

La app **no tiene usuarios ni contraseñas**. Sobre la mesa hay dos opciones:

**1. Token (recomendado).** Con `SKILLSBOOK_TOKEN`, el navegador pide usuario y
contraseña la primera vez: el usuario da igual, la contraseña es el token. Lo recuerda
mientras la ventana siga abierta, y sirve también para las descargas y para los scripts:

```bash
curl -u equipo:EL-TOKEN http://192.168.1.50:8777/api/skills
curl -H "X-Skillsbook-Token: EL-TOKEN" http://192.168.1.50:8777/api/stats
```

**2. Sin token.** Válido solo si la red ya está controlada, porque cualquiera que llegue
al puerto puede crear, editar y **borrar** skills. La app avisa al arrancar.

Cosas que conviene tener claras:

- **El tráfico va en claro (HTTP).** Dentro de la LAN suele ser aceptable; si va a salir
  de ahí, ponlo detrás de un nginx/Caddy con TLS. El token viaja en cada petición, así que
  sin TLS es sniffable en la propia red.
- **No lo publiques en internet** sin poner delante un proxy con TLS y, a ser posible, el
  SSO de la organización.
- **`/healthz` no pide token** a propósito: es la sonda de Docker y systemd. Solo responde
  `{"ok": true}` y cuántas skills hay.
- Las protecciones de siempre siguen en pie: las rutas no pueden salir de la carpeta de la
  skill, los zips no pueden escribir fuera de la biblioteca y el markdown se escapa antes
  de pintarse.

---

## Copias de seguridad

```bash
./deploy/copia-seguridad.sh                          # → ./backups/skillsbook-AAAAMMDD-HHMMSS.tar.gz
./deploy/copia-seguridad.sh /srv/skills /mnt/nas     # origen y destino a medida
```

```bat
deploy\windows\copia-seguridad.bat
```

Los dos guardan las últimas 14 copias y borran las anteriores. Para dejarlo automático:

```bash
# Linux: a las 22:00 todos los días
0 22 * * * /opt/skillsbook/deploy/copia-seguridad.sh >> /var/log/skillsbook-backup.log 2>&1
```

```bat
:: Windows
schtasks /create /tn "Skills Book backup" /tr "C:\SkillsBook\deploy\windows\copia-seguridad.bat" /sc daily /st 22:00 /ru SYSTEM
```

**Restaurar** es descomprimir encima de la carpeta de la biblioteca. No hace falta parar
el servidor, aunque es más limpio hacerlo.

Desde la interfaz también tienes *Exportar todo* (un zip con la biblioteca entera), útil
como copia puntual antes de tocar algo.

---

## Comprobar que funciona

```bash
curl http://IP-DEL-SERVIDOR:8777/healthz        # {"ok": true, "skills": 3}
curl -u x:EL-TOKEN http://IP-DEL-SERVIDOR:8777/api/stats
```

Con Docker, `docker compose ps` muestra la columna de salud, que sale de esa misma sonda.

## Si algo va mal

| Síntoma | Qué mirar |
| --- | --- |
| Desde el servidor sí, desde otro PC no | Firewall del servidor y que `SKILLSBOOK_HOST` sea `0.0.0.0`, no `127.0.0.1`. |
| «El puerto 8777 está ocupado» | Otra copia ya arrancada (`docker compose ps`, `schtasks /query`), o cambia `SKILLSBOOK_PORT`. |
| El navegador pide contraseña una y otra vez | El token no coincide. El usuario da igual; la contraseña es el token exacto, sin espacios. |
| Docker: «no puedo escribir en /data/skills» | `sudo chown -R 1000:1000 data`, o usa `user:` en el compose. |
| La biblioteca sale vacía tras mover la app | `SKILLSBOOK_HOME` apunta a otro sitio. La cabecera del arranque dice qué carpeta está usando. |
| Windows: «no se encontró Python» | Python no está en el PATH de SYSTEM. Reinstálalo para todos los usuarios con *Add to PATH*. |

En el registro de arranque siempre está la verdad: carpeta de la biblioteca, interfaz,
puerto y si hay token o no.
