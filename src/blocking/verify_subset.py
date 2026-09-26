"""Strict proof that each match is present in the exact candidate row."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def verify_subset(matching_path: Path, candidate_path: Path) -> int:
    checked = 0
    with matching_path.open(encoding="utf-8", newline="") as matches, candidate_path.open(
        encoding="utf-8", newline=""
    ) as candidates:
        match_reader = csv.reader(matches, delimiter="\t")
        candidate_reader = csv.reader(candidates, delimiter="\t")
        if next(match_reader, None) != ["source1_entity_id", "matched_entity_ids"]:
            raise ValueError("unexpected matching_results.tsv header")
        if next(candidate_reader, None) != ["source1_entity_id", "candidate_entity_ids"]:
            raise ValueError("unexpected candidate_pairs.tsv header")
        sentinel = object()
        while True:
            match_row = next(match_reader, sentinel)
            candidate_row = next(candidate_reader, sentinel)
            if match_row is sentinel or candidate_row is sentinel:
                if match_row is not sentinel or candidate_row is not sentinel:
                    raise ValueError("matching and candidate row counts differ")
                break
            if len(match_row) != 2 or len(candidate_row) != 2:
                raise ValueError(f"malformed row after {checked} checked rows")
            if match_row[0] != candidate_row[0]:
                raise ValueError(f"S1 row order differs at {match_row[0]} / {candidate_row[0]}")
            matched = set(filter(None, match_row[1].split(",")))
            candidate = set(filter(None, candidate_row[1].split(",")))
            missing = matched - candidate
            if missing:
                raise ValueError(f"{match_row[0]} has non-candidate matches: {sorted(missing)[:5]}")
            checked += 1
    return checked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matching", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    print(f"PASS: {verify_subset(args.matching, args.candidate)} rows; every match is a candidate")


if __name__ == "__main__":
    main()
