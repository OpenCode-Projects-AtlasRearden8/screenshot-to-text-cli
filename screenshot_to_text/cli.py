"""Command-line interface for screenshot-to-text."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .llm import DEFAULT_API_BASE, DEFAULT_MODEL
from .ocr import available_backends
from .pipeline import process_folder

EXAMPLE_EPILOG = """\
examples:
  screenshot-to-text ~/Screenshots
  screenshot-to-text ~/Screenshots -o out --recursive
  screenshot-to-text shots --resume --force
  screenshot-to-text shots --cleanup --api-base http://localhost:11434/v1 --model llama3.2
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="screenshot-to-text",
        description=(
            "Local-first OCR for a folder of screenshots: writes one clean, "
            "copyable .txt per image, keeps a manifest CSV, and dedupes by "
            "image hash. Your original images are never modified."
        ),
        epilog=EXAMPLE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", nargs="?", type=Path, default=None,
        help="folder containing screenshots")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("text-out"),
        help="folder for output .txt files (default: ./text-out)",
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("manifest.csv"),
        help="path for the manifest CSV (default: ./manifest.csv)",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true",
        help="also process subfolders",
    )
    parser.add_argument(
        "--no-dedupe", action="store_true",
        help="OCR duplicates too (hash-based dedupe stays on by default)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="ignore the manifest and re-run OCR from scratch",
    )
    parser.add_argument(
        "--backend", choices=["rapidocr", "tesseract"],
        help="force a specific OCR backend (default: first available)",
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help="after OCR, send the junk-stripped text to an OpenAI-compatible "
        "endpoint (works with Ollama, no API key required) for a tidy-up pass",
    )
    parser.add_argument(
        "--api-base", default=DEFAULT_API_BASE,
        help="OpenAI-compatible endpoint base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help="model name to request (default: %(default)s)",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="API key if your endpoint needs one; Ollama does not. "
        "Prefer the OPENAI_API_KEY environment variable.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="show detected OCR backends / run environment and exit",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _print_check() -> int:
    backends = available_backends()
    if backends:
        print("OCR backends available:", ", ".join(backends))
    else:
        print("OCR backends available: none")
        print(
            "Install the pip-only, fully local backend with:\n"
            "  pip install screenshot-to-text[rapidocr]"
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check:
        return _print_check()

    if args.input is None:
        parser.error("the following arguments are required: input")

    if not Path(args.input).is_dir():
        parser.error(f"input folder not found: {args.input}")

    backends = available_backends()
    if not backends and not args.api_key:
        print(
            "No OCR backend found. Install one first:\n"
            "  pip install screenshot-to-text[rapidocr]\n"
            "(or tesseract: install the binary via your OS, then\n"
            "  pip install screenshot-to-text[tesseract])",
            file=sys.stderr,
        )
        return 1

    from .ocr import OcrEngine

    engine = OcrEngine(backend=args.backend) if args.backend else OcrEngine()
    if args.backend and args.backend not in backends:
        print(f"Requested backend '{args.backend}' is not available.", file=sys.stderr)
        return 1

    def on_event(name: str, row: dict) -> None:
        status = row.get("status", "?")
        print(f"  [{status:>9}] {name}")

    try:
        result = process_folder(
            input_dir=args.input,
            out_dir=args.output,
            manifest_path=args.manifest,
            engine=engine,
            recursive=args.recursive,
            dedupe=not args.no_dedupe,
            force=args.force,
            tidy=args.cleanup,
            api_base=args.api_base,
            model=args.model,
            api_key=args.api_key,
            on_event=on_event,
        )
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print(
        f"Done: {result['images_found']} image(s) in this run -> "
        f"{summary.get('ok', 0)} ok, {summary.get('duplicate', 0)} duplicate, "
        f"{summary.get('empty', 0)} empty, {summary.get('error', 0)} error."
    )
    print(f"Manifest: {args.manifest}")
    print(f"Text files: {args.output}")
    return 0 if result["images_found"] >= 0 and summary.get("error", 0) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
