"""Average fold probabilities without reordering candidates."""

from __future__ import annotations


def average_fold_probabilities(fold_probabilities: list[list[float]]) -> list[float]:
    """Mean across fold models. Every fold must score the same candidate order."""
    if not fold_probabilities:
        raise ValueError("no fold probabilities")
    width = len(fold_probabilities[0])
    if any(len(row) != width for row in fold_probabilities):
        raise ValueError("fold probability rows differ in length")
    count = float(len(fold_probabilities))
    return [sum(row[index] for row in fold_probabilities) / count for index in range(width)]
