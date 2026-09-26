# Candidate-to-matcher contract (Phase 1)

This is the interface Srishti (candidate generation) hands to Namita (match
decisions). It is frozen before the Phase 1 matcher is integrated.

- The exact inference set is `candidate_pairs.tsv`, with exactly two columns:
  `source1_entity_id` and `candidate_entity_ids`.
- It contains one row for every requested S1 ID, including France and empty
  candidate lists. Candidate IDs are unique existing S2/S3 test IDs.
- The matcher scores every pair in this file and no pair outside it. Therefore
  every ID emitted in `matching_results.tsv` must occur in the corresponding
  candidate row.
- Candidate order is deterministic retrieval rank; it is not a match decision.
- Pair-level audit provenance uses these frozen columns:
  `source1_entity_id`, `candidate_entity_id`, `target_source`, `provenance`,
  `rank`, `exact_name`, `exact_address`, `name_token`, `address_token`, and
  `retrieval_score`.
- `provenance` is a comma-separated combination of `exact_name`,
  `exact_address`, `rare_name_token`, and `rare_address_token`. The four flag
  columns are the machine-readable equivalent.
- Development miss audits use `source1_entity_id`, `truth_entity_ids`,
  `candidate_entity_ids`, `missed_truth_ids`, `status`, and `miss_reason`.
  `miss_reason` is one of `cap_truncation`, `no_retrieval_evidence`,
  `no_retrieval_evidence_for_truth`, or
  `mixed_cap_and_no_retrieval_evidence`; complete rows have a blank reason.

Phase 1 uses only raw fields, Unicode-preserving local normalization, exact
keys, and token retrieval. Country is an open equality label and S2/S3 indices
are queried separately. No external business lookup or geocoder is used.
