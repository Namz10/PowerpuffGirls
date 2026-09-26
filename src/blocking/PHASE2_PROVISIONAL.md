# Provisional Phase 2 blocker

Status: **implementation available for development and `loop` experiments; not
selected, frozen, or approved as a Phase 2 gate**

The Phase 2 blocker is isolated in `src/blocking/phase2.py`. It does not modify
the frozen `phase1-raw-v1` implementation or its artifacts.

## Implemented channels

- raw exact-name, exact-address, and rare-token fallback;
- canonical and accent-folded exact name;
- canonical exact address and rare name/address tokens;
- romanized exact and rare-token retrieval for cross-script names;
- boundary-aware romanized character trigrams;
- exact postal retrieval;
- conservative deterministic phonetic rescue; and
- strict country and target-source separation.

The union ranker applies a strict global cap, an opportunity floor for S2 and
S3, and a separate quota for candidates supported only by high-collision rescue
channels. Candidate order and all tie breaks are deterministic.

Canonical records are computed while the disk-backed SQLite index is built.
This avoids requiring pandas or a multi-gigabyte intermediate Parquet file in
the blocker. The representation normalizer version is nevertheless recorded in
the index and manifests.

## Build and run on the frozen loop split

```bash
python3.11 -m src.blocking.cli phase2-build-index \
  --source2 dataset/train/train_source2.tsv \
  --source3 dataset/train/train_source3.tsv \
  --index artifacts/blocking/train_canonical_v1.sqlite \
  --manifest artifacts/blocking/train_canonical_v1_manifest.json

python3.11 -m src.blocking.cli phase2-generate \
  --index artifacts/blocking/train_canonical_v1.sqlite \
  --source1 dataset/train/train_source1.tsv \
  --ids src/eval/splits/loop_ids.txt \
  --truth dataset/train/train_ground_truth.tsv \
  --cap 50 --rescue-quota 10 \
  --output artifacts/blocking/phase2_loop_candidates.tsv \
  --provenance artifacts/blocking/phase2_loop_provenance.tsv \
  --misses artifacts/blocking/phase2_loop_misses.tsv \
  --report artifacts/blocking/phase2_loop_report.json
```

The report contains raw-only, canonical-only, and union metrics; cap and rescue
quota sweeps and their joint selection surface; channel-level total and
incremental recall; source, country, script, and truth-cardinality slices; a
deterministic 2,000-resample paired bootstrap; a recall/width Pareto frontier;
runtime and peak RSS; and input/output fingerprints.

## Selection guardrails

- Use labeled truth only for the frozen 25,000-ID `loop` split.
- Do not run a provisional Phase 2 comparison on `report`.
- A challenger is promotable only when its paired-bootstrap 95% lower bound is
  above zero and it lies on the supported recall/width Pareto frontier.
- Do not create the 400k matcher handoff, freeze a Phase 2 configuration, or
  write `artifacts/gates/phase_2.json` until Phase 1 is green.

## Verification

```bash
python3.11 -m unittest -v tests.blocking.test_phase2 tests.blocking.test_blocking
```
