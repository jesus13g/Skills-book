"""HTTP layer for Skills Book.

Standard library only: ``ThreadingHTTPServer`` serves the static UI and a small
JSON API on top of :class:`skillsbook.store.SkillStore`.
"""

from __future__ import annotations

import base64
import hmac
import json
import mimetypes
import posixpath
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .store import Conflict, NotFound, SkillStore, StoreError, slugify

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY_BYTES = 96 * 1024 * 1024
PUBLIC_PATHS = ("/healthz",)  # sin token: sondas de Docker, systemd o el balanceador


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _match(pattern: str, path: str) -> dict | None:
    regex = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$"
    found = re.match(regex, path)
    return {key: unquote(value) for key, value in found.groupdict().items()} if found else None


class Handler(BaseHTTPRequestHandler):
    server_version = "SkillsBook"
    protocol_version = "HTTP/1.1"
    store: SkillStore

    # ------------------------------------------------------------------ helpers
    def log_message(self, fmt, *args):  # quieter console
        if self.server.verbose:  # type: ignore[attr-defined]
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, status: int = 200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(status, payload, "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise ApiError("El cuerpo de la peticion es demasiado grande.", 413)
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError("JSON no valido.") from exc
        if not isinstance(data, dict):
            raise ApiError("Se esperaba un objeto JSON.")
        return data

    @property
    def query(self) -> dict:
        raw = parse_qs(urlparse(self.path).query)
        return {key: values[0] for key, values in raw.items()}

    # --------------------------------------------------------------------- auth
    def _authorized(self) -> bool:
        """Basic auth (contrasena = token) o cabecera ``X-Skillsbook-Token``.

        Basic auth es lo unico que el navegador sabe hacer solo: pide las
        credenciales, las recuerda y las manda tambien en las descargas
        (``/api/export``), sin tocar el frontend.
        """
        token = self.server.token  # type: ignore[attr-defined]
        if not token:
            return True
        header = self.headers.get("Authorization") or ""
        if header[:6].lower() == "basic ":
            try:
                decoded = base64.b64decode(header[6:].strip()).decode("utf-8")
            except Exception:
                decoded = ""
            password = decoded.partition(":")[2]
            if hmac.compare_digest(password, token) or hmac.compare_digest(decoded, token):
                return True
        supplied = self.headers.get("X-Skillsbook-Token") or ""
        return bool(supplied) and hmac.compare_digest(supplied, token)

    def _ask_for_credentials(self):
        # El cuerpo de la peticion se queda sin leer, asi que esta conexion ya
        # no es reutilizable: se cierra para no confundir al siguiente mensaje.
        self.close_connection = True
        body = json.dumps({"error": "Necesitas el token de acceso."}).encode("utf-8")
        self._send(
            401, body, "application/json; charset=utf-8",
            {
                "WWW-Authenticate": 'Basic realm="Skills Book", charset="UTF-8"',
                "Connection": "close",
            },
        )

    # -------------------------------------------------------------------- verbs
    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method: str):
        path = posixpath.normpath(unquote(urlparse(self.path).path))
        try:
            if path in PUBLIC_PATHS:
                return self._json({"ok": True, "skills": len(self.server.store.list_skills())})
            if not self._authorized():
                return self._ask_for_credentials()
            if path.startswith("/api/"):
                self._api(method, path)
            elif method == "GET":
                self._static(path)
            else:
                self._json({"error": "Ruta no encontrada."}, 404)
        except ApiError as exc:
            self._json({"error": str(exc)}, exc.status)
        except (NotFound, Conflict, StoreError) as exc:
            self._json({"error": str(exc)}, getattr(exc, "status", 400))
        except BrokenPipeError:
            pass
        except Exception as exc:  # pragma: no cover - defensive
            self._json({"error": f"Error interno: {exc}"}, 500)

    # ------------------------------------------------------------------- static
    def _static(self, path: str):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC_DIR / rel).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            self._json({"error": "Ruta no permitida."}, 403)
            return
        if not target.is_file():
            target = STATIC_DIR / "index.html"
            if not target.is_file():
                self._json({"error": "Interfaz no encontrada."}, 404)
                return
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    # ---------------------------------------------------------------------- api
    def _api(self, method: str, path: str):
        store = self.server.store  # type: ignore[attr-defined]

        if method == "GET" and path == "/api/stats":
            stats = store.stats()
            stats["path_import"] = bool(self.server.allow_path_import)  # type: ignore[attr-defined]
            return self._json(stats)

        if method == "GET" and path == "/api/skills":
            return self._json({"skills": store.list_skills()})

        if method == "POST" and path == "/api/skills":
            return self._json(store.create_skill(self._read_json()), 201)

        if method == "GET" and path == "/api/search":
            return self._json({"results": store.search(self.query.get("q", ""))})

        if method == "GET" and path == "/api/export":
            blob = store.export_all_zip()
            return self._send(
                200, blob, "application/zip",
                {"Content-Disposition": 'attachment; filename="skills-book.zip"'},
            )

        if method == "POST" and path == "/api/import":
            data = self._read_json()
            if data.get("path"):
                if not self.server.allow_path_import:  # type: ignore[attr-defined]
                    raise ApiError(
                        "La importacion por ruta esta desactivada en este servidor: "
                        "sube un zip.",
                        403,
                    )
                return self._json({"imported": store.import_folder(str(data["path"]))}, 201)
            raw = data.get("zip_base64") or ""
            if not raw:
                raise ApiError("Falta el zip o la ruta a importar.")
            try:
                blob = base64.b64decode(raw.split(",")[-1], validate=False)
            except Exception as exc:
                raise ApiError("El zip enviado no se pudo decodificar.") from exc
            return self._json({"imported": store.import_zip(blob)}, 201)

        if method == "POST" and path == "/api/slugify":
            return self._json({"slug": slugify(self._read_json().get("name", ""))})

        params = _match("/api/skills/{slug}", path)
        if params:
            slug = params["slug"]
            if method == "GET":
                return self._json(store.get_skill(slug))
            if method == "PUT":
                return self._json(store.update_skill(slug, self._read_json()))
            if method == "DELETE":
                store.delete_skill(slug)
                return self._json({"ok": True})

        params = _match("/api/skills/{slug}/duplicate", path)
        if params and method == "POST":
            data = self._read_json()
            return self._json(store.duplicate_skill(params["slug"], data.get("slug")), 201)

        params = _match("/api/skills/{slug}/tree", path)
        if params and method == "GET":
            return self._json({"tree": store.tree(params["slug"])})

        params = _match("/api/skills/{slug}/file", path)
        if params:
            slug = params["slug"]
            if method == "GET":
                return self._json(store.read_file(slug, self.query.get("path", "")))
            if method == "PUT":
                data = self._read_json()
                rel = str(data.get("path") or "")
                if not rel:
                    raise ApiError("Falta la ruta del archivo.")
                if data.get("base64") is not None:
                    blob = base64.b64decode(str(data["base64"]).split(",")[-1])
                    return self._json(store.write_binary(slug, rel, blob))
                return self._json(store.write_file(slug, rel, data.get("content", "")))
            if method == "DELETE":
                store.delete_path(slug, self.query.get("path", ""))
                return self._json({"ok": True})

        params = _match("/api/skills/{slug}/raw", path)
        if params and method == "GET":
            slug = params["slug"]
            rel = self.query.get("path", "")
            target = store.resolve(slug, rel)
            if not target.is_file():
                raise ApiError("No es un archivo.", 400)
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            disposition = "inline" if ctype.startswith(("image/", "text/")) else "attachment"
            return self._send(
                200, target.read_bytes(), ctype,
                {"Content-Disposition": f'{disposition}; filename="{target.name}"'},
            )

        params = _match("/api/skills/{slug}/folder", path)
        if params and method == "POST":
            data = self._read_json()
            return self._json(store.create_folder(params["slug"], str(data.get("path") or "")), 201)

        params = _match("/api/skills/{slug}/move", path)
        if params and method == "POST":
            data = self._read_json()
            return self._json(
                store.move_path(params["slug"], str(data.get("path") or ""), str(data.get("to") or ""))
            )

        params = _match("/api/skills/{slug}/export", path)
        if params and method == "GET":
            slug = params["slug"]
            blob = store.export_zip(slug)
            return self._send(
                200, blob, "application/zip",
                {"Content-Disposition": f'attachment; filename="{slug}.zip"'},
            )

        self._json({"error": "Ruta no encontrada."}, 404)


class SkillsBookServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address,
        store: SkillStore,
        verbose: bool = False,
        token: str = "",
        allow_path_import: bool = True,
    ):
        super().__init__(address, Handler)
        self.store = store
        self.verbose = verbose
        self.token = token or ""
        self.allow_path_import = allow_path_import


def serve(
    root: str,
    host: str = "127.0.0.1",
    port: int = 8777,
    verbose: bool = False,
    *,
    token: str = "",
    allow_path_import: bool = True,
):
    """Build a ready-to-run server bound to ``host:port`` over ``root``.

    ``token`` protege todo salvo ``/healthz``; ``allow_path_import`` controla
    si ``POST /api/import`` acepta rutas del disco del servidor.
    """
    store = SkillStore(root)
    httpd = SkillsBookServer((host, port), store, verbose, token, allow_path_import)
    return httpd, store
