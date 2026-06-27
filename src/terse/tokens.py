"""Dependency-free token estimation.

This is an *approximation* of how modern BPE tokenizers (the GPT / Claude
families) count tokens. It is deliberately not exact: the whole point of
``terse`` is to stay dependency-free, so we do not pull in a multi-megabyte
tokenizer just to print a savings number.

The heuristic treats each word-ish chunk as roughly ``ceil(len / 4)`` tokens
(most short words are a single token; longer identifiers split into several),
counts each punctuation symbol as one token, and adds one token per newline.
On typical developer log output this lands within ~10-15% of tiktoken's
``cl100k_base`` — close enough to compare *before* and *after*, which is all
we use it for.
"""

from __future__ import annotations

import math
import re

# Word-ish runs OR a single non-word, non-space character.
_CHUNK = re.compile(r"\w+|[^\w\s]")


def estimate_tokens(text: str) -> int:
    """Return an approximate LLM token count for ``text``."""
    if not text:
        return 0
    total = 0
    for chunk in _CHUNK.findall(text):
        # Short words ~= 1 token; long identifiers split roughly every 4 chars.
        total += max(1, math.ceil(len(chunk) / 4))
    # Newlines are almost always their own token.
    total += text.count("\n")
    return total


def human_bytes(n: int) -> str:
    """Format a byte count as a short human-readable string."""
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)}{unit}"
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GB"
