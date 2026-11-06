"""Tests for hash-based dedupe logic."""

from pathlib import Path

import pytest

from screenshot_to_text import dedupe
from screenshot_to_text.utils import sha256_file


def _row(name, sha=""):
    return {"image_file": name, "sha256": sha, "status": "ok", "output_file": ""}


# --- sha256_file ----------------------------------------------------------

def test_sha256_stable_and_content_based(tmp_path: Path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    c = tmp_path / "c.png"
    a.write_bytes(b"identical-content")
    b.write_bytes(b"identical-content")
    c.write_bytes(b"identical-contenX")  # one byte differs

    hash_a = sha256_file(a)
    assert hash_a == sha256_file(b)
    assert hash_a != sha256_file(c)
    assert len(hash_a) == 64


def test_sha256_matches_expected_digest(tmp_path: Path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"hello")
    import hashlib

    assert sha256_file(f) == hashlib.sha256(b"hello").hexdigest()


# --- decide_for_hash ------------------------------------------------------

def test_first_occurrence_is_not_duplicate():
    d = dedupe.decide_for_hash("h1", current_pass={}, prior_hashes={})
    assert d.is_duplicate is False
    assert d.first_file == ""


def test_within_run_duplicate():
    current_pass = {"h1": _row("shots/a.png", "h1")}
    d = dedupe.decide_for_hash("h1", current_pass, prior_hashes={})
    assert d.is_duplicate is True
    assert d.first_file == "shots/a.png"


def test_prior_run_duplicate():
    prior = {"h1": _row("old/a.png", "h1")}
    d = dedupe.decide_for_hash("h1", current_pass={}, prior_hashes=prior)
    assert d.is_duplicate is True
    assert d.first_file == "old/a.png"


def test_within_run_wins_over_prior():
    current_pass = {"h1": _row("this-run/a.png", "h1")}
    prior = {"h1": _row("last-run/a.png", "h1")}
    d = dedupe.decide_for_hash("h1", current_pass, prior)
    assert d.is_duplicate and d.first_file == "this-run/a.png"


def test_recorded_error_count_as_seen():
    prior = {"h1": {"image_file": "bad.png", "status": "error", "output_file": ""}}
    d = dedupe.decide_for_hash("h1", current_pass={}, prior_hashes=prior)
    assert d.is_duplicate is True


# --- text_for_duplicate ---------------------------------------------------

def test_text_for_duplicate_copies_original_text(tmp_path: Path):
    original = _row("shots/a.png")
    original["output_file"] = "a.txt"
    (tmp_path / "a.txt").write_text("the original text", encoding="utf-8")
    assert dedupe.text_for_duplicate(original, tmp_path) == "the original text"


def test_text_for_duplicate_handles_missing_output(tmp_path: Path):
    original = _row("shots/a.png")
    original["output_file"] = "missing.txt"
    assert dedupe.text_for_duplicate(original, tmp_path) is None
    assert dedupe.text_for_duplicate(_row("shots/a.png"), tmp_path) is None
    assert dedupe.text_for_duplicate(None, tmp_path) is None
