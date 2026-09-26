"""Phase 2 capacity on one real 50k-entity chunk. Does not retune the threshold."""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path

from src.eval.fingerprint import sha256_file
from src.matching.config import PHASE2_DIR, REPO_ROOT
from src.matching.features_v2 import phase2_feature_row, schema_bytes, schema_sha256
from src.represent.canonical_record import transform_single_record
from src.represent.config import NORMALIZER_VERSION, resource_dir
from src.represent.token_resource import TokenResource


def _canonical_cache(entities: dict[str, tuple[str, str, str]]):
    cache = {}
    for entity_id, (name, address, country) in entities.items():
        cache[entity_id] = transform_single_record(entity_id, name, address, country)
    return cache


def measure_chunk(groups, entities) -> dict:
    token_resource = TokenResource.load(resource_dir())
    tracemalloc.start()
    started = time.perf_counter()
    records = _canonical_cache(entities)
    rows = 0
    for source_id, candidate_ids, _provenance in groups:
        source = records[source_id]
        for candidate_id in candidate_ids:
            phase2_feature_row(source, records[candidate_id], token_resource)
            rows += 1
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    entities_n = len(groups)
    return {
        "entities": entities_n,
        "pair_rows": rows,
        "elapsed_seconds": round(elapsed, 3),
        "peak_traced_bytes": peak,
        "seconds_per_entity": round(elapsed / entities_n, 6) if entities_n else None,
    }


def write_schema(path: Path | None = None) -> Path:
    path = path or (PHASE2_DIR / "feature_schema.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(schema_bytes())
    return path


def write_capacity(
    measurement: dict,
    phase1_inference_seconds: float | None,
    phase1_entities: int,
    test_entities: int,
) -> Path:
    schema_path = write_schema()
    ratio = None
    if phase1_inference_seconds and phase1_entities and measurement["entities"]:
        phase1_per_entity = phase1_inference_seconds / phase1_entities
        ratio = measurement["seconds_per_entity"] / phase1_per_entity if phase1_per_entity else None
    projected = None
    if measurement["seconds_per_entity"] is not None and test_entities:
        projected = round(measurement["seconds_per_entity"] * test_entities, 1)
    resources = resource_dir()
    manifest = {
        "schema_version": "phase2-v1",
        "schema_sha256": schema_sha256(),
        "schema_path": "artifacts/matching/phase2/feature_schema.json",
        "normalizer_version": NORMALIZER_VERSION,
        "resource_hashes": {
            "name_idf": sha256_file(resources / "name_idf.json"),
            "address_idf": sha256_file(resources / "address_idf.json"),
            "boilerplate_tokens": sha256_file(resources / "boilerplate_tokens.json"),
        },
        "threshold_retuned": False,
        "measurement": measurement,
        "phase1_inference_seconds": phase1_inference_seconds,
        "phase2_seconds_per_entity_over_phase1": None if ratio is None else round(ratio, 3),
        "projected_full_test_feature_seconds": projected,
        "note": (
            "Feature schema only. phase1_provisional_threshold is unchanged. "
            "This is not Srishti's frozen Phase 2 blocker and not the 400k fit candidate file."
        ),
    }
    PHASE2_DIR.mkdir(parents=True, exist_ok=True)
    if schema_path.read_bytes() != schema_bytes():
        raise ValueError("written schema bytes do not match the hashed document")
    path = PHASE2_DIR / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def count_data_rows(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        next(handle, None)
        return sum(1 for line in handle if line.strip())


def test_source1_count() -> int:
    path = REPO_ROOT / "test_source1.tsv"
    if not path.is_file():
        raise FileNotFoundError(path)
    return count_data_rows(path)
