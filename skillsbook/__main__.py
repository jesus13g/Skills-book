"""Command line entry point: ``python3 -m skillsbook``.

Works in two modes:

* **Escritorio** — sin argumentos escucha en ``127.0.0.1`` y abre el navegador.
* **Servidor LAN** — con ``--host 0.0.0.0`` (o ``SKILLSBOOK_HOST``) escucha en
  toda la red, no abre navegador, no salta de puerto y puede pedir un token.
"""

from __future__ import annotations

import argparse
import errno
import ipaddress
import os
import signal
import socket
import sys
import webbrowser
from pathlib import Path

from . import __version__
from .prompts import default_prompts_root as prompts_sibling
from .server import serve

DEFAULT_PORT = 8777
DEFAULT_HOST = "127.0.0.1"
_TRUE = {"1", "true", "yes", "on", "si", "sí"}
_FALSE = {"0", "false", "no", "off"}


def env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable (``1/true/yes/on`` and friends)."""
    raw = (os.environ.get(name) or "").strip().lower()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    return default


def default_root() -> Path:
    env = os.environ.get("SKILLSBOOK_HOME")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent.parent / "skills"


def default_prompts(root: Path) -> Path:
    """Carpeta de prompts: ``SKILLSBOOK_PROMPTS`` o la hermana de la biblioteca."""
    env = os.environ.get("SKILLSBOOK_PROMPTS")
    if env:
        return Path(env).expanduser()
    return prompts_sibling(root)


def default_token() -> str:
    """Token from ``SKILLSBOOK_TOKEN`` or from ``SKILLSBOOK_TOKEN_FILE``.

    The file variant exists for Docker/Compose secrets, where putting the
    token in the environment is not ideal.
    """
    path = os.environ.get("SKILLSBOOK_TOKEN_FILE")
    if path:
        try:
            return Path(path).expanduser().read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SystemExit(f"No se pudo leer SKILLSBOOK_TOKEN_FILE ({path}): {exc}")
    return (os.environ.get("SKILLSBOOK_TOKEN") or "").strip()


def default_port() -> int:
    raw = (os.environ.get("SKILLSBOOK_PORT") or "").strip()
    if not raw:
        return DEFAULT_PORT
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"SKILLSBOOK_PORT no es un numero: '{raw}'.")


def is_loopback(host: str) -> bool:
    """True when ``host`` only reaches this machine."""
    if host in ("localhost", "localhost.localdomain"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def lan_ip() -> str | None:
    """Best guess at this machine's address on the LAN, or ``None``.

    ``connect`` on a UDP socket sends no packet: it just asks the routing
    table which interface would be used, so this works without network.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.settimeout(0.2)
            probe.connect(("192.0.2.1", 9))  # TEST-NET-1, nunca enrutada
            address = probe.getsockname()[0]
        if address and not address.startswith("127."):
            return address
    except OSError:
        pass
    try:
        address = socket.gethostbyname(socket.gethostname())
        return address if address and not address.startswith("127.") else None
    except OSError:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillsbook",
        description="Biblioteca local de skills de agentes (Claude, ChatGPT, opencode…).",
    )
    parser.add_argument("--dir", "-d", default=None, help="Carpeta de la biblioteca de skills.")
    parser.add_argument(
        "--prompts-dir",
        default=None,
        help="Carpeta de la biblioteca de prompts (por defecto, hermana de la de skills).",
    )
    parser.add_argument("--port", "-p", type=int, default=default_port(), help="Puerto HTTP.")
    parser.add_argument(
        "--host",
        default=os.environ.get("SKILLSBOOK_HOST", DEFAULT_HOST),
        help="Interfaz de escucha (0.0.0.0 para publicar en la LAN).",
    )
    parser.add_argument("--no-browser", action="store_true", help="No abrir el navegador.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Registrar cada peticion.")
    parser.add_argument(
        "--token",
        default=None,
        help="Exige este token para entrar (Basic auth: usuario libre, contrasena = token).",
    )
    parser.add_argument(
        "--strict-port",
        action="store_true",
        help="Fallar si el puerto esta ocupado en vez de saltar al siguiente libre.",
    )
    parser.add_argument(
        "--allow-path-import",
        dest="allow_path_import",
        action="store_true",
        default=None,
        help="Permitir importar carpetas por ruta del servidor (por defecto solo en local).",
    )
    parser.add_argument(
        "--no-path-import",
        dest="allow_path_import",
        action="store_false",
        help="Desactivar la importacion de carpetas por ruta del servidor.",
    )
    parser.add_argument("--version", action="version", version=f"skillsbook {__version__}")
    return parser


def _pick_port(host: str, port: int, strict: bool = False) -> int:
    """Return ``port``, or the next free one when it is already taken.

    In ``strict`` mode (servidor) no se salta de puerto: un despliegue tiene
    que escuchar donde dicen el firewall, el proxy y los marcadores de la
    gente, o fallar diciendolo.
    """
    last = port if strict else port + 19
    for candidate in range(port, last + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, candidate))
            except OSError as exc:
                if exc.errno in (errno.EADDRINUSE, errno.EACCES):
                    continue
                raise
            return candidate
    if strict:
        raise SystemExit(
            f"El puerto {port} esta ocupado en {host}. Libera el puerto o usa --port."
        )
    raise SystemExit(f"No hay puertos libres entre {port} y {port + 19}.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.dir).expanduser() if args.dir else default_root()
    prompts_root = Path(args.prompts_dir).expanduser() if args.prompts_dir else default_prompts(root)
    host = args.host
    local_only = is_loopback(host)

    token = args.token if args.token is not None else default_token()
    verbose = args.verbose or env_flag("SKILLSBOOK_VERBOSE")
    strict = args.strict_port or env_flag("SKILLSBOOK_STRICT_PORT") or not local_only

    # Importar una carpeta por ruta lee el disco del servidor: solo se permite
    # por defecto cuando la app es de una sola persona en su maquina.
    allow_path_import = args.allow_path_import
    if allow_path_import is None:
        allow_path_import = env_flag("SKILLSBOOK_ALLOW_PATH_IMPORT", default=local_only)

    port = _pick_port(host, args.port, strict)
    httpd, store = serve(
        str(root), host, port, verbose,
        token=token, allow_path_import=allow_path_import,
        prompts_root=str(prompts_root),
    )
    count = len(store.list_skills())
    prompt_count = len(httpd.prompts.list_prompts())

    print(f"  Skills Book {__version__}")
    print(f"  Biblioteca : {store.root}  ({count} skills)")
    print(f"  Prompts    : {httpd.prompts.root}  ({prompt_count} prompts)")
    if local_only:
        print(f"  Abierta en : http://{host}:{port}/")
    else:
        shown = host if host not in ("0.0.0.0", "::", "") else "0.0.0.0"
        print(f"  Escuchando : {shown}:{port}  (toda la red)")
        address = lan_ip() if shown == "0.0.0.0" else host
        if address:
            print(f"  En la LAN  : http://{address}:{port}/")
        print(
            "  Acceso     : "
            + ("token requerido (usuario libre, contrasena = token)" if token
               else "SIN token — cualquiera en la red puede editar y borrar")
        )
    if not allow_path_import:
        print("  Importar   : solo zip (importacion por ruta desactivada)")
    print("  Ctrl+C para parar.\n", flush=True)

    if local_only and not args.no_browser and os.environ.get("SKILLSBOOK_NO_BROWSER") != "1":
        try:
            webbrowser.open(f"http://{host}:{port}/")
        except Exception:
            pass

    def _stop(_signum, _frame):  # docker stop / systemctl stop
        raise KeyboardInterrupt

    for name in ("SIGTERM", "SIGINT"):
        handler = getattr(signal, name, None)
        if handler is not None:
            try:
                signal.signal(handler, _stop)
            except (ValueError, OSError):  # pragma: no cover - hilo secundario
                pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Hasta luego.", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
