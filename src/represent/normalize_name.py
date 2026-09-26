"""Deterministic business name normalization."""

import re
from typing import List, Tuple
from src.represent.unicode_utils import normalize_nfkc, fold_accents, detect_script
from src.represent.romanization import romanize_indic_text

# Regex for common formal prefixes
JUNK_PREFIX_RE = re.compile(r"^(m/s|messrs|the|shree|sri)\b\s*", re.IGNORECASE)

# Legal suffix dictionary ordered from longest / most specific to shortest
LEGAL_SUFFIXES = [
    # Multi-word forms
    (re.compile(r"\b(pvt\.?\s*ltd\.?|private\s+limited)\b", re.IGNORECASE), "private limited"),
    (re.compile(r"\b(l\.?l\.?c\.?|limited\s+liability\s+co(mpany)?)\b", re.IGNORECASE), "llc"),
    (re.compile(r"\b(l\.?l\.?p\.?|limited\s+liability\s+partnership)\b", re.IGNORECASE), "llp"),
    (re.compile(r"\b(inc\.?|incorporated)\b", re.IGNORECASE), "inc"),
    (re.compile(r"\b(corp\.?|corporation)\b", re.IGNORECASE), "corp"),
    (re.compile(r"\b(ltd\.?|limited)\b", re.IGNORECASE), "ltd"),
    (re.compile(r"\b(co\.?|company)\b", re.IGNORECASE), "company"),
    
    # French legal entities
    (re.compile(r"\b(s\.?a\.?s\.?u\.?|societe\s+par\s+actions\s+simplifiee\s+unipersonnelle)\b", re.IGNORECASE), "sasu"),
    (re.compile(r"\b(s\.?a\.?s\.?|societe\s+par\s+actions\s+simplifiee)\b", re.IGNORECASE), "sas"),
    (re.compile(r"\b(e\.?u\.?r\.?l\.?|entreprise\s+unipersonnelle\s+a\s+responsabilite\s+limitee)\b", re.IGNORECASE), "eurl"),
    (re.compile(r"\b(s\.?a\.?r\.?l\.?|societe\s+a\s+responsabilite\s+limitee)\b", re.IGNORECASE), "sarl"),
    (re.compile(r"\b(s\.?c\.?i\.?|societe\s+civile\s+immobiliere)\b", re.IGNORECASE), "sci"),
    (re.compile(r"\b(s\.?n\.?c\.?|societe\s+en\s+nom\s+collectif)\b", re.IGNORECASE), "snc"),
    (re.compile(r"\b(s\.?c\.?|societe\s+civile)\b", re.IGNORECASE), "sc"),
    (re.compile(r"\b(s\.?a\.?|societe\s+anonyme)\b", re.IGNORECASE), "sa"),
    
    # Other common international forms
    (re.compile(r"\b(gmbh|ag|bv|nv|sp\s*z\s*o\s*o)\b", re.IGNORECASE), r"\1"),
]

# Non-alphanumeric punctuation (preserves unicode letters and digits)
PUNCT_SPLIT_RE = re.compile(r"[^\w\s]", re.UNICODE)
WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(raw_name: str) -> Tuple[str, str, str, str, List[str]]:
    """Normalize a business name.
    
    Returns:
        (normalized_name, romanized_name, accent_folded_name, source_script, tokens)
    """
    if not raw_name or not isinstance(raw_name, str):
        return "", "", "", "latin", []

    # 1. NFKC Unicode normalization
    text = normalize_nfkc(raw_name)

    # 2. Conjunction expansion
    text = text.replace("&", " and ").replace("+", " and ")

    # 3. Detect script before Romanization
    script = detect_script(text)

    # 4. Strip junk prefixes
    text = JUNK_PREFIX_RE.sub("", text)

    # 5. Accent-folded Latin view
    folded = fold_accents(text)

    # 6. Legal suffix mapping on folded text
    clean_text = folded.lower()
    for pattern, replacement in LEGAL_SUFFIXES:
        clean_text = pattern.sub(f" {replacement} ", clean_text)

    # 7. Clean punctuation and whitespace
    clean_text = PUNCT_SPLIT_RE.sub(" ", clean_text)
    clean_text = WHITESPACE_RE.sub(" ", clean_text).strip()

    # 8. Compute Romanized representation for Indic scripts
    if script != "latin":
        raw_romanized = romanize_indic_text(text)
        rom_folded = fold_accents(raw_romanized).lower()
        rom_folded = rom_folded.replace("&", " and ").replace("+", " and ")
        rom_folded = JUNK_PREFIX_RE.sub("", rom_folded)
        for pattern, replacement in LEGAL_SUFFIXES:
            rom_folded = pattern.sub(f" {replacement} ", rom_folded)
        rom_clean = PUNCT_SPLIT_RE.sub(" ", rom_folded)
        romanized_name = WHITESPACE_RE.sub(" ", rom_clean).strip()
    else:
        romanized_name = clean_text

    # 9. Extract unique tokens
    if script != "latin":
        tokens = [t for t in rom_clean.split() if t]
    else:
        tokens = [t for t in clean_text.split() if t]

    # Original normalized name preserves Indic / NFKC chars with punctuation cleaned
    orig_clean = PUNCT_SPLIT_RE.sub(" ", text.lower())
    orig_clean = WHITESPACE_RE.sub(" ", orig_clean).strip()

    return orig_clean, romanized_name, clean_text, script, tokens
