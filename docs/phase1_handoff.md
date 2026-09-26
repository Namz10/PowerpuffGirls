# Phase 1 handoff — Person 1 (Dishita)

Status of Person 1's Phase 1 work: **Parts 1–3 are complete. Part 4 is pending.**

Part 4 is the Phase 1 integration and exit gate. It runs later, once the required pipeline artifacts and teammate handoffs exist. Completing Parts 1–3 does not mean the Phase 1 exit gate has passed. `artifacts/gates/phase_1.json` does not exist. No public score has been recorded.

This file was written by inspecting the repository on branch `plan_finalised` (HEAD `cf9932d`, planning documents only). The Person 1 implementation is in the working tree under `src/eval/` and `tests/eval/` and is **untracked**. It has not been committed.

Authority used, in order:

1. `docs/final_build_plan.md` — what Person 1 must do in Phase 1, and what the exit gate requires.
2. The current files under `src/eval/` and `tests/eval/` — what was actually built.
3. `.cursor/plans/consolidated_er_pipeline_cf74755a.plan.md` and `docs/consolidated_er_pipeline_audit.md` — architecture and terminology only.

`docs/build_plan_person1.md` was not used to add scope beyond the final plan.

## What Person 1 owns

From `docs/final_build_plan.md`: Dishita writes `src/eval/`, split files, score/slice/CI reports, and the package checklist, and decides which number is trusted and whether a file may be uploaded.

Phase 1 required work for Dishita, from the same document: freeze `fit` / 25,000-id `loop` / `report`; publish `SPLIT.md`; implement the stdlib scorer and the listed tests, including the predict-nothing baseline; publish a difficulty pack and a slice schema. The named Phase 1 handoff from that row is: split id files, scorer command, baseline score, test log.

Environment contract from the same document: Python 3.11, UTF-8, explicit tab parsing, seed 42, deterministic ordering, relative paths, fingerprinted inputs and artifacts. Verification in this inspection used Python 3.11.14.

---

## Part 1 — Split and reproducibility

**Status: COMPLETE.**

### Files

| Path | Role |
|---|---|
| `src/eval/config.py` | Relative paths, `SEED = 42`, `LOOP_SIZE = 25000`, `REPORT_PERCENT = 10`, buckets `0`, `1`, `2-3`, `4-5`, `6+`. `EVAL_TRAIN_DIR` overrides the training directory. Default training path is `../student_resource/dataset/train`. |
| `src/eval/fingerprint.py` | Streaming SHA-256 of exact file bytes. |
| `src/eval/split_protocol.py` | Bucket, stratum, allocation, assignment. |
| `src/eval/build_split.py` | Writes the id files, `manifest.json`, and `SPLIT.md`. `--check` rebuilds the assignment in memory and compares it to the files. It does not rewrite them. |
| `src/eval/SPLIT.md` | Published contract. |
| `src/eval/splits/fit_ids.txt` | Frozen fit ids. |
| `src/eval/splits/loop_ids.txt` | Frozen loop ids. |
| `src/eval/splits/report_ids.txt` | Frozen report ids. |
| `src/eval/splits/manifest.json` | Counts, strata, seed, input and artifact fingerprints. |
| `tests/eval/test_split.py` | Protocol tests on synthetic strata. |
| `tests/eval/test_split_artifacts.py` | Tests over the committed id files and manifest. |

Package markers: `src/__init__.py`, `src/eval/__init__.py`, `tests/__init__.py`, `tests/eval/__init__.py`.

### Protocol

The unit is the Source 1 `entity_id`. A gold link is never assigned apart from its Source 1 id.

Strata are observed country × gold-list bucket. `bucket_name` maps length `0` → `0`, `1` → `1`, `2–3` → `2-3`, `4–5` → `4-5`, and length `6` or more, including 11, → `6+`. Countries are the labels in the file. The manifest's observed countries are `India` and `US`.

- `report` gets `(stratum_size * 10) // 100` ids from each stratum (floor of 10 percent).
- `loop` gets exactly 25,000 ids from outside `report`. Seats are proportional to stratum size by largest remainder: base = `(25000 * size) // total`, leftover seats go to the largest `(25000 * size) % total`, ties broken by country then bucket order.
- `fit` is every remaining Source 1 id.

Assignment uses one `random.Random(42)`. Strata are walked in `(country, bucket)` order. Inside a stratum the ids are sorted, shuffled, then cut: report, then loop, then fit. Published files are sorted lexicographically, one id per line, UTF-8, LF, trailing newline, no header.

`report` is for the predeclared Phase 1 readiness score and the later locked Phase 3 confirmation. It does not select features, caps, quotas, thresholds, or set rules. No threshold, cap, quota, or set rule is chosen on `fit`.

### Cardinalities

These counts are in `src/eval/splits/manifest.json` and `src/eval/SPLIT.md`. Line counts of the id files were re-counted in this inspection and match.

| Split | Ids |
|---|---:|
| fit | 1,961,144 |
| loop | 25,000 |
| report | 220,677 |
| all Source 1 | 2,206,821 |

The three id sets are disjoint, their union has 2,206,821 ids, every id starts with `S1-`, and each file is lexicographically sorted. `python3.11 -m src.eval.build_split --check` reprinted the assignment from the training files and printed `PASS fit=1961144 loop=25000 report=220677`.

| Country | Bucket | Size | Report | Loop | Fit |
|---|---|---:|---:|---:|---:|
| India | 0 | 49351 | 4935 | 559 | 43857 |
| India | 1 | 47468 | 4746 | 538 | 42184 |
| India | 2-3 | 361892 | 36189 | 4100 | 321603 |
| India | 4-5 | 323008 | 32300 | 3659 | 287049 |
| India | 6+ | 101469 | 10146 | 1149 | 90174 |
| US | 0 | 73896 | 7389 | 837 | 65670 |
| US | 1 | 71689 | 7168 | 812 | 63709 |
| US | 2-3 | 544161 | 54416 | 6165 | 483580 |
| US | 4-5 | 483064 | 48306 | 5472 | 429286 |
| US | 6+ | 150823 | 15082 | 1709 | 134032 |

### Fingerprints

SHA-256 of the exact file bytes. Recomputed in this inspection. All matched the manifest and `SPLIT.md`.

| File | SHA-256 |
|---|---|
| `src/eval/splits/fit_ids.txt` | `206ba5c0c08e9bef9984ca6370e0845b84757d5d1a736b2de2c7db06982f9d42` |
| `src/eval/splits/loop_ids.txt` | `ffc47cbc3b5585c2ac163335ec518a5efc220e5dd49066788cf97de796abe3ac` |
| `src/eval/splits/report_ids.txt` | `0f33644ee6a55a5d1df3ea176fe37aef56e1b3d6260f1037602d22d6002fa186` |
| `src/eval/splits/manifest.json` | `b71e79bbb97afd99be4c199d299bda8144c56fe0a5659771a376269dffcadf54` |
| `../student_resource/dataset/train/train_source1.tsv` | `591af0e1dfeb65cab71ea6ee8cb69df00f92d6ba6fa79e05746c938775d14973` |
| `../student_resource/dataset/train/train_ground_truth.tsv` | `70bc1d8a16c667e0155c2105d0ab2ebe41d7e7a85d8a529e3ca81c6c3a5af037` |

`SPLIT.md` records the manifest hash. The manifest does not record a hash of `SPLIT.md` itself. The current `SPLIT.md` bytes hash to `140a4716d3e7bcf9fb94c3660310918f0bb9a602702cae5ad30c63b977db2a72`.

### Commands and tests

Safe check (does not rewrite the split):

```bash
python3.11 -m src.eval.build_split --check
```

Result in this inspection: `PASS fit=1961144 loop=25000 report=220677`.

`python3.11 -m src.eval.build_split` without `--check` calls `build()` and rewrites the id files, the manifest, and `SPLIT.md`. Do not run that unless a reviewed redraw is required.

Protocol tests (`tests/eval/test_split.py`, 3 tests): length 11 folds into `6+`; floor-10% report and loop budget of 25,000; assignment is disjoint, sorted, and repeatable.

Artifact tests (`tests/eval/test_split_artifacts.py`, 5 tests): fingerprints match the files; counts match and loop is 25,000; disjoint, complete, sorted, all `S1-`; each stratum's report is `(size * 10) // 100` and the loop seats sum to 25,000; seed is 42. These tests read the split files only. They do not reload the training TSVs. The `--check` command above is the check that reloads training data.

Both modules were included in the suite run recorded at the end of this document.

---

## Part 2 — Scorer, tests, predict-nothing baseline

**Status: COMPLETE.**

### Location and command

Implementation: `src/eval/score.py`. Standard library only. The module docstring states that sklearn is not used.

```bash
python3.11 -m src.eval.score --predict-nothing
python3.11 -m src.eval.score --predict-nothing --gold PATH
python3.11 -m src.eval.score --matching PATH --gold PATH
```

`--predict-nothing` with no `--gold` reads `train_dir() / train_ground_truth.tsv`. The command prints the macro F₀.₅ with 16 digits after the decimal. Omitting both `--matching` and `--gold`, and omitting `--predict-nothing`, exits with `pass --matching and --gold, or --predict-nothing`.

Headers the loader accepts:

- matching / gold: `source1_entity_id`, `matched_entity_ids`
- candidates: `source1_entity_id`, `candidate_entity_ids`

`score_files` scores a matching file against gold. `load_id_lists` is what reads a candidate file when the caller passes the candidate header.

### Metric

Per Source 1 entity, F₀.₅ is `(1.25 * P * R) / (0.25 * P + R)`, where `P` and `R` are set precision and recall on the matched-id sets.

| Case | Result |
|---|---|
| Both sets empty | `1.0` |
| Prediction empty, truth non-empty | `0.0` |
| Truth empty, prediction non-empty | `0.0` |
| Both non-empty and overlap is 0 | `0.0`, and the value is finite. Overlap 0 returns before the division. |
| Identical non-empty sets | `1.0` |
| Partial example locked by the test: prediction `{S2-1, S2-2}`, truth `{S2-1, S2-2, S2-3}` | `10/11` |
| PDF example locked by the test: prediction `{S2-00047, S2-00193, S3-00812}`, truth `{S2-00047, S3-00812}` | equals `5/7` to 12 decimal places, and `round(score, 3) == 0.714` |

Macro F₀.₅ is the unweighted mean of the per-entity scores. Entities are scored in sorted id order and summed with `math.fsum`, then divided by the number of entities. A test locks that a perfect singleton plus a 1-of-4 partial scores `(1.0 + 0.625) / 2`, which is the entity mean, and rejects the link-weighted alternative. Repeated calls on the same inputs return the same float. A non-finite score raises `ValueError`.

The prediction id set and the truth id set must be equal. An empty truth mapping raises `ValueError`.

### Parsing

- UTF-8, tab-separated, one row per Source 1 id. A blank line is skipped.
- The file must contain a tab in the header, and the header must equal the expected header after lowercasing and stripping.
- Each data line has exactly two columns. The source id must start with `S1-`. A repeated source id is an error.
- An empty match field is an empty set and is valid.
- A non-empty list is comma-separated. An empty token or a duplicate token is an error. Each id must start with `S2-` or `S3-`.
- Parsed values are sets, so order inside a valid list does not change the score. Duplicates are rejected before the set is built.

### Predict-nothing baseline

`predict_nothing_score` loads the gold file and scores an empty prediction for every gold Source 1 id. Because empty/empty is 1 and empty/non-empty is 0, the score equals the share of Source 1 ids whose gold list is empty.

`tests/eval/test_score.py` locks that value on the full training gold file:

- numerator: `123247`
- denominator: `2206821`
- exact score: `123247 / 2206821`

The CLI's 16-decimal formatting of that ratio is `0.0558482088035233`. The unit test calls `predict_nothing_score` on the real gold file twice and asserts both calls equal that ratio and are finite. This inspection did not invoke the CLI as a separate process; the passing unit test is the check against the file.

### Tests

`tests/eval/test_score.py` has 11 tests: PDF rounding, empty/empty, both one-empty directions, finite disjoint zero, perfect match, partial overlap, unweighted macro, repeated execution, full-train predict-nothing, and a candidate-header file with one populated list and one empty list.

---

## Part 3 — Difficulty pack and slice schema

**Status: COMPLETE.**

This part publishes a reading fixture and a slice-definition file. It does not populate per-slice performance, and it does not do the Phase 2 gold-join, oracle, recall, width, singleton, source/country/script, or bootstrap measurements in `docs/final_build_plan.md`.

### Difficulty pack

| Item | Value |
|---|---|
| Implementation | `src/eval/difficulty_pack.py` |
| Table | `src/eval/difficulty_pack/pack.tsv` |
| Manifest | `src/eval/difficulty_pack/manifest.json` |
| Tests | `tests/eval/test_difficulty_pack.py` (6 tests) |

Columns, in order: `source1_entity_id`, `related_entity_ids`, `kind`, `overlap_bucket`, `reason`.

The file has 331 lines: one header and **330 data rows**. All 330 Source 1 ids are unique. Every one is in `fit_ids.txt`. None is in `loop_ids.txt` or `report_ids.txt`. Related ids are empty or `S2-` / `S3-` ids.

Eleven kinds, 30 rows each. `shortfall` in the manifest is `{}`.

| Kind | Rows |
|---|---:|
| `easy_latin` | 30 |
| `legal_suffix` | 30 |
| `low_overlap` | 30 |
| `accented_latin` | 30 |
| `indic_other_side` | 30 |
| `empty_address_match` | 30 |
| `multi_id` | 30 |
| `unmatched_distractor_near_miss` | 30 |
| `stolen_neighborhood_near_miss` | 30 |
| `singleton_lookalike` | 30 |
| `singleton_isolated` | 30 |

Observed `overlap_bucket` counts in the published TSV: `high` 96, `mid` 54, `none` 60, `na` 120.

Selection, from the implementation and the manifest:

- Drawn from `fit` only.
- Probe pools are the first 40,000 sorted non-singleton fit ids and the first 12,000 sorted singleton fit ids. The manifest records those pool sizes. The manifest field `selection` is `deterministic sort by (kind order, source1_entity_id); no RNG required`. Seed `42` is recorded. The pack is not a `random.Random` sample of all of `fit`.
- Each Source 1 id is used at most once. Rows are then sorted by kind order, then id.
- Gold-derived kinds use the gold target's name and address: `easy_latin` (Latin script, name Jaccard ≥ 0.70, non-empty address, address Jaccard ≥ 0.30), `legal_suffix` (same core tokens after dropping a fixed legal-token set, surface form differs), `low_overlap` (name Jaccard ≤ 0.10), `accented_latin`, `indic_other_side` (Devanagari, Bengali, Gujarati, Tamil, Telugu, Kannada, Malayalam), `empty_address_match`, and `multi_id` (gold-list length 4 or 5).
- Near-miss kinds use a same-country token-overlap search over Source 2 and Source 3: document-frequency cap 200, at most 50 postings kept per token, near-miss Jaccard ≥ 0.5. `unmatched_distractor_near_miss` is a high-overlap id that is gold for nobody. `stolen_neighborhood_near_miss` is a high-overlap id that is gold for a different Source 1 id. `singleton_lookalike` is an empty-gold entity whose best same-country neighbour is at least 0.5. `singleton_isolated` is an empty-gold entity whose best neighbour is at most 0.10.
- The module states that this search is not the candidate blocker and that it does not compute recall, oracle, width, or bootstrap numbers.

`easy_latin` thresholds `0.70` and `0.30` are constants in `difficulty_pack.py`. They are not copied into the manifest's `miner` object. The manifest miner block records `df_cap` 200, `post_cap` 50, `near_miss_min` 0.5, `isolated_max` 0.1, and `low_overlap_max` 0.1.

Pack fingerprint, recomputed and matched to the manifest:

`529371581c832fc73c6355ff615a050a78e43ffd316ce841776553f11476f6ae`

Input fingerprints recorded in the pack manifest, recomputed against the training files and `fit_ids.txt`, all matched:

| Input | SHA-256 |
|---|---|
| `src/eval/splits/fit_ids.txt` | `206ba5c0c08e9bef9984ca6370e0845b84757d5d1a736b2de2c7db06982f9d42` |
| `../student_resource/dataset/train/train_ground_truth.tsv` | `70bc1d8a16c667e0155c2105d0ab2ebe41d7e7a85d8a529e3ca81c6c3a5af037` |
| `../student_resource/dataset/train/train_source1.tsv` | `591af0e1dfeb65cab71ea6ee8cb69df00f92d6ba6fa79e05746c938775d14973` |
| `../student_resource/dataset/train/train_source2.tsv` | `6336c1a055eec79cf8a6d99fdc8d32a2e4d9dc2662e00963cb35d66b89ed09ed` |
| `../student_resource/dataset/train/train_source3.tsv` | `67da22f5151898ff3006febd836c1a159e97ae95efa7257a5aff4fda685e58e9` |

The manifest file's own current SHA-256 is `a40c88af51df92ca3ebaa6caebe38d05cc183cb6e42d56a5e1e54691839dc2b5`. That hash is not stored inside the manifest.

`python3.11 -m src.eval.difficulty_pack` rewrites `pack.tsv` and `manifest.json`. It was not re-run for this handoff. The published bytes were hashed and checked against the manifest.

Tests: tokenisation and Jaccard; overlap-bucket edges; Latin / accented-Latin / Devanagari / Tamil script class; legal-suffix variant; a synthetic build that is byte-identical across two runs, has five columns, unique `S1-` ids, valid related-id prefixes, and kind-then-id order; pack ids come from the supplied fit file.

Deferred limitation: the pack is a fixed example list for reading. It is not a threshold-selection set, and the probe pools cover a prefix of sorted fit ids, not every fit entity.

### Slice schema

| Item | Value |
|---|---|
| Implementation | `src/eval/slice_schema.py` |
| Published schema | `src/eval/slice_schema.json` |
| Schema version | `1.0` |
| Definitions | 11 |
| Tests | `tests/eval/test_slice_schema.py` (7 tests) |

SHA-256 of `slice_schema.json`, recomputed, and equal to `sha256` of `canonical_bytes()`: `950ea4f688f797a9e1fc467a00e8dddc05a13d75a4e00077734a30ea23932cc9`. The in-memory canonical bytes match the file on disk.

These are definitions. No slice has been filled with a performance number.

| Key | Level | When it can be populated | Values |
|---|---|---|---|
| `country` | entity | `phase1` | Open set. Documented categories include `US`, `India`, `France`, `OTHER`. `open_set` is true. |
| `singleton` | entity | `phase1` | Boolean. Gold match list is empty. |
| `gold_list_bucket` | entity | `phase1` | `0`, `1`, `2-3`, `4-5`, `6+`. Length 11 folds into `6+`. |
| `target_empty_address` | entity | `phase1` | Boolean. At least one gold S2/S3 match has an empty `business_address`. |
| `source_composition` | entity | `phase1` | `none`, `s2_only`, `s3_only`, `both`. |
| `short_name` | entity | `phase1` | Boolean. **Cutoff not frozen.** `parameters.frozen` is false. `max_chars` and `max_tokens` are null. `frozen_on` is `fit`. |
| `generic_name` | entity | `phase1` | Boolean. **Cutoff not frozen.** `parameters.frozen` is false. `df_source` is `fit`. |
| `target_script_class` | entity | `after_gold_join` | `latin`, `accented_latin`, `indic`. |
| `cross_country_prediction` | prediction | `prediction_time` | Boolean. Needs a match file. |
| `false_id_type` | prediction | `prediction_time` | `stolen_id`, `unmatched_distractor`. Needs a match file and gold. |
| `predicted_vs_gold_length` | prediction | `prediction_time` | `longer`, `equal`, `shorter`. |

`short_name` and `generic_name` are declared and intentionally unresolved. `SPLIT.md` does not contain a short-name cutoff. `target_script_class` is marked `after_gold_join` because the schema module says it needs the Unicode-block gold join. That join is Phase 2 work in the final plan and has not been done. The three `prediction_time` slices cannot be populated until a prediction file exists. No prediction file is in the repository.

`validate()` requires schema version `1.0`, a non-empty slice list, unique keys, and the fields `key`, `description`, `level`, `phase_available`, `value_type`, `categories`, `open_set`, `source_fields`, `parameters`. Levels are `entity` or `prediction`. Phases are `phase1`, `after_gold_join`, or `prediction_time`. A boolean slice must have empty categories.

Tests: schema validates; the 11 keys above are present; every `phase1` slice is entity-level; the two name cutoffs are flagged unfrozen; `target_script_class` is `after_gold_join` with the three script categories; the three prediction slices are `prediction_time`; canonical bytes are deterministic UTF-8; a bad version and a bad level are rejected.

`python3.11 -m src.eval.slice_schema` rewrites `slice_schema.json`. It was not re-run for this handoff.

The schema module's own comment points at a `person1_slice_tags` column name in `docs/build_plan_person3.md`. That column name is present there. `docs/final_build_plan.md` does not put the slice schema in Dishita's Phase 1 handoff cell. Treat the schema as an additional artifact, described in the next section.

---

## Official Phase 1 handoffs

The handoff column in `docs/final_build_plan.md` is the list below. Presence was checked in this repository. `src/represent/`, `src/blocking/`, `src/matching/`, `src/pipeline/`, and `artifacts/` do not exist.

### Dishita (Person 1)

| Handoff | Status | Where |
|---|---|---|
| Split id files | **AVAILABLE NOW** | `src/eval/splits/fit_ids.txt`, `loop_ids.txt`, `report_ids.txt`, plus `manifest.json` and `src/eval/SPLIT.md` |
| Scorer command | **AVAILABLE NOW** | `python3.11 -m src.eval.score` with the flags in Part 2 |
| Baseline score | **AVAILABLE NOW** | Exact ratio `123247 / 2206821`, locked by `tests/eval/test_score.py` |
| Test log | **AVAILABLE NOW as a command and as the result below.** A separate checked-in log file was not found. | Re-run the unittest command in "Verification recorded for this handoff" |

### Shriya (Person 2)

Official handoff: schema/version contract and golden examples.

**EXPECTED / REQUIRED FROM OWNER. PENDING.** `src/represent/` is not in the repository. No canonical schema file or golden-example set was found.

### Srishti (Person 3)

Official handoff: candidate TSV/Parquet, width/recall report, and manifest.

**EXPECTED / REQUIRED FROM OWNER. PENDING.** `src/blocking/` is not in the repository. No `candidate_pairs.tsv`, candidate Parquet, width/recall report, or blocking manifest was found.

### Namita (Person 4)

Official handoff: prediction TSV, timing/memory projection, and model manifest.

**EXPECTED / REQUIRED FROM OWNER. PENDING.** `src/matching/` is not in the repository. No `matching_results.tsv`, 50k timing projection, or model manifest was found.

---

## Additional Person 1 artifacts available for downstream evaluation/integration

`docs/final_build_plan.md` requires Dishita to publish the difficulty pack and the slice schema as Phase 1 work. The handoff cell of that same row does not name them. They are additional artifacts, not a substitute for the official handoff list above.

| Artifact | Path | What it is |
|---|---|---|
| Difficulty pack | `src/eval/difficulty_pack/pack.tsv` | 330 fit-only example rows, 11 kinds × 30. For reading. |
| Difficulty-pack manifest | `src/eval/difficulty_pack/manifest.json` | Counts, miner parameters, probe pools, input fingerprints, pack fingerprint. |
| Slice schema | `src/eval/slice_schema.json` | Version `1.0`. Eleven definitions. Two name cutoffs are unfrozen. No performance table. |
| Slice-schema tests | `tests/eval/test_slice_schema.py` | Validation and byte-stability of the definitions. |
| Difficulty-pack tests | `tests/eval/test_difficulty_pack.py` | Helper checks and a synthetic deterministic build. |

No downstream owner is assigned these files by the final plan's handoff column.

---

## Frozen contracts — do not silently change

If a change becomes necessary, stop and report the conflict against `docs/final_build_plan.md` before editing. A redraw has to update the id files, `SPLIT.md`, `manifest.json`, and every fingerprint together, then pass `--check` and the artifact tests. Do not edit one side and leave the other stale.

| Frozen item | Location | What is frozen | Why it matters |
|---|---|---|---|
| Split ids | `src/eval/splits/{fit,loop,report}_ids.txt` | The exact id lists and the SHA-256 values in the manifest | `fit` trains, `loop` selects, `report` confirms. Moving an id changes which number is allowed to tune. |
| Split semantics | `src/eval/split_protocol.py`, `src/eval/SPLIT.md` | Source 1 unit, country × bucket, floor 10% report, largest-remainder loop of 25,000 outside report, fit = remainder | The final plan fixes this allocation. |
| Seed | `src/eval/config.py` (`SEED = 42`), manifest `"seed": 42` | CPython 3.11 `random.Random(42)`, one generator, stratum order, sort-then-shuffle-then-cut | A different interpreter or shuffle order produces different ids. |
| Split fingerprints | `src/eval/splits/manifest.json` and the fingerprint table in `SPLIT.md` | SHA-256 of the three id files, the manifest, `train_source1.tsv`, and `train_ground_truth.tsv` | Later gates compare bytes, not regenerated contents. |
| Scorer semantics | `src/eval/score.py` | Formula, empty/empty = 1, either one-empty = 0, disjoint non-empty = finite 0, unweighted macro, set parsing rules | The final plan says this scorer is the number. Another implementation that disagrees is wrong. |
| Baseline definition | `tests/eval/test_score.py` (`123247 / 2206821`) | Predict-nothing on the full training gold file | Phase 1's portal probe, when it happens, uses this known local score. |
| Scorer CLI | `python3.11 -m src.eval.score` | `--predict-nothing`, `--matching`, `--gold`, 16-decimal print | This is the command in the official handoff. |
| Difficulty-pack format and rows | `src/eval/difficulty_pack/pack.tsv` and its manifest | 330 rows, the five columns, the 11 kinds at 30 each, pack SHA-256 `52937158…f6ae` | It is a fixed reading list. Re-running the miner changes which examples people debug. |
| Slice schema version and keys | `src/eval/slice_schema.json` version `1.0` | The 11 keys, levels, phases, and categories listed above | Reports have to use the same tags. |
| Unfrozen name cutoffs | `short_name` and `generic_name` parameters | Explicitly **not** frozen (`frozen: false`, null cutoffs) | Do not invent a cutoff and write it in as if it were already decided. Freezing it is a later, reviewed decision on `fit`. |

`python3.11 -m src.eval.build_split` without `--check`, `python3.11 -m src.eval.difficulty_pack`, and `python3.11 -m src.eval.slice_schema` all rewrite published files. Use `--check` and the tests unless a reviewed regeneration is the task.

---

## Person 1 Part 4 — PENDING

Part 4 is the Phase 1 integration and exit gate from `docs/final_build_plan.md`. It is not part of the completed Parts 1–3 work. Run it when the pipeline artifacts and the teammate handoffs above are available. Do not mark the gate passed in advance.

From the Phase 1 "Integration and exit gate" section, the remaining work is:

1. **Subset checker.** Dishita runs a check that every matched id is a candidate. No subset-checker implementation was found under `src/`. `docs/build_plan_person3.md` mentions a future `verify_subset.py`; that file is not in the repository.
2. **Official validator.** `docs/validate_submission.py` is present (CLI: `--matching`, `--candidate`, `--test-dir`, `--check-ids`). It has not been run as a Phase 1 gate. There is no `output/matching_results.tsv` and no `output/candidate_pairs.tsv`.
3. **Raw-field `report` readiness score.** Score the predeclared raw pipeline once on `report`. Log the macro F₀.₅. That score must not select features, caps, or thresholds. No candidate file, match file, or report score exists.
4. **Predict-nothing format probe.** The team uploads exactly one predict-nothing file. This has not been done.
5. **Portal `SCORED` status.** Not recorded.
6. **Encoding and header acceptance.** Not recorded.
7. **Public score.** Not recorded. Do not invent one.
8. **50k timing.** Namita's Phase 1 work includes timing a 50k-entity inference sample and handing off a timing/memory projection. The exit condition is that this projection leaves enough time for a full run, validation, and one rerun. The projection is not in the repository, so the judgment cannot be made.
9. **Schema and artifact fingerprint freeze for the integrated spine.** Person 1's split, pack, and slice-schema fingerprints exist. Shriya's schema/version contract does not, and there is no integrated candidate or match artifact to fingerprint.
10. **Gate evidence file.** The execution rules say Phase 2 does not start until the Phase 1 exit gate is recorded in `artifacts/gates/phase_1.json`. That directory and file do not exist.

---

## Phase 1 exit gate

Copied from `docs/final_build_plan.md`: Phase 1 passes only when all six conditions below hold. Statuses are from the repository as inspected, including the test run at the end of this file.

| # | Condition | Status | Evidence |
|---|---|---|---|
| 1 | Scorer tests are finite and green, including non-empty disjoint truth and prediction. | **COMPLETE** | `tests/eval/test_score.py` includes `test_nonempty_disjoint_sets_are_finite_zero`. The full eval suite, 32 tests, passed. |
| 2 | A real raw-field pipeline produces candidates, matches, and a `report` macro F₀.₅. | **BLOCKED** | No blocking output, no matching output, no report score. Needs Srishti's candidates and Namita's predictions. |
| 3 | All matches are candidates, and both validators pass. | **BLOCKED** | No match file to check. Subset checker is not implemented. `docs/validate_submission.py` has not been run on a Phase 1 submission. |
| 4 | The 50k timing projects enough time for a full run, validation, and one rerun. | **BLOCKED** | Namita's timing/memory projection is not in the repository. |
| 5 | The portal probe result is recorded. | **PENDING** | No portal `SCORED` record, no encoding/header note, no public score. |
| 6 | Schema and artifact fingerprints are frozen. | **PENDING** | Person 1 split, difficulty-pack, and slice-schema fingerprints are frozen. The phase-level schema (Shriya) and the integrated pipeline artifacts are not. |

**Person 1 Parts 1–3 are complete. The overall Phase 1 exit gate has not passed.**

---

## Where to continue

1. Person 1 has finished the split, the scorer and predict-nothing baseline, the difficulty pack, and the slice-schema definitions.
2. Frozen artifacts are the three id files, `src/eval/splits/manifest.json`, `src/eval/SPLIT.md`, the scorer behavior locked by `tests/eval/test_score.py`, `src/eval/difficulty_pack/pack.tsv` with its manifest, and `src/eval/slice_schema.json` version `1.0`. The two name-slice cutoffs are deliberately unfrozen.
3. Do not redraw the split, rewrite the pack, or rewrite the slice schema. Do not reimplement the scorer. Verify with:
   - `python3.11 -m src.eval.build_split --check`
   - `python3.11 -m unittest tests.eval.test_split tests.eval.test_split_artifacts tests.eval.test_score tests.eval.test_slice_schema tests.eval.test_difficulty_pack`
4. Still required from teammates before the gate can pass: Shriya's schema/version contract and golden examples; Srishti's candidate TSV/Parquet, width/recall report, and manifest; Namita's prediction TSV, timing/memory projection, and model manifest.
5. The remaining Person 1 work is Part 4, the integration and exit gate in the previous two sections. It waits on those handoffs. It does not include Phase 2 measurement.
6. Read, in this order, before changing anything: `docs/final_build_plan.md`, this file, `src/eval/SPLIT.md`, then `.cursor/plans/consolidated_er_pipeline_cf74755a.plan.md`. Use `docs/build_plan_person1.md` only as background. Where it conflicts with the final plan, the final plan wins.

The implementation under `src/` and `tests/` is untracked on `plan_finalised`. Committing it is a separate decision. This handoff does not commit it.

---

## Verification recorded for this handoff

Commands actually run while writing this file. No implementation file was modified.

```bash
python3.11 -m unittest tests.eval.test_split tests.eval.test_split_artifacts tests.eval.test_score tests.eval.test_slice_schema tests.eval.test_difficulty_pack
```

Result: `Ran 32 tests in 81.212s` / `OK` / exit code 0. Python 3.11.14.

Breakdown: `test_split.py` 3, `test_split_artifacts.py` 5, `test_score.py` 11, `test_slice_schema.py` 7, `test_difficulty_pack.py` 6.

```bash
python3.11 -m src.eval.build_split --check
```

Result: `PASS fit=1961144 loop=25000 report=220677`.

Also recomputed: SHA-256 of the three id files, both manifests, `SPLIT.md`, `slice_schema.json`, `pack.tsv`, and the four training TSVs plus the check that pack ids sit only in `fit`. Training hashes matched the manifests. `canonical_bytes()` matched `slice_schema.json`.
