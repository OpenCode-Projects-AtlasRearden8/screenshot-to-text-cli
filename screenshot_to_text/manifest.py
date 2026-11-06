"""Manifest CSV: one row per image processed, ever.

The manifest is what makes runs resumable and hash-based dedupe stable
across invocations: a hash seen in any previous run is a duplicate.
"""

from __future__ import annotations

import csv
from pathlib import Path

MANIFEST_FIELDS = [
    "image_file",
    "sha256",
    "bytes",
    "dimensions",
    "processed_utc",
    "engine",
    "status",
    "duplicate_of",
    "output_file",
    "text_chars",
    "llm_tidy",
    "error",
]


def read_manifest(csv_path: Path) -> list[dict]:
    """Read the manifest, returning rows as dicts. Missing file -> []."""
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        return []
    with open(csv_path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        rows = []
        for row in reader:
            rows.append({field: row.get(field, "") for field in MANIFEST_FIELDS})
    return rows


def write_manifest(csv_path: Path, rows: list[dict]) -> None:
    """(Over)write the manifest with the given rows."""
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MANIFEST_FIELDS})


def append_manifest_rows(csv_path: Path, new_rows: list[dict]) -> None:
    """Append rows, creating the manifest (with header) if needed."""
    csv_path = Path(csv_path)
    exists = csv_path.is_file()
    with open(csv_path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        if not exists:
            writer.writeheader()
        for row in new_rows:
            writer.writerow({field: row.get(field, "") for field in MANIFEST_FIELDS})


def known_hashes(rows: list[dict]) -> dict[str, dict]:
    """Map sha256 -> first (oldest) successfully processed row.

    A hash counts as known if any prior row processed it, even with an
    error, so we never repeat work on unreadable files either.
    """
    known: dict[str, dict] = {}
    for row in rows:
        sha = (row.get("sha256") or "").strip()
        if not sha:
            continue
        if sha not in known:
            known[sha] = row
    return known


def summary(rows: list[dict]) -> dict[str, int]:
    """Tiny headline counts for terminal output."""
    counts = {"seen": 0, "ok": 0, "duplicate": 0, "error": 0, "empty": 0, "other": 0}
    for row in rows:
        status = row.get("status", "") or "other"
        if status not in counts:
            status = "other"
        counts[status] += 1
        counts["seen"] += 1
    return counts
