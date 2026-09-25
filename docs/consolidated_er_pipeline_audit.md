# Ruthless audit — Consolidated ER pipeline plan

Audit of [.cursor/plans/consolidated_er_pipeline_cf74755a.plan.md](.cursor/plans/consolidated_er_pipeline_cf74755a.plan.md).

Single source of truth (SSOT): [docs/Problem Statement.pdf](docs/Problem%20Statement.pdf) and [docs/guidelines_and_key_instructions_amazon_ml_challenge_2026.pdf](docs/guidelines_and_key_instructions_amazon_ml_challenge_2026.pdf). Cross-checked against [docs/validate_submission.py](docs/validate_submission.py), [docs/Documentation_template.md](docs/Documentation_template.md), [docs/work_distribution.md](docs/work_distribution.md), [docs/problem_understanding_and_research.md](docs/problem_understanding_and_research.md), and the raw dataset on disk. Per instruction, the four individual role plans were **not** read; this audits only the consolidated plan against the SSOT and the data.

Severity legend: **[BLOCKER]** can lose the hackathon or reject the submission · **[HIGH]** materially costs score · **[MEDIUM]** meaningful ROI · **[LOW]** polish / judgment call.

---

## 0. Verdict

**Current engineering rating: 4.0 / 5.** This is an unusually disciplined plan — well above typical hackathon quality. Its factual foundation is real (I re-measured every headline number against the dataset and they are exact), it is faithful to the problem statement's intent, and its hardest decisions (hard country-equality blocking, one-owner assignment, expected-F set selection) are each grounded in a *verified* property of the data rather than a guess.

It is held back from 5/5 by **one quantified recall hole (cross-script Indic matching) that is currently deferred with no committed fallback**, a **statistically under-powered operating-point set (`loop` = 5,000)**, and a handful of de-risking / edge-case gaps. None of the fixes below require changing the core architecture you and your teammates designed. They harden it.

---

## 1. Facts I verified against the real dataset

Every one of these was recomputed from the TSVs on disk. The plan's Section 2 is **accurate — not hallucinated.**

- Test Source 1 = **1,732,544**; India **809,986 (46.8%)**, US **663,106 (38.3%)**, France **259,452 (15.0%)**. Exact match to the plan.
- Ground truth: **2,206,821** rows; **123,247** empty (predict-nothing baseline = 123,247 / 2,206,821 = **0.05586**, exactly as claimed); **7,638,365** links; S2 links **3,693,619**; S3 links **3,944,746**; max list length **11** with **37** entities at length 11. All exact.
- **Every matched S2/S3 id appears in exactly one Source 1 list** (distinct matched ids 7,638,365 == total links; ids linked to >1 S1 = **0**). This *confirms* the assumption under Person 4's one-owner assignment step. Good.
- **France exists in test Source 2 (703,378) and Source 3 (731,615).** This *confirms* France-to-France blocking and the France IDF-from-test approach are actually executable. Good.
- **Gold links are 100% same-country (0 cross-country out of 7,638,365).** This *confirms* the hard country-equality blocking loses zero recall on train. This is the single biggest reduction lever in the plan and it is safe.

**New measurement the plan does not contain (and should):** among India gold links, **23.51%** have a **non-Latin (non-ASCII) target name** on the Source 2/3 side (719,443 of 3,059,843 links); US is **7.46%** (341,338 of 4,578,522). Since Source 1 names are 100% Latin, this is the size of the **cross-script matching problem** — see Finding 2.1.

---

## 2. Part 1 — Alignment with the SSOT: gaps, fallacies, PS-intent risks

### 2.1 [BLOCKER] Cross-script (Latin ↔ Indic) matching is deferred with no committed fallback

- **What the plan does.** Person 2 does NFKC, lowercase, suffix mapping, punctuation stripping — but **no transliteration/romanization**. The plan explicitly defers the decision: Day 2, "gold-join of script, Indic fraction versus accented-Latin fraction, **before anyone schedules transliteration**." Person 4 has only a `script` flag feature; Person 3 has a `REPRESENTATION_DESTROYED_SIGNAL` miss code. There is a script *diagnostic* everywhere and a script *solution* nowhere.
- **Why it is a blocker.** India is **46.8% of the test set**, and I measured that **23.5% of India's true matches carry a non-Latin name** on the target side while the Source 1 name is always Latin. Every name channel in Person 3 (exact name, name+postal, name-token signature, rare-token name retrieval, char n-grams) is a **Latin-vs-Devanagari/Kannada/Tamil comparison that returns nothing**. Those ~720k India links can only survive through address/postal channels — which in India are the *noisiest* fields (landmark refs, missing PIN, reordering). This is a large, structural recall ceiling hit on the biggest slice, and it is the difference between top-50 and mid-pack.
- **Why "measure first, then decide on Day 2" is the wrong sequencing.** Building a robust offline transliteration path on Day 2–3, on the critical path, under time pressure, with Person 3/4 waiting on it, is exactly how this gets half-built and shipped broken. The measurement is worth doing, but the *fallback must already exist*.
- **Fix (no architecture change — it lives inside Person 2's existing normalizer and Person 3's existing channels).** Pre-build an **offline, rule-based romanization** (ISO-15919 / ITRANS-style deterministic transliteration for Devanagari + the other Indic scripts present) applied inside Person 2 so both sides land in a common Latin space; then the existing name channels and a phonetic key (see 4.4) work cross-script. This is offline, deterministic, ships no external data, and does not touch the fair-play rule. If you use any transliteration model, it must satisfy the MIT/Apache + 8B rule — which is another reason to prefer rules. This directly serves the PS "transliteration variants" noise item that is currently unaddressed.

### 2.2 [MEDIUM] Missing `0/0` guard in the metric and its pytest locks

- The plan defines the F₀.₅ cases for empty/empty, empty-truth/non-empty-pred, and empty-pred/non-empty-truth — but **not the case where truth and prediction are both non-empty and disjoint** (|P∩T| = 0). Then P = R = 0 and the formula `1.25·P·R / (0.25·P + R)` is **0/0**. The pytest locks listed (PDF example = 0.714, empty/empty = 1.0, empty-truth = 0.0, predict-nothing = singleton rate) do **not** cover this.
- This is not academic: a matcher that returns the wrong id for a singleton-adjacent entity hits this constantly. An unguarded scorer will crash or emit NaN and silently corrupt the macro average.
- **Fix.** State the convention (P=R=0 → F=0) and add a pytest lock for "non-empty truth, non-empty prediction, zero overlap → 0.0". One line of code, one test.

### 2.3 [MEDIUM] French legal-suffix and address coverage is thin for a 15% unseen slice

- Person 2's suffix map covers `gmbh, sarl, sa, bv` but **misses the most common French forms**: `SAS`, `SASU`, `EURL`, `SCI`, `SNC`, `SC`. France is 15% of test and has **zero** training rows, so any French-specific normalization gap is pure, uncorrected loss.
- `CEDEX` is handled (good). But French address grammar (e.g., `BP` for boîte postale, arrondissement/`e` ordinals) is not mentioned.
- **Fix.** Expand the French legal-suffix list and add a small French address-token pass. Cheap, and it is the only lever you have on a slice with no labels.

### 2.4 [LOW] "France ... unscored" phrasing

- Section 3 says "France is stated as 15.0% of test Source 1 and unscored." In context this means *unscored in local validation* (no train labels), which is correct — but France **is** scored on the real public/private leaderboard. Make sure nobody on the team internalizes "France doesn't count." It is 15% of your actual grade.

### 2.5 [LOW] Public leaderboard is slightly under-weighted vs the guidelines

- The plan says "Public rank is not a target" and leans entirely on the private leaderboard (correct per the PS's "final decision"). But the **guidelines** explicitly say "evaluation and shortlisting will be based on performance across **both** leaderboards." Treating public as noise-only slightly contradicts the guidelines' shortlisting rule.
- **Fix.** Keep private as the optimization target, but track public as a *monitored signal* (public-vs-`report` gap = your overfitting / distribution-shift alarm, especially for France).

**PS-intent compliance check (passes):** country-open, no `{US,India}` hard-code (verified safe), no external lookup, precision-heavy set selection, singletons first-class, `candidate_pairs.tsv` defined as the exact scored set. No blasphemy against the PS intent. The France-IDF-from-test-input is transductive use of *provided* data, not external augmentation — defensible and smart.

---

## 3. Part 2 — Decisions missed or still undecided after the bridge

These are the seams where four independent plans were stitched together and a decision fell through.

### 3.1 [HIGH] The operating point is chosen on only 5,000 `loop` ids — statistically under-powered

- `loop` = 5,000 ids, stratified over country(2) × bucket(5) = 10 strata ≈ **500 ids/stratum**. On this set the team chooses: Person 3 caps/quotas, Person 4's one-owner on/off, **and** the set-rule family (expected-F vs one global threshold vs per-source thresholds). Meanwhile `report` is ~221,000.
- Competing operating points frequently differ by **< 0.005 macro F₀.₅**. On 5,000 samples the standard error of a per-entity mean bounded in [0,1] is easily ±0.004–0.006. **You will routinely pick the noise, not the winner** — and then confirm it on `report` only once, after lock.
- This is the classic bridging gap: nobody re-derived whether 5,000 is *powered* for the number of decisions being made on it.
- **Fix (no architecture change):** (a) enlarge `loop` to ~20–30k (still leaves `report` untouched and clean); and/or (b) report a **bootstrap 95% CI** on `loop` macro for every candidate config and only prefer a config whose gain clears the CI. Cheap, and it stops you shipping a worse operating point.

### 3.2 [MEDIUM] The Day-1 "no portal upload" rule wastes the cheapest de-risking you have

- The plan bans any portal upload on Day 1 and makes the first upload Day 2 after the gate. Rationale ("a slot is not a format check") is reasonable but overcorrects. The research doc itself lists **"portal quirks, file size caps" as unverified**. The local validator cannot catch a portal-side encoding/size/header quirk.
- With 5 slots/day × 3 days = **15 slots**, spending **one** on Day 1 with a trivially-correct predict-nothing file (known score 0.056) confirms **SCORED** status and the true portal contract before you are under Day-3 deadline pressure. That is the highest-ROI slot you own.
- **Fix.** One sacrificial Day-1 format-probe upload (predict-nothing). Keep the "no *real* model upload until the gate" discipline for the other slots.

### 3.3 [MEDIUM] The critical path P2 → P3 → P4 all converges on Day 2 — fragile

- Person 2's canonical records land Day 2; Person 3's *real* (canonical, frozen) candidates depend on them; Person 4's *real* training depends on Person 3's frozen 400k `fit` candidates. All three "real" milestones stack on Day 2. If Person 2 slips even half a day, blocking, training, calibration, the one-owner ablation, and the set-rule choice all compress into Day 3.
- The plan does say "until canonical exists, use raw fields," but there is **no committed checkpoint that a full raw-field end-to-end (retrieval → features → model → `report` score) is green by end of Day 1.** The mitigation is stated as a fallback, not scheduled as a gate.
- **Fix.** Make "raw-field full pipeline produces a real `report` macro" a **hard Day-1 exit gate**. Then canonical records are pure upside on Day 2, not a single point of failure.

### 3.4 [MEDIUM] Scope/execution risk is not bounded (MoSCoW missing)

- The plan is extremely ambitious for 3 days / 4 people: Person 3 channels A–F + guarded expansion + Pareto sweep; Person 4 two-pass features + isotonic + one-owner ablation + expected-F derivation + LOCO + Optuna; Person 1 ~20 slices + difficulty pack + reason-coded miss TSVs. Every item is individually justified; collectively it is a lot of surface to finish *and debug* before freeze.
- No decision states **what gets cut first if you are behind.** In a 25k-team field, a robust end-to-end fully executed beats an elaborate one half-built.
- **Fix.** Add an explicit **Must/Should/Could** tier. Must: country-equality blocking + exact/rare-token channels + LightGBM pass-1 + one global threshold + one-owner. Should: pass-2 context features, expected-F rule, char n-grams. Could: Optuna, guarded expansion, the long tail of slices. Freeze in that order.

### 3.5 [LOW] The one-owner assumption is extrapolated to test/France

- Verified true in train (0 ids shared across S1). The plan gates the step on `loop` (train), which is right, but the *property itself* is assumed to hold on test including France. It almost certainly does (Source 1 is the deduplicated reference), but note it as an explicit assumption in the write-up rather than silently.

### 3.6 [LOW] Boilerplate threshold is a single global 1.0%

- `boilerplate_tokens.json` uses a flat 1.0% document-frequency cut across all training records. Indian and US boilerplate differ ("pvt", "ltd", "nagar", "marg" vs "inc", "llc", "ave"). A single global cut either over-suppresses one country's real signal or under-suppresses the other's noise. The plan already computes IDF **per country** — the boilerplate list should be per country too, for consistency.

---

## 4. Part 3 — Engineering upgrades: 4/5 → 5/5 (no architecture change)

Ranked by ROI. Each fits inside the existing role boundaries and file layout.

### 4.1 [HIGH ROI] Ship offline Indic romanization (this is Finding 2.1, restated as the top upgrade)
The single highest-value change. Recovers the ~23.5% of India links currently unreachable by name channels. Lives inside Person 2 + Person 3's existing multi-channel design. Prebuild it; do not defer it.

### 4.2 [HIGH ROI] Power up the operating-point selection (Finding 3.1)
Bootstrap CIs + a larger `loop`. Turns "we picked the config that looked best on 5k" into "we picked the config whose gain is real." Directly protects the number you upload.

### 4.3 [MEDIUM-HIGH ROI] Per-country isotonic calibration
The plan calibrates isotonic on out-of-fold pass-2 scores **globally**, with per-country reliability *curves* for inspection only. US and India have visibly different score distributions (different noise, different name entropy). **Calibrate per country** where labels exist (US, India); for France, use the calibration of whichever of US/India the drift check says France is closer to. Better-calibrated probabilities feed the expected-F set rule directly — this improves the *precision* the metric doubly rewards, at near-zero cost.

### 4.4 [MEDIUM-HIGH ROI] Add a phonetic blocking channel
`jellyfish` is already a Person 4 dependency. Adding a **Double Metaphone** (on romanized names, post-4.1) or a `Soundex`-style key as an *additional* Person 3 channel is additive within the explicitly-extensible A–F design. It cheaply rescues typo and transliteration near-misses ("Tetlecommunication" ↔ "Telecommunication") that exact/token channels drop. This is exactly the PS "typos / transliteration variants" case, and the PS tips section explicitly says to invest in blocking.

### 4.5 [MEDIUM ROI] Seed/fold-bagged inference for stability
Person 4 already trains 5 GroupKFold models for OOF scores. At inference, **average the 5 fold models** (or 3 seeds) instead of retraining one. Small, free variance reduction on the precision-critical scores — meaningful when configs differ by <0.005 and the private slice is hidden.

### 4.6 [MEDIUM ROI] Make the France drift-check an explicit gate, not a note
Person 4 has a drift check (France vs US/India on list-size, empty-rate, score histogram) with one trigger ("empty-rate > 2× → investigate"). Promote it to a **pre-upload gate with numeric thresholds** on all three distributions, since France is 15% and blind. A France distribution that silently collapses is the most likely way this plan loses the private leaderboard.

### 4.7 [LOW ROI] Replace the E[F_k] plug-in with a direct per-bucket grid on `loop`
The closed form `E[F_k] ≈ 1.25·Σp / (0.25k + E|T|)` is a ratio-of-expectations approximation (E[F] ≠ F[E]); it ignores calibration-error correlation. Since the rule family is already chosen on `loop` by the real scorer, you can skip the approximation and **grid-search k directly per candidate-count bucket** on `loop`. Simpler, exact under the real metric, one fewer thing to be subtly wrong. Keep the closed form only as the initialization.

---

## 5. Part 4 — What is right; do not touch

Credit where due — these are the load-bearing calls, and they are correct:

- **Hard country-equality blocking.** Verified to lose 0 recall (0 cross-country gold links). Massive, safe reduction.
- **One-owner assignment.** Grounded in the verified fact that every S2/S3 id has exactly one true S1 owner. Principled, and correctly gated on `loop` with the thief risk called out.
- **`candidate_pairs.tsv` = exactly the scored set, with the width cap applied inside Person 3.** This matches the PS's precise definition ("the last stage ... whatever your model actually runs inference over") and keeps the audited file honest.
- **Frozen `report`, operating point locked on `loop` first.** Textbook leakage discipline.
- **Classical LightGBM over a transformer/GNN/LLM.** Correct for dirty structured text, 3-day budget, and the MIT/Apache + 8B license rule. No pretrained weights = trivial license compliance.
- **France IDF from test input.** Transductive use of provided data; not external lookup.
- **Reproducibility spine** (seed=42, manifests, fingerprints, deterministic order, `SPLIT.md`). This is what gets a top-team package through the reproducibility review the PS warns about.
- **Not using `sklearn.metrics.fbeta_score`; a stdlib scorer as the single source of the number.** Correct — avoids a subtle multilabel-vs-per-entity-set mismatch.

---

## 6. Prioritized action list

1. **[BLOCKER]** Pre-build offline Indic romanization inside Person 2; wire it into Person 3's name channels. Quantified exposure: ~23.5% of India links. (2.1 / 4.1)
2. **[HIGH]** Power up operating-point selection: enlarge `loop` to ~20–30k and/or add bootstrap CIs before preferring any config. (3.1 / 4.2)
3. **[HIGH]** Make "raw-field full end-to-end produces a real `report` macro" a hard Day-1 exit gate; canonical becomes pure upside. (3.3)
4. **[MEDIUM]** Add the `0/0` metric guard and its pytest lock. (2.2)
5. **[MEDIUM]** One sacrificial Day-1 predict-nothing portal upload to confirm SCORED + portal quirks. (3.2)
6. **[MEDIUM]** Expand French legal-suffix + address coverage (SAS, SASU, EURL, SCI, SNC, BP). (2.3)
7. **[MEDIUM]** Per-country isotonic calibration; France borrows the closer of US/India. (4.3)
8. **[MEDIUM]** Add a phonetic (Double Metaphone) blocking channel on romanized names. (4.4)
9. **[MEDIUM]** Promote the France drift-check to a numeric pre-upload gate. (4.6)
10. **[MEDIUM]** Add a Must/Should/Could freeze order to bound scope risk. (3.4)
11. **[LOW]** Fold/seed-bagged inference; per-country boilerplate; direct per-bucket `k` grid; public-leaderboard-as-signal; state the one-owner test assumption. (4.5, 3.6, 4.7, 2.5, 3.5)

---

### Honesty note on my own limits
- I did **not** read the four individual role plans (per your instruction), so any decision that exists only inside those and was dropped during consolidation is out of scope here.
- The 23.5% / 7.46% cross-script figures count **any non-ASCII target name**, which lumps true Indic scripts together with accented Latin (e.g., `Límited`); accented-Latin is partially bridgeable by char n-grams, so the *truly* unreachable-without-transliteration share is somewhat below 23.5% but still large and India-dominated. I did not separate them by Unicode block — that is the exact measurement Person 1's Day-2 gold-join should produce, and it is worth doing before sizing the transliteration effort.
- I did not attempt to fetch the challenge video or best-practices blog (not present locally, and fetching would risk the external-data line); those remain unread, as the research doc already noted.
