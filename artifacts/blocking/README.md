# Blocking evidence

The JSON files in this directory include the committed evidence for Person 3's
Phase 1 raw blocker: input/index manifests, the loop cap sweep, the selected
loop run, and the single readiness report run.

Phase 2 is closed. `phase2_blocker_freeze.json` records the frozen canonical
SQLite blocker configuration and linked hashes; `phase2_fit400k_report.json`
records the CPU-first, streaming 400,000-entity fit handoff. The corresponding
formal gate is `artifacts/gates/phase_2.json`.

Candidate, provenance, and miss-audit TSVs are reproducible local artifacts.
They are intentionally excluded by the repository-wide challenge-data policy;
their row counts and SHA-256 fingerprints are recorded in the reports and
freezes. The multi-gigabyte SQLite indices are also local-only and can be
rebuilt with the commands in the repository README.
