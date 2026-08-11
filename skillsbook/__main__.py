"""Command line entry point: ``python3 -m skillsbook``."""

from __future__ import annotations

import argparse
import errno
import os
import socket
import sys
import webbrowser
from pathlib import Path

from . import __version__
from .server import serve

DEFAULT_PORT = 8777


def default_root() -> Path:
    env = os.environ.get("SKILLSBOOK_HOME")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent.parent / "skills"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillsbook",
        description="Biblioteca local de skills de agentes (Claude, ChatGPT, opencode…).",
    )
    parser.add_argument("--dir", "-d", default=None, help="Carpeta de la biblioteca de skills.")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help="Puerto HTTP.")
    parser.add_argument("--host", default="127.0.0.1", help="Interfaz de escucha.")
    parser.add_argument("--no-browser", action="store_true", help="No abrir el navegador.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Registrar cada peticion.")
    parser.add_argument("--version", action="version", version=f"skillsbook {__version__}")
    return parser


def _pick_port(host: str, port: int) -> int:
    """Return ``port``, or the next free one when it is already taken."""
    for candidate in range(port, port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, candidate))
            except OSError as exc:
                if exc.errno in (errno.EADDRINUSE, errno.EACCES):
                    continue
                raise
            return candidate
    raise SystemExit(f"No hay puertos libres entre {port} y {port + 19}.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.dir).expanduser() if args.dir else default_root()
    port = _pick_port(args.host, args.port)

    httpd, store = serve(str(root), args.host, port, args.verbose)
    url = f"http://{args.host}:{port}/"
    count = len(store.list_skills())

    print(f"  Skills Book {__version__}")
    print(f"  Biblioteca : {store.root}  ({count} skills)")
    print(f"  Abierta en : {url}")
    print("  Ctrl+C para parar.\n")

    if not args.no_browser and os.environ.get("SKILLSBOOK_NO_BROWSER") != "1":
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Hasta luego.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
