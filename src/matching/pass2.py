"""Pass-2 context features from out-of-fold pass-1 scores. No country one-hot."""

from __future__ import annotations

PASS2_FEATURE_NAMES = (
    "p1_rank_in_s1_source",
    "p1_gap_to_best",
    "p1_gap_to_next",
    "p1_count_above_0_5",
    "p1_is_best_owner",
)


def source_of(candidate_id: str) -> str:
    if candidate_id.startswith("S2-"):
        return "S2"
    if candidate_id.startswith("S3-"):
        return "S3"
    raise ValueError(f"candidate id is not S2 or S3: {candidate_id}")


def pass2_feature_rows(
    source_ids: list[str],
    candidate_ids: list[str],
    probabilities: list[float],
) -> list[list[float]]:
    """One feature row per pair, in the same order as the inputs.

    Rank, gaps, and the 0.5 count are computed inside one Source 1 id and one
    target source. Best-owner uses every Source 1 in this scored split.
    Probability ties break toward the lexicographically smaller Source 1 id.
    """
    if not (len(source_ids) == len(candidate_ids) == len(probabilities)):
        raise ValueError("pass-2 inputs are not aligned")
    best_owner: dict[str, tuple[float, str]] = {}
    for source_id, candidate_id, probability in zip(source_ids, candidate_ids, probabilities):
        current = best_owner.get(candidate_id)
        if current is None or probability > current[0] or (probability == current[0] and source_id < current[1]):
            best_owner[candidate_id] = (probability, source_id)
    grouped: dict[tuple[str, str], list[int]] = {}
    for index, (source_id, candidate_id) in enumerate(zip(source_ids, candidate_ids)):
        grouped.setdefault((source_id, source_of(candidate_id)), []).append(index)
    rows: list[list[float] | None] = [None] * len(source_ids)
    for indexes in grouped.values():
        ordered = sorted(indexes, key=lambda index: (-probabilities[index], candidate_ids[index]))
        ordered_probs = [probabilities[index] for index in ordered]
        above = float(sum(probability >= 0.5 for probability in ordered_probs))
        best = ordered_probs[0]
        for rank, index in enumerate(ordered, start=1):
            probability = probabilities[index]
            gap_next = 0.0 if rank == len(ordered) else probability - ordered_probs[rank]
            rows[index] = [
                float(rank),
                best - probability,
                gap_next,
                above,
                1.0 if best_owner[candidate_ids[index]][1] == source_ids[index] else 0.0,
            ]
    if any(row is None for row in rows):
        raise RuntimeError("pass-2 missed a pair")
    return rows  # type: ignore[return-value]
