# screenshot-to-text-cli

**Local-first text extraction for a folder of screenshots.**

Point it at a folder of screenshots and get one clean, copyable `.txt` file per
image, a manifest CSV that tracks everything it has ever processed, and
hash-based dedupe so repeated screenshots never get OCR'd twice. An optional
second pass sends the junk-stripped text to any OpenAI-compatible endpoint --
**Ollama included, no API key needed** -- for a friendlier tidy-up.

Your original images are only ever *read*, never modified or moved. Everything
runs locally by default: no cloud OCR, no accounts, no secrets.

Brought to you by [Asdale Dynamics, LLC](https://dylanasdale.github.io) --
beginner-friendly AI tools, explained like a friend would.

## Why

Screenshots pile up: receipts, confirmation numbers, error messages, notes.
Copy-paste usually fails on them because the text lives in pixels. This tool
turns a whole folder of screenshots into plain text files you can copy, search,
and archive.

## Install

Python 3.10+ recommended.

```bash
# Recommended: the OCR model ships inside the pip package. Fully local.
pip install screenshot-to-text[rapidocr]

# Or, if you already have tesseract installed on your system:
pip install screenshot-to-text[tesseract]

# Development (tests):
pip install -e ".[rapidocr,dev]"
```

Check that OCR is ready:

```bash
screenshot-to-text --check
```

If you have [Ollama](https://ollama.com) running, you already have an
OpenAI-compatible endpoint at `http://localhost:11434/v1` -- no key, no setup.

## Usage

```bash
# Basic: OCR every image in a folder
screenshot-to-text ~/Screenshots

# Choose an output folder, include subfolders
screenshot-to-text ~/Screenshots -o out --recursive

# Send text through Ollama for a tidy-up pass (no API key)
screenshot-to-text shots --cleanup --model llama3.2

# Re-OCR everything from scratch, ignoring the manifest
screenshot-to-text shots --force

# Show what backends are available
screenshot-to-text --check
```

After a run:

```
text-out/          one .txt per screenshot
manifest.csv       a permanent record of every image ever processed
```

The manifest records, per image: path, SHA-256 hash, file size, pixel
dimensions, processing time, OCR engine, status (`ok` / `duplicate` / `empty` /
`error`), duplicate original when applicable, output file name, text length,
and whether the LLM tidy-up ran.

Run it again on the same folder and nothing is re-OCR'd: hashes already in the
manifest are skipped (or duplicated with the original's text), so re-runs are
fast. Use `--force` to start over.

### Options

| Flag | What it does |
| --- | --- |
| `-o, --output PATH` | Output folder for `.txt` files (default `./text-out`) |
| `--manifest PATH` | Manifest CSV path (default `./manifest.csv`) |
| `-r, --recursive` | Include subfolders |
| `--no-dedupe` | OCR duplicates too |
| `--force` | Ignore the manifest and re-OCR everything |
| `--backend {rapidocr,tesseract}` | Pick a specific OCR backend |
| `--cleanup` | Post-process text via an OpenAI-compatible endpoint |
| `--api-base URL` | Endpoint base URL (default `http://localhost:11434/v1`) |
| `--model NAME` | Model to request (default `llama3.2` for Ollama) |
| `--api-key KEY` | Optional; Ollama needs none. Prefer the `OPENAI_API_KEY` env var -- this tool never writes keys to disk |

### Alternatives

- **voice-notes-transcriber-cli** -- same idea, but for audio/voice memos.
- **photo-dedupe-lite-cli** -- just the dedupe part, without OCR.

## How dedupe works

Each image is hashed with SHA-256 (file bytes). The first copy gets OCR'd;
every other image with the same hash -- in this run or any past run recorded
in the manifest -- is marked `duplicate` in the CSV, lists which original it
matches, and (when the original produced text) gets a copy of that text file
so every screenshot still ends up with text next to it. Note: byte hashes
won't catch re-cropped or re-compressed lookalikes; use `--no-dedupe`
if you would rather pay the OCR cost than ever skip anything.

## Privacy

- OCR runs entirely on your machine.
- The only network call happens with `--cleanup`, and it goes wherever *you*
  point it (Ollama on your own machine by default).
- No API keys are stored or logged. No telemetry.

## Development

```bash
pip install -e ".[rapidocr,dev]"
pytest
screenshot-to-text --check
```

Backend auto-detection: `rapidocr` (preferred, pip-only, models bundled) then
`pytesseract` (needs the system tesseract binary). Force one with `--backend`.

## License

MIT. See `LICENSE`. Copyright (c) 2026 Asdale Dynamics, LLC.
