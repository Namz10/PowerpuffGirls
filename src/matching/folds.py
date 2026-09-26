"""Group folds by Source 1 id. A pair never leaves its Source 1 group.

sklearn ``GroupKFold`` has no ``random_state``. The seed shuffles Source 1 ids,
then each id is assigned by round-robin. That is the group-k-fold constraint.
``GroupKFold`` is used to reject a split count the library itself would reject.
"""

from __future__ import annotations

import random

from sklearn.model_selection import GroupKFold

from src.matching.config import SEED


def assert_fit_only(train_ids: set[str], fit_ids: set[str], loop_ids: set[str], report_ids: set[str]) -> None:
    """Training ids must be fit ids. Loop and report are selection and confirmation only."""
    leaked = set(train_ids) & (set(loop_ids) | set(report_ids))
    if leaked:
        raise ValueError(f"training ids overlap loop or report ({len(leaked)} ids)")
    outside = set(train_ids) - set(fit_ids)
    if outside:
        raise ValueError(f"training ids are not a subset of fit ({len(outside)} ids)")


def group_fold_ids(source_ids: list[str], n_splits: int = 5, seed: int = SEED) -> list[int]:
    """Return one fold id per row. Every row of one Source 1 id shares that fold."""
    if n_splits < 2:
        raise ValueError("n_splits must be at least 2")
    unique = sorted(set(source_ids))
    if len(unique) < n_splits:
        raise ValueError(f"need at least {n_splits} Source 1 ids, found {len(unique)}")
    GroupKFold(n_splits=n_splits)
    shuffled = list(unique)
    random.Random(seed).shuffle(shuffled)
    fold_of = {source_id: index % n_splits for index, source_id in enumerate(shuffled)}
    assigned = [fold_of[source_id] for source_id in source_ids]
    by_fold: dict[int, set[str]] = {fold: set() for fold in range(n_splits)}
    for source_id, fold in zip(source_ids, assigned):
        by_fold[fold].add(source_id)
    seen: set[str] = set()
    for members in by_fold.values():
        if seen & members:
            raise RuntimeError("a Source 1 id landed in two folds")
        seen |= members
    if seen != set(unique):
        raise RuntimeError("fold assignment dropped a Source 1 id")
    return assigned


def train_valid_groups(source_ids: list[str], n_splits: int = 5, seed: int = SEED) -> list[tuple[set[str], set[str]]]:
    """Five disjoint held-out Source 1 sets. Training groups are the complement."""
    folds = group_fold_ids(source_ids, n_splits, seed)
    groups = set(source_ids)
    held: list[set[str]] = []
    for fold in range(n_splits):
        held.append({source_id for source_id, assigned in zip(source_ids, folds) if assigned == fold})
    return [(groups - test, test) for test in held]
