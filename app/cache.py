"""Content-addressed audio cache."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import config

NAME_RE = re.compile(r"^[a-f0-9]{20}\.(mp3|wav)$")


def key_for(*parts: object) -> str:
    raw = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:20]


def path_for(key: str, ext: str) -> Path:
    return config.CACHE_DIR / f"{key}.{ext}"


def read(key: str, ext: str) -> bytes | None:
    path = path_for(key, ext)
    return path.read_bytes() if path.exists() else None


def write(key: str, ext: str, data: bytes) -> Path:
    path = path_for(key, ext)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path


def safe_name(name: str) -> bool:
    return bool(NAME_RE.match(name))
