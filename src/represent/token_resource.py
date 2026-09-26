"""Per-country token frequency, boilerplate mining, and IDF computation.

Rules:
- Mined strictly from train data for US, India, and global fallback.
- France IDF uses provided France test text only for France IDF (no labels).
"""

import json
import math
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set, Tuple
import pandas as pd

from src.represent.config import resource_dir


class TokenResource:
    """Manages document frequencies, IDFs, and boilerplate tokens per country."""

    def __init__(
        self,
        name_idf: Dict[str, Dict[str, float]],
        address_idf: Dict[str, Dict[str, float]],
        boilerplate_tokens: Dict[str, Set[str]],
    ):
        self.name_idf = name_idf
        self.address_idf = address_idf
        self.boilerplate_tokens = boilerplate_tokens

    def get_name_idf(self, token: str, country: str = "global") -> float:
        c_map = self.name_idf.get(country, self.name_idf.get("global", {}))
        return c_map.get(token, self.name_idf.get("global", {}).get(token, 10.0))

    def get_address_idf(self, token: str, country: str = "global") -> float:
        c_map = self.address_idf.get(country, self.address_idf.get("global", {}))
        return c_map.get(token, self.address_idf.get("global", {}).get(token, 10.0))

    def is_boilerplate(self, token: str, country: str = "global") -> bool:
        b_set = self.boilerplate_tokens.get(country, self.boilerplate_tokens.get("global", set()))
        return token in b_set

    def save(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        # Convert sets to lists for JSON serialization
        serializable_boilerplate = {k: sorted(list(v)) for k, v in self.boilerplate_tokens.items()}
        
        with (output_dir / "name_idf.json").open("w", encoding="utf-8") as f:
            json.dump(self.name_idf, f, indent=2, ensure_ascii=False)
        with (output_dir / "address_idf.json").open("w", encoding="utf-8") as f:
            json.dump(self.address_idf, f, indent=2, ensure_ascii=False)
        with (output_dir / "boilerplate_tokens.json").open("w", encoding="utf-8") as f:
            json.dump(serializable_boilerplate, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, resource_path: Path) -> "TokenResource":
        with (resource_path / "name_idf.json").open("r", encoding="utf-8") as f:
            name_idf = json.load(f)
        with (resource_path / "address_idf.json").open("r", encoding="utf-8") as f:
            address_idf = json.load(f)
        with (resource_path / "boilerplate_tokens.json").open("r", encoding="utf-8") as f:
            raw_bp = json.load(f)
            boilerplate = {k: set(v) for k, v in raw_bp.items()}
        return cls(name_idf, address_idf, boilerplate)


def compute_idf_and_boilerplate_from_tokens(
    token_lists_by_country: Dict[str, List[List[str]]],
    boilerplate_df_threshold: float = 0.01,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Set[str]]]:
    """Compute smoothed IDF and extract boilerplate tokens (> threshold DF)."""
    idf_by_country: Dict[str, Dict[str, float]] = {}
    boilerplate_by_country: Dict[str, Set[str]] = {}

    all_tokens_global: List[List[str]] = []

    for country, doc_tokens in token_lists_by_country.items():
        doc_count = len(doc_tokens)
        if doc_count == 0:
            continue

        df_counter: Counter = Counter()
        for doc in doc_tokens:
            unique_in_doc = set(doc)
            df_counter.update(unique_in_doc)

        c_idf: Dict[str, float] = {}
        c_bp: Set[str] = set()

        for token, df in df_counter.items():
            # Smooth IDF formula: log((1 + N) / (1 + df)) + 1
            idf = math.log((1 + doc_count) / (1 + df)) + 1.0
            c_idf[token] = round(idf, 4)
            if (df / doc_count) >= boilerplate_df_threshold:
                c_bp.add(token)

        idf_by_country[country] = c_idf
        boilerplate_by_country[country] = c_bp
        all_tokens_global.extend(doc_tokens)

    # Compute global fallback
    total_docs = len(all_tokens_global)
    if total_docs > 0:
        global_df: Counter = Counter()
        for doc in all_tokens_global:
            global_df.update(set(doc))
        g_idf: Dict[str, float] = {}
        g_bp: Set[str] = set()
        for token, df in global_df.items():
            idf = math.log((1 + total_docs) / (1 + df)) + 1.0
            g_idf[token] = round(idf, 4)
            if (df / total_docs) >= boilerplate_df_threshold:
                g_bp.add(token)
        idf_by_country["global"] = g_idf
        boilerplate_by_country["global"] = g_bp

    return idf_by_country, boilerplate_by_country
