"""Command-line entry point for frozen Phase 1 and provisional Phase 2 blocking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.eval.config import split_dir

from .generate import CAP_SWEEP, choose_cap, generate, load_queries, load_requested_ids, load_truth, write_report
from .index import build_index, write_manifest
from .phase2 import (
    CAP_SWEEP as PHASE2_CAP_SWEEP,
    RESCUE_QUOTA_SWEEP,
    Phase2Config,
    build_phase2_index,
    generate_phase2,
    load_truth as load_phase2_truth,
    write_json,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-index")
    build.add_argument("--source2", type=Path, required=True)
    build.add_argument("--source3", type=Path, required=True)
    build.add_argument("--index", type=Path, required=True)
    build.add_argument("--manifest", type=Path, required=True)
    run = commands.add_parser("generate")
    run.add_argument("--index", type=Path, required=True)
    run.add_argument("--source1", type=Path, required=True)
    run.add_argument("--ids", type=Path)
    run.add_argument("--truth", type=Path)
    run.add_argument("--cap", type=int, required=True)
    run.add_argument("--sweep", action="store_true")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--provenance", type=Path)
    run.add_argument("--report", type=Path, required=True)
    run.add_argument("--workers", type=int, default=1)
    run.add_argument("--misses", type=Path)
    build2 = commands.add_parser("phase2-build-index")
    build2.add_argument("--source2", type=Path, required=True)
    build2.add_argument("--source3", type=Path, required=True)
    build2.add_argument("--index", type=Path, required=True)
    build2.add_argument("--manifest", type=Path, required=True)
    run2 = commands.add_parser("phase2-generate")
    run2.add_argument("--index", type=Path, required=True)
    run2.add_argument("--source1", type=Path, required=True)
    run2.add_argument("--ids", type=Path)
    run2.add_argument("--truth", type=Path)
    run2.add_argument("--cap", type=int, default=50)
    run2.add_argument("--source-floor", type=int, default=2)
    run2.add_argument("--rescue-quota", type=int, default=10)
    run2.add_argument("--output", type=Path, required=True)
    run2.add_argument("--provenance", type=Path)
    run2.add_argument("--misses", type=Path)
    run2.add_argument("--report", type=Path, required=True)
    run2.add_argument("--resources", type=Path, default=Path("artifacts/resources"))
    run2.add_argument("--no-sweep", action="store_true")
    semantic_build = commands.add_parser("phase2-semantic-build")
    semantic_build.add_argument("--source2", type=Path, required=True)
    semantic_build.add_argument("--source3", type=Path, required=True)
    semantic_build.add_argument("--index", type=Path, required=True)
    semantic_build.add_argument("--manifest", type=Path, required=True)
    semantic_build.add_argument("--model")
    semantic_build.add_argument("--device", choices=("cuda", "cpu"), default="cpu")
    semantic_build.add_argument("--batch-size", type=int, default=64)
    semantic_build.add_argument("--lsh-bits", type=int, default=16)
    semantic_build.add_argument("--lsh-seed", type=int, default=42)
    semantic_union = commands.add_parser("phase2-semantic-union")
    semantic_union.add_argument("--semantic-index", type=Path, required=True)
    semantic_union.add_argument("--source1", type=Path, required=True)
    semantic_union.add_argument("--lexical", type=Path, required=True)
    semantic_union.add_argument("--ids", type=Path)
    semantic_union.add_argument("--output", type=Path, required=True)
    semantic_union.add_argument("--provenance", type=Path)
    semantic_union.add_argument("--report", type=Path, required=True)
    semantic_union.add_argument("--model")
    semantic_union.add_argument("--device", choices=("cuda", "cpu"), default="cpu")
    semantic_union.add_argument("--batch-size", type=int, default=64)
    semantic_union.add_argument("--semantic-top-k", type=int, default=10)
    semantic_union.add_argument("--union-cap", type=int, default=60)
    semantic_union.add_argument("--max-pool-per-source", type=int, default=2000)
    semantic_union.add_argument("--probe-radius", type=int, choices=(0, 1, 2), default=1)
    semantic_union.add_argument("--lsh-bits", type=int, default=16)
    semantic_union.add_argument("--lsh-seed", type=int, default=42)
    return result


def main() -> None:
    args = parser().parse_args()
    if args.command == "build-index":
        manifest = build_index((args.source2, args.source3), args.index)
        write_manifest(manifest, args.manifest)
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return
    if args.command == "phase2-build-index":
        manifest = build_phase2_index((args.source2, args.source3), args.index)
        write_json(manifest, args.manifest)
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return
    if args.command == "phase2-semantic-build":
        from .semantic import DEFAULT_MODEL, SemanticConfig, build_semantic_index

        config = SemanticConfig(
            device=args.device,
            batch_size=args.batch_size,
            lsh_bits=args.lsh_bits,
            lsh_seed=args.lsh_seed,
        )
        manifest = build_semantic_index(
            (args.source2, args.source3),
            args.index,
            args.manifest,
            config,
            args.model or DEFAULT_MODEL,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return
    if args.command == "phase2-semantic-union":
        from .semantic import SemanticConfig, union_semantic_candidates

        config = SemanticConfig(
            device=args.device,
            batch_size=args.batch_size,
            top_k=args.semantic_top_k,
            union_cap=args.union_cap,
            max_pool_per_source=args.max_pool_per_source,
            probe_radius=args.probe_radius,
            lsh_bits=args.lsh_bits,
            lsh_seed=args.lsh_seed,
        )
        report = union_semantic_candidates(
            args.semantic_index,
            args.source1,
            args.lexical,
            args.output,
            args.report,
            config,
            args.ids,
            args.provenance,
            args.model,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    if args.command == "phase2-generate":
        requested = load_requested_ids(args.ids) if args.ids else None
        if args.truth and requested is None:
            raise ValueError("--truth requires --ids so truth cannot leak outside a frozen split")
        truth = load_phase2_truth(args.truth, requested) if args.truth else None
        if truth is not None:
            frozen_loop = load_requested_ids(split_dir() / "loop_ids.txt")
            if requested != frozen_loop:
                raise ValueError("Phase 2 labeled evaluation is restricted to the frozen loop split")
        config = Phase2Config(
            cap=args.cap, source_floor=args.source_floor, rescue_quota=args.rescue_quota
        )
        report = generate_phase2(
            args.index,
            args.source1,
            args.output,
            config,
            requested,
            truth,
            args.provenance,
            args.misses,
            () if args.no_sweep else PHASE2_CAP_SWEEP,
            () if args.no_sweep else RESCUE_QUOTA_SWEEP,
            args.resources,
        )
        if truth is not None:
            report["selection_split"] = "loop"
        write_json(report, args.report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    requested = load_requested_ids(args.ids) if args.ids else None
    queries = load_queries(args.source1, requested)
    truth = load_truth(args.truth, {query.entity_id for query in queries}) if args.truth else None
    report = generate(
        args.index, queries, args.output, args.cap, args.provenance, truth,
        CAP_SWEEP if args.sweep else (),
        args.workers,
        args.misses,
    )
    write_report(report, args.report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
