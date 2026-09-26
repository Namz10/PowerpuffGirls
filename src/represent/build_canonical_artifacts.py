"""Person 2 script to build token resources, version fingerprints, and before/after report."""

import json
import time
from pathlib import Path
from typing import Dict, List
import pandas as pd

from src.eval.fingerprint import sha256_file
from src.represent.config import dataset_dir, resource_dir, REPO_ROOT, NORMALIZER_VERSION
from src.represent.canonical_record import transform_single_record
from src.represent.token_resource import TokenResource, compute_idf_and_boilerplate_from_tokens


def build_representation_artifacts():
    print("=== Person 2: Building Canonical Representation Artifacts ===")
    start_time = time.time()
    
    train_d = dataset_dir("train")
    test_d = dataset_dir("test")
    res_d = resource_dir()
    
    # 1. Mine tokens from train datasets for US and India
    print(f"Reading train dataset from {train_d}...")
    s1_path = train_d / "train_source1.tsv"
    s2_path = train_d / "train_source2.tsv"
    s3_path = train_d / "train_source3.tsv"

    name_tokens_by_country: Dict[str, List[List[str]]] = {"US": [], "India": []}
    addr_tokens_by_country: Dict[str, List[List[str]]] = {"US": [], "India": []}

    for path, src_name in [(s1_path, "source1"), (s2_path, "source2"), (s3_path, "source3")]:
        if path.exists():
            print(f"Sampling tokens from {path.name}...")
            df = pd.read_csv(path, sep="\t", quoting=3, nrows=100000)
            for _, row in df.iterrows():
                rec = transform_single_record(
                    entity_id=str(row.get("entity_id", "")),
                    raw_name=str(row.get("business_name", "")) if pd.notna(row.get("business_name")) else "",
                    raw_address=str(row.get("business_address", "")) if pd.notna(row.get("business_address")) else None,
                    raw_country=str(row.get("country", "")) if pd.notna(row.get("country")) else None,
                    source=src_name,
                )
                c = rec.country if rec.country in ("US", "India") else "US"
                name_tokens_by_country[c].append(rec.name_tokens)
                addr_tokens_by_country[c].append(rec.address_tokens)

    # 2. Mine France test text (no labels) strictly for France IDF
    print(f"Reading France text from {test_d} for France IDF...")
    france_name_tokens: List[List[str]] = []
    france_addr_tokens: List[List[str]] = []
    for test_name in ["test_source1.tsv", "test_source2.tsv", "test_source3.tsv"]:
        test_path = test_d / test_name
        if test_path.exists():
            df_test = pd.read_csv(test_path, sep="\t", quoting=3, nrows=50000)
            for _, row in df_test.iterrows():
                country_val = str(row.get("country", "")) if pd.notna(row.get("country")) else ""
                if country_val.strip().lower() in ("france", "fr", "fra"):
                    rec = transform_single_record(
                        entity_id=str(row.get("entity_id", "")),
                        raw_name=str(row.get("business_name", "")) if pd.notna(row.get("business_name")) else "",
                        raw_address=str(row.get("business_address", "")) if pd.notna(row.get("business_address")) else None,
                        raw_country="France",
                    )
                    france_name_tokens.append(rec.name_tokens)
                    france_addr_tokens.append(rec.address_tokens)

    if france_name_tokens:
        name_tokens_by_country["France"] = france_name_tokens
        addr_tokens_by_country["France"] = france_addr_tokens

    # 3. Compute IDF and boilerplate
    print("Computing smoothed IDF and boilerplate dictionaries...")
    name_idf, name_bp = compute_idf_and_boilerplate_from_tokens(name_tokens_by_country)
    addr_idf, addr_bp = compute_idf_and_boilerplate_from_tokens(addr_tokens_by_country)

    # Combine boilerplate
    combined_bp = {
        c: sorted(list(name_bp.get(c, set()).union(addr_bp.get(c, set()))))
        for c in sorted(set(name_bp.keys()).union(addr_bp.keys()))
    }

    token_res = TokenResource(name_idf, addr_idf, combined_bp)
    token_res.save(res_d)
    print(f"Saved token resources to {res_d}")

    # 4. Generate Before/After Transformation Audit Report
    print("Generating before/after transformation audit report...")
    sample_cases = [
        # Indian cases & Indic scripts
        ("S1-IN01", "M/s Reliance Industries Pvt. Ltd.", "Near MG Road, Bangalore 560001", "India"),
        ("S1-IN02", "टाटा कंसल्टेंसी सर्विसेज लिमिटेड", "मुंबई महाराष्ट्र", "India"),
        ("S1-IN03", "ಕರ್ನಾಟಕ ಎಂಟರ್ಪ್ರೈಸಸ್", "ಬೆಂಗಳೂರು", "India"),
        ("S1-IN04", "தமிழ்நாடு நிறுவனம்", "சென்னை 600001", "India"),
        ("S1-IN05", "భారత్ ఎలక్ట్రానిక్స్ లిమిటెడ్", "హైదరాబాద్", "India"),
        ("S1-IN06", "বাংলা ট্রেডার্স", "কলকাতা 700001", "India"),
        ("S1-IN07", "ગુજરાત ટેક્સટાઈલ્સ", "અમદાવાદ", "India"),
        ("S1-IN08", "കേരള ആയുർവേദ", "കൊച്ചി", "India"),
        # French cases
        ("S1-FR01", "L'Oréal S.A.S.", "15 Boulevard Haussmann, 75440 CEDEX 09, Paris", "France"),
        ("S1-FR02", "Boulangerie Moderne E.U.R.L.", "12 1er étage, Boîte Postale 45, Lyon", "France"),
        ("S1-FR03", "Immobilier Parisien S.C.I.", "8 3ème Avenue, 75008 Paris", "France"),
        ("S1-FR04", "Transport Rapide S.N.C.", "BP 102, Marseille", "France"),
        # US cases & edge cases
        ("S1-US01", "Google LLC & Co.", "1600 Amphitheatre Pkwy, Mountain View, CA 94043", "US"),
        ("S1-US02", "Acme Corporation", "", "US"),
        ("S1-US03", "Smith & Sons Incorporated", "Suite 400, 5th Fl., New York, NY 10001", "US"),
    ]

    report_lines = [
        "# Person 2: Representation & Normalization Before/After Audit Report",
        "",
        f"**Normalizer Version:** `{NORMALIZER_VERSION}`  ",
        f"**Generated:** `{time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}`  ",
        "",
        "## Transformation Sample Matrix",
        "",
        "| ID | Country | Raw Name | Normalized / Romanized Name | Script | Raw Address | Normalized Address | Postal / Flags |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for eid, r_name, r_addr, r_country in sample_cases:
        rec = transform_single_record(eid, r_name, r_addr, r_country)
        flags = []
        if rec.postal_code:
            flags.append(f"postal={rec.postal_code}")
        if rec.is_empty_address:
            flags.append("empty_addr")
        if rec.has_landmark_ref:
            flags.append("landmark")
        if rec.is_cedex:
            flags.append("cedex")
        flag_str = ", ".join(flags) if flags else "-"
        
        display_name = rec.romanized_name if rec.source_script != "latin" else rec.accent_folded_name
        report_lines.append(
            f"| `{eid}` | {rec.country} | {r_name} | **{display_name}** | `{rec.source_script}` | {r_addr or '*(empty)*'} | {rec.normalized_address or '*(empty)*'} | {flag_str} |"
        )

    report_path = REPO_ROOT / "docs" / "representation_before_after_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Audit report written to {report_path}")

    # 5. Create Resource Manifest with SHA-256 fingerprints
    manifest = {
        "version": NORMALIZER_VERSION,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "resources": {
            "name_idf": {
                "path": "artifacts/resources/name_idf.json",
                "sha256": sha256_file(res_d / "name_idf.json"),
            },
            "address_idf": {
                "path": "artifacts/resources/address_idf.json",
                "sha256": sha256_file(res_d / "address_idf.json"),
            },
            "boilerplate_tokens": {
                "path": "artifacts/resources/boilerplate_tokens.json",
                "sha256": sha256_file(res_d / "boilerplate_tokens.json"),
            },
        },
        "supported_indic_scripts": [
            "devanagari", "bengali", "gujarati", "tamil", "telugu", "kannada", "malayalam"
        ],
        "supported_french_entities": ["SAS", "SASU", "EURL", "SCI", "SNC", "SC", "SARL", "SA"],
        "runtime_seconds": round(time.time() - start_time, 2),
    }

    manifest_path = res_d / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest written to {manifest_path}")
    print("=== Person 2 deliverables complete ===")


if __name__ == "__main__":
    build_representation_artifacts()
