# Person 2: Entity Representation & Text Normalization Methodology

**Project:** Amazon ML Challenge 2026 — Business Entity Resolution  
**Role:** Person 2 — Name and Address Representation  
**Downstream Consumers:** Person 3 (Candidate Generation / Blocking) & Person 4 (Matching / Classification)  
**Owned Subsystem:** `src/represent/`

---

## 1. Scope & Ownership

### 1.1 Core Mission
Person 2 owns the **shared canonical view** of every record across all three data sources (`Source 1`, `Source 2`, `Source 3`). In entity resolution, raw text suffers from typographic noise, inconsistent abbreviations, legal entity variants, formatting anomalies, landmark notations, and multilingual/accented characters. 

The primary deliverable is a deterministic transformation pipeline that converts noisy raw records into standardized **Canonical Records** and derived token metadata, preventing downstream components (blocking and matching) from writing redundant or conflicting ad-hoc string cleaners.

```
+------------------+      +-----------------------+      +-------------------------------+
| Raw Input Record | ---> | Person 2: Normalizer  | ---> |       Canonical Record        |
| (Name, Addr, Co) |      | (Deterministic Rules) |      | (Clean Name, Addr, Flags, ...) |
+------------------+      +-----------------------+      +-------------------------------+
                                                                 |                 |
                                                                 v                 v
                                                          Person 3 (Blocking)   Person 4 (Matching)
```

### 1.2 Boundary of Responsibility
- **What Person 2 OWNS:**
  - Standardized normalization functions for business names and addresses.
  - Open-country normalization rules (handling training labels `US`, `India`, and test-set additions such as `France` or unseen countries).
  - Corpus-wide boilerplate vs. distinctive token frequency extraction from training data.
  - Derived token annotations (e.g., empty address flags, landmark indicators, postal/PIN code extraction).
  - Unit and integration test suites, smoke test packs, and before/after transformation audit reports.
- **What Person 2 DOES NOT DO:**
  - Candidate generation / Blocking (Owned by Person 3).
  - Pairwise similarity computation, scoring, or match thresholding (Owned by Person 4).
  - Official macro $F_{0.5}$ evaluation and global error slicing (Owned by Person 1).
  - Modifying files outside `src/represent/`.

---

## 2. Technology Stack & Design Rationale

| Component / Layer | Technology Chosen | Technical Rationale |
|---|---|---|
| **Programming Language** | Python 3.11 | Standard across team workflow; provides optimized regex engines and unicode support. |
| **I/O & Data Structures** | `pandas` (with explicit `sep='\t'`, `quoting=csv.QUOTE_NONE`) | Handles TSV format safely without accidental delimiter corruption from commas inside address strings. |
| **Text Processing & Regex** | Standard Library `re`, `unicodedata`, `string` | Zero runtime external dependencies, deterministic behavior, maximum processing throughput, zero model licensing ambiguities (MIT/Apache 2.0 compliant). |
| **Unicode & Script Standardization** | `unicodedata.normalize("NFKC", ...)` | Decomposes composite characters, strips non-printable control symbols, standardizes full-width Latin/punctuations into standard ASCII/Latin equivalents. |
| **Token Mining & Frequency** | `collections.Counter` | High-efficiency frequency aggregation across millions of tokens without heavy NLP dependencies. |
| **Unit & Integration Testing** | `pytest` | Automated regression detection, property testing (idempotency, determinism, crash safety). |
| **Configuration Management** | `config.py` with dynamic directory discovery | Decouples absolute paths from codebase, ensuring portability across Windows and Linux environments. |

---

## 3. Why NOT Large Language Models (LLMs) for Person 2 Normalization?

A critical architectural decision was made to **avoid LLMs** for the bulk normalization and representation stage. The rationale is based on four concrete engineering factors:

### 3.1 Throughput, Latency & Scale
- **Dataset Volume:** The dataset contains millions of records across Source 1, Source 2, and Source 3 (test sets scale into multi-millions).
- **Processing Time:** Even a quantized, lightweight local LLM running at 100 iterations/sec would require **over 35 hours of non-stop GPU inference** to process 12.5 million rows.
- **Deterministic Rule Engine:** In contrast, optimized Python compiled regular expressions and string tables process **10,000 to 50,000 records per second per CPU core**, normalizing the entire dataset in minutes with zero GPU requirements.

### 3.2 Strict Determinism and Idempotency ($f(f(x)) = f(x)$)
- LLMs are probabilistic generation engines. Even at temperature $0$, small variations in prompt formatting or tokenization boundaries can yield divergent outputs for identical entities across runs.
- Rule-based normalization provides mathematical guarantees of idempotency: running `normalize_name(normalize_name(x))` produces the exact same string as `normalize_name(x)`.

### 3.3 Elimination of Hallucinations and Information Loss
- LLMs frequently "correct" rare, unusual, or typo-ridden business names into popular, unrelated brand names (e.g., normalizing `"Amzon Retail"` to `"Amazon.com Inc."` or altering distinctive building/plot numbers).
- In entity resolution, preserving unique entity tokens (such as plot numbers, ward codes, and unique proprietor surnames) is essential for Person 4's high-precision matching. Rule engines standardize structural noise (e.g. `Pvt Ltd` $\rightarrow$ `private limited`) while preserving critical entity identifiers.

### 3.4 Challenge Constraints & Reproducibility
- Competition rules require offline submission reproducibility, bounded compute packages, and strict parameter limits (<= 8B parameters total across the solution).
- By keeping Person 2 completely rule-based and lightweight, the team preserves 100% of compute and memory budgets for downstream blocking and matching algorithms.

---

## 4. Detailed Methodology & Pipeline Architecture

```
                                  +-----------------------+
                                  |   Raw Input Record    |
                                  | (name, addr, country) |
                                  +-----------------------+
                                              |
                                              v
                              +-------------------------------+
                              |    Unicode NFKC & Encoding    |
                              |    - NFKC Normalization       |
                              |    - Control Character Strip  |
                              |    - Lowercase Canonical Form |
                              +-------------------------------+
                                              |
                     +------------------------+------------------------+
                     |                                                 |
                     v                                                 v
   +------------------------------------+            +------------------------------------+
   |     Name Normalization Engine      |            |    Address Normalization Engine    |
   | - Ampersand/Symbol Conversion      |            | - Empty/Null Address Detection     |
   | - Junk Prefix Removal (M/s, etc.)  |            | - Street/Unit Abbrev Expansion     |
   | - Legal Suffix Standardization     |            | - Landmark Signal Extraction       |
   | - Punctuation & Whitespace Cleanup |            | - PIN/ZIP Code Isolation           |
   | - Distinctive Token Extraction     |            | - Punctuation & Whitespace Cleanup |
   +------------------------------------+            +------------------------------------+
                     |                                                 |
                     +------------------------+------------------------+
                                              |
                                              v
                              +-------------------------------+
                              |     Country-Open Rules        |
                              | - Known (US, India) Rules     |
                              | - Unseen (France/Generic)     |
                              | - CEDEX/Postal Heuristics     |
                              +-------------------------------+
                                              |
                                              v
                              +-------------------------------+
                              |   Canonical Record Assembly   |
                              | - Clean Name & Clean Address  |
                              | - Metadata & Boolean Flags    |
                              | - Distinctive Token Lists     |
                              +-------------------------------+
```

### 4.1 Unicode & Character Standardization
1. **NFKC Normalization:** All text passes through `unicodedata.normalize("NFKC", text)` to decompose composite characters and standardize full-width representations.
2. **Control Character Removal:** Strips non-printable ASCII/Unicode control characters (`\x00-\x1f`, `\x7f-\x9f`).
3. **Casing:** Converts all strings to lowercase for case-insensitive downstream processing.

### 4.2 Business Name Normalization (`normalize_name.py`)
1. **Symbol & Conjunction Normalization:** Converts `&` and `+` to the universal token `and` surrounded by clean spaces.
2. **Junk Prefix Stripping:** Identifies and strips common formal prefixes that do not contribute to business identity (e.g., `m/s`, `messrs`, `the`, `shree`, `sri` when used as pure noise prefixes, domain prefixes like `http://`, `www.`).
3. **Legal Suffix Canonicalization:** Maps multi-word and abbreviated legal structures to canonical expanded or standardized forms using a structured lookup table:
   - `pvt ltd`, `p. ltd`, `pvt. limited` $\rightarrow$ `private limited`
   - `ltd`, `l.t.d.` $\rightarrow$ `limited`
   - `inc`, `inc.` $\rightarrow$ `incorporated`
   - `corp`, `corp.` $\rightarrow$ `corporation`
   - `llc`, `l.l.c.` $\rightarrow$ `limited liability company`
   - `co`, `co.` $\rightarrow$ `company`
   - `gmbh`, `sarl`, `sa`, `bv` (European/International variants)
4. **Punctuation & Delimiter Handling:** Replaces non-alphanumeric characters (hyphens, slashes, periods, commas, quotes) with single spaces while preventing concatenated word merges.
5. **Whitespace Collapsing:** Collapses multiple consecutive whitespace characters into a single space and trims leading/trailing boundaries.

### 4.3 Address Normalization (`normalize_address.py`)
1. **Missing / Empty Address Handling:** Accurately identifies `None`, `NaN`, `"nan"`, `""`, and whitespace-only addresses. Emits an empty string `""` (never `NaN`) and sets `is_empty_address = True`.
2. **Street & Locality Abbreviation Expansion:** Expands standard address abbreviations:
   - `rd`, `rd.` $\rightarrow$ `road`
   - `st`, `st.` $\rightarrow$ `street`
   - `ave`, `ave.` $\rightarrow$ `avenue`
   - `blvd` $\rightarrow$ `boulevard`
   - `bldg` $\rightarrow$ `building`
   - `apt`, `ste` $\rightarrow$ `suite`
   - `flr`, `fl` $\rightarrow$ `floor`
   - `opp`, `opp.` $\rightarrow$ `opposite`
   - `nr`, `nr.` $\rightarrow$ `near`
3. **Landmark Signal Extraction:** Detects presence of relative landmarks (`near`, `opposite`, `behind`, `beside`, `adjacent to`) and flags `has_landmark_ref = True`.
4. **Postal & Postal Code Preservation:** Identifies and preserves 6-digit Indian PIN codes, 5-digit US ZIP codes, and 5-digit French postal codes so they remain contiguous tokens for Person 3's blocking index.

### 4.4 Country-Open & Unseen Country Adaptability (`country_rules.py`)
- **Training Labels:** `US`, `India`.
- **Test Label Addition:** `France`, plus potential unseen country labels.
- **Design Policy:**
  - Country labels are treated as an open set — records are never filtered out or discarded due to an unfamiliar country tag.
  - Applies a fallback generic rule pipeline to unknown country strings.
  - France-specific heuristic: Identifies French `CEDEX` (Courrier d'Entreprise à Distribution Exceptionnelle) postal routing tokens and flags `is_cedex = True`.
  - India-specific heuristic: Validates 6-digit PIN codes (`^[1-9][0-9]{5}$`).
  - US-specific heuristic: Validates 5-digit ZIP codes (`^[0-9]{5}$`).

### 4.5 Boilerplate vs. Distinctive Token Resource (`build_token_resource.py`)
- Mined strictly from the training partition across all three source datasets (`train_source1.tsv`, `train_source2.tsv`, `train_source3.tsv`).
- Calculates corpus-wide document frequency ($DF$) for every unique token in names and addresses.
- **Classification Rules:**
  - **Boilerplate Tokens:** Tokens appearing in $> 1.0\%$ of records (e.g., `limited`, `private`, `road`, `street`, `floor`, `india`, `usa`, `services`).
  - **Distinctive Tokens:** Rare, high-entropy tokens (e.g., brand names, specific surnames, unique geographic identifiers).
- Exports a structured JSON/TSV resource that Person 3 uses for TF-IDF/weighted inverted indexing and Person 4 uses for weighted token-overlap feature calculation.

---

## 5. Module Specification: Inputs, Outputs & Operations

### 5.1 `normalize_name.py`
- **Inputs:** `raw_name: str`
- **Operations:**
  1. Unicode NFKC normalization and lowercasing.
  2. Conjunction expansion (`&` $\rightarrow$ `and`).
  3. Junk prefix removal.
  4. Legal entity suffix mapping to canonical forms.
  5. Punctuation stripping and whitespace collapsing.
  6. Extraction of distinct name tokens.
- **Outputs:** `(normalized_name: str, name_tokens: List[str])`

### 5.2 `normalize_address.py`
- **Inputs:** `raw_address: str`
- **Operations:**
  1. Missing/NaN detection.
  2. Unicode NFKC normalization and lowercasing.
  3. Abbreviation dictionary substitution with boundary regex (`\b(rd|st|ave|bldg)\b`).
  4. Landmark keyword pattern matching.
  5. Postal/PIN code extraction.
  6. Tokenization and deduplicated address token set generation.
- **Outputs:** `(normalized_address: str, address_tokens: List[str], is_empty: bool, has_landmark: bool, postal_code: Optional[str])`

### 5.3 `country_rules.py`
- **Inputs:** `country_label: str`, `normalized_address: str`
- **Operations:**
  1. Case-insensitive country label normalization.
  2. Dispatch to specific country rule handlers (`US`, `India`, `France`, or `Generic Fallback`).
  3. Extraction of region-specific postal codes and routing indicators (e.g. `CEDEX`).
- **Outputs:** `country_metadata: Dict[str, Any]` (containing validated postal code, country code, and regional flags).

### 5.4 `canonical_record.py` & `canonical_record_batch.py`
- **Inputs:** Raw input row or DataFrame containing `entity_id`, `business_name`, `business_address`, `country`.
- **Operations:**
  1. Orchestrates name normalizer, address normalizer, and country rules.
  2. Compiles derived tokens, boolean flags, and cleaned strings into a unified schema.
  3. Supports single-record execution and vectorized/batched chunk processing.
- **Outputs:** Canonical Record Dictionary / DataFrame with the fixed contract:
  - `entity_id`: Raw ID unchanged (e.g. `S1-000123`).
  - `country`: Normalized country tag.
  - `normalized_name`: Standardized clean business name.
  - `normalized_address`: Standardized clean address (empty string if missing).
  - `derived_tokens`: Structured dictionary / JSON containing `name_tokens`, `address_tokens`, `is_empty_address`, `has_landmark_ref`, `postal_code`, `is_cedex`.

### 5.5 `build_token_resource.py`
- **Inputs:** `train_source1.tsv`, `train_source2.tsv`, `train_source3.tsv`
- **Operations:**
  1. Iterates over training corpus names and addresses.
  2. Computes unigram frequency distributions.
  3. Sets frequency thresholds ($> 1\%$ frequency for boilerplate).
  4. Saves token classification dictionary with metadata.
- **Outputs:** `token_frequencies.json` / `boilerplate_tokens.json` for Person 3 & Person 4.

### 5.6 `before_after_report.py`
- **Inputs:** Difficulty pack or sample dataset (`smoke_difficulty_set.py`).
- **Operations:**
  1. Runs canonical normalization across edge-case entities.
  2. Generates a side-by-side comparison table showing original strings vs. normalized strings.
  3. Computes change summary metrics and flag distributions.
- **Outputs:** `before_after_report.md` / console audit table for team review.

---

## 6. Verification, Quality Assurance & Edge-Case Coverage

To ensure zero regressions across downstream consumers, the normalization module is validated by automated test suites and smoke sets covering the following challenge-specific edge cases:

```
+---------------------------------------------------------------------------------------+
|                              Edge-Case Coverage Matrix                                |
+-----------------------------------+---------------------------------------------------+
| Challenge Noise Pattern           | Normalizer Behavior / Guarantee                   |
+-----------------------------------+---------------------------------------------------+
| Legal Suffix Variants             | Standardizes "Corp", "Corporation", "Inc", "LLC"   |
| Conjunction Variations            | Converts "&", "+", "and" into uniform "and"       |
| Accented Latin (e.g., Café, SA)  | Preserved or NFKC normalized without string loss  |
| Empty / NaN Addresses             | Converted to "" with is_empty_address=True flag   |
| Landmark Indicators (near/opp)    | Standardized and flagged with has_landmark=True   |
| Word Order Inversions             | Normalized tokens collected for set comparison    |
| French CEDEX Routing Codes        | Detected and isolated in derived metadata         |
| Indian 6-Digit PIN Codes          | Extracted and validated into postal_code field    |
| US 5-Digit ZIP Codes              | Extracted and validated into postal_code field    |
| Idempotency Guarantee             | f(f(x)) == f(x) verified across all inputs        |
+-----------------------------------+---------------------------------------------------+
```

---

## 7. Downstream Handoff Contracts

| Consumer | Provided Artefacts | Usage in Pipeline |
|---|---|---|
| **Person 3 (Blocking)** | `normalized_name`, `normalized_address`, `postal_code`, `boilerplate_tokens.json` | Used to generate candidate blocking keys (e.g., prefix blocking, PIN code blocks, distinctive token inverted index). |
| **Person 4 (Matching)** | `normalized_name`, `normalized_address`, `derived_tokens`, `is_empty_address` | Used to compute high-precision pairwise similarity features (e.g., Jaro-Winkler, Levenshtein, distinctive token overlap, landmark matching). |
| **Person 1 (Evaluation)** | `before_after_report.py`, transformation audit logs | Used for error diagnosis on false-positive and false-negative evaluation slices. |
