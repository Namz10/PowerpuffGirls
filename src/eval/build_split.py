"""Freeze fit / loop / report and record SHA-256 fingerprints."""

import json
from pathlib import Path

from src.eval.config import (
    LOOP_SIZE,
    REPO_ROOT,
    SEED,
    SPLIT_DIR_RELATIVE,
    SPLIT_MD_RELATIVE,
    TRAIN_DIR_RELATIVE,
    train_dir,
)
from src.eval.fingerprint import sha256_file
from src.eval.split_protocol import allocate, assign, stratum_key

SOURCE1_NAME = "train_source1.tsv"
GOLD_NAME = "train_ground_truth.tsv"


def _rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        header = handle.readline()
        if not header:
            raise ValueError(f"empty file: {path.name}")
        if "\t" not in header:
            raise ValueError(f"{path.name} is not tab-separated")
        header_cols = header.rstrip("\n").split("\t")
        for line_number, line in enumerate(handle, start=2):
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            yield line_number, header_cols, parts


def load_records(train: Path) -> tuple[dict[tuple[str, str], list[str]], dict]:
    source_path = train / SOURCE1_NAME
    gold_path = train / GOLD_NAME
    countries: dict[str, str] = {}
    bad_source = 0
    for line_number, header, parts in _rows(source_path):
        if header[:4] != ["entity_id", "business_name", "business_address", "country"]:
            raise ValueError(f"unexpected source1 header: {header}")
        if len(parts) != 4 or not parts[0] or not parts[3]:
            bad_source += 1
            continue
        if parts[0] in countries:
            raise ValueError(f"duplicate source1 id {parts[0]} at line {line_number}")
        countries[parts[0]] = parts[3]
    if bad_source:
        raise ValueError(f"{bad_source} source1 rows are not four non-empty id/country fields")

    lengths: dict[str, int] = {}
    for line_number, header, parts in _rows(gold_path):
        if header[:2] != ["source1_entity_id", "matched_entity_ids"]:
            raise ValueError(f"unexpected ground-truth header: {header}")
        if len(parts) != 2:
            raise ValueError(f"ground truth line {line_number} does not have two columns")
        source_id = parts[0]
        if source_id in lengths:
            raise ValueError(f"duplicate ground-truth id {source_id}")
        raw = parts[1].strip()
        matched = raw.split(",") if raw else []
        if len(matched) != len(set(matched)) or any(not item for item in matched):
            raise ValueError(f"bad match list for {source_id}")
        lengths[source_id] = len(matched)

    if set(countries) != set(lengths):
        raise ValueError("source1 ids and ground-truth ids differ")

    strata: dict[tuple[str, str], list[str]] = {}
    for source_id, country in countries.items():
        strata.setdefault(stratum_key(country, lengths[source_id]), []).append(source_id)
    stats = {
        "source1_rows": len(countries),
        "countries": sorted(set(countries.values())),
    }
    return strata, stats


def _write_ids(path: Path, ids: list[str]) -> None:
    path.write_text("".join(f"{item}\n" for item in ids), encoding="utf-8", newline="\n")


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def write_split_md(manifest: dict) -> None:
    strata_lines = [
        "| Country | Bucket | Size | Report | Loop | Fit |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in manifest["strata"]:
        strata_lines.append(
            f"| {row['country']} | {row['bucket']} | {row['size']} | {row['report']} | {row['loop']} | {row['fit']} |"
        )
    counts = manifest["counts"]
    fingerprints = manifest["artifacts"]
    text = f"""# SPLIT

Frozen Source 1 assignment for evaluation. Do not redraw.

## Contract

- Unit is the Source 1 `entity_id`. A gold link is never assigned apart from its Source 1 id.
- Strata are observed country × gold-list bucket `{{0, 1, 2–3, 4–5, 6+}}`. Length 11 folds into `6+`. Countries are whatever labels are in the file. They are not restricted to `{{US, India}}`.
- `report` receives `(stratum size × 10) // 100` ids from each stratum. That is the floor of 10 percent.
- `loop` receives exactly {LOOP_SIZE} ids drawn from outside `report`. Within that budget, seats are proportional to stratum size by the largest-remainder method: base = `(25000 × size) // total`, and leftover seats go to the largest `(25000 × size) % total`, ties broken by country then bucket order.
- `fit` is every remaining Source 1 id.
- `report` is scored only for the predeclared Phase 1 raw-pipeline readiness run, then left untouched until the Phase 3 operating point is locked on `loop`. It does not select features, caps, quotas, thresholds, or other loop decisions.
- No threshold, cap, quota, or set rule is chosen on `fit`.

## Assignment

Seed `{SEED}` on CPython {manifest["python_required"]}. One `random.Random({SEED})` walks strata in `(country, bucket)` order. Inside a stratum the ids are sorted, shuffled, then cut: report, then loop, then fit. Published files are sorted lexicographically, one id per line, UTF-8, LF, trailing newline, no header.

## Cardinalities

| Split | Ids |
|---|---:|
| fit | {counts["fit"]} |
| loop | {counts["loop"]} |
| report | {counts["report"]} |
| all Source 1 | {counts["source1"]} |

{chr(10).join(strata_lines)}

## Reproducibility

Rebuild with `python3.11 -m src.eval.build_split` from the repository root. Check with `python3.11 -m src.eval.build_split --check`. Input location defaults to `{TRAIN_DIR_RELATIVE.as_posix()}` and may be overridden with `EVAL_TRAIN_DIR`. Committed config stores that relative path only.

## Fingerprints

SHA-256 of the exact file bytes.

| File | SHA-256 |
|---|---|
| `{fingerprints["fit"]["path"]}` | `{fingerprints["fit"]["sha256"]}` |
| `{fingerprints["loop"]["path"]}` | `{fingerprints["loop"]["sha256"]}` |
| `{fingerprints["report"]["path"]}` | `{fingerprints["report"]["sha256"]}` |
| `{manifest["inputs"]["train_source1"]["path"]}` | `{manifest["inputs"]["train_source1"]["sha256"]}` |
| `{manifest["inputs"]["train_ground_truth"]["path"]}` | `{manifest["inputs"]["train_ground_truth"]["sha256"]}` |
| `{manifest["manifest_path"]}` | `{manifest["manifest_sha256"]}` |
"""
    (REPO_ROOT / SPLIT_MD_RELATIVE).write_text(text, encoding="utf-8", newline="\n")


def build() -> dict:
    train = train_dir()
    strata, stats = load_records(train)
    sizes = {key: len(ids) for key, ids in strata.items()}
    allocation = allocate(sizes)
    assigned = assign(strata, allocation, SEED)
    out = REPO_ROOT / SPLIT_DIR_RELATIVE
    out.mkdir(parents=True, exist_ok=True)
    for name in ("fit", "loop", "report"):
        _write_ids(out / f"{name}_ids.txt", assigned[name])

    manifest = {
        "seed": SEED,
        "python_required": "3.11",
        "loop_size": LOOP_SIZE,
        "report_rule": "(stratum_size * 10) // 100",
        "loop_rule": "largest remainder of 25000 proportional to stratum size, outside report",
        "counts": {
            "fit": len(assigned["fit"]),
            "loop": len(assigned["loop"]),
            "report": len(assigned["report"]),
            "source1": stats["source1_rows"],
        },
        "countries": stats["countries"],
        "strata": [
            {
                "country": country,
                "bucket": bucket,
                **allocation[(country, bucket)],
            }
            for country, bucket in sorted(allocation, key=lambda key: (key[0], key[1]))
        ],
        "inputs": {},
        "artifacts": {},
    }
    for label, filename in (
        ("train_source1", SOURCE1_NAME),
        ("train_ground_truth", GOLD_NAME),
    ):
        path = train / filename
        manifest["inputs"][label] = {
            "path": TRAIN_DIR_RELATIVE.joinpath(filename).as_posix(),
            "sha256": sha256_file(path),
        }
    for name in ("fit", "loop", "report"):
        path = out / f"{name}_ids.txt"
        manifest["artifacts"][name] = {
            "path": _relative(path),
            "count": len(assigned[name]),
            "sha256": sha256_file(path),
        }
    manifest_path = out / "manifest.json"
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(encoded, encoding="utf-8", newline="\n")
    manifest["manifest_path"] = _relative(manifest_path)
    manifest["manifest_sha256"] = sha256_file(manifest_path)
    write_split_md(manifest)
    return manifest


def check() -> None:
    train = train_dir()
    strata, stats = load_records(train)
    allocation = allocate({key: len(ids) for key, ids in strata.items()})
    expected = assign(strata, allocation, SEED)
    out = REPO_ROOT / SPLIT_DIR_RELATIVE
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    seen = set()
    for name in ("fit", "loop", "report"):
        path = out / f"{name}_ids.txt"
        text = path.read_text(encoding="utf-8")
        ids = text.splitlines()
        if ids != expected[name]:
            raise SystemExit(f"{name} ids do not match the seeded assignment")
        if ids != sorted(ids):
            raise SystemExit(f"{name} is not lexicographically sorted")
        if any(not item.startswith("S1-") for item in ids):
            raise SystemExit(f"{name} contains a non-S1 id")
        if sha256_file(path) != manifest["artifacts"][name]["sha256"]:
            raise SystemExit(f"{name} fingerprint does not match manifest")
        overlap = seen.intersection(ids)
        if overlap:
            raise SystemExit(f"{name} overlaps another split")
        seen.update(ids)
    if len(seen) != stats["source1_rows"]:
        raise SystemExit("split does not cover every Source 1 id")
    if manifest["counts"]["loop"] != LOOP_SIZE:
        raise SystemExit("loop cardinality is not 25000")
    for label, filename in (
        ("train_source1", SOURCE1_NAME),
        ("train_ground_truth", GOLD_NAME),
    ):
        digest = sha256_file(train / filename)
        if digest != manifest["inputs"][label]["sha256"]:
            raise SystemExit(f"{filename} fingerprint does not match manifest")
    print(
        f"PASS fit={manifest['counts']['fit']} "
        f"loop={manifest['counts']['loop']} "
        f"report={manifest['counts']['report']}"
    )


def main() -> None:
    import sys

    if "--check" in sys.argv:
        check()
    else:
        manifest = build()
        print(
            f"WROTE fit={manifest['counts']['fit']} "
            f"loop={manifest['counts']['loop']} "
            f"report={manifest['counts']['report']}"
        )
        check()


if __name__ == "__main__":
    main()
