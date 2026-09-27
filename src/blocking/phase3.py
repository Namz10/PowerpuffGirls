"""Guarded Phase 3 candidate handoffs for the frozen Phase 2 blocker.

This module deliberately has two separate operations.  ``reproduce_loop``
proves that the selected blocker still emits the frozen, labeled-loop files.
``generate_locked_report`` emits the untouched report split only after the
matcher has supplied a valid locked decision configuration.  Neither operation
selects a retrieval setting or consumes report truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.matching.decision_config import validate_config

from .index import sha256_file
from .phase2 import Phase2Config, generate_phase2, write_json


REPO_ROOT = Path(__file__).resolve().parents[2]
PROOF_SCHEMA_VERSION = "phase3-blocker-reproduction-v1"
REPORT_MANIFEST_SCHEMA_VERSION = "phase3-locked-report-candidates-v1"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON artifact {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact {path} must be an object")
    return value


def _artifact_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _config_sha256(config: Mapping[str, object]) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(dict(config), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _ids_sha256(ids: set[str]) -> str:
    import hashlib

    digest = hashlib.sha256()
    for entity_id in sorted(ids):
        digest.update(entity_id.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def load_frozen_blocker(path: Path) -> dict[str, Any]:
    """Load and validate the minimum immutable Phase 2 blocker contract."""
    freeze = _load_json(path)
    if freeze.get("schema_version") != "phase2-blocker-freeze-v1" or freeze.get("status") != "frozen":
        raise ValueError("Phase 3 requires a frozen phase2-blocker-freeze-v1 manifest")
    if freeze.get("selection_split") != "loop":
        raise ValueError("frozen blocker was not selected on the loop split")
    config = freeze.get("config")
    if not isinstance(config, dict) or _config_sha256(config) != freeze.get("config_sha256"):
        raise ValueError("frozen blocker config hash does not match its body")
    try:
        Phase2Config(**config)
    except TypeError as error:
        raise ValueError("frozen blocker config is not a Phase2Config") from error
    loop = freeze.get("loop")
    fit = freeze.get("fit_400k")
    if not isinstance(loop, dict) or loop.get("entities") != 25_000 or not loop.get("report_path"):
        raise ValueError("frozen blocker lacks the 25k loop evidence")
    if not isinstance(fit, dict) or fit.get("entities") != 400_000 or not fit.get("candidate_file_sha256"):
        raise ValueError("frozen blocker lacks the 400k fit handoff")
    for key in ("index_sha256", "boilerplate_sha256", "normalizer_version"):
        if not freeze.get(key):
            raise ValueError(f"frozen blocker is missing {key}")
    return freeze


def _verify_retrieval_inputs(
    freeze: Mapping[str, Any], index_path: Path, resources_path: Path
) -> None:
    if sha256_file(index_path) != freeze["index_sha256"]:
        raise ValueError("index hash differs from the frozen Phase 2 blocker")
    boilerplate = resources_path / "boilerplate_tokens.json"
    if sha256_file(boilerplate) != freeze["boilerplate_sha256"]:
        raise ValueError("boilerplate token resource differs from the frozen Phase 2 blocker")


def _phase2_config(freeze: Mapping[str, Any]) -> Phase2Config:
    return Phase2Config(**freeze["config"])


def _expected_loop_hashes(freeze: Mapping[str, Any]) -> dict[str, str]:
    loop_report_path = _artifact_path(freeze["loop"]["report_path"])
    expected_report_sha = freeze["loop"].get("report_sha256")
    if expected_report_sha and sha256_file(loop_report_path) != expected_report_sha:
        raise ValueError("frozen loop report hash differs from the Phase 2 freeze manifest")
    loop_report = _load_json(loop_report_path)
    expected = {
        "candidate_file_sha256": freeze["loop"].get("candidate_file_sha256"),
        "provenance_sha256": loop_report.get("provenance_sha256"),
        "misses_sha256": freeze["loop"].get("misses_sha256"),
        "requested_ids_sha256": loop_report.get("requested_ids_sha256"),
    }
    if not all(expected.values()):
        raise ValueError("frozen loop evidence lacks candidate, provenance, or miss fingerprints")
    return expected  # type: ignore[return-value]


def verify_loop_outputs(
    *, freeze_path: Path, index_path: Path, source1_path: Path,
    loop_ids_path: Path, resources_path: Path, output_path: Path,
    provenance_path: Path, misses_path: Path, report_path: Path,
    proof_path: Path,
) -> dict[str, Any]:
    """Verify an already-completed loop replay and write its proof."""
    from .generate import load_requested_ids

    freeze = load_frozen_blocker(freeze_path)
    _verify_retrieval_inputs(freeze, index_path, resources_path)
    requested = load_requested_ids(loop_ids_path)
    generated = _load_json(report_path)
    expected = _expected_loop_hashes(freeze)
    actual = {
        "candidate_file_sha256": sha256_file(output_path),
        "provenance_sha256": sha256_file(provenance_path),
        "misses_sha256": sha256_file(misses_path),
        "requested_ids_sha256": _ids_sha256(requested),
    }
    if len(requested) != 25_000 or generated.get("entities") != 25_000:
        raise ValueError("loop proof requires exactly 25,000 generated entities")
    for key, value in actual.items():
        if generated.get(key) != value:
            raise ValueError(f"generated loop report disagrees with {key}")
    for key in ("config_sha256", "index_sha256", "source1_sha256", "truth_sha256"):
        frozen_report = _load_json(_artifact_path(freeze["loop"]["report_path"]))
        if generated.get(key) != frozen_report.get(key):
            raise ValueError(f"generated loop report disagrees with frozen {key}")
    mismatches = {
        key: {"expected": expected[key], "actual": actual[key]}
        for key in expected if expected[key] != actual[key]
    }
    if mismatches:
        raise ValueError(f"loop reproduction is not byte-identical: {mismatches}")
    proof = {
        "schema_version": PROOF_SCHEMA_VERSION, "status": "passed",
        "freeze_manifest": str(freeze_path),
        "freeze_manifest_sha256": sha256_file(freeze_path),
        "index_sha256": sha256_file(index_path),
        "source1_sha256": sha256_file(source1_path),
        "loop_ids_sha256": actual["requested_ids_sha256"],
        "normalizer_version": freeze["normalizer_version"],
        "config_sha256": freeze["config_sha256"],
        "expected": expected, "actual": actual,
        "outputs": {"candidates": str(output_path), "provenance": str(provenance_path),
                    "misses": str(misses_path), "report": str(report_path)},
    }
    write_json(proof, proof_path)
    return proof


def reproduce_loop(
    *,
    freeze_path: Path,
    index_path: Path,
    source1_path: Path,
    loop_ids_path: Path,
    truth_path: Path,
    resources_path: Path,
    output_path: Path,
    provenance_path: Path,
    misses_path: Path,
    report_path: Path,
    proof_path: Path,
    workers: int = 1,
) -> dict[str, Any]:
    """Regenerate loop artifacts and write a pass-only reproducibility proof."""
    from .generate import load_requested_ids
    from .phase2 import load_truth

    freeze = load_frozen_blocker(freeze_path)
    _verify_retrieval_inputs(freeze, index_path, resources_path)
    requested = load_requested_ids(loop_ids_path)
    if len(requested) != 25_000:
        raise ValueError("Phase 3 loop reproduction requires exactly 25,000 loop ids")
    expected = _expected_loop_hashes(freeze)
    if _ids_sha256(requested) != expected["requested_ids_sha256"]:
        raise ValueError("loop ids differ from the frozen Phase 2 loop evidence")
    truth = load_truth(truth_path, requested)
    # Sweeps were Phase 2 selection evidence.  They cannot alter the frozen
    # selected candidate row, provenance, or miss audit, so rerunning them in
    # Phase 3 would only add runtime and new non-frozen diagnostics.
    generated = generate_phase2(
        index_path, source1_path, output_path, _phase2_config(freeze), requested, truth,
        provenance_path, misses_path, (), (), resources_path, workers,
    )
    generated["purpose"] = "phase3_loop_reproduction"
    write_json(generated, report_path)
    return verify_loop_outputs(
        freeze_path=freeze_path, index_path=index_path, source1_path=source1_path,
        loop_ids_path=loop_ids_path, resources_path=resources_path,
        output_path=output_path, provenance_path=provenance_path,
        misses_path=misses_path, report_path=report_path, proof_path=proof_path,
    )


def generate_locked_report(
    *,
    freeze_path: Path,
    decision_config_path: Path,
    index_path: Path,
    source1_path: Path,
    report_ids_path: Path,
    resources_path: Path,
    output_path: Path,
    provenance_path: Path,
    report_path: Path,
    manifest_path: Path,
    workers: int = 1,
) -> dict[str, Any]:
    """Create report candidates only when Namita's config is genuinely locked."""
    from .generate import load_requested_ids

    freeze = load_frozen_blocker(freeze_path)
    _verify_retrieval_inputs(freeze, index_path, resources_path)
    decision = _load_json(decision_config_path)
    validate_config(decision)
    if decision.get("status") != "locked":
        raise ValueError("report candidates require Namita's locked Phase 3 decision config")
    fit = freeze["fit_400k"]
    if decision.get("fit_400k_candidate_sha256") != fit["candidate_file_sha256"]:
        raise ValueError("locked decision config is not bound to this frozen 400k candidate handoff")
    if decision.get("fit_400k_entity_count") != fit["entities"]:
        raise ValueError("locked decision config is not bound to 400,000 fit entities")
    requested = load_requested_ids(report_ids_path)
    if not requested:
        raise ValueError("report id file is empty")
    from src.eval.config import split_dir

    official_report_ids = load_requested_ids(split_dir() / "report_ids.txt")
    if requested != official_report_ids:
        raise ValueError("Phase 3 report generation requires the frozen report id split")
    generated = generate_phase2(
        index_path, source1_path, output_path, _phase2_config(freeze), requested, None,
        provenance_path, None, (), (), resources_path, workers,
    )
    generated.update({
        "provisional": False,
        "phase": 3,
        "purpose": "locked_report_candidates",
        "blocker_freeze_sha256": sha256_file(freeze_path),
        "decision_config_sha256": decision["sha256"],
        "decision_config_path": str(decision_config_path),
    })
    write_json(generated, report_path)
    manifest = {
        "schema_version": REPORT_MANIFEST_SCHEMA_VERSION,
        "status": "locked",
        "blocker_freeze_sha256": sha256_file(freeze_path),
        "blocker_config_sha256": freeze["config_sha256"],
        "decision_config_sha256": decision["sha256"],
        "fit_400k_candidate_sha256": fit["candidate_file_sha256"],
        "report_ids_sha256": generated["requested_ids_sha256"],
        "entities": generated["entities"],
        "candidate_file": str(output_path),
        "candidate_file_sha256": generated["candidate_file_sha256"],
        "provenance_file": str(provenance_path),
        "provenance_sha256": generated["provenance_sha256"],
        "report_path": str(report_path),
    }
    write_json(manifest, manifest_path)
    return manifest
