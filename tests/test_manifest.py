"""Tests for the manifest CSV logic."""

from pathlib import Path

from screenshot_to_text import manifest


def _row(**overrides) -> dict:
    base = {
        "image_file": "shots/a.png",
        "sha256": "abc123",
        "bytes": "10",
        "dimensions": "100x100",
        "processed_utc": "2026-01-01T00:00:00Z",
        "engine": "rapidocr",
        "status": "ok",
        "duplicate_of": "",
        "output_file": "a.txt",
        "text_chars": "15",
        "llm_tidy": "no",
        "error": "",
    }
    base.update(overrides)
    return base


def test_read_missing_manifest(tmp_path: Path):
    assert manifest.read_manifest(tmp_path / "manifest.csv") == []


def test_write_and_read_roundtrip(tmp_path: Path):
    path = tmp_path / "manifest.csv"
    rows = [
        _row(),
        _row(image_file="shots/b.png", sha256="def456", status="duplicate", duplicate_of="shots/a.png"),
    ]
    manifest.write_manifest(path, rows)

    loaded = manifest.read_manifest(path)
    assert len(loaded) == 2
    assert loaded[0]["sha256"] == "abc123"
    assert loaded[0]["status"] == "ok"
    assert loaded[1]["status"] == "duplicate"
    assert loaded[1]["duplicate_of"] == "shots/a.png"
    # Every column survives the roundtrip, even blanks.
    assert set(loaded[0].keys()) == set(manifest.MANIFEST_FIELDS)


def test_append_creates_header_then_appends(tmp_path: Path):
    path = tmp_path / "manifest.csv"
    manifest.append_manifest_rows(path, [_row()])
    manifest.append_manifest_rows(path, [_row(image_file="shots/b.png", sha256="def456")])

    rows = manifest.read_manifest(path)
    assert len(rows) == 2
    assert rows[0]["sha256"] == "abc123"
    assert rows[1]["sha256"] == "def456"
    # Header written exactly once, on first append.
    assert len(path.read_text().strip().splitlines()) == 3


def test_known_hashes_maps_first_occurrence(tmp_path: Path):
    legacy = [
        _row(image_file="shots/a.png", sha256="x"),
        _row(image_file="shots/b.png", sha256="x"),
        _row(image_file="shots/c.png", sha256="y", status="error"),
        _row(image_file="", sha256=""),
    ]
    hashes = manifest.known_hashes(legacy)
    assert set(hashes) == {"x", "y"}
    assert hashes["x"]["image_file"] == "shots/a.png"
    # Even an errored prior attempt counts as "seen" so it is never redone.
    assert hashes["y"]["status"] == "error"


def test_summary_counts(tmp_path: Path):
    rows = [
        _row(status="ok"),
        _row(status="duplicate"),
        _row(status="duplicate"),
        _row(status="error"),
        _row(status="empty", text_chars="0"),
        _row(image_file="z.png", sha256="zz"),
    ]
    counts = manifest.summary(rows)
    assert counts["seen"] == 6
    assert counts["ok"] == 2
    assert counts["duplicate"] == 2
    assert counts["error"] == 1
    assert counts["empty"] == 1
    assert counts["other"] == 0


def test_short_rows_are_padded(tmp_path: Path):
    path = tmp_path / "manifest.csv"
    path.write_text("image_file,sha256\nold.png,hash1\n", encoding="utf-8")
    rows = manifest.read_manifest(path)
    assert rows[0]["image_file"] == "old.png"
    assert rows[0].get("status", "") == ""
    assert set(rows[0].keys()) == set(manifest.MANIFEST_FIELDS)
