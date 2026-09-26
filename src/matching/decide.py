"""Keep a candidate only when its probability clears one global threshold."""

from __future__ import annotations

from src.eval.score import entity_f05, macro_f05

Group = tuple[str, list[str], list[float], set[str]]


def kept_ids(candidate_ids: list[str], probabilities: list[float], threshold: float) -> list[str]:
    if len(candidate_ids) != len(probabilities):
        raise ValueError("probabilities do not align with candidates")
    kept = [
        candidate_id
        for candidate_id, probability in zip(candidate_ids, probabilities)
        if probability >= threshold
    ]
    if any(candidate_id not in candidate_ids for candidate_id in kept):
        raise ValueError("decision emitted an id that is not a candidate")
    if len(kept) != len(set(kept)):
        raise ValueError("decision emitted a duplicate id")
    return kept


def macro_at_threshold(groups: list[Group], threshold: float) -> float:
    predicted = {
        source_id: set(kept_ids(candidate_ids, probabilities, threshold))
        for source_id, candidate_ids, probabilities, _truth in groups
    }
    truth = {source_id: truth for source_id, _ids, _probs, truth in groups}
    return macro_f05(predicted, truth)


def choose_threshold(groups: list[Group], grid: list[float] | None = None) -> tuple[float, float]:
    """Highest loop macro F0.5. Ties keep the higher threshold (precision)."""
    if not groups:
        raise ValueError("no loop groups")
    if grid is None:
        grid = [index / 100 for index in range(101)]
    best_threshold = grid[0]
    best_score = macro_at_threshold(groups, best_threshold)
    for threshold in grid[1:]:
        score = macro_at_threshold(groups, threshold)
        if score > best_score or (score == best_score and threshold > best_threshold):
            best_score = score
            best_threshold = threshold
    if best_score != best_score:  # NaN
        raise ValueError("threshold search produced a non-finite score")
    return best_threshold, best_score


def finite_disjoint_example() -> float:
    """Lock the official scorer's disjoint case. Do not reimplement the metric."""
    return entity_f05({"S2-a"}, {"S2-b"})
