"""Hashed Phase 3 decision config. Status stays skeleton until the 400k file exists."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.matching.config import SEED
from src.matching.features_v2 import schema_sha256

UNIQUENESS_NOTE = (
    "Train Source 2/3 uniqueness is proven on the training gold. "
    "Test and France uniqueness is an assumption, not a measured fact."
)
LICENSE_NOTE = (
    "LightGBM is MIT. scikit-learn is BSD-3. RapidFuzz and jellyfish are MIT. "
    "No submitted model exceeds 8 billion parameters. No external lookup."
)
PHASE1_THRESHOLD = 0.58


def skeleton_config() -> dict[str, Any]:
    document = {
        "status": "skeleton",
        "fold_count": 5,
        "seed": SEED,
        "feature_schema_sha256": schema_sha256(),
        "calibrator": "unselected",
        "one_owner": None,
        "rule_family": "unselected",
        "threshold": None,
        "t_s2": None,
        "t_s3": None,
        "k_by_bucket": None,
        "fit_400k_candidate_sha256": None,
        "fit_400k_entity_count": None,
        "phase1_provisional_threshold_unchanged": PHASE1_THRESHOLD,
        "uniqueness_note": UNIQUENESS_NOTE,
        "license_note": LICENSE_NOTE,
    }
    document["sha256"] = config_sha256(document)
    return document


def config_sha256(document: dict[str, Any]) -> str:
    payload = {key: value for key, value in document.items() if key != "sha256"}
    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_config(document: dict[str, Any]) -> None:
    if document.get("status") not in {"skeleton", "locked"}:
        raise ValueError("decision config status must be skeleton or locked")
    if document.get("status") == "locked":
        fingerprint = document.get("fit_400k_candidate_sha256")
        if not fingerprint or document.get("fit_400k_entity_count") != 400_000:
            raise ValueError("status locked requires the frozen 400k fit candidate fingerprint")
    if document.get("phase1_provisional_threshold_unchanged") != PHASE1_THRESHOLD:
        raise ValueError("this skeleton must not retune the Phase 1 threshold")
    if "sha256" in document and document["sha256"] != config_sha256(document):
        raise ValueError("decision config hash does not match its body")
