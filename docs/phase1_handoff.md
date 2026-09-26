# Phase 1 handoff — Person 1 (Dishita)

Status: **evaluation implementation mostly complete; Phase 1 integration gate pending**

This handoff describes the repository as it exists now. The [final build plan](final_build_plan.md) is authoritative; implementation and tests are the evidence for completed work.

## Completed deliverables

### Frozen evaluation split

Person 1 implemented the deterministic `fit` / `loop` / `report` split under `src/eval/`.

| Artifact | Location |
|---|---|
| Split protocol | `src/eval/split_protocol.py` |
| Split builder and checker | `src/eval/build_split.py` |
| Reproducibility contract | `src/eval/SPLIT.md` |
| Frozen ids | `src/eval/splits/{fit,loop,report}_ids.txt` |
| Counts and fingerprints | `src/eval/splits/manifest.json` |

The frozen cardinalities are:

| Split | Source 1 ids |
|---|---:|
| `fit` | 1,961,144 |
| `loop` | 25,000 |
| `report` | 220,677 |
| Total | 2,206,821 |

Do not regenerate or redistribute these ids casually. A reviewed split change must update the id files, `SPLIT.md`, the manifest, and all dependent fingerprints together.

### Official metric implementation

`src/eval/score.py` implements the unweighted mean of per-entity F₀.₅ with the required edge cases:

- both sets empty: `1.0`;
- exactly one set empty: `0.0`;
- non-empty disjoint sets: finite `0.0`;
- predictions are parsed as sets; and
- the full-train predict-nothing baseline is exactly `123247 / 2206821` (`0.0558482088035233` when printed to 16 decimal places).

The scorer is covered by `tests/eval/test_score.py`. Use it as the only source of local score values.

### Difficulty-pack tooling and slice schema

| Artifact | Status |
|---|---|
| `src/eval/difficulty_pack.py` | Implemented and covered by synthetic determinism tests. |
| `src/eval/difficulty_pack/manifest.json` | Present; records the expected 330-row pack and its fingerprint. |
| `src/eval/difficulty_pack/pack.tsv` | **Not present in this checkout.** TSV files are ignored repository-wide. Regenerate and verify it before treating the reading pack as available. |
| `src/eval/slice_schema.json` | Present, version `1.0`, with 11 slice definitions. |
| `tests/eval/test_difficulty_pack.py` | Covers helpers, format, fit-only membership, and deterministic synthetic builds. |
| `tests/eval/test_slice_schema.py` | Covers schema validation and byte stability. |

The `short_name` and `generic_name` cutoffs remain deliberately unfrozen. The script slice requires the Phase 2 Unicode-block gold join, and prediction-level slices require actual prediction files.

To recreate the local reading pack from the challenge data:

```bash
python3.11 -m src.eval.difficulty_pack
```

Confirm that the generated file matches the fingerprint in its manifest. Do not commit challenge-derived TSV data unless the team explicitly changes the repository data policy.

## Required teammate handoffs

These Phase 1 inputs are not present yet:

| Owner | Required handoff | Current status |
|---|---|---|
| Shriya | Canonical schema/version contract and golden examples | Pending; `src/represent/` is absent. |
| Srishti | Candidate TSV/Parquet, width/recall report, and manifest | Pending; `src/blocking/` is absent. |
| Namita | Prediction TSV, 50k timing/memory projection, and model manifest | Pending; `src/matching/` is absent. |

`src/pipeline/`, `output/`, and `artifacts/gates/` are also absent. Those absences prevent the integrated Phase 1 gate from passing; they do not invalidate Person 1's completed scorer and split work.

## Remaining Person 1 work

After the teammate handoffs arrive, Person 1 must:

1. prove every predicted match is in the corresponding candidate set;
2. run the official validator at `docs/validate_submission.py` with id checks;
3. score the raw-field pipeline once on `report` without using that result for tuning;
4. record the 50k timing projection and confirm capacity for a full run plus one rerun;
5. upload exactly one predict-nothing format probe and record portal status, encoding/header acceptance, and public score;
6. freeze the integrated schemas, configurations, inputs, and output fingerprints; and
7. record the passing gate in `artifacts/gates/phase_1.json`.

## Phase 1 gate status

| Gate condition | Status |
|---|---|
| Scorer tests are finite and green, including the disjoint case. | Ready to verify from the committed tests. |
| A raw-field pipeline produces candidates, matches, and a `report` score. | Blocked on candidate and matching handoffs. |
| Matches are a subset of candidates and both validators pass. | Blocked on output files and the subset checker. |
| The 50k timing leaves room for a full run and rerun. | Blocked on Namita's timing report. |
| The portal probe is recorded. | Pending. |
| Integrated schema and artifact fingerprints are frozen. | Pending teammate and pipeline artifacts. |

Phase 2 must not begin until every row above passes and the gate evidence file exists.

## Verification commands

Run from the repository root with Python 3.11:

```bash
python3.11 -m src.eval.build_split --check
python3.11 -m unittest \
  tests.eval.test_split \
  tests.eval.test_split_artifacts \
  tests.eval.test_score \
  tests.eval.test_slice_schema \
  tests.eval.test_difficulty_pack
```

Before modifying evaluation behavior, read these files in order:

1. `docs/final_build_plan.md`
2. `docs/phase1_handoff.md`
3. `src/eval/SPLIT.md`

Any change to a frozen contract requires review and updated tests, manifests, and fingerprints in the same change.
