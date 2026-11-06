"""Small shared helpers."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".webp",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 hex digest of a file's bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def natural_key(text: str) -> list:
    """Sort key that treats digit runs numerically: shot2 before shot10."""
    parts = []
    for token in re.split(r"(\d+)", text):
        if token.isdigit():
            parts.append((1, int(token), ""))
        elif token:
            parts.append((0, 0, token.lower()))
    return parts
