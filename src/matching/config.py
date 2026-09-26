"""Relative paths for Namita's artifacts. No absolute user paths are committed."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED = 42
FIT_SAMPLE_SIZE = 50_000
CAP = 50
CHUNK_ENTITIES = 50_000
HOLDOUT_FRACTION = 0.2

INPUT_DIR = REPO_ROOT / "artifacts" / "matching" / "inputs"
PHASE1_DIR = REPO_ROOT / "artifacts" / "matching" / "phase1"
PHASE2_DIR = REPO_ROOT / "artifacts" / "matching" / "phase2"
INDEX_PATH = REPO_ROOT / "artifacts" / "blocking" / "train_raw.sqlite"
BLOCKING_DIR = REPO_ROOT / "artifacts" / "blocking"
PHASE1_MANIFEST = REPO_ROOT / "src" / "blocking" / "phase1_manifest.json"


def train_dir() -> Path:
    """Resolve training TSVs without editing the eval path helper.

    The eval helper looks under ``student_resource``. This checkout keeps the
    official TSVs at the repository root, so that location is accepted too.
    """
    override = os.environ.get("EVAL_TRAIN_DIR")
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates.append(REPO_ROOT / ".." / "student_resource" / "dataset" / "train")
    candidates.append(REPO_ROOT / "student_resource_datasets" / "dataset" / "train")
    candidates.append(REPO_ROOT)
    for directory in candidates:
        if (directory / "train_source1.tsv").is_file():
            return directory
    raise FileNotFoundError("train_source1.tsv was not found")
