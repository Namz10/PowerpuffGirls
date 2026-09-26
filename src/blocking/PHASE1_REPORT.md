# Phase 1 raw-blocker report

Configuration: `phase1-raw-v1`; frozen split: `loop` (25,000 S1 IDs); seed
and membership are inherited unchanged from `src/eval/splits/manifest.json`.
Only same-country S2/S3 targets were eligible. S2 and S3 were queried through
separate exact-name, exact-address, rare-name-token, and rare-address-token
indices. No external lookup or geocoder was used.

## Measured cap frontier

| Cap | Link recall | Complete-entity recall | Mean | p95 | p99 | Max | Candidate pairs | Reduction ratio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 0.395230 | 0.138578 | 4.269 | 5 | 5 | 5 | 106,726 | 0.9999992043 |
| 10 | 0.459379 | 0.207253 | 8.050 | 10 | 10 | 10 | 201,240 | 0.9999984996 |
| 20 | 0.519200 | 0.264404 | 14.992 | 20 | 20 | 20 | 374,798 | 0.9999972056 |
| 30 | 0.550875 | 0.298297 | 21.395 | 30 | 30 | 30 | 534,880 | 0.9999960121 |
| **50** | **0.589621** | **0.341086** | **33.157** | **50** | **50** | **50** | **828,935** | **0.9999938197** |
| 100 | 0.643748 | 0.411032 | 56.894 | 100 | 100 | 100 | 1,422,354 | 0.9999893954 |

The comparison denominator is 134,126,287,365 same-country pairs. Reduction
ratio is `1 - candidate_pairs / same_country_pairs`; at cap 50 this is also a
161,805.6-fold reduction.

At the selected cap, S2 link recall is 0.618189 (25,891 of 41,882 links)
and S3 link recall is 0.562750 (25,057 of 44,526 links). The explicit
25,000-row miss audit contains 9,447 complete rows, 3,444 cap-truncation
misses, 1,205 rows with no candidates, 9,135 rows whose true IDs had no
retrieval evidence, and 1,769 mixed cap/evidence misses.

## Cap decision

The selector accepts an increment only while its marginal cost is at most 100
additional candidate pairs per additional recovered truth link. Measured costs
for 5→10, 10→20, 20→30, 30→50, and 50→100 were respectively 17.1, 33.6,
58.5, 87.8, and 126.9. The selected cap is therefore **50**. This removes
593,419 loop pairs (41.7%) relative to cap 100 while retaining the measured
knee, rather than assuming the largest cap is safest.

Cap selection used only `loop`. The committed split stays at exactly 25,000
IDs. The Phase 1 `report` run is performed once at cap 50 and is not used to
revise the cap.

## One Phase 1 readiness report

The single frozen `report` run at the already-selected cap 50 covered 220,677
S1 IDs and measured 0.591701 link recall and 0.342995 complete-entity recall.
Candidate width was mean 33.189, p95 50, p99 50, and maximum 50, for 7,324,037
total pairs. Against 1,183,941,282,489 same-country comparisons, the reduction
ratio was 0.9999938139 (161,651.5-fold). The candidate artifact SHA-256 was
`045374644663db8187fbe50de59e674b00ca0a57dbd35a83d52c291aa46ec304`.
These confirmation results did not alter the cap or any retrieval setting.

The batched FTS optimization was accepted only after regenerating all 25,000
loop rows and reproducing the original candidate TSV byte-for-byte (SHA-256
`480b9837be3da424c240b7eb55595be16602cce4e5d0f9c7447fa44116739902`).

## Matcher handoff

The final two-column candidate file and pair-level provenance schema are frozen
in [CANDIDATE_CONTRACT.md](CANDIDATE_CONTRACT.md). `candidate_pairs.tsv` is the
exact set Person 4 scores, not a wider intermediate union. Submission validation
must prove every predicted ID is contained in its S1 row's candidate list.
