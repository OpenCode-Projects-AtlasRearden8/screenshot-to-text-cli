"""Junk-stripping clean-up for raw OCR text.

Deliberately conservative: OCR mistakes are hard to undo, so we only
remove text that is almost certainly junk and normalize whitespace.
"""

from __future__ import annotations

import re
import unicodedata

# Lines that consist only of punctuation, symbols, or single-word UI
# noise ("sharing", "com"). Kept short on purpose.
JUNK_LINE_PATTERN = re.compile(
    r"""^(?:[\W_]+|\s*(?:share|sharing|comment|subscribe|like)\s*)$""",
    re.IGNORECASE,
)

# A word broken by a line wrap: "sys-\ntem" -> "system"
HYPHEN_BREAK = re.compile(r"([A-Za-z])-\n([A-Za-z])")


def strip_control_chars(text: str) -> str:
    """Remove control/invisible characters, keep tabs and newlines."""
    cleaned = []
    for char in text:
        if char in ("\n", "\t"):
            cleaned.append(char)
            continue
        category = unicodedata.category(char)
        if category in ("Cn", "Cc", "Cf", "Zl", "Zp"):
            continue
        cleaned.append(char)
    return "".join(cleaned)


def clean_ocr_text(raw: str) -> str:
    """Turn raw OCR output into tidy, copyable text.

    - removes control characters
    - repairs words split across lines by hyphens
    - strips junk lines (stray symbols, UI noise) and blank lines
    - trims trailing spaces
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = strip_control_chars(text)
    text = HYPHEN_BREAK.sub(r"\1\2", text)

    lines = []
    for line in text.split("\n"):
        line = line.rstrip()
        if not line.strip():
            continue
        if JUNK_LINE_PATTERN.match(line.strip()):
            continue
        lines.append(line)

    return "\n".join(lines).strip()
