"""Unicode normalization, script detection, and accent-folding utilities."""

import unicodedata
import re

# Unicode script ranges for Indic languages + Latin
SCRIPT_RANGES = {
    "devanagari": (0x0900, 0x097F),
    "bengali": (0x0980, 0x09FF),
    "gujarati": (0x0A80, 0x0AFF),
    "tamil": (0x0B80, 0x0BFF),
    "telugu": (0x0C00, 0x0C7F),
    "kannada": (0x0C80, 0x0CFF),
    "malayalam": (0x0D00, 0x0D7F),
}

# Regex to remove non-printable control characters
CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def normalize_nfkc(text: str) -> str:
    """Standardize Unicode composite characters and full-width representations."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    return CONTROL_CHAR_RE.sub("", normalized)


def detect_script(text: str) -> str:
    """Detect the dominant script of a text string.
    
    Returns one of: 'devanagari', 'kannada', 'tamil', 'telugu',
    'bengali', 'gujarati', 'malayalam', 'latin', or 'mixed'.
    """
    if not text:
        return "latin"
    
    script_counts = {k: 0 for k in SCRIPT_RANGES}
    latin_count = 0
    total_alpha = 0
    
    for ch in text:
        cp = ord(ch)
        if not ch.isalpha():
            continue
        total_alpha += 1
        found = False
        for script, (start, end) in SCRIPT_RANGES.items():
            if start <= cp <= end:
                script_counts[script] += 1
                found = True
                break
        if not found and ((0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A) or (0x00C0 <= cp <= 0x024F) or (0x1E00 <= cp <= 0x1EFF)):
            latin_count += 1
            
    if total_alpha == 0:
        return "latin"
        
    for script, count in script_counts.items():
        if count > 0 and count >= total_alpha * 0.3:
            return script
            
    if latin_count > 0:
        return "latin"
        
    max_script, max_count = max(script_counts.items(), key=lambda x: x[1])
    if max_count > 0:
        return max_script
    return "latin"


def fold_accents(text: str) -> str:
    """Strip combining diacritics and convert accented Latin characters to basic ASCII.
    
    E.g., 'Café' -> 'Cafe', 'Société' -> 'Societe'.
    Preserves Indic characters and dependent vowel signs untouched.
    """
    if not text:
        return ""
    # NFD decomposition decomposes accented characters into base char + combining mark
    decomposed = unicodedata.normalize("NFD", text)
    # Filter out combining diacritical marks (Mn category) only for Latin / ASCII combining marks
    filtered = []
    for ch in decomposed:
        cp = ord(ch)
        # Latin combining diacritical mark ranges: 0x0300-0x036F, 0x1AB0-0x1AFF, 0x1DC0-0x1DFF, 0x20D0-0x20FF, 0xFE20-0xFE2F
        if (0x0300 <= cp <= 0x036F) or (0x1AB0 <= cp <= 0x1AFF) or (0x1DC0 <= cp <= 0x1DFF) or (0x20D0 <= cp <= 0x20FF) or (0xFE20 <= cp <= 0xFE2F):
            continue
        filtered.append(ch)
    # Return normalized back to NFC
    return unicodedata.normalize("NFC", "".join(filtered))
