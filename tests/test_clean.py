"""Tests for the junk-stripping cleaner."""

from screenshot_to_text.clean import clean_ocr_text, strip_control_chars


def test_removes_control_characters():
    cleaned = strip_control_chars("hello\u200bworld\x07!")
    assert "\x07" not in cleaned
    assert "\u200b" not in cleaned
    assert "\x0b" not in strip_control_chars("line\nnext\x0b")


def test_keeps_newlines_and_tabs():
    assert strip_control_chars("a\nb\td") == "a\nb\td"


def test_junk_lines_removed():
    raw = "\n".join(["Answer: 42", "----", "~", "42"])
    cleaned = clean_ocr_text(raw)
    assert "Answer: 42" in cleaned
    assert "----" not in cleaned
    assert "\n42" in cleaned


def test_collapse_blank_lines():
    raw = "one\n\n\n\n\ntwo\n\nthree"
    assert clean_ocr_text(raw) == "one\ntwo\nthree"


def test_trailing_whitespace_trimmed():
    assert clean_ocr_text("line one   \nline two   ") == "line one\nline two"


def test_empty_and_whitespace_only():
    assert clean_ocr_text("") == ""
    assert clean_ocr_text("\n\n\n") == ""
    assert clean_ocr_text("   ") == ""


def test_already_clean_text_unchanged():
    text = "Total: $19.99\nOrder #12345\nThanks!"
    assert clean_ocr_text(text) == text


def test_hyphenated_line_break_rejoined():
    raw = "excep-\ntional value"
    assert clean_ocr_text(raw) == "exceptional value"
