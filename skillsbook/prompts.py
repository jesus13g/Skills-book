"""Filesystem-backed prompt library.

Un prompt es un bloque de texto que se reutiliza mucho pero que no llega a ser
una skill: no tiene scripts, ni referencias, ni carpeta propia. Por eso aqui
cada prompt es **un archivo suelto**::

    <biblioteca-de-prompts>/
        resumen-ejecutivo.md
        correo-de-seguimiento.md

El formato es el mismo que el de ``SKILL.md`` (frontmatter YAML + cuerpo), asi
que el archivo se sigue leyendo bien desde la terminal, desde git y desde
cualquier editor de markdown::

    ---
    name: Resumen ejecutivo
    tags: [redaccion, cliente]
    updated: 2026-08-13T10:04:11
    ---

    Resume el siguiente texto en cinco vinetas...
"""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from . import frontmatter
from .store import (
    Conflict,
    NotFound,
    StoreError,
    _as_list,
    _check_slug,
    _now,
    _SLUG_RE,
    slugify,
)

PROMPT_SUFFIX = ".md"
ZIP_PREFIX = "prompts/"
MAX_PROMPT_BYTES = 512 * 1024
_MANAGED_KEYS = {"name", "tags", "updated"}


class PromptStore:
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ paths
    def path_for(self, slug: str) -> Path:
        """Archivo de un prompt.

        El slug pasa por ``_check_slug``, que solo admite minusculas, numeros,
        guiones y guiones bajos: no hay forma de escribir una ruta que salga de
        la carpeta de prompts.
        """
        return self.root / (_check_slug(slug) + PROMPT_SUFFIX)

    def _existing(self, slug: str) -> Path:
        path = self.path_for(slug)
        if not path.is_file() or path.is_symlink():
            raise NotFound(f"El prompt '{slug}' no existe.")
        return path

    # ----------------------------------------------------------------- reading
    def _read(self, path: Path) -> tuple[dict, str]:
        text = path.read_text(encoding="utf-8", errors="replace")
        return frontmatter.parse(text)

    def summary(self, slug: str) -> dict:
        """Datos de un prompt, con el texto incluido.

        El texto viaja tambien en el listado: son bloques cortos y el boton de
        copiar de cada tarjeta lo necesita sin pedir nada mas al servidor.
        """
        path = self._existing(slug)
        meta, body = self._read(path)
        stat = path.stat()
        return {
            "slug": slug,
            "name": str(meta.get("name") or slug),
            "tags": _as_list(meta.get("tags")),
            "text": body,
            "updated": str(meta.get("updated") or ""),
            "size_bytes": stat.st_size,
            "mtime": stat.st_mtime,
        }

    def list_prompts(self) -> list[dict]:
        prompts = []
        try:
            entries = sorted(self.root.iterdir())
        except OSError:
            return prompts
        for entry in entries:
            if not entry.is_file() or entry.is_symlink():
                continue
            if entry.suffix.lower() != PROMPT_SUFFIX:
                continue
            if not _SLUG_RE.match(entry.stem):
                continue
            try:
                prompts.append(self.summary(entry.stem))
            except StoreError:
                continue
        prompts.sort(key=lambda item: item["name"].lower())
        return prompts

    def get_prompt(self, slug: str) -> dict:
        path = self._existing(slug)
        meta, _ = self._read(path)
        data = self.summary(slug)
        data["extra"] = {key: value for key, value in meta.items() if key not in _MANAGED_KEYS}
        return data

    # ----------------------------------------------------------------- writing
    def _build_meta(self, data: dict, previous: dict | None = None) -> dict:
        meta: dict = {}
        meta["name"] = str(data.get("name") or "").strip() or str(data.get("slug") or "")
        tags = _as_list(data.get("tags"))
        if tags:
            meta["tags"] = tags
        # Se conservan las claves de frontmatter que la app no conoce, pero
        # nunca se resucita una que el usuario acaba de vaciar (tags).
        for key, value in (previous or {}).items():
            if key in _MANAGED_KEYS or key in meta:
                continue
            meta[key] = value
        meta["updated"] = _now()
        return meta

    def _write(self, path: Path, meta: dict, text: str) -> None:
        document = frontmatter.dump(meta, text)
        if len(document.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise StoreError("El prompt supera el limite de 512 KB.")
        path.write_text(document, encoding="utf-8")

    @staticmethod
    def _check_text(text) -> str:
        text = str(text or "")
        if not text.strip():
            raise StoreError("El prompt no puede estar vacio: es el texto que vas a copiar.")
        return text

    def create_prompt(self, data: dict) -> dict:
        name = str(data.get("name") or "").strip()
        if not name:
            raise StoreError("El nombre del prompt es obligatorio.")
        slug = _check_slug(data.get("slug") or slugify(name))
        text = self._check_text(data.get("text"))
        path = self.root / (slug + PROMPT_SUFFIX)
        if path.exists():
            raise Conflict(f"Ya existe un prompt con el identificador '{slug}'.")
        self._write(path, self._build_meta({**data, "name": name, "slug": slug}), text)
        return self.get_prompt(slug)

    def update_prompt(self, slug: str, data: dict) -> dict:
        path = self._existing(slug)
        previous_meta, previous_body = self._read(path)
        if "name" in data and not str(data.get("name") or "").strip():
            raise StoreError("El nombre del prompt es obligatorio.")
        text = self._check_text(data.get("text", previous_body))
        merged = {
            "name": data.get("name", previous_meta.get("name", slug)),
            "tags": data.get("tags", _as_list(previous_meta.get("tags"))),
            "slug": slug,
        }
        self._write(path, self._build_meta(merged, previous_meta), text)

        new_slug = data.get("slug")
        if new_slug and _check_slug(new_slug) != slug:
            slug = self.rename_prompt(slug, new_slug)
        return self.get_prompt(slug)

    def rename_prompt(self, slug: str, new_slug: str) -> str:
        path = self._existing(slug)
        target = self.root / (_check_slug(new_slug) + PROMPT_SUFFIX)
        if target.exists():
            raise Conflict(f"Ya existe un prompt con el identificador '{new_slug}'.")
        path.rename(target)
        return target.stem

    def delete_prompt(self, slug: str) -> None:
        self._existing(slug).unlink()

    def duplicate_prompt(self, slug: str, new_slug: str | None = None) -> dict:
        source = self._existing(slug)
        new_slug = _check_slug(new_slug or _unique_slug(self.root, f"{slug}-copia"))
        target = self.root / (new_slug + PROMPT_SUFFIX)
        if target.exists():
            raise Conflict(f"Ya existe un prompt con el identificador '{new_slug}'.")
        meta, body = self._read(source)
        meta["name"] = f"{meta.get('name', slug)} (copia)"
        meta["updated"] = _now()
        self._write(target, meta, body)
        return self.get_prompt(new_slug)

    # ------------------------------------------------------------ import/export
    def export_members(self) -> list[tuple[str, Path]]:
        """Pares ``(nombre dentro del zip, archivo)`` para el zip de la biblioteca."""
        return [
            (f"{ZIP_PREFIX}{prompt['slug']}{PROMPT_SUFFIX}",
             self.root / (prompt["slug"] + PROMPT_SUFFIX))
            for prompt in self.list_prompts()
        ]

    def import_zip(self, blob: bytes) -> list[str]:
        """Restaura los prompts de un zip exportado (los de ``prompts/``)."""
        try:
            archive = zipfile.ZipFile(io.BytesIO(blob))
        except zipfile.BadZipFile as exc:
            raise StoreError("El archivo no es un zip valido.") from exc

        imported: list[str] = []
        for name in sorted(archive.namelist()):
            if not name.startswith(ZIP_PREFIX) or name.endswith("/"):
                continue
            rel = name[len(ZIP_PREFIX):]
            if "/" in rel or not rel.lower().endswith(PROMPT_SUFFIX):
                continue
            slug = _unique_slug(self.root, slugify(rel[: -len(PROMPT_SUFFIX)]) or "prompt-importado")
            with archive.open(name) as source:
                raw = source.read(MAX_PROMPT_BYTES + 1)
            if len(raw) > MAX_PROMPT_BYTES:
                continue
            meta, body = frontmatter.parse(raw.decode("utf-8", errors="replace"))
            meta.setdefault("name", slug)
            meta["updated"] = _now()
            self._write(self.root / (slug + PROMPT_SUFFIX), meta, body)
            imported.append(slug)
        return imported

    # ---------------------------------------------------------------- searching
    def search(self, query: str) -> list[dict]:
        query = (query or "").strip().lower()
        if not query:
            return []
        hits = []
        for prompt in self.list_prompts():
            matches = []
            for number, line in enumerate(prompt["text"].splitlines(), start=1):
                if query in line.lower():
                    matches.append({"line": number, "text": line.strip()[:200]})
                    if len(matches) >= 20:
                        break
            if not matches and query in prompt["name"].lower():
                matches.append({"line": 0, "text": prompt["name"]})
            if matches:
                hits.append({"slug": prompt["slug"], "name": prompt["name"], "matches": matches})
        return hits

    def stats(self) -> dict:
        prompts = self.list_prompts()
        tags: dict[str, int] = {}
        for prompt in prompts:
            for tag in prompt["tags"]:
                tags[tag] = tags.get(tag, 0) + 1
        return {
            "root": str(self.root),
            "count": len(prompts),
            "size_bytes": sum(prompt["size_bytes"] for prompt in prompts),
            "tags": dict(sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))),
        }


def _unique_slug(root: Path, slug: str) -> str:
    slug = slug or "prompt"
    candidate = slug
    index = 2
    while (root / (candidate + PROMPT_SUFFIX)).exists():
        candidate = f"{slug}-{index}"
        index += 1
    return candidate


def default_prompts_root(skills_root: str | os.PathLike) -> Path:
    """Carpeta hermana de la biblioteca de skills: ``.../skills`` -> ``.../prompts``."""
    path = Path(skills_root).expanduser()
    return path.parent / "prompts"
