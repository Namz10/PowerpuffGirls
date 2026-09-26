"""Country normalization and open-country rule dispatching."""

from typing import Any, Dict, Optional

# Standard known country mappings
COUNTRY_MAP = {
    "india": "India",
    "in": "India",
    "ind": "India",
    "us": "US",
    "usa": "US",
    "united states": "US",
    "united states of america": "US",
    "france": "France",
    "fr": "France",
    "fra": "France",
}


def normalize_country(country_raw: Optional[str]) -> str:
    """Normalize country string to canonical title/code, preserving unknown countries as open labels."""
    if not country_raw or not isinstance(country_raw, str):
        return "Unknown"
    cleaned = country_raw.strip()
    lower = cleaned.lower()
    if lower in COUNTRY_MAP:
        return COUNTRY_MAP[lower]
    # Open equality label: preserve whatever country name was provided
    return cleaned.title() if len(cleaned) > 2 else cleaned.upper()
