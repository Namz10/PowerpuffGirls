# Phase 1 blocking evidence

The JSON files in this directory are the committed evidence for Person 3's
Phase 1 raw blocker: input/index manifests, the loop cap sweep, the selected
loop run, and the single readiness report run.

Candidate, provenance, and miss-audit TSVs are reproducible local artifacts.
They are intentionally excluded by the repository-wide challenge-data policy;
their row counts and SHA-256 fingerprints are recorded in the reports and in
`src/blocking/phase1_manifest.json`. The multi-gigabyte SQLite indices are also
local-only and can be rebuilt with the commands in the repository README.
