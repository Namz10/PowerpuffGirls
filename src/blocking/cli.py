"""Command-line entry point for Phase-1 indexing, cap selection, and generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .generate import CAP_SWEEP, choose_cap, generate, load_queries, load_requested_ids, load_truth, write_report
from .index import build_index, write_manifest


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
    return result


def main() -> None:
    args = parser().parse_args()
    if args.command == "build-index":
        manifest = build_index((args.source2, args.source3), args.index)
        write_manifest(manifest, args.manifest)
        print(json.dumps(manifest, indent=2, sort_keys=True))
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
