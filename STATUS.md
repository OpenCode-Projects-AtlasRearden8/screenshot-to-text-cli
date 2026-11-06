# STATUS.md — screenshot-to-text-cli

Built 2026-11-06 by ASDALE DYNAMICS, LLC (as an open-source tool).

## What was built

A local-first Python CLI that turns a folder of screenshots into clean,
copyable text files:

- **OCR, fully local.** Auto-detects backends: `rapidocr` (pip-only,
  ONNX models bundled, preferred) or `pytesseract` (needs the system
  tesseract binary). Word boxes are grouped into visual lines and joined
  so spaces survive.
- **Clean text output.** One `.txt` per image: control characters stripped,
  hyphenated line wraps repaired, junk lines (stray symbols, UI noise)
  removed. Original images are only ever read, never modified.
- **Manifest CSV.** Every image ever processed gets a row: path, SHA-256,
  size, dimensions, timestamp, engine, status (`ok`/`duplicate`/`empty`/
  `error`), duplicate original, output file, text length, LLM flag, error.
- **Hash-based dedupe.** Same file bytes = same SHA-256. The first copy
  gets OCR'd; later identical hashes (this run or any past run via the
  manifest) are marked duplicates and get a copy of the original's text
  file. `--force` re-OCRs everything; `--no-dedupe` disables skipping.
- **Optional LLM tidy-up.** `--cleanup` sends the junk-stripped text to any
  OpenAI-compatible `/chat/completions` endpoint. Ollama works with no API
  key (`--api-base http://localhost:11434/v1`). Keys stay in `--api-key`
  or the `OPENAI_API_KEY` env var; nothing is written to disk.

## How to run it

```bash
pip install screenshot-to-text[rapidocr]     # recommended, fully local
screenshot-to-text --check                   # verify a backend is detected
screenshot-to-text ~/Screenshots -o out      # basic run
screenshot-to-text shots --cleanup           # tidy text via Ollama (no key)
screenshot-to-text shots --force             # re-OCR from scratch
```

Dev install: `pip install -e ".[rapidocr,dev]"`, then `pytest`.

## Verification results

- `pytest`: **33 passed, 0 failed** (manifest roundtrip/append/padding,
  dedupe decisions across/prior runs, hash stability, cleaner behavior,
  full pipeline with a fake engine, LLM tidy-up against a local stub server).
- Real OCR end-to-end with RapidOCR on generated screenshots: text
  extracted with correct line breaks and spaces; manifest written; a
  byte-identical duplicate was detected and copied the original's text.
- Re-run dedupe: second pass marked all previously seen hashes as
  `duplicate` with no re-OCR. `--force` re-OCR-ed everything.
- `--cleanup` end-to-end against a stub OpenAI-compatible server with no
  API key: text tidied, manifest `llm_tidy` recorded (`yes`/`copied`).

## Known gaps

- **Small text loses spaces.** At tiny font sizes RapidOCR detects a whole
  line as one box (`AskDanaforfigma`); at normal screenshot sizes spacing
  is fine (verified at 32 px).
- **Byte-hash dedupe only.** Re-cropped/resaved screenshots of the same
  content will not be caught; structural minHash/feature dedupe could be a
  future add-on (see also photo-dedupe-lite-cli).
- **Blank/empty images** are flagged `empty` rather than retried; `--force`
  is the retry path.
- **Windows paths** in the manifest use backslashes (as found); it is a
  CSV record of where files were, not a portable key.
- **No OCR tests with a real model** in CI-style runs (models are heavy);
  pipeline tests use a fake engine, and real-model behavior was verified
  manually as listed above.
