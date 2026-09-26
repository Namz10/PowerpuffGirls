"""Write matching_results.tsv in candidate-file order. Empty lists stay empty."""

from __future__ import annotations

import csv
from pathlib import Path

from src.matching.decide import kept_ids

MATCHING_HEADER = ["source1_entity_id", "matched_entity_ids"]


def write_matching(path: Path, rows: list[tuple[str, list[str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(MATCHING_HEADER)
        for source_id, matched in rows:
            if len(matched) != len(set(matched)):
                raise ValueError(f"duplicate match ids for {source_id}")
            if any(not item.startswith(("S2-", "S3-")) for item in matched):
                raise ValueError(f"{source_id} has a non S2/S3 id")
            writer.writerow((source_id, ",".join(matched)))


def decide_rows(
    groups: list[tuple[str, list[str], list[float]]],
    threshold: float,
) -> list[tuple[str, list[str]]]:
    return [
        (source_id, kept_ids(candidate_ids, probabilities, threshold))
        for source_id, candidate_ids, probabilities in groups
    ]
