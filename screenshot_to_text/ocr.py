"""OCR backends. Fully local by default.

Backends are detected lazily so the CLI works with a minimal install:

1. rapidocr (rapidocr-onnxruntime): pip-only, models bundled, fully
   local, no system packages needed. Preferred.
2. pytesseract: needs the `tesseract` binary installed by your OS.
"""

from __future__ import annotations

from pathlib import Path

from .clean import clean_ocr_text


def available_backends() -> list[str]:
    backends = []
    try:
        import rapidocr_onnxruntime  # noqa: F401

        backends.append("rapidocr")
    except ImportError:
        pass
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        backends.append("tesseract")
    except Exception:
        pass
    return backends


class OcrEngine:
    """Uniform interface over whatever backend is installed."""

    def __init__(self, backend: str | None = None):
        self.backend_name = backend
        self._rapidocr = None
        self._pytesseract = None

    def _init_rapidocr(self):
        try:
            import rapidocr_onnxruntime
        except ImportError as exc:  # pragma: no cover - guarded by CLI
            raise RuntimeError(
                "RapidOCR is not installed. Install OCR extras with:\n"
                "  pip install screenshot-to-text[rapidocr]"
            ) from exc
        self._rapidocr = rapidocr_onnxruntime.RapidOCR()

    def _init_pytesseract(self):
        try:
            import pytesseract
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pytesseract is not installed. Install the tesseract extra:\n"
                "  pip install screenshot-to-text[tesseract]"
            ) from exc
        pytesseract.get_tesseract_version()
        self._pytesseract = pytesseract

    def ensure_loaded(self) -> str:
        """Load the configured (or first available) backend and return its name."""
        if self._rapidocr is not None:
            return "rapidocr"
        if self._pytesseract is not None:
            return "tesseract"
        backend = self.backend_name or _first_available()
        if backend == "rapidocr":
            self._init_rapidocr()
            return "rapidocr"
        if backend == "tesseract":
            self._init_pytesseract()
            return "tesseract"
        raise RuntimeError(backend_missing_message())

    def extract_text(self, image_path: Path) -> str:
        """Run OCR over one image and return cleaned text."""
        name = self.ensure_loaded()
        if name == "rapidocr":
            result, _ = self._rapidocr(str(image_path))
            if not result:
                return ""
            return clean_ocr_text(_join_lines(result))
        import pytesseract  # already validated

        img = pytesseract.image_to_string(str(image_path))
        return clean_ocr_text(img)


def _first_available() -> str | None:
    backends = available_backends()
    return backends[0] if backends else None


def backend_missing_message() -> str:
    return (
        "No OCR backend found.\n"
        "Install the recommended pip-only backend (fully local, no system packages):\n"
        "  pip install screenshot-to-text[rapidocr]\n"
        "Or install tesseract via your OS package manager and run:\n"
        "  pip install screenshot-to-text[tesseract]"
    )


def _join_lines(items) -> str:
    """Group word boxes into visual lines and join with spaces.

    RapidOCR returns one box per detected word. Joining naively would
    either lose spaces or scramble lines, so we group boxes whose
    vertical ranges overlap by more than half of the smaller height,
    then sort each line left-to-right.
    """
    boxes = []
    for box, text, *_ in items:
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        boxes.append({"left": min(xs), "right": max(xs), "top": min(ys), "bottom": max(ys), "text": text})
    boxes.sort(key=lambda b: (b["top"], b["left"]))

    lines: list[list[dict]] = []
    for item in boxes:
        height = max(item["bottom"] - item["top"], 1.0)
        placed = False
        for line in lines:
            anchor = line[0]
            anchor_height = max(anchor["bottom"] - anchor["top"], 1.0)
            overlap = min(item["bottom"], anchor["bottom"]) - max(item["top"], anchor["top"])
            if overlap > 0.5 * min(height, anchor_height):
                line.append(item)
                placed = True
                break
        if not placed:
            lines.append([item])

    out_lines = []
    for line in sorted(lines, key=lambda l: min(b["top"] for b in l)):
        line.sort(key=lambda b: b["left"])
        out_lines.append(" ".join(b["text"] for b in line))
    return "\n".join(out_lines)
