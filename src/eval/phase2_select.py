"""Compare the Phase 1 raw loop candidates with the Phase 2 union on oracle F0.5."""

import json
import math
import random
from pathlib import Path

from src.eval.config import REPO_ROOT, SEED, train_dir
from src.eval.fingerprint import sha256_file
from src.eval.score import entity_f05, macro_f05


def paired_bootstrap_delta(incumbent, challenger, resamples: int = 2000, seed: int = SEED) -> dict:
    if len(incumbent) != len(challenger) or not incumbent:
        raise ValueError("paired non-empty samples must have equal length")
    if resamples < 2000:
        raise ValueError("the selection protocol requires at least 2,000 resamples")
    differences = [new - old for old, new in zip(incumbent, challenger)]
    rng = random.Random(seed)
    size = len(differences)
    sampled = []
    for _ in range(resamples):
        sampled.append(sum(differences[rng.randrange(size)] for _ in range(size)) / size)
    sampled.sort()
    lower = sampled[math.floor(0.025 * (resamples - 1))]
    upper = sampled[math.ceil(0.975 * (resamples - 1))]
    return {
        "delta": sum(differences) / size,
        "ci95_lower": lower,
        "ci95_upper": upper,
        "resamples": resamples,
        "seed": seed,
        "promote": lower > 0.0,
    }


def retrieval_metrics(rows: dict[str, set[str]], truth: dict[str, set[str]]) -> dict:
    widths = []
    truth_links = recovered = nonempty = complete = empty = 0
    truth_by_source = {"S2": 0, "S3": 0}
    recovered_by_source = {"S2": 0, "S3": 0}
    for source_id in sorted(truth):
        predicted = rows[source_id]
        gold = truth[source_id]
        widths.append(len(predicted))
        empty += int(not predicted)
        overlap = predicted & gold
        truth_links += len(gold)
        recovered += len(overlap)
        if gold:
            nonempty += 1
            complete += int(gold <= predicted)
        for item in gold:
            truth_by_source[item[:2]] += 1
        for item in overlap:
            recovered_by_source[item[:2]] += 1
    entities = len(widths)
    return {
        "entities": entities,
        "link_recall": recovered / truth_links if truth_links else 1.0,
        "complete_entity_recall": complete / nonempty if nonempty else 1.0,
        "empty_candidate_rate": empty / entities if entities else 0.0,
        "mean_width": sum(widths) / entities if entities else 0.0,
        "max_width": max(widths, default=0),
        "link_recall_by_source": {
            source: (
                recovered_by_source[source] / truth_by_source[source]
                if truth_by_source[source] else 1.0
            )
            for source in ("S2", "S3")
        },
    }


def oracle_scores(rows: dict[str, set[str]], truth: dict[str, set[str]]) -> list[float]:
    predicted = {source_id: rows[source_id] & truth[source_id] for source_id in truth}
    return [entity_f05(predicted[source_id], truth[source_id]) for source_id in sorted(truth)]


def load_candidates(path: Path) -> dict[str, set[str]]:
    rows = {}
    with path.open(encoding="utf-8", newline="") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        if header != ["source1_entity_id", "candidate_entity_ids"]:
            raise ValueError(f"unexpected candidate header in {path}")
        for line in handle:
            if not line.strip():
                continue
            source_id, _, rest = line.rstrip("\n").partition("\t")
            ids = rest.split(",") if rest else []
            rows[source_id] = set(ids)
    return rows


def decide(bootstrap: dict, on_pareto: bool) -> str:
    if bootstrap["ci95_lower"] > 0.0 and on_pareto:
        return "promote_phase2"
    return "keep_phase1_raw"


def _tsv_map(path: Path) -> dict[str, list[str]]:
    rows = {}
    with path.open(encoding="utf-8", newline="") as handle:
        handle.readline()
        for line in handle:
            if line.strip():
                parts = line.rstrip("\n").split("\t")
                rows[parts[0]] = parts
    return rows


def build_report(
    phase1_path: Path,
    phase2_path: Path,
    gold_path: Path,
    join_path: Path,
    source1_path: Path,
    misses_path: Path,
    blocker_report_path: Path,
    loop_ids: list[str],
) -> dict:
    phase1 = load_candidates(phase1_path)
    phase2 = load_candidates(phase2_path)
    if set(phase1) != set(loop_ids) or set(phase2) != set(loop_ids):
        raise ValueError("candidate files do not cover the frozen loop")
    gold = {}
    with gold_path.open(encoding="utf-8", newline="") as handle:
        handle.readline()
        wanted = set(loop_ids)
        for line in handle:
            source_id, _, rest = line.rstrip("\n").partition("\t")
            if source_id in wanted:
                gold[source_id] = set(rest.split(",")) if rest else set()
    if set(gold) != set(loop_ids):
        raise ValueError("gold does not cover the loop")
    countries = {}
    with source1_path.open(encoding="utf-8", newline="") as handle:
        handle.readline()
        wanted = set(loop_ids)
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if parts and parts[0] in wanted:
                countries[parts[0]] = parts[3]
    join = _tsv_map(join_path)
    incumbent = oracle_scores(phase1, gold)
    challenger = oracle_scores(phase2, gold)
    ordered = sorted(gold)
    bootstrap = paired_bootstrap_delta(incumbent, challenger)
    blocker = json.loads(blocker_report_path.read_text(encoding="utf-8"))
    on_pareto = bool(blocker.get("promotion_check", {}).get("selected_point_on_pareto_frontier"))
    choice = decide(bootstrap, on_pareto)

    def slice_metrics(ids: list[str], rows: dict[str, set[str]]) -> dict:
        sub_rows = {item: rows[item] for item in ids}
        sub_gold = {item: gold[item] for item in ids}
        return retrieval_metrics(sub_rows, sub_gold)

    by_script: dict[str, list[str]] = {}
    by_country: dict[str, list[str]] = {}
    singletons = []
    nonsingletons = []
    for source_id in ordered:
        label = join[source_id][2]
        by_script.setdefault(label, []).append(source_id)
        by_country.setdefault(countries[source_id], []).append(source_id)
        (singletons if not gold[source_id] else nonsingletons).append(source_id)

    miss_counts = {"overall": {}, "indic": {}, "accented_latin": {}}
    with misses_path.open(encoding="utf-8", newline="") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        reason_at = header.index("miss_reason")
        id_at = header.index("source1_entity_id")
        for line in handle:
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            reason = parts[reason_at]
            if not reason:
                continue
            source_id = parts[id_at]
            script = join[source_id][2]
            for key in ("overall",) + (("indic",) if script == "indic" else ()) + (
                ("accented_latin",) if script == "accented_latin" else ()
            ):
                bucket = miss_counts[key]
                bucket[reason] = bucket.get(reason, 0) + 1
    dominant = {
        key: max(counts, key=counts.get) if counts else None
        for key, counts in miss_counts.items()
    }
    return {
        "decision": choice,
        "oracle_macro_f05": {
            "phase1": macro_f05(
                {item: phase1[item] & gold[item] for item in gold}, gold
            ),
            "phase2": macro_f05(
                {item: phase2[item] & gold[item] for item in gold}, gold
            ),
        },
        "bootstrap": bootstrap,
        "selected_point_on_pareto_frontier": on_pareto,
        "phase1": retrieval_metrics(phase1, gold),
        "phase2": retrieval_metrics(phase2, gold),
        "country_slices": {
            country: {
                "phase1": slice_metrics(ids, phase1),
                "phase2": slice_metrics(ids, phase2),
            }
            for country, ids in sorted(by_country.items())
        },
        "script_slices": {
            script: {
                "phase1": slice_metrics(ids, phase1),
                "phase2": slice_metrics(ids, phase2),
            }
            for script, ids in sorted(by_script.items())
        },
        "singleton_empty_candidate_rate": {
            "phase1": retrieval_metrics(
                {item: phase1[item] for item in singletons},
                {item: gold[item] for item in singletons},
            )["empty_candidate_rate"] if singletons else None,
            "phase2": retrieval_metrics(
                {item: phase2[item] for item in singletons},
                {item: gold[item] for item in singletons},
            )["empty_candidate_rate"] if singletons else None,
        },
        "nonsingleton_empty_candidate_rate": {
            "phase1": retrieval_metrics(
                {item: phase1[item] for item in nonsingletons},
                {item: gold[item] for item in nonsingletons},
            )["empty_candidate_rate"] if nonsingletons else None,
            "phase2": retrieval_metrics(
                {item: phase2[item] for item in nonsingletons},
                {item: gold[item] for item in nonsingletons},
            )["empty_candidate_rate"] if nonsingletons else None,
        },
        "miss_counts": miss_counts,
        "dominant_miss_reason": dominant,
        "fingerprints": {
            "phase1_candidates_sha256": sha256_file(phase1_path),
            "phase2_candidates_sha256": sha256_file(phase2_path),
            "misses_sha256": sha256_file(misses_path),
            "blocker_report_sha256": sha256_file(blocker_report_path),
            "gold_join_sha256": sha256_file(join_path),
        },
    }


def main() -> None:
    root = REPO_ROOT
    out = root / "artifacts" / "eval" / "phase2" / "selection_report.json"
    report = build_report(
        root / "artifacts" / "blocking" / "loop_candidate_pairs.tsv",
        root / "artifacts" / "blocking" / "phase2_loop_candidates.tsv",
        train_dir() / "train_ground_truth.tsv",
        root / "artifacts" / "eval" / "phase2" / "loop_script_join.tsv",
        train_dir() / "train_source1.tsv",
        root / "artifacts" / "blocking" / "phase2_loop_misses.tsv",
        root / "artifacts" / "blocking" / "phase2_loop_report.json",
        (root / "src" / "eval" / "splits" / "loop_ids.txt").read_text(encoding="utf-8").splitlines(),
    )
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(report["decision"], report["bootstrap"]["ci95_lower"])


if __name__ == "__main__":
    main()
