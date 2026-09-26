"""Phase 3 skeleton commands.

``smoke`` fits two tiny fold models on synthetic rows. It writes nothing under
``artifacts/gates/``. ``prepare`` checks that training ids are fit-only and
prints the future train command. ``train`` always refuses: the 400k fit
candidate file is not frozen, and this command will not start that job.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from src.matching.config import REPO_ROOT, SEED
from src.matching.decision_config import skeleton_config, validate_config
from src.matching.ensemble import average_fold_probabilities
from src.matching.folds import assert_fit_only
from src.matching.sample_fit import load_ids

GATE_PATH = REPO_ROOT / "artifacts" / "gates" / "phase_3.json"
TRAIN_BLOCK = (
    "Phase 3 train is blocked until Srishti freezes the 400k fit candidate file. "
    "This skeleton will not train on the 50k Phase 1 candidates and will not "
    "start a job longer than a few minutes."
)


def prepare_message(train_ids: set[str], fit_ids: set[str], loop_ids: set[str], report_ids: set[str]) -> str:
    assert_fit_only(train_ids, fit_ids, loop_ids, report_ids)
    return (
        "Not training. When the frozen 400k fit candidates exist, the command will be:\n"
        "python -m src.matching.run_phase3 train --fit-candidates <400k-candidate-tsv>\n"
        + TRAIN_BLOCK
    )


def smoke() -> dict:
    """Two LightGBM folds on synthetic rows. Seconds, not a real operating point."""
    import lightgbm as lgb

    if GATE_PATH.exists():
        raise RuntimeError(f"refusing to run while {GATE_PATH} exists")
    rng = np.random.default_rng(SEED)
    features = rng.random((16, 4))
    labels = (features[:, 0] > 0.5).astype(int)
    groups = np.array([index // 4 for index in range(16)])
    fold_probs = []
    for fold in (0, 1):
        held = groups == fold
        train_set = lgb.Dataset(features[~held], label=labels[~held])
        booster = lgb.train(
            {
                "objective": "binary",
                "verbosity": -1,
                "seed": SEED,
                "deterministic": True,
                "num_leaves": 3,
                "min_data_in_leaf": 1,
            },
            train_set,
            num_boost_round=5,
        )
        fold_probs.append([float(value) for value in booster.predict(features[:2])])
    averaged = average_fold_probabilities(fold_probs)
    document = skeleton_config()
    validate_config(document)
    if GATE_PATH.exists():
        raise RuntimeError("smoke created a Phase 3 gate")
    return {"averaged": averaged, "status": document["status"], "folds": 2}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("smoke")
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--ids", type=Path, required=True)
    commands.add_parser("train")
    args = parser.parse_args()
    if args.command == "train":
        raise SystemExit(TRAIN_BLOCK)
    if args.command == "smoke":
        result = smoke()
        print(f"smoke status={result['status']} folds={result['folds']}")
        return
    split_dir = REPO_ROOT / "src" / "eval" / "splits"
    message = prepare_message(
        load_ids(args.ids),
        load_ids(split_dir / "fit_ids.txt"),
        load_ids(split_dir / "loop_ids.txt"),
        load_ids(split_dir / "report_ids.txt"),
    )
    print(message)


if __name__ == "__main__":
    main()
