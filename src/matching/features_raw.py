"""Phase 1 pair features on raw text plus blocker provenance. No transliteration."""

from __future__ import annotations

from src.blocking.normalize import normalize_raw, raw_tokens

FEATURE_NAMES = (
    "name_jaccard",
    "name_jaro_winkler",
    "name_length_ratio",
    "address_jaccard",
    "candidate_address_empty",
    "retrieval_score",
    "retrieval_rank",
    "exact_name",
    "exact_address",
    "name_token",
    "address_token",
    "src_is_s3",
)


def jaccard(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def length_ratio(left: str, right: str) -> float:
    left_n = len(left)
    right_n = len(right)
    if left_n == 0 and right_n == 0:
        return 1.0
    if left_n == 0 or right_n == 0:
        return 0.0
    return min(left_n, right_n) / max(left_n, right_n)


def jaro_winkler(left: str, right: str) -> float:
    from rapidfuzz.distance import JaroWinkler

    return float(JaroWinkler.normalized_similarity(left, right))


def raw_feature_row(
    source_name: str,
    source_address: str,
    candidate_name: str,
    candidate_address: str,
    provenance: dict[str, str],
) -> list[float]:
    left_name = normalize_raw(source_name)
    right_name = normalize_raw(candidate_name)
    left_address = normalize_raw(source_address)
    right_address = normalize_raw(candidate_address)
    return [
        jaccard(raw_tokens(source_name), raw_tokens(candidate_name)),
        jaro_winkler(left_name, right_name),
        length_ratio(left_name, right_name),
        jaccard(raw_tokens(source_address), raw_tokens(candidate_address)),
        1.0 if not right_address else 0.0,
        float(provenance["retrieval_score"]),
        float(provenance["rank"]),
        float(provenance["exact_name"]),
        float(provenance["exact_address"]),
        float(provenance["name_token"]),
        float(provenance["address_token"]),
        1.0 if provenance["target_source"] == "S3" else 0.0,
    ]
