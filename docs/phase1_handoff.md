# Phase 1 implementation and gate handoff

Status: **Completed — the repository checks and external portal probe gate passed**

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
| Dishita (Person 1) | Frozen split, official scorer, difficulty pack/slices, and release gate | `src/eval/`, `tests/eval/`, frozen split artifacts, and `artifacts/gates/phase_1.json` are present. All 87 repository tests pass; the portal accepted and evaluated the probe. | Handoff complete; Phase 1 gate passed. |
| Shriya (Person 2) | Canonical schema/version contract and golden examples | `src/represent/`, `tests/represent/`, `artifacts/resources/manifest.json`, and the representation audit are present. Scalar canonicalization and its tests no longer require pandas. | Handoff implemented. |
| Srishti (Person 3) | Raw candidates, width/recall report, miss audit, and manifest | `src/blocking/`, `tests/blocking/`, `src/blocking/PHASE1_REPORT.md`, `src/blocking/phase1_manifest.json`, and `artifacts/blocking/` are present. The frozen `report` candidate run contains 220,677 rows and 7,324,037 pairs. | Handoff implemented. |
| Namita (Person 4) | Minimum pair features, pass-1 matcher, raw predictions, model manifest, and 50k timing/memory projection | `src/matching/`, its tests, the Phase 1 manifest, the trained model, loop/fit predictions, and the completed frozen-report predictions are present. | Handoff complete. |

The frozen `report` run contains 220,677 prediction rows. Its macro-F0.5 is
`0.6753125283185789`, and every emitted match is in the corresponding frozen
candidate row. Its fingerprints are recorded in the matching manifest and the
Phase 1 gate artifact.

## External portal gate completion

The prepared `artifacts/gates/phase_1_predict_nothing_probe.tsv` was accepted
and evaluated by the portal. The portal status was `Evaluated`, the header and
encoding were accepted, and the public score was `0.056`. This satisfies the
required scored/evaluated confirmation. As expected for a predict-nothing
format probe, that score is not a measure of matcher quality.

## Phase 1 gate status

| Gate condition | Status |
|---|---|
| Scorer tests are finite and green, including the disjoint case. | **Pass:** all 87 repository tests pass. |
| A raw-field pipeline produces candidates, matches, and a `report` score. | **Pass:** 220,677 rows; macro-F0.5 `0.6753125283185789`. |
| Matches are a subset of candidates and both validators pass. | **Pass:** strict subset proof, official format/candidate validation, and 10,320,219-target ID-existence validation pass. |
| The 50k timing leaves room for a full run and rerun. | **Recorded:** 1,006.473 seconds for 50k; projected full test plus one rerun is 69,750.3 seconds. |
| The portal probe is recorded. | **Pass:** portal status `Evaluated`; header and encoding accepted; public score `0.056`. |
| Integrated schema and artifact fingerprints are frozen. | **Pass:** model, report candidates/provenance, report predictions, and probe hashes are recorded in `artifacts/gates/phase_1.json`. |

The Phase 1 gate is explicitly `passed` in `artifacts/gates/phase_1.json`; the
Phase 2 entry condition is satisfied.

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
