"""Filesystem-backed skill library.

Every skill is a real directory on disk::

    <library>/<slug>/
        SKILL.md          # YAML frontmatter + markdown body
        scripts/…         # arbitrary extra folders and files
        references/…

Nothing is hidden in a database, so the library stays usable straight from a
terminal, git, or the agent runtimes themselves.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import time
import unicodedata
import zipfile
from pathlib import Path

from . import frontmatter

SKILL_FILE = "SKILL.md"
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
KNOWN_AGENTS = ["claude", "chatgpt", "opencode", "cursor", "copilot", "gemini", "generic"]
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
_TEXT_SUFFIXES = {
    ".md", ".markdown", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".bash", ".zsh", ".fish",
    ".ps1", ".rb", ".go", ".rs", ".java", ".c", ".h", ".cpp", ".hpp", ".sql",
    ".html", ".css", ".csv", ".tsv", ".xml", ".env", ".gitignore", ".lua",
}
_RESERVED_NAMES = {"", ".", ".."}
_MANAGED_KEYS = {
    "name", "description", "agents", "agent", "tags", "version", "author",
    "license", "updated", "allowed-tools", "allowed_tools",
}


class StoreError(Exception):
    status = 400


class NotFound(StoreError):
    status = 404


class Conflict(StoreError):
    status = 409


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return slug[:80]


def _check_slug(slug: str) -> str:
    slug = (slug or "").strip()
    if not _SLUG_RE.match(slug):
        raise StoreError(
            "El identificador debe usar minusculas, numeros y guiones (ej. code-review)."
        )
    return slug


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _as_list(value) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace(";", ",").split(",") if part.strip()]


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            chunk = handle.read(4096)
    except OSError:
        return False
    if b"\0" in chunk:
        return False
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


class SkillStore:
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ paths
    def skill_dir(self, slug: str) -> Path:
        path = self.root / _check_slug(slug)
        if not path.is_dir():
            raise NotFound(f"La skill '{slug}' no existe.")
        return path

    def _split_rel(self, rel: str | None) -> list[str]:
        parts = [part for part in (rel or "").strip().replace("\\", "/").split("/") if part]
        if any(part in ("..", ".") for part in parts):
            raise StoreError("Ruta no valida.")
        return parts

    def resolve(self, slug: str, rel: str | None, *, must_exist: bool = True) -> Path:
        """Resolve ``rel`` inside a skill, refusing anything that escapes it.

        Absolute paths are treated as relative to the skill, ``..`` is rejected
        outright, and a symlink anywhere along the way is refused so a link
        planted inside a skill cannot be used to read or write outside it.
        """
        base = self.skill_dir(slug).resolve()
        parts = self._split_rel(rel)

        probe = base
        for part in parts:
            probe = probe / part
            if probe.is_symlink():
                raise StoreError("La ruta atraviesa un enlace simbolico.")
        if probe != base and base not in probe.parents:
            raise StoreError("La ruta sale de la carpeta de la skill.")
        if must_exist and not probe.exists():
            raise NotFound(f"No existe '{rel or '/'}' en la skill.")
        return probe

    # ----------------------------------------------------------------- reading
    def _read_skill_file(self, path: Path) -> tuple[dict, str]:
        skill_md = path / SKILL_FILE
        if not skill_md.is_file():
            return {}, ""
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        return frontmatter.parse(text)

    def summary(self, slug: str) -> dict:
        path = self.skill_dir(slug)
        meta, body = self._read_skill_file(path)
        files = 0
        folders: list[str] = []
        bytes_total = 0
        for entry in path.rglob("*"):
            if entry.is_dir():
                if entry.parent == path:
                    folders.append(entry.name)
            else:
                files += 1
                try:
                    bytes_total += entry.stat().st_size
                except OSError:
                    pass
        return {
            "slug": slug,
            "name": str(meta.get("name") or slug),
            "description": str(meta.get("description") or ""),
            "agents": _as_list(meta.get("agents") or meta.get("agent")),
            "tags": _as_list(meta.get("tags")),
            "version": str(meta.get("version") or ""),
            "author": str(meta.get("author") or ""),
            "license": str(meta.get("license") or ""),
            "updated": str(meta.get("updated") or ""),
            "allowed_tools": _as_list(meta.get("allowed-tools") or meta.get("allowed_tools")),
            "has_body": bool(body.strip()),
            "file_count": files,
            "folders": sorted(folders),
            "size_bytes": bytes_total,
            "mtime": path.stat().st_mtime,
        }

    def list_skills(self) -> list[dict]:
        skills = []
        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if not _SLUG_RE.match(entry.name):
                continue
            try:
                skills.append(self.summary(entry.name))
            except StoreError:
                continue
        skills.sort(key=lambda item: item["name"].lower())
        return skills

    def get_skill(self, slug: str) -> dict:
        path = self.skill_dir(slug)
        meta, body = self._read_skill_file(path)
        data = self.summary(slug)
        extra = {key: value for key, value in meta.items() if key not in _MANAGED_KEYS}
        data.update({"body": body, "extra": extra, "tree": self.tree(slug)})
        return data

    def tree(self, slug: str) -> list[dict]:
        base = self.skill_dir(slug)

        def walk(directory: Path) -> list[dict]:
            nodes = []
            try:
                entries = sorted(
                    directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower())
                )
            except OSError:
                return nodes
            for entry in entries:
                rel = entry.relative_to(base).as_posix()
                if entry.is_symlink():
                    continue
                if entry.is_dir():
                    nodes.append(
                        {"name": entry.name, "path": rel, "type": "dir", "children": walk(entry)}
                    )
                else:
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = 0
                    nodes.append(
                        {
                            "name": entry.name,
                            "path": rel,
                            "type": "file",
                            "size": size,
                            "editable": is_probably_text(entry),
                        }
                    )
            return nodes

        return walk(base)

    # ----------------------------------------------------------------- writing
    def _build_meta(self, data: dict, previous: dict | None = None) -> dict:
        meta: dict = {}
        meta["name"] = str(data.get("name") or "").strip() or str(data.get("slug") or "")
        meta["description"] = str(data.get("description") or "").strip()
        agents = _as_list(data.get("agents"))
        if agents:
            meta["agents"] = agents
        tags = _as_list(data.get("tags"))
        if tags:
            meta["tags"] = tags
        for key in ("version", "author", "license"):
            value = str(data.get(key) or "").strip()
            if value:
                meta[key] = value
        allowed = _as_list(data.get("allowed_tools"))
        if allowed:
            meta["allowed-tools"] = allowed
        extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}
        # Carry over unknown frontmatter keys, but never resurrect a managed
        # field the user just emptied (agents, tags, version…).
        for key, value in (previous or {}).items():
            if key in _MANAGED_KEYS or key in meta or key in extra:
                continue
            meta[key] = value
        for key, value in extra.items():
            if key.strip():
                meta[key.strip()] = value
        meta["updated"] = _now()
        return meta

    def create_skill(self, data: dict) -> dict:
        slug = _check_slug(data.get("slug") or slugify(data.get("name", "")))
        if not str(data.get("description") or "").strip():
            raise StoreError("La descripcion es obligatoria: es lo que hace que el agente active la skill.")
        path = self.root / slug
        if path.exists():
            raise Conflict(f"Ya existe una skill con el identificador '{slug}'.")
        path.mkdir(parents=True)
        meta = self._build_meta({**data, "slug": slug})
        body = data.get("body") or _starter_body(meta["name"])
        (path / SKILL_FILE).write_text(frontmatter.dump(meta, body), encoding="utf-8")
        for folder in _as_list(data.get("folders")):
            self.create_folder(slug, folder)
        return self.get_skill(slug)

    def update_skill(self, slug: str, data: dict) -> dict:
        path = self.skill_dir(slug)
        previous_meta, previous_body = self._read_skill_file(path)
        if "description" in data and not str(data.get("description") or "").strip():
            raise StoreError("La descripcion es obligatoria.")
        merged = {
            "name": data.get("name", previous_meta.get("name", slug)),
            "description": data.get("description", previous_meta.get("description", "")),
            "agents": data.get("agents", _as_list(previous_meta.get("agents") or previous_meta.get("agent"))),
            "tags": data.get("tags", _as_list(previous_meta.get("tags"))),
            "version": data.get("version", previous_meta.get("version", "")),
            "author": data.get("author", previous_meta.get("author", "")),
            "license": data.get("license", previous_meta.get("license", "")),
            "allowed_tools": data.get(
                "allowed_tools",
                _as_list(previous_meta.get("allowed-tools") or previous_meta.get("allowed_tools")),
            ),
            "extra": data.get("extra", {}),
        }
        meta = self._build_meta(merged, previous_meta)
        body = data.get("body", previous_body)
        (path / SKILL_FILE).write_text(frontmatter.dump(meta, body), encoding="utf-8")

        new_slug = data.get("slug")
        if new_slug and _check_slug(new_slug) != slug:
            slug = self.rename_skill(slug, new_slug)
        return self.get_skill(slug)

    def rename_skill(self, slug: str, new_slug: str) -> str:
        path = self.skill_dir(slug)
        new_slug = _check_slug(new_slug)
        target = self.root / new_slug
        if target.exists():
            raise Conflict(f"Ya existe una skill con el identificador '{new_slug}'.")
        path.rename(target)
        return new_slug

    def delete_skill(self, slug: str) -> None:
        shutil.rmtree(self.skill_dir(slug))

    def duplicate_skill(self, slug: str, new_slug: str | None = None) -> dict:
        source = self.skill_dir(slug)
        new_slug = _check_slug(new_slug or _unique_slug(self.root, f"{slug}-copia"))
        target = self.root / new_slug
        if target.exists():
            raise Conflict(f"Ya existe una skill con el identificador '{new_slug}'.")
        shutil.copytree(source, target, symlinks=False)
        meta, body = self._read_skill_file(target)
        meta["name"] = f"{meta.get('name', slug)} (copia)"
        meta["updated"] = _now()
        (target / SKILL_FILE).write_text(frontmatter.dump(meta, body), encoding="utf-8")
        return self.get_skill(new_slug)

    # -------------------------------------------------------------- file tools
    def read_file(self, slug: str, rel: str) -> dict:
        path = self.resolve(slug, rel)
        if not path.is_file():
            raise StoreError("La ruta indicada no es un archivo.")
        size = path.stat().st_size
        editable = is_probably_text(path) and size <= MAX_TEXT_BYTES
        payload = {"path": rel, "size": size, "editable": editable, "content": ""}
        if editable:
            payload["content"] = path.read_text(encoding="utf-8", errors="replace")
        return payload

    def write_file(self, slug: str, rel: str, content: str) -> dict:
        path = self.resolve(slug, rel, must_exist=False)
        _check_name(path.name)
        if path.is_dir():
            raise StoreError("Esa ruta es una carpeta.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content or "", encoding="utf-8")
        if path.suffix.lower() in (".sh", ".bash", ".zsh") or content.startswith("#!"):
            path.chmod(path.stat().st_mode | 0o111)
        return {"path": rel, "size": path.stat().st_size}

    def write_binary(self, slug: str, rel: str, blob: bytes) -> dict:
        if len(blob) > MAX_FILE_BYTES:
            raise StoreError("El archivo supera el limite de 64 MB.")
        path = self.resolve(slug, rel, must_exist=False)
        _check_name(path.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return {"path": rel, "size": len(blob)}

    def create_folder(self, slug: str, rel: str) -> dict:
        path = self.resolve(slug, rel, must_exist=False)
        if path == self.skill_dir(slug):
            raise StoreError("Indica un nombre de carpeta.")
        for part in self._split_rel(rel):
            _check_name(part)
        path.mkdir(parents=True, exist_ok=True)
        return {"path": rel}

    def delete_path(self, slug: str, rel: str) -> None:
        parts = self._split_rel(rel)
        if not parts:
            raise StoreError("Indica que quieres borrar.")
        base = self.skill_dir(slug).resolve()
        probe = base
        for part in parts[:-1]:
            probe = probe / part
            if probe.is_symlink():
                raise StoreError("La ruta atraviesa un enlace simbolico.")
        path = probe / parts[-1]
        if path.is_symlink():  # remove the link itself, never its target
            path.unlink()
            return
        if not path.exists():
            raise NotFound(f"No existe '{rel}' en la skill.")
        if path.name == SKILL_FILE and path.parent == base:
            raise StoreError("SKILL.md no se puede borrar: es el corazon de la skill.")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    def move_path(self, slug: str, rel: str, new_rel: str) -> dict:
        source = self.resolve(slug, rel)
        target = self.resolve(slug, new_rel, must_exist=False)
        if source == self.skill_dir(slug):
            raise StoreError("No puedes mover la raiz de la skill.")
        if target.exists():
            raise Conflict(f"Ya existe '{new_rel}'.")
        for part in self._split_rel(new_rel):
            _check_name(part)
        if source.is_dir() and str(target).startswith(str(source) + os.sep):
            raise StoreError("No puedes mover una carpeta dentro de si misma.")
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        return {"path": new_rel}

    # ------------------------------------------------------------ import/export
    def export_zip(self, slug: str) -> bytes:
        path = self.skill_dir(slug)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry in sorted(path.rglob("*")):
                if entry.is_symlink() or entry.is_dir():
                    continue
                archive.write(entry, f"{slug}/{entry.relative_to(path).as_posix()}")
        return buffer.getvalue()

    def export_all_zip(self) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for skill in self.list_skills():
                base = self.root / skill["slug"]
                for entry in sorted(base.rglob("*")):
                    if entry.is_symlink() or entry.is_dir():
                        continue
                    archive.write(entry, f"{skill['slug']}/{entry.relative_to(base).as_posix()}")
        return buffer.getvalue()

    def import_zip(self, blob: bytes) -> list[str]:
        if len(blob) > MAX_FILE_BYTES:
            raise StoreError("El zip supera el limite de 64 MB.")
        try:
            archive = zipfile.ZipFile(io.BytesIO(blob))
        except zipfile.BadZipFile as exc:
            raise StoreError("El archivo no es un zip valido.") from exc

        names = [n for n in archive.namelist() if not n.endswith("/")]
        if not names:
            raise StoreError("El zip esta vacio.")
        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        top_level = [name for name in names if "/" not in name]
        imported: list[str] = []

        if SKILL_FILE in top_level or "skill.md" in [n.lower() for n in top_level]:
            imported.append(self._extract_one(archive, names, prefix="", fallback="skill-importada"))
            return imported

        for root in sorted(roots):
            members = [name for name in names if name.startswith(root + "/")]
            has_skill = any(
                name[len(root) + 1 :].lower() == SKILL_FILE.lower() for name in members
            )
            if not has_skill:
                continue
            imported.append(self._extract_one(archive, members, prefix=root + "/", fallback=root))
        if not imported:
            raise StoreError("No se encontro ningun SKILL.md dentro del zip.")
        return imported

    def _extract_one(self, archive: zipfile.ZipFile, members, prefix: str, fallback: str) -> str:
        slug = _unique_slug(self.root, slugify(fallback) or "skill-importada")
        base = self.root / slug
        base.mkdir(parents=True)
        for name in members:
            rel = name[len(prefix) :]
            if not rel or rel.endswith("/"):
                continue
            parts = Path(rel).parts
            if any(part in ("..", "") for part in parts) or Path(rel).is_absolute():
                continue
            destination = base.joinpath(*parts)
            resolved = destination.resolve()
            if base.resolve() not in resolved.parents:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, destination.open("wb") as out:
                shutil.copyfileobj(source, out, length=1024 * 128)
        skill_md = base / SKILL_FILE
        if not skill_md.is_file():
            for candidate in base.iterdir():
                if candidate.name.lower() == SKILL_FILE.lower():
                    candidate.rename(skill_md)
                    break
        meta, body = self._read_skill_file(base)
        meta.setdefault("name", slug)
        meta.setdefault("description", "")
        meta["updated"] = _now()
        skill_md.write_text(frontmatter.dump(meta, body), encoding="utf-8")
        return slug

    def import_folder(self, source_path: str) -> list[str]:
        source = Path(source_path).expanduser()
        if not source.is_dir():
            raise NotFound(f"No existe la carpeta '{source_path}'.")
        if source.resolve() == self.root or self.root in source.resolve().parents:
            raise StoreError("Esa carpeta ya forma parte de la biblioteca.")

        candidates = []
        if (source / SKILL_FILE).is_file():
            candidates.append(source)
        else:
            candidates.extend(
                child for child in sorted(source.iterdir())
                if child.is_dir() and (child / SKILL_FILE).is_file()
            )
        if not candidates:
            raise StoreError("No se encontro ningun SKILL.md en esa carpeta.")

        imported = []
        for candidate in candidates:
            slug = _unique_slug(self.root, slugify(candidate.name) or "skill-importada")
            shutil.copytree(candidate, self.root / slug, symlinks=False)
            imported.append(slug)
        return imported

    # ---------------------------------------------------------------- searching
    def search(self, query: str) -> list[dict]:
        query = (query or "").strip().lower()
        if not query:
            return []
        hits = []
        for skill in self.list_skills():
            base = self.root / skill["slug"]
            matches = []
            for entry in sorted(base.rglob("*")):
                if not entry.is_file() or entry.is_symlink():
                    continue
                if not is_probably_text(entry) or entry.stat().st_size > MAX_TEXT_BYTES:
                    continue
                try:
                    text = entry.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for number, line in enumerate(text.splitlines(), start=1):
                    if query in line.lower():
                        matches.append(
                            {
                                "path": entry.relative_to(base).as_posix(),
                                "line": number,
                                "text": line.strip()[:200],
                            }
                        )
                        if len(matches) >= 20:
                            break
                if len(matches) >= 20:
                    break
            if matches:
                hits.append({"slug": skill["slug"], "name": skill["name"], "matches": matches})
        return hits

    def stats(self) -> dict:
        skills = self.list_skills()
        agents: dict[str, int] = {}
        tags: dict[str, int] = {}
        for skill in skills:
            for agent in skill["agents"] or ["sin-agente"]:
                agents[agent] = agents.get(agent, 0) + 1
            for tag in skill["tags"]:
                tags[tag] = tags.get(tag, 0) + 1
        return {
            "root": str(self.root),
            "count": len(skills),
            "files": sum(skill["file_count"] for skill in skills),
            "size_bytes": sum(skill["size_bytes"] for skill in skills),
            "agents": dict(sorted(agents.items(), key=lambda kv: (-kv[1], kv[0]))),
            "tags": dict(sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))),
            "known_agents": KNOWN_AGENTS,
        }


def _check_name(name: str) -> None:
    if name in _RESERVED_NAMES or "/" in name or "\\" in name:
        raise StoreError(f"Nombre no valido: '{name}'.")
    if name.startswith("-"):
        raise StoreError("Los nombres no pueden empezar por '-'.")


def _unique_slug(root: Path, slug: str) -> str:
    slug = slug or "skill"
    candidate = slug
    index = 2
    while (root / candidate).exists():
        candidate = f"{slug}-{index}"
        index += 1
    return candidate


def _starter_body(name: str) -> str:
    return f"""# {name}

## Cuando usarla

Describe aqui las situaciones en las que el agente debe activar esta skill.

## Como funciona

1. Primer paso.
2. Segundo paso.

## Recursos

- `scripts/` — utilidades ejecutables.
- `references/` — documentacion de apoyo que el agente puede leer bajo demanda.
"""
