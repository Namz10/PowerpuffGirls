"""Pass-1 LightGBM on the fit candidate distribution. No upsampling and no Optuna."""

from __future__ import annotations

import os
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from src.eval.split_protocol import stratum_key
from src.matching.config import HOLDOUT_FRACTION, SEED
from src.matching.features_raw import FEATURE_NAMES, raw_feature_row

PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 200,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "seed": SEED,
    "bagging_seed": SEED,
    "feature_fraction_seed": SEED,
    "data_random_seed": SEED,
    "verbosity": -1,
    "num_threads": max(1, os.cpu_count() or 1),
    "force_row_wise": True,
    "deterministic": True,
}


def holdout_ids(
    entity_ids: list[str],
    countries: dict[str, str],
    gold_sizes: dict[str, int],
    fraction: float = HOLDOUT_FRACTION,
    seed: int = SEED,
) -> set[str]:
    """Fit-internal entity holdout for early stopping. Not used to pick the threshold."""
    strata: dict[tuple[str, str], list[str]] = defaultdict(list)
    for entity_id in entity_ids:
        strata[stratum_key(countries[entity_id], gold_sizes[entity_id])].append(entity_id)
    rng = random.Random(seed)
    held: set[str] = set()
    for key in sorted(strata):
        ids = sorted(strata[key])
        rng.shuffle(ids)
        held.update(ids[: int(len(ids) * fraction)])
    if not held or len(held) == len(entity_ids):
        raise ValueError("fit-internal holdout is empty or took every entity")
    return held


def build_matrices(groups, entities, gold: dict[str, set[str]], held: set[str]):
    n_rows = sum(len(ids) for _source, ids, _rows in groups)
    features = len(FEATURE_NAMES)
    train_x = np.empty((n_rows, features), dtype=np.float32)
    train_y = np.empty(n_rows, dtype=np.uint8)
    train_n = 0
    valid_x = np.empty((n_rows, features), dtype=np.float32)
    valid_y = np.empty(n_rows, dtype=np.uint8)
    valid_n = 0
    for source_id, candidate_ids, provenance_rows in groups:
        source_name, source_address, _country = entities[source_id]
        truth = gold[source_id]
        is_held = source_id in held
        for candidate_id, provenance in zip(candidate_ids, provenance_rows):
            candidate_name, candidate_address, _candidate_country = entities[candidate_id]
            row = raw_feature_row(
                source_name,
                source_address,
                candidate_name,
                candidate_address,
                provenance,
            )
            label = 1 if candidate_id in truth else 0
            if is_held:
                valid_x[valid_n] = row
                valid_y[valid_n] = label
                valid_n += 1
            else:
                train_x[train_n] = row
                train_y[train_n] = label
                train_n += 1
    return train_x[:train_n], train_y[:train_n], valid_x[:valid_n], valid_y[:valid_n]


def train_booster(train_x, train_y, valid_x, valid_y, num_boost_round: int = 300):
    import lightgbm as lgb

    train_set = lgb.Dataset(train_x, label=train_y, feature_name=list(FEATURE_NAMES))
    valid_set = lgb.Dataset(
        valid_x, label=valid_y, reference=train_set, feature_name=list(FEATURE_NAMES)
    )
    return lgb.train(
        PARAMS,
        train_set,
        num_boost_round=num_boost_round,
        valid_sets=[valid_set],
        valid_names=["fit_holdout"],
        callbacks=[lgb.early_stopping(30), lgb.log_evaluation(50)],
    )


def save_model(booster, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(path))


def load_model(path: Path):
    import lightgbm as lgb

    return lgb.Booster(model_file=str(path))


def predict_probabilities(booster, matrix: np.ndarray) -> np.ndarray:
    iteration = booster.best_iteration or booster.current_iteration()
    return booster.predict(matrix, num_iteration=iteration)


def score_groups(booster, groups, entities) -> list[tuple[str, list[str], list[float]]]:
    scored = []
    for source_id, candidate_ids, provenance_rows in groups:
        if not candidate_ids:
            scored.append((source_id, [], []))
            continue
        source_name, source_address, _country = entities[source_id]
        matrix = np.empty((len(candidate_ids), len(FEATURE_NAMES)), dtype=np.float32)
        for index, (candidate_id, provenance) in enumerate(zip(candidate_ids, provenance_rows)):
            candidate_name, candidate_address, _candidate_country = entities[candidate_id]
            matrix[index] = raw_feature_row(
                source_name,
                source_address,
                candidate_name,
                candidate_address,
                provenance,
            )
        probabilities = predict_probabilities(booster, matrix)
        scored.append((source_id, list(candidate_ids), [float(value) for value in probabilities]))
    return scored
