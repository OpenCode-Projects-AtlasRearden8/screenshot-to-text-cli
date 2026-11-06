"""Optional tidy-up pass through an OpenAI-compatible chat endpoint.

Works out of the box with Ollama (no API key): Ollama exposes an
OpenAI-compatible endpoint at http://localhost:11434/v1. Any other
OpenAI-compatible server works too; pass --api-key if you need one.
The key is only read from the flag or environment at runtime and is
never written to disk by this tool.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_API_BASE = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.2"
DEFAULT_TIMEOUT = 120.0

SYSTEM_PROMPT = (
    "You are a text cleaner. You receive OCR text extracted from a screenshot. "
    "Fix obvious OCR mistakes, remove leftover UI junk and stray symbols, and "
    "keep the original wording, line breaks and structure. Never add commentary. "
    "Return only the cleaned text."
)

_MAX_TEXT_CHARS = 12000  # keep requests small and predictable


class LlmError(RuntimeError):
    pass


def tidy_text(
    text: str,
    api_base: str = DEFAULT_API_BASE,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Return the model's cleaned-up version of `text`."""
    if not text.strip():
        return text
    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS]

    base = api_base.rstrip("/")
    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json"}
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"

    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise LlmError(f"endpoint returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LlmError(
            f"could not reach {url} ({exc.reason}). Is the server running?"
        ) from exc

    try:
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError(f"unexpected response shape: {body}") from exc
