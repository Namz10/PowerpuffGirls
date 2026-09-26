# Phase 2 handoff — Person 4 (Namita)

Status: **feature schema frozen; Phase 1 threshold not retuned**

The pair-feature schema is `artifacts/matching/phase2/feature_schema.json`. Its SHA-256 is in `artifacts/matching/phase2/manifest.json`.

- Phase 1 raw features stay in the schema.
- Phase 2 adds normalized, romanized, accent-folded, phonetic, per-country IDF, postal, CEDEX, and script evidence.
- Phonetic codes are Metaphone (`jellyfish`, MIT) on `romanized_name`, computed in matching. Current jellyfish removed Double Metaphone for license reasons. They are not a second blocker.
- `phase1_provisional_threshold` is the loop-only baseline. This handoff does not move it.
- Phase 3 still owns GroupKFold, fold averaging, isotonic calibration, one-owner assignment, and the set rule.
- France has no local labels. Every France Source 1 id must still receive a row. Do not tune a France threshold on unlabeled data.
- The 50,000-id fit candidate file under `artifacts/matching/inputs/` is the Phase 1 training distribution. It is not Srishti's 400,000-id Phase 2 fit candidate file.
