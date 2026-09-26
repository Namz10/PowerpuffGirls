"""Generate, evaluate, and serialize the exact matcher candidate set."""

from __future__ import annotations

import csv
import json
import math
import multiprocessing
import resource
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .index import RawIndex, sha256_file
from .normalize import normalize_raw, raw_tokens

CANDIDATE_HEADER = ("source1_entity_id", "candidate_entity_ids")
PROVENANCE_HEADER = (
    "source1_entity_id", "candidate_entity_id", "target_source", "provenance",
    "rank", "exact_name", "exact_address", "name_token", "address_token", "retrieval_score",
)
MISS_HEADER = (
    "source1_entity_id", "truth_entity_ids", "candidate_entity_ids",
    "missed_truth_ids", "status", "miss_reason",
)
CAP_SWEEP = (5, 10, 20, 30, 50, 100)
MAX_MARGINAL_PAIRS_PER_LINK = 100.0
_WORKER_INDEX: RawIndex | None = None


@dataclass(frozen=True)
class Query:
    entity_id: str
    name: str
    address: str
    country: str


@dataclass
class Evidence:
    source: str
    exact_name: bool = False
    exact_address: bool = False
    name_token: bool = False
    address_token: bool = False
    retrieval_score: float = 0.0

    @property
    def provenance(self) -> str:
        labels = []
        for enabled, label in (
            (self.exact_name, "exact_name"), (self.exact_address, "exact_address"),
            (self.name_token, "rare_name_token"), (self.address_token, "rare_address_token"),
        ):
            if enabled:
                labels.append(label)
        return ",".join(labels)

    def sort_key(self, entity_id: str) -> tuple:
        return (
            -(self.exact_name + self.exact_address),
            -(self.name_token + self.address_token),
            -self.retrieval_score,
            entity_id,
        )


def load_queries(path: Path, requested_ids: set[str] | None = None) -> list[Query]:
    queries = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["entity_id", "business_name", "business_address", "country"]:
            raise ValueError(f"unexpected source header in {path}: {reader.fieldnames}")
        for row in reader:
            if requested_ids is None or row["entity_id"] in requested_ids:
                queries.append(Query(
                    row["entity_id"], row["business_name"], row["business_address"], row["country"].strip()
                ))
    if requested_ids is not None and {query.entity_id for query in queries} != requested_ids:
        missing = requested_ids - {query.entity_id for query in queries}
        raise ValueError(f"{len(missing)} requested S1 ids are absent from {path}")
    return queries


def load_requested_ids(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def load_truth(path: Path, requested_ids: set[str]) -> dict[str, set[str]]:
    truth = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            if row["source1_entity_id"] in requested_ids:
                truth[row["source1_entity_id"]] = set(filter(None, row["matched_entity_ids"].split(",")))
    if set(truth) != requested_ids:
        raise ValueError("ground truth does not cover requested ids")
    return truth


def retrieve(index: RawIndex, query: Query, pool_per_channel: int = 120) -> list[tuple[str, Evidence]]:
    name = normalize_raw(query.name)
    address = normalize_raw(query.address)
    evidence: dict[str, Evidence] = {}
    for source in ("S2", "S3"):
        for field, value, attribute in (
            ("name", name, "exact_name"), ("address", address, "exact_address")
        ):
            for entity_id in index.exact(query.country, source, field, value, pool_per_channel):
                item = evidence.setdefault(entity_id, Evidence(source))
                setattr(item, attribute, True)
        for entity_id, field, score in index.rare_fields(
            query.country,
            source,
            raw_tokens(query.name),
            raw_tokens(query.address),
            pool_per_channel,
        ):
            item = evidence.setdefault(entity_id, Evidence(source))
            setattr(item, "name_token" if field == "name" else "address_token", True)
            item.retrieval_score += score
    return sorted(evidence.items(), key=lambda pair: pair[1].sort_key(pair[0]))


def _worker_init(index_path: str) -> None:
    global _WORKER_INDEX
    _WORKER_INDEX = RawIndex(Path(index_path))


def _worker_retrieve(query: Query) -> list[tuple[str, Evidence]]:
    if _WORKER_INDEX is None:
        raise RuntimeError("blocking worker index was not initialized")
    return retrieve(_WORKER_INDEX, query)


def select(ranked: list[tuple[str, Evidence]], cap: int, source_floor: int = 2) -> list[tuple[str, Evidence]]:
    """Strict global cap with a small opportunity floor for each target source."""
    if cap < 0:
        raise ValueError("candidate cap must be non-negative")
    if len(ranked) <= cap:
        return ranked
    selected: list[tuple[str, Evidence]] = []
    selected_ids = set()
    for source in ("S2", "S3"):
        for item in (pair for pair in ranked if pair[1].source == source):
            if (
                len(selected) >= cap
                or sum(1 for pair in selected if pair[1].source == source) >= source_floor
            ):
                break
            selected.append(item)
            selected_ids.add(item[0])
    for item in ranked:
        if len(selected) >= cap:
            break
        if item[0] not in selected_ids:
            selected.append(item)
            selected_ids.add(item[0])
    return sorted(selected, key=lambda pair: pair[1].sort_key(pair[0]))


def percentile(values: list[int], quantile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[math.ceil(quantile * len(ordered)) - 1]


def metrics(candidates: dict[str, list[str]], truth: dict[str, set[str]], comparison_space: int) -> dict:
    widths = [len(candidates[entity_id]) for entity_id in truth]
    links = sum(len(items) for items in truth.values())
    recovered = sum(len(set(candidates[entity_id]) & items) for entity_id, items in truth.items())
    nonempty = [entity_id for entity_id, items in truth.items() if items]
    any_hit = sum(bool(set(candidates[entity_id]) & truth[entity_id]) for entity_id in nonempty)
    complete = sum(truth[entity_id] <= set(candidates[entity_id]) for entity_id in nonempty)
    pairs = sum(widths)
    return {
        "entities": len(widths),
        "truth_links": links,
        "recovered_truth_links": recovered,
        "link_recall": recovered / links if links else 1.0,
        "any_hit_recall": any_hit / len(nonempty) if nonempty else 1.0,
        "complete_entity_recall": complete / len(nonempty) if nonempty else 1.0,
        "candidate_width": {
            "mean": pairs / len(widths) if widths else 0.0,
            "p95": percentile(widths, 0.95),
            "p99": percentile(widths, 0.99),
            "max": max(widths, default=0),
        },
        "total_candidate_pairs": pairs,
        "country_equality_pairs": comparison_space,
        "reduction_ratio": 1.0 - pairs / comparison_space if comparison_space else 1.0,
        "reduction_factor": comparison_space / pairs if pairs else None,
        "empty_candidate_rate": sum(width == 0 for width in widths) / len(widths) if widths else 0.0,
    }


class MetricAccumulator:
    """Constant-memory recall/width accounting for one cap."""

    def __init__(self) -> None:
        self.widths: list[int] = []
        self.truth_links = 0
        self.recovered = 0
        self.nonempty = 0
        self.any_hit = 0
        self.complete = 0
        self.truth_by_source = Counter()
        self.recovered_by_source = Counter()

    def add(self, candidate_ids: list[str], truth_ids: set[str]) -> None:
        candidate_set = set(candidate_ids)
        overlap = candidate_set & truth_ids
        self.widths.append(len(candidate_ids))
        self.truth_links += len(truth_ids)
        self.recovered += len(overlap)
        for entity_id in truth_ids:
            self.truth_by_source[entity_id[:2]] += 1
        for entity_id in overlap:
            self.recovered_by_source[entity_id[:2]] += 1
        if truth_ids:
            self.nonempty += 1
            self.any_hit += bool(overlap)
            self.complete += truth_ids <= candidate_set

    def finish(self, comparison_space: int) -> dict:
        pairs = sum(self.widths)
        entities = len(self.widths)
        result = {
            "entities": entities,
            "truth_links": self.truth_links,
            "recovered_truth_links": self.recovered,
            "link_recall": self.recovered / self.truth_links if self.truth_links else 1.0,
            "any_hit_recall": self.any_hit / self.nonempty if self.nonempty else 1.0,
            "complete_entity_recall": self.complete / self.nonempty if self.nonempty else 1.0,
            "candidate_width": {
                "mean": pairs / entities if entities else 0.0,
                "p95": percentile(self.widths, 0.95),
                "p99": percentile(self.widths, 0.99),
                "max": max(self.widths, default=0),
            },
            "total_candidate_pairs": pairs,
            "country_equality_pairs": comparison_space,
            "reduction_ratio": 1.0 - pairs / comparison_space if comparison_space else 1.0,
            "reduction_factor": comparison_space / pairs if pairs else None,
            "empty_candidate_rate": sum(width == 0 for width in self.widths) / entities if entities else 0.0,
        }
        result["link_recall_by_source"] = {
            source: {
                "truth_links": self.truth_by_source[source],
                "recovered_truth_links": self.recovered_by_source[source],
                "link_recall": (
                    self.recovered_by_source[source] / self.truth_by_source[source]
                    if self.truth_by_source[source] else 1.0
                ),
            }
            for source in ("S2", "S3")
        }
        return result


def choose_cap(sweep: dict[int, dict]) -> int:
    """Stop before an increment costs over 100 extra pairs per true link."""
    ordered = sorted(sweep)
    chosen = ordered[0]
    for previous_cap, current_cap in zip(ordered, ordered[1:]):
        previous = sweep[previous_cap]
        current = sweep[current_cap]
        gained_links = current["recovered_truth_links"] - previous["recovered_truth_links"]
        added_pairs = current["total_candidate_pairs"] - previous["total_candidate_pairs"]
        if gained_links <= 0 or added_pairs / gained_links > MAX_MARGINAL_PAIRS_PER_LINK:
            break
        chosen = current_cap
    return chosen


def generate(
    index_path: Path,
    queries: list[Query],
    output_path: Path,
    cap: int,
    provenance_path: Path | None = None,
    truth: dict[str, set[str]] | None = None,
    sweep_caps: Iterable[int] = (),
    workers: int = 1,
    misses_path: Path | None = None,
) -> dict:
    started = time.monotonic()
    index = RawIndex(index_path)
    country_counts = Counter(query.country for query in queries)
    comparison_space = index.comparison_space(country_counts)
    sweep_caps = tuple(sweep_caps)
    sweep_metrics = {current_cap: MetricAccumulator() for current_cap in sweep_caps}
    selected_metrics = MetricAccumulator() if truth is not None else None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if provenance_path is not None:
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        provenance_handle = provenance_path.open("w", encoding="utf-8", newline="")
        provenance_writer = csv.writer(provenance_handle, delimiter="\t", lineterminator="\n")
        provenance_writer.writerow(PROVENANCE_HEADER)
    else:
        provenance_handle = None
        provenance_writer = None
    if misses_path is not None:
        if truth is None:
            raise ValueError("miss reasons require --truth")
        misses_path.parent.mkdir(parents=True, exist_ok=True)
        misses_handle = misses_path.open("w", encoding="utf-8", newline="")
        misses_writer = csv.writer(misses_handle, delimiter="\t", lineterminator="\n")
        misses_writer.writerow(MISS_HEADER)
    else:
        misses_handle = None
        misses_writer = None
    pool = None
    if workers > 1:
        index.close()
        pool = multiprocessing.Pool(workers, initializer=_worker_init, initargs=(str(index_path),))
        ranked_rows = pool.imap(_worker_retrieve, queries, chunksize=16)
    else:
        ranked_rows = map(lambda query: retrieve(index, query), queries)
    try:
        output = output_path.open("w", encoding="utf-8", newline="")
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(CANDIDATE_HEADER)
        for query, ranked in zip(queries, ranked_rows):
            selected = select(ranked, cap)
            ids = [entity_id for entity_id, _ in selected]
            if selected_metrics is not None:
                truth_ids = truth[query.entity_id]
                selected_metrics.add(ids, truth_ids)
                for current_cap in sweep_caps:
                    current_ids = [
                        entity_id for entity_id, _ in select(ranked, current_cap)
                    ]
                    sweep_metrics[current_cap].add(current_ids, truth_ids)
                if misses_writer is not None:
                    selected_set = set(ids)
                    ranked_ids = {entity_id for entity_id, _ in ranked}
                    missed = truth_ids - selected_set
                    if not missed:
                        status, reason = "complete", ""
                    elif missed <= ranked_ids:
                        status, reason = "miss", "cap_truncation"
                    elif not selected_set:
                        status, reason = "miss", "no_retrieval_evidence"
                    elif missed & ranked_ids:
                        status, reason = "miss", "mixed_cap_and_no_retrieval_evidence"
                    else:
                        status, reason = "miss", "no_retrieval_evidence_for_truth"
                    misses_writer.writerow((
                        query.entity_id,
                        ",".join(sorted(truth_ids)),
                        ",".join(ids),
                        ",".join(sorted(missed)),
                        status,
                        reason,
                    ))
            writer.writerow((query.entity_id, ",".join(ids)))
            if provenance_writer is not None:
                for rank, (candidate_id, item) in enumerate(selected, start=1):
                    provenance_writer.writerow((
                        query.entity_id, candidate_id, item.source, item.provenance, rank,
                        int(item.exact_name), int(item.exact_address), int(item.name_token),
                        int(item.address_token), f"{item.retrieval_score:.9f}",
                    ))
    finally:
        if pool is not None:
            pool.close()
            pool.join()
        else:
            index.close()
        if 'output' in locals():
            output.close()
        if provenance_handle is not None:
            provenance_handle.close()
        if misses_handle is not None:
            misses_handle.close()

    result = {
        "cap": cap,
        "source_floor": 2,
        "candidate_file": str(output_path),
        "candidate_file_sha256": sha256_file(output_path),
        "candidate_header": list(CANDIDATE_HEADER),
        "provenance_columns": list(PROVENANCE_HEADER),
        "miss_columns": list(MISS_HEADER),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    if truth is not None:
        result["selected_metrics"] = selected_metrics.finish(comparison_space)
        result["cap_sweep"] = {
            str(key): value.finish(comparison_space)
            for key, value in sweep_metrics.items()
        }
    return result


def write_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
