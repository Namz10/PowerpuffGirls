# Phase 3 Handoff — Person 3 (Srishti)

The frozen Phase 2 blocker now has a guarded Phase 3 execution path in
`src.blocking.phase3` and `src.blocking.cli`.

## Completed artifact audit

- `phase2_fit400k_candidate_pairs.tsv`: 400,000 unique data rows, exactly the
  frozen fit sample; SHA-256 `bd2bb5209675cefc2da43aa20ba26e0f4745897d0ed4b2298b785f38ffab6ba3`.
- `phase2_fit400k_candidate_provenance.tsv`: 16,108,924 lines including the
  header; SHA-256 `d55b4573c9f9b241ef7d9bd96e09517d82c1c7327fadb86dbcc7ab702aeaa05f`.
- `phase2_loop_candidates.tsv`: 25,000 unique data rows, exactly the frozen
  loop split; SHA-256 `a423048b1562ccc58abf7b4abd32035b5b68b3a89a4c4dc845f37bbf583fb22e`.
- The loop provenance and miss audit hashes are recorded in
  `phase3_loop_reproduction_proof.json`, whose status is `passed`.

The previously packaged loop TSVs were truncated/padded previews. The complete
replay artifacts replace them, and the loop report, blocker freeze, and Phase 2
gate now point to the verified complete hashes. The 400k artifacts already
matched their gate fingerprints and were not changed.

## Loop reproduction

Run this before candidate generation for the final report split. It regenerates
the 25,000 labeled `loop` rows, verifies the frozen index and boilerplate
fingerprints before retrieval, and writes a proof only if candidate,
provenance, and miss TSV hashes exactly match the frozen Phase 2 evidence.

```bash
python3 -m src.blocking.cli phase3-reproduce-loop \
  --freeze artifacts/blocking/phase2_blocker_freeze.json \
  --index artifacts/blocking/train_canonical_v1.sqlite \
  --source1 dataset/train/train_source1.tsv \
  --ids src/eval/splits/loop_ids.txt \
  --truth dataset/train/train_ground_truth.tsv \
  --output artifacts/blocking/phase3_loop_candidates.tsv \
  --provenance artifacts/blocking/phase3_loop_provenance.tsv \
  --misses artifacts/blocking/phase3_loop_misses.tsv \
  --report artifacts/blocking/phase3_loop_report.json \
  --proof artifacts/blocking/phase3_loop_reproduction_proof.json
```

Do not use the report split to debug a mismatch. A mismatch is a retrieval,
index, normalization, resource, or packaging defect and must be investigated
against the frozen loop evidence.

## Locked report candidates

This command intentionally refuses a skeleton or mismatched decision config.
It requires Namita's config to be `locked`, validly hashed, and bound to the
same frozen 400k fit-candidate fingerprint. It does not accept truth or run
any sweep.

```bash
python3 -m src.blocking.cli phase3-generate-report \
  --freeze artifacts/blocking/phase2_blocker_freeze.json \
  --decision-config artifacts/matching/phase3/decision_config.json \
  --index artifacts/blocking/train_canonical_v1.sqlite \
  --source1 dataset/train/train_source1.tsv \
  --ids src/eval/splits/report_ids.txt \
  --output artifacts/blocking/phase3_report_candidate_pairs.tsv \
  --provenance artifacts/blocking/phase3_report_candidate_provenance.tsv \
  --report artifacts/blocking/phase3_report_candidate_report.json \
  --manifest artifacts/blocking/phase3_report_candidate_manifest.json
```

The manifest is the handoff to matching. It binds the report candidates to the
Phase 2 blocker freeze, its retrieval config, Namita's decision config, the
400k fit-candidate hash, the requested report IDs, and candidate/provenance
hashes.
