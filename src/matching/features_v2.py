"""Phase 2 feature schema. Adds canonical, romanized, and phonetic evidence.

This module does not train and does not move the Phase 1 threshold.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.matching.features_raw import FEATURE_NAMES as PHASE1_FEATURE_NAMES
from src.matching.features_raw import jaccard, jaro_winkler
from src.represent.canonical_record import CanonicalRecord
from src.represent.config import NORMALIZER_VERSION

PHASE2_FEATURE_NAMES = (
    "norm_name_jaccard",
    "norm_name_jaro",
    "romanized_name_jaccard",
    "romanized_name_jaro",
    "accent_folded_name_jaro",
    "phonetic_primary_equal",
    "phonetic_primary_jaro",
    "name_idf_overlap",
    "address_idf_overlap",
    "postal_equal",
    "postal_conflict",
    "postal_missing",
    "address_empty_canonical",
    "is_cedex_either",
    "same_script",
)

ALL_FEATURE_NAMES = PHASE1_FEATURE_NAMES + PHASE2_FEATURE_NAMES
SCHEMA_VERSION = "phase2-v1"


def primary_metaphone(text: str) -> str:
    """Metaphone code. Current jellyfish dropped Double Metaphone on license grounds."""
    import jellyfish

    if not text:
        return ""
    return jellyfish.metaphone(text) or ""


def idf_overlap(left: list[str], right: list[str], country: str, lookup) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    shared = left_set & right_set

    def weight(tokens: set[str]) -> float:
        return sum(float(lookup(token, country)) for token in tokens)

    left_weight = weight(left_set)
    right_weight = weight(right_set)
    shared_weight = weight(shared)
    denominator = left_weight + right_weight - shared_weight
    if denominator <= 0:
        return 0.0
    return shared_weight / denominator


def postal_flags(left: str | None, right: str | None) -> tuple[float, float, float]:
    if not left or not right:
        return 0.0, 0.0, 1.0
    if left == right:
        return 1.0, 0.0, 0.0
    return 0.0, 1.0, 0.0


def phase2_feature_row(
    source: CanonicalRecord,
    candidate: CanonicalRecord,
    token_resource,
) -> list[float]:
    source_code = primary_metaphone(source.romanized_name)
    candidate_code = primary_metaphone(candidate.romanized_name)
    equal, conflict, missing = postal_flags(source.postal_code, candidate.postal_code)
    country = source.country or "global"
    return [
        jaccard(tuple(source.name_tokens), tuple(candidate.name_tokens)),
        jaro_winkler(source.normalized_name, candidate.normalized_name),
        jaccard(tuple(source.romanized_name.split()), tuple(candidate.romanized_name.split())),
        jaro_winkler(source.romanized_name, candidate.romanized_name),
        jaro_winkler(source.accent_folded_name, candidate.accent_folded_name),
        1.0 if source_code and source_code == candidate_code else 0.0,
        jaro_winkler(source_code, candidate_code) if source_code and candidate_code else 0.0,
        idf_overlap(source.name_tokens, candidate.name_tokens, country, token_resource.get_name_idf),
        idf_overlap(
            source.address_tokens,
            candidate.address_tokens,
            country,
            token_resource.get_address_idf,
        ),
        equal,
        conflict,
        missing,
        1.0 if candidate.is_empty_address else 0.0,
        1.0 if source.is_cedex or candidate.is_cedex else 0.0,
        1.0 if source.source_script == candidate.source_script else 0.0,
    ]


def schema_document() -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "normalizer_version": NORMALIZER_VERSION,
        "phase1_features": list(PHASE1_FEATURE_NAMES),
        "phase2_features": list(PHASE2_FEATURE_NAMES),
        "features": list(ALL_FEATURE_NAMES),
        "threshold_policy": "phase1_provisional_threshold is not changed by this schema",
        "country_features": "none; country equality is enforced by the blocker",
        "idf": "TokenResource.load artifacts/resources; unseen token uses that loader's default",
        "phonetic": "jellyfish metaphone on romanized_name, computed in matching",
    }


def schema_bytes() -> bytes:
    return (json.dumps(schema_document(), indent=2, sort_keys=True) + "\n").encode("utf-8")


def schema_sha256() -> str:
    return hashlib.sha256(schema_bytes()).hexdigest()
