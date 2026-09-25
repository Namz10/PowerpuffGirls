# Amazon ML Challenge 2026 — problem reading and research map

This note records what the official materials actually say, what the training files contain, and what exists in the market and in the literature for the same kind of problem.

It does not choose a model, a blocking method, features, a threshold, or an evaluation design. Those decisions come later, after the task is clear.

Sources read in full:

- `docs/Problem Statement.pdf` (8 pages)
- `docs/guidelines_and_key_instructions_amazon_ml_challenge_2026.pdf` (2 pages)
- `docs/Documentation_template.md`
- `docs/validate_submission.py`
- `README.md` (one line: “Business Entity Resolution Challenge”)
- Headers and full-file counts from the four training TSVs in the repo root

The problem-statement PDF says “refer to this video” and the guidelines say “walk through the blog for ML Challenge on best practices and live demo.” Those hyperlinks did not survive text extraction, and a web search did not turn up a confirmed 2026 video URL or best-practices blog URL. Those two resources are unread.

---

## 1. What the task is

Entity resolution here means: records from independent systems describe the same real-world business, but they share no common ID, and the text fields disagree.

The required answer is narrower than “cluster every record in the world.”

**Source 1 is already a deduplicated reference list.** For each Source 1 business, return every Source 2 record and every Source 3 record that is the same real-world business.

One Source 1 row may match:

- nothing (a singleton),
- one record,
- or many records, and those records may come from Source 2, Source 3, or both.

Matches are not one-to-one. The same Source 2 or Source 3 record could, in principle, be a correct match for more than one Source 1 row; the problem statement does not forbid that, and it does not say it happens. That has not been checked in the files.

Source 1 records are never matched to other Source 1 records. The output may contain only `S2-` and `S3-` IDs.

The only fields you may use are the ones in the files:

| Field | Role |
|---|---|
| `entity_id` | Unique within the files. Prefix is the source: `S1-`, `S2-`, `S3-`. There is no separate source column. |
| `business_name` | Noisy name: abbreviations, legal suffixes, typos, transliteration, and the other name noise listed below. |
| `business_address` | Noisy address: partial, reordered, abbreviated, landmark-based, missing pieces. |
| `country` | A string label. Train contains `US` and `India` only. Test adds `France`, which never appears in training. |

Country is an open set of labels. The statement forbids hard-coding, filtering, or one-hot encoding the pipeline to only `{US, India}`. Every test Source 1 entity, including every France entity, must have a row in the submission.

There is no phone, domain-as-a-structured-field, registration number, PIN as its own column, latitude, or industry code. A website string can appear inside `business_name` (seen in a sample row). That is still just the name field.

---

## 2. What the task is not

- It is not “deduplicate Source 1.” Source 1 is already the reference.
- It is not “produce one cluster ID for every record across all three files.” The scored object is a set of Source 2/3 IDs for each Source 1 ID.
- It is not “find the single best match.” Cardinality is variable, including zero.
- It is not a lookup against a business registry, a map API, or the public web. That is explicitly disqualifying. See section 7.
- It is not three separate binary classifiers with a fixed output size. Each Source 1 entity has its own list, and that list can be empty.

---

## 3. Noise the statement tells you to expect

Names:

- Abbreviations: Corp / Corporation, Pvt / Private, Ltd / Limited
- Legal-suffix inconsistencies
- DBA / trade names
- Punctuation: `&` versus `and`
- Word-order transpositions
- Typos

Addresses:

- Abbreviations: Rd / Road, St / Street
- Transliteration variants
- Missing components, including no PIN and no state
- Landmark references, example given: “Near SBI ATM”
- Municipal numbering formats
- Component reordering

The statement does not give a complete noise inventory. A few rows inspected while checking the file format also show Devanagari names, a Kannada token inside an India address, a leading `--` on a US name, a `.com` string used as the business name, an empty address, a US address with city/state before the street, and a misspelling (`Tetlecommunication`). Those are samples, not a census. A full noise study has not been done.

---

## 4. Files and measured training size

The statement’s paths are `dataset/train/` and `dataset/test/`. In this workspace the four training files sit at the repo root. No test files are in the repo.

All files are tab-separated. Commas appear inside addresses and inside the ID-list column, so a comma reader will silently collapse a row into one field. Read with `sep="\t"`.

Measured from the training files on 25 Sep 2026 (data rows, header excluded):

| File | Rows | `US` | `India` | Empty name | Empty address | Empty country |
|---|---:|---:|---:|---:|---:|---:|
| `train_source1.tsv` | 2,206,821 | 1,323,633 | 883,188 | 0 | 0 | 0 |
| `train_source2.tsv` | 5,034,616 | 3,016,817 | 2,017,799 | 0 | 168,967 | 0 |
| `train_source3.tsv` | 5,285,603 | 3,170,056 | 2,115,547 | 0 | 175,916 | 0 |
| `train_ground_truth.tsv` | 2,206,821 | — | — | — | — | — |

Longest observed strings: name 105 / 104 / 123 characters (S1 / S2 / S3); address 256 / 249 / 240.

Ground truth has one row per Source 1 entity. Column 2 is a comma-separated list of matching `S2-` / `S3-` IDs, or empty.

Match-list sizes in training ground truth:

| Matches per Source 1 entity | Entities |
|---|---:|
| 0 (singleton) | 123,247 |
| 1 | 119,157 |
| 2–3 | 906,053 |
| 4–5 | 806,072 |
| 6–10 | 252,255 |
| 11 or more | 37 |
| Maximum list length | 11 |

Link totals: 7,638,365 positive links. Average list length 3.46, including singletons. Of those links, 3,693,619 point at Source 2 and 3,944,746 point at Source 3. No ID had a prefix other than `S2-` or `S3-`. No list contained a repeated ID.

How those non-empty lists are composed:

| Pattern | Entities |
|---|---:|
| Both Source 2 and Source 3 | 1,776,047 |
| Source 2 only | 143,029 |
| Source 3 only | 164,498 |
| Empty | 123,247 |

Naive comparison of every Source 1 row with every Source 2 or Source 3 row is about 2.2 million × 10.3 million pairs. The statement’s “tips” section says blocking sets the recall ceiling for that reason. `candidate_pairs.tsv` exists so reviewers can measure that ceiling (recall of the candidate set) and the reduction ratio. It is not a leaderboard file.

Test size is not in the repo. The validator comment says the full test set is on the order of 1.7 million entities and that loading all Source 2/3 IDs for an existence check costs a few GB. “1.7 million entities” is the validator author’s figure for the test set as a whole; it is not a measured count from files we have.

France exists only in test. Nothing in the training counts above describes France.

---

## 5. What you must submit

Two TSV files. Only the first is scored.

### `matching_results.tsv` (leaderboard)

Header, exactly, tab-separated:

`source1_entity_id` tab `matched_entity_ids`

One row for every Source 1 entity in the test file. The second column is a comma-separated list of Source 2 and Source 3 IDs, with no quoting. Empty second column means “no match.”

### `candidate_pairs.tsv` (not scored; required in the final zip)

Header:

`source1_entity_id` tab `candidate_entity_ids`

Same row rules. This file is the candidate set the matching model actually scores at inference time. If the pipeline blocks in several stages, this is the last stage, not an earlier superset that you later filter before the model. Every ID in `matching_results.tsv` should appear in the candidate list for that Source 1 entity. The validator warns if it does not. The warning does not fail validation. A missing candidate file does not fail the local validator, but the final zip must still contain `output/candidate_pairs.tsv`.

### Final zip, after the live leaderboard uploads

```
<team_name>_submission.zip
├── output/
│   ├── matching_results.tsv
│   └── candidate_pairs.tsv
├── code/
│   └── business_entity_resolution/
│       ├── src/
│       ├── README.md          # reproduce data → blocking → matching → both outputs
│       └── requirements.txt   # pinned versions
└── Documentation_template.md  # filled in; pdf export also accepted; do not rename
```

The code folder must be enough for someone else to regenerate both output files from the provided train and test data.

The methodology write-up must cover: methodology, candidate generation / blocking, model architecture and feature engineering, and anything else relevant. The template also asks for an executive summary, error analysis (false merges vs missed matches), and the validation F_0.5. The template says there is no page limit and to prefer clarity and technical depth. The guidelines PDF separately asks for a 1–2 page document. Both requests are in the official PDFs. They are not reconciled in those PDFs.

### Format rules that reject a submission

From the problem statement, and re-checked in `validate_submission.py`:

1. Tab-separated UTF-8 text. A comma-separated file is the failure the validator calls out first.
2. Exact headers, lowercased after strip. Wrong header stops parsing.
3. Every test Source 1 ID appears exactly once. Missing IDs reject. Extra IDs reject. Duplicate Source 1 rows reject.
4. No duplicate IDs inside one list.
5. No `S1-` IDs in a match or candidate list. IDs must start with `S2-` or `S3-`.
6. IDs should exist in the test Source 2/3 files. The statement says non-existent IDs “will be rejected.” The validator’s own comment says a missing or garbage matched ID only lowers the score and does not reject, and that the existence check is off unless `--check-ids` is passed. Those two sentences disagree. Treat existence as required; do not rely on the softer comment.
7. Empty list is valid and means no match. The validator counts empty rows; it does not treat them as errors.

Self-matches and duplicate rows are hard errors in the validator. Unknown IDs are errors only when `--check-ids` is on.

---

## 6. How scoring works

The leaderboard metric is given. It is not a choice.

**Macro F_0.5.** For each Source 1 entity, compute precision and recall of the predicted ID set against the true ID set, then

```
F_0.5 = (1.25 × Precision × Recall) / (0.25 × Precision + Recall)
```

Average that number across all Source 1 entities in the evaluation set, singletons included.

Worked example from the statement: prediction `{S2-00047, S2-00193, S3-00812}`, truth `{S2-00047, S3-00812}` → precision 2/3, recall 1, F_0.5 = 0.714.

Why this formula: a false merge of two different businesses is treated as more damaging than a missed link. With β = 0.5, precision is weighted more than recall. The statement’s wording is “weights precision 2× over recall.”

Singletons are part of the average:

- Truth is empty and you predict empty → 1.0 for that entity.
- Truth is empty and you predict any ID → 0.0 for that entity.

The statement tells you to hold out a validation split from training and score it yourself with this same formula. It does not specify how to split (random entities, by country, by name frequency, or otherwise).

Leaderboards:

- During the challenge, the public rank uses a subset of the test set.
- After the challenge, the private rank uses the remaining portion.
- You always upload predictions for the full test set. The organizers apply the split at scoring time.
- The problem statement says the final decision is the private leaderboard.
- The guidelines say evaluation and shortlisting use performance across both leaderboards, and that after artefacts, leaderboard score, and eligibility, the top 100 teams are announced. Those top 100 then submit methodology, blocking strategy, architecture, and feature engineering — which is the same content the zip’s documentation already asks for.

Public rank is a partial view. A method that fits the public slice and fails on the private slice loses under the problem statement’s final-decision rule.

Submission budget from the guidelines: at most 5 leaderboard submissions per day, for 3 days. Keep every version. Shortlisting uses the submitted solutions, and source code may be required again later.

Window: 25 September 2026, 12:00 AM IST, through 27 September 2026, 11:59 PM IST.

Other operational rules from the guidelines: desktop or laptop only, one machine per participant, no simultaneous logins, no second account. Queries go to the Google Form mentioned in the guidelines; the form URL was not in the extracted text. Technical problems go to support@unstop.com with a screenshot and the registered email. Organizers will not make modeling decisions by email.

A search result points at an Unstop listing: https://unstop.com/hackathons/crp-amazon-ml-challenge-2026-amazon-1743604/coding-challenge/290344 . The page body was not retrieved, so this note does not treat that URL as an extra rule source.

---

## 7. Hard constraints

1. **No external identity lookup.** Prohibited: commercial entity-resolution APIs, government business registries, geocoding APIs, and any internet augmentation of the records. Pipelines are reviewed. Evidence of external lookup is immediate disqualification. The allowed data is the provided training data.
2. **Model license and size.** The final model must be MIT or Apache 2.0, and at most 8 billion parameters.
3. **Reproducibility.** Top teams’ zips are reviewed before final rankings are confirmed: rerun, blocking audit, fair-play check, license check.
4. **Cheating.** Multiple IDs, plagiarism, and the lookup rule above are disqualifying.

The market products in section 9 are maps of how the industry frames this problem. Calling them, or calling a registry or a geocoder, on this dataset is a fair-play violation. Reading their public docs to understand blocking, match grades, and failure modes is not the same act as sending these records to them.

---

## 8. Where the two official PDFs do not say the same thing

Recorded so they are not smoothed over:

| Topic | Problem statement | Guidelines |
|---|---|---|
| What decides the rank | “The final decision will be based on the private leaderboard.” | “Evaluation and shortlisting will be based on performance across both leaderboards.” Then top 100 are announced. |
| Write-up length | Template: no page limit; clarity and depth. | “1–2-page document” as an artefact of the best solution. |
| Who is reviewed | “Top teams’ packages are reviewed in detail before the final rankings are confirmed.” | Top 100 submit methodology details after shortlisting. |

Nothing else in the local files resolves these. Do not invent a resolution.

---

## 9. Points that are easy to miss

- The scored unit is the Source 1 entity, not the pair. A model can be strong on pairs and still lose if singleton decisions or list precision are wrong.
- An empty prediction on a singleton is a full point. A single false ID on that same entity is a zero. There are 123,247 training singletons (about 5.6% of Source 1).
- Most training entities have more than one true match, and most of those touch both Source 2 and Source 3. A pipeline that returns only the top-1 ID cannot represent the training labels.
- Blocking recall is a ceiling. A true pair that never enters `candidate_pairs.tsv` can never be recovered by the matcher. That file is audited.
- `candidate_pairs.tsv` is defined as the model’s inference input, not as “everything blocking ever emitted.”
- France is unseen. Any step that only knows US and India address grammar, or that drops unknown country strings, fails the written rule even before accuracy.
- Source 2 and Source 3 contain on the order of 170k–176k empty addresses each. Source 1 does not. Name is never empty in training. Matching cannot assume both sides have an address.
- IDs are the only join key you are given, and they do not join across sources. String fields are the evidence.
- The validator’s default run does not prove that your IDs exist. Pass `--check-ids` when you want that check, and expect high memory if the candidate file is included.
- Five submissions a day means a broken TSV wastes a slot. The validator exists to catch that before upload.
- License cap is on the model you submit, not on whatever paper you read.

---

## 10. Market systems that solve this kind of problem

These products match organization or customer records that lack a shared key. They are not interchangeable with this challenge: almost all of them also enrich from a private reference graph, which this challenge forbids. Links were retrieved 25 Sep 2026. Product pages move; if a link dies, search the product name.

| System | What it claims to do | Link |
|---|---|---|
| Dun & Bradstreet match / D-U-N-S | Match a name and address to a D&B company record and a D-U-N-S number. Confidence grades, country-specific rules. | https://docs.dnb.com/direct/2.0/en-US/company/5.0/match/rest-API |
| D&B Connect Discover | Stewardship UI on top of that match-and-enrich flow. | https://www.dnb.com/en-us/products/dnb-connect/dnb-connect-discover.html |
| AWS Entity Resolution | Managed rule-based and ML matching across your own tables. Amazon’s product in this category; it is not the hackathon. | https://aws.amazon.com/entity-resolution/ and https://aws.amazon.com/blogs/aws/aws-entity-resolution-match-and-link-related-records-from-multiple-applications-and-data-stores/ |
| Senzing | Embeddable real-time resolution SDK aimed at people and organizations, with its own entity-centric scoring. | https://senzing.com/ |
| Quantexa | Batch and dynamic resolution plus a graph, sold heavily for financial crime. | https://www.quantexa.com/platform/entity-resolution-software/ |
| Tamr | AI-assisted mastering and golden records, human curation on the hard pairs. | https://www.tamr.com/entity-resolution |
| Informatica MDM (CLAIRE matching) | Enterprise MDM: deterministic and probabilistic match, survivorship, stewardship. | https://www.informatica.com/products/master-data-management.html |
| Reltio | Cloud MDM with real-time match and a persistent entity ID. | https://www.reltio.com/ |
| SAS Data Quality / entity resolution | Long-standing commercial match-merge. | https://www.sas.com/en_us/software/data-quality.html |
| WinPure | Desktop / server match-merge for business files. | https://winpure.com/ |
| DataMatch Enterprise (Data Ladder) | No-code cleanse, dedupe, and golden record on structured business files. Their 2026 comparison roundup is useful as a map and is vendor-authored. | https://dataladder.com/ and https://dataladder.com/best-entity-resolution-software/ |
| Global Database | Resolve a company to a government registration number and enrich from registries. | https://www.globaldatabase.com/master-data-management |
| Zephira | Same pattern: registry identity as the anchor, then dedupe. | https://zephira.ai/solutions/master-data-entity-resolution/ |
| Tilores | API for real-time identity search and link. | https://tilores.io/ |
| OpenCorporates reconciliation | Reconcile a company name to a legal entity in public registries. Using it on this data would be external lookup. | https://opencorporates.com/ and https://api.opencorporates.com/ |
| Dedupe.io | Hosted product around the open-source `dedupe` library. | https://dedupe.io/ |

Industry pattern, visible across these pages: normalize, block, score a pair, threshold, then a human reviews the middle band. The valuable idea for a three-day build is that split of labor. The disallowed idea is borrowing their reference data.

---

## 11. Open-source systems for the same pipeline shape

Useful as code to study. Check the license before any weight or library ships in the zip. The challenge requires the final model to be MIT or Apache 2.0. AGPL code (Zingg) is a legal question, not a default.

| System | Role | License note from the project page | Link |
|---|---|---|---|
| Splink | Fellegi–Sunter probabilistic linkage, DuckDB or Spark. Strong when you have several weakly dependent fields. The authors say it is a poor fit for a single bag-of-words column. This challenge has name, address, and country only. | MIT | https://github.com/moj-analytical-services/splink and https://moj-analytical-services.github.io/splink/ |
| dedupe | Active learning, affine gap distance on strings, blocking predicates. Designed for name-and-address files. Scale target is smaller than 10M×2M. | MIT (confirm in repo before use) | https://github.com/dedupeio/dedupe and https://docs.dedupe.io/ |
| Zingg | Spark ER: blocking plus a similarity classifier, active learning, non-English names including Hindi. | AGPL-3.0 | https://github.com/zinggAI/zingg |
| Python Record Linkage Toolkit | Indexing (blocking) and comparison features, pandas-scale. | — | https://recordlinkage.readthedocs.io/ |
| Magellan / py_entitymatching | End-to-end EM: blockers, string features, classical classifiers. The research system behind a large fraction of the papers below. | — | https://sites.google.com/site/anhaidgroup/projects/magellan |
| deepmatcher | The deep models from the Magellan design-space paper. | — | https://github.com/anhaidgroup/deepmatcher |
| Ditto | Pair classifier fine-tuned from a pretrained language model. | — | https://github.com/megagonlabs/ditto |
| JedAI / pyJedAI | Toolkit that implements many published blockers and matchers so they can be compared. | — | https://github.com/scify-org/JedAIToolkit |
| Sparkly | Industrial TF-IDF blocking that the 2024 blocking generalization paper treats as a strong non-neural baseline. | — | Paper: https://aclanthology.org/2024.naacl-long.483.pdf (cites Paulsen et al., 2023) |

A vendor survey of open-source tools, useful as a directory and not as an independent benchmark: https://www.zingg.ai/post/top-10-open-source-entity-resolution-tools-2026

---

## 12. Research papers

Grouped by the part of this problem they speak to. “Relevant” means the paper studies blocking, matching, business/name/address linkage, multilingual names, or precision-oriented decisions. It does not mean the paper’s dataset is this dataset, or that its F1 number transfers.

### Foundations

- Fellegi and Sunter, “A Theory for Record Linkage,” JASA 1969. The probabilistic model behind Splink and most commercial match weights. https://doi.org/10.1080/01621459.1969.10501049
- Christen, *Data Matching* (Springer, 2012). The textbook for blocking, string comparison, and classification. https://link.springer.com/book/10.1007/978-3-642-31164-2
- Christophides, Efthymiou, Palpanas, Papadakis, Stefanidis, “An Overview of End-to-End Entity Resolution for Big Data,” ACM Computing Surveys, 2020. https://doi.org/10.1145/3418896
- Papadakis, Skoutas, Thanos, Palpanas, “Blocking and Filtering Techniques for Entity Resolution: A Survey,” ACM Computing Surveys, 2020. The blocking map. https://doi.org/10.1145/3377455 — PDF also circulates as https://arxiv.org/pdf/1905.06167
- Li, Liu, Zhang, Wang, Wan, “A Survey on Blocking Technology of Entity Resolution,” JCST 2020. https://doi.org/10.1007/s11390-020-0350-4
- Elmagarmid, Ipeirotis, Verykios, “Duplicate Record Detection: A Survey,” IEEE TKDE 2007. Older, still the right survey for string-edit features. https://doi.org/10.1109/TKDE.2007.250581
- Getoor and Machanavajjhala, “Entity Resolution: Theory, Practice & Open Challenges,” VLDB tutorial. http://www.vldb.org/pvldb/vol5/p2018_getoor_machanavajjhala_vldb2012.pdf

### Classical systems and company-name practice

- Konda et al., “Magellan: Toward Building Entity Matching Management Systems,” PVLDB 2016. Includes a real company-name-and-address matching discussion: same name at different addresses can be a branch, not a non-match. https://pages.cs.wisc.edu/~anhai/papers1/magellan-sigmodrec18.pdf and https://dl.acm.org/doi/10.14778/2994509.2994535
- Papadakis, Ioannou, Palpanas, “Entity Resolution: Past, Present, and Yet-to-Come,” EDBT 2020 tutorial-style talk. https://openproceedings.org/2020/conf/edbt/60.pdf
- Gormley, “Probabilistic Record Linkage Using Pretrained Text Embeddings,” and the Splink paper: Linacre et al., “Splink: Free software for probabilistic record linkage at scale,” IJPDS 2022. https://doi.org/10.23889/ijpds.v7i3.1794

### Neural matching

- Mudgal, Li, Rekatsinas, Doan, et al., “Deep Learning for Entity Matching: A Design Space Exploration” (DeepMatcher), SIGMOD 2018. The result that matters here: deep models did not beat classical ML on clean structured data, and did help on textual and dirty data. This challenge is dirty text. https://dl.acm.org/doi/10.1145/3183713.3196926 — PDF: https://dm-gatech.github.io/CS8803-Fall2018-DML-Papers/deepmatcher-space-exploration.pdf
- Ebraheem, Thirumuruganathan, Joty, Ouzzani, Tang, “Distributed Representations of Tuples for Entity Resolution” (DeepER), PVLDB 2018. https://doi.org/10.14778/3236187.3236198
- Li, Li, Suhara, Doan, Tan, “Deep Entity Matching with Pre-Trained Language Models” (Ditto), PVLDB 2020. Pair serialization plus a pretrained LM. https://www.vldb.org/pvldb/vol14/p50-li.pdf — arXiv: https://arxiv.org/abs/2004.00584
- Li, Li, Suhara, Doan, Tan, “Deep Entity Matching: Challenges and Opportunities,” SIGMOD Record 2021. States the open problems: blocking and matching are still separate, labels are expensive, explanations matter, and “same company” is broader than “same string.” https://doi.org/10.1145/3431816
- Yao et al. / the HierGAT line: “Entity Resolution with Hierarchical Graph Attention Networks,” SIGMOD 2022. Uses neighboring candidates, not only the pair. https://doi.org/10.1145/3514221.3517872
- Wang, Zhang, et al., Sudowoodo: contrastive self-supervision for blocking and matching with few labels. arXiv: https://arxiv.org/abs/2112.06049 — code: https://github.com/megagonlabs/sudowoodo
- Brinkmann, Shraga, Bizer, “SC-Block: Supervised Contrastive Blocking within Entity Resolution Pipelines.” https://arxiv.org/abs/2309.03202

### Language-model blocking, which is the scale problem

- Thirumuruganathan et al., “Deep Learning for Blocking in Entity Matching: A Design Space Exploration” (DeepBlocker), PVLDB 2021. Embedding retrieval as blocking, including methods that do not need pair labels. https://www.vldb.org/pvldb/vol14/p2459-thirumuruganathan.pdf
- Zeakis, Papadakis, Skoutas, Koubarakis, “An in-depth analysis of pre-trained embeddings for entity resolution,” VLDB Journal 2024 (conference version PVLDB 2023). Twelve embedding models, blocking and matching, schema-aware vs concatenated text. https://link.springer.com/article/10.1007/s00778-024-00879-4 — earlier: https://arxiv.org/abs/2302.02003
- Wang and Zhang, “Pre-trained Language Models for Entity Blocking: A Generalization Study,” NAACL 2024. Directly about whether a blocker survives a shift in the data. France-unseen is that kind of shift. https://aclanthology.org/2024.naacl-long.483.pdf
- Borthwick, Golac, et al., neural LSH blocking. Cited from the NAACL 2024 paper; confirm the exact PDF before relying on a number. https://doi.org/10.1137/1.9781611978032.101
- A structured review of 54 LM-era matching papers: “Entity Matching in the Era of Language Models: A Structured Literature Review,” 2025. https://doi.org/10.1109/cscs66924.2025.00061

### Company names, addresses, and scripts

- “CompanyDepot: Employer Name Normalization in the Online Recruitment Industry,” KDD 2016. The industrial version of legal-suffix and trade-name noise. https://dl.acm.org/doi/10.1145/2939672.2939727
- “A Hybrid Approach to Company Name Disambiguation” and related affiliation-parsing work. Useful for legal-form tokens; do not assume a paper about academic affiliations is a paper about shopfronts. Search title before citing a number.
- Libpostal is the standard open statistical address parser (training data is OpenAddresses / OpenStreetMap derived). Using a geocoding API is forbidden. Whether shipping parser weights counts as external data augmentation is a fair-play question to treat conservatively: the rule names geocoding APIs and internet augmentation, and it does not name offline libraries. Do not decide that by assumption. Project: https://github.com/openvenues/libpostal
- Indic / transliteration: the training sample already contains Devanagari names and a Kannada address token. General-purpose references, not ER papers: IndicNLP and AI4Bharat transliteration models. https://github.com/AI4Bharat/IndicXlit — any model weights still have to satisfy the MIT/Apache and 8B rules, and an offline normalizer is not a license to call a translation API.

### Benchmarks people will be tempted to quote

These are the public ER benchmarks. They are smaller, cleaner, and mostly product or citation data. A number on them is not a prediction for this challenge.

- Magellan data: https://sites.google.com/site/anhaidgroup/useful-stuff/the-magellan-data-repository
- WDC Product matching: http://webdatacommons.org/largescaleproductcorpus/v2/
- Leipzig company / affiliation datasets are sometimes used for organization linking; verify the exact corpus before citing it.

A third party has mirrored this challenge’s statement text on Hugging Face: https://huggingface.co/datasets/logicalguy/amazon-ml-challenge-2026 . That page is not an official rule source. Pulling extra records from the internet, including a mirror, collides with the external-data rule.

---

## 13. Other material that is actually usable

- The local validator, `docs/validate_submission.py`. It is the executable form of the format rules. Read it before the first upload.
- The documentation template, `docs/Documentation_template.md`. It tells you what the reviewers will look for: blocking keys, candidate-pair count, how true matches were kept, name features, address features, threshold method, false merges, false misses.
- Christen’s book and the Papadakis blocking survey, if only two references are read. They are about the part the statement itself flags: candidate generation sets the recall ceiling, and the metric then punishes extra IDs.
- DeepMatcher’s negative result on structured data, and Ditto’s result on dirty text. Together they say “neural” is not automatically the better matcher for every field type. That is a fact from those papers, not a model choice for this contest.
- The NAACL 2024 generalization study, because France is an explicit distribution shift and public-vs-private is a second hidden shift.
- Splink’s documentation on term-frequency adjustments. A token like “Inc” or “Pvt” that appears everywhere should not count as much as a rare distinctive token. That mechanism is why probabilistic linkage still shows up in production next to neural rankers.
- Senzing’s public “principles of entity resolution” essays (entity-centric scoring, why pairwise thresholds drift). Conceptual, not a code dependency. Start at https://senzing.com/

---

## 14. What was not verified

- The challenge video and the best-practices blog. Links were not recoverable from the PDFs.
- The Unstop page body and the Google Form URL.
- Any test file. France is known only from the problem statement.
- Whether a Source 2/3 ID is ever a true match for more than one Source 1 ID.
- A full pass over noise types. Section 3’s script-mixing and empty-address notes are either a few printed rows or a full-file count, and the section says which.
- Leaderboard submission mechanics beyond the two PDFs (portal quirks, file size caps).
- License of every GitHub repo above. “MIT” is only stated where the project page said so in the search result. Re-read the license file before depending on it.
- The claim of “over 25k teams.” That number is not in the local PDFs. It is not confirmed or denied here.

No model, parameter, blocking key, or threshold is recommended in this file. The metric is already fixed by the organizers; there is nothing to select.
