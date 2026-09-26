# PowerpuffGirls

Business Entity Resolution Challenge.

## Project documentation

- [Final build plan](docs/final_build_plan.md) — authoritative architecture, execution order, ownership, handoffs, and exit gates.
- [Phase 1 handoff](docs/phase1_handoff.md) — current owner-by-owner implementation status and remaining gate work.
- [Phase 1 raw-blocker report](src/blocking/PHASE1_REPORT.md) — measured cap frontier and selected operating point.
- [Candidate-to-matcher contract](src/blocking/CANDIDATE_CONTRACT.md) — exact inference-set and provenance schema.
- [Problem understanding and research](docs/problem_understanding_and_research.md) — background analysis and challenge constraints.
- [Problem statement](docs/Problem%20Statement.pdf) and [challenge guidelines](docs/guidelines_and_key_instructions_amazon_ml_challenge_2026.pdf) — organizer-provided requirements.
- [Documentation template](docs/Documentation_template.md) — required submission documentation structure.

## Phase 1 candidate generation

The blocker uses only Python 3.11 and SQLite FTS5. It discovers countries from
the supplied data (including France), keeps S2/S3 indices separate, and never
performs external business lookup.

```bash
python3.11 -m src.blocking.cli build-index \
  --source2 dataset/train/train_source2.tsv \
  --source3 dataset/train/train_source3.tsv \
  --index artifacts/blocking/train_raw.sqlite \
  --manifest artifacts/blocking/train_index_manifest.json

python3.11 -m src.blocking.cli generate \
  --index artifacts/blocking/train_raw.sqlite \
  --source1 dataset/train/train_source1.tsv \
  --ids src/eval/splits/loop_ids.txt \
  --truth dataset/train/train_ground_truth.tsv \
  --cap 50 --output artifacts/blocking/loop_candidate_pairs.tsv \
  --provenance artifacts/blocking/loop_candidate_provenance.tsv \
  --report artifacts/blocking/loop_selected_report.json --workers 4
```

For final test generation, build the index from `dataset/test/test_source2.tsv`
and `test_source3.tsv`, omit `--ids` and `--truth`, retain the selected
`--cap 50`, and write `--output output/candidate_pairs.tsv`. The generated TSV
contains the exact required header and one row per test S1 ID, including empty
lists.

The final build plan supersedes earlier individual, consolidated, and audit plans.
