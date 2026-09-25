---
name: Consolidated ER pipeline
overview: Final audited end-to-end pipeline. Dishita measures and gates, Shriya canonicalizes and romanizes, Srishti retrieves a same-country candidate set, and Namita scores and keeps a subset. Every finding in the consolidated-plan audit is closed below, and delivery proceeds through four sequential integration phases.
todos:
  - id: p1-split-scorer
    content: "Dishita / Person 1: freeze fit/25k-loop/report, stdlib scorer with every empty/disjoint case locked, paired-bootstrap comparisons, attribute table, difficulty pack, portal probe, and upload gate"
    status: pending
  - id: p2-canonical
    content: "Shriya / Person 2: rule-based canonical record, deterministic Indic romanization, French normalization, one postal_code field, per-country train-only boilerplate lists, and shared per-country IDF table"
    status: pending
  - id: p3-blocking
    content: "Srishti / Person 3: country-equality retrieval with romanized/phonetic rescue, Pareto cap on the 25k loop, then one candidate run on the 400k fit sample, report, and test"
    status: pending
  - id: p4-matching
    content: "Namita / Person 4: train on Person 3 fit candidates, fold-bagged LightGBM, per-country calibration, one-owner ablation, direct per-bucket set selection on loop, France drift gate, and matching_results.tsv"
    status: pending
isProject: false
---

# Consolidated pipeline — Amazon ML Challenge 2026

Assembled from [Dishita's measurement plan](../../docs/build_plan_person1.md), [Shriya's representation plan](../../docs/person_2_representation_methodology.md), [Srishti's candidate-generation plan](../../docs/build_plan_person3.md), and [Namita's matching plan](person_4_matching_plan_24b6b5a3.plan.md). It has been corrected against the [consolidated-plan audit](../../docs/consolidated_er_pipeline_audit.md). The implementation order and phase exits are in the [four-phase final build plan](../../docs/final_build_plan.md). This file is the architecture source of truth; the final build plan is the execution source of truth.

## 1. What the submission is

For every Source 1 entity, return the set of Source 2 and Source 3 ids that are the same real-world business. The set may be empty. Source 1 is never matched to Source 1.

Scored file: `output/matching_results.tsv`, header `source1_entity_id` tab `matched_entity_ids`. Audited file: `output/candidate_pairs.tsv`, header `source1_entity_id` tab `candidate_entity_ids`. One UTF-8 row per Source 1 entity. Empty second column means no match. No duplicate ids inside a list. No `S1-` ids. Every matched id must already be in that entity's candidate list. Person 1's rule is stricter than the official validator: the validator only warns on a subset violation; the team fails the upload.

Metric, owned by Dishita and not reimplemented by anyone else: unweighted mean of per-entity F₀.₅. Both empty → 1. Exactly one set empty → 0. Both non-empty but disjoint (`|P ∩ T| = 0`) → 0; return before evaluating the formula, so `0/0` can never become NaN. Otherwise precision = `|P ∩ T| / |P|`, recall = `|P ∩ T| / |T|`, and F₀.₅ = `(1.25 × P × R) / (0.25 × P + R)`. Do not use `sklearn.metrics.fbeta_score`. Predict-nothing on the full train must score exactly `123,247 / 2,206,821`.

Final zip:

```
<team_name>_submission.zip
├── output/matching_results.tsv
├── output/candidate_pairs.tsv
├── code/business_entity_resolution/src/
├── code/business_entity_resolution/README.md
├── code/business_entity_resolution/requirements.txt
└── Documentation_template.md
```

Code folders: `src/represent/`, `src/blocking/`, `src/matching/`, `src/eval/`. A thin `src/pipeline/` joins them. No registry, geocoder, search API, or external identity lookup. Model weights, if any, MIT or Apache 2.0 and at most 8B parameters. Person 4's dependencies are MIT, BSD, or Apache. No LLM in normalization. No Zingg. No libpostal.

```mermaid
flowchart LR
  raw[Raw TSV rows] --> p2[Person2 canonical record]
  p2 --> p3[Person3 country-sharded retrieval]
  p3 --> cand[candidate_pairs.tsv plus provenance]
  p2 --> p4[Person4 LightGBM pair scores]
  cand --> p4
  p4 --> match[matching_results.tsv]
  match --> p1[Person1 macro F0.5 and upload gate]
  cand --> p1
```

## 2. Facts the plans already use

- Train Source 1: 2,206,821. US 1,323,633. India 883,188. France 0. Empty name, address, and country: 0. Names 100% Latin letters.
- Train Source 2: 5,034,616. Empty address 168,967. Names: 84.8% plain Latin, 5.1% Devanagari-only, 0.7% Kannada-only, 0.2% mixed, 9.1% other letters (Tamil, Telugu, Bengali, Gujarati, Malayalam, and accented Latin such as `Límited` are mixed inside that 9.1% and are not one job).
- Train Source 3: 5,285,603. Empty address 175,916.
- Gold links: 7,638,365. All same-country. Zero missing ids. Zero Source 2/3 ids linked to more than one Source 1. Source 2 links 3,693,619. Source 3 links 3,944,746. Both sources 1,776,047. Source 2 only 143,029. Source 3 only 164,498. Empty 123,247. List sizes: 1 → 119,157; 2–3 → 906,053; 4–5 → 806,072; 6–10 → 252,255; 11 or more → 37; max 11. Unmatched Source 2/3 records: 2,681,854.
- Test Source 1: 1,732,544. India 809,986 (46.8%). US 663,106 (38.3%). France 259,452 (15.0%). Test Source 2: 4,887,273, empty address 129,408. Test Source 3: 5,082,316, empty address 136,098.
- Cross-script exposure is material: Source 1 names are Latin, while 719,443 of 3,059,843 India gold links (23.51%) and 341,338 of 4,578,522 US gold links (7.46%) have a non-ASCII target name. The gold-join must split true Indic Unicode blocks from merely accented Latin, but deterministic Indic-to-Latin romanization is a committed capability rather than a deferred experiment.
- Cost of one isolated mistake (F₀.₅, then cost versus 1): miss the only true id → 0, cost 1. Add one false id on a 1-id truth while keeping the true id → 0.556, cost 0.444. On a 2-id truth, miss one → 0.833 (cost 0.167) and add one false → 0.714 (cost 0.286). On a 4-id truth, miss one → 0.938 (cost 0.062) and add one false → 0.833 (cost 0.167). Predicting nothing on a non-singleton costs 1. Share of the macro average if that bucket scores 0: singletons 5.6%, length 1 is 5.4%, 2–3 is 41.1%, 4–5 is 36.5%, 6–10 is 11.4%.
- If two Source 1 rows predict the same Source 2/3 id, only the row that does not own it takes the precision hit, unless a later uniqueness step strips the id from the true owner. That step can lower macro F₀.₅. Stolen ids and unmatched distractors are reported separately.
- Non-Latin text is real UTF-8. Open every file with `encoding="utf-8"`. Read with an explicit tab split. Commas inside addresses and id lists will collapse a row if read as CSV.
- One environment: Python 3.11 virtualenv. LightGBM and Polars are not bet on the system 3.14. Person 1's scorer is standard library only and runs in this same 3.11 env, with no pandas on that path. Polars is the attribute-table and feature tool. Pandas is Person 2's TSV reader. Cross-person handoff is Parquet plus the official TSVs, not an in-memory dataframe. Do not copy TSVs into git. Data stays outside the repo; paths live in `config.py`.

## 3. Person 1 — the only number

Artifacts in `src/eval/`. No model code and no GPU there.

Split, frozen before any model score, stratified by country × gold-list bucket `{0, 1, 2–3, 4–5, 6+}`. The 37 length-11 entities fold into `6+`. Unit is the Source 1 id. Never split links.

- `report`: 10% of each stratum, about 221,000 ids. This is the only local number that can authorize a competitive upload. A predeclared raw-pipeline readiness baseline is scored once in Phase 1 and cannot choose a feature, threshold, or cap; after that, `report` is untouched until the operating point is locked on `loop`.
- `loop`: 25,000 ids, same strata, drawn from outside `report`. Retrieval, match-list, cap, and threshold experiments happen here. For every competing operating point, report a paired entity bootstrap 95% confidence interval with at least 2,000 deterministic resamples. Prefer the simpler incumbent when the interval for the macro-F₀.₅ difference includes zero; promote a challenger only when the lower bound is above zero, unless the team records a correctness-driven exception.
- `fit`: the remainder, about 1.96 million. Person 4 trains on a 400k stratified sample drawn from here. The difficulty pack is drawn here. Model fitting happens here. No threshold, cap, quota, or set rule is chosen on `fit`.

Seed and strata in `SPLIT.md`. Ids are one per line. Do not redraw. Do not hold out all of India as a fake France. Do not replace macro with `0.550 × F_India + 0.450 × F_US`.

Beside every score, print US and India F₀.₅, singleton and non-singleton, the loss budget `sum(1 − F_i)` by error type and gold-list length, oracle F₀.₅ (`truth ∩ candidates`), candidate recall on non-empty gold lists, candidates per entity (median and share above 20, 50, 100, plus singleton width), and collision count. Micro precision, recall, and F₀.₅ are diagnostic only. France is 15.0% of test Source 1 and has no local labels; it is therefore unscored **locally**, but it is scored by both challenge leaderboards. Do not invent France labels.

The operating point is the candidate whose paired-bootstrap gain over the incumbent clears the rule above on `loop`; raw point estimates alone do not decide. Slices are printed on every run and choose the next experiment. They do not each veto a statistically supported macro improvement, but correctness failures and the explicit France drift gate do. Short-name cutoff is frozen on `fit` character length and token count and written in `SPLIT.md`. Generic names use Person 2's train-only, per-country boilerplate lists once they exist; until then, document frequency on `fit` text only. Slices: US, India; singleton vs non-singleton; empty address on the Source 2/3 side of a gold list; short names; generic names; gold buckets `{0, 1, 2–3, 4–5, 6+}`. After the gold-join: true Indic-script target versus accented-Latin-only name difference, as separate slices; Source 2 only, Source 3 only, both; cross-country predictions; stolen vs unmatched distractor; predicted list longer than gold versus shorter.

Difficulty pack: about 330 Source 1 entities from `fit` only, never resampled, for reading, not for choosing a threshold. Counts of 30: easy Latin; legal-suffix/abbreviation; low-overlap true matches taken from the gold file; accented-Latin; Indic other side; empty-address matches; multi-id entities of length 4–5; unmatched-distractor near-misses; stolen-neighborhood near-misses; singletons with a lookalike; singletons with nothing nearby.

Error causes from the files: true id absent from candidates → Person 3. True id present but dropped, or false id kept → Person 4. Representation is a counterfactual on the frozen pack: compare raw token overlap with Person 2's canonical overlap. Until canonical records exist, the report says representation was not tested.

Upload gate, in order: official validator passes, including `--check-ids`; every matched id is already a candidate; the France drift gate in §6 passes or has a written team disposition; macro F₀.₅ on `report`, computed after the operating point was locked on `loop`, is a number the team will stand on. Slice drops and a higher collision count trigger loss-budget review. Phase 1 spends exactly one slot on a predict-nothing file with the known local score `123,247 / 2,206,821`, solely to confirm `SCORED` status and portal encoding/header/size behavior. It cannot select a model. Competitive uploads begin only after the full gate, and each logs the locked config hash, `report` macro, public score, and public–local gap. Private performance remains the main optimization target; public performance is a monitored distribution-shift/overfitting signal because the guidelines use both leaderboards for shortlisting. At most 5 submissions a day, 25–27 September 2026 IST. Keep a spare slot each day and every submitted version.

pytest locks: PDF example equals 0.714; empty/empty equals 1.0; empty truth and non-empty prediction equals 0.0; non-empty truth and prediction with zero overlap equals 0.0 and is finite; predict-nothing equals the singleton rate. Official validator stays byte-for-byte; wrap `docs/validate_submission.py`, do not fork it.

Writes §2.1 from measurements, §5 from the last `report` error report, and compiles §1 and §6 from the other three notes without inventing missing architecture text. The guidelines ask for 1–2 pages and the template says no page limit. Both stay. Do not invent a resolution. Depth lives in the template. A short overview can be the executive summary.

## 4. Person 2 — one canonical record

`src/represent/`. Python 3.11. pandas with `sep='\t'` and `quoting=csv.QUOTE_NONE`. Standard-library `re`, `unicodedata`, `string`. `collections.Counter` for token mining. pytest. Paths in `config.py`. No LLM: a local model at 100 rows/sec would take over 35 hours for 12.5 million rows; rules do 10,000–50,000 records/sec/core, are idempotent, and do not rewrite rare names into popular brands.

Pipeline, in order:

- Unicode NFKC, strip control characters `\x00-\x1f` and `\x7f-\x9f`, lowercase.
- Name: `&` and `+` → `and`; strip junk prefixes `m/s`, `messrs`, `the`, `shree`, `sri` only when measured as pure noise, and `http://`, `www.`; map legal suffixes to canonical forms (`pvt ltd` / `p. ltd` / `pvt. limited` → `private limited`; `ltd` → `limited`; `inc` → `incorporated`; `corp` → `corporation`; `llc` → `limited liability company`; `co` → `company`; also `gmbh`, `sarl`, `sa`, `bv`). French coverage is mandatory: normalize `sas`, `sasu`, `eurl`, `sci`, `snc`, and `sc` as legal-form tokens rather than identity-bearing words. Replace other punctuation with spaces and collapse whitespace.
- Deterministic romanization: retain `normalized_name` in its original script and also emit `romanized_name`. Use an offline, versioned rule table for Devanagari, Kannada, Tamil, Telugu, Bengali, Gujarati, and Malayalam, covering independent/dependent vowels, virama, anusvara/chandrabindu, digits, and common conjunct behavior. The scheme is fixed and ISO-15919/ITRANS-style; it never calls a model, network, registry, or external identity data. Latin input passes through unchanged after accent folding into the romanized view. Unknown code points are preserved rather than dropped. Golden cross-script pairs, determinism, idempotency, empty input, mixed script, and no-information-loss tests are release blockers. The measured Unicode-block slice decides prioritization and diagnostics, not whether this fallback exists.
- Address: `None`, `NaN`, `"nan"`, `""`, and whitespace become `""` with `is_empty_address = True`, never NaN. Expand `rd`→`road`, `st`→`street`, `ave`→`avenue`, `blvd`→`boulevard`, `bldg`→`building`, `apt`/`ste`→`suite`, `flr`/`fl`→`floor`, `opp`→`opposite`, `nr`→`near`. French address handling normalizes `BP`/`boîte postale`, preserves arrondissement tokens and numeric ordinals such as `1er`, and retains `CEDEX`. Flag landmarks `near`, `opposite`, `behind`, `beside`, `adjacent to` as `has_landmark_ref`. Keep 6-digit Indian PIN, 5-digit US ZIP, and 5-digit French postal codes as contiguous tokens.
- Country is an open label. Unknown countries take the generic fallback. They are never dropped. France: flag `CEDEX` as `is_cedex`. India PIN `^[1-9][0-9]{5}$`. US ZIP `^[0-9]{5}$`.

Canonical contract: `entity_id`, `country`, `normalized_name`, `romanized_name`, `normalized_address`, `derived_tokens` (`name_tokens`, `romanized_name_tokens`, `address_tokens`, `source_script`, `is_empty_address`, `has_landmark_ref`, `postal_code`, `is_cedex`). Original-script and romanized values coexist; downstream code never overwrites one with the other.

Two token artifacts, and only these:

- `boilerplate_tokens_by_country.json`, mined only from the three training sources and partitioned by country, plus a global fallback for unseen countries. A token above the documented 1.0% starting threshold within a country is a boilerplate candidate; the final threshold is frozen on `fit`. Person 1's generic-name slice uses the matching country list. It is not an IDF. France receives only the global fallback here because test text must not create a train-only diagnostic resource.
- `idf_by_country`, one table shared by Person 3 and Person 4. Document frequency is computed inside each country label, with no labels and no external text. US and India use training rows of that country. France has no training rows, so France uses the organizer-provided test rows with `country = France` (name and address text only). An unseen token gets a smoothed background IDF, never infinity. A train-only global IDF would treat every unseen French token as maximally rare, which opens wide blocks and false merges. This is not an identity lookup.

Also `before_after_report` on the difficulty pack, including original script, romanized output, and French cases. Idempotency `f(f(x)) = f(x)` is a test. `postal_code` in the canonical record is the only postal field in the pipeline. Person 3 blocks on it. Person 4 does not parse a second postal regex.

Until this exists, Person 3 and Person 4 use raw fields, and Person 1's representation probe says it has not run.

## 5. Person 3 — the recall ceiling at minimum width

`src/blocking/`. The audited file is the exact last-stage set Person 4 scores, not an earlier union. Amazon reviews candidate generation, and smaller candidate sets rank better beyond the leaderboard.

Indices are built for every country string found in the current target files. An S1 row is queried only against S2/S3 rows with the same normalized country. No `if country in {"US", "India"}`. France builds and queries a France shard. Source 2 and Source 3 are queried independently, with a per-source minimum opportunity before a global cap.

Channels, each emitting provenance and a retrieval score:

- A. Exact and near-exact signatures inside country: canonical name; distinctive non-empty canonical address; `(canonical name, postal code)`; distinctive-name-token signature; raw normalized equivalents in parallel until Person 2 is trusted. Generic exact-name buckets are guarded by document frequency; a large bucket needs postal or address evidence or goes to ranked channels.
- B. Rare-token inverted retrieval, per country and source, weighted by `idf_by_country`. Rarest usable name and address tokens. Cap posting-list length. Boilerplate never opens a million-row block alone.
- C. Character n-grams on the name, initially 3–5, tested on the machine. Sparse TF-IDF/BM25, or a disk-backed n-gram accumulator, or ANN only if low-overlap gold recall does not fall. No all-pairs matrix.
- D. Address retrieval separate from name: rare address tokens, house/plot numbers with locality, postal as a partition or strong feature rather than a sole key, char n-grams or token BM25 on non-empty addresses. Empty target address goes through name-only channels and is tagged.
- E. Postal plus weak-name rescue inside equal country and postal code. Exact-name duplicates are preserved before truncation.
- F. Romanized/phonetic rescue inside country and source: run exact, rare-token, and character channels on `romanized_name`; add a deterministic Metaphone/Soundex-style key from the same romanized text as an additive channel, never as a sole match decision. Log its incremental recall and width, especially on the true-Indic and typo slices.
- G. If nothing earlier fires, a small name-first fallback inside country and source. If still nothing clears a permissive threshold, emit a legal empty list. Do not pad every row to k.

After a strong anchor, expand only through a tight duplicate signature (equal canonical name plus postal, or a high-confidence address signature). No unrestricted transitive expansion.

Selector: always keep protected high-confidence exact hits subject to generic-bucket guards; keep per-source minimum quotas when candidates exist; rank the rest with a retrieval-only score calibrated on `fit` only; choose the cap on `loop`; never touch `report` until the design is locked. Deduplicate and sort deterministically. Person 4 does not filter before scoring. `candidate_pairs.tsv` is exactly the set scored.

Country equality is enforced here and only here. No `{US, India}` whitelist. Person 4 does not apply a second country filter and does not take `country_equal` as a feature, because every candidate is already same-country. A cross-country pair in this file is a blocking bug, counted by Person 1.

After the `loop` Pareto point is frozen, run that one config, with no sweep, on Person 4's 400k `fit` sample. Those candidates are the training negatives. Then run it once on `report` after Person 4 locks the set rule. Then the full test.

Experiment ladder B0–B8 adds one channel at a time, including romanized and phonetic rescue as separately measurable additions. Sweep per-source top-k in {3, 5, 10, 20} and global caps in {10, 20, 30, 50, 100}, fixed versus adaptive caps, exact-hit protection on/off, expansion on/off. Select on the 25,000-id `loop` using the paired-bootstrap rule. Confirm once on `report` after the design is locked. Keep only Pareto points: no retained config may have both lower recall and greater-or-equal width. Initial engineering targets, not official rules: link recall ≥ 99.5%, complete-entity recall ≥ 98%, no unexplained S2/S3 or country collapse, median width ≤ 20, p95 ≤ 50, controlled p99, and a pair count Person 4 can score in the remaining time. Also report any-hit recall, oracle macro F₀.₅ by calling Person 1's scorer, S2 and S3 recall and width, recall for S2-only / S3-only / both, complete-list recall by gold bucket, true-Indic and accented-Latin recall separately, mean/p90/p99/max width, share above 20/50/100, singleton mean width, empty rate, reduction ratio against the country-equality search space, wall time, peak RSS, index bytes, output bytes.

Miss TSV, same day, one row per missed true id, with Person 1's slice tags and a reason in: `NO_SHARED_EXACT_OR_TOKEN_KEY`, `FUZZY_SCORE_BELOW_THRESHOLD`, `BELOW_TOP_K`, `SOURCE_QUOTA_STARVATION`, `GLOBAL_CAP_TRUNCATION`, `MULTIMATCH_EXPANSION_MISSED`, `EMPTY_TARGET_ADDRESS_NAME_DRIFT`, `REPRESENTATION_DESTROYED_SIGNAL`, `INDEX_OR_JOIN_BUG`, `UNKNOWN`. Fix the largest bucket by lost true ids and lost complete entities.

Start on raw fields. When canonical records arrive, A/B raw only, canonical only, and the union. Accept canonical for blocking only when the frontier improves or the union repairs regressions.

Engineering: explicit tab separator, compact integer ids, persisted fingerprinted indices, chunked resumable shards, deterministic order independent of worker count, peak RSS logged. Capacity gate on a sample of at least 100k Source 1 rows before the full test run: candidate count, TSV size, retrieval time, Person 4 scoring time, index disk, peak RSS with margin, and time for validation plus one rerun. Do not launch a config that cannot finish retrieval, matching, validation, and packaging. After freeze, only a demonstrated correctness or packaging bug is accepted.

Tests include: unseen country accepted; both sources queried; empty address does not become the token `nan`; duplicates collapse; a synthetic France shard retrieves France-to-France; no cross-country pair is emitted; empty list serializes as `S1-id<TAB>\n`; `matching_results.tsv` is a row-wise subset or the checker exits non-zero and writes a proof JSON with counts and hashes.

Phase 1 deliverable is a raw-field candidate baseline for all 25,000 `loop` ids plus the miss list and enough `report` candidates to execute the predeclared raw end-to-end readiness score. Phase 2 freezes one recall/width point and generates the 400k `fit` candidates. Phase 3 runs the locked configuration on `report`. Phase 4 writes one row per test Source 1 id.

Writes all of template §3 and the blocking half of §2.2 from measured numbers. Does not claim France accuracy. States only that the implementation is country-open, builds France shards from test data, and contains no US/India whitelist.

## 6. Person 4 — keep, drop, or return nobody

`src/matching/`. Python 3.11 venv. Pinned polars, lightgbm, rapidfuzz, jellyfish, scikit-learn, optuna. `PYTHONUTF8=1`. `seed=42`.

Scorer: LightGBM binary, two passes. Pass 1 is pair features. Pass 2 adds context. Isotonic calibration on out-of-fold pass-2 scores is fit separately for US and India. France borrows the US or India calibrator selected by the predeclared unlabeled drift distance over canonical feature and score distributions; if neither is acceptable, use the global calibrator and fail the France drift gate pending review. Then one-owner assignment, then set selection. Rejected inside this plan: a transformer over every pair, Splink as the main matcher (term-frequency weighting is the only idea taken from it), a graph neural net, an LLM, weights above 8B.

Training rows are Person 3's candidates for about 400k Source 1 ids, stratified by list size including singletons, drawn from `fit`. The stand-in 3-gram blocker is not used. A model trained on a different candidate distribution will be miscalibrated on the file that is scored. Each candidate is labeled 1 iff it is in gold. 5-fold `GroupKFold` by `s1_id`, inside `fit`. Out-of-fold scores feed pass 2 and calibration. At inference, average the five fold-model probabilities before calibration; do not replace them with one refit unless a measured capacity failure forces it. No upsampling and no class reweight. Optuna (about 20 trials, 100k-entity subsample) and early stopping on log-loss also stay inside `fit`. Features built in chunks of 50k entities. Positives the blocker never returned are blocker-lost, not matcher-lost.

Name features, calculated both on Person 2's original-script normalized name and its romanized view, plus legal-suffix-stripped variants: Jaro-Winkler, normalized Levenshtein, token-sort, token-set, partial ratio; char 3-gram TF-IDF cosine; token Jaccard; IDF-weighted overlap from `idf_by_country`; IDF of the rarest shared token and of the rarest unshared token on each side; exact match after suffix stripping; acronym and phonetic-key match; digit tokens equal / conflict / absent; token counts and length ratio; script flag Latin / Devanagari / other and a same-script flag; mean IDF of the S1 name.

Address features, each with a missing indicator, never imputed: candidate address empty; house/building number equal / conflict / missing; `postal_code` from Person 2 equal / conflict / missing; `is_cedex` as a flag; token-set ratio, IDF-weighted overlap, 3-gram cosine; overlap of the last two comma-separated segments. No second postal parser.

Other: `src_is_S3`; Person 3's retrieval score and rank within source; candidate list size per source. No country one-hot and no `country_equal` feature. Pass 2 only: rank within S1 and source, gap to best, gap to next, count of candidates above 0.5, best pass-1 score this candidate gets from any other S1, and whether this S1 is its best owner. That needs `candidate_entity_id → [(source1_entity_id, p1)]` over the whole split.

LightGBM start: `num_leaves=127`, `learning_rate=0.05`, `min_data_in_leaf=200`, `feature_fraction=0.8`, `bagging_fraction=0.8`. Monotone constraints on the main similarity features. Reliability curves and calibration-error tables separately for US, India, empty-address candidates, and singletons. Per-country isotonic calibration must beat or tie global calibration on its own `fit` OOF Brier score and reliability error; otherwise that country uses the global fallback.

Leave-one-country-out, inside `fit`: train on US and score India, then the reverse. This is the France proxy. Remove a feature whose importance collapses under that shift, or whose removal improves the held-out country score. Do not use `loop` or `report` for this.

Decision, step A, ablated on `loop`: each S2/S3 id is kept only for the S1 where its calibrated probability is highest. Keep the step only if its paired-bootstrap macro-F₀.₅ gain clears the selection rule. Collision count is reported and does not alone gate the step. The risk Person 1 named is real: if a thief outscores the true owner, the step takes the id off the owner and costs a full miss plus a false merge. The ablation is what catches that. The uniqueness property is verified only on train; applying it to test, especially France, is an explicit distributional assumption recorded in the final documentation and never described as proven.

Decision, step B, chosen on `loop`: sort remaining candidates by calibrated `p`. Person 1's scorer is the definition, including empty-on-non-empty = 0. The approximation below initializes the search only:

```
E[F_k] ~= 1.25 * sum(p[0:k]) / (0.25 * k + E|T|),   E|T| = sum(p) + m
E[F_0]  = prod(1 - p) * q_empty
```

`E[F_0]` is the probability the truth is empty. When the truth is non-empty, predicting empty scores 0, so those cases add nothing. `m` and `q_empty` are estimated on the `fit` candidates, bucketed by candidate count, not on `loop` or `report`. Because a ratio of expectations is not the expectation of the ratio, the shipped rule is selected by a direct grid over `k` (including zero) per predeclared candidate-count bucket on `loop`, scored by the real macro F₀.₅ implementation. Compare that rule with one global threshold and separate `t_S2`/`t_S3`; use the paired-bootstrap promotion rule, not the highest noisy point estimate.

Always: output is a subset of candidates, asserted before write; no duplicate ids; no S1 ids; one row per Source 1 entity.

Inference: chunks of 100k S1 entities; pass 1 scores written out; competition index over the whole test split; then pass 2, per-country calibration, owner step, set rule. Person 4's volume estimate is 1.73M times width about 40, about 70M pairs. Time a 50k-entity run in Phase 1. If the full run would exceed 6 hours, cut feature cost according to the scope tiers below. If width is too wide, the cap is applied inside Person 3's stage so the audited file still equals what is scored.

France pre-upload drift gate, computed against both US and India test predictions: fail and investigate if (a) France's empty rate is more than 2× both references or differs from the nearer reference by more than 10 percentage points; (b) its median predicted-list size is outside `[0.5×, 2.0×]` the nearer reference; or (c) population-stability index for the calibrated-score histogram exceeds `0.25` against both references. Record which calibrator France borrowed and the distances. A failure does not permit silent threshold retuning on France; it triggers data/normalization/index checks, global-calibrator fallback evaluation, and explicit four-person sign-off before any upload.

Writes template §4, the decision half of §2.2, and false-merge / false-miss notes for Person 1 (top 50 of each, categorized).

## 7. Scope tiers and freeze order

Freeze from the top down. A lower tier may not delay a higher tier or the Phase 4 package.

- **Must ship:** official scorer and all edge-case tests; frozen splits; deterministic canonical/raw views plus Indic romanization and French rules; same-country exact and rare-token retrieval from both sources; audited candidate file; pass-1 LightGBM; global threshold baseline; one-owner ablation; row-wise subset proof; validator; raw Day-1 end-to-end score; France drift gate.
- **Should ship:** address/postal channels; romanized/phonetic blocking; pass-2 context; per-country calibration; fold-bagged inference; direct per-bucket `k` grid; character n-grams; bootstrap comparisons and detailed slices.
- **Could ship:** Optuna beyond a small baseline search; guarded duplicate expansion; extra seeds beyond the five folds; long-tail slices or feature variants that do not close a dominant miss bucket.

If a capacity or timing gate fails, cut Could items first, then Should items in reverse measured value. Never cut a Must item to preserve an unproven optimization.

## 8. Contracts

- Dishita publishes the 25,000-id `loop`, `report`, `fit`, `SPLIT.md`, scorer command, bootstrap comparator, slice tags, and difficulty pack. If any other F₀.₅ disagrees with `src/eval/`, `src/eval/` is the number.
- Shriya publishes the canonical schema, version fingerprint, romanization tables/tests, `boilerplate_tokens_by_country.json`, `idf_by_country`, and before/after sheet.
- Srishti publishes candidates for `loop`, then the 400k `fit` sample, then `report`, then test. Official TSV headers stay `source1_entity_id` and `candidate_entity_ids`. The side Parquet, which Namita reads, uses those same id names plus `target_source`, `retrieval_score`, `retrieval_rank_in_src`, channel bitmask, per-channel ranks and scores, exact-signature flags, rarity evidence, country, script/romanization provenance, and empty-address flag. Also ship the candidate-report JSON, miss TSV, and manifest (git state, input fingerprints, normalizer version, every retrieval parameter, seed, dependency versions, hashes, wall time, peak RSS, machine summary). No absolute user paths in committed config.
- Namita returns `matching_results.tsv`, calibration/drift reports, and the locked set-rule config. Srishti's subset checker and Dishita's upload gate both require every match to be a candidate. Dishita returns a slice report, not a new model.
- Srishti calls Dishita for oracle macro F₀.₅ and does not ship a rival scorer.
- What is fit where: weights, Optuna, early stopping, leave-one-country-out, retrieval-score calibration, country/global isotonic calibrators, `m`, and `q_empty` on `fit`. Caps, quotas, one-owner ablation, threshold/set-rule comparisons, and direct per-bucket `k` values on `loop`. `report` receives one predeclared raw readiness score in Phase 1 and one locked confirmation in Phase 3; neither may be used for iterative tuning.

## 9. Four sequential integration phases

The detailed ownership matrix, commands/artifacts, entry conditions, and exit gates are in [docs/final_build_plan.md](../../docs/final_build_plan.md).

1. **Phase 1 — prove the raw end-to-end spine.** Dishita freezes data and scoring; Srishti produces raw candidates; Namita produces raw-baseline predictions; Shriya establishes the canonical/romanization contract. Exit only after a real raw `report` macro exists, the validator/subset checks pass, timing is extrapolated, and the one predict-nothing portal probe is recorded.
2. **Phase 2 — harden representation and recall.** Shriya ships deterministic Indic romanization, French rules, per-country token resources, and canonical data. Srishti integrates raw/canonical/romanized/phonetic channels and freezes a bootstrap-supported recall/width point on `loop`. Dishita publishes miss attribution; Namita freezes features. Exit only when the 400k `fit` candidates and their manifest exist.
3. **Phase 3 — train, calibrate, and lock decisions.** Namita trains fold models, compares calibration, one-owner, and set rules; Dishita applies paired bootstrap and performs the locked `report` confirmation; Shriya and Srishti repair correctness defects only. Exit only with a hashed operating point, capacity proof, documentation numbers, and no unresolved Must defect.
4. **Phase 4 — full test, drift gate, package, and submit.** Srishti writes test candidates; Namita writes test matches and the France drift report; Dishita validates, packages, and controls uploads; Shriya verifies representation fingerprints and finishes documentation. Exit only when both TSVs cover every test Source 1 id, hashes/manifests and subset proof pass, the France gate is resolved, the zip is reproducible, and a spare upload slot remains.

## 10. Audit closure

Every audit item has an explicit resolution: Indic romanization (§4); disjoint-set metric guard (§1/§3); French normalization (§4); correct local-vs-leaderboard France language and public monitoring (§3); a 25k loop with paired bootstrap (§3); the Day-1 portal probe and raw end-to-end gate (§3/§9); Must/Should/Could freeze order (§7); stated test uniqueness assumption, per-country calibration, fold bagging, direct `k` search, and numeric France drift gates (§6); per-country boilerplate (§4); and phonetic rescue (§5). The audit remains evidence; this corrected plan supersedes its action list.
