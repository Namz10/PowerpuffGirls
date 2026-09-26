"""Relative paths. No absolute user paths are committed."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAIN_DIR_RELATIVE = Path("..") / "student_resource" / "dataset" / "train"
SPLIT_DIR_RELATIVE = Path("src") / "eval" / "splits"
SPLIT_MD_RELATIVE = Path("src") / "eval" / "SPLIT.md"
PACK_DIR_RELATIVE = Path("src") / "eval" / "difficulty_pack"
SLICE_SCHEMA_RELATIVE = Path("src") / "eval" / "slice_schema.json"

SEED = 42
LOOP_SIZE = 25_000
REPORT_PERCENT = 10
BUCKETS = ("0", "1", "2-3", "4-5", "6+")

# Difficulty pack: 11 documented kinds x 30 = about 330 fit-only entities.
PACK_PER_KIND = 30


def pack_dir() -> Path:
    return REPO_ROOT / PACK_DIR_RELATIVE


def slice_schema_path() -> Path:
    return REPO_ROOT / SLICE_SCHEMA_RELATIVE


def train_dir() -> Path:
    override = os.environ.get("EVAL_TRAIN_DIR")
    if override:
        return Path(override)
    repository_path = REPO_ROOT / "dataset" / "train"
    if repository_path.exists():
        return repository_path
    default_path = REPO_ROOT / TRAIN_DIR_RELATIVE
    if not default_path.exists():
        fallback = REPO_ROOT / "student_resource_datasets" / "dataset" / "train"
        if fallback.exists():
            return fallback
    return default_path


def split_dir() -> Path:
    return REPO_ROOT / SPLIT_DIR_RELATIVE
