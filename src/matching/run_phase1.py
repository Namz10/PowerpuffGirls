"""Phase 1 raw baseline: fit sample, frozen blocker, loop threshold, one report score."""

from __future__ import annotations

import json
import shutil
import time
import tracemalloc
from importlib.metadata import version
from pathlib import Path

from src.blocking.verify_subset import verify_subset
from src.eval.fingerprint import sha256_file
from src.eval.score import score_files
from src.matching.capacity import measure_chunk, test_source1_count, write_capacity
from src.matching.config import (
    BLOCKING_DIR,
    CAP,
    CHUNK_ENTITIES,
    FIT_SAMPLE_SIZE,
    INDEX_PATH,
    INPUT_DIR,
    PHASE1_DIR,
    PHASE1_MANIFEST,
    REPO_ROOT,
    SEED,
    train_dir,
)
from src.matching.decide import choose_threshold
from src.matching.features_raw import FEATURE_NAMES
from src.matching.invoke_blocker import run as run_blocker
from src.matching.pairs import iter_groups, load_entities, load_gold
from src.matching.predict import MATCHING_HEADER, write_matching
from src.matching.sample_fit import write_sample
from src.matching.train_baseline import (
    build_matrices,
    holdout_ids,
    load_model,
    save_model,
    score_groups,
    train_booster,
)

import csv


def _expected_hashes() -> dict[str, str]:
    manifest = json.loads(PHASE1_MANIFEST.read_text(encoding="utf-8"))
    return {
        "loop": manifest["loop"]["candidate_file_sha256"],
        "report": manifest["readiness_report"]["candidate_file_sha256"],
        "source2": manifest["train_inputs"]["source2_sha256"],
        "source3": manifest["train_inputs"]["source3_sha256"],
    }


def _blocker(argv: list[str]) -> None:
    code = run_blocker(argv)
    if code != 0 and "--workers" in argv:
        workers_at = argv.index("--workers")
        if argv[workers_at + 1] != "1":
            fallback = list(argv)
            fallback[workers_at + 1] = "1"
            code = run_blocker(fallback)
    if code != 0:
        raise SystemExit(f"blocker command failed: {argv}")


def ensure_index(source2: Path, source3: Path, expected: dict[str, str]) -> None:
    for path, key in ((source2, "source2"), (source3, "source3")):
        digest = sha256_file(path)
        if digest != expected[key]:
            raise SystemExit(f"{path.name} hash {digest} != frozen {expected[key]}")
    if INDEX_PATH.is_file() and INDEX_PATH.stat().st_size > 0:
        print(f"index present: {INDEX_PATH}")
        return
    print("building phase1 raw index")
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    _blocker(
        [
            "build-index",
            "--source2",
            str(source2),
            "--source3",
            str(source3),
            "--index",
            str(INDEX_PATH),
            "--manifest",
            str(INPUT_DIR / "train_index_manifest.json"),
        ]
    )


def _generate(ids: Path, output: Path, provenance: Path, report: Path, source1: Path, gold: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    _blocker(
        [
            "generate",
            "--index",
            str(INDEX_PATH),
            "--source1",
            str(source1),
            "--ids",
            str(ids),
            "--truth",
            str(gold),
            "--cap",
            str(CAP),
            "--output",
            str(output),
            "--provenance",
            str(provenance),
            "--report",
            str(report),
            "--workers",
            "4",
        ]
    )


def ensure_fit_candidates(ids: Path, source1: Path, gold: Path) -> tuple[Path, Path]:
    output = INPUT_DIR / "fit50k_candidate_pairs.tsv"
    provenance = INPUT_DIR / "fit50k_candidate_provenance.tsv"
    if output.is_file() and provenance.is_file():
        print(f"fit candidates present: {output}")
        return output, provenance
    print("generating 50k fit candidates at cap 50")
    _generate(ids, output, provenance, INPUT_DIR / "fit50k_generate_report.json", source1, gold)
    return output, provenance


def ensure_frozen_candidates(
    name: str,
    expected_hash: str,
    ids: Path,
    source1: Path,
    gold: Path,
) -> tuple[Path, Path]:
    final_candidates = BLOCKING_DIR / f"{name}_candidate_pairs.tsv"
    final_provenance = BLOCKING_DIR / f"{name}_candidate_provenance.tsv"
    if final_candidates.is_file() and sha256_file(final_candidates) == expected_hash:
        if not final_provenance.is_file():
            raise FileNotFoundError(
                f"{final_candidates.name} matches the frozen hash but "
                f"{final_provenance.name} is absent. Refusing to rebuild."
            )
        print(f"leave {name} candidates; sha256 matches")
        return final_candidates, final_provenance
    staging = INPUT_DIR / f"staging_{name}"
    staged_candidates = staging / final_candidates.name
    staged_provenance = staging / final_provenance.name
    print(f"regenerating {name} candidates; final file will be replaced only if the hash matches")
    _generate(
        ids,
        staged_candidates,
        staged_provenance,
        INPUT_DIR / f"{name}_regenerate_report.json",
        source1,
        gold,
    )
    digest = sha256_file(staged_candidates)
    if digest != expected_hash:
        raise SystemExit(
            f"{name} candidate hash {digest} != {expected_hash}. "
            f"Staging files were left in {staging}. The previous final file was not replaced."
        )
    BLOCKING_DIR.mkdir(parents=True, exist_ok=True)
    for staged, final in (
        (staged_candidates, final_candidates),
        (staged_provenance, final_provenance),
    ):
        if final.exists():
            final.unlink()
        shutil.move(str(staged), str(final))
    print(f"{name} candidates match {expected_hash}")
    return final_candidates, final_provenance


def _entities_for(groups, source_paths: list[Path]):
    needed: set[str] = set()
    for source_id, candidate_ids, _rows in groups:
        needed.add(source_id)
        needed.update(candidate_ids)
    return load_entities(source_paths, needed)


def _write_gold_slice(gold: Path, wanted: set[str], output: Path) -> None:
    found = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    with gold.open(encoding="utf-8", newline="") as source, output.open(
        "w", encoding="utf-8", newline=""
    ) as target:
        reader = csv.reader(source, delimiter="\t")
        writer = csv.writer(target, delimiter="\t", lineterminator="\n")
        header = next(reader)
        writer.writerow(header)
        for row in reader:
            if row and row[0] in wanted:
                writer.writerow((row[0], row[1] if len(row) > 1 else ""))
                found += 1
    if found != len(wanted):
        raise ValueError(f"gold slice has {found} rows, expected {len(wanted)}")


def _chunked(groups, size: int):
    batch = []
    for group in groups:
        batch.append(group)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def score_named(matching: Path, gold: Path, wanted: set[str], name: str) -> float:
    gold_slice = PHASE1_DIR / f"{name}_gold.tsv"
    _write_gold_slice(gold, wanted, gold_slice)
    checked = verify_subset(matching, BLOCKING_DIR / f"{name}_candidate_pairs.tsv" if name != "fit" else INPUT_DIR / "fit50k_candidate_pairs.tsv")
    print(f"{name} subset check passed for {checked} rows")
    return score_files(matching, gold_slice)


def main() -> None:
    data = train_dir()
    source1 = data / "train_source1.tsv"
    source2 = data / "train_source2.tsv"
    source3 = data / "train_source3.tsv"
    gold = data / "train_ground_truth.tsv"
    source_paths = [source1, source2, source3]
    expected = _expected_hashes()
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    PHASE1_DIR.mkdir(parents=True, exist_ok=True)

    ids_path = INPUT_DIR / "fit50k_ids.txt"
    print("drawing fit sample")
    chosen = write_sample(ids_path)
    if len(chosen) != FIT_SAMPLE_SIZE:
        raise SystemExit(f"fit sample has {len(chosen)} ids")

    ensure_index(source2, source3, expected)
    fit_candidates, fit_provenance = ensure_fit_candidates(ids_path, source1, gold)
    loop_candidates, loop_provenance = ensure_frozen_candidates(
        "loop", expected["loop"], REPO_ROOT / "src" / "eval" / "splits" / "loop_ids.txt", source1, gold
    )
    report_candidates = BLOCKING_DIR / "report_candidate_pairs.tsv"
    report_provenance = BLOCKING_DIR / "report_candidate_provenance.tsv"
    if not report_candidates.is_file() or sha256_file(report_candidates) != expected["report"]:
        raise SystemExit("report candidate hash does not match the frozen manifest; refusing to rebuild")
    print("leave report candidates; sha256 matches")

    print("loading fit pairs")
    fit_groups = list(iter_groups(fit_candidates, fit_provenance))
    fit_entities = _entities_for(fit_groups, source_paths)
    fit_ids = {source_id for source_id, _ids, _rows in fit_groups}
    fit_gold = load_gold(gold, fit_ids)
    held = holdout_ids(
        sorted(fit_ids),
        {entity_id: fit_entities[entity_id][2] for entity_id in fit_ids},
        {entity_id: len(fit_gold[entity_id]) for entity_id in fit_ids},
    )
    print(f"training pass-1 LightGBM; fit-internal holdout entities={len(held)}")
    train_x, train_y, valid_x, valid_y = build_matrices(fit_groups, fit_entities, fit_gold, held)
    if len(valid_x) == 0 or len(train_x) == 0:
        raise SystemExit("fit matrices are empty")
    booster = train_booster(train_x, train_y, valid_x, valid_y)
    model_path = PHASE1_DIR / "model.txt"
    save_model(booster, model_path)
    (PHASE1_DIR / "feature_names.json").write_text(
        json.dumps(list(FEATURE_NAMES), indent=2) + "\n", encoding="utf-8"
    )

    print("timing 50k fit inference")
    fit_matching = PHASE1_DIR / "fit50k_matching_results.tsv"
    tracemalloc.start()
    started = time.perf_counter()
    fit_scored = score_groups(booster, fit_groups, fit_entities)
    inference_seconds = time.perf_counter() - started
    _current, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del train_x, train_y, valid_x, valid_y

    print("choosing the global threshold on loop only")
    loop_groups = list(iter_groups(loop_candidates, loop_provenance))
    loop_scored = []
    for batch in _chunked(loop_groups, CHUNK_ENTITIES):
        loop_scored.extend(score_groups(load_model(model_path), batch, _entities_for(batch, source_paths)))
    loop_ids = {source_id for source_id, _ids, _probs in loop_scored}
    loop_gold = load_gold(gold, loop_ids)
    threshold, loop_macro = choose_threshold(
        [
            (source_id, candidate_ids, probabilities, loop_gold[source_id])
            for source_id, candidate_ids, probabilities in loop_scored
        ]
    )
    print(f"phase1_provisional_threshold={threshold:.2f} loop_macro={loop_macro:.6f}")

    from src.matching.decide import kept_ids

    write_matching(
        fit_matching,
        [(source_id, kept_ids(ids, probs, threshold)) for source_id, ids, probs in fit_scored],
    )
    write_matching(
        PHASE1_DIR / "loop_matching_results.tsv",
        [(source_id, kept_ids(ids, probs, threshold)) for source_id, ids, probs in loop_scored],
    )
    loop_file_score = score_named(PHASE1_DIR / "loop_matching_results.tsv", gold, loop_ids, "loop")
    if abs(loop_file_score - loop_macro) > 1e-12:
        raise SystemExit(f"loop file score {loop_file_score} != selection score {loop_macro}")

    report_macro = None
    if report_provenance.is_file():
        print("scoring report once")
        report_groups = iter_groups(report_candidates, report_provenance)
        report_matching = PHASE1_DIR / "report_matching_results.tsv"
        report_ids: set[str] = set()
        with report_matching.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(MATCHING_HEADER)
            batch = []
            for group in report_groups:
                batch.append(group)
                if len(batch) == CHUNK_ENTITIES:
                    _write_batch(writer, batch, source_paths, model_path, threshold)
                    report_ids.update(source_id for source_id, _ids, _rows in batch)
                    batch = []
            if batch:
                _write_batch(writer, batch, source_paths, model_path, threshold)
                report_ids.update(source_id for source_id, _ids, _rows in batch)
        report_macro = score_named(report_matching, gold, report_ids, "report")
        print(f"report macro F0.5={report_macro:.6f}")
    else:
        print("report provenance is absent; threshold stays frozen and report is not scored")

    fit_pairs = sum(len(ids) for _source, ids, _probs in fit_scored)
    test_entities = test_source1_count()
    projected = inference_seconds / len(fit_scored) * test_entities
    manifest = {
        "seed": SEED,
        "cap": CAP,
        "fit_sample_ids": len(chosen),
        "fit_sample_sha256": sha256_file(ids_path),
        "fit_candidate_sha256": sha256_file(fit_candidates),
        "loop_candidate_sha256": sha256_file(loop_candidates),
        "report_candidate_sha256": sha256_file(report_candidates),
        "phase1_provisional_threshold": threshold,
        "loop_macro_f05": loop_macro,
        "report_macro_f05": report_macro,
        "report_provenance_present": report_provenance.is_file(),
        "fit_inference_seconds": round(inference_seconds, 3),
        "fit_inference_peak_traced_bytes": peak_bytes,
        "fit_pairs": fit_pairs,
        "projected_full_test_inference_seconds": round(projected, 1),
        "projected_full_test_plus_one_rerun_seconds": round(projected * 2, 1),
        "test_source1_entities": test_entities,
        "feature_names": list(FEATURE_NAMES),
        "lightgbm": version("lightgbm"),
        "rapidfuzz": version("rapidfuzz"),
        "model": "artifacts/matching/phase1/model.txt",
        "not_phase3_lock": True,
        "not_the_400k_fit_candidate_file": True,
    }
    (PHASE1_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("measuring phase 2 feature capacity on the 50k fit chunk")
    measurement = measure_chunk(fit_groups, fit_entities)
    write_capacity(measurement, inference_seconds, len(fit_scored), test_entities)
    print(json.dumps({"loop_macro_f05": loop_macro, "report_macro_f05": report_macro, "threshold": threshold}))


def _write_batch(writer, batch, source_paths, model_path: Path, threshold: float) -> None:
    from src.matching.decide import kept_ids

    booster_groups = score_groups(load_model(model_path), batch, _entities_for(batch, source_paths))
    for source_id, candidate_ids, probabilities in booster_groups:
        writer.writerow((source_id, ",".join(kept_ids(candidate_ids, probabilities, threshold))))


if __name__ == "__main__":
    main()
