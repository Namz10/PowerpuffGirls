"""Deterministic address normalization with French, Indian, and US rule sets."""

import re
from typing import List, Optional, Tuple
from src.represent.unicode_utils import normalize_nfkc, fold_accents

# Landmark keywords
LANDMARK_RE = re.compile(
    r"\b(near|opp|opposite|behind|beside|adj|adjacent|next\s+to|in\s+front\s+of)\b",
    re.IGNORECASE,
)

# Postal code patterns
INDIA_PIN_RE = re.compile(r"\b([1-9][0-9]{5})\b")
US_ZIP_RE = re.compile(r"\b([0-9]{5}(?:-[0-9]{4})?)\b")
FRANCE_POSTAL_RE = re.compile(r"\b([0-9]{5})\b")

# French specific patterns
FRENCH_CEDEX_RE = re.compile(r"\bcedex(?:\s+[0-9]{1,3})?\b", re.IGNORECASE)
FRENCH_BP_RE = re.compile(r"\b(bo[iî]te\s+postale|b\.?p\.?)\b", re.IGNORECASE)
FRENCH_ORDINAL_RE = re.compile(r"\b([0-9]+)\s*(?:[eè]me|er|[eè]re|e)\b", re.IGNORECASE)

# Standard street and address abbreviations
ADDRESS_ABBREVIATIONS = [
    (re.compile(r"\b(rd\.?|rd)\b", re.IGNORECASE), "road"),
    (re.compile(r"\b(st\.?|str\.?)\b", re.IGNORECASE), "street"),
    (re.compile(r"\b(ave\.?|av\.?)\b", re.IGNORECASE), "avenue"),
    (re.compile(r"\b(blvd\.?|bvd\.?)\b", re.IGNORECASE), "boulevard"),
    (re.compile(r"\b(bldg\.?|build\.?)\b", re.IGNORECASE), "building"),
    (re.compile(r"\b(apt\.?|suite|ste\.?)\b", re.IGNORECASE), "suite"),
    (re.compile(r"\b(flr\.?|fl\.?)\b", re.IGNORECASE), "floor"),
    (re.compile(r"\b(opp\.?)\b", re.IGNORECASE), "opposite"),
    (re.compile(r"\b(nr\.?)\b", re.IGNORECASE), "near"),
    (re.compile(r"\b(dept\.?)\b", re.IGNORECASE), "department"),
    (re.compile(r"\b(sq\.?)\b", re.IGNORECASE), "square"),
    (re.compile(r"\b(dr\.?)\b", re.IGNORECASE), "drive"),
    (re.compile(r"\b(ln\.?)\b", re.IGNORECASE), "lane"),
    (re.compile(r"\b(pl\.?)\b", re.IGNORECASE), "place"),
    (re.compile(r"\b(ct\.?)\b", re.IGNORECASE), "court"),
    (re.compile(r"\b(pkwy\.?|pky\.?)\b", re.IGNORECASE), "parkway"),
    (re.compile(r"\b(hwy\.?)\b", re.IGNORECASE), "highway"),
]

PUNCT_SPLIT_RE = re.compile(r"[^\w\s]", re.UNICODE)
WHITESPACE_RE = re.compile(r"\s+")


def normalize_address(
    raw_address: Optional[str], country: str = ""
) -> Tuple[str, List[str], bool, bool, bool, Optional[str]]:
    """Normalize an address string.
    
    Returns:
        (normalized_address, tokens, is_empty, has_landmark, is_cedex, postal_code)
    """
    if not raw_address or not isinstance(raw_address, str) or raw_address.strip().lower() in ("", "nan", "null", "none"):
        return "", [], True, False, False, None

    # 1. NFKC & Accent-folding
    text = normalize_nfkc(raw_address)
    folded = fold_accents(text).lower()

    # 2. Detect landmark references
    has_landmark = bool(LANDMARK_RE.search(folded))

    # 3. Detect CEDEX (French routing)
    is_cedex = bool(FRENCH_CEDEX_RE.search(folded))

    # 4. Standardize French BP (boîte postale)
    clean_text = FRENCH_BP_RE.sub(" bp ", folded)

    # 5. Standardize French ordinals (e.g., '1er' -> '1', '2ème' -> '2')
    clean_text = FRENCH_ORDINAL_RE.sub(r" \1 ", clean_text)

    # 6. Extract postal code based on country or general heuristics
    postal_code: Optional[str] = None
    country_upper = country.strip().upper() if country else ""

    if country_upper == "INDIA":
        pin_match = INDIA_PIN_RE.search(clean_text)
        if pin_match:
            postal_code = pin_match.group(1)
    elif country_upper == "FRANCE":
        fr_match = FRANCE_POSTAL_RE.search(clean_text)
        if fr_match:
            postal_code = fr_match.group(1)
    elif country_upper == "US":
        us_match = US_ZIP_RE.search(clean_text)
        if us_match:
            postal_code = us_match.group(1)[:5]
    else:
        # Fallback: check 6-digit India PIN first, then 5-digit postal code
        pin_match = INDIA_PIN_RE.search(clean_text)
        if pin_match:
            postal_code = pin_match.group(1)
        else:
            zip_match = FRANCE_POSTAL_RE.search(clean_text)
            if zip_match:
                postal_code = zip_match.group(1)

    # 7. Expand standard abbreviations
    for pattern, replacement in ADDRESS_ABBREVIATIONS:
        clean_text = pattern.sub(f" {replacement} ", clean_text)

    # 8. Clean punctuation and collapse whitespace
    clean_text = PUNCT_SPLIT_RE.sub(" ", clean_text)
    clean_text = WHITESPACE_RE.sub(" ", clean_text).strip()

    is_empty = len(clean_text) == 0
    tokens = [t for t in clean_text.split() if t]

    return clean_text, tokens, is_empty, has_landmark, is_cedex, postal_code
