# Optional Phase 2 semantic retrieval

The canonical SQLite blocker remains the required default. It is CPU-first,
streaming, deterministic, and has no PyTorch, GPU, or model dependency. The
semantic path is an optional challenger and must be evaluated on `loop` before
its candidates are used anywhere else.

## Design

- Only canonicalized business names and addresses are sent to the encoder.
  Entity IDs, country labels, truth, and candidate pairs are never model input.
- S2/S3 records are encoded in bounded batches and appended incrementally to a
  SQLite index as normalized float32 vectors.
- A persisted random-hyperplane signature partitions each country/source
  shard. Querying probes only bounded Hamming-neighbor buckets, then computes
  cosine scores for at most `max_pool_per_source` records per source.
- The union command streams the lexical candidate TSV, preserves every lexical
  candidate in its original order, appends unseen semantic top-K candidates,
  and enforces a strict `union_cap`.
- No command constructs or stores the Source 1 × Source 2/3 Cartesian product.

The default model is multilingual MiniLM. Model loading is lazy, so ordinary
`phase2-build-index` and `phase2-generate` commands work without the optional
packages.

## Installation

Install the PyTorch build appropriate for the machine's CUDA runtime first,
then install:

```bash
python3.11 -m pip install -r src/blocking/requirements-semantic.txt
```

## Build the semantic target index

For an RTX 3050 with 6 GB VRAM, begin at batch size 32. Batch size 64 is the
default and is usually reasonable for MiniLM, but can be reduced to 16 if CUDA
runs out of memory.

```bash
python3.11 -m src.blocking.cli phase2-semantic-build \
  --source2 dataset/train/train_source2.tsv \
  --source3 dataset/train/train_source3.tsv \
  --index artifacts/blocking/train_semantic_v1.sqlite \
  --manifest artifacts/blocking/train_semantic_v1_manifest.json \
  --device cuda --batch-size 32
```

Use `--device cpu` to run the same bounded workflow without CUDA.

## Union semantic top-K with lexical candidates

The following example adds at most 10 semantic results and keeps at most 60
total candidates per entity. `--ids` makes the streamed Source 1 rows align
with the frozen candidate file.

```bash
python3.11 -m src.blocking.cli phase2-semantic-union \
  --semantic-index artifacts/blocking/train_semantic_v1.sqlite \
  --source1 dataset/train/train_source1.tsv \
  --lexical artifacts/blocking/phase2_loop_candidates.tsv \
  --ids src/eval/splits/loop_ids.txt \
  --semantic-top-k 10 --union-cap 60 \
  --max-pool-per-source 2000 --probe-radius 1 \
  --device cuda --batch-size 32 \
  --output artifacts/blocking/phase2_loop_semantic_candidates.tsv \
  --provenance artifacts/blocking/phase2_loop_semantic_provenance.tsv \
  --report artifacts/blocking/phase2_loop_semantic_report.json
```

Semantic promotion follows the same leakage rule as lexical selection: measure
recall/width only on the frozen 25k `loop`, freeze the semantic configuration
and model/index hashes, then regenerate the unlabeled 400k fit handoff. Do not
tune it on `report`.
