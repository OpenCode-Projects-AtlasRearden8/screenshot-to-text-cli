"""Dedupe by image content hash (SHA-256 of the file bytes).

Two screenshots can look identical after re-cropping or re-saving;
progressive JPEG re-encodes change bytes, but for the common case --
the exact same file appearing more than once, or a previously
processed folder being re-run -- a byte hash is simple and reliable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DedupeDecision:
    is_duplicate: bool
    first_file: str = ""
    first_row: dict | None = None


def decide_for_hash(
    sha: str, current_pass: dict[str, dict], prior_hashes: dict[str, dict]
) -> DedupeDecision:
    """Return whether a hash was already seen, in this run or before.

    `current_pass` maps sha256 -> manifest row for images handled earlier
    in the same run; `prior_hashes` covers every previous manifest run.
    """
    if sha in current_pass:
        return DedupeDecision(
            is_duplicate=True, first_file=current_pass[sha]["image_file"], first_row=current_pass[sha]
        )
    prior = prior_hashes.get(sha)
    if prior is not None:
        return DedupeDecision(is_duplicate=True, first_file=prior.get("image_file", ""), first_row=prior)
    return DedupeDecision(is_duplicate=False)


def text_for_duplicate(first_row: dict | None, out_dir) -> str | None:
    """Best output-file text for a duplicate: reuse the original's text.

    Returns None when we cannot find the original's text file, in which
    case the duplicate gets no output file of its own.
    """
    if first_row is None:
        return None
    output_file = (first_row.get("output_file") or "").strip()
    if not output_file:
        return None
    candidate = out_dir / output_file
    try:
        return candidate.read_text(encoding="utf-8")
    except OSError:
        return None
