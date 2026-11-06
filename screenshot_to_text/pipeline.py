"""The processing pipeline: scan -> hash -> dedupe -> OCR -> clean -> write -> manifest."""

from __future__ import annotations

from pathlib import Path

from . import dedupe as dedupe_mod
from . import manifest as manifest_mod
from .llm import tidy_text
from .ocr import backend_missing_message, OcrEngine
from .utils import IMAGE_EXTENSIONS, natural_key, sha256_file, utc_now_iso


def scan_images(input_dir: Path, recursive: bool = False) -> list[Path]:
    """List candidate images, sorted naturally (shot2 < shot10)."""
    patterns = input_dir.rglob if recursive else input_dir.glob
    files = [p for p in patterns("*.*") if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file()]
    return sorted(files, key=lambda path: natural_key(path.name))


def blank_row(path: Path, sha: str) -> dict:
    stat = path.stat()
    return {
        "image_file": str(path),
        "sha256": sha,
        "bytes": stat.st_size,
        "dimensions": "",
        "processed_utc": utc_now_iso(),
        "engine": "",
        "status": "",
        "duplicate_of": "",
        "output_file": "",
        "text_chars": 0,
        "llm_tidy": "no",
        "error": "",
    }


def process_folder(
    input_dir: Path,
    out_dir: Path,
    manifest_path: Path,
    engine: OcrEngine | None = None,
    recursive: bool = False,
    dedupe: bool = True,
    force: bool = False,
    tidy: bool = False,
    api_base: str = "",
    model: str = "",
    api_key: str | None = None,
    on_event=None,
) -> dict:
    """OCR every image in `input_dir`, writing text files and manifest rows.

    Returns a summary dict. The input folder is only ever read.
    """
    input_dir = Path(input_dir)
    out_dir = Path(out_dir)
    manifest_path = Path(manifest_path)
    if not input_dir.is_dir():
        raise NotADirectoryError(f"input folder not found: {input_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)

    prior_rows = manifest_mod.read_manifest(manifest_path)
    prior_hashes = {} if force else manifest_mod.known_hashes(prior_rows)
    current_pass: dict[str, dict] = {}

    images = scan_images(input_dir, recursive=recursive)
    if engine is None:
        engine = OcrEngine()

    rows: list[dict] = []
    for image in images:
        row = blank_row(image, "")
        try:
            sha = sha256_file(image)
        except OSError as exc:
            row["status"] = "error"
            row["error"] = f"read failed: {exc}"
            rows.append(row)
            _emit(on_event, image.name, row)
            continue

        row["sha256"] = sha
        row["dimensions"] = _dimensions(image)

        decision = dedupe_mod.decide_for_hash(sha, current_pass, prior_hashes) if dedupe else None
        if decision is None and sha in prior_hashes:
            # Not deduping duplicates against each other, but never redo
            # past work unless --force; a re-run stays cheap by default.
            decision = dedupe_mod.DedupeDecision(
                is_duplicate=True,
                first_file=prior_hashes[sha].get("image_file", ""),
                first_row=prior_hashes[sha],
            )
        if decision is not None and decision.is_duplicate:
            row["status"] = "duplicate"
            row["duplicate_of"] = decision.first_file
            text = dedupe_mod.text_for_duplicate(decision.first_row, out_dir)
            if text is not None:
                target = out_dir / _unique_output_path(out_dir, image.stem + ".txt")
                target.write_text(text, encoding="utf-8")
                row["output_file"] = target.name
                row["text_chars"] = len(text)
                row["llm_tidy"] = "copied"
            rows.append(row)
            current_pass[sha] = row
            _emit(on_event, image.name, row)
            continue

        # Fresh OCR.
        try:
            text = engine.extract_text(image)
            engine_name = engine.ensure_loaded()
            row["engine"] = engine_name
        except Exception as exc:
            row["status"] = "error"
            row["error"] = str(exc)
            rows.append(row)
            _emit(on_event, image.name, row)
            continue

        if tidy:
            text = tidy_text(
                text,
                api_base=api_base,
                model=model,
                api_key=api_key,
            )
            row["llm_tidy"] = "yes"

        row["status"] = "ok" if text.strip() else "empty"
        target = out_dir / _unique_output_path(out_dir, image.stem + ".txt")
        target.write_text(text, encoding="utf-8")
        row["output_file"] = target.name
        row["text_chars"] = len(text)
        rows.append(row)
        current_pass[sha] = row
        _emit(on_event, image.name, row)

    manifest_mod.append_manifest_rows(manifest_path, rows)

    all_rows = prior_rows + rows
    return {
        "images_found": len(images),
        "rows": rows,
        "all_rows": all_rows,
        "summary": manifest_mod.summary(all_rows),
    }


def _unique_output_path(out_dir: Path, name: str) -> str:
    """Prevent clobbering: shot.txt, shot.2.txt, shot.3.txt ..."""
    if not (out_dir / name).exists():
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    counter = 2
    while (out_dir / f"{stem}.{counter}{suffix}").exists():
        counter += 1
    return f"{stem}.{counter}{suffix}"


def _dimensions(image: Path) -> str:
    try:
        from PIL import Image

        with Image.open(image) as img:
            return f"{img.width}x{img.height}"
    except Exception:
        return ""


def _emit(on_event, name: str, row: dict) -> None:
    if on_event:
        on_event(name, row)
