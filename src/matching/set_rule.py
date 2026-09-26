"""Set selection on loop groups. Macro F0.5 comes from src.eval.score.

Ties keep the simpler rule, then the higher threshold. Candidate counts outside
the declared buckets raise: this skeleton does not invent a bucket for them.
"""

from __future__ import annotations

from src.eval.score import macro_f05
from src.matching.pass2 import source_of

BUCKETS = ("0", "1", "2-5", "6-20", "21-50")
# Lower rank is simpler. One-owner off is simpler than on. A single threshold
# is simpler than two thresholds, which is simpler than a per-bucket k rule.
SIMPLICITY = {
    ("off", "global_threshold"): 0,
    ("off", "per_source_threshold"): 1,
    ("off", "k_by_bucket"): 2,
    ("on", "global_threshold"): 3,
    ("on", "per_source_threshold"): 4,
    ("on", "k_by_bucket"): 5,
}

Group = tuple[str, list[str], list[float], set[str]]


def candidate_bucket(count: int) -> str:
    if count == 0:
        return "0"
    if count == 1:
        return "1"
    if 2 <= count <= 5:
        return "2-5"
    if 6 <= count <= 20:
        return "6-20"
    if 21 <= count <= 50:
        return "21-50"
    raise ValueError(f"candidate count {count} is outside the declared buckets {BUCKETS}")


def apply_one_owner(groups: list[Group]) -> list[Group]:
    """Keep each target id only for the Source 1 with the highest probability.

    Ties break toward the lexicographically smaller Source 1 id, so one id
    cannot remain on two Source 1 rows.
    """
    best: dict[str, tuple[float, str]] = {}
    for source_id, candidate_ids, probabilities, _truth in groups:
        for candidate_id, probability in zip(candidate_ids, probabilities):
            current = best.get(candidate_id)
            if current is None or probability > current[0] or (
                probability == current[0] and source_id < current[1]
            ):
                best[candidate_id] = (probability, source_id)
    owned: list[Group] = []
    for source_id, candidate_ids, probabilities, truth in groups:
        kept = [
            (candidate_id, probability)
            for candidate_id, probability in zip(candidate_ids, probabilities)
            if best[candidate_id][1] == source_id
        ]
        owned.append(
            (source_id, [item[0] for item in kept], [item[1] for item in kept], truth)
        )
    return owned


def _macro(groups: list[Group], predicted: dict[str, set[str]]) -> float:
    truth = {source_id: truth for source_id, _ids, _probs, truth in groups}
    return macro_f05(predicted, truth)


def _predict_threshold(groups: list[Group], threshold: float, source_thresholds: dict[str, float] | None) -> dict[str, set[str]]:
    predicted: dict[str, set[str]] = {}
    for source_id, candidate_ids, probabilities, _truth in groups:
        kept = []
        for candidate_id, probability in zip(candidate_ids, probabilities):
            cutoff = threshold if source_thresholds is None else source_thresholds[source_of(candidate_id)]
            if probability >= cutoff:
                kept.append(candidate_id)
        if len(kept) != len(set(kept)):
            raise ValueError(f"duplicate ids for {source_id}")
        predicted[source_id] = set(kept)
    return predicted


def _predict_k(groups: list[Group], k_by_bucket: dict[str, int]) -> dict[str, set[str]]:
    predicted: dict[str, set[str]] = {}
    for source_id, candidate_ids, probabilities, _truth in groups:
        bucket = candidate_bucket(len(candidate_ids))
        k = k_by_bucket[bucket]
        order = sorted(range(len(candidate_ids)), key=lambda index: (-probabilities[index], candidate_ids[index]))
        predicted[source_id] = {candidate_ids[index] for index in order[:k]}
    return predicted


def _best_global(groups: list[Group], grid: list[float]) -> tuple[float, float]:
    best_threshold = grid[0]
    best_score = _macro(groups, _predict_threshold(groups, best_threshold, None))
    for threshold in grid[1:]:
        score = _macro(groups, _predict_threshold(groups, threshold, None))
        if score > best_score or (score == best_score and threshold > best_threshold):
            best_score = score
            best_threshold = threshold
    return best_threshold, best_score


def _best_per_source(groups: list[Group], grid: list[float]) -> tuple[float, float, float]:
    best = (grid[0], grid[0])
    best_score = _macro(groups, _predict_threshold(groups, 0.0, {"S2": best[0], "S3": best[1]}))
    for t_s2 in grid:
        for t_s3 in grid:
            score = _macro(groups, _predict_threshold(groups, 0.0, {"S2": t_s2, "S3": t_s3}))
            higher = (t_s2 + t_s3) > (best[0] + best[1]) or (
                (t_s2 + t_s3) == (best[0] + best[1]) and t_s2 > best[0]
            )
            if score > best_score or (score == best_score and higher):
                best_score = score
                best = (t_s2, t_s3)
    return best[0], best[1], best_score


def _best_k(groups: list[Group]) -> tuple[dict[str, int], float]:
    by_bucket: dict[str, list[Group]] = {name: [] for name in BUCKETS}
    for group in groups:
        by_bucket[candidate_bucket(len(group[1]))].append(group)
    chosen: dict[str, int] = {}
    for name, members in by_bucket.items():
        if not members:
            chosen[name] = 0
            continue
        width = max(len(group[1]) for group in members)
        best_k = 0
        best_score = _macro(members, _predict_k(members, {name: 0}))
        for k in range(1, width + 1):
            score = _macro(members, _predict_k(members, {name: k}))
            if score > best_score:
                best_score = score
                best_k = k
        chosen[name] = best_k
    return chosen, _macro(groups, _predict_k(groups, chosen))


def choose_set_rule(groups: list[Group], grid: list[float] | None = None) -> dict:
    """Highest loop macro F0.5. Equal scores keep the simpler family."""
    if not groups:
        raise ValueError("no loop groups")
    if grid is None:
        grid = [index / 100 for index in range(101)]
    candidates = []
    for owner in ("off", "on"):
        current = apply_one_owner(groups) if owner == "on" else groups
        threshold, score = _best_global(current, grid)
        candidates.append(
            {"one_owner": owner, "rule_family": "global_threshold", "threshold": threshold, "score": score}
        )
        t_s2, t_s3, score = _best_per_source(current, grid)
        candidates.append(
            {
                "one_owner": owner,
                "rule_family": "per_source_threshold",
                "t_s2": t_s2,
                "t_s3": t_s3,
                "score": score,
            }
        )
        k_by_bucket, score = _best_k(current)
        candidates.append(
            {
                "one_owner": owner,
                "rule_family": "k_by_bucket",
                "k_by_bucket": k_by_bucket,
                "score": score,
            }
        )
    def sort_key(item: dict) -> tuple:
        return (-item["score"], SIMPLICITY[(item["one_owner"], item["rule_family"])])

    winner = sorted(candidates, key=sort_key)[0]
    if winner["score"] != winner["score"]:
        raise ValueError("set rule search produced a non-finite score")
    return winner
