"""Minimal YAML-frontmatter reader/writer.

Only the subset used by agent skill files is supported: scalars, inline lists
(``[a, b]``) and block lists (``- item``). That keeps the app dependency-free
while staying compatible with the ``SKILL.md`` files Claude/opencode ship.
"""

from __future__ import annotations

import re

DELIM = "---"
_UNQUOTED_SAFE = re.compile(r"^[A-Za-z0-9_./@+][A-Za-z0-9_./@+ -]*$")


def _parse_scalar(raw: str):
    text = raw.strip()
    if not text:
        return ""
    if text[0] in "\"'" and len(text) >= 2 and text[-1] == text[0]:
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in _split_inline(inner)]
    low = text.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    return text


def _split_inline(inner: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p for p in (p.strip() for p in parts) if p]


def parse(text: str) -> tuple[dict, str]:
    """Split ``text`` into (metadata, body)."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.lstrip("\ufeff").startswith(DELIM):
        return {}, normalized
    normalized = normalized.lstrip("\ufeff")
    lines = normalized.split("\n")
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == DELIM:
            end = index
            break
    if end is None:
        return {}, normalized

    meta: dict = {}
    key: str | None = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") or stripped == "-":
            if key is None:
                continue
            item = _parse_scalar(stripped[1:].strip())
            current = meta.get(key)
            if isinstance(current, list):
                current.append(item)
            elif current in ("", None):
                meta[key] = [item]
            else:
                meta[key] = [current, item]
            continue
        if ":" not in line:
            continue
        raw_key, raw_value = line.split(":", 1)
        key = raw_key.strip()
        if not key:
            continue
        value = raw_value.strip()
        meta[key] = [] if value == "" else _parse_scalar(value)

    body = "\n".join(lines[end + 1 :])
    return meta, body.lstrip("\n")


def _dump_scalar(value) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return ""
    text = str(value)
    if text == "":
        return '""'
    if _UNQUOTED_SAFE.match(text) and not text.endswith(" "):
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{escaped}"'


def dump(meta: dict, body: str) -> str:
    """Rebuild a ``SKILL.md`` document from metadata and body."""
    lines = [DELIM]
    for key, value in meta.items():
        if isinstance(value, (list, tuple)):
            items = [_dump_scalar(item) for item in value]
            lines.append(f"{key}: [{', '.join(items)}]" if items else f"{key}: []")
        else:
            lines.append(f"{key}: {_dump_scalar(value)}")
    lines.append(DELIM)
    text = "\n".join(lines) + "\n\n" + (body or "").strip()
    return text.rstrip() + "\n"
