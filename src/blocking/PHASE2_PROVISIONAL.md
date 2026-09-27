# Phase 2 frozen blocker

Status: **frozen and approved by the passing Phase 2 gate**

The selected configuration is `cap=50`, `source_floor=2`, and
`rescue_quota=10` (with the remaining retrieval bounds recorded in
`artifacts/blocking/phase2_blocker_freeze.json`). The formal gate is
`artifacts/gates/phase_2.json`.

The Phase 2 blocker is isolated in `src/blocking/phase2.py`. It does not modify
the frozen `phase1-raw-v1` implementation or its artifacts.

The default path is CPU-first and streaming: raw/canonical records live in
SQLite, every retrieval channel has a posting/pool bound, and only the selected
candidate rows are written. It has no GPU, PyTorch, or model dependency. An
optional bounded semantic challenger is documented in
`src/blocking/SEMANTIC_RETRIEVAL.md`; it incrementally embeds only names and
addresses and unions semantic top-K with these lexical candidates.

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

## Selection evidence

- Labeled truth was used only on the frozen 25,000-ID `loop` split.
- Raw-only link recall was `0.6241`; union retrieval reached `0.6945`.
- The paired-bootstrap 95% lower bound was positive, and the selected point is
  on the supported recall/width Pareto frontier.
- The gate records script slices, France retrieval, unknown-code-point
  preservation, resource/version hashes, and the focused-test result.

## Deterministic 400k fit handoff

The fit sample was generated independently of blocker selection, using the
same fixed country × truth-cardinality stratification as the earlier capacity
sample:

```bash
python3.11 -m src.blocking.phase2_freeze sample-fit \
  --source1 dataset/train/train_source1.tsv \
  --truth dataset/train/train_ground_truth.tsv \
  --output src/eval/splits/fit400k_ids.txt \
  --manifest artifacts/blocking/phase2_fit400k_manifest.json
```

Candidate generation omitted `--truth` and used the selected configuration.
The frozen output has 400,001 lines including its header: exactly one candidate
row for each of the 400,000 requested fit entities. The freeze binds the
eligible loop report, the 400k sample manifest, and the unlabeled fit report,
and rejects mismatched configs, indices, normalizer/token hashes, sample
hashes, or entity counts. The compact tracked evidence is
`artifacts/blocking/phase2_blocker_freeze.json`,
`artifacts/blocking/phase2_fit400k_report.json`, and
`artifacts/gates/phase_2.json`; generated candidate and provenance TSVs remain
local artifacts.

## Verification

```bash
python3.11 -m unittest -v tests.blocking.test_phase2 tests.blocking.test_blocking
```
