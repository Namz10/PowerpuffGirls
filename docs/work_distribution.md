# Work distribution — four people

Assign names later. The tags below are roles, not rank.

This split is by **owned outcome**. Each person ships a technical artifact that can raise or lower the score, and each person can start from the training files without waiting on the others. The “how” is left open on purpose.

The challenge window is 25–27 September 2026, with at most five leaderboard uploads per day. The scored file is `matching_results.tsv`. The audited file is `candidate_pairs.tsv`. The metric is macro F₀.₅ per Source 1 entity, singletons included. Final model weights, if any, must be MIT or Apache 2.0 and at most 8 billion parameters. No registry, geocoder, or external identity lookup.

---



## Why this cut

The work has four decisions that cannot be collapsed into one person:

1. What “better” means on this data, and which errors are actually expensive.
2. How a noisy name and address become comparable, including an unseen country.
3. Which Source 2 / Source 3 records are even allowed to be considered.
4. Which of those candidates are true matches, including the choice to return nobody.

Those four decisions map to Person 1–4. Documentation, zip assembly, and portal uploads are shared checkpoints, not a fifth job and not one person’s whole role.

---



## Shared rules

- Train only on the provided files. Country is an open label. France is in test and absent from train. Do not hard-code the pipeline to `{US, India}`.
- Every test Source 1 entity gets one row. An empty list is a real prediction.
- Final match IDs are a subset of that entity’s candidate IDs.
- One shared scoreboard: macro F₀.₅ on a frozen validation split, plus the slices in Person 1’s pack. Nobody tunes to a private slice they invented alone.
- Code lands in separate folders so four people are not editing the same file: `src/eval/`, `src/represent/`, `src/blocking/`, `src/matching/`. A thin `src/pipeline/` joins them at integration checkpoints.
- Each person writes the methodology sections listed on their card. Person 1 compiles the template. They do not ghostwrite the others’ technical claims.
- Before any portal upload, the team agrees in one short checkpoint. Person 1 runs the validator. The team picks which file goes up, so the five daily slots are spent on purpose.

---



## Handoff contracts

Agree these on the first working session. Change them only together.


| Contract                                                                                          | Producer | Consumers          | v0, so nobody waits                                                               |
| ------------------------------------------------------------------------------------------------- | -------- | ------------------ | --------------------------------------------------------------------------------- |
| Frozen validation Source 1 IDs, plus the scorer                                                   | Person 1 | Everyone           | Scorer runs on raw strings the same day                                           |
| Canonical record: entity id, country, normalized name, normalized address, and any derived tokens | Person 2 | Person 3, Person 4 | Until it exists, blocker and matcher use the raw fields                           |
| `candidate_pairs` for the validation Source 1 IDs, then for full test                             | Person 3 | Person 4           | Until it exists, Person 4 studies gold matches and hard non-matches from Person 1 |
| `matching_results` for those same IDs                                                             | Person 4 | Person 1           | Person 1 scores it and returns a slice report, not a new model                    |


v0 is allowed to be crude. The point is that integration happens on day 1, not on the last evening.

---



## Person 1 — Measurement and error map

**Owns:** the team’s definition of progress, and the catalog of failures that tells the other three what to change.

**Ship:**

- A frozen validation split of Source 1 entities, with the rule for how it was frozen written down.
- A scorer that implements the official macro F₀.₅, including empty-list singletons, and that reports precision and recall beside it.
- Slice scores, at minimum: US, India, singleton vs non-singleton, empty address on the Source 2/3 side, short or generic names, lists of different lengths.
- A difficulty pack: confirmed true pairs, near-miss non-matches, and singleton cases, stable enough that Person 3 and Person 4 can debug against the same examples.
- An error report after each integrated run: false merges (wrong businesses joined) and false misses (true links dropped), each traced to representation, candidate generation, or the match decision.
- Validator pass/fail on every file before a portal upload.

**Creative work:** design a validation story that still means something when the test set contains France and when half the test set is hidden as the private leaderboard. Decide which slices are allowed to move the team’s next experiment. A single overall number will hide a blocker that drops India matches or a matcher that destroys singletons.

**Starts immediately:** ground truth and the three training sources are enough. No dependency.

**Writes in the template:** §2.1 Problem Analysis, §5 Results & Error Analysis, and the compilation of §1 and §6 from the other three people’s notes.

**Leaves to others:** normalized text, the candidate set, the match lists.

---



## Person 2 — Name and address representation

**Owns:** the shared text view of a record. Person 3 and Person 4 consume it. They do not each invent their own cleaner.

**Ship:**

- One function from a raw row to the canonical record in the handoff table.
- A written account of what the function does to legal suffixes, abbreviations, punctuation, word order, script mixing, transliteration, empty addresses, and landmark-style addresses.
- A country behavior that still returns a usable record for a label that never appeared in training.
- A token resource the others can use: which tokens are boilerplate (`Inc`, `Pvt`, `Ltd`, `Road`, and whatever else the data supports) and which are distinctive. Built only from the training files.
- A short before/after sheet on Person 1’s difficulty pack, so the team can see what the representation fixed and what it destroyed.

**Creative work:** this is the linguistic and structural problem in the challenge. The same business does not share a string. Train shows Devanagari names, a Kannada token inside an India address, empty addresses on Source 2 and Source 3, reordered US addresses, and legal-suffix noise. Test adds France. The representation has to survive all of that without a geocoder and without dropping unknown countries.

**Starts immediately:** raw training rows. No dependency.

**Writes in the template:** the name-feature and address-feature parts of §4 that describe representation, plus the noise findings Person 1 needs for §2.1.

**Leaves to others:** which records become candidates, which candidates become matches, the official score.

---



## Person 3 — Candidate generation

**Owns:** recall. A true Source 2 or Source 3 id that never enters the candidate list cannot be recovered later. Also owns `candidate_pairs.tsv`, defined as the set the matcher actually scores, not an earlier superset.

**Ship:**

- A candidate list per Source 1 entity, including a legal empty list when retrieval finds nobody.
- On the frozen validation split: candidate recall (fraction of true match ids present) and a size report (how many candidates per entity, and the total).
- A miss list: true ids that were not retrieved, grouped by the slice tags from Person 1, handed back the same day.
- The full-test `candidate_pairs.tsv` once the validation recall is acceptable to the team.
- Proof that every id Person 4 keeps is already in this file.

**Creative work:** the comparison space is about 2.2 million Source 1 rows against about 10.3 million Source 2 and Source 3 rows. The invention is a retrieval scheme that keeps true matches, stays computable on the machines you actually have, and does not hand Person 4 a list so wide that precision collapses. Multi-match labels matter: most training entities have several true ids, usually in both sources.

**Starts immediately:** on raw fields. Swap in Person 2’s canonical records when they land, and re-measure recall. Do not block on a perfect normalizer.

**Writes in the template:** §3 Candidate Generation, and the blocking half of §2.2.

**Leaves to others:** the final keep/drop decision, the F₀.₅ threshold, text normalization policy.

---



## Namita — Match decisions

**Owns:** precision under the official metric, and `matching_results.tsv`. For each Source 1 entity, the output is a set: zero, one, or many Source 2/3 ids, drawn only from that entity’s candidates.

**Ship:**

- A decision procedure that takes one Source 1 record plus its candidates and returns a subset.
- Validation predictions on Person 1’s frozen split, then full-test `matching_results.tsv`.
- A written rule for the empty prediction. Singletons are 123,247 training entities. A correct empty scores 1.0 on that entity. Any false id scores 0.0.
- A written rule for multi-id lists. Training lists run up to 11 ids, and the bulk sit between 2 and 5. A top-1-only output cannot represent the labels.
- The precision/recall operating point the team agrees to submit, justified on Person 1’s slices rather than on one pooled number.

**Creative work:** false merges cost more than misses, but misses still cost, and both source families must be recoverable. The invention is the keep/drop rule and how aggressive it is, entity by entity, including the decision to return nobody.

**Starts immediately:** gold pairs and hard non-matches from Person 1. Move to Person 3’s real candidate lists as soon as they exist. Do not wait for the final blocker to start studying matches.

**Writes in the template:** §4 Matching Model, the decision half of §2.2, and the false-merge / false-miss notes Person 1 uses in §5.

**Leaves to others:** retrieval, the candidate file, the scorer, text normalization policy.

---



## How the three days fit

Day boundaries are coordination points, not gates that idle someone.

**Day 1 — four v0 artifacts, one integrated score.**
Person 1 freezes the split and publishes the scorer and difficulty pack. Person 2 publishes a first canonical record. Person 3 publishes validation candidates and a recall number. Person 4 publishes validation match lists, first on gold pairs, then on those candidates if they are ready. End the day with one macro F₀.₅ and the slice sheet.

**Day 2 — each person answers their own misses.**
Person 1’s report names where the score was lost. Person 2 changes the representation only where the sheet shows it helps. Person 3 closes holes in the miss list without a blow-up in list size. Person 4 moves the keep/drop rule using the slice scores. Integrate once more. Spend a leaderboard slot only if the local score and the validator both agree the file is a real step.

**Day 3 — freeze, then submit the package.**
One agreed operating point. Full-test `candidate_pairs.tsv` and `matching_results.tsv`. Validator pass. Each person finishes their template sections. Person 1 compiles. The zip matches the required layout: `output/`, `code/business_entity_resolution/` with `src/`, `README.md`, `requirements.txt`, and `Documentation_template.md`.

If a person finishes early, they pair on the miss list in their own artifact. They do not take over another person’s outcome.

---



## Fairness check


|                                 | Person 1                                   | Person 2                                                          | Person 3                          | Person 4                     |
| ------------------------------- | ------------------------------------------ | ----------------------------------------------------------------- | --------------------------------- | ---------------------------- |
| Can start with zero waiting     | Yes                                        | Yes                                                               | Yes                               | Yes                          |
| Artifact that moves the score   | Scorer, slices, what the team trusts       | Shared representation                                             | Recall ceiling, candidate file    | Scored match file            |
| Creative decision               | What we are allowed to call an improvement | What “the same string” means across scripts and an unseen country | What is retrievable at this scale | What is safe to merge        |
| Mechanical work they also carry | Validator, template compilation            | Before/after sheet                                                | Size and recall tables            | Empty-list and subset checks |
| Template sections               | 2.1, 5, compile 1 and 6                    | Representation parts of 4, inputs to 2.1                          | 3, blocking half of 2.2           | 4, decision half of 2.2      |


Person 1’s compilation pass is real work and is capped: assemble what the others wrote, do not re-research it. Person 3 and Person 4 own the two files the organizers actually look at. Person 2 owns the input both of those files depend on. Nobody is the documentation person and nobody is the only model person.