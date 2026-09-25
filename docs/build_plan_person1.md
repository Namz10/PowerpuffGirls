# Person 1 build plan — measurement and error map

Person 1 does not match records. Person 1 decides which number the team is allowed to trust, and turns every later run into a map of where the points were lost.

The score lives or dies on that. Train is 60% US and 40% India. The test set the team will be ranked on is 46.8% India, 38.3% US, and 15.0% France (259,452 of 1,732,544 Source 1 entities). A validation score on the raw training mix will flatter a US-strong system and then lose on the leaderboard.

This plan chooses the split, the scorer, the slices, the difficulty pack, the error taxonomy, the tools, and the upload rule. It does not implement them.

Role source: `docs/work_distribution.md`, Person 1 — Measurement and error map.

---

## What you own

You ship the shared definition of progress. Everyone else consumes it. You do not own normalization, candidate lists, or the keep/drop rule.

Concrete artifacts, in `src/eval/`:

1. A frozen split of Source 1 ids, with the rule written down before anyone sees a model score.
2. One scorer that implements official macro F₀.₅, plus precision and recall beside it.
3. Slice scores. Slices choose the next experiment. They do not all veto an upload.
4. A frozen difficulty pack: true pairs, near-miss non-matches, singletons.
5. An error report after each integrated run.
6. A validator pass before every upload.
7. Later, template §2.1, §5, and a compilation of §1 and §6 from the other three people's notes. Compilation means assembly. It does not mean filling in their model for them.

Data is already on disk at `/Users/dishita/Amazon_ML/student_resource/dataset/`. Do not copy the TSVs into the git repo. `.gitignore` already excludes them.

Template sections you write:

- §2.1 Problem Analysis
- §5 Results & Error Analysis
- Compilation of §1 Executive Summary and §6 Conclusion from the other three people's notes

You leave to others: normalized text, the candidate set, the match lists.

---

## Facts that fix the design

These are measured from the files on 25 Sep 2026, not inferred from the PDFs.

| Fact | Number | What it forces |
|---|---|---|
| Train Source 1 | 2,206,821. US 1,323,633. India 883,188. France 0. Empty name 0. Empty address 0. Empty country 0. | You cannot score France. You can stop the team optimizing the US. |
| Train Source 2 | 5,034,616. US 3,016,817. India 2,017,799. Empty address 168,967. | |
| Train Source 3 | 5,285,603. US 3,170,056. India 2,115,547. Empty address 175,916. | |
| Test Source 1 | 1,732,544. India 809,986. US 663,106. France 259,452. Empty address 0. | The leaderboard mix is not the train mix. |
| Test Source 2 | 4,887,273. India 2,312,565. US 1,871,330. France 703,378. Empty address 129,408. | Same shape as train, slightly fewer empty addresses. |
| Test Source 3 | 5,082,316. India 2,405,000. US 1,945,701. France 731,615. Empty address 136,098. | |
| Gold links | 7,638,365. Average list length 3.46 including singletons. Source 2: 3,693,619. Source 3: 3,944,746. All same-country. Zero cross-country. Zero missing ids. | Country **equality** is safe. A whitelist of `{US, India}` is not. France survives only if the check is "labels match," not "label is one of the two we saw." |
| Gold list composition | Both sources 1,776,047. Source 2 only 143,029. Source 3 only 164,498. Empty 123,247. | A blocker that retrieves only one source shows up as its own slice. |
| ID reuse | 0 Source 2/3 ids belong to more than one Source 1. Unique matched ids = 7,638,365. | On this training distribution a duplicated prediction is wrong for at least one Source 1 row. The scorer charges only the row that does not own the id, unless a later unique-assignment step strips the owner. |
| Unmatched Source 2/3 | 10,320,219 − 7,638,365 = 2,681,854 records are nobody's match. | Hard negatives exist. They are not "all the other rows." |
| Cardinality | 0 matches: 123,247 (5.6%). 1: 119,157. 2–3: 906,053. 4–5: 806,072. 6–10: 252,255. 11 or more: 37. Maximum list length 11. | Top-1 cannot represent the labels. Empty-on-doubt is also a losing policy. |
| Source 1 names | 100% Latin letters. | The script problem is on the other side. |
| Source 2 names | 84.8% plain Latin, 5.1% Devanagari-only, 0.7% Kannada-only, 0.2% Devanagari+Latin, 9.1% other letters. That 9.1% is not one phenomenon: the sample contains Tamil, Telugu, Bengali, Gujarati, Malayalam, and accented Latin such as `Límited`. | This is a count of Source 2 rows, not of true matches. Do not prioritize transliteration, and do not split the work by script, until gold pairs are joined to script and accented Latin is counted separately from Indic. |
| Source 2 addresses | 87.1% plain Latin, 5.5% Devanagari+Latin, 3.4% no letters (empty or digits only), 3.2% other alpha, 0.8% Kannada+Latin. | |
| Source 3 names | 88.5% plain Latin, 8.1% other alpha, 2.6% Devanagari-only, 0.4% Devanagari+Latin, 0.4% Kannada-only. | |
| Source 3 addresses | 87.7% plain Latin, 5.2% Devanagari+Latin, 3.3% no letters, 3.1% other alpha, 0.7% Kannada+Latin. | |
| Longest observed strings (train) | Name 105 / 104 / 123 characters (S1 / S2 / S3). Address 256 / 249 / 240. | |
| Naive pair space | About 2.2 million Source 1 × 10.3 million Source 2+3. | Blocking sets the recall ceiling. `candidate_pairs.tsv` is how that ceiling is audited. |

No list in training contained a repeated id. No gold id had a prefix other than `S2-` or `S3-`.

---

## How the metric actually spends points

The leaderboard metric is fixed. It is macro F₀.₅ per Source 1 entity, singletons included.

Per Source 1 entity, with `tp = |P ∩ T|`, predicted set `P`, truth set `T`:

- Both empty → precision 1, recall 1, F₀.₅ 1.
- Truth empty, prediction non-empty → F₀.₅ 0.
- Prediction empty, truth non-empty → precision 0, recall 0, F₀.₅ 0. Abstaining is not "perfect precision."
- Otherwise precision = `tp / |P|`, recall = `tp / |T|`, and

```
F₀.₅ = (1.25 × Precision × Recall) / (0.25 × Precision + Recall)
```

- The official number is the **unweighted mean of per-entity F₀.₅**. It is not link-weighted.

Do not call `sklearn.metrics.fbeta_score`. That will silently compute a different average. Implement the formula. Lock it with tests.

Worked example from the problem statement: prediction `{S2-00047, S2-00193, S3-00812}`, truth `{S2-00047, S3-00812}` → precision 2/3, recall 1, F₀.₅ = 0.714.

The formula weights a false id more than a partial miss when some true ids are still kept. That is not the same claim as "a missed link is cheap." A miss of the only true id scores 0. There are 119,157 such entities.

Cost of one mistake on one entity, no other error mixed in:

| Gold list | Miss 1 true id | Add 1 false id, keep every true id | Predict nothing |
|---|---|---|---|
| 1 | 0 → cost 1.000 | 0.556 → cost 0.444 | 0 → cost 1 |
| 2 | 0.833 → cost 0.167 | 0.714 → cost 0.286 | 0 → cost 1 |
| 3 | 0.909 → cost 0.091 | 0.789 → cost 0.211 | 0 → cost 1 |
| 4 | 0.938 → cost 0.062 | 0.833 → cost 0.167 | 0 → cost 1 |
| Singleton, one false id | | | cost 1 (F₀.₅ = 0) |
| Singleton, empty | | | cost 0 (F₀.₅ = 1) |

How much of the macro average each bucket can move, if that bucket scores 0 and every other entity scores 1:

| Gold list | Entities | Share of the macro average |
|---|---:|---:|
| 0 (singleton) | 123,247 | 5.6% |
| 1 | 119,157 | 5.4% |
| 2–3 | 906,053 | 41.1% |
| 4–5 | 806,072 | 36.5% |
| 6–10 | 252,255 | 11.4% |
| 11 or more | 37 | ~0 |

A 4-match illustration is the cheap-miss regime. The 2–3 match bucket is 41% of the average. Predicting nothing for a non-singleton is a full point, same as a false id on a singleton.

Every error report sums `(1 − F_i)` by error type and by gold-list length: singleton false id, empty prediction on a non-empty truth, partial miss with no extra id, extra id with every true id kept, and both a miss and an extra. Slice averages do not say which of those repairs is worth doing. Also report micro precision, recall, and F₀.₅ over links, labeled as diagnostic. Decide only on macro.

### Ceiling and list width

After every candidate file, score an oracle: for each Source 1 entity, predict `truth ∩ candidates`. That oracle F₀.₅ is the highest the matcher can reach on this candidate file. A true id that never enters `candidate_pairs.tsv` cannot be recovered later. That file is the set the matcher actually scores, not an earlier superset.

The oracle does not measure junk. For a singleton the truth is empty, so the oracle scores 1.0 no matter how many false candidates were attached. Publish three numbers with the oracle:

- Oracle F₀.₅, and actual F₀.₅. The gap is what the matcher left on the table.
- Candidate recall of true ids: `|truth ∩ candidates| / |truth|` over non-empty gold lists.
- Candidates per entity: median, and the share of entities above 20, 50, and 100. Separately, candidates per singleton.

Pair recall is not a conversion formula into macro F₀.₅. A wide list with a high oracle is still a blocker problem, because Person 4 then has to keep precision on that width. A matcher change that does not move actual-versus-oracle did not improve matching. It may still be the right next experiment if the width is the thing that changed.

### Colliding ids

No Source 2/3 id is gold for more than one Source 1 in training. If A owns the id and B also predicts it, A keeps a true positive and only B takes the precision hit. Both entities are charged only if a later step removes the id from A to enforce uniqueness. That step can lower macro F₀.₅. Count collisions. Do not describe them as an automatic double penalty, and do not veto an upload because the count rose.

Report two kinds of false id separately:

- **Stolen id:** the predicted id is gold for a different Source 1 entity.
- **Unmatched distractor:** the predicted id is gold for nobody.

---

## Decisions

### Split

One shared protocol, three files, stratified by country × gold-list bucket `{0, 1, 2–3, 4–5, 6+}`. The 37 entities with 11 matches fold into `6+`. That is 2 countries × 5 buckets = 10 strata.

Unit of split is the Source 1 entity id. Never split links independently. Splitting links would put some of an entity's true ids in fit and score the same entity on report.

| File | How it is drawn | About how many Source 1 ids | Who may use it |
|---|---|---|---|
| `report` | 10% of each stratum | ~221,000 | The only number that can authorize an upload. Scored only after an operating point is locked. Not the day-1 retrieval target. |
| `loop` | 5,000 ids, stratified with the same buckets, drawn from outside `report` | 5,000 | Hourly retrieval, match lists, and threshold sweeps. |
| `fit` | Whatever remains | ~1.98 million | Person 4 may train here. The difficulty pack is drawn here. You never choose an operating point on it. |

Seed and strata go in a short `SPLIT.md` next to the id files. Ids are one per line, plain text, so the others can load them with no library. Freeze the files. Do not redraw.

Hourly commands score `loop` only. Score `report` only after the operating point is locked on `loop`. Printing `report` from the sweep command spends the holdout across three days of iteration. Both id files are published. There is no split that only one person looks at.

Do not hold out all of India as a fake France. India is 47% of the test set and you would be throwing away the part you can actually learn. The work-distribution rule is one shared scoreboard: macro F₀.₅ on `report`. `loop` is the working set so day-1 retrieval finishes. It is not a second leaderboard.

Why this cut: 5,000 stratified ids can be retrieved on day 1 against about 10 million Source 2/3 rows. A second 221k sweep set cannot. `report` stays large so the upload number is not a few thousand anecdotes. Person 3's day-1 target is candidates for `loop`. Candidates for `report` are produced when there is an operating point to score.

### The number that matters

The upload number is official macro F₀.₅ on `report`. Same definition as the leaderboard: unweighted mean over Source 1 entities, singletons included.

Publish these beside it. They do not replace it.

- US F₀.₅ and India F₀.₅. Train is about 60% US and 40% India. Test Source 1 is 46.8% India, 38.3% US, and 15.0% France. A single average can hide a US-strong run. Looking at the two country scores is how you see that. Do not replace the average with `0.550 × F_India + 0.450 × F_US`. That formula deletes France, which is 259,452 of 1,732,544 test Source 1 entities, and it assumes train-India behaves like test-India. Only country counts were measured. Two systems can swap order once France is included.
- Singleton and non-singleton F₀.₅.
- The loss budget: sum of `(1 − F_i)` by error type and gold-list length.
- Oracle F₀.₅, candidate recall, and candidates per entity.

When a file is uploaded, log the `report` macro and the public score next to each other. One paired move tells you whether `report` tracks the leaderboard. The public rank is not a target. The problem statement's final decision is the private half. The guidelines also use both leaderboards for shortlisting. You cannot tune the private half. Chasing the public half burns the five daily slots.

### France

You cannot estimate France. Do not invent labels. Do not fetch external French business data. That is a disqualification. Do not treat Indic script or accented Latin in the training files as a France score. France in this test is a country label the training files never contain. Train accents on words like `Límited` are not French legal forms or French address order.

Do two honest checks:

1. Publish US and India scores beside the macro, and state in every report that France is 15.0% of test Source 1 and is inside neither score.
2. A behavior check, not a retrieval test: a row whose country string is `France` must still produce a canonical record, and no branch may drop it for failing a `{US, India}` whitelist. Do not query those relabeled rows against the training index and call empty candidates a failure. Country-equality retrieval returns nobody when the index contains no other France rows. That empty result is the correct behavior of the rule the gold links support. French match accuracy stays unscored.

Say in §2.1 that this check catches a hard-coded country whitelist. It does not predict French accuracy.

Before anyone prioritizes transliteration, measure gold pairs. Join each true Source 2/3 id to the script of its name and report: the fraction of Source 1 entities with at least one Indic true match, and the fraction whose non-exact name difference is only accented Latin. Those are different jobs. A record-level 9.1% "other letters" count does not answer either one.

Country **equality** (Source 1 country string equals Source 2/3 country string) is supported by 7,638,365 of 7,638,365 training links. A whitelist of `{US, India}` is forbidden by the problem statement and would drop every France entity. Those are different rules. The error report should count cross-country predictions on validation. Expect zero. Any non-zero count is a pure false-merge pile. Test could in principle contain a cross-country true link that train never showed. The training evidence is perfect and the cost of a cross-country false merge is a precision hit under F₀.₅, so the default is to treat inequality as a near-certain false merge and to say so. Do not silently convert that into a `{US, India}` filter.

### What can veto an upload

Three checks, in this order:

1. The official validator passes, including `--check-ids`.
2. Every matched id is already in that entity's candidate list.
3. Macro F₀.₅ on `report` is the score the team is willing to stand on, computed after the operating point was locked on `loop`.

US, India, singleton, non-singleton, empty address, name slices, list length, script (once the gold-join exists), oracle, list width, and collision count are how you choose the next experiment. They are printed on every `report` run. They do not each hold a veto. A pile of 0.005 slice gates can reject a better file because one slice twitched. Collision count rising is not by itself a reason to block the upload.

### Slices that choose the next experiment

They explain a failure. They do not veto an upload.

Minimum set required by the work distribution, defined operationally:

| Slice | Definition |
|---|---|
| US, India | Country of the Source 1 entity. France will not appear in any training split. |
| Singleton vs non-singleton | Gold list empty vs not. |
| Empty address on the Source 2/3 side | Gold list contains at least one match whose Source 2 or Source 3 address is empty. Source 1 itself has zero empty addresses. |
| Short names | Freeze a cutoff after measuring character length and token count on `fit` only. Write the cutoff into `SPLIT.md`. Do not guess "12 characters." |
| Generic names | A name whose tokens are all boilerplate or all very high document frequency. Compute document frequency on `fit` text only, then apply it. Align later with Person 2's boilerplate list. Do not block on Person 2 to define v1. |
| Lists of different lengths | Gold buckets `{0, 1, 2–3, 4–5, 6+}`. |

Additional slices, after the measurement that makes them real:

- Indic true match versus accented-Latin-only name difference. Build these only after the gold-join. Do not treat them as one "non-Latin" slice, and do not aim a day of work at them before the fractions exist.
- Source 2 only, Source 3 only, both.
- Cross-country predictions.
- Stolen ids versus unmatched distractors. A count, not a double penalty.
- Predicted list longer than gold versus shorter than gold.

### Difficulty pack

About 330 Source 1 entities, drawn from `fit` only. Never from `loop` or `report`. Ids frozen in a TSV. Never resampled. The pack is for reading. Thresholds are not chosen on 30 examples. A pack that changes every run is not a pack.

Minimum counts:

| Kind | Count | What it is |
|---|---|---|
| Easy Latin true matches | 30 | Near-exact name and address, same country. High token overlap. |
| Legal-suffix / abbreviation true matches | 30 | Corp/Corporation, Pvt/Private, Ltd/Limited, punctuation, word order |
| Low-overlap true matches | 30 | Same-country gold pairs whose token overlap is near zero: trade name versus legal name, address-only, transliteration. Token-overlap mining cannot find these. Take them from the gold file. |
| Accented-Latin true matches | 30 | `Límited`, `Ínc`, `Nétwork` style. Separate from Indic. |
| Indic other side | 30 | Devanagari, Kannada, Tamil, Telugu, Bengali, Gujarati, or Malayalam on a true Source 2/3 match against a Latin Source 1 name. Fill from the gold-join, not from token overlap. |
| Empty-address matches | 30 | True match whose Source 2 or Source 3 address is empty |
| Multi-id entities | 30 | Full gold list, length 4–5, not a single pair pulled out of it |
| Unmatched-distractor near-misses | 30 | High token overlap, same country, id is gold for nobody |
| Stolen-neighborhood near-misses | 30 | High overlap with a record that is gold for a different Source 1. Reading material. Not proof that the metric charges both entities. |
| Singletons with a lookalike | 30 | Empty gold, but a plausible same-country neighbor exists |
| Singletons with nothing nearby | 30 | Empty gold, no close neighbor |

True pairs are stratified by token overlap, including an overlap-near-zero bucket. Near-misses may use cheap same-country token overlap, because a near-miss is supposed to look similar. That miner is not Person 3's blocker and must not become one. Store the Source 1 id, the related Source 2/3 ids, the kind code, the overlap bucket, and a one-line reason.

### Error causes

Only two causes are observable from the files alone:

1. True id absent from `candidate_pairs` → Person 3.
2. True id present but dropped, or false id kept → Person 4.

Representation is a counterfactual, not a third automatic bucket. On the frozen pack, compare token overlap of the raw strings with overlap of Person 2's canonical strings.

- Overlap fell and the matcher missed → representation damaged the pair.
- Overlap is high and the matcher still missed → match decision.
- Until the canonical records exist, the report says "representation not yet tested" instead of guessing.

Each report is a generated JSON plus a one-page markdown summary:

- Macro F₀.₅ on the split that was scored (`loop` or `report`), labeled as which one.
- US, India, singleton, non-singleton, and a line that France is 15% of test and unscored.
- Sum of `(1 − F_i)` by error type and gold-list length.
- Oracle F₀.₅, candidate recall of true ids, and candidates per entity including the tail and the singleton width.
- Collision count, as a count.
- Counts by cause and by the diagnostic tags.
- Example entities with the largest `(1 − F_i)` inside each gold-list bucket, not the 30 weirdest strings overall. A global sort by point loss shows only total losses and hides the 2–3 match bucket.

Do not dump 221k entities into chat. The JSON is the source of truth. Hourly reports are on `loop`. A `report` score is produced only after the operating point is locked.

### Technology

- Python 3.13, which is what this machine has. Anything in the scorer that must be trusted stays on the standard library: read TSV with an explicit tab split, set intersection, the formula above. No pandas on that path, so a library upgrade cannot move the number.
- Polars for the one-time attribute table (country, list length, empty address, script tag) and the slice joins. Pandas will get used for convenience. It is not the system of record. Reading a TSV without `sep="\t"` silently collapses the row. Addresses and id lists contain commas.
- pytest, with three locks before anyone trusts a score:
  - PDF example equals 0.714.
  - Truth empty and prediction empty equals 1.0.
  - Truth empty and prediction non-empty equals 0.0.
- A dumb baseline as a fourth lock: predicting nothing for every entity must score exactly the singleton rate, 123,247 / 2,206,821 on a full pass, and about 0.056 on a stratified 10%. If it does not, the scorer is wrong and nothing else you publish is usable.
- The official validator at `/Users/dishita/Amazon_ML/student_resource/utils/validate_submission.py` stays byte-for-byte. A copy lives at `docs/validate_submission.py`. Wrap it. Do not fork it. For local validation files, point `--test-dir` at a folder shaped like the test set (`test_source1.tsv` and, when `--check-ids` is on, `test_source2.tsv` and `test_source3.tsv`).
- No notebook as the official score. One command writes the JSON. If a notebook disagrees with the JSON, the notebook is wrong.
- No GPU and no model code in `src/eval/`.
- Attribute table in parquet via Polars. Id lists in plain text. Difficulty pack in TSV.

Do not use:

- `sklearn.metrics.fbeta_score` as the official number.
- A notebook as the score the team quotes.
- A second private split only Person 1 looks at.
- Link-weighted F₀.₅ as the decision number. That is micro. Report it beside macro. Do not steer by it.
- Holding out all of India as a fake France.
- Geocoders, business registries, search APIs, or any external identity lookup. The pipeline is audited. Evidence of that is immediate disqualification.
- An 8B-over or non-MIT / non-Apache model. Person 1 does not train one. If someone else does, the license check is part of the day-3 package review, not part of the scorer.

### Validator protocol

The problem statement says unknown ids will be rejected. The validator's own comment says a missing id only lowers the score unless `--check-ids` is passed. Treat existence as required. Do not rely on the softer comment.

Before any portal upload:

- Run the official validator.
- Run it again with `--check-ids`. Source 2 + Source 3 on the full test set is about 10 million ids and a few GB of RAM. If memory is tight, check the matching file first. The matching file is the one that is scored.
- Confirm every matched id is a subset of that entity's candidates. The official validator only warns on this. The team's rule is stronger: it fails the upload gate.
- Person 1 presents macro F₀.₅ on `report`, the country slices, the loss budget, and the oracle next to list width. The team agrees in one short checkpoint. Five slots a day are spent on purpose.

Empty lists are valid and mean no match. Duplicate Source 1 rows, duplicate ids inside a list, `S1-` ids in a match list, wrong headers, and comma-separated files are hard failures. UTF-8 only.

Headers, exactly, tab-separated:

- `source1_entity_id` tab `matched_entity_ids`
- `source1_entity_id` tab `candidate_entity_ids`

Every Source 1 entity in the file under test has exactly one row.

### Upload budget

Window: 25 September 2026, 12:00 AM IST, through 27 September 2026, 11:59 PM IST. At most 5 leaderboard submissions per day.

Spend zero on the evening of day 1 unless a trivial valid file is useful as a public-leaderboard anchor. If you do upload, write down `report` macro F₀.₅ and the public score side by side. That pair is a calibration of whether the frozen split moves with the leaderboard. It is not a target. Chasing the public rank burns the slots needed on day 3.

Final decision in the problem statement is the private leaderboard. The guidelines also say shortlisting uses both leaderboards. You cannot tune the private half. A public bump that fails the validator, the candidate-subset check, or that you will not stand behind on `report` macro F₀.₅ does not go up.

Keep every submitted version. Shortlisting uses the submitted solutions, and source code may be required again later.

### What you write, and when

§2.1 is a measured noise study, not a restatement of the PDF bullets. It has to contain: zero cross-country links, exclusive ids, Source 1 all Latin, the Source 2/3 script counts with Indic separated from accented Latin, the gold-pair script fractions once they exist, empty-address counts, the train/test country shift, and the France hole. It must not claim that record-level script rates are gold-pair rates, and it must not claim a France score.

§5 is filled from the last `report` error report: macro F₀.₅, the loss budget by list length, oracle F₀.₅, candidate recall, list width, false merges, false misses, singleton behavior. Do not write it from memory at the end. Do not replace the macro with a US/India reweight.

§1 and §6 take about two hours on day 3. Assemble sentences the others wrote. If a note is missing, the template shows the gap. Do not invent an architecture paragraph to make it look finished.

The guidelines ask for a 1–2 page document. The problem statement's template says there is no page limit and to prefer depth. Both are in the official PDFs. Do not invent a resolution. Person 1 compiles the template. The depth lives there. A short overview can be the executive summary, not a second conflicting design.

---

## Order of work

Day boundaries are coordination points. It is the evening of day 1 as of this plan. The split and the scorer have to exist before the other three can integrate. The noise essay can wait until morning.

### Tonight (rest of day 1)

1. Write the scorer and the three pytest locks, plus the predict-nothing baseline lock. This is the whole job if time runs out.
2. Draw `fit` / `loop` / `report` with a fixed seed. Publish the id files and `SPLIT.md`.
3. Build the attribute table and confirm the stratum counts match the totals in this plan.
4. Score predict-nothing on `report` so the command path is real. This does not require retrieval.
5. If those four are done, start the difficulty pack from `fit`, including a gold-file sample of low-overlap true pairs. If not, the pack slips to morning. The others debug against the pack and against `loop`, not against `report`.

Handoff the same night, even if crude: `loop` ids as the retrieval target, `report` ids as the frozen scoreboard, and the scorer command. The number that authorizes an upload is macro F₀.₅ on `report`. v0 is allowed to be crude. Integration on day 1 means candidates and a match list for `loop`, not for 221k ids.

### Day 2 morning

6. Join gold pairs to script. Separate Indic from accented Latin. Publish the two fractions before anyone schedules transliteration work.
7. Freeze short-name and generic-name cutoffs on `fit`.
8. Run the first error report on `loop` when Person 3's candidates and Person 4's match file exist. Lead with the loss budget by list length, then oracle versus actual next to list width, then India versus US.
9. Run the unknown-country behavior check. Do not treat empty France retrieval as a failure.
10. Start §2.1 from the counts in this plan plus the gold-join and the first `loop` report.

### Day 2 afternoon through day 3

11. Hourly error reports stay on `loop`. Score `report` only after an operating point is locked. Same slices, same pack. Say which person owns the gap.
12. Hold the upload gate: validator with `--check-ids`, every matched id already a candidate, and macro F₀.₅ on `report` that the team will stand on. A slice drop or a higher collision count is a reason to look at the loss budget. It is not, by itself, a rejected upload.
13. Day 3, after the operating point is frozen: full-test `matching_results.tsv` and `candidate_pairs.tsv` from Person 3 and Person 4, validator pass with `--check-ids`, then compile §1 and §6. Fill §5 from the last report.

Zip layout the package must match:

```
<team_name>_submission.zip
├── output/
│   ├── matching_results.tsv
│   └── candidate_pairs.tsv
├── code/
│   └── business_entity_resolution/
│       ├── src/
│       ├── README.md
│       └── requirements.txt
└── Documentation_template.md
```

Person 1's code lives under `src/eval/`. Person 1 does not own the match file or the candidate file. Person 1 does own the validator checkpoint and the compiled template.

If you finish early, pair on the miss list inside the error report. Do not take over another person's outcome.

---

## Definition of done

Person 1 is done when all of these exist:

- `SPLIT.md` plus `fit`, `loop`, and `report` id files, seed written down, stratum counts checked. `loop` is 5,000 ids outside `report`.
- A stdlib scorer whose pytest locks pass, including predict-nothing = singleton rate.
- A command that, given predictions and candidates, writes JSON with macro F₀.₅, US, India, singleton, non-singleton, the loss budget by error type and list length, oracle F₀.₅, candidate recall, candidates per entity, collision count, and the diagnostic slices. The command must say whether the ids were `loop` or `report`.
- A frozen difficulty-pack TSV of about 330 cases drawn from `fit`, including a low-overlap gold bucket and Indic separated from accented Latin.
- At least one error report from an integrated run, with causes assigned by the rule in this plan.
- Upload gate applied in writing to whatever file actually goes to the portal.
- §2.1 and §5 filled from those measurements. §1 and §6 compiled from the others' notes.

---

## What this will not do

A perfect scorer does not raise F₀.₅ by itself. The way this role wins is by showing, in macro points, which error type and which list length actually moved the average, and by refusing to aim the next day at a script rate or a reweighted country formula that was never the leaderboard.

France remains a 15% hole. No validation design closes it without labels you are not allowed to fetch. Indic names and accented Latin in train are not that missing label.

Public versus private is also a hole. You upload the full test set. The organizers split it at scoring time. The defense is the three upload checks, plus one log of `report` macro against the public score. It is not a second holdout that pretends to be their private slice, and it is not a pile of slice vetoes.

---

## Shared contracts this plan depends on

From `docs/work_distribution.md`. Change them only together.

| Contract | Producer | Consumers |
|---|---|---|
| Frozen validation Source 1 ids, plus the scorer | Person 1 | Everyone |
| Canonical record: entity id, country, normalized name, normalized address, derived tokens | Person 2 | Person 3, Person 4 |
| `candidate_pairs` for the validation Source 1 ids, then for full test | Person 3 | Person 4 |
| `matching_results` for those same ids | Person 4 | Person 1 |

Until Person 2's canonical records exist, the blocker and the matcher use raw fields, and your representation probe says it has not run.

Until Person 3's candidates exist, Person 4 studies gold matches and hard non-matches from your difficulty pack. You still score whatever match file comes back.

You score Person 4's file and return a slice report. You do not return a new model.

Code folders so four people are not editing the same file: `src/eval/`, `src/represent/`, `src/blocking/`, `src/matching/`. A thin `src/pipeline/` joins them at integration checkpoints.

One shared scoreboard: macro F₀.₅ on the frozen `report` split. The slices, the loss budget, and the oracle-plus-width sit beside that number. Hourly work uses `loop`. If Person 4 prints their own F₀.₅ and it disagrees with `src/eval/`, `src/eval/` is the number.
