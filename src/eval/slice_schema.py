"""Slice schema — Person 1 Phase 1.

This publishes the *definitions* of the evaluation slice tags, not populated
per-slice performance (that is Phase 2/3: final_build_plan.md lines 73, 98, 111).
The schema exists so later evaluation reports and Person 3's `person1_slice_tags`
column (build_plan_person3.md line 287) reference the same tags without redefining
them.

Every slice is traceable to an authoritative source:
- consolidated plan section 3 (the "Slices:" sentence);
- build_plan_person1.md "Slices that choose the next experiment" (lines 199-221).

`phase_available` records when a slice can actually be populated:
- "phase1": computable now from the training files (country, gold length, target
  empty address, source composition). Parameterized name slices are phase1 in
  intent but their cutoffs are frozen separately on `fit` and are not yet frozen
  (marked `frozen: false`), so they are declared, not resolved here.
- "after_gold_join": needs the Unicode-block gold join (Phase 2).
- "prediction_time": needs a match file to exist.
"""

import hashlib
import json
from pathlib import Path

from src.eval.config import BUCKETS, slice_schema_path

SCHEMA_VERSION = "1.0"

# Ordered list of slice definitions. Order is fixed for deterministic output.
_SLICES = [
    {
        "key": "country",
        "description": "Country label of the Source 1 entity. Open set of strings; never a {US, India} whitelist.",
        "level": "entity",
        "phase_available": "phase1",
        "value_type": "categorical",
        "categories": ["US", "India", "France", "OTHER"],
        "open_set": True,
        "source_fields": ["source1.country"],
        "parameters": {},
    },
    {
        "key": "singleton",
        "description": "Gold match list is empty.",
        "level": "entity",
        "phase_available": "phase1",
        "value_type": "boolean",
        "categories": [],
        "open_set": False,
        "source_fields": ["ground_truth.matched_entity_ids"],
        "parameters": {},
    },
    {
        "key": "gold_list_bucket",
        "description": "Gold match-list length bucket. Length 11 folds into 6+.",
        "level": "entity",
        "phase_available": "phase1",
        "value_type": "categorical",
        "categories": list(BUCKETS),
        "open_set": False,
        "source_fields": ["ground_truth.matched_entity_ids"],
        "parameters": {},
    },
    {
        "key": "target_empty_address",
        "description": "At least one gold S2/S3 match has an empty business_address. Source 1 addresses are never empty.",
        "level": "entity",
        "phase_available": "phase1",
        "value_type": "boolean",
        "categories": [],
        "open_set": False,
        "source_fields": ["ground_truth.matched_entity_ids", "source2.business_address", "source3.business_address"],
        "parameters": {},
    },
    {
        "key": "source_composition",
        "description": "Which sources the gold list draws from.",
        "level": "entity",
        "phase_available": "phase1",
        "value_type": "categorical",
        "categories": ["none", "s2_only", "s3_only", "both"],
        "open_set": False,
        "source_fields": ["ground_truth.matched_entity_ids"],
        "parameters": {},
    },
    {
        "key": "short_name",
        "description": "Source 1 name is short. Cutoff frozen on fit character length and token count; not yet frozen.",
        "level": "entity",
        "phase_available": "phase1",
        "value_type": "boolean",
        "categories": [],
        "open_set": False,
        "source_fields": ["source1.business_name"],
        "parameters": {"max_chars": None, "max_tokens": None, "frozen": False, "frozen_on": "fit"},
    },
    {
        "key": "generic_name",
        "description": "Source 1 name tokens are all boilerplate or very high document frequency. DF measured on fit text only; not yet frozen.",
        "level": "entity",
        "phase_available": "phase1",
        "value_type": "boolean",
        "categories": [],
        "open_set": False,
        "source_fields": ["source1.business_name"],
        "parameters": {"df_source": "fit", "frozen": False, "frozen_on": "fit"},
    },
    {
        "key": "target_script_class",
        "description": "Script of the true S2/S3 target name against the always-Latin Source 1 name. Indic is separate from accented Latin.",
        "level": "entity",
        "phase_available": "after_gold_join",
        "value_type": "categorical",
        "categories": ["latin", "accented_latin", "indic"],
        "open_set": False,
        "source_fields": ["source2.business_name", "source3.business_name"],
        "parameters": {},
    },
    {
        "key": "cross_country_prediction",
        "description": "A predicted match whose country differs from the Source 1 country.",
        "level": "prediction",
        "phase_available": "prediction_time",
        "value_type": "boolean",
        "categories": [],
        "open_set": False,
        "source_fields": ["matching_results.matched_entity_ids"],
        "parameters": {},
    },
    {
        "key": "false_id_type",
        "description": "For a predicted false id: stolen (gold for a different Source 1) vs unmatched distractor (gold for nobody).",
        "level": "prediction",
        "phase_available": "prediction_time",
        "value_type": "categorical",
        "categories": ["stolen_id", "unmatched_distractor"],
        "open_set": False,
        "source_fields": ["matching_results.matched_entity_ids", "ground_truth.matched_entity_ids"],
        "parameters": {},
    },
    {
        "key": "predicted_vs_gold_length",
        "description": "Predicted list length relative to the gold list.",
        "level": "prediction",
        "phase_available": "prediction_time",
        "value_type": "categorical",
        "categories": ["longer", "equal", "shorter"],
        "open_set": False,
        "source_fields": ["matching_results.matched_entity_ids", "ground_truth.matched_entity_ids"],
        "parameters": {},
    },
]

VALID_LEVELS = {"entity", "prediction"}
VALID_PHASES = {"phase1", "after_gold_join", "prediction_time"}
VALID_VALUE_TYPES = {"categorical", "boolean"}


def schema() -> dict:
    return {"schema_version": SCHEMA_VERSION, "slices": _SLICES}


def validate(document: dict) -> None:
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version mismatch")
    slices = document.get("slices")
    if not isinstance(slices, list) or not slices:
        raise ValueError("slices must be a non-empty list")
    seen = set()
    required = {"key", "description", "level", "phase_available", "value_type", "categories", "open_set", "source_fields", "parameters"}
    for entry in slices:
        missing = required - entry.keys()
        if missing:
            raise ValueError(f"slice {entry.get('key')!r} missing fields {sorted(missing)}")
        if entry["key"] in seen:
            raise ValueError(f"duplicate slice key {entry['key']!r}")
        seen.add(entry["key"])
        if entry["level"] not in VALID_LEVELS:
            raise ValueError(f"{entry['key']}: bad level {entry['level']!r}")
        if entry["phase_available"] not in VALID_PHASES:
            raise ValueError(f"{entry['key']}: bad phase {entry['phase_available']!r}")
        if entry["value_type"] not in VALID_VALUE_TYPES:
            raise ValueError(f"{entry['key']}: bad value_type {entry['value_type']!r}")
        if not isinstance(entry["categories"], list):
            raise ValueError(f"{entry['key']}: categories must be a list")
        if entry["value_type"] == "boolean" and entry["categories"]:
            raise ValueError(f"{entry['key']}: boolean slice must have empty categories")
        if entry["value_type"] == "categorical" and not entry["categories"] and not entry["open_set"]:
            raise ValueError(f"{entry['key']}: categorical slice needs categories or open_set")
        if not isinstance(entry["source_fields"], list) or not entry["source_fields"]:
            raise ValueError(f"{entry['key']}: source_fields must be a non-empty list")


def canonical_bytes() -> bytes:
    document = schema()
    validate(document)
    return (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write() -> str:
    payload = canonical_bytes()
    path = slice_schema_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return sha256_bytes(payload)


def main() -> None:
    digest = write()
    print(f"WROTE {slice_schema_path().name} sha256={digest} slices={len(_SLICES)}")


if __name__ == "__main__":
    main()
