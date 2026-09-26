# Final build plan — four sequential integration phases

Status: **finalized for implementation**

This document is the single source of truth for architecture and execution. Earlier role plans, consolidation drafts, and planning audits are superseded.

Implementation branch owner after handoff: **Dishita**

## Team and fixed ownership

| Owner | Role | Writes | Decides |
|---|---|---|---|
| Dishita (Person 1) | Evaluation and release gate | `src/eval/`, split files, score/slice/CI reports, package checklist | Which number is trusted and whether a file may be uploaded |
| Shriya (Person 2) | Representation | `src/represent/`, canonical Parquet, romanization tables/tests, token resources | How raw multilingual text becomes comparable without losing the original |
| Srishti (Person 3) | Candidate generation | `src/blocking/`, candidate reports/manifests, `candidate_pairs.tsv` | Which target records reach the matcher and at what width |
| Namita (Person 4) | Match decisions | `src/matching/`, model/calibration artifacts, drift report, `matching_results.tsv` | Which candidates are returned, including the empty set |

Each owner commits only within the listed subsystem unless the affected owner reviews the change. `src/pipeline/` is changed at phase integration checkpoints by the two owners on either side of the handoff. Submission-document ownership is defined in Phase 4 below.

## Execution rules

The phases below are sequential: Phase N+1 does not begin until the Phase N exit gate is recorded in `artifacts/gates/phase_N.json`. Work inside a phase may run in parallel.

- Use Python 3.11, UTF-8, explicit tab parsing, seed 42, deterministic ordering, relative configuration, and fingerprinted inputs/artifacts.
- `fit` trains; the 25,000-id `loop` selects caps, quotas, owner behavior, thresholds, and set rules; `report` gets only the predeclared Phase 1 readiness score and the locked Phase 3 confirmation.
- A challenger replaces an incumbent only when the 95% paired-bootstrap interval for its `loop` macro-F₀.₅ gain, using at least 2,000 seeded resamples, has a lower bound above zero. If the interval crosses zero, keep the simpler incumbent unless fixing a demonstrated correctness defect.
- Candidate and matching TSVs always contain one row per requested Source 1 id. Every match must be a candidate. Empty lists are valid.
- Every item labelled "Required work" and every exit-gate condition is a **Must**. Work that directly strengthens a Must is a **Should**. Unlisted exploratory work is a **Could** and is cut first when time or capacity is tight.
- No external lookup, registry, geocoder, search API, identity enrichment, or unapproved model weight is used.

## Phase 1 — prove the raw end-to-end spine

**Purpose:** remove integration and portal risk before canonical representation becomes a dependency.

**Entry:** the repository, official input files, and Python 3.11 environment are available.

### Parallel work

| Owner | Required work | Handoff |
|---|---|---|
| Dishita | Freeze `fit`/25k `loop`/`report`; publish `SPLIT.md`; implement the stdlib scorer and tests for PDF example, empty/empty, each one-empty case, non-empty disjoint sets, and predict-nothing baseline; publish difficulty pack and slice schema. | Split id files, scorer command, baseline score, test log |
| Shriya | Freeze the canonical schema, including original `normalized_name`, separate `romanized_name`, source-script metadata, one `postal_code`, and the France fields. Implement a small golden smoke set before the full normalizer. | Schema/version contract and golden examples |
| Srishti | Build same-country, source-separated raw exact and rare-token indices; produce deterministic candidates and miss reasons for all 25k `loop` ids; produce the raw candidate set needed for the readiness `report` run. | Candidate TSV/Parquet, width/recall report, manifest |
| Namita | Implement minimum pair features and pass-1 LightGBM/global-threshold baseline on Srishti's actual candidate distribution; time a 50k-entity inference sample; output raw-baseline predictions. | Prediction TSV, timing/memory projection, model manifest |

### Integration and exit gate

Dishita runs the subset checker, official validator, and the predeclared raw-field `report` readiness score. That score is logged but may not select features, caps, or thresholds. The team also uploads exactly one predict-nothing format probe and records portal `SCORED` status, encoding/header acceptance, and the public score.

Phase 1 passes only when:

1. scorer tests are finite and green, including non-empty disjoint truth/prediction;
2. a real raw-field pipeline produces candidates, matches, and a `report` macro F₀.₅;
3. all matches are candidates and both validators pass;
4. the 50k timing projects enough time for a full run, validation, and one rerun;
5. the portal probe result is recorded; and
6. schema and artifact fingerprints are frozen.

## Phase 2 — harden representation and candidate recall

**Purpose:** close the audited cross-script and France gaps, then lock the smallest defensible candidate frontier.

**Entry:** Phase 1 gate is green. The raw pipeline remains a working fallback.

### Parallel work

| Owner | Required work | Handoff |
|---|---|---|
| Shriya | Ship NFKC/original-script canonicalization; deterministic offline romanization for Devanagari, Kannada, Tamil, Telugu, Bengali, Gujarati, and Malayalam; accent-folded Latin view; French `SAS`, `SASU`, `EURL`, `SCI`, `SNC`, `SC`, `BP`/boîte postale, ordinal, postal, and CEDEX handling; per-country train-only boilerplate plus global fallback; per-country IDF, using provided France test text only for France IDF. | Canonical Parquet, token resources, version hash, idempotency/golden test report, before/after sheet |
| Srishti | Compare raw-only, canonical-only, and union; add address/postal retrieval, romanized exact/token/ngram rescue, and deterministic phonetic rescue; report incremental recall/width by channel and script slice; sweep caps/quotas only on `loop`; apply paired-bootstrap promotion and Pareto filtering. | Frozen blocker config, miss TSV, candidate report and manifest |
| Dishita | Gold-join Unicode blocks to separate true Indic from accented Latin; report candidate oracle, link/complete-entity recall, widths, singleton behavior, source/country/script slices, and bootstrap intervals; attribute every miss. | Signed selection report and dominant miss list |
| Namita | Finalize pair-feature schema on actual candidates, including original/romanized/phonetic evidence; ensure chunked feature generation fits the measured budget; do not tune final thresholds yet. | Feature schema/hash and capacity report |

### Integration and exit gate

Phase 2 passes only when:

1. all romanization and French Must tests pass and unknown code points are preserved;
2. country remains an open equality label and a synthetic France-to-France retrieval works;
3. the frozen blocker is a supported Pareto point on the 25k `loop`, with no unexplained source/country/script collapse;
4. cross-script improvement and added width are explicitly measured;
5. Srishti generates the exact frozen blocker candidates for Namita's 400k `fit` sample; and
6. candidate configuration, normalizer version, inputs, runtime, memory, and outputs are hashed in the manifest.

## Phase 3 — train, calibrate, and lock the operating point

**Purpose:** choose match behavior with powered comparisons, then confirm it once on the untouched competitive report point.

**Entry:** Phase 2 blocker and 400k `fit` candidates are frozen.

### Parallel work

| Owner | Required work | Handoff |
|---|---|---|
| Namita | Train 5-fold GroupKFold pass-1/pass-2 LightGBM; average fold models at inference; fit global and US/India isotonic calibrators on OOF `fit` scores; keep a country calibrator only if it ties/beats global OOF calibration; run leave-one-country-out; compare one-owner off/on; directly grid `k` including zero by predeclared candidate-count bucket; compare global and per-source thresholds. | Fold models, calibrators, ablation table, locked decision config |
| Dishita | Score every candidate operating point on `loop`; compute paired-bootstrap intervals; enforce the promotion rule; audit singleton, script, source, list-length, stolen-id, false-merge, and false-miss slices. | Signed lock report and selected config hash |
| Srishti | Reproduce `loop` candidates from the manifest; repair only proven retrieval/index correctness defects; produce locked `report` candidates after Namita's decision rule is fixed. | Reproduction proof and `report` candidates |
| Shriya | Reproduce canonical artifacts from raw inputs; repair only proven information-loss or normalization correctness defects; finish measured representation documentation. | Reproduction proof and documentation tables |

### Integration and exit gate

Dishita performs the single locked competitive `report` confirmation. Do not return to `loop` to chase a disappointing `report` score; only a demonstrated correctness/packaging defect can reopen a component, and it must invalidate and rerun the affected gate.

Phase 3 passes only when:

1. the selected operating point has a config hash and a bootstrap-supported justification;
2. the one-owner decision records that train uniqueness is proven but test/France uniqueness is only an assumption;
3. fold-bagged inference, chosen calibration, and direct set rule reproduce deterministically;
4. the locked `report` score, slices, loss budget, and candidate oracle are saved;
5. a 100k capacity rehearsal leaves time and disk/memory margin for full test plus one rerun; and
6. no Must defect remains open.

## Phase 4 — full test, drift gate, package, and submit

**Purpose:** create the two audited outputs reproducibly and make the final upload decision.

**Entry:** Phase 3 config and all artifact versions are frozen.

### Sequential production with parallel verification

1. Shriya materializes or verifies canonical test shards and publishes their version/hash.
2. Srishti runs the frozen blocker and writes `output/candidate_pairs.tsv` plus its side Parquet/report/manifest.
3. Namita scores exactly those candidates with averaged fold models, applies the selected calibration/owner/set rule, and writes `output/matching_results.tsv` plus calibration and France drift reports.
4. Dishita runs subset proof, official validator with `--check-ids`, row/cardinality/UTF-8 checks, archive-layout checks, and a clean-environment reproduction smoke test.

Documentation proceeds in parallel after numbers freeze: Dishita owns §2.1, §5, and compilation; Shriya owns representation parts of §4 and noise evidence; Srishti owns §3 and blocking half of §2.2; Namita owns matching parts of §4 and decision half of §2.2.

### France gate

Against both US and India test predictions, stop for investigation if France:

- has an empty-prediction rate over 2× both references or more than 10 percentage points from the nearer reference;
- has median predicted-list size outside 0.5×–2.0× the nearer reference; or
- has calibrated-score histogram PSI above 0.25 against both references.

Record the selected US/India/global calibrator and all distances. A failure permits data, normalizer, index, or calibrator-fallback investigation; it does not permit unlabeled France threshold tuning. Upload after a failure requires an explicit written disposition signed by all four owners.

### Final exit gate

Phase 4 is complete only when:

1. both TSVs have exactly one valid row per test Source 1 id;
2. every matched id exists, is S2/S3, is unique within its row, and appears in that row's candidates;
3. hashes, manifests, config, environment, and archive layout reproduce;
4. France drift passes or has a four-person written disposition;
5. documentation states that France is locally unlabeled but leaderboard-scored, and that public score is monitored while private remains the main target;
6. Dishita records the local config hash, locked `report` score, public score, public–local gap, validator logs, and chosen upload; and
7. at least one daily upload slot remains for recovery.

## Current implementation handoff

Person 1 has implemented most of the Phase 1 evaluation work. Continue from the [Phase 1 handoff](phase1_handoff.md), which records completed deliverables, missing artifacts, and the remaining integration gate.

Use reviewed implementation branches and preserve phase-gate evidence in `artifacts/gates/`. Do not begin Phase 2 until `artifacts/gates/phase_1.json` records a passing Phase 1 gate.
