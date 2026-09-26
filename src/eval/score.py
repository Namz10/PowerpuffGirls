"""Official macro F0.5. Standard library only. No sklearn."""

import math
from pathlib import Path

MATCHING_HEADER = ["source1_entity_id", "matched_entity_ids"]
CANDIDATE_HEADER = ["source1_entity_id", "candidate_entity_ids"]


def entity_f05(predicted: set[str], truth: set[str]) -> float:
    """Per-Source-1 F0.5. Empty/empty is 1. One empty side, or a disjoint pair, is 0."""
    if not predicted and not truth:
        return 1.0
    if not predicted or not truth:
        return 0.0
    overlap = len(predicted & truth)
    if overlap == 0:
        return 0.0
    precision = overlap / len(predicted)
    recall = overlap / len(truth)
    score = (1.25 * precision * recall) / (0.25 * precision + recall)
    if not math.isfinite(score):
        raise ValueError("F0.5 is not finite")
    return score


def macro_f05(predicted: dict[str, set[str]], truth: dict[str, set[str]]) -> float:
    """Unweighted mean of per-entity F0.5. Entity order does not change the result."""
    if set(predicted) != set(truth):
        raise ValueError("prediction ids and truth ids differ")
    if not truth:
        raise ValueError("no entities")
    total = math.fsum(entity_f05(predicted[entity_id], truth[entity_id]) for entity_id in sorted(truth))
    score = total / len(truth)
    if not math.isfinite(score):
        raise ValueError("macro F0.5 is not finite")
    return score


def parse_id_list(field: str) -> set[str]:
    text = field.strip()
    if not text:
        return set()
    ids = text.split(",")
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("id list has a duplicate or an empty token")
    for item in ids:
        if not item.startswith(("S2-", "S3-")):
            raise ValueError(f"id is not S2- or S3-: {item}")
    return set(ids)


def load_id_lists(path: Path, expected_header: list[str]) -> dict[str, set[str]]:
    """Read a matching or candidate TSV. One row per Source 1 id. Empty lists are valid."""
    rows: dict[str, set[str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        header_line = handle.readline()
        if not header_line or "\t" not in header_line:
            raise ValueError(f"{path.name} is not tab-separated")
        header = [column.strip().lower() for column in header_line.rstrip("\n").split("\t")]
        if header != expected_header:
            raise ValueError(f"{path.name} header {header} != {expected_header}")
        value_column = expected_header[1]
        for line_number, line in enumerate(handle, start=2):
            if not line.strip():
                continue
            source_id, separator, rest = line.rstrip("\n").partition("\t")
            if not separator:
                raise ValueError(f"{path.name}:{line_number} has no tab")
            if "\t" in rest:
                raise ValueError(f"{path.name}:{line_number} has more than two columns")
            if not source_id.startswith("S1-"):
                raise ValueError(f"{path.name}:{line_number} source id is not S1-")
            if source_id in rows:
                raise ValueError(f"duplicate source id {source_id}")
            try:
                rows[source_id] = parse_id_list(rest)
            except ValueError as exc:
                raise ValueError(f"{path.name}:{line_number} {value_column}: {exc}") from exc
    return rows


def score_files(matching_path: Path, gold_path: Path) -> float:
    predicted = load_id_lists(matching_path, MATCHING_HEADER)
    truth = load_id_lists(gold_path, MATCHING_HEADER)
    return macro_f05(predicted, truth)


def predict_nothing_score(gold_path: Path) -> float:
    truth = load_id_lists(gold_path, MATCHING_HEADER)
    predicted = {entity_id: set() for entity_id in truth}
    return macro_f05(predicted, truth)


def main() -> None:
    import argparse

    from src.eval.config import train_dir

    parser = argparse.ArgumentParser(description="Macro F0.5 scorer")
    parser.add_argument("--matching", type=Path)
    parser.add_argument("--gold", type=Path)
    parser.add_argument("--predict-nothing", action="store_true")
    args = parser.parse_args()
    if args.predict_nothing:
        gold = args.gold or (train_dir() / "train_ground_truth.tsv")
        print(f"{predict_nothing_score(gold):.16f}")
        return
    if args.matching is None or args.gold is None:
        raise SystemExit("pass --matching and --gold, or --predict-nothing")
    print(f"{score_files(args.matching, args.gold):.16f}")


if __name__ == "__main__":
    main()
