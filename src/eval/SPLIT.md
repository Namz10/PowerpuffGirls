# SPLIT

Frozen Source 1 assignment for evaluation. Do not redraw.

## Contract

- Unit is the Source 1 `entity_id`. A gold link is never assigned apart from its Source 1 id.
- Strata are observed country × gold-list bucket `{0, 1, 2–3, 4–5, 6+}`. Length 11 folds into `6+`. Countries are whatever labels are in the file. They are not restricted to `{US, India}`.
- `report` receives `(stratum size × 10) // 100` ids from each stratum. That is the floor of 10 percent.
- `loop` receives exactly 25000 ids drawn from outside `report`. Within that budget, seats are proportional to stratum size by the largest-remainder method: base = `(25000 × size) // total`, and leftover seats go to the largest `(25000 × size) % total`, ties broken by country then bucket order.
- `fit` is every remaining Source 1 id.
- `report` is scored only for the predeclared Phase 1 raw-pipeline readiness run, then left untouched until the Phase 3 operating point is locked on `loop`. It does not select features, caps, quotas, thresholds, or other loop decisions.
- No threshold, cap, quota, or set rule is chosen on `fit`.

## Assignment

Seed `42` on CPython 3.11. One `random.Random(42)` walks strata in `(country, bucket)` order. Inside a stratum the ids are sorted, shuffled, then cut: report, then loop, then fit. Published files are sorted lexicographically, one id per line, UTF-8, LF, trailing newline, no header.

## Cardinalities

| Split | Ids |
|---|---:|
| fit | 1961144 |
| loop | 25000 |
| report | 220677 |
| all Source 1 | 2206821 |

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

## Reproducibility

Rebuild with `python3.11 -m src.eval.build_split` from the repository root. Check with `python3.11 -m src.eval.build_split --check`. Input location defaults to `../student_resource/dataset/train` and may be overridden with `EVAL_TRAIN_DIR`. Committed config stores that relative path only.

## Fingerprints

SHA-256 of the exact file bytes.

| File | SHA-256 |
|---|---|
| `src/eval/splits/fit_ids.txt` | `206ba5c0c08e9bef9984ca6370e0845b84757d5d1a736b2de2c7db06982f9d42` |
| `src/eval/splits/loop_ids.txt` | `ffc47cbc3b5585c2ac163335ec518a5efc220e5dd49066788cf97de796abe3ac` |
| `src/eval/splits/report_ids.txt` | `0f33644ee6a55a5d1df3ea176fe37aef56e1b3d6260f1037602d22d6002fa186` |
| `../student_resource/dataset/train/train_source1.tsv` | `591af0e1dfeb65cab71ea6ee8cb69df00f92d6ba6fa79e05746c938775d14973` |
| `../student_resource/dataset/train/train_ground_truth.tsv` | `70bc1d8a16c667e0155c2105d0ab2ebe41d7e7a85d8a529e3ca81c6c3a5af037` |
| `src/eval/splits/manifest.json` | `b71e79bbb97afd99be4c199d299bda8144c56fe0a5659771a376269dffcadf54` |
