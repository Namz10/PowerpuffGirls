"""Freeze the Phase 2 blocker and its deterministic 400k fit handoff.

Selection is permitted only from the labeled ``loop`` split.  The 400k sample
is drawn from ``fit`` and is used without labels by candidate generation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.matching.sample_fit import (
    assert_no_leak,
    assert_split_disjoint,
    draw,
    load_ids,
    load_strata,
)

from .index import sha256_file


REPO_ROOT = Path(__file__).resolve().parents[2]
SPLIT_DIR = REPO_ROOT / "src" / "eval" / "splits"
FIT_400K_SIZE = 400_000
FIT_400K_SEED = 42


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_fit_sample(
    output: Path,
    manifest_path: Path,
    source1: Path,
    truth: Path,
    fit_path: Path = SPLIT_DIR / "fit_ids.txt",
    loop_path: Path = SPLIT_DIR / "loop_ids.txt",
    report_path: Path = SPLIT_DIR / "report_ids.txt",
    total: int = FIT_400K_SIZE,
    seed: int = FIT_400K_SEED,
) -> dict[str, Any]:
    """Write a deterministic, stratified fit-only sample and its manifest."""
    fit_ids = load_ids(fit_path)
    loop_ids = load_ids(loop_path)
    report_ids = load_ids(report_path)
    assert_split_disjoint(fit_ids, loop_ids, report_ids)
    strata = load_strata(fit_ids, source1, truth)
    selected = draw(strata, total, seed)
    assert_no_leak(selected, fit_ids, loop_ids, report_ids)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(f"{entity_id}\n" for entity_id in selected), encoding="utf-8")
    selected_set = set(selected)
    stratum_counts = {
        f"{country}|{bucket}": sum(entity_id in selected_set for entity_id in ids)
        for (country, bucket), ids in sorted(strata.items())
    }
    manifest: dict[str, Any] = {
        "schema_version": "phase2-fit-sample-v1",
        "status": "frozen",
        "count": len(selected),
        "seed": seed,
        "algorithm": "largest-remainder by country x gold-list bucket, then Random(seed)",
        "strata": "country x gold-list bucket {0, 1, 2-3, 4-5, 6+}",
        "stratum_counts": stratum_counts,
        "excluded_splits": ["loop", "report"],
        "output": {"path": _relative(output), "sha256": sha256_file(output)},
        "inputs": {
            "fit_ids": {"path": _relative(fit_path), "sha256": sha256_file(fit_path)},
            "loop_ids": {"path": _relative(loop_path), "sha256": sha256_file(loop_path)},
            "report_ids": {"path": _relative(report_path), "sha256": sha256_file(report_path)},
            "source1": {"path": _relative(source1), "sha256": sha256_file(source1)},
            "truth": {"path": _relative(truth), "sha256": sha256_file(truth)},
        },
    }
    _write_json(manifest_path, manifest)
    return manifest


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def validate_loop_report(report: dict[str, Any]) -> None:
    """Refuse a freeze that was not selected exclusively on the frozen loop."""
    if report.get("selection_split") != "loop":
        raise ValueError("selection report is not marked as the frozen loop split")
    if report.get("entities") != 25_000:
        raise ValueError("selection report must cover exactly 25,000 loop entities")
    check = report.get("promotion_check", {})
    if not check.get("selected_point_on_pareto_frontier"):
        raise ValueError("selected blocker configuration is not on the Pareto frontier")
    if not check.get("bootstrap_lower_bound_above_zero"):
        raise ValueError("paired-bootstrap lower bound is not above zero")
    if not check.get("eligible"):
        raise ValueError("selection report does not mark the configuration eligible")


def build_freeze_manifest(
    loop_report_path: Path,
    fit_sample_manifest_path: Path,
    fit_report_path: Path,
    output: Path,
) -> dict[str, Any]:
    """Bind the selected loop config to the exact 400k candidate handoff."""
    loop_report = _load_json(loop_report_path)
    sample_manifest = _load_json(fit_sample_manifest_path)
    fit_report = _load_json(fit_report_path)
    validate_loop_report(loop_report)

    if sample_manifest.get("count") != FIT_400K_SIZE:
        raise ValueError("fit sample manifest must contain exactly 400,000 ids")
    if fit_report.get("entities") != FIT_400K_SIZE:
        raise ValueError("fit candidate report must cover exactly 400,000 entities")
    if fit_report.get("truth_sha256") is not None:
        raise ValueError("fit candidates must be generated without truth labels")
    if fit_report.get("config_sha256") != loop_report.get("config_sha256"):
        raise ValueError("fit candidates do not use the loop-selected blocker config")
    if fit_report.get("requested_ids_sha256") != sample_manifest["output"]["sha256"]:
        raise ValueError("fit candidate report does not match the frozen 400k sample")
    for key in ("index_sha256", "normalizer_version", "boilerplate_sha256"):
        if fit_report.get(key) != loop_report.get(key):
            raise ValueError(f"loop and fit reports disagree on {key}")

    manifest: dict[str, Any] = {
        "schema_version": "phase2-blocker-freeze-v1",
        "status": "frozen",
        "selection_split": "loop",
        "fit_truth_used": False,
        "config": loop_report["config"],
        "config_sha256": loop_report["config_sha256"],
        "normalizer_version": loop_report["normalizer_version"],
        "index_sha256": loop_report["index_sha256"],
        "boilerplate_sha256": loop_report["boilerplate_sha256"],
        "loop": {
            "entities": loop_report["entities"],
            "report_path": _relative(loop_report_path),
            "report_sha256": sha256_file(loop_report_path),
            "candidate_file_sha256": loop_report["candidate_file_sha256"],
            "misses_sha256": loop_report["misses_sha256"],
            "promotion_check": loop_report["promotion_check"],
        },
        "fit_400k": {
            "entities": fit_report["entities"],
            "sample_manifest_path": _relative(fit_sample_manifest_path),
            "sample_manifest_sha256": sha256_file(fit_sample_manifest_path),
            "ids_sha256": sample_manifest["output"]["sha256"],
            "report_path": _relative(fit_report_path),
            "report_sha256": sha256_file(fit_report_path),
            "candidate_file": fit_report["candidate_file"],
            "candidate_file_sha256": fit_report["candidate_file_sha256"],
            "provenance_sha256": fit_report["provenance_sha256"],
            "elapsed_seconds": fit_report["elapsed_seconds"],
            "peak_rss_kib": fit_report["peak_rss_kib"],
        },
    }
    _write_json(output, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("sample-fit")
    sample.add_argument("--source1", type=Path, required=True)
    sample.add_argument("--truth", type=Path, required=True)
    sample.add_argument("--output", type=Path, required=True)
    sample.add_argument("--manifest", type=Path, required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--loop-report", type=Path, required=True)
    freeze.add_argument("--fit-sample-manifest", type=Path, required=True)
    freeze.add_argument("--fit-report", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "sample-fit":
        result = build_fit_sample(args.output, args.manifest, args.source1, args.truth)
    else:
        result = build_freeze_manifest(
            args.loop_report, args.fit_sample_manifest, args.fit_report, args.output
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
