# Phase 2 handoff — Person 2 (Shriya)

Status: **Representation implementation complete; Phase 2 Person 2 handoff ready**

This handoff describes the completed representation subsystem owned by Person 2 (Shriya) in Phase 2 as specified in [final_build_plan.md](final_build_plan.md).

---

## 1. Scope & Ownership

* **Owner:** Shriya (Person 2)
* **Owned Subsystems:** `src/represent/`, `tests/represent/`, `artifacts/resources/`, `docs/representation_before_after_report.md`
* **Normalizer Version:** `2.0.0`
* **Downstream Consumers:** 
  * Person 3 (Srishti — Candidate Generation / Blocking)
  * Person 4 (Namita — Match Decisions / Pair Features)
  * Person 1 (Dishita — Evaluation & Release Gate)

---

## 2. Completed Deliverables

### 2.1 Canonical Record Schema & Transformation Contract
* Implemented in `src/represent/canonical_record.py`.
* Transforms raw entities from Source 1, Source 2, and Source 3 into a standardized, deterministic `CanonicalRecord`:
  * `entity_id`: Raw entity ID.
  * `source`: Provenance (`source1`, `source2`, `source3`).
  * `country`: Normalized country tag (open equality label).
  * `normalized_name`: NFKC-normalized, lowercase, junk-prefix stripped name.
  * `romanized_name`: Fully romanized phonetic representation for Indic scripts (equal to normalized name for Latin).
  * `accent_folded_name`: Accent-folded Latin view (diacritics stripped for Latin; Indic characters preserved).
  * `normalized_address`: Standardized street/locality names, expanded abbreviations, stripped noise.
  * `source_script`: Dominant detected script (`devanagari`, `bengali`, `gujarati`, `tamil`, `telugu`, `kannada`, `malayalam`, `latin`).
  * `postal_code`: Extracted 6-digit Indian PIN, 5-digit US ZIP, or 5-digit French postal code.
  * `is_empty_address`: `True` if address is empty, `None`, or whitespace-only.
  * `has_landmark_ref`: `True` if address contains relative landmark indicators (`near`, `opp`, `behind`, `beside`).
  * `is_cedex`: `True` if French CEDEX routing is present.
  * `name_tokens`: Ordered list of distinctive name tokens.
  * `address_tokens`: Ordered list of address tokens.
  * `normalizer_version`: `"2.0.0"`.

### 2.2 Deterministic Offline Indic Romanization
* Implemented in `src/represent/romanization.py`.
* Complete Brahmic abugida transliteration covering **7 Indic scripts**:
  1. Devanagari (Hindi, Marathi, Sanskrit)
  2. Bengali (Bengali, Assamese)
  3. Gujarati
  4. Tamil
  5. Telugu
  6. Kannada
  7. Malayalam
* Accurately models independent vowels, dependent matras, virama/halant inherent-vowel cancellation, anusvara (`m`/`n`), visarga (`h`), and preserves unknown code points and ASCII numbers/symbols without data loss.

### 2.3 French Rule Set
* Implemented in `src/represent/normalize_name.py` and `src/represent/normalize_address.py`.
* Legal entity forms: `SAS`, `SASU`, `EURL`, `SCI`, `SNC`, `SC`, `SARL`, `SA`.
* Routing and postal: `BP` / `boîte postale` $\rightarrow$ `bp`, 5-digit French postal code extraction, and `CEDEX` routing detection.
* Ordinals: `1er`, `1ère`, `2ème`, `3ème` $\rightarrow$ `1`, `2`, `3`.

### 2.4 Token Resources & Boilerplate Mining
* Generated under `artifacts/resources/`:
  * `name_idf.json`: Per-country smoothed inverse document frequency ($IDF$) for name tokens.
  * `address_idf.json`: Per-country smoothed $IDF$ for address tokens.
  * `boilerplate_tokens.json`: Corpus-wide high-frequency boilerplate tokens ($> 1\%$ frequency) per country.
  * `manifest.json`: Version contract (`2.0.0`), supported scripts, and SHA-256 fingerprints.
* Mining policy strictly obeys rules:
  * US and India: Mined strictly from training sources (`train_source1`, `train_source2`, `train_source3`).
  * France: Mined strictly using provided France test text without labels.

### 2.5 Audit Report & Test Suite
* Side-by-side transformation audit report: `docs/representation_before_after_report.md`.
* Automated test suite under `tests/represent/` (23 tests, 100% green):
  * `test_romanization.py`: Script transliteration & code-point preservation.
  * `test_french_rules.py`: French legal forms, ordinals, BP, and CEDEX.
  * `test_idempotency.py`: Mathematical idempotency $f(f(x)) = f(x)$.
  * `test_canonical_record.py`: Record assembly & open-country behavior.
  * `test_token_resource.py`: IDF computation & serialization.
  * `test_golden_smoke.py`: Golden multi-lingual test pack.

---

## 3. Downstream Handoff Contracts

| Consumer | Provided Deliverables | How Downstream Role Should Use Them |
|---|---|---|
| **Person 3 (Srishti)** | `normalized_name`, `romanized_name`, `postal_code`, `artifacts/resources/boilerplate_tokens.json` | Use for candidate blocking keys: exact name blocks, romanized name blocks, rare token inverted indexing (skipping boilerplate), and postal code retrieval. |
| **Person 4 (Namita)** | `CanonicalRecord` schema, `accent_folded_name`, `name_tokens`, `artifacts/resources/name_idf.json` | Use for pair-feature extraction: Levenshtein ratio, Jaro-Winkler similarity, IDF-weighted Jaccard overlap, and script match indicators. |
| **Person 1 (Dishita)** | `source_script`, `is_cedex`, `representation_before_after_report.md` | Use for error slicing (evaluating Indic vs. Latin slices, CEDEX/France slices) and release gate auditing. |

---

## 4. Verification Commands

Run from the repository root:

```bash
# 1. Run all Person 2 representation unit and golden tests
python -m unittest -v tests.represent.test_romanization tests.represent.test_french_rules tests.represent.test_idempotency tests.represent.test_canonical_record tests.represent.test_token_resource tests.represent.test_golden_smoke

# 2. Run the interactive representation demo
python -m src.represent.inspect_demo

# 3. Rebuild canonical token resources and audit report anytime
python -m src.represent.build_canonical_artifacts
```
