# Matching-side contract review

Status: **APPROVED — no contract changes required**

The Phase 1 matching-side review verified that:

- the candidate headers match the generator, strict subset checker, and supplied
  submission validator;
- the ten provenance columns are sufficient to join raw S1/S2/S3 records and
  audit target source, retrieval channel, rank, and retrieval score;
- all 25,000 loop S1 rows, 828,935 candidate pairs, and 828,935 provenance rows
  agree on candidate order, rank, source prefix, provenance labels, and flags;
  and
- `candidate_pairs.tsv` is unambiguously the exact set the matcher must score.

Repository audit found no `src/matching/`, matching model, inference program, or
`matching_results.tsv` in the worktree or available Git refs. Consequently,
the contract is approved, but an actual Person 4 prediction handoff and its
final subset proof remain external integration dependencies; candidate
generation must not invent those predictions.
