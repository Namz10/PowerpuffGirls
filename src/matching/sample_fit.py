"""Draw the 50,000-id fit training sample. Never touches loop or report."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from src.eval.split_protocol import stratum_key
from src.matching.config import FIT_SAMPLE_SIZE, INPUT_DIR, REPO_ROOT, SEED, train_dir

SPLIT_DIR = REPO_ROOT / "src" / "eval" / "splits"


def load_ids(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def assert_split_disjoint(fit_ids: set[str], loop_ids: set[str], report_ids: set[str]) -> None:
    leaked = (fit_ids & loop_ids) | (fit_ids & report_ids) | (loop_ids & report_ids)
    if leaked:
        raise ValueError(f"frozen split ids overlap; refusing to sample ({len(leaked)} ids)")


def allocate(sizes: dict[tuple[str, str], int], total: int) -> dict[tuple[str, str], int]:
    """Largest-remainder allocation. No stratum is asked for more ids than it has."""
    if total < 0:
        raise ValueError("sample size must be non-negative")
    grand = sum(sizes.values())
    if total > grand:
        raise ValueError(f"sample size {total} exceeds fit ids {grand}")
    if total == 0 or grand == 0:
        return {key: 0 for key in sizes}
    keys = sorted(sizes)
    counts = {key: (total * sizes[key]) // grand for key in keys}
    remainder = {key: (total * sizes[key]) % grand for key in keys}
    leftover = total - sum(counts.values())
    winners = sorted(keys, key=lambda key: (-remainder[key], key[0], key[1]))
    for key in winners[:leftover]:
        counts[key] += 1
    if sum(counts.values()) != total:
        raise ValueError("allocation does not sum to the sample size")
    return counts


def draw(strata: dict[tuple[str, str], list[str]], total: int, seed: int = SEED) -> list[str]:
    """One Random(seed) walk over sorted strata. Returned ids are sorted."""
    counts = allocate({key: len(ids) for key, ids in strata.items()}, total)
    rng = random.Random(seed)
    chosen: list[str] = []
    for key in sorted(strata):
        ids = sorted(strata[key])
        rng.shuffle(ids)
        take = counts[key]
        if take > len(ids):
            raise ValueError(f"stratum {key} cannot supply {take} ids")
        chosen.extend(ids[:take])
    if len(chosen) != len(set(chosen)):
        raise ValueError("sample drew a duplicate id")
    return sorted(chosen)


def assert_no_leak(chosen: list[str], fit_ids: set[str], loop_ids: set[str], report_ids: set[str]) -> None:
    chosen_set = set(chosen)
    if not chosen_set <= fit_ids:
        raise ValueError("sample contains an id outside fit")
    leaked = chosen_set & (loop_ids | report_ids)
    if leaked:
        raise ValueError(f"sample contains {len(leaked)} loop or report ids")


def _list_length(field: str) -> int:
    text = field.strip()
    if not text:
        return 0
    return text.count(",") + 1


def load_strata(fit_ids: set[str], source1: Path, gold: Path) -> dict[tuple[str, str], list[str]]:
    lengths: dict[str, int] = {}
    with gold.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        if header != ["source1_entity_id", "matched_entity_ids"]:
            raise ValueError(f"unexpected gold header: {header}")
        for row in reader:
            if row and row[0] in fit_ids:
                lengths[row[0]] = _list_length(row[1] if len(row) > 1 else "")
    missing = fit_ids - set(lengths)
    if missing:
        raise ValueError(f"gold is missing {len(missing)} fit ids")
    strata: dict[tuple[str, str], list[str]] = defaultdict(list)
    seen: set[str] = set()
    with source1.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["entity_id", "business_name", "business_address", "country"]:
            raise ValueError(f"unexpected source1 header: {reader.fieldnames}")
        for row in reader:
            entity_id = row["entity_id"]
            if entity_id in fit_ids:
                strata[stratum_key(row["country"].strip(), lengths[entity_id])].append(entity_id)
                seen.add(entity_id)
    if seen != fit_ids:
        raise ValueError(f"source1 is missing {len(fit_ids - seen)} fit ids")
    return strata


def write_sample(
    output: Path,
    total: int = FIT_SAMPLE_SIZE,
    seed: int = SEED,
    fit_path: Path | None = None,
    loop_path: Path | None = None,
    report_path: Path | None = None,
    source1: Path | None = None,
    gold: Path | None = None,
) -> list[str]:
    fit_path = fit_path or (SPLIT_DIR / "fit_ids.txt")
    loop_path = loop_path or (SPLIT_DIR / "loop_ids.txt")
    report_path = report_path or (SPLIT_DIR / "report_ids.txt")
    data = train_dir()
    source1 = source1 or (data / "train_source1.tsv")
    gold = gold or (data / "train_ground_truth.tsv")
    fit_ids = load_ids(fit_path)
    loop_ids = load_ids(loop_path)
    report_ids = load_ids(report_path)
    assert_split_disjoint(fit_ids, loop_ids, report_ids)
    chosen = draw(load_strata(fit_ids, source1, gold), total, seed)
    assert_no_leak(chosen, fit_ids, loop_ids, report_ids)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(f"{entity_id}\n" for entity_id in chosen), encoding="utf-8")
    meta = {
        "count": len(chosen),
        "seed": seed,
        "strata": "country x gold-list bucket {0, 1, 2-3, 4-5, 6+}",
        "excluded": ["loop", "report"],
        "path": str(output.relative_to(REPO_ROOT)).replace("\\", "/"),
    }
    output.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=INPUT_DIR / "fit50k_ids.txt")
    args = parser.parse_args()
    chosen = write_sample(args.output)
    print(f"wrote {len(chosen)} fit ids to {args.output}")


if __name__ == "__main__":
    main()
