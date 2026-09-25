# Person 3 build plan — recall ceiling at minimum candidate width

Person 3 owns the comparison space. The matcher can reject a bad candidate, but it can never recover a true Source 2 or Source 3 id that was not retrieved. The winning blocker therefore has two simultaneous objectives:

1. make the validation recall ceiling nearly lossless, including **every id** for multi-match entities; and
2. achieve that ceiling with the smallest deterministic candidate set the real machine can generate and Person 4 can score.

This is not a plan to maximize recall by dumping a wide neighbor list into `candidate_pairs.tsv`. Amazon explicitly says candidate generation is reviewed in the final ranking and that smaller candidate sets rank better beyond the public/private leaderboard. The final file is the exact last-stage set scored by Person 4, not an earlier superset.

Role source: `docs/work_distribution.md`, Person 3 — Candidate generation.

---

## 1. Mission, boundaries, and non-negotiable rules

### Person 3 owns

- `src/blocking/` and its tests/configuration.
- One candidate list for every requested Source 1 id, including a legal empty list.
- Candidate generation first on Person 1's 5,000-id `loop`, later on frozen `report`, and finally on the full test set.
- Candidate-recall, oracle-ceiling, width, total-pair, runtime, and memory reports.
- A same-day miss list grouped by Person 1's slice tags.
- Final `output/candidate_pairs.tsv`.
- A hard proof that Person 4's `matching_results.tsv` is a row-wise subset of `candidate_pairs.tsv`.
- The blocking half of template §2.2 and all of §3.

### Person 3 does not own

- Person 2's normalization policy or canonical-record contract.
- Person 4's similarity features, classifier, keep/drop rule, or F₀.₅ threshold.
- Person 1's official macro F₀.₅ scorer, split, or upload decision.
- External identity lookup. Registries, geocoders, search APIs, and internet enrichment are forbidden.

### Official constraints that shape the design

- Train is about 2.21M Source 1 rows against 10.32M Source 2+3 rows. Cartesian comparison is impossible.
- Test is about 1.73M Source 1 rows against 9.97M Source 2+3 rows.
- The test includes France although train includes only US and India. Country is an open string label.
- All 7,638,365 observed training links are same-country. Use **country equality**, never a `{US, India}` whitelist.
- Most matched Source 1 entities have multiple true ids; 1,776,047 have truth in both Source 2 and Source 3.
- Source 2-only and Source 3-only entities also exist, so both indices must be queried independently.
- `candidate_pairs.tsv` is required in the final package and audited for recall ceiling and reduction ratio.
- It must contain one tab-separated row per test Source 1 id; candidate lists may be empty, contain only existing S2/S3 ids, and contain no duplicates.
- Every final match must already be a candidate.
- Final outputs and the complete runnable pipeline must be reproducible from the provided data.

---

## 2. The decision rule: win on the Pareto frontier

Do not choose a blocker by one recall number. For every configuration, record:

- link recall: `retrieved true ids / all true ids`;
- complete-entity recall: fraction of non-singleton S1 entities for which **all** true ids were retrieved;
- any-hit recall: fraction with at least one true id retrieved;
- oracle macro F₀.₅ from `truth ∩ candidates`;
- Source 2 and Source 3 link recall separately;
- candidates per entity: mean, median, p90, p95, p99, maximum;
- share above 20, 50, and 100 candidates;
- mean width for singleton entities;
- empty-candidate rate;
- total pair count and reduction ratio against the country-equality search space `Σ_country N(S1_country) × (N(S2_country)+N(S3_country))`;
- wall time, peak RSS, index size, and output size.

Keep only Pareto-optimal configurations: no retained configuration may have both lower recall and greater-or-equal width than another. The team chooses the operating point after seeing Person 4's actual score and throughput. A useful initial engineering target—not a fabricated rule—is:

- link recall ≥ 99.5%;
- complete-entity recall ≥ 98%;
- no unexplained Source 2/Source 3 or country collapse;
- median width ≤ 20, p95 ≤ 50, and a tightly controlled p99;
- full-test pair count small enough for Person 4 to score within the remaining challenge time.

If the data cannot meet these together, publish the frontier and the exact misses. Never hide a width explosion behind a single high-recall average.

### Why complete-entity recall matters

A top-k query can find one easy duplicate and miss the other true ids. Link recall alone can make this look tolerable, while macro F₀.₅ still loses on that Source 1 entity. Every experiment therefore reports both link recall and complete-list recovery by gold-list bucket `{1, 2–3, 4–5, 6+}`.

---

## 3. Proposed blocker: a recall union followed by a learned width budget

The recommended design is a deterministic, multi-channel retrieval union. Each channel catches a different failure mode. Every emitted pair carries provenance and a retrieval score. A cheap last-stage candidate selector removes redundant low-value pairs and writes exactly what Person 4 scores.

```text
raw records ─────────────┐
                        ├─ country-equal target shards
Person 2 canonical ─────┘          │
                                   ├─ exact/signature lookup
                                   ├─ rare-token inverted retrieval
                                   ├─ name char-ngram retrieval
                                   ├─ address char-ngram retrieval
                                   ├─ postal + weak-name retrieval
                                   └─ fallback retrieval
                                              │
                                      union + deduplicate
                                              │
                              quota/cap + provenance selector
                                              │
                              exact matcher-scored candidate set
                                              │
                                  candidate_pairs.tsv
```

### 3.1 Always shard dynamically by country equality

Build indices for every country string found in the current target files. Query an S1 row only against S2/S3 rows with the same normalized country label. This is supported by every training link and prevents huge cross-country false candidate pools.

The implementation must discover country values from data. There must be no branch such as `if country in {"US", "India"}`. A synthetic or real `France` row must build/query the France shard normally.

### 3.2 Query Source 2 and Source 3 independently

Run each retrieval channel against both source families and merge afterward. Maintain a small per-source minimum opportunity before applying a global cap. A high-scoring Source 2 neighborhood must not consume every slot and silently suppress Source 3 matches.

Every report includes:

- S2 recall and width;
- S3 recall and width;
- recall for gold lists that are S2-only, S3-only, or both;
- complete-list recall for the `both` slice.

### 3.3 Channel A — exact and near-exact signatures

High precision, cheap, and capable of returning all duplicated true rows:

- exact canonical name within country;
- exact canonical address within country when non-empty and sufficiently distinctive;
- exact `(canonical name, postal code)`;
- exact distinctive-name-token signature;
- raw normalized equivalents as a parallel fallback until Person 2's representation is trusted.

Do not blindly emit enormous exact-name buckets such as generic business names. Apply document-frequency guards. For a large bucket, require postal/address evidence or hand it to the ranked channels.

### 3.4 Channel B — rare-token inverted retrieval

Build a disk-backed or memory-measured posting list from distinctive name and address tokens, separately by country and source. Weight tokens with training-only IDF or another monotonic rarity score. For each S1 row:

1. select the rarest usable name tokens and address tokens;
2. retrieve posting lists from both target sources;
3. accumulate weighted overlap without constructing a dataframe of the full cross product;
4. retain the best candidates per source and per field;
5. record which tokens caused retrieval.

Set a maximum posting-list length or DF ratio. Boilerplate such as legal suffixes, `road`, `street`, and very common business words must never open a million-row block by themselves.

This channel should be the workhorse for reordered fields, legal suffix changes, and partial addresses.

### 3.5 Channel C — character n-gram name retrieval

Use sparse character n-grams (initially 3–5 characters, tested rather than assumed) over canonical names. Character retrieval catches typos, punctuation changes, glued/split tokens, and some transliteration variants. Query country/source shards in chunks and retain only top-k neighbors above a minimum similarity.

Implementation choices must be benchmarked on the actual machine:

- sparse TF-IDF/BM25 with chunked top-n multiplication if RAM permits;
- a disk-backed inverted n-gram accumulator if a full sparse matrix does not fit;
- an approximate-nearest-neighbor index only if measured recall does not regress on low-overlap gold pairs.

Do not materialize an all-pairs similarity matrix. Persist shard/index artifacts so parameter sweeps do not rebuild them.

### 3.6 Channel D — address retrieval

Run separately from the name channel so trade-name/legal-name differences can still match on location. Use:

- rare address tokens;
- house/building/plot numbers as high-value tokens when combined with locality evidence;
- postal/PIN code as a partition or strong feature, not necessarily as a sole key;
- character n-grams or token BM25 on non-empty addresses.

Never require an address: Source 2 and Source 3 contain roughly 169k and 176k empty training addresses. If target address is empty, route through name-only channels and tag the provenance.

### 3.7 Channel E — postal plus weak-name rescue

Postal codes can make a tractable local search for noisy short names, but a postal code alone may create a wide block. Within equal country and postal code, rank by name evidence and rare address evidence. Preserve all exact-name duplicates before truncation.

### 3.8 Channel F — guarded fallback

If no earlier channel emits a candidate, use a small name-first fallback within country and source. If there is still no candidate above a deliberately permissive retrieval threshold, emit the legal empty list. Do not fill every row to k merely to avoid empties.

Fallback rate and fallback-only true-link recovery must be reported. A large fallback rate signals a broken upstream representation or index.

### 3.9 Multi-match expansion without width explosion

After finding a strong anchor, expand only through a tightly defined duplicate signature, for example equal canonical name plus postal code, or equal high-confidence address signature. This can recover multiple S2/S3 records belonging to the same entity.

Measure expansion separately:

- extra true ids recovered;
- extra false candidates added;
- width change by list-length bucket;
- buckets skipped because they exceeded a frequency guard.

Never use unrestricted transitive graph expansion. One generic record can otherwise flood the candidate list.

### 3.10 Final candidate selector

The union is not automatically the audited file. Build a compact candidate-row table with:

- `source1_entity_id`, `candidate_entity_id`;
- target source (`S2` or `S3`);
- channel bitmask/provenance;
- per-channel retrieval ranks/scores;
- exact-signature flags;
- rarity evidence;
- country and empty-address flags.

Then apply a deterministic selector:

1. always retain protected high-confidence exact/signature hits, subject to generic-bucket guards;
2. retain source-specific minimum quotas when candidates exist;
3. rank remaining pairs with a cheap retrieval-only score calibrated on `fit` or `loop`, never on `report`;
4. cap by a global budget and, if useful, a confidence-adaptive budget;
5. deduplicate and sort ids deterministically.

If Person 4 applies another pre-scoring filter, that filter belongs here or must be imported into this stage. `candidate_pairs.tsv` must equal the pairs after that filter.

---

## 4. The experiment ladder

Run small, attributable experiments. Every row in the experiment ledger changes one thing and writes both recall and width.

| Stage | Candidate union | Question answered |
|---|---|---|
| B0 | Exact canonical name only | Cheap lower bound and duplicate-bucket behavior |
| B1 | B0 + exact postal/name and rare name tokens | How much recall comes from deterministic keys? |
| B2 | B1 + name char n-grams | What do fuzzy names recover and cost? |
| B3 | B2 + rare address retrieval | How many trade-name/name-drift cases are rescued? |
| B4 | B3 + address char n-grams/postal local search | Does address fuzziness justify its width/runtime? |
| B5 | B4 + guarded fallback | What remains among zero-candidate rows? |
| B6 | B5 + multi-match expansion | Does full-list recall rise efficiently? |
| B7 | B6 + final selector/cap sweep | Which Pareto point should Person 4 score? |

For each channel, report marginal true ids gained, newly completed entities, candidates added, and candidates added per recovered true id. Remove channels that add width but no meaningful oracle or complete-recall gain.

### Cap and quota sweep

At minimum sweep:

- per-source top-k values such as 3, 5, 10, and 20;
- global caps such as 10, 20, 30, 50, and 100;
- fixed versus confidence-adaptive caps;
- exact-hit protection on/off;
- multi-match expansion on/off.

These are starting sweep values, not hard-coded final choices. Select on `loop`; confirm once on frozen `report` only after the design is locked.

---

## 5. Evaluation and same-day miss loop

### Required candidate report

Write machine-readable JSON and a compact Markdown table containing:

```json
{
  "split": "loop|report|test",
  "config_hash": "...",
  "source1_rows": 0,
  "candidate_pairs": 0,
  "link_recall": 0.0,
  "complete_entity_recall": 0.0,
  "any_hit_recall": 0.0,
  "oracle_macro_f0_5": 0.0,
  "s2_link_recall": 0.0,
  "s3_link_recall": 0.0,
  "width": {"mean": 0, "median": 0, "p90": 0, "p95": 0, "p99": 0, "max": 0},
  "share_over": {"20": 0, "50": 0, "100": 0},
  "singleton_mean_width": 0,
  "empty_candidate_rate": 0,
  "reduction_ratio": 0,
  "runtime_seconds": 0,
  "peak_rss_mb": 0,
  "index_bytes": 0,
  "output_bytes": 0
}
```

Person 1 owns the trusted implementation of oracle macro F₀.₅; Person 3 calls it rather than creating a rival scorer.

### Miss list contract

For every missing true id, write one TSV row:

```text
source1_entity_id  missed_entity_id  target_source  country  gold_list_bucket
person1_slice_tags  s1_name  target_name  s1_address  target_address
channels_attempted  best_available_rank  best_score  miss_reason  suggested_owner
```

Group the summary by Person 1's tags: US/India, gold-list length, S2-only/S3-only/both, empty target address, short/generic name, script category when available, stolen-id/unmatched context where applicable. Hand this back the same day.

Use a stable reason taxonomy:

- `NO_SHARED_EXACT_OR_TOKEN_KEY`
- `FUZZY_SCORE_BELOW_THRESHOLD`
- `BELOW_TOP_K`
- `SOURCE_QUOTA_STARVATION`
- `GLOBAL_CAP_TRUNCATION`
- `MULTIMATCH_EXPANSION_MISSED`
- `EMPTY_TARGET_ADDRESS_NAME_DRIFT`
- `REPRESENTATION_DESTROYED_SIGNAL`
- `INDEX_OR_JOIN_BUG`
- `UNKNOWN`

The first action after every report is to rank miss reasons by lost true ids and lost complete entities. Fix the largest attributable bucket, not the most interesting anecdote.

### Raw-versus-canonical A/B

Start on raw fields immediately. When Person 2 ships canonical records, run the identical configuration on:

- raw only;
- canonical only;
- union of raw and canonical keys.

Measure recovered and newly lost true ids plus width. The canonical representation is accepted for blocking only when its frontier improves or the union repairs its regressions.

---

## 6. Scale engineering on the machines we actually have

Before committing to an index, benchmark a representative country/source shard and extrapolate. Record CPU count, RAM, free disk, rows/sec, bytes/row, and expected full-run time.

### Hard engineering rules

- Stream TSVs with an explicit tab separator and fixed dtypes; never parse them as CSV.
- Do not load 10M Python dictionaries of heavyweight row objects without a measured memory budget.
- Map ids to compact integer row indices internally; convert back only for output.
- Partition indices by dynamically discovered country and target source.
- Persist reusable index artifacts with input fingerprints and schema versions.
- Query S1 in chunks and write intermediate candidate shards atomically.
- Merge/deduplicate shards by integer keys; never hold the complete textual pair table in RAM if it is avoidable.
- Make chunk size and worker count configurable.
- Keep deterministic ordering independent of process count.
- On interruption, resume from completed shards rather than rebuilding the world.
- Log peak RSS and elapsed time per stage.

### Capacity gate before the full test run

From a representative ≥100k S1 sample, estimate:

- full candidate count and TSV size;
- full retrieval and Person 4 scoring time;
- index build time and disk footprint;
- peak RSS with a safety margin;
- time for validation and one complete rerun.

Do not launch a final configuration that cannot finish retrieval, matching, validation, and packaging before the deadline. Freeze the last safe configuration early enough to rerun it.

---

## 7. Code and artifact design

Recommended layout under the final package's `code/business_entity_resolution/`:

```text
src/
├── blocking/
│   ├── config.py
│   ├── schema.py
│   ├── io.py
│   ├── signatures.py
│   ├── token_index.py
│   ├── char_index.py
│   ├── retrieve.py
│   ├── expand.py
│   ├── select.py
│   ├── evaluate.py
│   ├── miss_report.py
│   ├── write_candidates.py
│   └── verify_subset.py
└── pipeline/
    └── ... thin integration entry point ...
tests/
└── blocking/
configs/
└── blocking.yaml
```

Every run writes a manifest with:

- Git commit and dirty/clean state;
- input paths, sizes, and hashes or stable fingerprints;
- normalization version;
- every retrieval parameter;
- random seed where relevant;
- dependency versions;
- candidate/report hashes;
- wall time, peak RSS, and machine summary.

No absolute user paths may appear in committed configuration. The README must contain exact build-index, retrieve-validation, retrieve-test, evaluate, subset-check, and validator commands.

---

## 8. Tests and gates

### Unit tests

- Country equality accepts unseen labels and never uses a known-country whitelist.
- Both S2 and S3 indices are queried.
- Empty addresses do not crash or create the literal token `nan`.
- Duplicate candidates collapse to one id.
- Exact-name duplicate buckets can return multiple true ids.
- Caps preserve protected exact hits according to the documented rule.
- Deterministic input produces byte-identical output.
- Empty candidate lists serialize as `S1-id<TAB>\n`.
- Headers are exact and the file is UTF-8 TSV.

### Integration tests

- Every requested S1 id appears exactly once, even with no candidate.
- Candidate ids exist and have only S2/S3 prefixes.
- A synthetic France shard retrieves France-to-France candidates.
- No cross-country pair is emitted.
- Raw and canonical modes both satisfy the same schema.
- Resume-from-shard produces the same final bytes as a clean run.
- `matching_results.tsv ⊆ candidate_pairs.tsv` row by row; any violation exits non-zero.

### Pre-upload gates

1. Person 1's official validator passes.
2. Validator passes with `--check-ids` where memory permits; otherwise run an equivalent streaming existence check for candidates and still run official checks on matches.
3. The subset checker reports zero missing matched ids and writes a proof JSON with counts and hashes of both files.
4. The chosen `report` candidate metrics and Person 4 score are attached to the run manifest.
5. `candidate_pairs.tsv` is confirmed to be the exact inference set, not an early union.

---

## 9. Three-day execution schedule

### Day 1 — establish a real ceiling

1. Receive Person 1's `loop` ids, gold access contract, scorer, and slice tags.
2. Inspect machine resources and benchmark TSV throughput.
3. Implement country/source-sharded exact signatures and rare-token inverted retrieval on raw fields.
4. Produce the first candidate file for all 5,000 loop ids, including empties.
5. Publish link recall, complete-entity recall, oracle ceiling, width distribution, total pairs, runtime, and the first miss list.
6. Add name char n-gram retrieval only for miss buckets exact/token blocking cannot reach.
7. Hand Person 4 the exact compact candidate set plus pair provenance.

End-of-day deliverable: an integrated candidate artifact that Person 4 actually scores, not a notebook demo.

### Day 2 — close misses, then compress

1. Swap in Person 2's canonical records and run raw/canonical/union A/B.
2. Add address retrieval, postal-local rescue, and guarded multi-match expansion based on measured miss buckets.
3. Sweep source quotas and caps on `loop`; build the Pareto table.
4. Let Person 4 score several Pareto points so matcher accuracy and runtime help choose width.
5. Freeze one design, run it once on `report`, and return the full report and miss list to Person 1.
6. Remove channels with poor marginal true-id recovery per candidate added.
7. Benchmark a large sample and reserve time/disk for the full-test run.

End-of-day deliverable: team-approved recall/width operating point and a runtime-proven frozen config.

### Day 3 — reproducibility over novelty

1. Freeze code, dependencies, normalization version, and config.
2. Build/query full test in resumable shards.
3. Write exactly one row for every test S1 id to `output/candidate_pairs.tsv`.
4. Hand the file and provenance-compatible pair features to Person 4.
5. Run existence, format, duplicate, country, and subset checks.
6. Run the official validator with Person 1.
7. Reproduce counts/hashes from the manifest and package runnable code.
8. Finish §3 and the blocking half of §2.2 from measured numbers, not aspirations.

After freeze, accept only a fix for a demonstrated correctness or packaging bug. A last-hour unbenchmarked retrieval idea is not a winning move.

---

## 10. Handoffs and questions that must be answered early

### From Person 1

- Where are `loop`, `report`, and `fit` ids?
- What is the exact truth-loading and oracle-scoring interface?
- What slice columns and tags must be copied into the miss list?
- Which number authorizes the one report run?

### From Person 2

- Exact canonical schema and null conventions.
- Version/fingerprint of canonical output.
- Token-frequency and boilerplate resource format.
- Whether postal codes, scripts, and distinctive tokens are already materialized.

### To Person 4

- Exact candidate schema and ordering.
- Provenance/retrieval columns available during model development.
- Maximum pair throughput and memory budget.
- Whether Person 4 performs any pre-model filtering; if yes, move or mirror it into the final candidate stage.
- A machine-readable match file for the hard subset proof.

### To Person 1 after every integrated run

- Candidate report JSON and Markdown.
- Miss TSV grouped by their slice tags.
- Candidate config/manifest hash.
- Person 4 subset-check result.

---

## 11. Documentation text Person 3 must ultimately supply

Template §3 must state, with final measured values:

- every blocking/retrieval channel and why it exists;
- country-equality and independent S2/S3 retrieval;
- how generic blocks and huge posting lists were guarded;
- how multi-match lists were protected;
- candidate link recall, complete-entity recall, and oracle F₀.₅;
- mean/median/p95/p99/max width and total pair count;
- reduction ratio, runtime, peak memory, index size, and output size;
- ablation/marginal contribution of each channel;
- how the operating point was selected from the recall-width frontier;
- proof that the candidate file is the exact matcher input and contains every kept match.

The blocking half of §2.2 should describe the strategic idea in one paragraph: country/source-sharded multi-channel sparse retrieval, followed by a deterministic learned or rule-based width budget optimized on the frozen validation protocol.

Do not claim France accuracy. State only that the implementation is country-open, builds France shards from test data, and contains no US/India whitelist.

---

## 12. Definition of done

Person 3 is done only when all of these are true:

- Validation candidates exist for every requested S1 id, including legal empty lists.
- Recall, complete-list recovery, oracle ceiling, widths, total candidates, reduction ratio, runtime, and memory are reported from one reproducible command.
- S2, S3, both-source, country, singleton, empty-address, and list-length behavior are visible.
- Every missing true id appears in a same-day, slice-tagged miss list with a reason code.
- Raw-versus-canonical behavior has been re-measured.
- The selected configuration is Pareto-justified and can finish on the actual hardware.
- Full-test `candidate_pairs.tsv` is the exact set Person 4 scores.
- It has one valid row per S1 test entity, no duplicate ids, no S1 ids, and only existing S2/S3 ids.
- The subset proof finds zero final matches outside candidates.
- Output and reports are deterministic and tied to a config/input/code manifest.
- §3 and the blocking half of §2.2 contain real final numbers.
- The official validator passes and the final package can regenerate the file.

---

## 13. Copy-paste Codex prompt for executing this role

Use this from the repository root on branch `rough_plan`:

```text
You are the implementation owner for Person 3 (Candidate Generation) in the Amazon ML Challenge 2026 Business Entity Resolution project.

Repository and safety:
- Work only in this repository and preserve unrelated user changes.
- Confirm the current branch is rough_plan before editing. Do not commit, push, switch branches, or delete files unless I explicitly ask.
- Use only the provided challenge data. Never use external business registries, geocoders, entity-resolution APIs, search engines, or internet-derived records.
- Do not implement Person 4's final keep/drop threshold or change Person 2's normalization policy.

Before proposing or editing anything, read every repository document in full, including:
- README.md
- docs/Problem Statement.pdf
- docs/guidelines_and_key_instructions_amazon_ml_challenge_2026.pdf
- docs/Documentation_template.md
- docs/problem_understanding_and_research.md
- docs/work_distribution.md
- docs/build_plan_person1.md
- docs/person_2_representation_methodology.md
- docs/validate_submission.py
- docs/build_plan_person3.md
Then inventory the repository, available data paths, existing code, tests, environment, RAM, CPU, and disk. Summarize the contracts you found and flag any conflict between docs without silently resolving it.

Goal:
Build a production-grade, deterministic candidate-generation pipeline that maximizes true-link and complete-entity recall at the smallest candidate width the real hardware and Person 4 can score. `candidate_pairs.tsv` must be the exact final set scored by the matcher, not an early superset. Multi-match entities and both Source 2 and Source 3 must be explicitly protected. Country must be treated as an open label; use dynamic country equality and never a {US, India} whitelist.

Required workflow:
1. Locate Person 1's frozen loop/report/fit ids, scorer, truth interface, and slice tags. If an artifact is not present, implement everything that does not depend on it, document the precise contract needed, and provide a small synthetic fixture rather than inventing team outputs.
2. Locate Person 2's canonical-record interface. Start with raw fields if it is unavailable. When it exists, benchmark raw-only, canonical-only, and their union and report regressions as well as gains.
3. Implement under src/blocking/ (or the repository's agreed final-package equivalent) a country- and source-sharded hybrid blocker using measured combinations of:
   - guarded exact name/address/signature lookup;
   - rare-token/IDF inverted retrieval;
   - chunked sparse character n-gram name retrieval;
   - separate address and postal-local retrieval;
   - guarded empty-result fallback;
   - guarded multi-match signature expansion;
   - deterministic union, provenance, per-source opportunity, and final width selection.
4. Do not materialize the Cartesian product. Use compact integer ids, chunking, persisted fingerprinted indices, resumable shards, deterministic ordering, and measured memory/runtime limits.
5. Add unit and integration tests for unseen-country behavior, same-country-only emission, both sources, empty addresses, duplicate removal, multi-match retrieval, caps, empty serialization, one row per S1, deterministic output, existing-id checks, and row-wise matching-results subset proof.
6. On Person 1's loop split, run an ablation ladder and cap/quota sweep. For every configuration record link recall, complete-entity recall, any-hit recall, oracle macro F0.5 using Person 1's scorer, S2/S3 recall, list-length/source/country slices, median/p90/p95/p99/max candidates, shares over 20/50/100, singleton width, empty rate, total pairs, reduction ratio, wall time, peak RSS, index bytes, and output bytes.
7. Keep and present the recall-width Pareto frontier. Never recommend a configuration only because recall rose; quantify candidate cost and Person 4 scoring feasibility. Treat link recall >=99.5%, complete-entity recall >=98%, median <=20, and p95 <=50 as initial engineering targets to test, not official rules.
8. Emit a TSV row for every missed true id with Person 1's slice tags, retrieval provenance, best rank/score, stable miss reason, and suggested owner. Summarize which reason buckets cost the most true ids and complete entities.
9. Generate candidate_pairs.tsv with exact required headers and legal empty lists. Verify UTF-8 TSV format, complete S1 coverage, unique rows/lists, S2/S3 prefixes, id existence, same-country behavior, and deterministic bytes.
10. Given Person 4's matching_results.tsv, fail non-zero if any kept id is absent from the same S1's candidate list. Write a proof JSON containing row/pair counts and hashes.
11. Run the official validator, including --check-ids when feasible. Treat the candidate file as required even though the local validator calls it optional.
12. Update runnable README instructions and draft final measured text for template §3 and the blocking half of §2.2. Do not insert placeholder performance claims.

Operating style:
- Lead with inspected evidence and make reasonable reversible assumptions.
- Implement and test, rather than stopping at another high-level plan, unless I explicitly ask for planning only.
- Benchmark on a small representative shard before expensive full-data work; extrapolate time, RAM, disk, pair count, matcher time, and output size.
- Do not run a full-test job until the selected configuration is frozen and capacity-checked.
- Preserve a run manifest with Git state, input fingerprints, normalizer version, config, dependency versions, machine facts, timings, metrics, and output hashes.
- Report exact files changed, commands run, tests/benchmarks passed, current Pareto frontier, blockers, and the safest next action.

The authoritative role plan is docs/build_plan_person3.md. Follow it closely, but if repository evidence contradicts it, show the evidence and propose the smallest correction before proceeding.
```

---

## 14. Final strategic warning

The easiest way to lose Person 3's contest is to celebrate 99.x% recall while handing Person 4 tens or hundreds of millions of weak pairs. The second-easiest is to report a small average width while a long tail explodes on generic names. The third is to find one true id and miss the remaining ids of a multi-match entity.

The winning evidence is a reproducible frontier: nearly every true id, nearly every complete gold list, both target sources, low tail width, bounded compute, and an audited final file that exactly matches what the classifier saw.
