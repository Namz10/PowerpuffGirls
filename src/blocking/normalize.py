"""Minimal Phase-1 raw-text normalization.

This deliberately does not transliterate or use external reference data.  The
raw blocker is a working baseline; richer canonical representations belong to
the later representation phase.
"""

from __future__ import annotations

import re
import unicodedata

_SPACE = re.compile(r"\s+")


def normalize_raw(value: str) -> str:
    """Return a deterministic, Unicode-preserving comparison form."""
    value = unicodedata.normalize("NFKC", value or "").casefold()
    # Combining marks are part of letters in Indic and other scripts; treating
    # them as punctuation would split one word into meaningless fragments.
    value = "".join(
        character
        if character.isalnum() or unicodedata.category(character).startswith("M")
        else " "
        for character in value
    )
    return _SPACE.sub(" ", value).strip()


def raw_tokens(value: str) -> tuple[str, ...]:
    """Unique useful tokens in stable order."""
    normalized = normalize_raw(value)
    return tuple(dict.fromkeys(token for token in normalized.split() if len(token) >= 2))
