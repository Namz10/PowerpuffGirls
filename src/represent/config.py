"""Relative path and artifact configuration for representation subsystem."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPRESENT_DIR_RELATIVE = Path("src") / "represent"
RESOURCE_DIR_RELATIVE = Path("artifacts") / "resources"
CANONICAL_DIR_RELATIVE = Path("artifacts") / "canonical"

NORMALIZER_VERSION = "2.0.0"


def represent_dir() -> Path:
    return REPO_ROOT / REPRESENT_DIR_RELATIVE


def resource_dir() -> Path:
    p = REPO_ROOT / RESOURCE_DIR_RELATIVE
    p.mkdir(parents=True, exist_ok=True)
    return p


def canonical_dir() -> Path:
    p = REPO_ROOT / CANONICAL_DIR_RELATIVE
    p.mkdir(parents=True, exist_ok=True)
    return p


def dataset_dir(split_name: str = "train") -> Path:
    override = os.environ.get(f"EVAL_{split_name.upper()}_DIR")
    if override:
        return Path(override)
    default_path = REPO_ROOT / ".." / "student_resource" / "dataset" / split_name
    if not default_path.exists():
        fallback = REPO_ROOT / "student_resource_datasets" / "dataset" / split_name
        if fallback.exists():
            return fallback
    return default_path
