# Phase 1 implementation and gate handoff

Status: **Person 1 evaluation, Person 2 representation, and Person 3 blocking are implemented; Person 4 matching and the Person 1 integration gate remain**

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
EVAL_TRAIN_DIR=dataset/train python3.11 -m src.eval.difficulty_pack
```

Confirm that the generated file matches the fingerprint in its manifest. Do not commit challenge-derived TSV data unless the team explicitly changes the repository data policy.

## Implementation status by owner

This table reflects the current merged worktree rather than the state when this
handoff was first written.

| Owner | Phase 1 responsibility | Current evidence | Status |
|---|---|---|---|
| Dishita (Person 1) | Frozen split, official scorer, difficulty pack/slices, and release gate | `src/eval/`, `tests/eval/`, and frozen split artifacts are present. The evaluation and blocking suite passes when `EVAL_TRAIN_DIR=dataset/train` is set. | Core evaluation implemented; final integration/release gate remains. |
| Shriya (Person 2) | Canonical schema/version contract and golden examples | `src/represent/`, `tests/represent/`, `artifacts/resources/manifest.json`, and the representation audit are present. Scalar canonicalization and its tests no longer require pandas. | Handoff implemented. |
| Srishti (Person 3) | Raw candidates, width/recall report, miss audit, and manifest | `src/blocking/`, `tests/blocking/`, `src/blocking/PHASE1_REPORT.md`, `src/blocking/phase1_manifest.json`, and `artifacts/blocking/` are present. The frozen `report` candidate run contains 220,677 rows and 7,324,037 pairs. | Handoff implemented. |
| Namita (Person 4) | Minimum pair features, pass-1 matcher, raw predictions, model manifest, and 50k timing/memory projection | The candidate contract was reviewed in `src/blocking/PERSON4_REVIEW.md`, but `src/matching/`, a model manifest, a timing report, and `output/matching_results.tsv` are absent. | **Remaining implementation owner.** |

`output/candidate_pairs.tsv` is present, but it is a test-set candidate artifact;
it does not replace the missing raw-baseline predictions or the frozen-train
`report` macro-F0.5 run. `src/pipeline/` and `artifacts/gates/phase_1.json` are
also absent.

## Remaining work

### Namita (Person 4)

1. implement the Phase 1 minimum pair features and pass-1 matcher against the
   frozen candidate contract;
2. produce raw-baseline predictions, including predictions for the frozen
   `report` split;
3. publish the model/configuration manifest; and
4. record a 50k-entity timing and memory measurement with a full-run-plus-rerun
   capacity projection.

### Dishita (Person 1), after the matching handoff

Dishita must:

1. prove every predicted match is in the corresponding candidate set;
2. run the official validator at `docs/validate_submission.py` with id checks;
3. score the raw-field pipeline once on `report` without using that result for tuning;
4. record the 50k timing projection and confirm capacity for a full run plus one rerun;
5. upload exactly one predict-nothing format probe and record portal status, encoding/header acceptance, and public score;
6. freeze the integrated schemas, configurations, inputs, and output fingerprints; and
7. record the passing gate in `artifacts/gates/phase_1.json`.

The portal upload in item 5 is an external team action. It cannot be completed
from repository implementation alone.

## Phase 1 gate status

| Gate condition | Status |
|---|---|
| Scorer tests are finite and green, including the disjoint case. | **Pass:** the combined evaluation/blocking run completes 38 tests successfully, and the repository dataset path is detected by default. |
| A raw-field pipeline produces candidates, matches, and a `report` score. | Candidates are complete; blocked on Namita's matcher and predictions. The existing readiness report records candidate recall, not macro-F0.5. |
| Matches are a subset of candidates and both validators pass. | The strict subset checker exists and is tested; blocked on `matching_results.tsv` and integrated validator runs. |
| The 50k timing leaves room for a full run and rerun. | Blocked on Namita's timing report. |
| The portal probe is recorded. | Pending external portal upload and evidence. |
| Integrated schema and artifact fingerprints are frozen. | Representation and candidate manifests exist; the matcher, integrated output, and final gate fingerprints remain. |

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
  tests.eval.test_difficulty_pack \
  tests.blocking.test_blocking
```

Before modifying evaluation behavior, read these files in order:

1. `docs/final_build_plan.md`
2. `docs/phase1_handoff.md`
3. `src/eval/SPLIT.md`

Any change to a frozen contract requires review and updated tests, manifests, and fingerprints in the same change.
