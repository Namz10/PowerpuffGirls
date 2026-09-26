"""Read candidate groups and the raw rows they point at."""

from __future__ import annotations

import csv
from pathlib import Path

CANDIDATE_HEADER = ["source1_entity_id", "candidate_entity_ids"]
PROVENANCE_HEADER = [
    "source1_entity_id",
    "candidate_entity_id",
    "target_source",
    "provenance",
    "rank",
    "exact_name",
    "exact_address",
    "name_token",
    "address_token",
    "retrieval_score",
]
SOURCE_HEADER = ["entity_id", "business_name", "business_address", "country"]


def parse_id_list(field: str) -> list[str]:
    text = field.strip()
    if not text:
        return []
    ids = text.split(",")
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("candidate list has a duplicate or an empty token")
    return ids


def iter_groups(candidate_path: Path, provenance_path: Path):
    """Yield ``(s1, candidate ids, provenance rows)`` in candidate-file order."""
    with candidate_path.open(encoding="utf-8", newline="") as candidates, provenance_path.open(
        encoding="utf-8", newline=""
    ) as provenance:
        candidate_reader = csv.reader(candidates, delimiter="\t")
        provenance_reader = csv.reader(provenance, delimiter="\t")
        if next(candidate_reader) != CANDIDATE_HEADER:
            raise ValueError(f"unexpected candidate header in {candidate_path}")
        if next(provenance_reader) != PROVENANCE_HEADER:
            raise ValueError(f"unexpected provenance header in {provenance_path}")
        for row in candidate_reader:
            if len(row) != 2:
                raise ValueError("candidate row does not have two columns")
            source_id, ids = row[0], parse_id_list(row[1])
            rows = []
            for candidate_id in ids:
                prov = next(provenance_reader, None)
                if prov is None:
                    raise ValueError(f"provenance ended before {source_id}")
                mapped = dict(zip(PROVENANCE_HEADER, prov))
                if mapped["source1_entity_id"] != source_id or mapped["candidate_entity_id"] != candidate_id:
                    raise ValueError(f"provenance does not follow candidate order at {source_id}")
                rows.append(mapped)
            yield source_id, ids, rows
        extra = next(provenance_reader, None)
        if extra is not None:
            raise ValueError("provenance has rows past the candidate file")


def load_entities(paths: list[Path], needed: set[str]) -> dict[str, tuple[str, str, str]]:
    """Return ``entity_id -> (name, address, country)`` for ``needed`` ids."""
    found: dict[str, tuple[str, str, str]] = {}
    remaining = set(needed)
    for path in paths:
        if not remaining:
            break
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if reader.fieldnames != SOURCE_HEADER:
                raise ValueError(f"unexpected source header in {path}: {reader.fieldnames}")
            for row in reader:
                entity_id = row["entity_id"]
                if entity_id in remaining:
                    found[entity_id] = (
                        row["business_name"],
                        row["business_address"],
                        row["country"].strip(),
                    )
                    remaining.remove(entity_id)
                    if not remaining:
                        break
    if remaining:
        raise ValueError(f"{len(remaining)} entity ids were not found in {paths}")
    return found


def load_gold(path: Path, needed: set[str]) -> dict[str, set[str]]:
    gold: dict[str, set[str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        if header != ["source1_entity_id", "matched_entity_ids"]:
            raise ValueError(f"unexpected gold header: {header}")
        for row in reader:
            if not row or row[0] not in needed:
                continue
            text = row[1].strip() if len(row) > 1 else ""
            gold[row[0]] = set(text.split(",")) if text else set()
    missing = needed - set(gold)
    if missing:
        raise ValueError(f"gold is missing {len(missing)} requested ids")
    return gold


def collect_ids(candidate_path: Path, provenance_path: Path) -> tuple[set[str], set[str]]:
    sources: set[str] = set()
    candidates: set[str] = set()
    for source_id, ids, _rows in iter_groups(candidate_path, provenance_path):
        sources.add(source_id)
        candidates.update(ids)
    return sources, candidates
